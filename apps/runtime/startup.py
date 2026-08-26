"""Amorçage du runtime au démarrage du serveur — indépendant du serveur ASGI.

Daphne n'émet pas (fiablement) les événements ASGI 'lifespan' ; on ne s'y fie
donc pas. À l'import du module ASGI (une fois par processus serveur), on :
1. estampille le battement de cette génération ;
2. réconcilie la DB (panes 'running' d'une génération morte → morts) ;
3. lance un thread daemon qui rafraîchit le battement périodiquement.

Un thread (et non une tâche asyncio) : ça marche quel que soit le serveur et
sans dépendre d'une boucle d'événements présente à l'import.
"""
import logging
import threading
import time

from django.conf import settings
from django.db import connection

from .runtime_state import BOOT_ID, touch_heartbeat

logger = logging.getLogger("spacelabs.runtime")

_started = False
_lock = threading.Lock()


def on_server_boot() -> None:
    """Idempotent : réconciliation + démarrage du battement, une seule fois."""
    global _started
    with _lock:
        if _started:
            return
        _started = True
    try:
        from apps.ops.services import reconcile_boot

        touch_heartbeat()
        n = reconcile_boot(BOOT_ID)
        logger.info("boot génération %s — %s pane(s) réconcilié(s)", BOOT_ID[:8], n)
        try:
            from apps.skills.services import ensure_builtins

            n_skills = ensure_builtins()
            if n_skills:
                logger.info("boot — %s skill(s) intégrée(s) créée(s)", n_skills)
        except Exception as exc:  # noqa: BLE001 — optionnel
            logger.debug("seed skills ignoré : %s", exc)

        # Les tâches d'orchestration en vol n'ont pas survécu non plus.
        try:
            from apps.tasker.services import reconcile_boot as tasker_reconcile

            freed = tasker_reconcile()
            if freed:
                logger.info("boot — %s tâche(s) d'orchestration libérée(s)", freed)
        except Exception as exc:  # noqa: BLE001 — le Tasker est optionnel
            logger.debug("réconciliation tasker ignorée : %s", exc)
    except Exception as exc:  # noqa: BLE001 — ne jamais empêcher le serveur de démarrer
        logger.warning("réconciliation au boot échouée : %s", exc)
    finally:
        connection.close()  # ne pas garder la connexion du thread principal ouverte
    _start_heartbeat_thread()


def _start_heartbeat_thread() -> None:
    interval = max(5, settings.COCKPIT_HEARTBEAT_STALE_SECONDS // 3)

    def loop():
        while True:
            time.sleep(interval)
            try:
                touch_heartbeat()
            except Exception as exc:  # noqa: BLE001
                logger.debug("battement raté : %s", exc)
            finally:
                connection.close()  # connexion propre à ce thread

    thread = threading.Thread(target=loop, name="cockpit-heartbeat", daemon=True)
    thread.start()
    logger.info("battement runtime démarré (toutes les %ss)", interval)
