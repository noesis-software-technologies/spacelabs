"""Taxonomie & plume du blog Yonkko (One Piece TCG, yonko.life).

Même structure qu'Atmosphère : un bloc « Yonkko » = blog principal + sous-blogs
par sous-catégorie. Rédaction : nouvelle journalistique vulgarisée pour
collectionneurs de One Piece Card Game.
"""

BLOC = "Yonkko"

# slug → (label, mots-clés de catégorisation, requête Pexels, angle éditorial)
SUBCATS = {
    "op-sorties": (
        "Sorties & précommandes",
        ["release", "sortie", "précommande", "preorder", "op-", "prb", "eb-",
         "new set", "extension", "display", "booster", "starter", "coffret"],
        "trading card game booster",
        "Annonce de sortie : dates, contenu du set, précommandes — ce que le collectionneur doit anticiper.",
    ),
    "op-meta": (
        "Méta & decklists",
        ["deck", "decklist", "meta", "méta", "tier", "leader", "matchup", "combo", "archetype"],
        "card game night table",
        "Décryptage méta : quels leaders/decks dominent, forces et faiblesses, expliqué simplement.",
    ),
    "op-marche": (
        "Cotes & marché",
        ["price", "prix", "cote", "value", "invest", "market", "marché", "scalp",
         "sold", "enchère", "auction", "expensive", "chase"],
        "collectible trading cards",
        "Marché & cotes : quelles cartes montent et pourquoi, repères de collection (pas de conseil financier).",
    ),
    "op-tournois": (
        "Tournois & compétitif",
        ["tournament", "tournoi", "championship", "regional", "top 8", "winner",
         "champion", "locals", "bandai", "worlds", "compet"],
        "card game tournament",
        "Compétitif : résultats, tops, tendances de tournoi, rendus accessibles.",
    ),
    "op-collection": (
        "Collection & artworks",
        ["alt art", "alternate art", "artwork", "illustration", "parallel",
         "special", "grading", "psa", "manga", "collector"],
        "anime collectible cards",
        "Collection : artworks, alt-arts, grading, pièces iconiques à connaître.",
    ),
    "op-actu": (
        "Actualité & lore",
        [],  # catégorie par défaut
        "manga anime store",
        "Actualité One Piece Card Game vulgarisée pour collectionneurs : contexte, enjeux, à retenir.",
    ),
}
DEFAULT = "op-actu"


def categorize(titre: str, corps: str) -> str:
    blob = f"{titre} {corps}".lower()
    best, best_hits = DEFAULT, 0
    for slug, (_lbl, kws, _q, _a) in SUBCATS.items():
        hits = sum(1 for k in kws if k in blob)
        if hits > best_hits:
            best, best_hits = slug, hits
    return best


def angle(slug: str) -> str:
    return SUBCATS.get(slug, SUBCATS[DEFAULT])[3]


def pexels_query(slug: str) -> str:
    return SUBCATS.get(slug, SUBCATS[DEFAULT])[2]


def build_prompt(sujet: str, corps: str, categorie: str) -> str:
    a = angle(categorie)
    matiere = (corps or "").strip()[:5000] or "(sujet sans corps ; s'appuyer sur le titre)"
    return f"""Tu es journaliste spécialisé du blog Yonkko, dédié au One Piece Card Game.
Écris une BRÈVE JOURNALISTIQUE VULGARISÉE pour des collectionneurs (débutants à confirmés),
à partir de la matière ci-dessous, dans une voix claire, vivante et fiable.

=== ANGLE ({categorie}) ===
{a}

=== MATIÈRE (à réécrire à 100 %, ne rien recopier, n'invente aucun prix/date/citation) ===
Sujet : {sujet}
Contenu :
{matiere}

=== CONSIGNE DE SORTIE ===
Rends UNIQUEMENT un objet JSON valide (sans texte autour, sans balises) :
{{"titre": "...", "chapo": "...", "corps": "...", "seo_title": "...",
  "meta_description": "...", "tags": ["...", "..."], "image_alt": "..."}}
- "titre" : accrocheur, clair (pas de clickbait mensonger, pas « Communiqué »).
- "chapo" : 2-3 phrases qui posent le sujet et pourquoi ça intéresse un collectionneur.
- "corps" : 300 à 550 mots, paragraphes courts, vulgarisé (explique le jargon TCG :
  leader, alt-art, méta, MOQ, grading…), rubriques en CAPITALES si utile, ton journalistique
  neutre et enthousiaste, AUCUNE donnée inventée. Pas de conseil financier.
- "seo_title" : ~60 caractères. "meta_description" : ~150 caractères, incitatif.
- "tags" : 4-6 mots-clés minuscules (inclure "one piece", "tcg" quand pertinent).
- "image_alt" : description courte de l'image principale.
"""
