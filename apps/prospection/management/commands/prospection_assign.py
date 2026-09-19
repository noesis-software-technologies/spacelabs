"""Assignation des opportunités aux commerciaux (rotation / garde).

- --to <username>  : assigne toutes les opportunités actionnables SANS owner à ce
  commercial de garde (le plus simple pour la garde du jour).
- --round-robin u1 u2 …  : répartit équitablement les opportunités sans owner
  entre plusieurs commerciaux (par score décroissant).

Ne touche jamais une opportunité déjà assignée.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.prospection.models import STATUTS_ACTIFS, Opportunity


class Command(BaseCommand):
    help = "Assigne les opportunités sans owner (garde ou round-robin)."

    def add_arguments(self, parser):
        parser.add_argument("--to", help="Username du commercial de garde")
        parser.add_argument("--round-robin", nargs="+", default=[], help="Usernames à répartir")
        parser.add_argument("--min-score", type=int, default=45)

    def handle(self, *args, **o):
        U = get_user_model()
        qs = (Opportunity.objects.filter(owner__isnull=True, stage__in=STATUTS_ACTIFS,
                                         score__gte=o["min_score"]).order_by("-score"))
        if o["to"]:
            user = U.objects.filter(username=o["to"]).first()
            if not user:
                raise CommandError(f"Utilisateur inconnu : {o['to']}")
            n = qs.update(owner=user)
            self.stdout.write(self.style.SUCCESS(f"{n} opportunité(s) assignée(s) à {user.username}."))
            return
        if o["round_robin"]:
            users = list(U.objects.filter(username__in=o["round_robin"]))
            if not users:
                raise CommandError("Aucun utilisateur valide.")
            n = 0
            for i, op in enumerate(qs):
                op.owner = users[i % len(users)]
                op.save(update_fields=["owner"])
                n += 1
            self.stdout.write(self.style.SUCCESS(
                f"{n} opportunité(s) réparties entre {', '.join(u.username for u in users)}."))
            return
        raise CommandError("Précise --to <username> ou --round-robin u1 u2 …")
