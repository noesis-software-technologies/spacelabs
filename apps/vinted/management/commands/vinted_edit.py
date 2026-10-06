"""
Édite une annonce Vinted déjà publiée via CDP (Playwright).
Usage : CDP_URL=http://127.0.0.1:9222 manage.py vinted_edit <ref> [--field colis|etat|prix|titre] [--dry-run]
Sans --field spécifié : réapplique tous les champs du listing (marque, état, colis, prix).
"""
import os
import re
import time

from django.core.management.base import BaseCommand, CommandError

from apps.vinted.models import VintedListing
from apps.vinted.management.commands.vinted_publish import (
    CDP_URL, COLIS_LABELS, ETAT_LABELS, clean_title, clean_desc, hpause,
)


class Command(BaseCommand):
    help = "Édite une annonce Vinted existante via CDP."

    def add_arguments(self, parser):
        parser.add_argument("id", help="ref (hex) ou pk de l'annonce")
        parser.add_argument("--cdp", default=CDP_URL)
        parser.add_argument("--dry-run", action="store_true",
                            help="Ouvre la page d'édition sans sauvegarder")
        parser.add_argument("--field", nargs="*",
                            help="Champs à corriger : colis etat marque prix titre desc (tous par défaut)")

    def _listing(self, key):
        return (VintedListing.objects.filter(ref=key).first()
                or (VintedListing.objects.filter(pk=key).first() if str(key).isdigit() else None))

    def handle(self, *args, **o):
        it = self._listing(o["id"])
        if not it:
            raise CommandError(f"Annonce introuvable : {o['id']}")
        if not it.vinted_url:
            raise CommandError(
                f"Annonce #{it.pk} n'a pas d'URL Vinted enregistrée. "
                "Publie d'abord avec vinted_publish pour capturer l'URL."
            )

        fields = set(o.get("field") or ["colis", "etat", "marque", "prix", "titre", "desc"])
        etat = ETAT_LABELS.get(it.etat, "")
        colis = COLIS_LABELS.get((it.format_colis or "").strip().lower(), "Petit")
        marque = (it.marque or "").strip()
        title = clean_title(it.titre)
        desc = clean_desc(it.description)

        # Construire l'URL d'édition : /items/<id>/edit
        item_url = it.vinted_url.rstrip("/")
        if not re.search(r"/items/\d+", item_url):
            raise CommandError(
                f"URL Vinted invalide pour édition : {item_url!r}\n"
                "Elle doit contenir /items/<id>."
            )
        item_id = re.search(r"/items/(\d+)", item_url).group(1)
        edit_url = f"https://www.vinted.fr/items/{item_id}/edit"

        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(o["cdp"])
            ctx = browser.contexts[0]
            page = ctx.new_page()
            page.goto(edit_url, wait_until="domcontentloaded")
            if "login" in page.url or "register" in page.url:
                raise CommandError("CDP non connecté à Vinted (redirigé login).")

            self.stdout.write(f"Edition : {edit_url}")

            if "titre" in fields:
                try:
                    page.get_by_role("textbox", name="Titre").fill(title); hpause()
                    self.stdout.write(f"titre : {title}")
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"titre : {e}"))

            if "desc" in fields:
                try:
                    page.get_by_role("textbox", name="Description").fill(desc); hpause()
                    self.stdout.write("desc : ok")
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"desc : {e}"))

            if "prix" in fields:
                try:
                    page.get_by_role("textbox", name="Prix").fill(
                        str(int(it.prix) if it.prix == int(it.prix) else it.prix)); hpause()
                    self.stdout.write(f"prix : {it.prix}")
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"prix : {e}"))

            if "etat" in fields and etat:
                try:
                    page.get_by_role("textbox", name="État").click(); hpause()
                    page.get_by_text(etat, exact=True).first.click(timeout=4000); hpause()
                    self.stdout.write(f"état : {etat}")
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"état : {e}"))

            if "marque" in fields and marque:
                try:
                    page.eval_on_selector("#brand", "el => el.scrollIntoView({block:'center'})")
                    hpause()
                    page.eval_on_selector("#brand", "el => el.click()")
                    time.sleep(0.8)
                    for inp in page.locator("input:not([readonly])").all():
                        try:
                            if inp.is_visible() and not inp.evaluate("e => !!e.closest('.js-header')"):
                                inp.fill(marque); break
                        except Exception:
                            continue
                    time.sleep(1.2)
                    page.get_by_text(marque, exact=True).first.click(timeout=4000)
                    time.sleep(0.5)
                    self.stdout.write(f"marque : {marque}")
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"marque : {e}"))

            if "colis" in fields:
                colis_clicked = False
                for colis_label in (f"{colis} colis", colis):
                    if colis_clicked:
                        break
                    for attempt in (
                        lambda l=colis_label: page.get_by_label(l, exact=False).first.click(timeout=3000),
                        lambda l=colis_label: page.get_by_role("button", name=re.compile(
                            rf"^{re.escape(l)}", re.I)).first.click(timeout=3000),
                        lambda l=colis_label: page.get_by_role("radio", name=re.compile(
                            rf"{re.escape(l)}", re.I)).check(timeout=3000),
                        lambda l=colis_label: page.locator(f"text={l}").first.click(timeout=3000),
                    ):
                        try:
                            attempt(); hpause(); colis_clicked = True; break
                        except Exception:
                            pass
                if colis_clicked:
                    self.stdout.write(f"colis : {colis}")
                else:
                    self.stdout.write(self.style.WARNING(f"colis « {colis} » non coché"))

            shot = f"/tmp/vinted_edit_{it.ref}.png"
            page.screenshot(path=shot)
            self.stdout.write(f"screenshot : {shot}")

            if not o["dry_run"]:
                try:
                    save = page.locator("[data-testid='upload-form-save-button']")
                    save.scroll_into_view_if_needed(); hpause()
                    save.click(timeout=6000)
                    page.wait_for_timeout(2000)
                    self.stdout.write(self.style.SUCCESS(f"✓ édition sauvegardée : {it.vinted_url}"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"sauvegarde échouée : {e}"))
            else:
                self.stdout.write(self.style.NOTICE("dry-run : formulaire non sauvegardé"))
