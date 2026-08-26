"""Exécution d'une intention vocale — pur DB, séparé du parsing.

Le parsing (``intents.parse``) dit CE QU'ON VEUT ; ici on le FAIT. Séparés
pour que le vocabulaire soit testable sans base, et l'exécution testable sans
reconnaissance vocale.

Rien n'est exécuté à l'aveugle : chaque action renvoie une phrase qui dit
exactement ce qui a été fait, affichée dans le journal de Bridge.
"""
from __future__ import annotations

import logging

from apps.workspaces.models import HeadlessPane, Pane

logger = logging.getLogger("spacelabs.voice")


def execute(intent, workspace) -> str:
    """Applique l'intention au workspace. Renvoie la réponse à afficher."""
    from apps.tasker.models import Mission, Task
    from apps.voice.intents import describe_unknown

    kind = intent.kind

    if kind == "status":
        panes = Pane.objects.filter(workspace=workspace, is_system=False)
        running = panes.filter(status=Pane.Status.RUNNING).count()
        missions = Mission.objects.filter(workspace=workspace, status=Mission.Status.RUNNING)
        parts = [f"{running} agent{'s' if running > 1 else ''} en cours sur {panes.count()}."]
        for m in missions:
            done = m.tasks.filter(status=Task.Status.DONE).count()
            parts.append(f"Mission « {m.goal[:40]} » : {done}/{m.tasks.count()} tâches faites.")
        return " ".join(parts)

    if kind == "spawn":
        from apps.runtime.capacity import CapacityError, ensure_can_start

        wanted = intent.args.get("count", 1)
        created = 0
        for _ in range(wanted):
            pane = HeadlessPane.objects.create(workspace=workspace)
            try:
                ensure_can_start(pane)
            except CapacityError as exc:
                pane.delete()
                if created:
                    return f"{created} agent(s) créé(s), puis arrêté : {exc}"
                return str(exc)
            created += 1
        return f"{created} agent{'s' if created > 1 else ''} ajouté{'s' if created > 1 else ''}. Démarre-les depuis la grille."

    if kind == "task_add":
        mission = Mission.objects.filter(workspace=workspace).order_by("-created_at").first()
        if mission is None:
            return "Aucune mission où ranger cette tâche. Crée d'abord une mission."
        key = f"V{mission.tasks.count() + 1}"
        Task.objects.create(mission=mission, key=key, title=intent.args["title"][:200],
                            brief=intent.args["title"])
        return f"Tâche {key} ajoutée à « {mission.goal[:40]} »."

    if kind in ("mission_start", "mission_pause"):
        mission = Mission.objects.filter(workspace=workspace).order_by("-created_at").first()
        if mission is None:
            return "Aucune mission dans ce workspace."
        mission.status = (
            Mission.Status.RUNNING if kind == "mission_start" else Mission.Status.PAUSED
        )
        mission.save(update_fields=["status"])
        verbe = "lancée" if kind == "mission_start" else "mise en pause"
        return f"Mission « {mission.goal[:40]} » {verbe}."

    if kind == "mission_plan":
        mission = Mission.objects.filter(workspace=workspace).order_by("-created_at").first()
        if mission is None:
            return "Aucune mission à planifier."
        # La planification est un aller-retour avec Claude : on ne la fait pas
        # dans la requête vocale, on renvoie l'utilisateur vers le board.
        return f"Ouvre le board de « {mission.goal[:40]} » et lance « Faire planifier »."

    if kind == "density":
        return f"Densité : {intent.args['level']}."

    if kind == "panic":
        from apps.observer.models import ObserverSettings

        settings_obj = ObserverSettings.for_owner(workspace.owner)
        settings_obj.live = False
        settings_obj.save(update_fields=["live"])
        Pane.objects.filter(workspace__owner=workspace.owner).update(is_public=False)
        return "Direct coupé, tous les panes repassés en privé."

    if kind == "dispatch":
        return (
            f"Consigne notée pour l'agent {intent.args.get('pane')} — "
            "l'envoi direct par la voix arrive au prochain sprint."
        )

    return describe_unknown()
