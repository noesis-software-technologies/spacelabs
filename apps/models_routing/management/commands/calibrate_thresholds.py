"""calibrate_thresholds — mesure le backend local et cale les seuils de routage.

Remplace les seuils provisoires de la fixture par des valeurs MESURÉES :
1. sonde l'endpoint (prompt calibré ~N tokens, petite génération) ;
2. mesure pp_tps (tokens de prompt / temps jusqu'au premier delta) et
   gen_tps (tokens générés / temps de génération) ;
3. applique la règle de la spec §6 : le local prend une tâche si
   prompt/pp_tps + réponse_attendue/gen_tps ≤ budget_secondes (90 s) ;
4. écrit max_est_tokens sur les règles du backend local qui en portent un.

À lancer sur le poste (le llama-server doit tourner) :
    python manage.py calibrate_thresholds [--budget-seconds 90] [--dry-run]
"""
from __future__ import annotations

import asyncio
import time

from django.core.management.base import BaseCommand

from apps.models_routing.adapters import OpenAIHttpAdapter, estimate_tokens
from apps.models_routing.models import ModelBackend, RoutingRule

EXPECTED_COMPLETION_TOKENS = 400  # réponse type d'un run d'agent


def derive_threshold(pp_tps: float, gen_tps: float, budget_seconds: float,
                     expected_completion: int = EXPECTED_COMPLETION_TOKENS,
                     prompt_budget: int | None = None) -> int:
    """Tokens de prompt max pour tenir dans le budget temps (spec §6)."""
    gen_seconds = expected_completion / max(gen_tps, 0.1)
    remaining = max(budget_seconds - gen_seconds, 0)
    threshold = int(pp_tps * remaining)
    if prompt_budget is not None:
        threshold = min(threshold, prompt_budget)
    return max(threshold, 0)


async def measure_backend(backend, prompt_tokens_target: int = 1500) -> tuple[float, float]:
    """(pp_tps, gen_tps) mesurés sur un aller-réel — TTFT ≈ prompt processing."""
    adapter = OpenAIHttpAdapter(backend)
    try:
        filler = "mesure de calibration du routeur. " * (prompt_tokens_target // 8)
        messages = [{"role": "user", "content": filler + "\nRéponds par un court paragraphe."}]
        est = estimate_tokens(messages)
        t0 = time.monotonic()
        t_first = None
        completion_tokens = 0
        async for ev in adapter.stream_chat(messages, max_tokens=128):
            if ev.type == "delta" and t_first is None:
                t_first = time.monotonic()
            elif ev.type == "usage" and ev.data:
                completion_tokens = int(ev.data.get("completion_tokens", 0))
            elif ev.type == "error":
                raise RuntimeError(f"backend {backend.slug} en erreur : {ev.data}")
        t_end = time.monotonic()
        if t_first is None:
            raise RuntimeError(f"backend {backend.slug} : aucun delta reçu")
        pp_tps = est / max(t_first - t0, 0.001)
        gen_tps = max(completion_tokens, 1) / max(t_end - t_first, 0.001)
        return pp_tps, gen_tps
    finally:
        await adapter.aclose()


class Command(BaseCommand):
    help = "Mesure les backends locaux et cale max_est_tokens sur les règles."

    def add_arguments(self, parser):
        parser.add_argument("--budget-seconds", type=float, default=90.0)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        budget_s = options["budget_seconds"]
        backends = ModelBackend.objects.filter(
            kind=ModelBackend.KIND_OPENAI_HTTP, enabled=True
        )
        if not backends:
            self.stdout.write(self.style.WARNING("Aucun backend openai_http actif."))
            return
        for backend in backends:
            pp, gen = asyncio.run(measure_backend(backend))
            threshold = derive_threshold(pp, gen, budget_s, prompt_budget=backend.prompt_budget)
            self.stdout.write(
                f"{backend.slug}: pp={pp:.0f} tok/s gen={gen:.1f} tok/s "
                f"→ max_est_tokens={threshold} (budget {budget_s:.0f}s)"
            )
            if options["dry_run"]:
                continue
            updated = RoutingRule.objects.filter(
                backend=backend, max_est_tokens__isnull=False
            ).update(max_est_tokens=threshold)
            backend.healthy = True
            backend.save(update_fields=["healthy"])
            self.stdout.write(self.style.SUCCESS(f"  {updated} règle(s) calée(s)."))
