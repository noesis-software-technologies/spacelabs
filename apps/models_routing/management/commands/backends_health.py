"""Health check des backends HTTP — pose healthy/last_health_at (spec §9 S-R1)."""
import asyncio

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.models_routing.adapters import OpenAIHttpAdapter
from apps.models_routing.models import ModelBackend


class Command(BaseCommand):
    help = "Vérifie la santé des backends openai_http et met à jour healthy."

    def handle(self, *args, **options):
        backends = list(ModelBackend.objects.filter(kind=ModelBackend.KIND_OPENAI_HTTP, enabled=True))
        results = asyncio.run(self._check_all(backends))
        for backend, ok in results:
            backend.healthy = ok
            backend.last_health_at = timezone.now()
            backend.save(update_fields=["healthy", "last_health_at"])
            style = self.style.SUCCESS if ok else self.style.ERROR
            self.stdout.write(style(f"{backend.slug}: {'OK' if ok else 'KO'}"))

    async def _check_all(self, backends):
        out = []
        for b in backends:
            adapter = OpenAIHttpAdapter(b)
            try:
                out.append((b, await adapter.health()))
            finally:
                await adapter.aclose()
        return out
