"""Ingestion RSS codeur.com → opportunités « Détecté » (fraîcheur = avantage n°1).

Crée une ligne par annonce du flux, dédup par id projet (guid). Parse le budget
et les catégories depuis la description. Annonce > 7 jours = « remontée » → rejetée
d'office (porte 2 du cahier des charges). Le reste passe en « Détecté ».

Usage :
  python manage.py prospection_rss                    # flux live
  python manage.py prospection_rss --file export.xml  # export fourni (secours)
  python manage.py prospection_rss --url "https://www.codeur.com/projects?format=rss&states[]=published"
"""
import datetime as _dt
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.prospection.models import Opportunity
from apps.prospection.scoring import compute_score

RSS_URL = "https://www.codeur.com/projects?format=rss"
TAG_RE = re.compile(r"<[^>]+>")
# Libellés budget → € médian de tranche (cahier des charges § mapping).
BUDGET_MAP = {
    "moins de 500": 250, "500 € à 1 000": 750, "1 000 € à 10 000": 4500,
    "10 000 € et plus": 15000, "demande de devis": 0,
}


def _clean(s):
    return TAG_RE.sub(" ", s or "").replace("\xa0", " ").strip()


def _parse_desc(desc):
    """Retourne (budget_texte, budget_eur, tjm, categories[list], extrait)."""
    txt = _clean(desc)
    budget_texte, cats, extrait = "", [], txt
    m = re.search(r"Budget\s*:\s*(.+?)\s*-\s*Cat[ée]gories\s*:\s*(.+)", txt)
    if m:
        budget_texte = m.group(1).strip()
        rest = m.group(2).strip()
        # les catégories sont en tête, séparées par des virgules ; l'extrait suit
        cats = [c.strip() for c in re.split(r",", rest)][:6]
        cats = [c for c in cats if c]
    low = budget_texte.lower()
    tjm = "/jour" in low or ("jour" in low and "€" in low)
    eur = 0
    for key, val in BUDGET_MAP.items():
        if key in low:
            eur = val
            break
    if not eur:
        digits = re.sub(r"[^\d]", "", budget_texte.split("-")[0])
        eur = int(digits) if digits else 0
    return budget_texte, eur, tjm, cats, extrait


class Command(BaseCommand):
    help = "Ingestion du flux RSS codeur.com dans le CRM (statut Détecté)."

    def add_arguments(self, parser):
        parser.add_argument("--url", default=RSS_URL)
        parser.add_argument("--file", default="")

    def handle(self, *args, **o):
        if o["file"]:
            raw = Path(o["file"]).read_bytes()
        else:
            try:
                r = requests.get(o["url"], timeout=25, headers={"User-Agent": "Mozilla/5.0"})
                r.raise_for_status()
                raw = r.content
            except requests.RequestException as e:
                self.stderr.write(self.style.ERROR(
                    f"Flux inaccessible ({e}). Fournis un export via --file."))
                return
        try:
            items = ET.fromstring(raw).findall(".//item")
        except ET.ParseError as e:
            self.stderr.write(self.style.ERROR(f"RSS illisible : {e}"))
            return

        now = timezone.now()
        created = rejete = skip = 0
        for it in items:
            link = (it.findtext("link") or "").strip()
            guid = (it.findtext("guid") or "").strip()
            cid = re.sub(r"[^\d]", "", guid) or (re.search(r"/projects/(\d+)", link) or [None, ""])[1]
            if not link or Opportunity.objects.filter(ext_url=link).exists() \
                    or (cid and Opportunity.objects.filter(codeur_id=cid).exists()):
                skip += 1
                continue
            titre = _clean(it.findtext("title"))[:400]
            btxt, eur, tjm, cats, extrait = _parse_desc(it.findtext("description"))
            pub = it.findtext("pubDate")
            pub_dt = None
            try:
                pub_dt = parsedate_to_datetime(pub) if pub else None
            except (TypeError, ValueError):
                pub_dt = None
            age_j = (now - pub_dt).days if pub_dt else None
            remontee = age_j is not None and age_j > 7

            op = Opportunity(
                source="codeur", codeur_id=cid, ext_url=link, titre=titre,
                budget_texte=btxt, budget_eur=eur, tjm=tjm,
                categorie=cats[0] if cats else "", competences=cats[1:] if len(cats) > 1 else [],
                description=extrait, resume_besoin=extrait[:400],
                publie_le=pub or "", publie_le_dt=pub_dt, date_detection=now,
                etat="ouvert", stage="rejete" if remontee else "detecte",
                motif_rejet="remontee" if remontee else "",
            )
            op.score = compute_score(op)
            op.save()
            created += 1
            rejete += 1 if remontee else 0
        self.stdout.write(self.style.SUCCESS(
            f"RSS codeur : {created} nouvelle(s) ligne(s) ({rejete} remontées→rejetées), "
            f"{skip} déjà connues. Total {Opportunity.objects.count()}."))
