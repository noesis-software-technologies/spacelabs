"""Vues du Master Tasker — double représentation via render_htmx."""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from apps.common.htmx import render_htmx
from apps.workspaces.models import Workspace

from .forms import MissionForm, TaskForm
from .models import Mission, Task
from .services import eligible_panes, free_slots, refresh_ready


def _own_mission(request, pk) -> Mission:
    return get_object_or_404(Mission.objects.for_owner(request.user), pk=pk)


def _board_context(mission):
    refresh_ready(mission)
    tasks = list(mission.tasks.prefetch_related("depends_on", "assignments__pane"))
    columns = [
        {
            "key": status.value,
            "label": status.label,
            "tasks": [t for t in tasks if t.status == status],
        }
        for status in Task.BOARD_COLUMNS
    ]
    # Les tâches bloquées ne sont dans aucune colonne du board : on les montre
    # à part, sinon elles disparaissent silencieusement.
    return {
        "mission": mission,
        "columns": columns,
        "blocked": [t for t in tasks if t.status == Task.Status.BLOCKED],
        "failed": [t for t in tasks if t.status == Task.Status.FAILED],
        "eligible": eligible_panes(mission),
        "slots": free_slots(mission),
        "task_form": TaskForm(),
    }


@login_required
def mission_list(request, slug):
    workspace = get_object_or_404(Workspace.objects.for_owner(request.user), slug=slug)
    return render_htmx(
        request, "tasker/mission_list.html", "tasker/partials/_mission_list.html",
        {"workspace": workspace, "missions": workspace.missions.all(), "form": MissionForm()},
    )


@login_required
def mission_create(request, slug):
    workspace = get_object_or_404(Workspace.objects.for_owner(request.user), slug=slug)
    form = MissionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        mission = form.save(commit=False)
        mission.workspace = workspace
        mission.save()
        return redirect("tasker:mission", pk=mission.pk)
    return render_htmx(
        request, "tasker/mission_list.html", "tasker/partials/_mission_list.html",
        {"workspace": workspace, "missions": workspace.missions.all(), "form": form},
    )


@login_required
def mission(request, pk):
    m = _own_mission(request, pk)
    return render_htmx(
        request, "tasker/mission_detail.html", "tasker/partials/_board.html", _board_context(m)
    )


@login_required
@require_POST
def task_create(request, pk):
    m = _own_mission(request, pk)
    form = TaskForm(request.POST)
    if form.is_valid():
        task = form.save(commit=False)
        task.mission = m
        task.save()
    return render_htmx(
        request, "tasker/mission_detail.html", "tasker/partials/_board.html", _board_context(m)
    )


@login_required
@require_POST
def task_move(request, pk, task_id):
    """Déplacement d'une carte sur le board (glisser-déposer → POST htmx)."""
    m = _own_mission(request, pk)
    task = get_object_or_404(Task, pk=task_id, mission=m)
    target = request.POST.get("status")
    if target in {s.value for s in Task.BOARD_COLUMNS}:
        task.status = target
        task.save(update_fields=["status"])
    return render_htmx(
        request, "tasker/mission_detail.html", "tasker/partials/_board.html", _board_context(m)
    )


@login_required
@require_POST
def mission_state(request, pk):
    """Lancer / mettre en pause une mission."""
    m = _own_mission(request, pk)
    target = request.POST.get("status")
    if target in {Mission.Status.RUNNING, Mission.Status.PAUSED, Mission.Status.DRAFT}:
        m.status = target
        m.save(update_fields=["status"])
    return render_htmx(
        request, "tasker/mission_detail.html", "tasker/partials/_board.html", _board_context(m)
    )


@login_required
def swarm(request, pk):
    """Le DAG de la mission, en lecture seule. On comprend, on ne pilote pas."""
    from .graph import build, edge_path

    m = _own_mission(request, pk)
    tasks = list(m.tasks.prefetch_related("depends_on", "assignments__pane"))
    graph = build(tasks)
    paths = [
        {"d": edge_path(graph, a, b), "to": graph.by_key(b).state}
        for a, b in graph.edges
        if edge_path(graph, a, b)
    ]
    done = sum(1 for t in tasks if t.status == Task.Status.DONE)
    return render_htmx(
        request, "tasker/swarm.html", "tasker/partials/_swarm.html",
        {"mission": m, "graph": graph, "paths": paths,
         "done": done, "total": len(tasks)},
    )


@login_required
@require_POST
def mission_plan(request, pk):
    """Fait écrire le plan par Claude, puis réaffiche le board.

    Synchrone côté vue (l'utilisateur attend sa réponse) mais la fonction
    métier est async : on la déroule avec async_to_sync. En cas de plan
    invalide, on REFUSE et on affiche pourquoi — pas de création partielle.
    """
    from asgiref.sync import async_to_sync

    from .planner import PlanError, request_plan

    m = _own_mission(request, pk)
    error = None
    try:
        pane = _ensure_planner(m)
        if pane is None:
            error = "Impossible de créer le pane planificateur."
        else:
            async_to_sync(request_plan)(m, feedback=request.POST.get("feedback", ""))
    except PlanError as exc:
        error = str(exc)
    except Exception as exc:  # noqa: BLE001
        error = f"Planification impossible : {exc}"

    context = _board_context(m)
    context["plan_error"] = error
    return render_htmx(request, "tasker/mission_detail.html", "tasker/partials/_board.html", context)


def _ensure_planner(mission):
    """Crée à la demande le pane de service qui planifie (ADR-2)."""
    from apps.workspaces.models import HeadlessPane

    if mission.planner_pane_id:
        return mission.planner_pane
    pane = HeadlessPane.objects.create(
        workspace=mission.workspace, title=f"Planner #{mission.pk}", is_system=True,
    )
    mission.planner_pane = pane
    mission.save(update_fields=["planner_pane"])
    return pane


@login_required
@require_POST
def mission_delete(request, pk):
    m = _own_mission(request, pk)
    slug = m.workspace.slug
    m.delete()
    if request.headers.get("HX-Request"):
        return HttpResponse("")
    return redirect("tasker:missions", slug=slug)
