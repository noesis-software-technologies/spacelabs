"""Authentication for machine-to-machine ingestion, independent of browser sessions."""
from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.utils.crypto import constant_time_compare


def require_ingress_secret(setting_name, header_name):
    """Fail closed when unconfigured; never accept a session or the shared LAN cookie."""
    def decorate(view):
        @wraps(view)
        def authenticated(request, *args, **kwargs):
            expected = getattr(settings, setting_name, "")
            supplied = request.headers.get(header_name, "")
            if not expected or not supplied or not constant_time_compare(supplied, expected):
                return JsonResponse({"error": "forbidden"}, status=403)
            return view(request, *args, **kwargs)

        return authenticated

    return decorate
