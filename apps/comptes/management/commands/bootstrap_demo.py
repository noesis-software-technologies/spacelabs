"""Crée l'opérateur local de démo (idempotent) — cf. README `make setup`."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crée l'utilisateur local 'pilote' (mot de passe : cockpit-local) s'il n'existe pas."

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username="pilote", defaults={"is_staff": True, "is_superuser": True}
        )
        if created:
            user.set_password("cockpit-local")
            user.save()
            self.stdout.write(self.style.SUCCESS("Utilisateur 'pilote' créé (mdp : cockpit-local)."))
        else:
            self.stdout.write("Utilisateur 'pilote' déjà présent — rien à faire.")
