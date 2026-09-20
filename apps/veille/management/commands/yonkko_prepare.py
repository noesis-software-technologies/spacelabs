"""Prépare le blog Yonkko façon Atmosphère : sous-blogs par sous-catégorie,
catégorisation et dispatch des sujets One Piece TCG vers le bon sous-blog.

Usage : python manage.py yonkko_prepare
"""
from django.core.management.base import BaseCommand

from apps.veille.models import Blog, PressItem
from apps.veille.yonkko import BLOC, SUBCATS, categorize


class Command(BaseCommand):
    help = "Crée les sous-blogs Yonkko + catégorise/dispatch les sujets One Piece TCG."

    def handle(self, *args, **o):
        principal = Blog.objects.filter(domaine="yonko.life").first()
        if not principal:
            self.stderr.write(self.style.ERROR("Blog Yonkko introuvable (lance veille_scrape_yonkko)."))
            return
        # 1) Sous-blogs (un par sous-catégorie), bloc Yonkko.
        sub = {}
        for slug, (label, *_rest) in SUBCATS.items():
            b, _ = Blog.objects.get_or_create(
                categorie=slug,
                defaults={"nom": f"Yonkko — {label}", "bloc": BLOC, "statut": "actif"})
            # garantir le rattachement au bloc + nom
            changed = False
            if b.bloc != BLOC:
                b.bloc = BLOC; changed = True
            if not b.nom.startswith("Yonkko"):
                b.nom = f"Yonkko — {label}"; changed = True
            if changed:
                b.save()
            sub[slug] = b
        # 2) Catégoriser + dispatcher les items du blog principal et sous-blogs Yonkko.
        blogs_yonkko = [principal] + list(sub.values())
        items = PressItem.objects.filter(blog_cible__in=blogs_yonkko)
        n = 0
        for it in items:
            slug = categorize(it.sujet, it.resume)  # résumé RSS propre (pas le gabarit)
            target = sub[slug]
            if it.categorie != slug or it.blog_cible_id != target.id:
                it.categorie = slug
                it.blog_cible = target
                it.save(update_fields=["categorie", "blog_cible"])
                n += 1
        # Répartition
        from collections import Counter
        rep = Counter(PressItem.objects.filter(blog_cible__in=list(sub.values()))
                      .values_list("categorie", flat=True))
        self.stdout.write(self.style.SUCCESS(
            f"Yonkko : {len(sub)} sous-blogs, {n} sujets (re)dispatché(s)."))
        for slug, (label, *_r) in SUBCATS.items():
            self.stdout.write(f"  · {label}: {rep.get(slug, 0)}")
