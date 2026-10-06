from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.vinted.models import STOCK_DESTINS, Fournisseur, StockItem

from .services import calculer_tiers, parse_decimal


@login_required
def calcul(request):
    return render(request, "cardshow/calcul.html")


@login_required
@require_POST
def apercu(request):
    pa_raw = request.POST.get("pa", "").strip()
    frais_raw = request.POST.get("frais", "0").strip()

    pa = parse_decimal(pa_raw)
    frais = parse_decimal(frais_raw) if frais_raw else Decimal("0")

    erreur_saisie = None
    tiers = []

    if pa_raw and pa is None:
        erreur_saisie = "PA invalide — saisissez un nombre positif (ex. 12.50)"
    elif frais_raw and frais is None:
        erreur_saisie = "Frais invalides — saisissez un nombre positif (ex. 1.80)"
    elif pa is not None:
        tiers = calculer_tiers(pa, frais or Decimal("0"))

    return render(request, "cardshow/partials/_tiers.html", {
        "tiers": tiers,
        "erreur_saisie": erreur_saisie,
        "pa": pa,
        "frais": frais,
        "cout": (pa + (frais or Decimal("0"))) if pa is not None else None,
    })


@login_required
def intake(request):
    """Intake rapide card show — formulaire mobile avec caméra recto/verso."""
    if request.method == "POST":
        nom = (request.POST.get("nom") or "").strip()
        if not nom:
            return render(request, "cardshow/intake.html", {
                "erreur": "Le nom de la carte est obligatoire.",
                "destins": STOCK_DESTINS,
            })
        from .services import parse_decimal as _pd
        item = StockItem(
            nom=nom,
            reference=(request.POST.get("reference") or "").strip(),
            prix_achat=_pd(request.POST.get("prix_achat", "")) ,
            prix_affiche=_pd(request.POST.get("prix_affiche", "")),
            prix_repli_1=_pd(request.POST.get("prix_repli_1", "")),
            prix_repli_2=_pd(request.POST.get("prix_repli_2", "")),
            destin=request.POST.get("destin") or "vente_directe",
            statut="recu",
        )
        item.save()
        if "image_recto" in request.FILES:
            item.image_recto = request.FILES["image_recto"]
        if "image_verso" in request.FILES:
            item.image_verso = request.FILES["image_verso"]
        item.save()
        if request.POST.get("action") == "etiquette":
            return redirect(f"/vinted/entrepot/{item.pk}/etiquette/")
        if request.POST.get("action") == "continuer":
            return render(request, "cardshow/intake.html", {
                "succes": f"« {item.nom } » ajouté (#{item.pk}). Carte suivante :",
                "dernier_pk": item.pk,
                "destins": STOCK_DESTINS,
            })
        return redirect(f"/vinted/entrepot/{item.pk}/etiquette/")

    return render(request, "cardshow/intake.html", {"destins": STOCK_DESTINS})
