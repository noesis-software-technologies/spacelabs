"""Pipeline complet Yonkko : rédaction → images (cover + galerie) → publication.

Pour chaque sujet du bloc Yonkko, dans l'ordre :
1. rédige le brouillon (modèle local) s'il n'existe pas ;
2. illustre (Pexels, cover + carrousel) s'il n'a pas d'images ;
3. pousse le brouillon sur yonko.life via MCP, daté à demain (publication
   manuelle par l'humain).

Idempotent/résumable : saute ce qui est déjà rédigé/illustré/poussé.
Usage : python manage.py yonkko_run [--limit 100] [--per-article 3]
"""
import datetime as _dt
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.utils.timezone import now

from apps.veille.mcp import image_arg, mcp_creds, publish_item, rpc
from apps.veille.models import PressItem
from apps.veille.pexels import search
from apps.veille.redaction import generer_draft_local
from apps.veille.yonkko import pexels_query

EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


class Command(BaseCommand):
    help = "Rédige + illustre + publie les articles Yonkko sur yonko.life (brouillons datés demain)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--per-article", type=int, default=4)
        parser.add_argument("--timeout", type=int, default=150)
        parser.add_argument("--reimage", action="store_true",
                            help="Re-illustre + met à jour cover/galerie des articles DÉJÀ poussés.")

    def _draft(self, it, timeout):
        draft, meta = generer_draft_local(it.sujet, it.corps, it.categorie, timeout=timeout)
        if not draft:
            return False
        it.draft_titre = draft["titre"]
        it.draft_chapo = draft["chapo"]
        it.draft_corps = draft["corps"]
        it.seo_title = draft.get("seo_title", "")
        it.meta_description = draft.get("meta_description", "")
        it.tags = draft.get("tags", [])
        it.image_alt = it.image_alt or draft.get("image_alt", "")
        it.slug = it.slug or slugify(draft.get("seo_title") or draft["titre"])[:300]
        it.draft_statut = "brouillon"
        it.draft_genere_le = now()
        it.save()
        return True

    def _images(self, it, per_article, timeout, force=False):
        # Requête curée par sous-catégorie (les tags d'article polluent Pexels).
        photos = search(pexels_query(it.categorie), per_page=per_article)
        if not photos:
            return 0
        dest = Path(settings.MEDIA_ROOT) / "veille" / str(it.pk) / "pexels"
        dest.mkdir(parents=True, exist_ok=True)
        local = []
        for n, ph in enumerate(photos):
            try:
                r = requests.get(ph["url"], timeout=timeout)
                r.raise_for_status()
            except requests.RequestException:
                continue
            ext = EXT.get(r.headers.get("Content-Type", "").split(";")[0].strip(), ".jpg")
            (dest / f"px{n:02d}{ext}").write_bytes(r.content)
            local.append(f"{settings.MEDIA_URL}veille/{it.pk}/pexels/px{n:02d}{ext}")
        if not local:
            return 0
        it.images_local = local
        if not it.image_url:
            it.image_url = local[0]
        if not it.image_alt and photos[0].get("alt"):
            it.image_alt = photos[0]["alt"][:300]
        it.save(update_fields=["images_local", "image_url", "image_alt"])
        return len(local)

    def _reimage_pushed(self, o):
        """Re-télécharge de belles images et met à jour cover + carrousel des
        articles déjà poussés, SANS recréer de brouillon (utilise l'article_id)."""
        qs = (PressItem.objects.filter(blog_cible__bloc="Yonkko")
              .filter(mcp_status__in=["draft", "published"]).exclude(mcp_article_id="")[: o["limit"]])
        fixed = 0
        for it in qs:
            try:
                if not self._images(it, o["per_article"], 25, force=True):
                    continue
                url, tok = mcp_creds(it)
                art = it.mcp_article_id
                if it.image_ref:
                    rpc("tools/call", {"name": "set_cover_image",
                                       "arguments": {"article_id": art,
                                                     "image": image_arg(it.image_ref, it.image_alt)}},
                        2, 60, url=url, token=tok)
                imgs = [image_arg(u, it.image_alt, f"img{n}") for n, u in enumerate(it.carrousel)]
                if imgs:
                    rpc("tools/call", {"name": "add_carousel_images",
                                       "arguments": {"article_id": art, "images": imgs}},
                        3, 60, url=url, token=tok)
                fixed += 1
                self.stdout.write(self.style.SUCCESS(f"✓ galerie MAJ : {it.draft_titre[:45]} ({len(imgs)} imgs)"))
            except Exception as e:  # noqa: BLE001
                self.stdout.write(self.style.ERROR(f"✗ reimage {it.sujet[:40]} : {type(e).__name__}"))
        self.stdout.write(self.style.SUCCESS(f"\nRe-illustration : {fixed} article(s) mis à jour."))

    def handle(self, *args, **o):
        if o["reimage"]:
            return self._reimage_pushed(o)
        demain = now().date() + _dt.timedelta(days=1)
        qs = (PressItem.objects.filter(blog_cible__bloc="Yonkko")
              .exclude(mcp_status__in=["draft", "published"])
              .order_by("-recu_le", "-id")[: o["limit"]])
        done = fail = 0
        for it in qs:
            try:
                if it.draft_statut == "vide" and not self._draft(it, o["timeout"]):
                    fail += 1
                    self.stdout.write(self.style.ERROR(f"✗ rédac {it.sujet[:40]}"))
                    continue
                if not it.toutes_images:
                    self._images(it, o["per_article"], 25)
                if not it.publier_le:
                    it.publier_le = demain
                    it.save(update_fields=["publier_le"])
                res = publish_item(it, with_images=True)
                if res.get("ok"):
                    done += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"✓ {done} publié : {it.draft_titre[:45]} (imgs {res.get('images', 0)})"))
                else:
                    fail += 1
                    self.stdout.write(self.style.ERROR(f"✗ push {it.sujet[:40]} : {res.get('error')}"))
            except Exception as e:  # noqa: BLE001
                fail += 1
                self.stdout.write(self.style.ERROR(f"✗ {it.sujet[:40]} : {type(e).__name__} {e}"))
        pushed = PressItem.objects.filter(blog_cible__bloc="Yonkko",
                                          mcp_status__in=["draft", "published"]).count()
        self.stdout.write(self.style.SUCCESS(
            f"\nYonkko run : {done} publié(s), {fail} échec(s) — total poussé {pushed}/100."))
