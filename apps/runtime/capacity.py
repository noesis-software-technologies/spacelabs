"""Capacité — combien d'instances d'agent peuvent tourner, et où.

Pourquoi ce module existe (S9)
------------------------------
Avant, le plafond vivait dans ``PaneManager.spawn`` sous la forme
``len(self.panes) >= COCKPIT_MAX_PANES``. Trois défauts :

1. **Global au processus** : le dict ``self.panes`` mélange tous les
   propriétaires. Deux utilisateurs à 6 panes bloquaient tout le monde à 12.
2. **Aveugle aux workspaces** : impossible de dire « ce workspace-ci a droit à
   4 agents, celui-là à 16 », alors que c'est précisément la promesse du
   produit (*n* instances Claude Code par workspace).
3. **Aveugle au headless** : ``HeadlessManager.start`` n'avait aucun contrôle.
   Le plafond ne s'appliquait donc qu'aux PTY, pendant que la jauge affichait
   ``actifs / MAX_PANES`` en comptant les deux familles — elle mentait.

Ici, le comptage se fait **en base**, comme ``apps/ops/services.py`` : c'est la
seule source vraie cross-process (le worker Celery ne voit pas les managers en
mémoire, et plusieurs Daphne peuvent tourner). Les managers gardent un garde-fou
mémoire *par propriétaire* en défense en profondeur, mais la décision est ici.

Invariant : on compte les panes **RUNNING en base**, tous types confondus
(``Pane`` de base, pas ``PtyPane``/``HeadlessPane``) — un agent est un agent.
"""

from __future__ import annotations

from django.conf import settings


class CapacityError(Exception):
    """Plafond atteint. Message destiné à l'utilisateur (affiché en toast)."""


def workspace_limit(workspace) -> int:
    """Plafond effectif d'un workspace : le sien, sinon le défaut global."""
    explicit = getattr(workspace, "max_panes", None)
    return int(explicit) if explicit else int(settings.COCKPIT_MAX_PANES)


def owner_limit() -> int:
    """Plafond effectif d'un propriétaire, toutes ses instances confondues."""
    return int(settings.COCKPIT_OWNER_MAX_PANES or settings.COCKPIT_MAX_PANES)


def _running_qs(exclude_pk=None):
    from apps.workspaces.models import Pane

    qs = Pane.objects.filter(status=Pane.Status.RUNNING)
    if exclude_pk is not None:
        # Un pane qui redémarre ne doit pas se compter lui-même : sinon
        # relancer le 16e agent échouerait alors qu'on n'en ajoute aucun.
        qs = qs.exclude(pk=exclude_pk)
    return qs


def running_in_workspace(workspace, exclude_pk=None) -> int:
    return _running_qs(exclude_pk).filter(workspace=workspace).count()


def running_for_owner(owner_id: int, exclude_pk=None) -> int:
    return _running_qs(exclude_pk).filter(workspace__owner_id=owner_id).count()


def ensure_can_start(pane) -> None:
    """Lève ``CapacityError`` si démarrer ``pane`` dépasserait un plafond.

    Appelé par le consumer AVANT tout spawn (PTY comme headless) : un seul
    point d'application pour les deux familles, quel que soit le type de pane.
    """
    workspace = pane.workspace
    ws_limit = workspace_limit(workspace)
    ws_running = running_in_workspace(workspace, exclude_pk=pane.pk)
    if ws_running >= ws_limit:
        raise CapacityError(
            f"Ce workspace est à son plafond de {ws_limit} agent"
            f"{'s' if ws_limit > 1 else ''} en cours."
        )

    o_limit = owner_limit()
    o_running = running_for_owner(workspace.owner_id, exclude_pk=pane.pk)
    if o_running >= o_limit:
        raise CapacityError(
            f"Plafond de {o_limit} agents en cours atteint pour ce compte."
        )


def snapshot(owner) -> dict:
    """Chiffres de capacité pour les jauges — honnêtes, les deux familles."""
    return {
        "running": running_for_owner(owner.pk),
        "limit": owner_limit(),
    }
