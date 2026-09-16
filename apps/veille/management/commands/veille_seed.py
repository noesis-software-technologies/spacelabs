"""Crée la constellation de blogs : 13-atmosphere.com (principal) + un blog par catégorie."""
from django.core.management.base import BaseCommand

from apps.veille.models import Blog, CATEGORIES


class Command(BaseCommand):
    help = "Initialise les blogs (principal + un par catégorie)"

    def handle(self, *args, **options):
        principal, _ = Blog.objects.update_or_create(
            categorie="",
            defaults=dict(nom="13 Atmosphère", domaine="13-atmosphere.com",
                          is_principal=True, statut="actif"),
        )
        self.stdout.write(self.style.SUCCESS(f"Principal: {principal}"))
        for slug, label in CATEGORIES:
            if slug == "autre":
                continue
            b, created = Blog.objects.get_or_create(
                categorie=slug,
                defaults=dict(nom=f"13 Atmosphère — {label}", domaine="",
                              is_principal=False, statut="a_ouvrir"),
            )
            self.stdout.write(("  + " if created else "  = ") + str(b))
        self.stdout.write(self.style.SUCCESS("Blogs OK"))
