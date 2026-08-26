"""Réconcilie les panes 'running' orphelins (hors génération courante)."""
from django.core.management.base import BaseCommand

from apps.ops.services import reconcile_boot
from apps.runtime.runtime_state import BOOT_ID


class Command(BaseCommand):
    help = "Marque morts les panes 'running' qui n'appartiennent pas à cette génération."

    def handle(self, *args, **options):
        n = reconcile_boot(BOOT_ID)
        self.stdout.write(self.style.SUCCESS(f"{n} pane(s) réconcilié(s)."))
