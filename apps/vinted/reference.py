"""Sélection de la photo « la plus lisible » comme image de référence.

Heuristique 100 % locale (Pillow) : netteté (variance des contours via
FIND_EDGES) pondérée par la résolution. La plus nette/définie l'emporte —
c'est en général celle qui porte l'étiquette / le texte lisible du produit.
"""
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat


def _score(path: str) -> float:
    try:
        im = Image.open(path).convert("L")
    except Exception:  # noqa: BLE001
        return -1.0
    w, h = im.size
    # normalise pour un calcul de netteté comparable, garde le facteur résolution
    small = im.copy()
    small.thumbnail((800, 800))
    edges = small.filter(ImageFilter.FIND_EDGES)
    sharp = ImageStat.Stat(edges).var[0]           # variance des contours
    res = min(w * h, 4_000_000) / 4_000_000        # bonus résolution (plafonné)
    return sharp * (0.6 + 0.4 * res)


def pick_reference(paths: list[str]) -> str:
    """Retourne le chemin de la photo la plus lisible (ou '' si aucune)."""
    best, best_score = "", -1.0
    for p in paths:
        if not Path(p).exists():
            continue
        s = _score(p)
        if s > best_score:
            best_score, best = s, p
    return best
