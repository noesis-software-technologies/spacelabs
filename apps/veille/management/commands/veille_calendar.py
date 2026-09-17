"""Planifie les dates de publication des brouillons (calendrier éditorial).

Répartit les articles prêts sur un rythme régulier (par défaut lun/mer/ven), à
partir d'une date de départ. À relancer « au fur et à mesure » que des brouillons
sont validés.

Exemples :
  python manage.py veille_calendar --dry-run
  python manage.py veille_calendar --per-week 3 --start 2026-09-22
  python manage.py veille_calendar --status valide --reset
"""
import datetime as dt

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.veille.models import PressItem

WEEKDAYS = {"lun": 0, "mar": 1, "mer": 2, "jeu": 3, "ven": 4, "sam": 5, "dim": 6}


class Command(BaseCommand):
    help = "Assigne des dates de publication (publier_le) aux brouillons prêts."

    def add_arguments(self, parser):
        parser.add_argument("--start", help="Date de départ YYYY-MM-DD (défaut : aujourd'hui).")
        parser.add_argument("--days", default="lun,mer,ven",
                            help="Jours de parution, ex. 'lun,mer,ven'.")
        parser.add_argument("--per-week", type=int, default=0,
                            help="Limite d'articles/semaine (0 = tous les jours choisis).")
        parser.add_argument("--status", default="brouillon,valide",
                            help="Statuts de brouillon éligibles (défaut brouillon,valide).")
        parser.add_argument("--categorie", help="Limiter à une catégorie.")
        parser.add_argument("--reset", action="store_true",
                            help="Replanifie aussi ceux qui ont déjà une date.")
        parser.add_argument("--dry-run", action="store_true")

    def _slots(self, start, weekdays, per_week):
        """Génère des dates successives sur les jours choisis, à l'infini."""
        day = start
        count_week, week_key = 0, start.isocalendar()[:2]
        while True:
            wk = day.isocalendar()[:2]
            if wk != week_key:
                week_key, count_week = wk, 0
            if day.weekday() in weekdays:
                if not per_week or count_week < per_week:
                    count_week += 1
                    yield day
            day += dt.timedelta(days=1)

    def handle(self, *args, **o):
        try:
            weekdays = {WEEKDAYS[d.strip()] for d in o["days"].split(",") if d.strip()}
        except KeyError as e:
            raise CommandError(f"Jour invalide : {e}. Utilise lun,mar,mer,jeu,ven,sam,dim.")
        if not weekdays:
            raise CommandError("Aucun jour de parution valide.")

        if o["start"]:
            start = dt.date.fromisoformat(o["start"])
        else:
            # Par défaut : lundi de la semaine PROCHAINE (visibilité + réédition manuelle).
            today = timezone.localdate()
            start = today + dt.timedelta(days=(7 - today.weekday()))
        statuses = [s.strip() for s in o["status"].split(",") if s.strip()]

        qs = PressItem.objects.filter(draft_statut__in=statuses)
        if o["categorie"]:
            qs = qs.filter(categorie=o["categorie"])
        if not o["reset"]:
            qs = qs.filter(publier_le__isnull=True)
        # Ordre : par catégorie puis chronologie de réception → cadence équilibrée
        items = list(qs.order_by("categorie", "recu_le", "id"))

        if not items:
            self.stdout.write(self.style.WARNING("Aucun brouillon éligible à planifier."))
            return

        slots = self._slots(start, weekdays, o["per_week"])
        plan = []
        for it in items:
            when = next(slots)
            plan.append((when, it))

        for when, it in plan:
            self.stdout.write(f"{when:%a %d/%m/%Y}  [{it.categorie:10}]  {(it.draft_titre or it.sujet)[:56]}")

        if o["dry_run"]:
            self.stdout.write(self.style.WARNING(f"\n[DRY-RUN] {len(plan)} article(s) — rien enregistré."))
            return

        for when, it in plan:
            it.publier_le = when
            it.save(update_fields=["publier_le"])
        self.stdout.write(self.style.SUCCESS(f"\nCalendrier enregistré : {len(plan)} article(s) planifié(s)."))
