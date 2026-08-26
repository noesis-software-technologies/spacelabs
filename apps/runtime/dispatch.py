"""Envoyer une consigne à un pane, sans savoir de quel type il est.

Pourquoi (S9, prépare le Master Tasker)
---------------------------------------
Le Tasker devra dire « exécute cette consigne » à un pane quelconque. Or
« envoyer » n'a pas la même forme selon la famille :

- ``PtyPane``      → écrire dans stdin (bytes, + retour chariot)
- ``HeadlessPane`` → un tour de conversation Claude (JSON, session suivie)

Sans abstraction, l'orchestrateur finirait en ``if pane.kind == "pty"``, ce que
le registre polymorphe (§6.9) interdit explicitement. On ajoute donc une
**capacité** au registre : chaque type déclare sa fonction d'envoi et s'il
sait signaler la fin d'une tâche.

``can_autocomplete`` porte la décision ADR-1 : seul le headless émet un
événement ``result`` exploitable. Le PTY, lui, est de l'ANSI opaque et
l'invariant n°1 interdit de le parser pour en tirer du sens métier. Un pane PTY
peut donc **recevoir** une consigne, mais il n'entre pas dans une boucle
d'orchestration automatique — c'est une limite assumée, pas un oubli.

Usage (à venir, S10) :

    entry = registry[pane.kind]
    if not entry.can_autocomplete:
        raise TaskerError("Ce type de pane ne sait pas signaler la fin.")
    await entry.dispatch(pane, brief)
"""

from __future__ import annotations

import logging

from .services.headless_manager import HeadlessManager
from .services.pane_manager import PaneError, PaneManager

logger = logging.getLogger("spacelabs.runtime")


async def pty_dispatch(pane, text: str) -> None:
    """Écrit la consigne dans le stdin du PTY, suivie d'un retour chariot.

    Le pane doit déjà tourner : on ne relance rien ici (ce serait une décision
    d'orchestration, pas d'envoi). Le texte part en bytes — la sortie, elle,
    reste en base64 de bout en bout (invariant n°1).
    """
    manager = PaneManager.get()
    runtime_id = str(pane.pk)
    if runtime_id not in manager.panes:
        raise PaneError(f"Pane {runtime_id} non démarré.")
    payload = (text.rstrip("\n") + "\n").encode("utf-8")
    manager.write(runtime_id, payload, owner_id=pane.workspace.owner_id)
    logger.info("dispatch pty pane=%s bytes=%d", runtime_id, len(payload))


async def headless_dispatch(pane, text: str) -> None:
    """Envoie un tour de conversation à la session Claude du pane.

    La session doit tourner (démarrée par ``chat_start``). La reprise et la
    persistance sont déjà gérées par ``HeadlessManager`` : rien à dupliquer.
    """
    headless = HeadlessManager.get()
    runtime_id = str(pane.pk)
    session = headless.sessions.get(runtime_id)
    if session is None or session.status != "running":
        raise PaneError(f"Session {runtime_id} non démarrée.")
    await headless.send(runtime_id, text, owner_id=pane.workspace.owner_id)
    logger.info("dispatch headless pane=%s chars=%d", runtime_id, len(text))
