import datetime as _dt

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import (ETATS, MOTIFS_PERTE, MOTIFS_REJET, STATUTS, STATUTS_ACTIFS,
                     Activity, Opportunity)
from .scoring import compute_score

# Vues métier prédéfinies (cahier des charges § Vues à créer).
VUES = {
    "aujourdhui": "À traiter aujourd'hui",
    "offres_attente": "Offres en attente (relance)",
    "vivier": "Vivier (opportunités futures)",
    "multi": "Comptes multi-annonces",
    "rejets_mois": "Rejets du mois",
}


def _apply_vue(qs, vue):
    today = timezone.localdate()
    if vue == "aujourdhui":
        return qs.filter(stage__in=["detecte", "qualifie"])
    if vue == "offres_attente":
        return qs.filter(stage="offre_envoyee",
                         date_offre__lte=today - _dt.timedelta(days=2),
                         date_offre__gte=today - _dt.timedelta(days=10))
    if vue == "vivier":
        return qs.filter(stage="opportunite_future").order_by("date_relance")
    if vue == "multi":
        return qs.filter(compte_multi=True)
    if vue == "rejets_mois":
        return qs.filter(stage="rejete", maj_le__year=today.year, maj_le__month=today.month)
    return qs


@login_required
@ensure_csrf_cookie
def board(request):
    """Pipeline CRM conforme au cahier des charges : KPIs de pilotage, filtres,
    vues métier, colonnes par statut actionnable, score de priorisation."""
    q = request.GET.get("q", "").strip()
    cat = request.GET.get("cat", "").strip()
    bmin = request.GET.get("bmin", "").strip()
    etat = request.GET.get("etat", "").strip()
    vue = request.GET.get("vue", "").strip()

    base = Opportunity.objects.all()
    if q:
        base = base.filter(Q(titre__icontains=q) | Q(description__icontains=q)
                           | Q(client_nom__icontains=q) | Q(client_societe__icontains=q))
    if cat:
        base = base.filter(categorie=cat)
    if bmin.isdigit():
        base = base.filter(budget_eur__gte=int(bmin))
    if etat:
        base = base.filter(etat=etat)
    if vue:
        base = _apply_vue(base, vue)

    sc = dict(base.values_list("stage").annotate(n=Count("id")).values_list("stage", "n"))
    actifs = base.filter(stage__in=STATUTS_ACTIFS)
    envoyees = base.filter(stage__in=["offre_envoyee", "echange", "gagne", "perdu", "sans_reponse"]).count()
    kpis = {
        "total": base.count(),
        "pipeline_eur": actifs.aggregate(s=Sum("budget_eur"))["s"] or 0,
        "qualifies": sc.get("qualifie", 0),
        "gagne": sc.get("gagne", 0),
        "gagne_eur": base.filter(stage="gagne").aggregate(s=Sum("budget_eur"))["s"] or 0,
        "score_moyen": round(base.aggregate(a=Avg("score"))["a"] or 0),
        "taux_reponse": round(100 * sc.get("echange", 0) / envoyees, 1) if envoyees else 0,
        "taux_transfo": round(100 * sc.get("gagne", 0) / envoyees, 1) if envoyees else 0,
    }
    if vue:  # une vue = une liste simple, pas des colonnes
        items = list(base.select_related("owner").order_by("-score", "-budget_eur")[:120])
        colonnes = None
    else:
        colonnes = []
        for slug in STATUTS_ACTIFS:
            label = dict(STATUTS)[slug]
            colonnes.append({"slug": slug, "label": label, "n": sc.get(slug, 0),
                             "items": list(base.filter(stage=slug)
                                           .select_related("owner").order_by("-score")[:40])})
        items = None
    cats = list(Opportunity.objects.exclude(categorie="")
                .values_list("categorie").annotate(n=Count("id")).order_by("-n")[:20])
    return render(request, "prospection/board.html", {
        "colonnes": colonnes, "items": items, "kpis": kpis, "stages": STATUTS,
        "etats": ETATS, "cats": cats, "vues": VUES,
        "q": q, "cat": cat, "bmin": bmin, "etat": etat, "vue": vue,
        "active_nav": "prospection",
    })


@login_required
def opportunity_detail(request, pk):
    it = get_object_or_404(Opportunity, pk=pk)
    from .scoring import suggest_rejet
    return render(request, "prospection/detail.html", {
        "it": it, "stages": STATUTS, "etats": ETATS,
        "motifs_rejet": MOTIFS_REJET, "motifs_perte": MOTIFS_PERTE,
        "rejet_suggere": suggest_rejet(it),
        "activites": it.activites.all()[:50], "active_nav": "prospection",
    })


@login_required
def modeles(request):
    """Modèles de messages + checklist (cahier des charges § Modèles de messages)."""
    return render(request, "prospection/modeles.html", {"active_nav": "prospection"})


@login_required
@require_POST
def set_stage(request, pk):
    it = get_object_or_404(Opportunity, pk=pk)
    new = request.POST.get("stage", "")
    if new not in dict(STATUTS):
        return JsonResponse({"ok": False, "error": "statut invalide"}, status=400)
    old = it.stage
    it.stage = new
    if new == "offre_envoyee" and not it.date_offre:
        it.date_offre = timezone.localdate()
    it.save(update_fields=["stage", "date_offre", "maj_le"])
    Activity.objects.create(opportunity=it, auteur=request.user,
                            texte=f"Statut : {dict(STATUTS).get(old, old)} → {dict(STATUTS)[new]}",
                            ancien_stage=old, nouveau_stage=new)
    return JsonResponse({"ok": True, "stage": new})


@login_required
@require_POST
def update_field(request, pk):
    """MAJ légère d'un champ CRM (etat, priorite, motif_rejet, motif_perte,
    offres_detection, date_relance) + recalcul du score."""
    it = get_object_or_404(Opportunity, pk=pk)
    champ = request.POST.get("champ", "")
    val = request.POST.get("valeur", "")
    allowed = {"etat", "priorite", "motif_rejet", "motif_perte", "offres_detection", "date_relance"}
    if champ not in allowed:
        return JsonResponse({"ok": False, "error": "champ non autorisé"}, status=400)
    if champ == "offres_detection":
        it.offres_detection = int(val) if val.isdigit() else None
    elif champ == "date_relance":
        it.date_relance = val or None
    else:
        setattr(it, champ, val)
    it.score = compute_score(it)
    it.save()
    return JsonResponse({"ok": True, "score": it.score})


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
