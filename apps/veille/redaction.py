"""Pré-rédaction humanisée dans la plume de Thérèse via le `claude` local.

Cohérent avec la philosophie du projet (aucune clé API) : on spawn le binaire
`claude` déjà authentifié sur la machine, en one-shot (`claude -p`), et on parse
sa sortie JSON. Aucune info n'est inventée : le communiqué est la matière première.
"""
import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path

from django.conf import settings

_PLUME_PATH = Path(__file__).parent / "plume_therese.md"

CATEGORIE_ANGLE = {
    "hotellerie": "le voyage, l'art de recevoir, l'échappée",
    "design": "l'objet comme geste, la matière, l'atelier",
    "mode": "la silhouette comme récit, la saison",
    "food": "la table comme lieu de partage, le producteur",
    "culture": "l'œuvre, le patrimoine, la rencontre",
    "habitat": "l'espace habité, la lumière, l'architecture vécue",
    "beaute": "le rituel, le soin comme attention à soi",
    "societe": "la tendance vue de biais, avec recul",
    "events": "l'événement comme rendez-vous, l'ambiance des lieux",
    "autre": "l'angle atmosphère : ce que l'objet évoque, au-delà de la fiche",
}


@lru_cache(maxsize=1)
def plume() -> str:
    return _PLUME_PATH.read_text(encoding="utf-8")


def build_prompt(sujet: str, corps: str, categorie: str) -> str:
    # Blog Yonkko (One Piece TCG) : plume journalistique dédiée.
    if (categorie or "").startswith("op-") or categorie == "onepiece-tcg":
        from .yonkko import build_prompt as yonkko_prompt
        return yonkko_prompt(sujet, corps, categorie)
    # Blog Agentic Pods : plume analyse business / transformation agentique.
    if categorie == "agentique":
        matiere = (corps or "").strip()[:5000] or "(sujet sans corps ; s'appuyer sur le titre)"
        return f"""Tu es analyste éditorial du blog Agentic Pods, dédié à la transformation
de l'entreprise dans l'univers agentique (agents IA, automatisation, type-safe AI, AI primitives).
Écris un ARTICLE d'ANALYSE clair et crédible pour des dirigeants et décideurs tech, à partir
de la matière ci-dessous — vulgarisé mais rigoureux, orienté enjeux, cas d'usage, ROI et gouvernance.

=== MATIÈRE (réécrire à 100 %, ne rien recopier, n'invente aucun chiffre/citation) ===
Sujet : {sujet}
Contenu :
{matiere}

=== SORTIE : uniquement un JSON valide (sans texte autour, sans balises) ===
{{"titre": "...", "chapo": "...", "corps": "...", "seo_title": "...",
  "meta_description": "...", "tags": ["...", "..."], "image_alt": "..."}}
- "titre" : clair et concret (pas de hype creuse).
- "chapo" : 2-3 phrases posant l'enjeu business.
- "corps" : 350 à 600 mots, paragraphes courts, rubriques en CAPITALES si utile, explique le
  jargon (agent, orchestration, type-safe AI, primitives, gouvernance), pas de données inventées.
- "seo_title" ~60 car. · "meta_description" ~150 car. · "tags" 4-6 (minuscules, dont "agentic ai").
- "image_alt" : description courte de l'image principale.
"""
    angle = CATEGORIE_ANGLE.get(categorie, CATEGORIE_ANGLE["autre"])
    matiere = (corps or "").strip()[:6000] or "(communiqué sans corps ; s'appuyer sur le sujet)"
    return f"""Tu es Thérèse, la plume du blog déco & lifestyle 13 Atmosphère.
Écris un article ORIGINAL à partir du communiqué de presse ci-dessous, dans TA voix.

=== GUIDE DE PLUME (à respecter absolument) ===
{plume()}

=== ANGLE POUR CETTE CATÉGORIE ({categorie}) ===
{angle}

=== COMMUNIQUÉ (matière première — NE PAS recopier, réécrire à 100 %) ===
Sujet : {sujet}
Contenu :
{matiere}

=== CONSIGNE DE SORTIE ===
Rends UNIQUEMENT un objet JSON valide, sans texte autour, sans balises de code,
de la forme :
{{"titre": "...", "chapo": "...", "corps": "...", "seo_title": "...",
  "meta_description": "...", "tags": ["...", "..."], "image_alt": "..."}}
- "titre" : évocateur, imagé (pas "Communiqué", pas la marque en premier mot).
- "chapo" : 2 à 3 phrases qui posent l'atmosphère.
- "corps" : 350 à 600 mots, paragraphes courts, rubriques en CAPITALES si pertinent,
  ponctuation vivante, aucune donnée inventée (ni prix, ni date, ni citation absente).
- "seo_title" : ~60 caractères, accrocheur et lisible en résultat Google.
- "meta_description" : ~150-155 caractères, incitatif, sans guillemets.
- "tags" : 4 à 6 mots-clés pertinents (minuscules).
- "image_alt" : description courte de l'image de référence pour l'accessibilité/SEO.
"""


def _parse_json(out: str) -> dict | None:
    out = out.strip()
    # retire d'éventuelles clôtures ```json ... ```
    out = re.sub(r"^```(?:json)?\s*|\s*```$", "", out, flags=re.S).strip()
    m = re.search(r"\{.*\}", out, flags=re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not data.get("corps"):
        return None
    tags = data.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    return {
        "titre": str(data.get("titre", "")).strip()[:300],
        "chapo": str(data.get("chapo", "")).strip(),
        "corps": str(data.get("corps", "")).strip(),
        "seo_title": str(data.get("seo_title", "")).strip()[:300],
        "meta_description": str(data.get("meta_description", "")).strip()[:320],
        "tags": [str(t).strip().lower()[:40] for t in tags if str(t).strip()][:8],
        "image_alt": str(data.get("image_alt", "")).strip()[:300],
    }


def _est_rubrique(ligne: str) -> bool:
    s = ligne.strip()
    if not (2 <= len(s) <= 40):
        return False
    lettres = [c for c in s if c.isalpha()]
    return bool(lettres) and all(c.isupper() for c in lettres)


def corps_to_html(chapo: str, corps: str) -> str:
    """Convertit le brouillon (texte + rubriques CAPITALES) en HTML pour le MCP."""
    from html import escape
    out = []
    if chapo:
        out.append(f'<p class="chapo"><em>{escape(chapo.strip())}</em></p>')
    para = []

    def flush():
        if para:
            out.append("<p>" + escape(" ".join(para)) + "</p>")
            para.clear()

    for ligne in (corps or "").splitlines():
        s = ligne.strip()
        if not s:
            flush()
        elif _est_rubrique(s):
            flush()
            out.append(f"<h2>{escape(s)}</h2>")
        else:
            para.append(s)
    flush()
    return "\n".join(out)


def generer_draft_local(sujet: str, corps: str, categorie: str, timeout: int = 120):
    """Rédige via le modèle local (llama.cpp :8081) — gratuit/rapide. (draft|None, meta)."""
    import os

    import requests
    base = os.environ.get("LOCAL_LLM_BASE", "http://127.0.0.1:8081").rstrip("/")
    model = os.environ.get("LOCAL_LLM_MODEL", "qwen2.5-3b-local")
    prompt = build_prompt(sujet, corps, categorie)
    meta = {"cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0, "duration_ms": 0}
    try:
        r = requests.post(f"{base}/v1/chat/completions", timeout=timeout, json={
            "model": model, "temperature": 0.5, "max_tokens": 1100,
            "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        u = data.get("usage") or {}
        meta["input_tokens"] = int(u.get("prompt_tokens") or 0)
        meta["output_tokens"] = int(u.get("completion_tokens") or 0)
    except Exception:  # noqa: BLE001
        return None, meta
    return _parse_json(text), meta


def generer_draft(sujet: str, corps: str, categorie: str, timeout: int = 180):
    """Appelle le `claude` local. Renvoie (draft|None, meta).

    meta = {cost_usd, input_tokens, output_tokens, duration_ms} (usage renvoyé
    par le CLI, `--output-format json`). Sur abonnement Claude Code : pas de
    facturation API au token, `cost_usd` reflète l'équivalent rapporté par le CLI.
    """
    claude = getattr(settings, "COCKPIT_CLAUDE_BIN", "claude")
    prompt = build_prompt(sujet, corps, categorie)
    meta = {"cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0, "duration_ms": 0}
    try:
        proc = subprocess.run(
            [claude, "-p", prompt, "--output-format", "json"],
            capture_output=True, text=True, timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None, meta
    if proc.returncode != 0:
        return None, meta
    text = proc.stdout
    try:
        env = json.loads(proc.stdout)
        if isinstance(env, dict):
            text = env.get("result", "") or ""
            u = env.get("usage") or {}
            meta = {
                "cost_usd": float(env.get("total_cost_usd") or 0.0),
                "input_tokens": int(u.get("input_tokens") or 0),
                "output_tokens": int(u.get("output_tokens") or 0),
                "duration_ms": int(env.get("duration_ms") or 0),
            }
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    return _parse_json(text), meta
