from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (STATUTS_ENVOI, STATUTS_ENVOI_A_FAIRE, TRANSPORTEURS,
                     VintedOrder)


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
    orders = list(VintedOrder.objects.select_related("listing").all())

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
        "transporteurs": TRANSPORTEURS,
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
