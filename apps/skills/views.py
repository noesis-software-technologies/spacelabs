"""Skills : liste dans le dock, application à un agent."""
from asgiref.sync import async_to_sync
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.workspaces.models import Pane, Workspace

from .models import Skill
from .services import SkillError, apply_to_pane


@login_required
def panel(request, slug):
    workspace = get_object_or_404(Workspace.objects.for_owner(request.user), slug=slug)
    return render(request, "skills/partials/_panel.html", {
        "workspace": workspace,
        "skills": Skill.objects.visible_for(request.user),
    })


@login_required
@require_POST
def apply(request, pk):
    """Applique une skill à un agent (glisser-déposer ou clic)."""
    skill = get_object_or_404(Skill.objects.visible_for(request.user), pk=pk)
    pane = get_object_or_404(
        Pane.objects.filter(workspace__owner=request.user), pk=request.POST.get("pane")
    )
    if pane.status != Pane.Status.RUNNING:
        return JsonResponse(
            {"ok": False, "reply": "Cet agent n'est pas démarré."}, status=409
        )
    try:
        reply = async_to_sync(apply_to_pane)(skill, pane)
    except SkillError as exc:
        return JsonResponse({"ok": False, "reply": str(exc)}, status=400)
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"ok": False, "reply": f"Envoi impossible : {exc}"}, status=502)
    return JsonResponse({"ok": True, "reply": reply})
