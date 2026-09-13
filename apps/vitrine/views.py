import json

from django.shortcuts import render
from django.views.decorators.cache import cache_page

from .catalogue import PRODUITS

_PRODUITS_JSON = json.dumps([
    {"slug": p["slug"], "nom": p["nom"], "tagline": p["tagline"],
     "categorie": p["categorie"], "couleur": p["couleur"], "url": p.get("url", "")}
    for p in PRODUITS
])


@cache_page(60)
def landing(request):
    return render(request, "landing.html", {
        "produits_json": _PRODUITS_JSON,
        "produits_count": len(PRODUITS),
    })


@cache_page(60)
def vitrine(request):
    return render(request, "vitrine/vitrine.html", {"produits": PRODUITS})


@cache_page(60)
def vitrine_v2(request):
    produits_json = json.dumps([
        {"slug": p["slug"], "nom": p["nom"], "tagline": p["tagline"],
         "categorie": p["categorie"], "couleur": p["couleur"], "url": p.get("url", "")}
        for p in PRODUITS
    ])
    return render(request, "vitrine/vitrine_v2.html", {
        "produits": PRODUITS,
        "produits_json": produits_json,
    })
