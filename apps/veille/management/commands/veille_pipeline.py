"""Orchestration complète de la veille (à mettre en cron).

Enchaîne : sync IMAP → images locales → fallback Pexels → rédaction (plume de
Thérèse) → inter-maillage → calendrier (semaine +1). Ne **publie pas** : la
poussée vers le MCP reste déclenchée manuellement après validation humaine.

  python manage.py veille_pipeline                 # tout le flux
  python manage.py veille_pipeline --draft-limit 10 --no-pexels
Cron (toutes les 30 min) :
  */30 * * * * cd /chemin/spacelabs && .venv/bin/python manage.py veille_pipeline >> logs/veille.log 2>&1
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Enchaîne sync → media → pexels → draft → link → calendar (pas de publication)."

    def add_arguments(self, parser):
        parser.add_argument("--draft-limit", type=int, default=0, help="Max rédactions (0 = tous).")
        parser.add_argument("--no-pexels", action="store_true", help="Sauter le fallback images.")
        parser.add_argument("--no-draft", action="store_true", help="Sauter la rédaction (claude).")
        parser.add_argument("--per-week", type=int, default=3)

    def _step(self, titre, fn):
        self.stdout.write(self.style.NOTICE(f"\n=== {titre} ==="))
        try:
            fn()
        except Exception as e:  # noqa: BLE001 - on continue le pipeline malgré une étape KO
            self.stdout.write(self.style.ERROR(f"  étape en échec : {e}"))

    def handle(self, *args, **o):
        self._step("SYNC (IMAP)", lambda: call_command("veille_sync"))
        self._step("MEDIA (images locales)", lambda: call_command("veille_media"))
        if not o["no_pexels"]:
            self._step("PEXELS (fallback visuels)", lambda: call_command("veille_pexels"))
        if not o["no_draft"]:
            kw = {"limit": o["draft_limit"]} if o["draft_limit"] else {}
            self._step("DRAFT (plume de Thérèse)", lambda: call_command("veille_draft", **kw))
        self._step("LINK (inter-maillage)", lambda: call_command("veille_link", all=True))
        self._step("CALENDAR (semaine +1)",
                   lambda: call_command("veille_calendar", status="brouillon,valide", per_week=o["per_week"]))
        self.stdout.write(self.style.SUCCESS("\nPipeline veille terminé."))
