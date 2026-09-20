"""Fallback images libres de droit via l'API Pexels.

Pour les articles sans visuel : on construit une requête à partir du contexte de
l'article (tags → titre → catégorie) pour rester cohérent, et on récupère des
photos Pexels (licence libre). La requête garantit la cohérence image↔article.
"""
import requests
from django.conf import settings

# Termes de recherche par défaut par catégorie (si l'article n'a pas de tags).
CAT_QUERY = {
    "hotellerie": "hôtel élégant voyage",
    "design": "design objet atelier",
    "mode": "mode défilé silhouette",
    "food": "gastronomie table restaurant",
    "culture": "art exposition musée",
    "habitat": "architecture intérieur maison",
    "beaute": "beauté soin cosmétique",
    "societe": "société ville tendance",
    "events": "événement salon exposition",
    "autre": "élégance lifestyle",
    # Yonkko — One Piece TCG
    "onepiece-tcg": "anime trading cards collection",
    "op-sorties": "trading card booster box collection",
    "op-meta": "card game strategy table",
    "op-marche": "rare collectible trading cards",
    "op-tournois": "card game tournament players competition",
    "op-collection": "anime art collectible cards",
    "op-actu": "one piece anime manga",
}


def build_query(item) -> str:
    if item.tags:
        return " ".join(item.tags[:3])
    base = (item.seo_title or item.draft_titre or item.sujet or "").strip()
    if base:
        # garde les 6 premiers mots significatifs
        return " ".join(base.split()[:6])
    return CAT_QUERY.get(item.categorie, CAT_QUERY["autre"])


def search(query: str, per_page: int = 3, orientation: str = "landscape") -> list[dict]:
    key = getattr(settings, "PEXELS_API_KEY", "")
    if not key:
        return []
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": key},
            params={"query": query, "per_page": per_page, "orientation": orientation},
            timeout=20,
        )
        r.raise_for_status()
    except requests.RequestException:
        return []
    out = []
    for p in r.json().get("photos", []):
        src = p.get("src") or {}
        url = src.get("large2x") or src.get("large") or src.get("original")
        if url:
            out.append({
                "url": url,
                "alt": (p.get("alt") or "").strip(),
                "credit": f"Photo : {p.get('photographer', 'Pexels')} / Pexels",
                "credit_url": p.get("url", ""),
            })
    return out
