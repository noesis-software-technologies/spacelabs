"""S1: real HTTP ingress rejects unauthenticated writes, including with CSRF enforced."""
import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from apps.comms.models import Message
from apps.models_routing.models import OpenclawExchangeLog


SECRET = "test-only-dedicated-ingress-secret"
RUNTIME = "/routage/openclaw-stats/log/"
TELEGRAM = "/comms/telegram/webhook/"
ENDPOINTS = [
    (RUNTIME, "COCKPIT_OPENCLAW_LOG_TOKEN", "HTTP_X_SPACELABS_RUNTIME_TOKEN"),
    (TELEGRAM, "COMMS_TG_WEBHOOK_SECRET", "HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN"),
]
TELEGRAM_UPDATE = {
    "update_id": 123,
    "message": {"message_id": 42, "chat": {"id": -123},
                "from": {"username": "sender"}, "text": "Un devis ?"},
}
pytestmark = pytest.mark.django_db


@pytest.fixture
def ingress(settings):
    settings.COCKPIT_LAN_TOKEN = ""
    settings.COCKPIT_OPENCLAW_LOG_TOKEN = SECRET
    settings.COMMS_TG_WEBHOOK_SECRET = SECRET
    return Client(enforce_csrf_checks=True)


def assert_no_writes():
    assert Message.objects.count() == 0
    assert OpenclawExchangeLog.objects.count() == 0


@pytest.mark.parametrize("url,setting,header", ENDPOINTS)
@pytest.mark.parametrize("supplied", [None, "wrong-token"])
def test_ingress_authenticates_before_parsing(ingress, url, setting, header, supplied):
    headers = {} if supplied is None else {header: supplied}
    response = ingress.post(url, data="invalid-json", content_type="application/json", **headers)
    assert response.status_code == 403
    assert_no_writes()


@pytest.mark.parametrize("url,setting,header", ENDPOINTS)
def test_unconfigured_endpoint_is_disabled(ingress, settings, url, setting, header):
    setattr(settings, setting, "")
    assert ingress.post(url, data={}, content_type="application/json",
                        **{header: SECRET}).status_code == 403
    assert_no_writes()


@pytest.mark.parametrize("url,setting,header", ENDPOINTS)
def test_login_is_not_an_ingress_credential(ingress, url, setting, header):
    user = get_user_model().objects.create_user(username="operator", password="test")
    ingress.force_login(user)
    assert ingress.post(url, data={}, content_type="application/json").status_code == 403
    assert_no_writes()


@pytest.mark.parametrize("url,setting,header", ENDPOINTS)
def test_only_post_is_accepted(ingress, url, setting, header):
    assert ingress.get(url, **{header: SECRET}).status_code == 405
    assert_no_writes()


@pytest.mark.parametrize("url,setting,header", ENDPOINTS)
@pytest.mark.parametrize("body", ["broken", "[]", "null", "12", '"text"', b"\xff"])
def test_authenticated_malformed_payload_is_400(ingress, url, setting, header, body):
    assert ingress.post(url, data=body, content_type="application/json",
                        **{header: SECRET}).status_code == 400
    assert_no_writes()


def test_runtime_accepts_dedicated_secret_without_browser_session(ingress):
    response = ingress.post(RUNTIME, data={"prompt_tokens": "12", "completion_tokens": 3},
                            content_type="application/json", HTTP_X_SPACELABS_RUNTIME_TOKEN=SECRET)
    assert response.status_code == 200
    assert OpenclawExchangeLog.objects.get().total_tokens == 15


@pytest.mark.parametrize("bad", [-1, 2_147_483_648, True, 1.2, None, {}, "-1", "99999999999"])
@pytest.mark.parametrize("field", ["prompt_tokens", "completion_tokens"])
def test_runtime_rejects_invalid_token_counts(ingress, bad, field):
    response = ingress.post(RUNTIME, data={field: bad}, content_type="application/json",
                            HTTP_X_SPACELABS_RUNTIME_TOKEN=SECRET)
    assert response.status_code == 400
    assert_no_writes()


@pytest.mark.parametrize("payload", [{"session_id": []}, {"model_id": "x" * 101}])
def test_runtime_rejects_invalid_fields(ingress, payload):
    assert ingress.post(RUNTIME, data=payload, content_type="application/json",
                        HTTP_X_SPACELABS_RUNTIME_TOKEN=SECRET).status_code == 400
    assert_no_writes()


def test_telegram_repeated_delivery_creates_one_message(ingress):
    for _ in range(2):
        response = ingress.post(TELEGRAM, data=TELEGRAM_UPDATE, content_type="application/json",
                                HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=SECRET)
        assert response.status_code == 200
    message = Message.objects.get()
    assert message.ext_id == "tg--123-42"
    assert message.corps == "Un devis ?"
    assert message.needs_reply


@pytest.mark.parametrize("message", [[], {}, {"chat": {}},
    {"chat": {"id": -123}, "message_id": 1, "text": []},
    {"chat": {"id": -123}, "message_id": 1, "from": {"username": None}},
])
def test_telegram_invalid_message_is_not_persisted(ingress, message):
    response = ingress.post(TELEGRAM, data={"message": message}, content_type="application/json",
                            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=SECRET)
    assert response.status_code == 400
    assert_no_writes()


def test_telegram_other_updates_are_acknowledged_without_write(ingress):
    response = ingress.post(TELEGRAM, data=json.dumps({"update_id": 1}),
                            content_type="application/json",
                            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=SECRET)
    assert response.status_code == 200
    assert_no_writes()


def test_ingress_credentials_are_separate(ingress, settings):
    settings.COMMS_TG_WEBHOOK_SECRET = "telegram-specific-secret"
    assert ingress.post(TELEGRAM, data=TELEGRAM_UPDATE, content_type="application/json",
                        HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=SECRET).status_code == 403
    assert_no_writes()


@pytest.mark.parametrize("url,setting,header", ENDPOINTS)
def test_lan_cookie_does_not_replace_ingress_secret(ingress, settings, url, setting, header):
    settings.COCKPIT_LAN_TOKEN = "test-only-lan-secret"
    ingress.cookies["cockpit_lan"] = settings.COCKPIT_LAN_TOKEN
    assert ingress.post(url, data={}, content_type="application/json").status_code == 403
    assert_no_writes()


@pytest.mark.parametrize("url,setting,header", ENDPOINTS)
def test_ingress_does_not_bypass_existing_lan_guard(ingress, settings, url, setting, header):
    settings.COCKPIT_LAN_TOKEN = "test-only-lan-secret"
    assert ingress.post(url, data={}, content_type="application/json",
                        **{header: SECRET}).status_code == 403
    assert_no_writes()
