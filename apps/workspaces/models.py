"""Workspaces & panes — le modèle de données du cockpit.

[Types polymorphes] : MTI ``Pane`` → ``PtyPane`` / ``HeadlessPane`` avec
registre (§6.9 du blueprint). Le pipeline (vues, grille, consumer) ne connaît
que la base ``Pane`` + le registre : ajouter un type = 1 modèle enfant,
1 form, 1 entrée de registre — zéro modification du pipeline.

[TENANCY] par user dès J0 : tout accès passe par ``for_owner(user)``.
"""
from __future__ import annotations

import itertools

from django.conf import settings
from django.db import models
from django.utils.text import slugify

# Labels d'agents auto — indicatifs courts, lisibles à 3 m sur la vue télé.
AGENT_NAMES = [
    "Rossignol", "Baryton", "Cormoran", "Dynamo", "Eclipse", "Falcon",
    "Girafe", "Harfang", "Icare", "Jaguar", "Kestrel", "Lumen",
    "Meteore", "Nimbus", "Ocelot", "Pulsar", "Quartz", "Renard",
    "Sirius", "Tandem", "Umami", "Vortex", "Wombat", "Xenon",
    "Yucca", "Zephyr",
]


class OwnedQuerySet(models.QuerySet):
    def for_owner(self, user):
        return self.filter(owner=user)

    def with_counts(self):
        """Compte des panes + des panes vivants, en UNE requête.

        La sidebar affichait ``ws.panes.first.status`` : une requête par
        workspace (N+1). Ici, deux agrégats annotés.
        """
        return self.annotate(
            pane_count=models.Count("panes", distinct=True),
            running_count=models.Count(
                "panes",
                filter=models.Q(panes__status=Pane.Status.RUNNING),
                distinct=True,
            ),
        )


class Workspace(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workspaces")
    name = models.CharField("nom", max_length=80)
    slug = models.SlugField(max_length=100)
    cwd = models.CharField(
        "répertoire de travail", max_length=500, default="~",
        help_text="Répertoire par défaut des panes de ce workspace.",
    )
    # Plafond d'agents simultanés DE CE workspace. Vide = défaut global
    # (COCKPIT_MAX_PANES). C'est le réglage « n instances » du produit.
    max_panes = models.PositiveSmallIntegerField(
        "agents simultanés", null=True, blank=True,
        help_text="Vide = plafond global. Nombre d'instances qui peuvent tourner en même temps ici.",
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OwnedQuerySet.as_manager()

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "slug"], name="uniq_workspace_slug_per_owner"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "workspace"
            slug = base
            for i in itertools.count(2):
                if not Workspace.objects.filter(owner=self.owner, slug=slug).exclude(pk=self.pk).exists():
                    break
                slug = f"{base}-{i}"
            self.slug = slug
        super().save(*args, **kwargs)


class PaneQuerySet(models.QuerySet):
    def for_owner(self, user):
        return self.filter(workspace__owner=user)


class Pane(models.Model):
    """Base MTI. ``kind`` est la clé de registre — jamais de isinstance dans
    le pipeline, toujours ``registry.get(pane.kind)``."""

    class Status(models.TextChoices):
        IDLE = "idle", "prêt"
        RUNNING = "running", "en cours"
        DEAD = "dead", "terminé"

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="panes")
    kind = models.CharField(max_length=20, editable=False)
    title = models.CharField("label", max_length=60, blank=True)
    # Confidentialité (S3) — PRIVÉ PAR DÉFAUT. L'observateur ne voit d'un pane
    # privé qu'un placeholder anonyme ; d'un pane public que le flux expurgé
    # et son alias — jamais cmd ni cwd.
    is_public = models.BooleanField("visible en live", default=False)
    public_alias = models.CharField("alias public", max_length=60, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.IDLE)
    # Pane de service (planificateur du Tasker) : il consomme une vraie session
    # Claude, donc il compte dans la CAPACITÉ, mais il n'apparaît pas dans la
    # grille et ne reçoit jamais de tâche à exécuter.
    is_system = models.BooleanField(default=False, editable=False)
    # Génération Daphne qui a lancé le process runtime (S5) — sert à repérer
    # les zombies : un pane 'running' d'une génération morte n'existe plus.
    runtime_boot_id = models.CharField(max_length=32, blank=True, editable=False)
    # Marqué au boot quand COCKPIT_RESUME_ON_BOOT : une session vivante avant
    # un redémarrage, à reprendre (bouton, ou reprise auto côté client).
    resume_pending = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = PaneQuerySet.as_manager()

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.title} ({self.kind})"

    @property
    def owner_id(self):
        return self.workspace.owner_id

    @property
    def public_label(self) -> str:
        """Ce que l'observateur a le droit de lire : alias sinon indicatif."""
        return self.public_alias or self.title

    def save(self, *args, **kwargs):
        if not self.kind:
            self.kind = KIND_BY_MODEL[type(self)]
        if not self.title:
            used = set(
                Pane.objects.filter(workspace=self.workspace).exclude(pk=self.pk).values_list("title", flat=True)
            )
            self.title = next((n for n in AGENT_NAMES if n not in used), f"Agent-{self.workspace.panes.count() + 1}")
        super().save(*args, **kwargs)

    @property
    def concrete(self) -> "Pane":
        """L'instance enfant MTI (accès via le registre, pas d'isinstance)."""
        entry = registry.get(self.kind)
        if entry is None or type(self) is entry.model:
            return self
        return entry.model.objects.get(pk=self.pk)


class PtyPane(Pane):
    """Terminal interactif : un vrai PTY streamé dans xterm.js."""

    cmd = models.CharField(
        "commande", max_length=200, default="claude",
        help_text="Binaire (liste blanche COCKPIT_ALLOWED_CMDS) + arguments.",
    )
    cwd = models.CharField("répertoire", max_length=500, blank=True,
                           help_text="Vide = répertoire du workspace.")

    class Meta:
        verbose_name = "pane terminal"

    def effective_cwd(self) -> str:
        return self.cwd or self.workspace.cwd

    def respawn_cmd(self) -> str:
        """Commande de relance après interruption. Pour ``claude``, on ajoute
        ``--continue`` (reprend la conversation la plus récente du cwd) —
        aucune extraction de session id depuis le flux ANSI (invariant §8.4).
        """
        parts = self.cmd.split()
        if parts and parts[0].rsplit("/", 1)[-1] == "claude" and "--continue" not in parts and "--resume" not in parts:
            return self.cmd + " --continue"
        return self.cmd


class HeadlessPane(Pane):
    """Chat structuré ``claude -p --output-format stream-json`` (Sprint 4)."""

    MODEL_CHOICES = [
        ("claude-haiku-4-5-20251001", "Haiku 4.5"),
        ("claude-sonnet-4-5",         "Sonnet 4.5"),
        ("claude-sonnet-4-6",         "Sonnet 4.6"),
        ("claude-opus-4-6",           "Opus 4.6"),
        ("claude-opus-4-8",           "Opus 4.8"),
        ("gpt-oss-20b",               "OSS Local"),
    ]

    prompt_initial = models.TextField(blank=True)
    model_id = models.CharField(
        "modèle",
        max_length=100,
        choices=MODEL_CHOICES,
        default="claude-sonnet-4-6",
    )
    # Identifiant de session Claude Code (émis dans l'événement init). Persisté
    # pour reprendre EXACTEMENT cette conversation via --resume après un
    # redémarrage — pas juste --continue (Sprint 8).
    claude_session_id = models.CharField(max_length=100, blank=True, editable=False)

    class Meta:
        verbose_name = "pane chat"

    def effective_cwd(self) -> str:
        return self.workspace.cwd

    @property
    def model_label(self) -> str:
        return dict(self.MODEL_CHOICES).get(self.model_id, self.model_id)

    @property
    def model_tier(self) -> str:
        """Retourne 'haiku', 'sonnet', 'opus' ou 'oss' pour le style de l'avatar."""
        mid = self.model_id.lower()
        if "haiku" in mid:
            return "haiku"
        if "sonnet" in mid:
            return "sonnet"
        if "opus" in mid:
            return "opus"
        return "oss"

    def save(self, *args, **kwargs):
        if not self.title:
            tier_map = {"haiku": "Haiku", "sonnet": "Sonnet", "opus": "Opus", "oss": "OSS"}
            ws_prefix = self.workspace.name[:25]
            base = f"{ws_prefix} · {tier_map.get(self.model_tier, self.model_tier.capitalize())}"
            used = set(
                Pane.objects.filter(workspace=self.workspace)
                .exclude(pk=self.pk)
                .values_list("title", flat=True)
            )
            if base not in used:
                self.title = base
            else:
                for i in range(2, 50):
                    candidate = f"{base} {i}"
                    if candidate not in used:
                        self.title = candidate
                        break
                else:
                    self.title = f"{base} {self.workspace.panes.count() + 1}"
        super().save(*args, **kwargs)


# ── Registre polymorphe (§6.9) ─────────────────────────────────────────────
class RegistryEntry:
    def __init__(self, kind, model, label, partial, form_path,
                 dispatch_path="", can_autocomplete=False):
        self.kind = kind
        self.model = model
        self.label = label
        self.partial = partial          # partial de rendu du pane
        self.form_path = form_path      # "module:Class" — résolu par forms_for()
        # [S9] Capacités — ce que l'orchestrateur a le droit de faire de ce type
        # sans jamais tester son kind (§6.9).
        self.dispatch_path = dispatch_path      # "module:fonction" (lazy)
        # Sait-il signaler la fin d'une tâche ? Seul le headless émet un
        # événement `result` exploitable (ADR-1). Le PTY est de l'ANSI opaque.
        self.can_autocomplete = can_autocomplete

    @property
    def dispatch(self):
        """Résout paresseusement la fonction d'envoi (évite un import cyclique
        models → runtime → models au chargement des apps)."""
        if not self.dispatch_path:
            raise NotImplementedError(
                f"Le type « {self.kind} » ne déclare pas de dispatch."
            )
        import importlib

        module_path, func_name = self.dispatch_path.split(":")
        return getattr(importlib.import_module(module_path), func_name)


registry: dict[str, RegistryEntry] = {}


def register(kind, model, label, partial, form_path,
             dispatch_path="", can_autocomplete=False):
    registry[kind] = RegistryEntry(
        kind, model, label, partial, form_path,
        dispatch_path=dispatch_path, can_autocomplete=can_autocomplete,
    )


register(
    "pty", PtyPane, "Terminal",
    partial="workspaces/partials/_pane_pty.html",
    form_path="apps.workspaces.forms:PtyPaneForm",
    dispatch_path="apps.runtime.dispatch:pty_dispatch",
    # Flux ANSI opaque : aucun signal de fin exploitable sans violer
    # l'invariant n°1 (ne jamais parser le flux). Pilotage manuel.
    can_autocomplete=False,
)
register(
    "headless", HeadlessPane, "Chat (Sprint 4)",
    partial="workspaces/partials/_pane_headless.html",
    form_path="apps.workspaces.forms:HeadlessPaneForm",
    dispatch_path="apps.runtime.dispatch:headless_dispatch",
    # L'événement `result` de stream-json porte coût, durée et is_error :
    # signal de fin fiable, déjà persisté dans EventLog.
    can_autocomplete=True,
)

KIND_BY_MODEL = {entry.model: kind for kind, entry in registry.items()}


def form_for(kind):
    entry = registry[kind]
    module_path, class_name = entry.form_path.split(":")
    import importlib

    return getattr(importlib.import_module(module_path), class_name)


def concrete_panes(pane_qs):
    """Résout les instances MTI **en lot** : une requête par kind présent
    (via le registre), pas une par pane — c'est la version anti-N+1 de
    ``Pane.concrete`` pour les listes. L'ordre du queryset est préservé."""
    panes = list(pane_qs)
    by_kind: dict[str, list[int]] = {}
    for pane in panes:
        by_kind.setdefault(pane.kind, []).append(pane.pk)
    children: dict[int, Pane] = {}
    for kind, pks in by_kind.items():
        model = registry[kind].model
        if model is Pane:
            continue
        children.update(
            model.objects.select_related("workspace").in_bulk(pks)
        )
    return [children.get(p.pk, p) for p in panes]
