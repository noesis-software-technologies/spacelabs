"""Scrape le site OFFICIEL One Piece Card Game (fr.onepiece-cardgame.com/news)
pour Yonkko, AVEC les vraies photos de chaque article (cover + galerie).

Source : API JSON /common/templates/api/article_list.php (liste), puis page de
chaque article pour récupérer les visuels officiels. Dédup par `path`.
Les images (URLs absolues du site officiel) alimentent cover + carrousel.

Usage : python manage.py veille_scrape_opcg [--limit 100] [--gallery 5]
"""
import re

import requests
from django.core.management.base import BaseCommand
from django.utils.timezone import now

from apps.veille.models import Blog, PressItem
from apps.veille.yonkko import BLOC, SUBCATS

BASE = "https://fr.onepiece-cardgame.com"
API = BASE + "/common/templates/api/article_list.php"
H = {"User-Agent": "Mozilla/5.0", "Referer": BASE + "/news/"}

# Catégories officielles → sous-catégories Yonkko.
CATMAP = {
    "PRODUCTS": "op-sorties", "EVENTS": "op-tournois", "CARDS": "op-collection",
    "ANNOUNCE": "op-actu", "RULES": "op-actu", "MAGAZINE": "op-actu", "STREAM": "op-actu",
}
IMG_RE = re.compile(r'(/onepiececg/[^"\')\s]+\.(?:webp|jpg|jpeg|png))', re.I)


def _abs(path):
    if not path:
        return ""
    path = path.split("?")[0]
    return path if path.startswith("http") else BASE + path


class Command(BaseCommand):
    help = "Scrape le site officiel One Piece Card Game (news + photos) pour Yonkko."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--gallery", type=int, default=5, help="Nb max d'images/galerie")
        parser.add_argument("--no-page", action="store_true",
                            help="Ne pas ouvrir chaque page (plus rapide, cover seule).")

    def handle(self, *args, **o):
        # Pagination : l'API renvoie 100/appel — on boucle sur start jusqu'à tout avoir.
        data, start = [], 0
        try:
            while True:
                d = requests.get(API, timeout=30, headers=H,
                                 params={"start": start, "limit": 100}).json()["data"]
                batch = d.get("article_list") or []
                data.extend(batch)
                total = d.get("total_count", len(data))
                start += len(batch)
                if not batch or start >= total or len(data) >= o["limit"]:
                    break
        except Exception as e:  # noqa: BLE001
            if not data:
                self.stderr.write(self.style.ERROR(f"API officielle inaccessible : {e}"))
                return
        # sous-blogs Yonkko (déjà créés par yonkko_prepare)
        subs = {b.categorie: b for b in Blog.objects.filter(bloc=BLOC)}
        principal = Blog.objects.filter(domaine="yonko.life").first()

        created = updated = 0
        for a in data[: o["limit"]]:
            path = a.get("path") or ""
            if not path:
                continue
            mid = "opcg-" + path
            title = (a.get("title") or "").strip()
            desc = (a.get("meta") or {}).get("fr") or ""
            catcode = (a.get("categories") or {}).get("code", "")
            slug = CATMAP.get(catcode, "op-actu")
            blog = subs.get(slug) or principal
            cover = _abs(a.get("thumbnail"))
            gallery = [cover] if cover else []
            # visuels dans la page de l'article
            url = a.get("url") or ""
            if not o["no_page"] and url.startswith("http"):
                try:
                    html = requests.get(url, timeout=20, headers=H).text
                    for p in IMG_RE.findall(html):
                        u = _abs(p)
                        if u not in gallery:
                            gallery.append(u)
                except requests.RequestException:
                    pass
            gallery = gallery[: o["gallery"]]
            corps = (f"Actualité officielle One Piece Card Game (catégorie {catcode}).\n"
                     f"Titre : {title}\n{desc}\n\n"
                     f"Angle Yonkko : vulgariser pour les collectionneurs FR — ce que ça change, "
                     f"dates, produits/cartes concernés, à retenir. Source : site officiel.")
            defaults = dict(
                expediteur="One Piece Card Game (officiel)", sujet=title[:500],
                recu_le=now(), categorie=slug, resume=desc[:500], corps=corps,
                blog_cible=blog, statut="nouveau",
                liens_sources=[{"url": url, "texte": "Site officiel", "kind": "source"}],
                image_url=cover, images=gallery, image_alt=title[:300],
            )
            obj, isnew = PressItem.objects.get_or_create(message_id=mid, defaults=defaults)
            if isnew:
                created += 1
            else:
                # rafraîchit images + rattachement si déjà présent (sans écraser le brouillon)
                obj.image_url = cover or obj.image_url
                if gallery:
                    obj.images = gallery
                obj.blog_cible = blog
                obj.categorie = slug
                obj.save(update_fields=["image_url", "images", "blog_cible", "categorie"])
                updated += 1
        self.stdout.write(self.style.SUCCESS(
            f"OPCG officiel : {created} créés, {updated} mis à jour (avec photos officielles)."))
