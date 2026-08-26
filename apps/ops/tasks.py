"""Tâches Celery — enveloppes minces autour de services.py (logique testée à
part). Aucune règle métier ici : juste le branchement au scheduler."""
from celery import shared_task

from . import services


@shared_task(name="ops.snapshot_usage")
def snapshot_usage():
    return services.snapshot_all_owners()


@shared_task(name="ops.reap_zombies")
def reap_zombies():
    return services.reap_zombies()


@shared_task(name="ops.archive_eventlog")
def archive_eventlog():
    return services.archive_eventlog()


@shared_task(name="ops.scan_mcp_auth")
def scan_mcp_auth():
    return services.scan_mcp_auth()
