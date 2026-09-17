"""Catégorisation heuristique des communiqués de presse (mots-clés sujet + corps).

9 catégories principales (= sous-marques de la constellation 13 Atmosphère).
"""

KEYWORDS = {
    "hotellerie": ["hotel", "hôtel", "palace", "resort", "four seasons", "crillon",
                   "monte-carlo", "croisi", "hospitality", "best hotels", "voyage",
                   "itinér", "astir", "milano", "delphina", "séjour", "sejour"],
    "beaute": ["beauté", "beaute", "bien-être", "bien être", "wellness", "spa",
               "cosmétique", "cosmetique", "soin", "athletics", "santé mentale",
               "sante mentale", "parfum", "maquillage"],
    "food": ["mocktail", "sans alcool", "aikan", "gastronom", "cuisine", "restaurant",
             "food", "boisson", "blender", "robot multifonction", "nomo", "collinet",
             "amarines", "bar ", "chef", "vin", "café", "cafe", "botran", "jpo fort et clair"],
    "habitat": ["batimat", "architect", "btp", "construction", "urbanisme", "immobilier",
                "habitat", "ville", "dalle", "défense", "quartier", "logement", "cosentino",
                "dekton", "villeroy", "boch", "ideal standard", "carrelage"],
    "culture": ["expo", "exposition", "galerie", "rankin", "chambord", "patrimoine",
                "musée", "musee", "festin", "fresque", "moretti", "ombromane",
                "philippe beau", "art)", "vernissage", "collection permanente"],
    "events": ["salon", "rendez-vous", "rdv", "foire", "journées du patrimoine",
               "journees du patrimoine", "invitation presse", "visite presse",
               "visite de presse", "jpo", "inscription", "last call", "vente usine",
               "mondial de l", "gally", "invitation /"],
    "design": ["design", "mobilier", "canapé", "canape", "dining table", "table",
               "fermob", "tolix", "jieldé", "jielde", "luminaire", "gautier", "dolce",
               "décor", "decor", "vaisselle", "textile", "aiper", "artik nodes"],
    "mode": ["mode", "fashion", "collina", "layered", "vestiaire", "madame rêve",
             "madame reve", "tom meyer", "style", "prêt-à-porter", "pret-a-porter",
             "sneaker", "accessoire", "télescope", "telescope", "unistellar", "noël", "noel"],
    "societe": ["étude", "etude", "% des français", "% des francais", "sondage", "pape",
                "geneanet", "enseigne", "fraude", "mario kart", "tendance", "français prêts",
                "francais prets", "insolite"],
}

# Ordre de priorité (catégorie la plus spécifique d'abord)
ORDER = ["hotellerie", "beaute", "food", "habitat", "culture",
         "events", "design", "mode", "societe"]


def categorize(subject: str, body: str = "") -> str:
    text = f"{subject} {body}".lower()
    for cat in ORDER:
        for kw in KEYWORDS[cat]:
            if kw in text:
                return cat
    return "autre"
