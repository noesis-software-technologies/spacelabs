"""Dédoublonnage des PressItem.

Regroupe par (blog_cible, sujet normalisé) et ne garde qu'UN item par groupe :
le « meilleur » selon une priorité qui fait primer le publié sur le brouillon.

Par défaut : DRY-RUN (n'affiche que ce qui serait supprimé). `--apply` supprime.
"""
import re
import unicodedata
from collections import defaultdict

from django.core.management.base import BaseCommand
from apps.veille.models import PressItem


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"\s+", " ", s)
    # on retire le suffixe de scrape « a ete mis a jour » pour rapprocher les variantes
    s = re.sub(r"\s*a ete mis a jour\.?$", "", s)
    return s


def _rank(it: PressItem):
    """Clé de tri : plus grand = à GARDER. Le publié prime toujours."""
    return (
        it.mcp_status == "published",      # 1. validé côté blog
        it.statut == "publie",             # 2. publié localement
        bool(it.mcp_article_id),           # 3. déjà poussé (draft)
        it.draft_statut in ("valide", "publie"),
        len(it.cover_url or ""),           # 4. a une cover
        len(it.galerie or []),             # 5. galerie fournie
        len(it.draft_corps or ""),         # 6. rédaction la plus complète
        it.id,                             # 7. le plus récent
    )


class Command(BaseCommand):
    help = "Dédoublonne les PressItem (le publié prime). DRY-RUN par défaut."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Supprime réellement (sinon dry-run)")
        parser.add_argument("--bloc", default="", help="Limiter à un bloc éditorial (ex: Yonkko)")
        parser.add_argument("--with-date", action="store_true",
                            help="Clé = sujet + publier_le (au lieu du sujet seul)")

    def handle(self, *args, **o):
        qs = PressItem.objects.all()
        if o["bloc"]:
            qs = qs.filter(blog_cible__bloc=o["bloc"])
        groups = defaultdict(list)
        for it in qs:
            key = (it.blog_cible_id, _norm(it.sujet))
            if o["with_date"]:
                key = key + (it.publier_le.isoformat() if it.publier_le else "",)
            groups[key].append(it)

        to_delete, kept = [], 0
        for key, items in groups.items():
            if len(items) < 2:
                continue
            items.sort(key=_rank, reverse=True)
            keep, losers = items[0], items[1:]
            kept += 1
            self.stdout.write(self.style.SUCCESS(
                f"GARDE #{keep.id} [{keep.mcp_status or '—'}] {keep.sujet[:60]}"))
            for l in losers:
                self.stdout.write(f"   supprime #{l.id} [{l.mcp_status or '—'}] "
                                  f"pushed={bool(l.mcp_article_id)}")
                to_delete.append(l)

        self.stdout.write("")
        self.stdout.write(f"{kept} groupes dupliqués · {len(to_delete)} items à supprimer")
        # garde-fou : on ne supprime jamais un item déjà validé/publié côté blog
        protected = [l for l in to_delete if l.mcp_status == "published"]
        if protected:
            self.stdout.write(self.style.WARNING(
                f"{len(protected)} items publiés seraient touchés → exclus de la suppression"))
            to_delete = [l for l in to_delete if l.mcp_status != "published"]

        if o["apply"]:
            ids = [l.id for l in to_delete]
            PressItem.objects.filter(id__in=ids).delete()
            self.stdout.write(self.style.SUCCESS(f"✓ {len(ids)} items supprimés"))
        else:
            self.stdout.write(self.style.NOTICE("DRY-RUN — rien supprimé. Relance avec --apply pour appliquer."))
