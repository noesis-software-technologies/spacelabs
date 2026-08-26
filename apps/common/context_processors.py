"""Expose quelques réglages au gabarit (drapeaux runtime côté client)."""
from django.conf import settings


def cockpit_flags(request):
    return {
        "resume_on_boot": settings.COCKPIT_RESUME_ON_BOOT,
        "stt_backend": settings.COCKPIT_STT_BACKEND,
    }
