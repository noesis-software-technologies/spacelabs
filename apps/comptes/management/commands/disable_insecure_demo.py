"""Révoque uniquement le compte démo qui utilise encore le secret public connu."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from .bootstrap_demo import DEMO_PASSWORD, DEMO_USERNAME


class Command(BaseCommand):
    help = (
        "Désactive 'pilote' uniquement si son mot de passe est encore celui de la démo ; "
        "préserve les comptes absents, déjà révoqués ou dont le secret a été changé."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        user = (
            get_user_model().objects.select_for_update()
            .filter(username=DEMO_USERNAME).first()
        )
        if user is None or not user.check_password(DEMO_PASSWORD):
            self.stdout.write("Aucun compte démo vulnérable à désactiver — rien à faire.")
            return
        user.set_unusable_password()
        user.is_active = False
        user.is_staff = False
        user.is_superuser = False
        user.save(update_fields=["password", "is_active", "is_staff", "is_superuser"])
        self.stdout.write(self.style.SUCCESS(
            "Compte démo désactivé, privilèges retirés et mot de passe révoqué."
        ))
