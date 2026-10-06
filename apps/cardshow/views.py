from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_POST

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
