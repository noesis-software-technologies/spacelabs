"""Amorce le journal « Sessions & consommation » avec les traces quantifiables.

Idempotent (clé `ref`). Les chiffres veille sont MESURÉS (coût/tokens rapportés
par le CLI claude) ; les autres projets sont des entrées à compléter (le détail
de consommation OpenClaw/Telegram n'est pas importé automatiquement — à saisir
via l'admin au fur et à mesure).

  python manage.py usage_seed
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.ops.models import SessionTrace
from apps.workspaces.models import Workspace

ROWS = [
    # ref, projet, source, workspace_name, sessions, conversations, tin, tout, cost, resume
    ("atmosphere-veille-lot1", "13 Atmosphère", "veille", "13 Atmosphère", 10, 10, 24, 24830, "2.2612",
     "Rédaction plume de Thérèse — 10 premiers articles (mesuré via claude)."),
    ("atmosphere-veille-lot2", "13 Atmosphère", "veille", "13 Atmosphère", 10, 10, 24, 25000, "2.3500",
     "Rédaction plume de Thérèse — 10 articles suivants (mesuré)."),
    ("atmosphere-mcp", "13 Atmosphère", "veille", "13 Atmosphère", 0, 6, 0, 0, "0.0000",
     "Publication MCP : test bout-en-bout + 1 article réel (id 1524, cover+6 images)."),
    ("atmosphere-pexels", "13 Atmosphère", "veille", "13 Atmosphère", 0, 0, 0, 0, "0.0000",
     "Fallback images Pexels (libre de droit, quota gratuit)."),
    ("spacelabs-build", "SpaceLabs — plateforme", "telegram", "Session 2026-08-27 — Telegram",
     1, 60, 0, 0, "0.0000",
     "Dév plateforme via ce chat (dashboard, veille, comms, design shadcn). Abonnement OpenClaw (quota, non facturé au $)."),
    ("rimbup", "RIMbup", "telegram", "RIMbup", 0, 0, 0, 0, "0.0000",
     "Bot BrainGod Telegram (client). À renseigner."),
    ("mohamed", "Mohamed", "cockpit", "Mohamed", 0, 0, 0, 0, "0.0000",
     "Projet Mohamed. À renseigner."),
    ("codeur-scraping", "Codeur.com — prospection", "scraping", "Codeur.com", 0, 0, 0, 0, "0.0000",
     "Scraping/prospection codeur.com. À renseigner."),
]


class Command(BaseCommand):
    help = "Amorce le journal Sessions & consommation (idempotent)."

    def handle(self, *args, **o):
        from django.contrib.auth import get_user_model
        owner = get_user_model().objects.filter(is_superuser=True).first()
        by_name = {w.name: w for w in Workspace.objects.all()}

        def workspace(name):
            if not name:
                return None
            w = by_name.get(name)
            if not w and owner:
                w, _ = Workspace.objects.get_or_create(owner=owner, name=name, defaults={"cwd": "~"})
                by_name[name] = w
            return w

        n = 0
        for ref, projet, source, wname, sess, conv, tin, tout, cost, resume in ROWS:
            _, created = SessionTrace.objects.update_or_create(
                ref=ref,
                defaults=dict(projet=projet, source=source, workspace=workspace(wname),
                              sessions=sess, conversations=conv, tokens_in=tin,
                              tokens_out=tout, cost_usd=cost, resume=resume,
                              date=timezone.localdate()),
            )
            n += 1
            self.stdout.write(("+ " if created else "~ ") + f"{projet} - {source} - ${cost}")
        self.stdout.write(self.style.SUCCESS(f"\n{n} trace(s) en base. Vue : /dashboard/usage/"))
