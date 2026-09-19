"""Agentic sales team — assistance IA locale (llama.cpp :8081) pour la vente.

- `draft_offer(op)`    : rédige une offre sur mesure à partir du brief, en suivant
  le modèle imposé par le score (≥70 vs 45-69 vs demande de devis), au nom de
  NOESIS SOFTWARE TECHNOLOGIES. Respecte les interdits du cahier des charges.
- `suggest_next(op)`   : propose la prochaine étape commerciale.
- `default_steps(op)`  : étapes SLA par défaut selon le statut (offre <2h, relance
  J+3, sans réponse J+10) — la matière de l'équipe agentique.

100 % local, sans coût API. Le résultat est un BROUILLON validé par un humain
avant envoi (contact via la messagerie de la plateforme).
"""
import datetime as _dt
import os

import requests

LLM_BASE = os.environ.get("LOCAL_LLM_BASE", "http://127.0.0.1:8081").rstrip("/")
LLM_MODEL = os.environ.get("LOCAL_LLM_MODEL", "qwen2.5-3b-local")

SYS = (
    "Tu es un ingénieur commercial de NOESIS SOFTWARE TECHNOLOGIES (dev sur mesure, "
    "Python/Django, SaaS, API, IA appliquée). Tu réponds à des appels d'offres. "
    "Règles STRICTES : message court (3-5 phrases), 1re phrase qui prouve qu'on a lu le "
    "brief, 2e qui prouve la compétence, UNE seule question, une fourchette ou une "
    "question de chiffrage (jamais un prix ferme sans brief complet). INTERDIT : "
    "« nous sommes une agence spécialisée », listes de technos, liens portfolio, "
    "mention d'outils d'assistance. Signe « [Prénom Nom] — NOESIS SOFTWARE TECHNOLOGIES ». "
    "Écris en français."
)


def _chat(prompt, max_tokens=400, timeout=60):
    r = requests.post(
        f"{LLM_BASE}/v1/chat/completions", timeout=timeout,
        json={"model": LLM_MODEL, "temperature": 0.4, "max_tokens": max_tokens,
              "messages": [{"role": "system", "content": SYS},
                           {"role": "user", "content": prompt}]},
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def draft_offer(op):
    """Retourne (ok, texte|erreur)."""
    if op.score >= 70:
        angle = "Offre engageante : reformule le besoin avec un détail technique, identifie la contrainte qui décide du budget, propose une fourchette conditionnée à UNE question."
    elif op.score >= 45:
        angle = "Offre courte : reformule le besoin, dis les 2 éléments manquants pour chiffrer, propose un devis ferme dès réponse."
    else:
        angle = "Demande de devis : demande 2 précisions (volumétrie/utilisateurs, existant à reprendre) pour chiffrer, propose un devis en lots."
    prompt = (
        f"{angle}\n\n"
        f"TITRE: {op.titre}\nBUDGET: {op.budget_texte or op.budget_eur}\n"
        f"CATÉGORIE: {op.categorie}\nPROFILS: {', '.join(op.competences or [])}\n"
        f"BRIEF:\n{(op.description or op.resume_besoin)[:1800]}\n\n"
        "Rédige uniquement le message d'offre (pas de préambule)."
    )
    try:
        return True, _chat(prompt)
    except Exception as e:  # noqa: BLE001
        return False, f"IA locale indisponible : {type(e).__name__}"


def draft_relance(op):
    """Rédige une relance courte J+3 (Modèle 3) — non insistante. (ok, texte|err)."""
    prompt = (
        f"Rédige une RELANCE courte et non insistante (modèle J+3) pour l'appel d'offres "
        f"« {op.titre} ». Rappelle le projet en une ligne, demande où en est la sélection, "
        f"propose un découpage en lots pour démarrer sur une 1re tranche, et dis que tu "
        f"n'insisteras pas si le sujet est en pause. Pas de prix. Signe NOESIS."
    )
    try:
        return True, _chat(prompt, max_tokens=220)
    except Exception as e:  # noqa: BLE001
        return False, f"IA locale indisponible : {type(e).__name__}"


def suggest_next(op):
    prompt = (
        f"Opportunité « {op.titre} » — statut actuel : {op.get_stage_display()}, "
        f"score {op.score}/100, état {op.get_etat_display()}. "
        "Donne en UNE phrase la prochaine action commerciale concrète à mener (impératif)."
    )
    try:
        return True, _chat(prompt, max_tokens=80)
    except Exception as e:  # noqa: BLE001
        return False, f"IA locale indisponible : {type(e).__name__}"


def default_steps(op):
    """Étapes SLA par défaut selon le statut (liste de dicts, non persistées)."""
    today = _dt.date.today()
    steps = []
    if op.stage in ("detecte", "qualifie"):
        steps.append({"type": "offre", "libelle": "Envoyer l'offre (SLA < 2 h si score ≥ 70)",
                      "echeance": today})
    if op.stage == "offre_envoyee":
        base = op.date_offre or today
        steps.append({"type": "relance", "libelle": "Relance unique J+3",
                      "echeance": base + _dt.timedelta(days=3)})
        steps.append({"type": "cloture", "libelle": "Passer en « Sans réponse » si silence",
                      "echeance": base + _dt.timedelta(days=10)})
    if op.stage == "opportunite_future":
        steps.append({"type": "relance", "libelle": "Relance vivier (reprise/évolution)",
                      "echeance": op.date_relance or today + _dt.timedelta(days=45)})
    return steps
