"""Master Tasker — missions, tâches, assignations.

S10 : toute la mécanique d'orchestration, SANS IA. Une mission se remplit à la
main ; le dispatcher distribue. Si ça marche à la main, S11 n'aura qu'à faire
écrire le plan par Claude — le reste du pipeline est déjà éprouvé.

Tenancy : tout passe par ``for_owner(user)`` via ``workspace__owner``.
"""
from __future__ import annotations

from django.db import models

from apps.workspaces.models import Pane, Workspace


class MissionQuerySet(models.QuerySet):
    def for_owner(self, user):
        return self.filter(workspace__owner=user)


class Mission(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "brouillon"
        PLANNING = "planning", "planification"
        RUNNING = "running", "en cours"
        PAUSED = "paused", "en pause"
        DONE = "done", "terminée"
        FAILED = "failed", "échouée"

    class Mode(models.TextChoices):
        # Par défaut le Tasker PROPOSE : n agents en parallèle, c'est n fois la
        # facture et n fois les dégâts (ADR-6).
        MANUAL = "manual", "validation humaine"
        AUTO = "auto", "automatique"

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="missions")
    # ADR-5 : classe de tâche DÉCLARÉE — c'est elle que le routeur de modèles
    # lit pour choisir le backend (spec MODEL_ROUTING.md §6 ; D2 : portée par
    # la Mission, pas par le pane). Choix partagés avec RoutingRule.
    task_class = models.CharField(
        "classe de tâche", max_length=32, default="default",
        choices=[
            ("draft", "Draft / rédaction courte"), ("summarize", "Résumé"),
            ("glue", "Glue code / scripts"), ("route", "Routage de messages"),
            ("code_small", "Code borné"), ("code_heavy", "Code lourd / refacto"),
            ("architecture", "Architecture / conception"),
            ("long_context", "Très long contexte"), ("default", "Défaut"),
        ],
    )
    goal = models.TextField("objectif")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.MANUAL)
    # Combien d'agents cette mission a le droit d'occuper simultanément. Borné
    # en plus par la capacité du workspace (apps/runtime/capacity.py).
    max_parallel = models.PositiveSmallIntegerField("agents simultanés", default=3)
    budget_usd = models.DecimalField(
        "budget", max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Plafond dur : le dispatch s'arrête au-delà. Vide = pas de plafond.",
    )
    # Le planificateur est un pane headless comme les autres (ADR-2) : il
    # hérite gratuitement de la reprise --resume, du coût, de l'EventLog.
    planner_pane = models.ForeignKey(
        "workspaces.HeadlessPane", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="planned_missions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = MissionQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.goal[:60]

    @property
    def spent_usd(self):
        total = self.tasks.aggregate(s=models.Sum("cost_usd"))["s"]
        return total or 0

    @property
    def over_budget(self) -> bool:
        return self.budget_usd is not None and self.spent_usd >= self.budget_usd


class Task(models.Model):
    class Status(models.TextChoices):
        TODO = "todo", "à faire"
        READY = "ready", "prête"
        RUNNING = "running", "en cours"
        REVIEW = "review", "à relire"
        DONE = "done", "terminée"
        FAILED = "failed", "échouée"
        BLOCKED = "blocked", "bloquée"

    # Colonnes du board, dans l'ordre. Le board lit CETTE liste : ajouter un
    # statut ne demande pas de toucher au template.
    BOARD_COLUMNS = [Status.TODO, Status.READY, Status.RUNNING, Status.REVIEW, Status.DONE]

    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name="tasks")
    key = models.SlugField("clé", max_length=12)
    title = models.CharField(max_length=200)
    brief = models.TextField("consigne", blank=True, help_text="Ce qui sera envoyé à l'agent.")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.TODO)
    depends_on = models.ManyToManyField("self", symmetrical=False, blank=True, related_name="blocks")
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=2)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["mission", "key"], name="uniq_task_key_per_mission"),
        ]

    def __str__(self):
        return f"{self.key} · {self.title[:40]}"

    def save(self, *args, **kwargs):
        """Ajouter une tâche à une mission close la ROUVRE.

        Sans ça, le replan de S11 (ajouter des tâches correctives après un
        échec) laisserait la mission marquée « terminée » avec du travail en
        attente : elle ne serait plus jamais distribuée.
        """
        creating = self._state.adding
        super().save(*args, **kwargs)
        if creating and self.mission.status in (Mission.Status.DONE, Mission.Status.FAILED):
            Mission.objects.filter(pk=self.mission_id).update(status=Mission.Status.RUNNING)
            self.mission.status = Mission.Status.RUNNING

    @property
    def is_open(self) -> bool:
        return self.status not in (self.Status.DONE, self.Status.FAILED)

    @property
    def can_retry(self) -> bool:
        return self.attempts < self.max_attempts


class Assignment(models.Model):
    """Qui a exécuté quoi. Trace l'historique, y compris les tentatives ratées."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="assignments")
    # FK vers la base Pane (polymorphe) : le dispatcher ne connaît pas le type.
    pane = models.ForeignKey(Pane, on_delete=models.CASCADE, related_name="assignments")
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["-started_at"]
