"""Détection de carte Pokémon depuis une image + estimation prix CardMarket.

Workflow :
  1. Image → subprocess `claude --print` (vision dans le projet) → JSON carte
  2. CardMarket → scrape tendance publique → prix de marché
"""
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

_CLAUDE_BIN = "claude"
_CM_BASE = "https://www.cardmarket.com"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}

_DETECT_PROMPT = """Read the image at {path} and identify the Pokémon trading card.
Return ONLY valid JSON (no markdown, no explanation):
{{
  "nom": "card name in original language",
  "nom_fr": "French name if known, else empty string",
  "numero": "card number e.g. 017/101",
  "serie": "set name in original language",
  "serie_cm": "CardMarket set name slug if known, else empty string",
  "langue": "japonais|francais|anglais|autre",
  "rarete": "Commune|Peu commune|Rare|Holo Rare|Ultra Rare|SAR|Secret Rare|etc",
  "etat_estime": "Mint|Near Mint|Excellent|Good|Poor",
  "prix_estime_eur": estimated_market_value_as_number,
  "confiance": "haute|moyenne|basse"
}}"""


def detect_from_image(image_path: str | Path) -> dict:
    """Identifie la carte dans image_path via Claude CLI (vision).

    image_path doit être relatif au répertoire SpaceLabs ou absolu dans /home/noesis/spacelabs/.
    Retourne un dict avec les champs du prompt, ou {"erreur": "..."} en cas d'échec.
    """
    from django.conf import settings

    img = Path(image_path)
    project_root = Path(settings.BASE_DIR)

    # Si chemin absolu dans le projet → convertir en relatif pour le prompt
    try:
        rel = img.relative_to(project_root)
    except ValueError:
        # Copier dans un tmp dans le projet
        tmp_dir = project_root / "media" / "stock" / "detect_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / img.name
        import shutil
        shutil.copy2(img, tmp_path)
        rel = tmp_path.relative_to(project_root)

    prompt = _DETECT_PROMPT.format(path=str(rel))
    try:
        result = subprocess.run(
            [_CLAUDE_BIN, "--print"],
            input=prompt,
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=45,
        )
        raw = result.stdout.strip()
    except subprocess.TimeoutExpired:
        return {"erreur": "Détection timeout (>45s)"}
    except Exception as e:
        return {"erreur": f"Subprocess error: {e}"}

    # Extraire JSON de la réponse (peut être entouré de backticks)
    json_match = re.search(r"\{[\s\S]+\}", raw)
    if not json_match:
        return {"erreur": f"Pas de JSON dans la réponse: {raw[:200]}"}
    try:
        return json.loads(json_match.group())
    except json.JSONDecodeError as e:
        return {"erreur": f"JSON invalide: {e}"}


def cardmarket_prix(serie_slug: str, nom_slug: str, langue: str = "") -> dict:
    """Scrape CardMarket pour la tendance de prix d'une carte Pokémon.

    serie_slug : nom du set tel qu'il apparaît dans l'URL CardMarket
                 (ex. "Surging-Sparks", "151", "Celebrations")
    nom_slug   : nom de la carte dans l'URL (ex. "Pikachu-EX")
    Retourne {tendance, bas, moyen, haut, nb_annonces, url} ou {"erreur": "..."}
    """
    # Essaie les URLs japonaises si langue == japonais
    candidates = [
        f"{_CM_BASE}/fr/Pokemon/Products/Singles/{serie_slug}/{nom_slug}",
    ]
    if langue == "japonais":
        candidates.insert(
            0,
            f"{_CM_BASE}/fr/Pokemon/Products/Singles/Japanese-{serie_slug}/{nom_slug}",
        )

    for url in candidates:
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            data = _parse_cm_page(soup, url)
            if data:
                return data
        except Exception:
            continue

    return {"erreur": "Carte introuvable sur CardMarket"}


def cardmarket_search(query: str) -> dict:
    """Recherche une carte par texte libre sur CardMarket et retourne le 1er résultat."""
    search_url = f"{_CM_BASE}/fr/Pokemon/Products/Search?searchString={requests.utils.quote(query)}"
    try:
        resp = requests.get(search_url, headers=_HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "lxml")
        # Premier lien produit dans les résultats
        link = soup.select_one("a.card-link, .table-body a[href*='/Singles/']")
        if not link:
            return {"erreur": "Aucun résultat CardMarket"}
        product_url = _CM_BASE + link["href"] if link["href"].startswith("/") else link["href"]
        resp2 = requests.get(product_url, headers=_HEADERS, timeout=10)
        soup2 = BeautifulSoup(resp2.text, "lxml")
        data = _parse_cm_page(soup2, product_url)
        return data or {"erreur": "Page CardMarket parsée mais prix introuvable"}
    except Exception as e:
        return {"erreur": f"Erreur CardMarket search: {e}"}


def _parse_cm_page(soup: BeautifulSoup, url: str) -> dict | None:
    """Extrait tendance et fourchette depuis une page produit CardMarket."""
    def _price(text: str) -> float | None:
        m = re.search(r"[\d,\.]+", text.replace("\xa0", "").replace(" ", ""))
        if m:
            try:
                return float(m.group().replace(",", "."))
            except ValueError:
                pass
        return None

    # Tendance — cherche la div/span avec le texte "Tendance" ou "Price Trend"
    tendance = None
    for el in soup.select("[class*='price'], [class*='trend'], dt, .info-list-item"):
        txt = el.get_text(" ", strip=True)
        if re.search(r"tendance|trend", txt, re.I):
            # Valeur suivante dans la liste
            sibling = el.find_next_sibling()
            if sibling:
                tendance = _price(sibling.get_text())
            if tendance is None:
                tendance = _price(txt)
            if tendance:
                break

    # Fourchette low / avg / high depuis les articles disponibles
    prices = []
    for el in soup.select(".price-container .color-primary, .table-body .col-price"):
        p = _price(el.get_text())
        if p and p > 0:
            prices.append(p)

    if not tendance and not prices:
        return None

    return {
        "tendance": tendance,
        "bas": min(prices) if prices else None,
        "moyen": round(sum(prices) / len(prices), 2) if prices else None,
        "haut": max(prices) if prices else None,
        "nb_annonces": len(prices),
        "url": url,
    }
