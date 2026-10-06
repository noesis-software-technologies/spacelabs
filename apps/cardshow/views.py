import json
import tempfile
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.vinted.models import STOCK_DESTINS, Fournisseur, StockItem

from .detect import cardmarket_search, detect_from_image
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


@login_required
@require_POST
def detect(request):
    """Détecte une carte depuis une image uploadée + récupère prix CardMarket.

    POST multipart avec `image` (fichier).
    Retourne JSON : {nom, numero, serie, langue, rarete, prix_estime_eur,
                     cardmarket: {tendance, bas, moyen, haut, url}, erreur?}
    """
    img_file = request.FILES.get("image")
    if not img_file:
        return JsonResponse({"erreur": "Aucune image reçue"}, status=400)

    from django.conf import settings
    tmp_dir = Path(settings.MEDIA_ROOT) / "stock" / "detect_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(img_file.name).suffix or ".jpg"
    tmp_path = tmp_dir / f"detect_{img_file.name}"
    with open(tmp_path, "wb") as f:
        for chunk in img_file.chunks():
            f.write(chunk)

    card = detect_from_image(tmp_path)

    cm_data = {}
    if "erreur" not in card:
        # Construire une query CardMarket depuis les infos détectées
        query_parts = [card.get("nom_fr") or card.get("nom", ""), card.get("serie", "")]
        query = " ".join(p for p in query_parts if p).strip()
        if query:
            cm_data = cardmarket_search(query)

    try:
        tmp_path.unlink(missing_ok=True)
    except Exception:
        pass

    return JsonResponse({
        **card,
        "cardmarket": cm_data,
    })
