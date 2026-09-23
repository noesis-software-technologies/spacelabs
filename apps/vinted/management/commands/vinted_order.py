"""Gestionnaire de commandes Vinted en CLI : suivi achat / vente / envoi.

Créer / mettre à jour une commande, ou lister le suivi (bénéfices, envois).

Exemples :
  # Enregistrer une vente (lie l'annonce via sa ref si fournie)
  python manage.py vinted_order --add --titre "Blaziken ex 016/175" \
      --achat 8 --vente 21 --acheteur ddorff --numero 123456 --listing 0666f9535a68

  # Mettre à jour un envoi
  python manage.py vinted_order --id 3 --statut expedie --transporteur Chronopost --tracking XY123 --expedie 2026-09-23

  # Lister (tout ou seulement ce qui reste à expédier)
  python manage.py vinted_order --list
  python manage.py vinted_order --list --a-expedier
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.vinted.models import (STATUTS_ENVOI, STATUTS_ENVOI_A_FAIRE,
                                VintedListing, VintedOrder)

_STATUTS = {k for k, _ in STATUTS_ENVOI}


def _d(s):
    if not s:
        return None
    y, m, d = (int(x) for x in s.split("-"))
    return date(y, m, d)


class Command(BaseCommand):
    help = "Crée / met à jour / liste les commandes Vinted (achat, vente, bénéfice, envoi)."

    def add_arguments(self, parser):
        parser.add_argument("--add", action="store_true", help="Créer une commande.")
        parser.add_argument("--id", type=int, help="Id de la commande à modifier.")
        parser.add_argument("--list", action="store_true", help="Lister les commandes.")
        parser.add_argument("--a-expedier", action="store_true",
                            help="Avec --list : seulement les envois à faire.")
        # Champs
        parser.add_argument("--titre")
        parser.add_argument("--numero")
        parser.add_argument("--acheteur")
        parser.add_argument("--listing", help="ref (hex) ou id d'un VintedListing à relier.")
        parser.add_argument("--achat", type=float)
        parser.add_argument("--vente", type=float)
        parser.add_argument("--frais", type=float)
        parser.add_argument("--statut", choices=sorted(_STATUTS))
        parser.add_argument("--transporteur")
        parser.add_argument("--tracking")
        parser.add_argument("--vendu", help="Date de vente AAAA-MM-JJ")
        parser.add_argument("--expedie", help="Date d'expédition AAAA-MM-JJ")
        parser.add_argument("--livre", help="Date de livraison AAAA-MM-JJ")
        parser.add_argument("--notes")

    def _resolve_listing(self, key):
        if not key:
            return None
        it = (VintedListing.objects.filter(ref=key).first()
              or (VintedListing.objects.filter(pk=key).first() if str(key).isdigit() else None))
        if not it:
            raise CommandError(f"VintedListing introuvable : {key}")
        return it

    def _apply(self, o, opts):
        m = {"titre": "titre", "numero": "numero", "acheteur": "acheteur",
             "statut": "statut_envoi", "transporteur": "transporteur", "tracking": "tracking",
             "notes": "notes"}
        for arg, field in m.items():
            if opts.get(arg) is not None:
                setattr(o, field, opts[arg])
        if opts.get("achat") is not None:
            o.prix_achat = opts["achat"]
        if opts.get("vente") is not None:
            o.prix_vente = opts["vente"]
        if opts.get("frais") is not None:
            o.frais = opts["frais"]
        if opts.get("listing"):
            o.listing = self._resolve_listing(opts["listing"])
            if not o.titre and o.listing:
                o.titre = o.listing.titre
        for arg, field in (("vendu", "date_vente"), ("expedie", "date_expedition"),
                           ("livre", "date_livraison")):
            if opts.get(arg):
                setattr(o, field, _d(opts[arg]))

    def handle(self, *args, **o):
        if o["list"]:
            qs = VintedOrder.objects.all()
            if o["a_expedier"]:
                qs = qs.filter(statut_envoi__in=STATUTS_ENVOI_A_FAIRE)
            total_benef = 0
            for c in qs:
                total_benef += c.benefice
                marge = "—" if c.marge_pct is None else f"{c.marge_pct}%"
                self.stdout.write(
                    f"#{c.pk:>4} [{c.get_statut_envoi_display():<16}] "
                    f"{(c.titre or c.numero or '?')[:38]:<38} "
                    f"achat {c.prix_achat or 0}€ / vente {c.prix_vente or 0}€ "
                    f"→ bénéf {c.benefice}€ ({marge})"
                    + (f" · {c.transporteur} {c.tracking}" if c.tracking else ""))
            self.stdout.write(self.style.SUCCESS(
                f"\n{qs.count()} commande(s) · bénéfice cumulé {total_benef} €"))
            return

        if o["add"]:
            order = VintedOrder()
            self._apply(order, o)
            order.save()
            self.stdout.write(self.style.SUCCESS(
                f"✓ commande #{order.pk} créée — bénéfice {order.benefice} €"))
            return

        if o["id"]:
            order = VintedOrder.objects.filter(pk=o["id"]).first()
            if not order:
                raise CommandError(f"Commande introuvable : #{o['id']}")
            self._apply(order, o)
            order.save()
            self.stdout.write(self.style.SUCCESS(
                f"✓ commande #{order.pk} mise à jour — {order.get_statut_envoi_display()} "
                f"· bénéfice {order.benefice} €"))
            return

        raise CommandError("Précise une action : --add, --id <n> (modif) ou --list.")
