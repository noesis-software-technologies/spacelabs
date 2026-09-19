"""Scoring 0-100 et classification fit (cahier des charges NOESIS).

Barème : fit 40 · concurrence 25 · budget 20 · fraîcheur 10 · brief 5.
Deux règles priment : budget < 500 € ne déclenche jamais d'offre ; fit=0 bloque.
"""
import re

# Fit technique — mots-clés Go / No-go.
GO = ["développement spécifique", "sur mesure", "sur-mesure", "saas", "application métier",
      "logiciel", "plateforme", "api", "back-end", "backend", "python", "django",
      "base de données", "automatisation", "ia ", "intelligence artificielle", "machine learning",
      "erp", "crm", "refonte", "reprise", "web app", "application web", "mobile", "fullstack",
      "full-stack", "microservice", "data", "scraping", "intégration", "webapp"]
NO_GO = ["wordpress", "prestashop", "shopify", "wix", "logo", "charte graphique", "flyer",
         "traduction", "rédaction", "redaction", "community management", "réseaux sociaux",
         "prospection commerciale", "saisie de données", "community manager", "seo ",
         "montage vidéo", "graphiste", "webdesign simple"]


def fit_score(titre: str, description: str, categorie: str, competences=None) -> int:
    """40 = cœur de métier · 20 = adjacent · 0 = no-go."""
    blob = " ".join([titre or "", description or "", categorie or "",
                     " ".join(competences or [])]).lower()
    if any(k in blob for k in NO_GO) and not any(k in blob for k in GO):
        return 0
    hits = sum(1 for k in GO if k in blob)
    if hits >= 2:
        return 40
    if hits == 1:
        return 20
    return 0


def _concurrence_score(offres) -> int:
    if offres is None:
        return 15  # inconnu → hypothèse médiane prudente
    if offres < 5:
        return 25
    if offres <= 15:
        return 15
    if offres <= 40:
        return 5
    return 0


def _budget_score(eur: int) -> int:
    if eur >= 10000:
        return 20
    if eur >= 1000:
        return 15
    if eur >= 500:
        return 5
    return 0


def _fraicheur_score(age_h) -> int:
    if age_h is None:
        return 5
    if age_h < 2:
        return 10
    if age_h <= 24:
        return 5
    return 0


def _brief_score(description: str) -> int:
    return 5 if len((description or "").strip()) >= 400 else 0


def compute_score(op) -> int:
    """Score global 0-100 avec les deux règles bloquantes du cahier des charges."""
    fit = fit_score(op.titre, op.description, op.categorie, op.competences)
    if fit == 0:                       # règle : fit=0 bloque
        return 0
    if op.budget_eur and op.budget_eur < 500:  # règle : < 500 € jamais d'offre
        return 0
    age_h = None
    if op.delai_detection_h is not None:
        age_h = op.delai_detection_h
    total = (fit + _concurrence_score(op.offres_detection) + _budget_score(op.budget_eur)
             + _fraicheur_score(age_h) + _brief_score(op.description))
    return min(100, total)


def suggest_rejet(op):
    """Motif de rejet suggéré si l'annonce ne passe pas les portes (ou None)."""
    if op.etat in ("termine", "ferme"):
        return "etat"
    if op.age_jours is not None and op.age_jours > 7:
        return "remontee"
    if fit_score(op.titre, op.description, op.categorie, op.competences) == 0:
        return "hors_fit"
    if op.budget_eur and op.budget_eur < 500:
        return "budget"
    if op.offres_detection is not None and op.offres_detection > 40 and op.budget_eur < 10000:
        return "trop_offres"
    return None
