import json
from pathlib import Path

from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.cache import cache_page

from .catalogue import PRODUITS
from .savoir_faire_data import DOMAINES, METRIQUES, STACK

_PRIVATE_PATH = Path(__file__).parents[2] / "SAVOIR_FAIRE_PRIVATE.json"

_PRODUITS_JSON = json.dumps([
    {"slug": p["slug"], "nom": p["nom"], "tagline": p["tagline"],
     "categorie": p["categorie"], "couleur": p["couleur"], "url": p.get("url", ""),
     "shot": static(f"vitrine/desktop/{p['slug']}.jpg"),
     "shot_mobile": static(f"vitrine/screenshots/{p['slug']}.jpg")}
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


def _clean_private(data):
    """Strip _note placeholders so Django template can iterate cleanly."""
    if isinstance(data, dict):
        return {k: _clean_private(v) for k, v in data.items() if not k.startswith("_")}
    if isinstance(data, list):
        cleaned = [_clean_private(i) for i in data if not (isinstance(i, dict) and set(i) == {"_note"})]
        return cleaned
    return data


def savoir_faire(request):
    private = {}
    if _PRIVATE_PATH.exists():
        try:
            raw = json.loads(_PRIVATE_PATH.read_text())
            private = _clean_private(raw)
        except Exception:
            pass
    cats = sorted({p["categorie"] for p in PRODUITS})
    stack_by_cat = {}
    for s in STACK:
        stack_by_cat.setdefault(s["cat"], []).append(s)
    return render(request, "vitrine/savoir_faire.html", {
        "stack": STACK,
        "stack_by_cat": stack_by_cat,
        "domaines": DOMAINES,
        "metriques": METRIQUES,
        "produits": PRODUITS,
        "produits_count": len(PRODUITS),
        "categories": cats,
        "private": private,
        "has_private": bool(private),
        "produits_json": json.dumps([
            {"slug": p["slug"], "nom": p["nom"], "tagline": p["tagline"],
             "categorie": p["categorie"], "couleur": p["couleur"], "url": p.get("url", "")}
            for p in PRODUITS
        ]),
    })


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
