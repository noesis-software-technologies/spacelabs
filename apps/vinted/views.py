from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (PLATEFORMES, STATUTS_ENVOI, STATUTS_ENVOI_A_FAIRE,
                     STOCK_DESTINS, STOCK_SOURCES, STOCK_STATUTS, TRANSPORTEURS,
                     Fournisseur, SaleOrderLine, StockItem, VintedOrder)

# Champs éditables en ligne (dashboard) + leur type pour la coercition.
_EDIT_TEXT = {"titre", "acheteur", "numero", "tracking", "notes"}
_EDIT_DECIMAL = {"prix_achat", "prix_vente", "frais"}
_EDIT_DATE = {"date_vente", "date_expedition", "date_livraison"}
_EDIT_CHOICE = {
    "plateforme": {k for k, _ in PLATEFORMES},
    "statut_envoi": {k for k, _ in STATUTS_ENVOI},
    "transporteur": {k for k, _ in TRANSPORTEURS} | {""},
}

# Entrepôt : champs éditables en ligne.
_STK_TEXT = {"nom", "reference", "gradeur", "notes"}
_STK_DECIMAL = {"prix_achat"}
_STK_INT = {"quantite"}
_STK_DATE = {"date_achat", "date_reception"}
_STK_CHOICE = {
    "source": {k for k, _ in STOCK_SOURCES},
    "destin": {k for k, _ in STOCK_DESTINS},
    "statut": {k for k, _ in STOCK_STATUTS},
}


def _kpis(orders):
    """Agrégats monétaires calculés en Python (le bénéfice est une propriété)."""
    ca = Decimal("0")
    cout = Decimal("0")
    benef = Decimal("0")
    for o in orders:
        ca += o.prix_vente or 0
        cout += o.prix_achat or 0
        benef += o.benefice
    marge = round(benef / cout * 100, 1) if cout else None
    return {"ca": ca, "cout": cout, "benefice": benef, "marge": marge}


@login_required
def dashboard(request):
    """Dashboard de vérification des envois + suivi achat/vente/bénéfice."""
    orders = list(VintedOrder.objects.select_related("listing").prefetch_related("lignes__stock_item").all())

    a_expedier = [o for o in orders if o.statut_envoi in STATUTS_ENVOI_A_FAIRE]
    en_transit = [o for o in orders if o.statut_envoi == "expedie"]
    recents = orders[:25]

    par_statut = dict(
        VintedOrder.objects.values_list("statut_envoi")
        .annotate(n=Count("id")).values_list("statut_envoi", "n")
    )
    par_plateforme = dict(
        VintedOrder.objects.values_list("plateforme")
        .annotate(n=Count("id")).values_list("plateforme", "n")
    )
    # Alerte : expédié depuis > 7 jours sans livraison confirmée.
    limite = timezone.localdate() - timezone.timedelta(days=7)
    en_retard = [o for o in en_transit
                 if o.date_expedition and o.date_expedition < limite]

    return render(request, "vinted/dashboard.html", {
        "kpis": _kpis(orders),
        "total": len(orders),
        "a_expedier": a_expedier,
        "en_transit": en_transit,
        "en_retard": en_retard,
        "recents": recents,
        "par_statut": par_statut,
        "par_plateforme": par_plateforme,
        "statuts": STATUTS_ENVOI,
        "plateformes": PLATEFORMES,
        "transporteurs": TRANSPORTEURS,
        "fournisseurs": list(Fournisseur.objects.filter(actif=True)),
        "sans_suivi": [o for o in orders
                       if o.statut_envoi in ("expedie", "livre") and not o.tracking],
        "active_nav": "vinted",
    })


@login_required
@require_POST
def order_ship(request, pk):
    """Marque une commande comme expédiée (tracking + transporteur optionnels)."""
    order = get_object_or_404(VintedOrder, pk=pk)
    order.transporteur = request.POST.get("transporteur", order.transporteur).strip()
    order.tracking = request.POST.get("tracking", order.tracking).strip()
    order.statut_envoi = "expedie"
    if not order.date_expedition:
        order.date_expedition = timezone.localdate()
    order.save(update_fields=["transporteur", "tracking", "statut_envoi",
                              "date_expedition", "maj_le"])
    return redirect("vinted:dashboard")


@login_required
@require_POST
def order_delivered(request, pk):
    """Confirme la livraison d'une commande expédiée."""
    order = get_object_or_404(VintedOrder, pk=pk)
    order.statut_envoi = "livre"
    if not order.date_livraison:
        order.date_livraison = timezone.localdate()
    order.save(update_fields=["statut_envoi", "date_livraison", "maj_le"])
    return redirect("vinted:dashboard")


@login_required
@require_POST
def order_update(request, pk):
    """Édition inline d'un champ d'une commande (dashboard JS).

    Reçoit `field` + `value`, valide/coerce selon le type, sauvegarde, et
    renvoie le bénéfice/marge recalculés."""
    order = get_object_or_404(VintedOrder, pk=pk)
    field = (request.POST.get("field") or "").strip()
    raw = request.POST.get("value", "")
    val = raw.strip()
    try:
        if field in _EDIT_TEXT:
            setattr(order, field, val)
        elif field in _EDIT_DECIMAL:
            setattr(order, field, Decimal(val) if val != "" else (Decimal("0") if field == "frais" else None))
        elif field in _EDIT_DATE:
            from datetime import date
            setattr(order, field, date.fromisoformat(val) if val else None)
        elif field in _EDIT_CHOICE:
            if val not in _EDIT_CHOICE[field]:
                return JsonResponse({"ok": False, "error": "valeur invalide"}, status=400)
            setattr(order, field, val)
        elif field == "fournisseur":
            if val == "":
                order.fournisseur = None
            elif val.isdigit() and Fournisseur.objects.filter(pk=int(val)).exists():
                order.fournisseur_id = int(val)
            else:
                return JsonResponse({"ok": False, "error": "fournisseur inconnu"}, status=400)
        else:
            return JsonResponse({"ok": False, "error": "champ non éditable"}, status=400)
    except (InvalidOperation, ValueError):
        return JsonResponse({"ok": False, "error": "format invalide"}, status=400)
    order.save()
    return JsonResponse({
        "ok": True,
        "benefice": f"{order.benefice:.2f}",
        "marge": "—" if order.marge_pct is None else f"{order.marge_pct} %",
        "statut_display": order.get_statut_envoi_display(),
        "transporteur_label": order.transporteur_label,
        "tracking_url": order.tracking_url,
    })


@login_required
@require_POST
def order_tracking(request, pk):
    """Renseigne / corrige le transporteur et le n° de suivi d'une commande
    (utile pour compléter une commande déjà passée « expédié » sans suivi)."""
    order = get_object_or_404(VintedOrder, pk=pk)
    order.transporteur = request.POST.get("transporteur", order.transporteur).strip()
    order.tracking = request.POST.get("tracking", order.tracking).strip()
    # Si on ajoute un suivi à une commande encore à préparer, on la passe expédiée.
    if order.tracking and order.statut_envoi in STATUTS_ENVOI_A_FAIRE:
        order.statut_envoi = "expedie"
        if not order.date_expedition:
            order.date_expedition = timezone.localdate()
    order.save(update_fields=["transporteur", "tracking", "statut_envoi",
                              "date_expedition", "maj_le"])
    return redirect("vinted:dashboard")


# ── Entrepôt (stock non listé) ──
@login_required
@require_POST
def order_create(request):
    """Crée une nouvelle commande depuis le formulaire d'ajout rapide du dashboard."""
    titre = (request.POST.get("titre") or "").strip()
    if not titre:
        return redirect("vinted:dashboard")
    prix_vente_raw = (request.POST.get("prix_vente") or "").strip()
    prix_achat_raw = (request.POST.get("prix_achat") or "").strip()
    try:
        prix_vente = Decimal(prix_vente_raw) if prix_vente_raw else None
    except InvalidOperation:
        prix_vente = None
    try:
        prix_achat = Decimal(prix_achat_raw) if prix_achat_raw else None
    except InvalidOperation:
        prix_achat = None
    VintedOrder.objects.create(
        titre=titre,
        prix_vente=prix_vente,
        prix_achat=prix_achat,
        date_vente=timezone.localdate(),
        plateforme=request.POST.get("plateforme") or "vinted",
    )
    return redirect("vinted:dashboard")


@login_required
def entrepot(request):
    """Vue entrepôt : articles achetés pas encore listés + leur devenir."""
    items = list(StockItem.objects.all())
    cout_total = sum(i.cout_total for i in items)
    par_statut = dict(StockItem.objects.values_list("statut")
                      .annotate(n=Count("id")).values_list("statut", "n"))
    par_destin = dict(StockItem.objects.values_list("destin")
                      .annotate(n=Count("id")).values_list("destin", "n"))
    a_grader = [i for i in items if i.destin in ("grade_collectaura", "grade_ccc")
                and i.statut not in ("grade", "vendu", "liste")]
    return render(request, "vinted/entrepot.html", {
        "items": items,
        "cout_total": cout_total,
        "nb": len(items),
        "par_statut": par_statut,
        "par_destin": par_destin,
        "a_grader": a_grader,
        "sources": STOCK_SOURCES,
        "destins": STOCK_DESTINS,
        "statuts_stock": STOCK_STATUTS,
        "fournisseurs": list(Fournisseur.objects.filter(actif=True)),
        "active_nav": "vinted",
    })


@login_required
@require_POST
def stock_add(request):
    """Crée un article d'entrepôt (formulaire du haut de page)."""
    nom = (request.POST.get("nom") or "").strip()
    if not nom:
        return redirect("vinted:entrepot")
    qte = request.POST.get("quantite") or "1"
    prix = (request.POST.get("prix_achat") or "").strip()
    try:
        pa = Decimal(prix) if prix else None
    except InvalidOperation:
        pa = None
    fid = (request.POST.get("fournisseur") or "").strip()
    StockItem.objects.create(
        nom=nom, prix_achat=pa, quantite=int(qte) if qte.isdigit() else 1,
        source=request.POST.get("source") or "autre",
        destin=request.POST.get("destin") or "a_definir",
        statut=request.POST.get("statut") or "en_transit",
        fournisseur_id=int(fid) if fid.isdigit() else None,
        reference=(request.POST.get("reference") or "").strip())
    return redirect("vinted:entrepot")


@login_required
@require_POST
def stock_update(request, pk):
    """Édition inline d'un champ d'un article d'entrepôt."""
    item = get_object_or_404(StockItem, pk=pk)
    field = (request.POST.get("field") or "").strip()
    val = (request.POST.get("value", "") or "").strip()
    try:
        if field in _STK_TEXT:
            setattr(item, field, val)
        elif field in _STK_DECIMAL:
            setattr(item, field, Decimal(val) if val else None)
        elif field in _STK_INT:
            setattr(item, field, int(val) if val else 1)
        elif field in _STK_DATE:
            from datetime import date
            setattr(item, field, date.fromisoformat(val) if val else None)
        elif field in _STK_CHOICE:
            if val not in _STK_CHOICE[field]:
                return JsonResponse({"ok": False, "error": "valeur invalide"}, status=400)
            setattr(item, field, val)
        elif field == "fournisseur":
            if val == "":
                item.fournisseur = None
            elif val.isdigit() and Fournisseur.objects.filter(pk=int(val)).exists():
                item.fournisseur_id = int(val)
            else:
                return JsonResponse({"ok": False, "error": "fournisseur inconnu"}, status=400)
        else:
            return JsonResponse({"ok": False, "error": "champ non éditable"}, status=400)
    except (InvalidOperation, ValueError):
        return JsonResponse({"ok": False, "error": "format invalide"}, status=400)
    item.save()
    return JsonResponse({"ok": True, "cout_total": f"{item.cout_total:.2f}"})


# ── Duesenberg — Telegram Mini-App ──────────────────────────────────────────

def duesenberg(request):
    """Telegram Mini-App : dashboard KPI SpaceLabs (lecture publique, no login)."""
    return render(request, "vinted/duesenberg.html")


def duesenberg_api(request):
    """API JSON pour la mini-app Duesenberg."""
    orders = list(
        VintedOrder.objects
        .prefetch_related("lignes__stock_item")
        .order_by("-date_vente", "-id")
    )

    ca = Decimal("0")
    cout = Decimal("0")
    benef = Decimal("0")
    for o in orders:
        ca += o.prix_vente or Decimal("0")
        cout += o.prix_achat or Decimal("0")
        benef += o.benefice

    marge = round(float(benef) / float(cout) * 100, 1) if cout else None
    a_preparer = [o for o in orders if o.statut_envoi in STATUTS_ENVOI_A_FAIRE]
    en_transit_envoi = [o for o in orders if o.statut_envoi == "expedie"]

    stock_entrepot = StockItem.objects.filter(
        statut__in=["en_transit", "recu", "a_grader", "en_gradation", "grade", "a_lister", "liste"]
    ).count()

    statut_labels = dict(STATUTS_ENVOI)
    plat_labels = dict(PLATEFORMES)

    def ligne_repr(l):
        pv = float(l.prix_vente_unitaire) if l.prix_vente_unitaire else None
        pa = float(l.prix_achat_unitaire) if l.prix_achat_unitaire else None
        benef_l = float(l.benefice_ligne) if l.prix_achat_unitaire else None
        photo = (l.stock_item.photo if l.stock_item and l.stock_item.photo else "")
        return {
            "designation": l.designation or "—",
            "prix_vente": round(pv, 2) if pv is not None else None,
            "prix_achat": round(pa, 2) if pa is not None else None,
            "benefice": round(benef_l, 2) if benef_l is not None else None,
            "quantite": l.quantite,
            "photo": photo,
        }

    def order_repr(o):
        lignes = list(o.lignes.all())
        return {
            "id": o.pk,
            "titre": o.titre or f"#{o.pk}",
            "plateforme": plat_labels.get(o.plateforme, o.plateforme),
            "prix_vente": str(o.prix_vente or ""),
            "prix_achat": str(o.prix_achat or ""),
            "remise": str(o.remise) if o.remise else "",
            "benefice": str(o.benefice),
            "statut": o.statut_envoi,
            "statut_label": statut_labels.get(o.statut_envoi, o.statut_envoi),
            "date": str(o.date_vente) if o.date_vente else "",
            "lignes": [ligne_repr(l) for l in lignes],
        }

    return JsonResponse({
        "kpis": {
            "ca": str(ca),
            "benefice": str(benef),
            "cout": str(cout),
            "marge": marge,
            "nb_commandes": len(orders),
            "stock_entrepot": stock_entrepot,
            "a_preparer": len(a_preparer),
            "en_transit": len(en_transit_envoi),
        },
        "a_preparer": [order_repr(o) for o in a_preparer[:5]],
        "recentes": [order_repr(o) for o in orders[:10]],
    })
