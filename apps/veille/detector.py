"""Détecteur « trace IA » maison — 100 % local, sans API externe.

Approche stylométrique (heuristique honnête, pas un modèle entraîné) : mesure les
signaux que les détecteurs et les lecteurs associent au texte IA en français, et
que notre humanizer doit faire disparaître :
  - burstiness faible (longueurs de phrases trop uniformes),
  - tics d'IA (« en conclusion », « plongez dans »...),
  - tells typographiques (tiret cadratin, puces •),
  - ouvertures de phrases répétitives,
  - sur-densité de connecteurs (« de plus », « par ailleurs »...).

score() renvoie 0 (très humain) à 100 (très « IA »). verdict : humain <35,
mitigé 35-60, ia >60. C'est un garde-fou local, pas une preuve absolue.
"""
import re
import statistics

AI_PHRASES = [
    "en conclusion", "en résumé", "pour conclure", "pour finir", "en somme",
    "il est important de", "il convient de", "force est de constater",
    "plongez dans", "plongeons", "n'hésitez pas", "dans cet article",
    "au-delà de", "que demander de plus", "il est essentiel", "il est crucial",
    "sans plus attendre", "au cœur de", "véritable", "incontournable",
    "dans un monde où", "à l'ère de", "riche en rebondissements",
]
CONNECTORS = [
    "de plus", "par ailleurs", "en effet", "ainsi", "cependant", "néanmoins",
    "notamment", "en outre", "toutefois", "de surcroît", "par conséquent",
]
TYPO_TELLS = ["—", "–", "•"]


def _strip(html):
    txt = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html or "")
    txt = re.sub(r"(?s)<[^>]+>", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()


def _sentences(txt):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", txt) if len(s.strip()) > 1]


def score(html_or_text):
    txt = _strip(html_or_text)
    low = txt.lower()
    words = re.findall(r"\w+", low)
    n = max(len(words), 1)
    sents = _sentences(txt)
    lengths = [len(re.findall(r"\w+", s)) for s in sents] or [0]

    signals = {}
    # 1. Burstiness : coefficient de variation des longueurs de phrases.
    if len(lengths) >= 3 and statistics.mean(lengths):
        cv = statistics.pstdev(lengths) / statistics.mean(lengths)
    else:
        cv = 0.5
    # cv humain typiquement >0.5 ; <0.35 = uniforme (robotique)
    burst_pen = max(0, min(1, (0.55 - cv) / 0.55)) * 30
    signals["burstiness"] = round(cv, 2)

    # 2. Tics d'IA
    ai_hits = sum(low.count(p) for p in AI_PHRASES)
    tic_pen = min(ai_hits * 8, 28)
    signals["tics_ia"] = ai_hits

    # 3. Tells typographiques
    typo_hits = sum(txt.count(t) for t in TYPO_TELLS)
    typo_pen = min(typo_hits * 6, 18)
    signals["typo_tells"] = typo_hits

    # 4. Ouvertures de phrases répétitives
    openers = [(re.findall(r"\w+", s.lower()) or [""])[0] for s in sents]
    rep = (len(openers) - len(set(openers))) / max(len(openers), 1)
    rep_pen = min(rep * 30, 14)
    signals["ouvertures_repetees"] = round(rep, 2)

    # 5. Sur-densité de connecteurs
    conn = sum(low.count(c) for c in CONNECTORS)
    conn_density = conn / (len(sents) or 1)
    conn_pen = min(conn_density * 20, 10)
    signals["densite_connecteurs"] = round(conn_density, 2)

    total = round(min(burst_pen + tic_pen + typo_pen + rep_pen + conn_pen, 100))
    verdict = "humain" if total < 35 else ("mitigé" if total <= 60 else "ia")
    return {"score": total, "verdict": verdict, "signals": signals,
            "penalites": {"burstiness": round(burst_pen), "tics": tic_pen,
                          "typo": typo_pen, "repetition": round(rep_pen),
                          "connecteurs": round(conn_pen)}}
