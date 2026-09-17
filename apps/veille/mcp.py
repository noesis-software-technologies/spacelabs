"""Client MCP 13 Atmosphère — logique de publication réutilisable.

Utilisé par la commande `veille_publish` et par le bouton « quick view » de la
liste veille. On ne crée que des **brouillons** (draft) : 13-atmosphere.com reste
le seul publicateur (validation humaine au calendrier).
"""
import base64
import time
from pathlib import Path

import requests
from django.conf import settings
from django.utils.timezone import now

from .categories import blog_slugs
from .redaction import corps_to_html


def _b64_local(media_path: str):
    rel = media_path.replace(settings.MEDIA_URL, "", 1).lstrip("/")
    f = Path(settings.MEDIA_ROOT) / rel
    return base64.b64encode(f.read_bytes()).decode("ascii") if f.exists() else None


def image_arg(url: str, alt: str = "", name: str = "") -> dict:
    arg = {"alt": alt, "name": name}
    if url.startswith(settings.MEDIA_URL):
        b64 = _b64_local(url)
        if b64:
            arg["data_base64"] = b64
            return arg
    arg["url"] = url
    return arg


def rpc(method: str, params: dict, rid: int = 1, timeout: int = 60, retries: int = 3) -> dict:
    """Appel JSON-RPC avec retry/backoff sur 503/502/504 (le blog flappe)."""
    last = None
    for attempt in range(retries):
        r = requests.post(
            settings.ATMOSPHERE_MCP_URL, timeout=timeout,
            headers={"Authorization": f"Bearer {settings.ATMOSPHERE_MCP_TOKEN}",
                     "Content-Type": "application/json"},
            json={"jsonrpc": "2.0", "id": rid, "method": method, "params": params},
        )
        if r.status_code in (502, 503, 504) and attempt < retries - 1:
            last = r
            time.sleep(1.5 * (attempt + 1))  # backoff : 1.5s, 3s
            continue
        r.raise_for_status()
        return r.json()
    if last is not None:
        last.raise_for_status()
    return {}


def payload(it) -> dict:
    internal = [{"text": lk["titre"], "slug": lk["slug"]}
                for lk in (it.liens_internes or []) if lk.get("slug")]
    external = [{"text": lk.get("texte") or lk["url"], "url": lk["url"]}
                for lk in (it.liens_sources or []) if lk.get("kind") in ("kit", "lien")]
    args = {
        "title": it.seo_title or it.draft_titre or it.sujet,
        "body_html": corps_to_html(it.draft_chapo, it.draft_corps),
        "meta_description": it.meta_description,
        "meta_keywords": ", ".join(it.tags or []),
        "category_slugs": blog_slugs(it.categorie),
        "internal_links": internal,
        "external_backlinks": external,
    }
    if it.publier_le:
        args["pub_date"] = it.publier_le.isoformat()
    return args


def publish_item(it, with_images: bool = True, timeout: int = 60) -> dict:
    """Crée/MAJ le brouillon sur le MCP. Renvoie {ok, article_id?, admin_url?, images?, error?}."""
    if not settings.ATMOSPHERE_MCP_TOKEN:
        return {"ok": False, "error": "ATMOSPHERE_MCP_TOKEN manquant (.env.local)"}
    try:
        res = rpc("tools/call", {"name": "draft_article", "arguments": payload(it)}, 1, timeout)
    except requests.RequestException as e:
        return {"ok": False, "error": f"MCP injoignable : {e}"}
    result = res.get("result") or {}
    if result.get("isError"):
        txt = (result.get("content") or [{}])[0].get("text", "")
        return {"ok": False, "error": f"MCP: {txt[:200]}"}
    sc = result.get("structuredContent") or {}
    art = sc.get("article_id") or result.get("article_id")
    if not art:
        return {"ok": False, "error": "pas d'article_id renvoyé"}
    it.mcp_article_id = str(art)
    it.mcp_pushed_at = now()
    it.mcp_status = "draft"
    it.save(update_fields=["mcp_article_id", "mcp_pushed_at", "mcp_status"])
    n_img = 0
    if with_images:
        try:
            if it.image_ref:
                rpc("tools/call", {"name": "set_cover_image",
                                   "arguments": {"article_id": art,
                                                 "image": image_arg(it.image_ref, it.image_alt)}}, 2, timeout)
            imgs = [image_arg(u, it.image_alt, f"img{n}") for n, u in enumerate(it.carrousel)]
            if imgs:
                rpc("tools/call", {"name": "add_carousel_images",
                                   "arguments": {"article_id": art, "images": imgs}}, 3, timeout)
                n_img = len(imgs)
        except requests.RequestException as e:
            return {"ok": True, "article_id": art, "admin_url": sc.get("admin_url", ""),
                    "images": 0, "warning": f"images non envoyées : {e}"}
    return {"ok": True, "article_id": art, "admin_url": sc.get("admin_url", ""),
            "slug": sc.get("slug", ""), "images": n_img}


def refresh_statuses(timeout: int = 30) -> dict:
    """Réconcilie l'état côté blog : list_drafts → 'draft' ; poussés absents = 'published'.

    Un article poussé qui n'est plus dans les brouillons a été validé/publié par
    l'équipe (accepté). Met à jour mcp_status localement. Renvoie {ok, draft, published}.
    """
    from .models import PressItem
    if not settings.ATMOSPHERE_MCP_TOKEN:
        return {"ok": False, "error": "token manquant"}
    try:
        res = rpc("tools/call", {"name": "list_drafts", "arguments": {}}, 1, timeout)
    except requests.RequestException as e:
        return {"ok": False, "error": str(e)}
    sc = (res.get("result") or {}).get("structuredContent") or {}
    draft_ids = {str(d.get("article_id")) for d in (sc.get("drafts") or [])}
    n_draft = n_pub = 0
    for it in PressItem.objects.exclude(mcp_article_id=""):
        st = "draft" if it.mcp_article_id in draft_ids else "published"
        if it.mcp_status != st:
            it.mcp_status = st
            it.save(update_fields=["mcp_status"])
        n_draft += st == "draft"
        n_pub += st == "published"
    return {"ok": True, "draft": n_draft, "published": n_pub}
