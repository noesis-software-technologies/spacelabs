"""Crée le workspace Mohamed avec 2 agents dédiés (idempotent)."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.workspaces.models import HeadlessPane, Workspace


class Command(BaseCommand):
    help = "Crée le workspace Mohamed (Sonnet 4.6 + Opus 4.6) s'il n'existe pas."

    def handle(self, *args, **options):
        User = get_user_model()
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            self.stderr.write("Aucun superutilisateur — lancez d'abord `make setup`.")
            return

        ws, created = Workspace.objects.get_or_create(
            owner=user,
            slug="mohamed",
            defaults={"name": "Mohamed", "cwd": "~"},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Workspace '{ws.name}' créé."))
        else:
            self.stdout.write(f"Workspace '{ws.name}' déjà présent.")

        agents = [
            ("claude-sonnet-4-6", "Mohamed · Sonnet"),
            ("claude-opus-4-6",   "Mohamed · Opus"),
        ]
        for model_id, title in agents:
            pane, pane_created = HeadlessPane.objects.get_or_create(
                workspace=ws,
                title=title,
                defaults={
                    "model_id": model_id,
                    "prompt_initial": (
                        f"Tu es un agent IA dans le workspace Mohamed. "
                        f"Modèle : {model_id}. Réponds en français."
                    ),
                },
            )
            if pane_created:
                self.stdout.write(self.style.SUCCESS(f"  Agent créé : {pane.title} ({model_id})"))
            else:
                self.stdout.write(f"  Agent déjà présent : {pane.title}")
