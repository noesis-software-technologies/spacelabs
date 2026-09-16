"""Catégorisation heuristique des communiqués de presse (mots-clés du sujet)."""

KEYWORDS = {
    "hotellerie": ["hotel", "hôtel", "palace", "resort", "four seasons", "crillon",
                   "monte-carlo", "croisi", "hospitality", "best hotels", "voyage",
                   "itinér", "astir", "milano"],
    "design": ["design", "mobilier", "canapé", "canape", "dining table", "table",
               "fermob", "tolix", "jieldé", "jielde", "luminaire", "gautier", "dolce",
               "décor", "decor"],
    "food": ["mocktail", "sans alcool", "aikan", "gastronom", "cuisine", "restaurant",
             "food", "boisson", "blender", "robot multifonction"],
    "mode": ["mode", "fashion", "collina", "layered", "wellness", "athletics",
             "lifestyle", "télescope", "telescope", "unistellar", "cadeau", "noel", "noël"],
    "culture": ["expo", "exposition", "galerie", "rankin", "chambord", "patrimoine",
                "musée", "musee", "festin", "art de vivre", "art)"],
    "archi": ["batimat", "architect", "btp", "construction", "urbanisme"],
    "salons": ["salon", "rendez-vous", "rdv", "foire", "journées du patrimoine",
               "journees du patrimoine"],
    "societe": ["étude", "etude", "% des français", "% des francais", "santé mentale",
                "sante mentale", "sondage", "pape", "geneanet", "enseigne", "français prêts",
                "francais prets"],
}

# Ordre de priorité (le plus spécifique d'abord)
ORDER = ["hotellerie", "food", "design", "culture", "archi", "salons", "mode", "societe"]


def categorize(subject: str, body: str = "") -> str:
    text = f"{subject} {body}".lower()
    for cat in ORDER:
        for kw in KEYWORDS[cat]:
            if kw in text:
                return cat
    return "autre"
