"""Passe « humanizer » : 2e réécriture d'articles déjà en base pour casser
l'empreinte IA (variation de registre/rythme), français préservé, faits gardés.

Récupère le corps via get_article, le fait réécrire par `claude -p` avec une
consigne de forte variation humaine, puis update_article (même date). Option
--backtranslate : ajoute un aller-retour FR->EN->FR (via claude) pour churn lexical.

DRY-RUN par défaut ; --apply écrit. Cible : --ids 649,650  ou  --recent 20.

⚠️ Je n'ai PAS de détecteur IA branché : cette passe applique les bonnes pratiques
mais ne peut pas *prouver* qu'un texte passe un détecteur. Pour une boucle
détection-guidée (le vrai moyen de garantir), fournir une clé API détecteur.
"""
import json
import re
import subprocess

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from apps.veille.models import Blog, PressItem
from apps.veille import mcp, detector

BLOG_ID = 20
CLAUDE = getattr(settings, "COCKPIT_CLAUDE_BIN", "claude")

HUMANIZE = """Réécris l'article HTML ci-dessous pour qu'il sonne 100 % écrit par un humain, sans aucune trace d'IA. GARDE exactement les mêmes faits, la même langue (français) et le format HTML (<p>, <h2>, puces « - »). Ne change pas le sens.
Impératifs de style :
- Burstiness forte : mélange phrases très courtes et longues, rythme irrégulier.
- Voix personnelle : une opinion, une pointe d'ironie ou une question de fan ; petits apartés entre parenthèses.
- Supprime tout tic d'IA (« plongez dans », « n'hésitez pas », « en conclusion », transitions génériques).
- Jamais de tiret cadratin « — »/« – » : uniquement « - ». Aucun mot tout en MAJUSCULES.
- Varie le vocabulaire, évite les tournures trop lisses/parallèles.
Réponds UNIQUEMENT par un JSON : {{"body_html": "<article réécrit>"}}.

ARTICLE :
{body}"""

BACKTRANSLATE = """Traduis fidèlement ce texte {src} vers {dst}, sans rien ajouter. Réponds uniquement par la traduction brute.

{text}"""


def _claude(prompt, timeout=180):
    try:
        p = subprocess.run([CLAUDE, "-p", prompt, "--output-format", "json"],
                           capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    out = (p.stdout or "").strip()
    try:
        env = json.loads(out)
        out = env.get("result", out) if isinstance(env, dict) else out
    except Exception:  # noqa: BLE001
        pass
    return out


def _json_body(out):
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0)).get("body_html")
    except Exception:  # noqa: BLE001
        return None


class Command(BaseCommand):
    help = "Passe humanizer (2e réécriture Claude) sur des articles Yonkko déjà poussés."

    def add_arguments(self, parser):
        parser.add_argument("--ids", default="", help="ids d'articles blog (csv)")
        parser.add_argument("--recent", type=int, default=0, help="N derniers articles poussés")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--backtranslate", action="store_true")
        parser.add_argument("--target", type=int, default=40, help="score détecteur visé (<)")
        parser.add_argument("--passes", type=int, default=3, help="tentatives max de réécriture")
        parser.add_argument("--force", action="store_true", help="humaniser même si déjà sous le seuil")

    def handle(self, *args, **o):
        b = Blog.objects.get(id=BLOG_ID)
        art_ids = [x.strip() for x in o["ids"].split(",") if x.strip()]
        if o["recent"]:
            qs = (PressItem.objects.filter(categorie__in=["onepiece"], mcp_article_id__gt="")
                  .order_by("-mcp_pushed_at")[:o["recent"]])
            art_ids = [p.mcp_article_id for p in qs]
        if not art_ids:
            raise CommandError("préciser --ids ou --recent")
        ok = err = 0
        for aid in art_ids:
            g = mcp.rpc("tools/call", {"name": "get_article", "arguments": {"article_id": int(aid)}},
                        url=b.mcp_url, token=b.mcp_token, timeout=60, retries=2)
            sc = (g.get("result") or {}).get("structuredContent") or {}
            body = sc.get("body_html") or ""
            rev = sc.get("revision")
            if not body or not rev:
                err += 1; self.stdout.write(f"  #{aid} illisible"); continue
            base_score = detector.score(body)["score"]
            if base_score < o["target"] and not o["force"]:
                self.stdout.write(f"  #{aid} déjà humain ({base_score}) — sauté"); continue
            # boucle guidée par le détecteur : on garde la meilleure des N réécritures
            best, best_s = None, base_score
            for _ in range(max(1, o["passes"])):
                cand = _json_body(_claude(HUMANIZE.format(body=body[:12000])))
                if cand and o["backtranslate"]:
                    en = _claude(BACKTRANSLATE.format(src="français", dst="anglais", text=cand[:12000]))
                    if en:
                        cand = _claude(BACKTRANSLATE.format(src="anglais", dst="français", text=en[:12000])) or cand
                if not cand or len(cand) < 200:
                    continue
                sc = detector.score(cand)["score"]
                if sc < best_s:
                    best, best_s = cand, sc
                if sc < o["target"]:
                    break
            new = best
            if not new:
                err += 1; self.stdout.write(f"  #{aid} pas d'amélioration ({base_score})"); continue
            if not o["apply"]:
                self.stdout.write(f"  DRY #{aid} {base_score} -> {best_s}"); ok += 1; continue
            u = mcp.rpc("tools/call", {"name": "update_article",
                                       "arguments": {"article_id": int(aid), "expected_revision": rev,
                                                     "body_html": new}},
                        url=b.mcp_url, token=b.mcp_token, timeout=90, retries=2)
            if (u.get("result") or {}).get("isError"):
                err += 1; self.stdout.write(f"  #{aid} update err")
            else:
                ok += 1; self.stdout.write(f"  #{aid} humanisé ({base_score} -> {best_s})")
        self.stdout.write(self.style.SUCCESS(f"humanize: ok {ok} / err {err} "
                                             + ("(DRY-RUN)" if not o["apply"] else "")))
