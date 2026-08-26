"""Logique d'exploitation, en fonctions PURES (sans Celery).

Les tâches Celery (tasks.py) ne sont que de fines enveloppes autour d'ici :
tout est testable en direct, sans broker ni worker. Tout travaille depuis la
DB — donc valable aussi bien dans Daphne que dans le worker.
"""
from __future__ import annotations

import json
import logging
import subprocess
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger("spacelabs.ops")


# ── Fenêtre « aujourd'hui » dans la timezone du projet ─────────────────────
def _start_of_today():
    now = timezone.localtime()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start


# ── Agrégation d'usage (DB uniquement) ─────────────────────────────────────
def usage_for_owner(owner) -> dict:
    """Valeurs de jauges dérivées des données déjà persistées.

    - active_panes : panes 'running' en DB (source cross-process fiable).
    - cost_usd_today : somme, par pane, du coût cumulé max de ses events
      `result` du jour (total_cost_usd étant cumulatif par session).
    - turns_today : nombre de tours humains (events d'origine 'user') du jour.
    """
    from apps.chat.models import EventLog
    from apps.workspaces.models import Pane

    since = _start_of_today()
    panes = Pane.objects.filter(workspace__owner=owner)
    active = panes.filter(status=Pane.Status.RUNNING).count()

    # Coût : max cumulé par pane parmi les result d'aujourd'hui, puis somme.
    results = (
        EventLog.objects.filter(
            pane__workspace__owner=owner, event_type="result", created_at__gte=since
        )
        .values_list("pane_id", "normalized")
    )
    max_by_pane: dict[int, float] = {}
    for pane_id, normalized in results:
        cost = 0.0
        if isinstance(normalized, dict):
            try:
                cost = float(normalized.get("cost_usd") or 0)
            except (TypeError, ValueError):
                cost = 0.0
        if cost > max_by_pane.get(pane_id, 0.0):
            max_by_pane[pane_id] = cost
    cost_today = round(sum(max_by_pane.values()), 4)

    turns_today = EventLog.objects.filter(
        pane__workspace__owner=owner, origin="user", created_at__gte=since
    ).count()

    # [S9] La jauge affichait `actifs / COCKPIT_MAX_PANES` alors que le plafond
    # ne s'appliquait qu'aux PTY : elle mentait. Le plafond couvre désormais les
    # deux familles (apps/runtime/capacity.py) et on lit la même limite qu'elle.
    from apps.runtime.capacity import owner_limit

    return {
        "active_panes": active,
        "max_panes": owner_limit(),
        "cost_usd_today": cost_today,
        "turns_today": turns_today,
    }


def external_usage() -> dict | None:
    """Exécute la commande d'usage optionnelle et parse sa sortie JSON.

    Permet de brancher la vraie fenêtre de quota de l'abonnement. Non
    configurée par défaut ⇒ None. Best-effort : toute erreur ⇒ None + log."""
    cmd = settings.COCKPIT_USAGE_CMD
    if not cmd:
        return None
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15, check=True
        ).stdout
        return json.loads(out)
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
        logger.warning("commande d'usage indisponible : %s", exc)
        return None


def snapshot_all_owners() -> int:
    """Écrit un UsageSnapshot par utilisateur ayant des workspaces. Renvoie le
    nombre d'instantanés créés."""
    from apps.ops.models import UsageSnapshot
    from apps.workspaces.models import Workspace

    ext = external_usage()
    owner_ids = Workspace.objects.values_list("owner_id", flat=True).distinct()
    users = get_user_model().objects.filter(pk__in=list(owner_ids))
    created = 0
    for user in users:
        data = usage_for_owner(user)
        UsageSnapshot.objects.create(owner=user, external=ext, **data)
        created += 1
    logger.info("snapshot d'usage : %s instantané(s)", created)
    return created


# ── Réconciliation & faucheur de zombies ───────────────────────────────────
def reconcile_boot(boot_id: str) -> int:
    """Au démarrage de Daphne : tout pane 'running' qui n'appartient PAS à la
    génération courante est mort (son process n'existe plus). Renvoie le
    nombre de panes réconciliés."""
    from apps.workspaces.models import Pane

    stale = Pane.objects.filter(status=Pane.Status.RUNNING).exclude(runtime_boot_id=boot_id)
    if settings.COCKPIT_RESUME_ON_BOOT:
        # On mémorise qu'elles tournaient, pour les reprendre (bouton / auto).
        n = stale.update(status=Pane.Status.DEAD, resume_pending=True)
    else:
        n = stale.update(status=Pane.Status.DEAD)
    if n:
        logger.info("réconciliation boot : %s pane(s) zombie(s) marqué(s) morts", n)
    return n


def reap_zombies() -> int:
    """Faucheur périodique (worker Celery). Sans processus Daphne vivant, rien
    ne peut tourner ⇒ tous les 'running' sont morts. Avec Daphne vivant, seules
    les générations autres que la courante sont des zombies."""
    from apps.ops.models import RuntimeHeartbeat
    from apps.workspaces.models import Pane

    hb = RuntimeHeartbeat.current()
    running = Pane.objects.filter(status=Pane.Status.RUNNING)
    stale = (
        hb is None
        or (timezone.now() - hb.last_seen) > timedelta(seconds=settings.COCKPIT_HEARTBEAT_STALE_SECONDS)
    )
    if stale:
        n = running.update(status=Pane.Status.DEAD)
        if n:
            logger.info("faucheur : Daphne absent, %s pane(s) marqué(s) morts", n)
        return n
    n = running.exclude(runtime_boot_id=hb.boot_id).update(status=Pane.Status.DEAD)
    if n:
        logger.info("faucheur : %s zombie(s) d'ancienne génération marqué(s) morts", n)
    return n


# ── Purge / archivage d'EventLog ───────────────────────────────────────────
def archive_eventlog() -> dict:
    """Purge les événements plus vieux que la rétention. Si un répertoire
    d'archive est configuré, dumpe d'abord en JSONL compressé avant suppression.
    Renvoie {archived, deleted}."""
    import gzip
    from pathlib import Path

    from apps.chat.models import EventLog

    days = settings.COCKPIT_EVENTLOG_RETENTION_DAYS
    if days <= 0:
        return {"archived": 0, "deleted": 0}
    cutoff = timezone.now() - timedelta(days=days)
    old = EventLog.objects.filter(created_at__lt=cutoff).order_by("pane_id", "seq")
    total = old.count()
    if total == 0:
        return {"archived": 0, "deleted": 0}

    archived = 0
    archive_dir = settings.COCKPIT_EVENTLOG_ARCHIVE_DIR
    if archive_dir:
        path = Path(archive_dir)
        path.mkdir(parents=True, exist_ok=True)
        fname = path / f"eventlog-{timezone.now():%Y%m%d-%H%M%S}.jsonl.gz"
        with gzip.open(fname, "wt", encoding="utf-8") as fh:
            for row in old.values("pane_id", "seq", "origin", "event_type", "payload", "created_at"):
                row["created_at"] = row["created_at"].isoformat()
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                archived += 1
        logger.info("archivage EventLog : %s événements → %s", archived, fname)

    deleted, _ = EventLog.objects.filter(created_at__lt=cutoff).delete()
    logger.info("purge EventLog : %s lignes supprimées", total)
    return {"archived": archived, "deleted": total}


# ── Détection d'auth MCP ───────────────────────────────────────────────────
def scan_mcp_auth(lookback_minutes: int = 30) -> int:
    """Cherche dans les events chat récents des signaux « MCP à ré-authentifier »
    et crée une MCPAlert non résolue par pane concerné (dédupliquée). Renvoie le
    nombre d'alertes créées."""
    from apps.chat.models import EventLog
    from apps.ops.models import MCPAlert

    patterns = [p.lower() for p in settings.COCKPIT_MCP_AUTH_PATTERNS if p]
    if not patterns:
        return 0
    since = timezone.now() - timedelta(minutes=lookback_minutes)
    rows = EventLog.objects.filter(
        created_at__gte=since, event_type__in=["assistant", "user", "result"]
    ).values_list("pane_id", "normalized")

    hit_panes: dict[int, str] = {}
    for pane_id, normalized in rows:
        blob = json.dumps(normalized, ensure_ascii=False).lower() if normalized else ""
        for pat in patterns:
            if pat in blob:
                hit_panes.setdefault(pane_id, pat)
                break

    created = 0
    for pane_id, pat in hit_panes.items():
        # Ne pas empiler : une alerte non résolue par pane suffit.
        if not MCPAlert.objects.filter(pane_id=pane_id, resolved=False).exists():
            MCPAlert.objects.create(pane_id=pane_id, detail=f"signal : {pat}")
            created += 1
    if created:
        logger.info("détection MCP : %s alerte(s) créée(s)", created)
    return created
