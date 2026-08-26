"""Routage déterministe (ADR-5) : règles ordonnées + budgets par mission."""
from __future__ import annotations

from dataclasses import dataclass

from django.db.models import F

from .models import MissionTokenBudget, ModelBackend, RoutingRule


class NoBackendAvailable(Exception):
    """Aucune règle ne matche avec un backend sain — erreur franche à l'UI."""


@dataclass
class RoutingDecision:
    backend: ModelBackend
    rule: RoutingRule | None
    degraded: bool = False  # re-routé pour cause de budget épuisé
    reason: str = ""


def _first_healthy_local() -> ModelBackend | None:
    return (
        ModelBackend.objects.filter(
            kind=ModelBackend.KIND_OPENAI_HTTP, enabled=True, healthy=True
        )
        .order_by("slug")
        .first()
    )


def route(task_class: str, est_tokens: int, mission=None) -> RoutingDecision:
    """Spec §6 : classe déclarée → première règle qui matche → backend sain,
    puis politique de budget de la mission."""
    rules = RoutingRule.objects.select_related("backend").filter(enabled=True)
    decision: RoutingDecision | None = None
    for rule in rules:
        if not rule.matches(task_class, est_tokens):
            continue
        if not (rule.backend.enabled and rule.backend.healthy):
            continue  # backend malade → règle suivante (spec §6.3)
        decision = RoutingDecision(backend=rule.backend, rule=rule)
        break
    if decision is None:
        raise NoBackendAvailable(f"aucune règle saine pour task_class={task_class!r}")

    if mission is not None:
        budget = MissionTokenBudget.objects.filter(mission=mission).first()
        if budget and budget.would_exceed(est_tokens):
            if budget.policy_on_exhaust == MissionTokenBudget.POLICY_BLOCK:
                raise NoBackendAvailable(
                    f"budget mission épuisé ({budget.spent}/{budget.budget_tokens})"
                )
            if budget.policy_on_exhaust == MissionTokenBudget.POLICY_DEGRADE:
                local = _first_healthy_local()
                if local and local.pk != decision.backend.pk:
                    return RoutingDecision(
                        backend=local,
                        rule=decision.rule,
                        degraded=True,
                        reason="budget épuisé → dégradé vers le local",
                    )
            # warn_only (ou pas de local disponible) : on laisse passer,
            # l'appelant reçoit decision.reason pour l'afficher.
            decision.reason = f"budget dépassé ({budget.spent}/{budget.budget_tokens})"
    return decision


def record_usage(mission, prompt_tokens: int, completion_tokens: int) -> None:
    """Incrémente les compteurs de la mission (appelé sur l'événement usage).

    Incréments via F() : atomiques côté SQL — deux runs qui se terminent en
    même temps ne s'écrasent pas (lire-modifier-écrire interdit ici). Les
    instances déjà chargées ailleurs (cache de relation) doivent relire la
    base pour voir les compteurs à jour."""
    if mission is None:
        return
    MissionTokenBudget.objects.get_or_create(mission=mission)
    MissionTokenBudget.objects.filter(mission=mission).update(
        spent_prompt=F("spent_prompt") + int(prompt_tokens or 0),
        spent_completion=F("spent_completion") + int(completion_tokens or 0),
    )
