"""Calcule l'inter-maillage : pour chaque article, les articles liés les plus proches.

Score = catégorie commune (fort) + tags/mots-clés partagés. Stocké dans
`liens_internes` = [{pk, titre, slug}] pour alimenter les liens internes à la
publication (bon pour le SEO et la navigation).

  python manage.py veille_link                 # tous les articles rédigés
  python manage.py veille_link --top 4
"""
import re

from django.core.management.base import BaseCommand

from apps.veille.models import PressItem

STOP = set("de la le les des un une du et à au aux en pour par sur dans avec sans "
           "the of and a an to in for with new nos notre nouvelle nouveau collection".split())


def _keywords(it):
    base = f"{it.draft_titre} {it.sujet} {' '.join(it.tags or [])}".lower()
    words = re.findall(r"[a-zàâäéèêëîïôöùûüç0-9]{4,}", base)
    return {w for w in words if w not in STOP}


class Command(BaseCommand):
    help = "Calcule les liens internes (inter-maillage) entre articles."

    def add_arguments(self, parser):
        parser.add_argument("--top", type=int, default=4, help="Nombre de liens par article.")
        parser.add_argument("--all", action="store_true",
                            help="Tous les communiqués (défaut : seulement ceux avec brouillon).")

    def handle(self, *args, **o):
        qs = PressItem.objects.all()
        if not o["all"]:
            qs = qs.filter(draft_statut__in=["brouillon", "valide", "publie"])
        items = list(qs)
        kw = {it.pk: _keywords(it) for it in items}

        n_links = 0
        for it in items:
            scored = []
            for other in items:
                if other.pk == it.pk:
                    continue
                score = len(kw[it.pk] & kw[other.pk])
                if other.categorie == it.categorie:
                    score += 3
                if score > 0:
                    scored.append((score, other))
            scored.sort(key=lambda x: (-x[0], -(x[1].recu_le.timestamp() if x[1].recu_le else 0)))
            liens = [{"pk": o2.pk, "titre": (o2.draft_titre or o2.sujet)[:120], "slug": o2.slug}
                     for _, o2 in scored[: o["top"]]]
            it.liens_internes = liens
            it.save(update_fields=["liens_internes"])
            n_links += len(liens)
            self.stdout.write(f"[{it.categorie}] {(it.draft_titre or it.sujet)[:48]} → {len(liens)} lien(s)")
        self.stdout.write(self.style.SUCCESS(f"\nInter-maillage : {n_links} lien(s) sur {len(items)} article(s)."))
