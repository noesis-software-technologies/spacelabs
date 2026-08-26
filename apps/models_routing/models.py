"""ADR-5 — plan de contrôle multi-modèles (spec MODEL_ROUTING.md).

Routage DÉTERMINISTE : une table de règles ordonnées choisit un backend par
classe de tâche ; aucun appel modèle pour décider du modèle (esprit ADR-4).
"""
from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.db import models


class ModelBackend(models.Model):
    """Un moteur d'exécution : le binaire claude, ou un endpoint OpenAI-compatible."""

    KIND_CLAUDE_BIN = "claude_bin"
    KIND_OPENAI_HTTP = "openai_http"
    KIND_CHOICES = [
        (KIND_CLAUDE_BIN, "Binaire claude (abonnement)"),
        (KIND_OPENAI_HTTP, "Endpoint OpenAI-compatible (HTTP)"),
    ]

    slug = models.SlugField(unique=True)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    base_url = models.URLField(
        blank=True,
        help_text="openai_http uniquement — ex. http://192.168.1.20:8081/v1 (LAN/loopback seulement)",
    )
    model_id = models.CharField(
        max_length=200,
        blank=True,
        help_text="Id modèle côté endpoint ; vide pour claude_bin (défaut du binaire).",
    )
    context_window = models.PositiveIntegerField(default=32768)
    max_tokens = models.PositiveIntegerField(default=4096)
    supports_tools = models.BooleanField(default=True)
    enabled = models.BooleanField(default=True)
    healthy = models.BooleanField(default=False)
    last_health_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["slug"]

    def __str__(self) -> str:  # pragma: no cover - repr
        return self.slug

    # Sécurité (spec §8) : les endpoints HTTP restent sur le LAN/loopback.
    def clean(self):
        super().clean()
        if self.kind == self.KIND_OPENAI_HTTP:
            if not self.base_url:
                raise ValidationError({"base_url": "Requis pour un backend openai_http."})
            host = urlparse(self.base_url).hostname or ""
            if host in ("localhost",):
                return
            try:
                ip = ipaddress.ip_address(host)
            except ValueError as exc:
                raise ValidationError(
                    {"base_url": "Hôte non résolu en IP : utilisez une IP privée ou localhost."}
                ) from exc
            if not (ip.is_private or ip.is_loopback):
                raise ValidationError({"base_url": "IP publique refusée (LAN/loopback uniquement)."})

    @property
    def prompt_budget(self) -> int:
        """Tokens de prompt disponibles une fois la réponse réservée."""
        return max(self.context_window - self.max_tokens, 0)


class RoutingRule(models.Model):
    """Règle ordonnée : première qui matche (classe + seuil) → backend."""

    TASK_CLASSES = [
        ("draft", "Draft / rédaction courte"),
        ("summarize", "Résumé"),
        ("glue", "Glue code / scripts"),
        ("route", "Routage de messages"),
        ("code_small", "Code borné"),
        ("code_heavy", "Code lourd / refacto"),
        ("architecture", "Architecture / conception"),
        ("long_context", "Très long contexte"),
        ("default", "Défaut"),
    ]

    order = models.PositiveIntegerField()
    task_class = models.CharField(max_length=32, choices=TASK_CLASSES, default="default")
    max_est_tokens = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Si l'estimation du prompt dépasse ce seuil, la règle ne matche pas.",
    )
    backend = models.ForeignKey(ModelBackend, on_delete=models.CASCADE, related_name="rules")
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:  # pragma: no cover - repr
        cap = f" ≤{self.max_est_tokens}tok" if self.max_est_tokens else ""
        return f"{self.order}. {self.task_class}{cap} → {self.backend.slug}"

    def matches(self, task_class: str, est_tokens: int) -> bool:
        if not self.enabled or self.task_class != task_class:
            return False
        if self.max_est_tokens is not None and est_tokens > self.max_est_tokens:
            return False
        return True


class MissionTokenBudget(models.Model):
    """Budget par mission — l'unité économique (spec §2.4)."""

    POLICY_BLOCK = "block"
    POLICY_DEGRADE = "degrade_to_local"
    POLICY_WARN = "warn_only"
    POLICY_CHOICES = [
        (POLICY_BLOCK, "Bloquer"),
        (POLICY_DEGRADE, "Dégrader vers le local"),
        (POLICY_WARN, "Avertir seulement"),
    ]

    mission = models.OneToOneField(
        "tasker.Mission", on_delete=models.CASCADE, related_name="token_budget"
    )
    budget_tokens = models.PositiveIntegerField(default=0, help_text="0 = illimité")
    spent_prompt = models.PositiveIntegerField(default=0)
    spent_completion = models.PositiveIntegerField(default=0)
    policy_on_exhaust = models.CharField(
        max_length=20, choices=POLICY_CHOICES, default=POLICY_DEGRADE
    )

    def __str__(self) -> str:  # pragma: no cover - repr
        return f"budget mission #{self.mission_id}: {self.spent}/{self.budget_tokens or '∞'}"

    @property
    def spent(self) -> int:
        return self.spent_prompt + self.spent_completion

    def would_exceed(self, est_tokens: int) -> bool:
        if not self.budget_tokens:
            return False
        return self.spent + est_tokens > self.budget_tokens


class RunLog(models.Model):
    """Métadonnées d'un run ; les événements vivent en JSONL append-only (spec §4)."""

    STATUS_CHOICES = [
        ("ok", "ok"),
        ("error", "error"),
        ("overflow", "overflow"),
        ("budget_blocked", "budget_blocked"),
        ("running", "running"),
    ]

    id = models.UUIDField(primary_key=True)
    mission = models.ForeignKey(
        "tasker.Mission", null=True, blank=True, on_delete=models.SET_NULL, related_name="runs"
    )
    backend = models.ForeignKey(ModelBackend, on_delete=models.PROTECT, related_name="runs")
    task_class = models.CharField(max_length=32, default="default")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="running")
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    jsonl_path = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-started_at"]
