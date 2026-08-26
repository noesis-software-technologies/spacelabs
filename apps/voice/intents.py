"""Routage d'intentions vocales — déterministe, jamais un LLM (ADR-4).

Pourquoi pas d'IA ici
---------------------
Une regex qui rate se corrige en une ligne et se teste. Une hallucination qui
tue un pane ou lance une mission ne se rattrape pas. Le LLM travaille *dans*
les agents ; il ne décide pas *quoi faire du cockpit*.

Conséquence assumée : le vocabulaire reconnu est fini et documenté. Une phrase
non comprise renvoie ``unknown`` avec la liste de ce qu'on sait faire — jamais
une action approximative.

Toutes les fonctions ici sont **pures** : texte → décision. L'exécution est
ailleurs (``execute``), ce qui rend le vocabulaire testable sans DB ni agents.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

MAX_SPAWN = 8


@dataclass
class Intent:
    kind: str
    args: dict = field(default_factory=dict)
    said: str = ""

    @property
    def understood(self) -> bool:
        return self.kind != "unknown"


def _norm(text: str) -> str:
    """Minuscules sans accents : « démarre » et « demarre » sont le même mot.

    La transcription vocale accentue de façon instable ; comparer sur une forme
    normalisée évite d'écrire chaque motif en double.
    """
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text.lower()).strip()


_WORDS = {
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4,
    "cinq": 5, "six": 6, "sept": 7, "huit": 8,
}


def _number(text: str, default=None):
    m = re.search(r"\b(\d{1,2})\b", text)
    if m:
        return int(m.group(1))
    for word, value in _WORDS.items():
        if re.search(rf"\b{word}\b", text):
            return value
    return default


def parse(said: str) -> Intent:
    """Texte transcrit → intention. Premier motif qui matche gagne."""
    t = _norm(said)
    if not t:
        return Intent("unknown", said=said)

    # L'ordre compte : « lance la mission » avant « lance un agent ».
    if re.search(r"\b(statut|status|ou en (est|sont)|que font|qui travaille)\b", t):
        return Intent("status", said=said)

    if re.search(r"\b(mission|planifie|planifier|plan)\b", t):
        if re.search(r"\b(lance|demarre|demarrer|commence|go)\b", t):
            return Intent("mission_start", said=said)
        if re.search(r"\b(pause|arrete|arreter|stop|suspend)\b", t):
            return Intent("mission_pause", said=said)
        if re.search(r"\b(planifie|planifier|plan|decoupe)\b", t):
            return Intent("mission_plan", said=said)

    if re.search(r"\b(ajoute|cree|creer|nouvelles?|nouvelle)\b.*\b(taches?|tickets?|cartes?)\b", t):
        title = re.sub(r"^.*?\b(taches?|tickets?|cartes?)\b\s*(pour|de|:)?\s*", "", t).strip()
        return Intent("task_add", {"title": title or "Nouvelle tâche"}, said=said)

    if re.search(r"\b(agents?|panes?|terminal|terminaux|instances?|chats?)\b", t) and re.search(
        r"\b(ajoute|lance|demarre|demarrer|ouvre|spawn|cree|creer)\b", t
    ):
        n = _number(t, 1) or 1
        return Intent("spawn", {"count": max(1, min(MAX_SPAWN, n))}, said=said)

    if re.search(r"\b(densite|compact|dense|micro|cozy|serre|confortable)\b", t):
        level = "cozy"
        if "micro" in t:
            level = "micro"
        elif "dense" in t or "serre" in t:
            level = "dense"
        elif "compact" in t:
            level = "compact"
        return Intent("density", {"level": level}, said=said)

    if re.search(r"\b(panique|panic|coupe tout|urgence)\b", t):
        return Intent("panic", said=said)

    # Adresser une consigne à un agent précis : « dis à l'agent deux de … »
    m = re.search(r"\b(?:agents?|panes?)\s*(?:numero\s*)?(\d{1,2}|un|une|deux|trois|quatre|cinq|six)\b", t)
    if m and re.search(r"\b(dis|demande|fais|envoie|passe)\b", t):
        order = re.sub(r"^.*?\b(de|que|:)\s+", "", said).strip()
        return Intent("dispatch", {"pane": _number(m.group(1), 1), "order": order or said}, said=said)

    return Intent("unknown", said=said)


VOCABULARY = [
    "« où en sont mes agents » — l'état du workspace",
    "« lance deux agents » — ouvre des instances",
    "« planifie la mission » — Claude découpe l'objectif",
    "« lance la mission » / « mets la mission en pause »",
    "« ajoute une tâche : relire les tests »",
    "« passe en dense » — densité d'affichage",
    "« panique » — coupe le direct et repasse tout en privé",
]


def describe_unknown() -> str:
    return "Je n'ai pas compris. Je sais faire : " + " · ".join(VOCABULARY)
