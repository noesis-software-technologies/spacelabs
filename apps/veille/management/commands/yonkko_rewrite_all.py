"""Réécrit (via claude -p) et pousse en masse les sujets One Piece sur Yonkko.

Conçu pour tourner DÉTACHÉ (setsid nohup) : survit aux redémarrages de session,
reprenable (ne traite que statut='nouveau'), checkpoint par item. Rédaction
humanisée par le `claude` CLI local, push MCP en brouillon à la vraie date,
image de couverture = og:image de la source (best effort).

Usage (détaché) :
  setsid nohup .venv/bin/python manage.py yonkko_rewrite_all --limit 220 \
      > /tmp/yk_rewrite.log 2>&1 &
"""
import json
import re
import subprocess
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.timezone import now
from apps.veille.models import Blog, PressItem
from apps.veille import mcp

BLOG_ID = 20
CLAUDE = getattr(settings, "COCKPIT_CLAUDE_BIN", "claude")

PROMPT = """Tu es rédacteur pour un blog de fans de One Piece (yonko.life). Réécris l'actualité ci-dessous en un article ORIGINAL en français, ton naturel et humain de passionné, 300 à 380 mots.
RÈGLES STRICTES (l'article doit passer pour écrit par un humain, aucune trace d'IA) :
- Reformule tout, ne copie aucune phrase de la source.
- BURSTINESS : varie fortement la longueur des phrases. Alterne des phrases très courtes (3-5 mots) avec des phrases longues. Rythme irrégulier, jamais monotone.
- VOIX HUMAINE : glisse une opinion, une réaction ou une question rhétorique de fan ; une expression familière de temps en temps ; de petits apartés entre parenthèses.
- Bannis les tics d'IA : pas de « plongez dans », « n'hésitez pas », « dans cet article » ; pas de conclusion en « En résumé / En conclusion / Pour finir » ; pas de transitions génériques répétées.
- N'utilise JAMAIS le tiret cadratin « — » ni « – ». Uniquement le trait d'union simple « - ».
- Aucun mot entièrement en MAJUSCULES (sigles courts comme OP tolérés).
- Si c'est un leak/spoiler de chapitre ou d'épisode, ajoute une ligne <p><strong>Attention, spoilers.</strong></p> après l'intro.
- body_html en HTML : des <p>, un <h2>, éventuellement des puces avec « - ». Termine par <p><em>Source : {source}</em></p>.
- Ne fabrique pas de détails d'intrigue précis : si le contexte est mince, reste général.

Sujet : {sujet}
Contexte source : {contexte}

Réponds UNIQUEMENT par un objet JSON valide, sans texte autour :
{{"title": "<titre reformulé accrocheur>", "body_html": "<article HTML>", "meta": "<meta description ~150 caractères>", "keywords": "<5 à 8 mots-clés minuscules séparés par des virgules>"}}"""


def _fetch(url, timeout=12):
    """Résout le lien (redirection Google News) et renvoie (texte, og_image)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            html = r.read(400000).decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return "", ""
    og = ""
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, re.I) \
        or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image', html, re.I)
    if m:
        og = m.group(1)
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text[:2500], og


def _claude(prompt, timeout=180):
    try:
        proc = subprocess.run([CLAUDE, "-p", prompt, "--output-format", "json"],
                              capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    out = proc.stdout.strip()
    if not out:
        return None
    # enveloppe claude --output-format json → champ "result"
    try:
        env = json.loads(out)
        out = env.get("result", out) if isinstance(env, dict) else out
    except Exception:  # noqa: BLE001
        pass
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return None


class Command(BaseCommand):
    help = "Réécrit (claude -p) + pousse en masse les sujets One Piece sur Yonkko. Détachable."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=220)

    def handle(self, *args, **o):
        b = Blog.objects.get(id=BLOG_ID)
        qs = PressItem.objects.filter(categorie="onepiece", statut="nouveau").order_by("id")[:o["limit"]]
        total = qs.count()
        ok = err = 0
        self.stdout.write(f"start: {total} à traiter", ending="\n")
        self.stdout.flush()
        for it in list(qs):
            src_url = (it.liens_sources or [{}])[0].get("url", "") if it.liens_sources else ""
            source_name = it.expediteur or "web"
            contexte, og = _fetch(src_url) if src_url else ("", "")
            if len(contexte) < 120:
                contexte = f"{it.sujet}. {it.resume or ''}"
            prompt = PROMPT.format(source=source_name, sujet=it.sujet, contexte=contexte[:2500])
            data = _claude(prompt)
            if not data or not data.get("body_html") or len(data.get("body_html", "")) < 200:
                err += 1
                self.stdout.write(f"  SKIP #{it.id} (rédaction vide)"); self.stdout.flush()
                continue
            args_ = {"title": (data.get("title") or it.sujet)[:300],
                     "body_html": data["body_html"],
                     "meta_description": (data.get("meta") or "")[:300],
                     "meta_keywords": (data.get("keywords") or "")[:300]}
            if it.publier_le:
                args_["pub_date"] = it.publier_le.isoformat()
            try:
                r = mcp.rpc("tools/call", {"name": "draft_article", "arguments": args_},
                            url=b.mcp_url, token=b.mcp_token, timeout=90, retries=3)
                res = r.get("result") or {}
                if res.get("isError"):
                    err += 1; self.stdout.write(f"  ERR #{it.id} MCP"); self.stdout.flush(); continue
                sc = res.get("structuredContent") or {}
                art = sc.get("article_id") or res.get("article_id")
                if not art:
                    err += 1; continue
                if og:
                    try:
                        mcp.rpc("tools/call", {"name": "set_cover_image",
                                               "arguments": {"article_id": art, "image": {"url": og}}},
                                url=b.mcp_url, token=b.mcp_token, timeout=45, retries=1)
                    except Exception:  # noqa: BLE001
                        pass
                it.mcp_article_id = str(art); it.mcp_status = "draft"; it.mcp_pushed_at = now()
                it.draft_titre = args_["title"]; it.statut = "publie"; it.draft_statut = "publie"
                it.save()
                ok += 1
                self.stdout.write(f"  OK #{it.id} -> {art}{' +img' if og else ''}"); self.stdout.flush()
            except Exception as e:  # noqa: BLE001
                err += 1
                self.stdout.write(f"  ERR #{it.id} {type(e).__name__}"); self.stdout.flush()
        self.stdout.write(self.style.SUCCESS(f"FIN: poussés {ok} / erreurs {err} / total {total}"))
