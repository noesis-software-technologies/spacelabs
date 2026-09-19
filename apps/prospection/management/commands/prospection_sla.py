"""Balayage SLA quotidien : génère les étapes par défaut manquantes et applique
les transitions automatiques (offre > J+10 sans réponse). Idempotent.

Usage : python manage.py prospection_sla [--auto-cloture]
"""
import datetime as _dt

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.prospection.models import Activity, Opportunity, SalesStep
from apps.prospection.sales_ai import default_steps


class Command(BaseCommand):
    help = "Génère les étapes SLA manquantes + transitions automatiques."

    def add_arguments(self, parser):
        parser.add_argument("--auto-cloture", action="store_true",
                            help="Passe les offres > J+10 en « Sans réponse ».")

    def handle(self, *args, **o):
        today = timezone.localdate()
        steps_crees = 0
        # 1) Étapes SLA manquantes pour les opportunités actives.
        for op in Opportunity.objects.filter(
                stage__in=["detecte", "qualifie", "offre_envoyee", "opportunite_future"]):
            existing = set(op.etapes.values_list("libelle", flat=True))
            for s in default_steps(op):
                if s["libelle"] not in existing:
                    SalesStep.objects.create(opportunity=op, auto=True, **s)
                    steps_crees += 1
        # 2) Transition auto : offre > J+10 → sans réponse.
        cloture = 0
        if o["auto_cloture"]:
            for op in Opportunity.objects.filter(
                    stage="offre_envoyee", date_offre__lt=today - _dt.timedelta(days=10)):
                op.stage = "sans_reponse"
                op.save(update_fields=["stage", "maj_le"])
                Activity.objects.create(opportunity=op, texte="Auto : passage en Sans réponse (>J+10)",
                                        ancien_stage="offre_envoyee", nouveau_stage="sans_reponse")
                cloture += 1
        self.stdout.write(self.style.SUCCESS(
            f"SLA : {steps_crees} étape(s) générée(s), {cloture} offre(s) clôturée(s)."))
