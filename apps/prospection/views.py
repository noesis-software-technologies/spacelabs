from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import STAGE_OUVERTS, STAGES, Activity, Opportunity


@login_required
@ensure_csrf_cookie
def board(request):
    """Pipeline CRM : KPIs + colonnes par étape (nouveau→proposition), avec filtres.

    Visibilité et prise de décision : valeur du pipeline, priorités, contacts.
    """
    q = request.GET.get("q", "").strip()
    cat = request.GET.get("cat", "").strip()
    bmin = request.GET.get("bmin", "").strip()
    base = Opportunity.objects.all()
    if q:
        base = base.filter(Q(titre__icontains=q) | Q(description__icontains=q)
                           | Q(client_nom__icontains=q) | Q(client_societe__icontains=q))
    if cat:
        base = base.filter(categorie=cat)
    if bmin.isdigit():
        base = base.filter(budget_eur__gte=int(bmin))

    stages_count = dict(base.values_list("stage").annotate(n=Count("id")).values_list("stage", "n"))
    ouvert_qs = base.filter(stage__in=STAGE_OUVERTS)
    kpis = {
        "total": base.count(),
        "ouverts": ouvert_qs.count(),
        "pipeline_eur": ouvert_qs.aggregate(s=Sum("budget_eur"))["s"] or 0,
        "gagne": stages_count.get("gagne", 0),
        "gagne_eur": base.filter(stage="gagne").aggregate(s=Sum("budget_eur"))["s"] or 0,
    }
    colonnes = []
    for slug in STAGE_OUVERTS:
        label = dict(STAGES)[slug]
        items = list(base.filter(stage=slug).select_related("owner")[:40])
        colonnes.append({"slug": slug, "label": label,
                         "n": stages_count.get(slug, 0), "items": items})
    # Catégories pour le filtre (top 20 par volume)
    cats = list(Opportunity.objects.exclude(categorie="")
                .values_list("categorie").annotate(n=Count("id"))
                .order_by("-n")[:20])
    return render(request, "prospection/board.html", {
        "colonnes": colonnes, "kpis": kpis, "stages": STAGES,
        "cats": cats, "q": q, "cat": cat, "bmin": bmin, "active_nav": "prospection",
    })


@login_required
def opportunity_detail(request, pk):
    it = get_object_or_404(Opportunity, pk=pk)
    return render(request, "prospection/detail.html", {
        "it": it, "stages": STAGES, "activites": it.activites.all()[:50],
        "active_nav": "prospection",
    })


@login_required
@require_POST
def set_stage(request, pk):
    it = get_object_or_404(Opportunity, pk=pk)
    new = request.POST.get("stage", "")
    if new not in dict(STAGES):
        return JsonResponse({"ok": False, "error": "étape invalide"}, status=400)
    old = it.stage
    it.stage = new
    it.save(update_fields=["stage", "maj_le"])
    Activity.objects.create(opportunity=it, auteur=request.user,
                            texte=f"Étape : {dict(STAGES).get(old, old)} → {dict(STAGES)[new]}",
                            ancien_stage=old, nouveau_stage=new)
    return JsonResponse({"ok": True, "stage": new})


@login_required
@require_POST
def save_note(request, pk):
    it = get_object_or_404(Opportunity, pk=pk)
    note = (request.POST.get("note") or "").strip()
    if not note:
        return JsonResponse({"ok": False, "error": "note vide"}, status=400)
    it.notes = (it.notes + "\n" if it.notes else "") + note
    it.save(update_fields=["notes", "maj_le"])
    Activity.objects.create(opportunity=it, auteur=request.user, texte=f"Note : {note[:200]}")
    return JsonResponse({"ok": True})
