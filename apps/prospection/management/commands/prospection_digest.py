"""Digest commercial quotidien — texte concis prêt à pousser sur Telegram.

Reprend le cockpit : prospects les plus chauds, relances dues, à clôturer,
+ rappel blogs (brouillons à pousser). Sortie stdout (récupérée par le cron).
"""
import datetime as _dt

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from apps.prospection.models import STATUTS_ACTIFS, Opportunity


class Command(BaseCommand):
    help = "Imprime le digest commercial du jour (pour push Telegram)."

    def add_arguments(self, parser):
        parser.add_argument("--top", type=int, default=5)

    def handle(self, *args, **o):
        today = timezone.localdate()
        ouverts = Opportunity.objects.filter(etat="ouvert")
        chauds = list(ouverts.filter(stage__in=["detecte", "qualifie"], score__gte=70)
                      .order_by("-score", "-budget_eur")[:o["top"]])
        relances = list(Opportunity.objects.filter(
            stage="offre_envoyee", date_offre__lte=today - _dt.timedelta(days=3),
            date_offre__gte=today - _dt.timedelta(days=10)).order_by("date_offre")[:o["top"]])
        a_cloturer = Opportunity.objects.filter(
            stage="offre_envoyee", date_offre__lt=today - _dt.timedelta(days=10)).count()
        pipe = ouverts.filter(stage__in=STATUTS_ACTIFS).aggregate(s=Sum("budget_eur"))["s"] or 0
        nb_chauds = ouverts.filter(stage__in=["detecte", "qualifie"], score__gte=70).count()

        L = [f"🎯 Digest commercial — {today:%d/%m}",
             f"🔥 {nb_chauds} prospects chauds · ↩️ {len(relances)} relances · 💰 pipeline {pipe} €", ""]
        if chauds:
            L.append("🔥 À contacter en priorité (offre <2h) :")
            for it in chauds:
                L.append(f"  • [{it.score}] {it.titre[:60]} — {it.budget_eur} €")
        if relances:
            L.append("\n↩️ Relances dues :")
            for it in relances:
                L.append(f"  • {it.titre[:60]} (offre {it.date_offre:%d/%m})")
        if a_cloturer:
            L.append(f"\n🚫 {a_cloturer} offre(s) à passer en « Sans réponse » (>J+10)")

        # Blogs
        try:
            from apps.veille.models import Blog, PressItem
            lignes = []
            for b in Blog.objects.all():
                prets = PressItem.objects.filter(
                    blog_cible=b, draft_statut__in=["brouillon", "valide"]
                ).exclude(mcp_status="published").count()
                if prets:
                    lignes.append(f"  • {b.nom} : {prets} brouillon(s) à valider/pousser")
            if lignes:
                L.append("\n🖼️ Blogs à ne pas oublier :")
                L.extend(lignes)
        except Exception:  # noqa: BLE001
            pass

        self.stdout.write("\n".join(L))
