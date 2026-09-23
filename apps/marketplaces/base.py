"""Socle commun aux clients de places de marché.

Aucun secret en dur : les clés vivent en variables d'environnement (`.env.local`,
gitignoré) et sont exposées via les settings (préfixes `EBAY_` / `MKM_`)."""
from django.conf import settings


class MarketplaceConfigError(RuntimeError):
    """Clés API manquantes / configuration incomplète pour la plateforme."""


class MarketplaceAPIError(RuntimeError):
    """Réponse d'erreur renvoyée par l'API de la plateforme."""


def require(*names):
    """Vérifie que les settings nommés sont non vides, sinon lève une erreur
    explicite listant ce qu'il manque (à mettre dans `.env.local`)."""
    missing = [n for n in names if not getattr(settings, n, "")]
    if missing:
        raise MarketplaceConfigError(
            "Clés manquantes dans .env.local : " + ", ".join(missing))
