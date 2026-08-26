"""Endpoint /voice/transcribe/."""
import io

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="pilote", password="x")


def _audio(content=b"RIFFfakeaudio"):
    f = io.BytesIO(content)
    f.name = "audio.webm"
    return f


@pytest.mark.django_db
def test_requires_login(client, settings):
    settings.COCKPIT_STT_BACKEND = "fake"
    assert client.post(reverse("voice:transcribe")).status_code == 302


@pytest.mark.django_db
def test_get_not_allowed(client, user, settings):
    settings.COCKPIT_STT_BACKEND = "fake"
    client.force_login(user)
    assert client.get(reverse("voice:transcribe")).status_code == 405


@pytest.mark.django_db
def test_webspeech_backend_rejects_server_transcribe(client, user, settings):
    settings.COCKPIT_STT_BACKEND = "webspeech"
    client.force_login(user)
    r = client.post(reverse("voice:transcribe"), {"audio": _audio()})
    assert r.status_code == 400


@pytest.mark.django_db
def test_missing_audio_field(client, user, settings):
    settings.COCKPIT_STT_BACKEND = "fake"
    client.force_login(user)
    r = client.post(reverse("voice:transcribe"))
    assert r.status_code == 400


@pytest.mark.django_db
def test_fake_transcription_roundtrip(client, user, settings):
    settings.COCKPIT_STT_BACKEND = "fake"
    settings.COCKPIT_STT_FAKE_TRANSCRIPT = "reschedule the thursday meeting"
    client.force_login(user)
    r = client.post(reverse("voice:transcribe"), {"audio": _audio()})
    assert r.status_code == 200
    assert r.json() == {"text": "reschedule the thursday meeting"}
