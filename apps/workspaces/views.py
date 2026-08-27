"""Vues workspaces — orchestration seulement, Forms systématiques,
double représentation via render_htmx, tenancy ``for_owner`` partout
(l'objet d'un autre user ⇒ 404, jamais 403 bavard)."""
import json
import os
from pathlib import Path

from django.conf import settings as dj_settings

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django_htmx.http import HttpResponseClientRedirect, trigger_client_event

from apps.common.htmx import render_htmx

from apps.runtime.capacity import workspace_limit

from .forms import WorkspaceForm, form_for_kind
from .agents import presets_with_availability
from .models import HeadlessPane, Pane, Workspace, concrete_panes, registry


# Paliers de densité — miroir exact des blocs [data-density] du design system
# (design-system.css). Toucher ici sans toucher le CSS = incohérence visible.
DENSITIES = [
    {"key": "cozy", "short": "Coz", "hint": "1–4 agents — confort de lecture"},
    {"key": "compact", "short": "Cmp", "hint": "4–6 agents"},
    {"key": "dense", "short": "Dns", "hint": "6–12 agents"},
    {"key": "micro", "short": "Mic", "hint": "12–16 agents sur un seul écran"},
]
# "auto" = le CSS choisit selon data-count ; sinon on force la grille.
COLUMN_CHOICES = ["auto", "2", "3", "4", "5", "6"]


def _own_workspace(request, slug):
    return get_object_or_404(Workspace.objects.for_owner(request.user), slug=slug)


@login_required
def home(request):
    """Point d'entrée : redirige vers le premier workspace (créé au besoin)."""
    workspace = Workspace.objects.for_owner(request.user).first()
    if workspace is None:
        workspace = Workspace.objects.create(owner=request.user, name="Local", cwd="~")
    return redirect("workspaces:detail", slug=workspace.slug)


@login_required
def detail(request, slug):
    workspace = _own_workspace(request, slug)
    from apps.observer.models import ObserverSettings

    from apps.ops.models import MCPAlert

    # Les panes de service (planificateur) ne sont pas des agents de travail :
    # ils ne s'affichent pas dans la grille.
    panes = concrete_panes(workspace.panes.filter(is_system=False).order_by("order", "id"))
    mcp_by_pane = dict(
        MCPAlert.objects.filter(pane__workspace=workspace, resolved=False)
        .values_list("pane_id", "pk")
    )
    context = {
        "workspace": workspace,
        "panes": [(pane, registry[pane.kind], mcp_by_pane.get(pane.pk)) for pane in panes],
        "pane_kinds": registry,
        "observer_live": ObserverSettings.for_owner(request.user).live,
        "priming_prompts": dj_settings.COCKPIT_PRIMING_PROMPTS,
        # Réglages de la grille n-agents (rendus dans la toolbar).
        "max_panes": dj_settings.COCKPIT_MAX_PANES,
        # Plafond effectif de CE workspace (le sien, sinon le défaut global) et
        # nombre d'agents réellement en cours — la jauge de la toolbar.
        "workspace_limit": workspace_limit(workspace),
        "running_count": sum(1 for p in panes if p.status == Pane.Status.RUNNING),
        "densities": DENSITIES,
        "column_choices": COLUMN_CHOICES,
    }
    return render_htmx(
        request, "workspaces/detail.html", "workspaces/partials/_workspace_view.html", context
    )


@login_required
def create(request):
    form = WorkspaceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        workspace = form.save(commit=False)
        workspace.owner = request.user
        workspace.save()
        if request.htmx:
            response = HttpResponseClientRedirect(workspace_url(workspace))
            return trigger_client_event(response, "workspacesChanged")
        return redirect("workspaces:detail", slug=workspace.slug)
    return render_htmx(
        request, "workspaces/form.html", "workspaces/partials/_workspace_form.html",
        {"form": form, "title": "Nouveau workspace", "post_url": reverse("workspaces:create")},
    )


@login_required
def update(request, slug):
    workspace = _own_workspace(request, slug)
    form = WorkspaceForm(request.POST or None, instance=workspace)
    if request.method == "POST" and form.is_valid():
        form.save()
        if request.htmx:
            response = HttpResponseClientRedirect(workspace_url(workspace))
            return trigger_client_event(response, "workspacesChanged")
        return redirect("workspaces:detail", slug=workspace.slug)
    return render_htmx(
        request, "workspaces/form.html", "workspaces/partials/_workspace_form.html",
        {"form": form, "title": f"Renommer « {workspace.name} »",
         "post_url": reverse("workspaces:update", kwargs={"slug": workspace.slug})},
    )


@login_required
def delete(request, slug):
    workspace = _own_workspace(request, slug)
    if request.method != "POST":
        return render_htmx(
            request, "workspaces/confirm_delete.html", "workspaces/partials/_confirm_delete.html",
            {"workspace": workspace},
        )
    workspace.delete()
    if request.htmx:
        response = HttpResponseClientRedirect("/cockpit/")
        return trigger_client_event(response, "workspacesChanged")
    return redirect("workspaces:home")


@login_required
def pane_create(request, slug, kind):
    workspace = _own_workspace(request, slug)
    if kind not in registry:
        return HttpResponse(status=404)
    FormClass = form_for_kind(kind)
    form = FormClass(request.POST or None)
    if request.method == "POST" and form.is_valid():
        pane = form.save(commit=False)
        pane.workspace = workspace
        pane.order = workspace.panes.count()
        pane.save()
        from django.conf import settings as dj_settings

        entry = registry[pane.kind]
        response = render(
            request, entry.partial,
            {"pane": pane, "workspace": workspace, "entry": entry,
             "priming_prompts": dj_settings.COCKPIT_PRIMING_PROMPTS},
        )
        return trigger_client_event(response, "paneCreated", {"paneId": pane.pk})
    # Le formulaire (ouverture GET ou POST invalide) vit dans l'overlay #modal,
    # jamais dans #pane-grid : on retargette pour que l'erreur reste dans la
    # modale au lieu de s'ajouter à la grille (le succès, lui, rend le pane et
    # vise #pane-grid via le hx-target du formulaire).
    response = render_htmx(
        request, "workspaces/form.html", "workspaces/partials/_pane_form.html",
        {"form": form, "workspace": workspace, "kind": kind,
         "title": f"Nouveau pane — {registry[kind].label}"},
    )
    if getattr(request, "htmx", False):
        response["HX-Retarget"] = "#modal"
        response["HX-Reswap"] = "innerHTML"
    return response


@login_required
def agent_picker(request, slug):
    """Sélecteur d'agents : ouvre la liste des presets dans la modale #modal.
    Chaque carte déclenche `pane_create` avec les valeurs du preset (hx-vals),
    donc la validation liste-blanche du Sprint 17 s'applique inchangée."""
    workspace = _own_workspace(request, slug)
    return render_htmx(
        request, "workspaces/form.html", "workspaces/partials/_agent_picker.html",
        {"workspace": workspace, "presets": presets_with_availability()},
    )


@login_required
def pane_delete(request, slug, pane_id):
    workspace = _own_workspace(request, slug)
    pane = get_object_or_404(Pane.objects.for_owner(request.user), pk=pane_id, workspace=workspace)
    if request.method != "POST":
        return HttpResponse(status=405)
    pane.delete()
    return HttpResponse("")


def workspace_url(workspace):
    return reverse("workspaces:detail", kwargs={"slug": workspace.slug})


@login_required
def sidebar(request):
    """Partial sidebar seul — rafraîchi par l'événement ``workspacesChanged``."""
    return render(
        request, "workspaces/partials/_sidebar_list.html",
        {"workspaces": Workspace.objects.for_owner(request.user).with_counts(), "current_slug": None},
    )


@login_required
def explorer(request, slug):
    """Arborescence d'un dossier du workspace (dock → Éditeur)."""
    from .services.files import FileAccessError, list_dir

    workspace = _own_workspace(request, slug)
    relative = request.GET.get("path", "")
    error, entries = None, []
    try:
        entries = list_dir(workspace, relative)
    except FileAccessError as exc:
        error = str(exc)
    parent = str(Path(relative).parent) if relative not in ("", ".") else None
    return render(request, "workspaces/partials/_explorer.html", {
        "workspace": workspace, "entries": entries, "cwd": relative,
        "parent": "" if parent == "." else parent, "error": error,
    })


@login_required
def file_view(request, slug):
    """Aperçu d'un fichier texte. Refuse secrets, binaires et hors-racine."""
    from .services.files import FileAccessError, read_text

    workspace = _own_workspace(request, slug)
    relative = request.GET.get("path", "")
    content, truncated, error = "", False, None
    try:
        content, truncated = read_text(workspace, relative)
    except FileAccessError as exc:
        error = str(exc)
    return render(request, "workspaces/partials/_file.html", {
        "workspace": workspace, "path": relative, "content": content,
        "truncated": truncated, "error": error,
    })


# ── History flux ────────────────────────────────────────────────────────────

@login_required
def history_flux(request, slug):
    """Vue unifiée de l'historique multi-agents d'un workspace."""
    from apps.chat.models import EventLog

    workspace = _own_workspace(request, slug)
    pane_ids = list(workspace.panes.values_list("id", flat=True))

    q = request.GET.get("q", "").strip()
    pane_filter = request.GET.get("pane")

    events = (
        EventLog.objects.filter(pane_id__in=pane_ids)
        .select_related("pane")
        .order_by("created_at")
    )
    if pane_filter:
        events = events.filter(pane_id=pane_filter)
    if q:
        events = events.filter(normalized__icontains=q)

    headless_panes = HeadlessPane.objects.filter(workspace=workspace)

    return render(request, "workspaces/history_flux.html", {
        "workspace": workspace,
        "events": events[:500],
        "headless_panes": headless_panes,
        "q": q,
        "pane_filter": pane_filter,
    })


# ── Obsidian export ─────────────────────────────────────────────────────────

@login_required
def obsidian_export(request, slug):
    """Génère un vault Obsidian (.md) depuis l'historique du workspace."""
    from apps.chat.models import EventLog

    workspace = _own_workspace(request, slug)
    vault_path = Path(f"/tmp/spacelabs_vault/{workspace.slug}")
    vault_path.mkdir(parents=True, exist_ok=True)

    headless_panes = list(HeadlessPane.objects.filter(workspace=workspace))
    pane_ids = [p.pk for p in headless_panes]

    # _workspace.md
    agent_links = "\n".join(f"- [[{p.title}]] `{p.model_id}`" for p in headless_panes)
    (vault_path / "_workspace.md").write_text(
        f"# {workspace.name}\n\n## Agents\n{agent_links}\n\n"
        f"Workspace : `{workspace.slug}`\n",
        encoding="utf-8",
    )

    # Fichier par agent
    for pane in headless_panes:
        events = EventLog.objects.filter(pane=pane).order_by("seq")
        lines = [f"# {pane.title}\n\nModel : `{pane.model_id}`\n\n## Historique\n"]
        for ev in events:
            norm = ev.normalized or {}
            kind = norm.get("kind", ev.event_type)
            if kind == "assistant":
                for block in norm.get("blocks", []):
                    if block.get("type") == "text":
                        lines.append(f"**assistant** : {block['text'][:500]}\n")
            elif kind == "user":
                lines.append(f"**human** : {norm.get('text', '')[:500]}\n")
        safe = pane.title.replace("/", "-").replace("·", "-").strip()
        (vault_path / f"{safe}.md").write_text("\n".join(lines), encoding="utf-8")

    files = sorted(p.name for p in vault_path.iterdir())
    return JsonResponse({"vault_path": str(vault_path), "files": files})
