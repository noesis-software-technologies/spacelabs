"""Publie une annonce Vinted en pilotant Chrome via CDP (Playwright).

Réutilisable au quotidien : on garde un Chrome lancé avec le débogage distant
(`--remote-debugging-port=9222`), connecté au compte Vinted. La commande s'y
attache et remplit le formulaire `items/new` à partir d'un VintedListing.

Sécurité : par défaut on REMPLIT sans valider (screenshot pour contrôle).
Ajoute --publish pour cliquer « Ajouter » et mettre l'annonce en ligne.

Exemples :
  python manage.py vinted_publish 564693f959f5            # remplit + screenshot
  python manage.py vinted_publish 564693f959f5 --publish  # remplit + publie
  CDP_URL=http://172.22.32.1:9222 python manage.py vinted_publish 12 --publish
"""
import os
import random
import re
import time

from django.core.management.base import BaseCommand, CommandError
from apps.vinted.models import VintedListing


def hpause(a=0.25, b=0.6):
    """Micro-pause aléatoire : donne un rythme « humain » au remplissage tout en
    restant rapide (industrialisable). Ajuster via VINTED_SPEED (0.5 = 2x plus vif)."""
    k = float(os.environ.get("VINTED_SPEED", "1"))
    time.sleep(random.uniform(a, b) * k)

CDP_URL = os.environ.get("CDP_URL", "http://127.0.0.1:9222")
# Catégorie par défaut : on vend surtout de la carte à collectionner.
DEFAULT_CATEGORY_QUERY = os.environ.get("VINTED_CATEGORY", "Cartes à collectionner")
ETAT_LABELS = {
    "neuf_etiquette": "Neuf avec étiquette",
    "neuf_sans": "Neuf sans étiquette",
    "tres_bon": "Très bon état",
    "bon": "Bon état",
    "satisfaisant": "Satisfaisant",
}
COLIS_LABELS = {"s": "Petit", "petit": "Petit", "m": "Moyen", "moyen": "Moyen",
                "l": "Grand", "grand": "Grand"}


def clean_title(t: str) -> str:
    """Anti « sonne IA » : pas de tiret cadratin, pas de mots tout en capitales."""
    t = (t or "").replace("—", "-").replace("–", "-")
    t = re.sub(r"\s+-\s+", " - ", t)
    words = []
    for w in t.split(" "):
        # on laisse les sigles courts (<=3) et alphanumériques (BT12-038, SR, EN)
        if w.isupper() and len(re.sub(r"[^A-Za-zÀ-ÿ]", "", w)) > 3:
            w = w.capitalize()
        words.append(w)
    return " ".join(words).strip()


def clean_desc(d: str) -> str:
    d = (d or "").replace("—", "-").replace("–", "-").replace("•", "-")
    d = re.sub(r"\bGEM MINT\b", "Gem Mint", d)
    return d


class Command(BaseCommand):
    help = "Publie/rempli une annonce Vinted via CDP (Playwright)."

    def add_arguments(self, parser):
        parser.add_argument("id", help="ref (hex) ou id de l'annonce")
        parser.add_argument("--publish", action="store_true", help="clique « Ajouter » (met en ligne)")
        parser.add_argument("--category", default=DEFAULT_CATEGORY_QUERY)
        parser.add_argument("--cdp", default=CDP_URL)

    def _listing(self, key):
        return (VintedListing.objects.filter(ref=key).first()
                or (VintedListing.objects.filter(pk=key).first() if str(key).isdigit() else None))

    def handle(self, *args, **o):
        it = self._listing(o["id"])
        if not it:
            raise CommandError(f"Annonce introuvable : {o['id']}")
        title = clean_title(it.titre)
        desc = clean_desc(it.description)
        photos = [p for p in (it.images or []) if os.path.exists(p)]
        if not (title and desc and it.prix):
            raise CommandError("Titre / description / prix requis avant publication.")
        etat = ETAT_LABELS.get(it.etat, "")
        # Colis : Petit par défaut (cas quasi systématique pour une carte) sauf indication.
        colis = COLIS_LABELS.get((it.format_colis or "").strip().lower(), it.format_colis or "Petit")
        marque = (it.marque or os.environ.get("VINTED_MARQUE", "")).strip()

        from playwright.sync_api import sync_playwright
        published_url = None
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(o["cdp"])
            ctx = browser.contexts[0]
            page = ctx.new_page()
            page.goto("https://www.vinted.fr/items/new", wait_until="domcontentloaded")
            if "register" in page.url or "login" in page.url:
                raise CommandError("Chrome CDP n'est pas connecté à Vinted (redirigé login).")

            # 1) PHOTOS D'ABORD : Vinted reconnaît le produit et PRÉ-SÉLECTIONNE la
            # catégorie + sous-catégorie (ex. « Cartes à collectionner à l'unité »).
            # On gagne toute l'étape de recherche/sélection de catégorie.
            if photos:
                page.set_input_files("input[type=file]", photos)
                self.stdout.write(f"photos: {len(photos)}")
                # laisser l'auto-détection peupler les champs (catégorie, sous-catégorie)
                time.sleep(float(os.environ.get("VINTED_DETECT_WAIT", "2.5")))

            # Titre / description / prix
            page.get_by_role("textbox", name="Titre").fill(title); hpause()
            page.get_by_role("textbox", name="Description").fill(desc); hpause()
            page.get_by_role("textbox", name="Prix").fill(
                str(int(it.prix) if it.prix == int(it.prix) else it.prix)); hpause()

            # Catégorie : ne rien faire si déjà auto-détectée (cas nominal cartes).
            # Fallback seulement si le champ est resté vide.
            cat_set = False
            try:
                cur = (page.get_by_role("textbox", name="Catégorie").input_value() or "").strip()
                cat_set = bool(cur)
                if cat_set:
                    self.stdout.write(f"catégorie auto-détectée : {cur}")
            except Exception:  # noqa: BLE001
                pass
            if not cat_set:
                try:
                    page.get_by_role("textbox", name="Catégorie").click(); hpause()
                    page.keyboard.type(o["category"], delay=25)
                    time.sleep(1.0)
                    page.get_by_text(o["category"], exact=False).first.click(timeout=4000)
                except Exception as e:  # noqa: BLE001
                    self.stdout.write(self.style.WARNING(f"catégorie non auto-sélectionnée : {e}"))

            # Marque : le champ « Marque » est un display readonly (#brand) qui ouvre
            # un menu (recherche + suggestions radio). ATTENTION : viser par rôle
            # « textbox Marque » matche AUSSI la barre de recherche de l'entête et se
            # fait intercepter par son overlay. On clique donc #brand en JS, on tape
            # dans le vrai champ de recherche du menu, puis on clique l'option.
            if marque:
                try:
                    page.eval_on_selector("#brand", "el => el.scrollIntoView({block:'center'})")
                    hpause()
                    page.eval_on_selector("#brand", "el => el.click()")
                    time.sleep(0.8)
                    # champ de recherche du menu (exclut l'entête .js-header)
                    for inp in page.locator("input:not([readonly])").all():
                        try:
                            if inp.is_visible() and not inp.evaluate(
                                    "e => !!e.closest('.js-header')"):
                                inp.fill(marque); break
                        except Exception:  # noqa: BLE001
                            continue
                    time.sleep(1.2)
                    # option : 1re occurrence exacte du nom dans le menu ouvert
                    page.get_by_text(marque, exact=True).first.click(timeout=4000)
                    time.sleep(0.5)
                    val = (page.locator("#brand").input_value() or "").strip()
                    if val:
                        self.stdout.write(f"marque : {val}")
                    else:
                        self.stdout.write(self.style.WARNING("marque non confirmée (champ vide)"))
                except Exception as e:  # noqa: BLE001
                    self.stdout.write(self.style.WARNING(f"marque « {marque} » non sélectionnée : {e}"))

            # État
            if etat:
                try:
                    page.get_by_role("textbox", name="État").click(); hpause()
                    page.get_by_text(etat, exact=True).first.click(timeout=4000); hpause()
                except Exception as e:  # noqa: BLE001
                    self.stdout.write(self.style.WARNING(f"état non sélectionné : {e}"))
            # Colis : cliquer le bouton du format (plus fiable que la case radio, qui
            # ne se coche pas toujours quand Vinted recommande une autre taille - le
            # défaut bascule sur « Moyen » selon la catégorie, donc on force toujours).
            try:
                page.get_by_role("button", name=re.compile(rf"^{re.escape(colis)}\b")).first.click(timeout=4000)
                hpause()
            except Exception:  # noqa: BLE001
                try:
                    page.get_by_role("radio", name=re.compile(colis)).check(timeout=3000)
                except Exception:  # noqa: BLE001
                    self.stdout.write(self.style.WARNING(f"colis « {colis} » non coché (défaut conservé)"))

            shot = f"/tmp/vinted_{it.ref}.png"
            page.screenshot(path=shot)
            self.stdout.write(f"TITRE : {title}")
            self.stdout.write(f"screenshot : {shot}")

            if o["publish"]:
                # Un bandeau cookies peut recouvrir le bouton et intercepter le clic.
                for cta in ("Tout accepter", "Accepter tout"):
                    try:
                        btn = page.get_by_role("button", name=cta)
                        if btn.count():
                            btn.first.click(timeout=2500); hpause(); break
                    except Exception:  # noqa: BLE001
                        pass
                # Bouton « Ajouter » ciblé par data-testid (fiable).
                save = page.locator("[data-testid='upload-form-save-button']")
                save.scroll_into_view_if_needed(); hpause()
                save.click(timeout=6000)
                # Attendre de quitter le formulaire (redirection profil = en ligne).
                for _ in range(25):
                    page.wait_for_timeout(700)
                    if "items/new" not in page.url:
                        break
                # NE PAS appeler l'ORM Django ici : on est dans le contexte async de
                # Playwright (sync_playwright ouvre une boucle) -> SynchronousOnlyOperation.
                # On capture l'URL et on sauvegarde APRÈS le bloc `with`.
                published_url = page.url
                self.stdout.write(self.style.SUCCESS(f"✓ publié : {published_url}"))
            else:
                self.stdout.write(self.style.NOTICE("rempli sans valider (ajoute --publish pour mettre en ligne)"))

        # Sauvegarde ORM hors du contexte Playwright (évite SynchronousOnlyOperation).
        if o["publish"] and published_url:
            it.vinted_url = published_url
            it.statut = "publie"
            it.save(update_fields=["vinted_url", "statut"])
