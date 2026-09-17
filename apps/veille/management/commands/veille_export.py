"""Exporte les articles prêts en JSON autonome — à pousser vers le MCP du blog.

Chaque fichier contient tout le nécessaire pour publier : titre optimisé, slug,
meta description, tags, image de référence (locale si téléchargée), galerie,
corps, et liens internes (inter-maillage). Un index.json récapitule le lot.

  python manage.py veille_export                       # articles validés
  python manage.py veille_export --status brouillon,valide --out exports/veille
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.veille.models import PressItem


def _payload(it):
    ref = (it.images_local[0] if it.images_local else "") or it.image_ref
    galerie = it.images_local or it.carrousel
    return {
        "id": it.pk,
        "categorie": it.categorie,
        "categorie_label": it.get_categorie_display(),
        "blog": it.blog_cible.nom if it.blog_cible else "",
        "blog_domaine": it.blog_cible.domaine if it.blog_cible else "",
        "titre": it.draft_titre or it.sujet,
        "seo_title": it.seo_title,
        "slug": it.slug or slugify(it.draft_titre or it.sujet)[:300],
        "meta_description": it.meta_description,
        "tags": it.tags or [],
        "chapo": it.draft_chapo,
        "corps": it.draft_corps,
        "image_ref": ref,
        "image_alt": it.image_alt,
        "galerie": galerie,
        "liens_internes": it.liens_internes or [],
        "liens_sources": it.liens_sources or [],
        "publier_le": it.publier_le.isoformat() if it.publier_le else None,
        "statut": it.draft_statut,
    }


class Command(BaseCommand):
    help = "Exporte les articles en JSON (prêt pour publication via MCP)."

    def add_arguments(self, parser):
        parser.add_argument("--status", default="valide",
                            help="Statuts de brouillon à exporter (défaut : valide).")
        parser.add_argument("--categorie")
        parser.add_argument("--out", default="exports/veille", help="Dossier de sortie.")

    def handle(self, *args, **o):
        statuses = [s.strip() for s in o["status"].split(",") if s.strip()]
        qs = PressItem.objects.filter(draft_statut__in=statuses)
        if o["categorie"]:
            qs = qs.filter(categorie=o["categorie"])
        items = list(qs.order_by("publier_le", "categorie", "id"))
        if not items:
            self.stdout.write(self.style.WARNING("Aucun article à exporter pour ce filtre."))
            return

        out = Path(settings.BASE_DIR) / o["out"]
        out.mkdir(parents=True, exist_ok=True)
        index = []
        for it in items:
            p = _payload(it)
            fname = f"{it.pk:04d}-{p['slug'][:60] or 'article'}.json"
            (out / fname).write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
            index.append({"id": it.pk, "fichier": fname, "titre": p["titre"],
                          "categorie": it.categorie, "publier_le": p["publier_le"]})
        (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(
            f"{len(items)} article(s) exporté(s) dans {out}/ (+ index.json)."))
