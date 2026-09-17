"""Pré-rédige des articles dans la plume de Thérèse (via le `claude` local).

Exemples :
  python manage.py veille_draft --dry-run                 # montre le prompt, n'appelle pas claude
  python manage.py veille_draft --limit 1                 # génère 1 brouillon (test)
  python manage.py veille_draft --categorie food          # toute une catégorie
  python manage.py veille_draft --only-empty              # seulement ceux sans brouillon (défaut)
  python manage.py veille_draft --regenerate --limit 5    # régénère par-dessus l'existant
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.utils.timezone import now

from apps.veille.models import PressItem
from apps.veille.redaction import build_prompt, generer_draft


class Command(BaseCommand):
    help = "Génère des brouillons d'articles humanisés (plume de Thérèse) pour les communiqués."

    def add_arguments(self, parser):
        parser.add_argument("--categorie", help="Limiter à une catégorie (slug).")
        parser.add_argument("--limit", type=int, default=0, help="Nombre max d'items (0 = tous).")
        parser.add_argument("--only-empty", action="store_true", default=True,
                            help="Seulement les items sans brouillon (défaut).")
        parser.add_argument("--regenerate", action="store_true",
                            help="Régénère même si un brouillon existe déjà.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Affiche le prompt du 1er item sans appeler claude.")
        parser.add_argument("--allow-empty", action="store_true",
                            help="Rédige même les communiqués sans corps (défaut : ignorés).")
        parser.add_argument("--timeout", type=int, default=180)

    def handle(self, *args, **o):
        qs = PressItem.objects.all().order_by("-recu_le", "-id")
        if o["categorie"]:
            qs = qs.filter(categorie=o["categorie"])
        if not o["regenerate"]:
            qs = qs.exclude(draft_statut__in=["brouillon", "valide", "publie"])
        if not o["allow_empty"]:
            qs = qs.exclude(corps="")
        if o["limit"]:
            qs = qs[: o["limit"]]

        items = list(qs)
        if not items:
            self.stdout.write(self.style.WARNING("Aucun communiqué à rédiger (filtre appliqué)."))
            return

        if o["dry_run"]:
            it = items[0]
            self.stdout.write(self.style.NOTICE(f"[DRY-RUN] Prompt pour : [{it.categorie}] {it.sujet[:70]}\n"))
            self.stdout.write(build_prompt(it.sujet, it.corps, it.categorie))
            self.stdout.write(self.style.WARNING(f"\n({len(items)} item(s) seraient traités)"))
            return

        ok = fail = 0
        tot_cost = tot_in = tot_out = 0
        for it in items:
            self.stdout.write(f"→ [{it.categorie}] {it.sujet[:60]} … ", ending="")
            self.stdout.flush()
            draft, meta = generer_draft(it.sujet, it.corps, it.categorie, timeout=o["timeout"])
            tot_cost += meta.get("cost_usd", 0.0)
            tot_in += meta.get("input_tokens", 0)
            tot_out += meta.get("output_tokens", 0)
            if not draft:
                fail += 1
                self.stdout.write(self.style.ERROR("échec (claude indispo / sortie non parsable)"))
                continue
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
            it.save(update_fields=["draft_titre", "draft_chapo", "draft_corps",
                                   "seo_title", "meta_description", "tags", "image_alt",
                                   "slug", "draft_statut", "draft_genere_le"])
            ok += 1
            self.stdout.write(self.style.SUCCESS(f"OK « {draft['titre'][:50]} »"))

        self.stdout.write(self.style.SUCCESS(f"\nTerminé : {ok} brouillon(s), {fail} échec(s)."))
        self.stdout.write(self.style.NOTICE(
            f"Usage claude — coût cumulé ~${tot_cost:.4f} · "
            f"{tot_in} tokens in · {tot_out} tokens out "
            f"(abonnement Claude Code, pas de facturation API au token)."))
