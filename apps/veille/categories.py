"""Correspondance catégories veille → slugs de la taxonomie du blog 13 Atmosphère.

Par défaut : une table raisonnable (déco/lifestyle/voyage…) — surchargeable via
le réglage `VEILLE_CATEGORY_MAP` (dict JSON dans l'environnement) une fois les
slugs réels du blog connus, sans toucher au code.
"""
from django.conf import settings

# Nos slugs (apps.veille.models.CATEGORIES) → slug(s) blog.
DEFAULT_MAP = {
    "hotellerie": "voyage",
    "design": "deco",
    "mode": "mode",
    "food": "gastronomie",
    "culture": "culture",
    "habitat": "maison",
    "beaute": "beaute",
    "societe": "lifestyle",
    "events": "lifestyle",
    "autre": "lifestyle",
    # Yonkko (yonko.life) — One Piece TCG : nos slugs veille → rubriques du blog.
    "onepiece": "actualite",
    "op-actu": "actualite",
    "op-sorties": "sorties",
    "op-meta": "meta",
    "op-marche": "cotes",
    "op-tournois": "tournois",
    "op-collection": "collection",
    "onepiece-tcg": "actualite",
}


def blog_slugs(categorie: str) -> list[str]:
    """Renvoie la liste de slugs blog pour une catégorie veille (jamais vide)."""
    mapping = {**DEFAULT_MAP, **(getattr(settings, "VEILLE_CATEGORY_MAP", {}) or {})}
    slug = mapping.get(categorie) or mapping.get("autre") or "lifestyle"
    return [slug] if isinstance(slug, str) else list(slug)
