"""Publie les brouillons vers le MCP de 13 Atmosphère (JSON-RPC).

Mappe nos articles sur les outils du MCP : draft_article → set_cover_image →
add_carousel_images. La publication finale reste une **validation humaine** côté
blog (/administration/calendar/) : ce client ne fait que créer les brouillons.

Sûr par défaut : **dry-run** (affiche les payloads). Ajoute --send pour émettre.
Requiert ATMOSPHERE_MCP_TOKEN (dans .env.local) et un endpoint joignable.

  python manage.py veille_publish --status valide --dry-run
  python manage.py veille_publish --status valide --send --limit 5
"""
import base64
import json
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.veille.models import PressItem
from apps.veille.redaction import corps_to_html


def _b64_local(media_path):
    """/media/veille/x/y.jpg -> base64 du fichier si présent localement."""
    rel = media_path.replace(settings.MEDIA_URL, "", 1).lstrip("/")
    f = Path(settings.MEDIA_ROOT) / rel
    if f.exists():
        return base64.b64encode(f.read_bytes()).decode("ascii")
    return None


def _image_arg(url, alt="", name=""):
    """Construit l'argument image {data_base64|url, alt, name} pour le MCP."""
    arg = {"alt": alt, "name": name}
    if url.startswith(settings.MEDIA_URL):
        b64 = _b64_local(url)
        if b64:
            arg["data_base64"] = b64
            return arg
    arg["url"] = url
    return arg


class Command(BaseCommand):
    help = "Publie les brouillons vers le MCP 13 Atmosphère (dry-run par défaut)."

    def add_arguments(self, parser):
        parser.add_argument("--status", default="valide",
                            help="Statuts de brouillon à publier (défaut : valide).")
        parser.add_argument("--categorie")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--send", action="store_true",
                            help="Émet réellement vers le MCP (sinon dry-run).")
        parser.add_argument("--dry-run", action="store_true",
                            help="Explicite le mode dry-run (défaut si --send absent).")
        parser.add_argument("--no-images", action="store_true", help="N'envoie pas les images.")
        parser.add_argument("--timeout", type=int, default=60)

    def _rpc(self, url, token, method, params, rid, timeout):
        r = requests.post(url, timeout=timeout,
                          headers={"Authorization": f"Bearer {token}",
                                   "Content-Type": "application/json"},
                          json={"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        r.raise_for_status()
        return r.json()

    def _payload(self, it):
        internal = [{"text": lk["titre"], "slug": lk["slug"]}
                    for lk in (it.liens_internes or []) if lk.get("slug")]
        external = [{"text": lk.get("texte") or lk["url"], "url": lk["url"]}
                    for lk in (it.liens_sources or []) if lk.get("kind") in ("kit", "lien")]
        args = {
            "title": it.seo_title or it.draft_titre or it.sujet,
            "body_html": corps_to_html(it.draft_chapo, it.draft_corps),
            "meta_description": it.meta_description,
            "meta_keywords": it.tags or [],
            "category_slugs": [it.categorie],
            "internal_links": internal,
            "external_backlinks": external,
        }
        if it.publier_le:
            args["pub_date"] = it.publier_le.isoformat()
        return args

    def handle(self, *args, **o):
        url = settings.ATMOSPHERE_MCP_URL
        token = settings.ATMOSPHERE_MCP_TOKEN
        statuses = [s.strip() for s in o["status"].split(",") if s.strip()]
        qs = PressItem.objects.filter(draft_statut__in=statuses).exclude(draft_corps="")
        if o["categorie"]:
            qs = qs.filter(categorie=o["categorie"])
        qs = qs.order_by("publier_le", "categorie", "id")
        if o["limit"]:
            qs = qs[: o["limit"]]
        items = list(qs)
        if not items:
            self.stdout.write(self.style.WARNING("Aucun brouillon à publier pour ce filtre."))
            return

        if o["send"] and not token:
            raise CommandError("ATMOSPHERE_MCP_TOKEN manquant (mets-le dans .env.local).")

        rid = 0
        ok = 0
        for it in items:
            args = self._payload(it)
            self.stdout.write(f"\n=== [{it.categorie}] {args['title'][:60]} ===")
            if not o["send"]:
                self.stdout.write(json.dumps(
                    {"method": "draft_article", "arguments": {**args, "body_html": args["body_html"][:120] + "…"}},
                    ensure_ascii=False, indent=2))
                if not o["no_images"]:
                    self.stdout.write(f"  + cover: {it.image_ref or '—'} | carrousel: {len(it.carrousel)} image(s)")
                continue
            try:
                rid += 1
                res = self._rpc(url, token, "tools/call",
                                {"name": "draft_article", "arguments": args}, rid, o["timeout"])
                art = (((res.get("result") or {}).get("structuredContent") or {}).get("article_id")
                       or (res.get("result") or {}).get("article_id"))
                if not art:
                    self.stdout.write(self.style.ERROR(f"  pas d'article_id renvoyé : {json.dumps(res)[:200]}"))
                    continue
                it.mcp_article_id = str(art)
                it.save(update_fields=["mcp_article_id"])
                if not o["no_images"]:
                    if it.image_ref:
                        rid += 1
                        self._rpc(url, token, "tools/call",
                                  {"name": "set_cover_image",
                                   "arguments": {"article_id": art, "image": _image_arg(it.image_ref, it.image_alt)}},
                                  rid, o["timeout"])
                    imgs = [_image_arg(u, it.image_alt, f"img{n}") for n, u in enumerate(it.carrousel)]
                    if imgs:
                        rid += 1
                        self._rpc(url, token, "tools/call",
                                  {"name": "add_carousel_images",
                                   "arguments": {"article_id": art, "images": imgs}}, rid, o["timeout"])
                ok += 1
                self.stdout.write(self.style.SUCCESS(f"  → brouillon MCP créé (article_id={art})"))
            except requests.RequestException as e:
                self.stdout.write(self.style.ERROR(f"  échec MCP : {e}"))

        if o["send"]:
            self.stdout.write(self.style.SUCCESS(f"\n{ok}/{len(items)} brouillon(s) créé(s) sur le MCP. "
                                                 f"Validation humaine sur /administration/calendar/."))
        else:
            self.stdout.write(self.style.WARNING(f"\n[DRY-RUN] {len(items)} article(s) prêts. Ajoute --send pour émettre."))
