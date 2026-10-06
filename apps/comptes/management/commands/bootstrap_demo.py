"""Crée l'opérateur local de démo (idempotent) — cf. README `make setup`."""
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


DEMO_USERNAME = "pilote"
DEMO_PASSWORD = "cockpit-local"


class Command(BaseCommand):
    help = "Crée l'utilisateur local 'pilote' (mot de passe : cockpit-local) s'il n'existe pas."

    def handle(self, *args, **options):
        # settings.SETTINGS_MODULE may be shadowed by Django's UserSettingsHolder class attr (None)
        # inside override_settings; fall back to env var only when not explicitly overridden.
        active_module = settings.SETTINGS_MODULE or os.environ.get("DJANGO_SETTINGS_MODULE", "")
        if active_module != "config.settings.dev" or not settings.DEBUG:
            raise CommandError(
                "bootstrap_demo est réservé à config.settings.dev avec DEBUG=True. "
                "En production, utiliser createsuperuser avec un mot de passe unique."
            )
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=DEMO_USERNAME, defaults={"is_staff": True, "is_superuser": True}
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
            self.stdout.write(self.style.SUCCESS("Utilisateur 'pilote' créé (mdp : cockpit-local)."))
        else:
            self.stdout.write("Utilisateur 'pilote' déjà présent — rien à faire.")
