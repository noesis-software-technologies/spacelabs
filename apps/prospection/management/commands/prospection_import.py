"""Importe les opportunités scrapées (Codeur.com) dans le CRM Prospection.

Usage :
  python manage.py prospection_import                       # CSV par défaut
  python manage.py prospection_import --csv /chemin/x.csv
Dédup par URL projet (ext_url). Met à jour le budget/description si déjà présent,
sans écraser les champs CRM (stage, owner, notes).
"""
import csv
import re
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.prospection.models import Opportunity
from apps.prospection.scoring import compute_score

DEFAULT_CSV = "/home/noesis/.openclaw/workspace/codeur_prospects_FINAL.csv"
TRUE = {"true", "1", "oui", "yes", "vérifié", "verifie"}


def _int_eur(s):
    digits = re.sub(r"[^\d]", "", (s or "").split("-")[0])
    return int(digits) if digits else 0


def _codeur_id(url):
    m = re.search(r"/projects/(\d+)", url or "")
    return m.group(1) if m else ""


def _is_tjm(s):
    return "/jour" in (s or "").lower() or "jour" in (s or "").lower() and "€" in (s or "")


def _skills(s):
    parts = re.split(r"[;,/]", s or "")
    return [p.strip() for p in parts if p.strip()][:15]


class Command(BaseCommand):
    help = "Importe les prospects Codeur.com (CSV) dans le pipeline CRM."

    def add_arguments(self, parser):
        parser.add_argument("--csv", default=DEFAULT_CSV)

    def handle(self, *args, **o):
        path = Path(o["csv"])
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"CSV introuvable : {path}"))
            return
        created = updated = 0
        with path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                url = (row.get("project_url") or "").strip()
                if not url:
                    continue
                desc = row.get("description") or ""
                defaults = {
                    "source": "codeur",
                    "codeur_id": _codeur_id(url),
                    "titre": (row.get("title") or "")[:400],
                    "budget_texte": (row.get("budget") or "")[:120],
                    "budget_eur": _int_eur(row.get("budget")),
                    "tjm": _is_tjm(row.get("budget")),
                    "description": desc,
                    "resume_besoin": re.sub(r"\s+", " ", desc).strip()[:400],
                    "categorie": (row.get("category") or "")[:120],
                    "competences": _skills(row.get("skills_sought")),
                    "publie_le": (row.get("published_at") or "")[:80],
                    "deadline_jours": (row.get("deadline_days") or "")[:40],
                    "vues": (row.get("views") or "")[:40],
                    "offres_existantes": (row.get("existing_offers") or "")[:40],
                    "client_nom": (row.get("client_name") or "")[:200],
                    "client_societe": (row.get("client_company") or "")[:200],
                    "client_localisation": (row.get("client_location") or "")[:200],
                    "client_site": (row.get("client_website") or "")[:300],
                    "client_url": (row.get("client_profile_url") or "")[:600],
                    "contact_tel": (row.get("phone") or row.get("profile_phone") or "")[:60],
                    "contact_email": (row.get("email") or row.get("profile_email") or "")[:200],
                    "email_verifie": (row.get("email_verified") or "").strip().lower() in TRUE,
                }
                obj, is_new = Opportunity.objects.get_or_create(ext_url=url, defaults=defaults)
                if is_new:
                    created += 1
                else:
                    # MAJ des champs sourcés sans toucher au CRM (stage/owner/notes)
                    for k in ("codeur_id", "titre", "budget_texte", "budget_eur", "tjm",
                              "description", "resume_besoin", "categorie", "competences",
                              "contact_tel", "contact_email"):
                        setattr(obj, k, defaults[k])
                    updated += 1
                # Score auto (barème cahier des charges)
                obj.score = compute_score(obj)
                obj.save()
        self.stdout.write(self.style.SUCCESS(
            f"Import terminé : {created} nouvelles opportunités, {updated} mises à jour "
            f"(total {Opportunity.objects.count()})."))
