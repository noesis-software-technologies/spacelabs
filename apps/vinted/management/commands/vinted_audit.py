"""Audit comptable Vinted : détecte et corrige les écarts entre les champs
agrégés d'une VintedOrder et la somme réelle de ses lignes.

Usage :
  python manage.py vinted_audit           # affiche les écarts
  python manage.py vinted_audit --fix     # corrige automatiquement
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.vinted.models import VintedOrder


class Command(BaseCommand):
    help = "Audit et recalcul des totaux VintedOrder (prix_vente, prix_achat)."

    def add_arguments(self, parser):
        parser.add_argument("--fix", action="store_true", help="Applique les corrections")

    def handle(self, *args, **o):
        fix = o["fix"]
        orders = VintedOrder.objects.prefetch_related("lignes__stock_item").all()
        ecarts = []

        for order in orders:
            lignes = list(order.lignes.all())
            if not lignes:
                continue

            pv_calc = sum((l.total_vente for l in lignes), Decimal("0"))
            pa_effectifs = [l.prix_achat_effectif for l in lignes]
            if all(pa is not None for pa in pa_effectifs):
                pa_calc = sum(
                    Decimal(str(pa)) * l.quantite
                    for pa, l in zip(pa_effectifs, lignes)
                )
            else:
                pa_calc = None

            pv_ok = order.prix_vente == pv_calc
            pa_ok = (pa_calc is None) or (order.prix_achat == pa_calc)

            if not pv_ok or not pa_ok:
                ecarts.append((order, pv_calc, pa_calc))
                self.stdout.write(
                    self.style.WARNING(
                        f"  Commande #{order.id} « {order.titre[:40]} »\n"
                        f"    PV  stocké={order.prix_vente}  calculé={pv_calc}"
                        f"  {'OK' if pv_ok else '⚠ ECART'}\n"
                        f"    PA  stocké={order.prix_achat}  calculé={pa_calc}"
                        f"  {'OK' if pa_ok else '⚠ ECART'}"
                    )
                )
                if fix:
                    order.recalculer_totaux()
                    self.stdout.write(self.style.SUCCESS(f"    → Corrigé."))

        if not ecarts:
            self.stdout.write(self.style.SUCCESS("Aucun écart détecté — tout est cohérent."))
        elif not fix:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{len(ecarts)} commande(s) avec écart. Relancez avec --fix pour corriger."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\n{len(ecarts)} commande(s) corrigée(s).")
            )
