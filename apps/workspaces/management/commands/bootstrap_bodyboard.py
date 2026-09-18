"""Crée le workspace BodyBoard avec 2 agents dédiés (idempotent)."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.workspaces.models import HeadlessPane, Workspace


class Command(BaseCommand):
    help = "Crée le workspace BodyBoard (Sonnet 4.6 + Opus 4.6) s'il n'existe pas."

    def add_arguments(self, parser):
        parser.add_argument("--user", default="noelabs", help="Username propriétaire du workspace (défaut: noelabs)")

    def handle(self, *args, **options):
        User = get_user_model()
        username = options["user"]
        user = User.objects.filter(username=username).first() or User.objects.filter(is_superuser=True).order_by("id").last()
        if not user:
            self.stderr.write("Aucun utilisateur trouvé — lancez d'abord `make setup`.")
            return
        self.stdout.write(f"Propriétaire : {user.username}")

        existing = Workspace.objects.filter(slug="bodyboard").exclude(owner=user).first()
        if existing:
            existing.owner = user
            existing.save()
            self.stdout.write(self.style.WARNING(f"Workspace 'BodyBoard' réassigné à {user.username}."))

        ws, created = Workspace.objects.get_or_create(
            owner=user,
            slug="bodyboard",
            defaults={
                "name": "BodyBoard",
                "cwd": "/home/noesis/bodyboard",
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Workspace '{ws.name}' créé."))
        else:
            self.stdout.write(f"Workspace '{ws.name}' déjà présent.")

        CONTEXTE = (
            "Tu travailles sur le projet BodyBoard — une plateforme Django/htmx où un "
            "créateur publie une campagne et des marques achètent des emplacements à prix "
            "fixe sur son corps, ses textiles ou ses contenus. "
            "Repo : github.com/noesis-software-technologies/bodyboard (branche prod). "
            "Règles fondamentales : le design system ne se réécrit pas (bodyboard.css verbatim), "
            "aucun style/script inline, le queryset filtré est l'autorisation, "
            "le navigateur ne marque jamais un paiement, un refus ne libère pas l'emplacement. "
            "Modèle : {model_id}. Réponds en français."
        )

        agents = [
            ("claude-sonnet-4-6", "BodyBoard · Sonnet"),
            ("claude-opus-4-6",   "BodyBoard · Opus"),
        ]
        for model_id, title in agents:
            pane, pane_created = HeadlessPane.objects.get_or_create(
                workspace=ws,
                title=title,
                defaults={
                    "model_id": model_id,
                    "prompt_initial": CONTEXTE.format(model_id=model_id),
                },
            )
            if pane_created:
                self.stdout.write(self.style.SUCCESS(f"  Agent créé : {pane.title} ({model_id})"))
            else:
                self.stdout.write(f"  Agent déjà présent : {pane.title}")
