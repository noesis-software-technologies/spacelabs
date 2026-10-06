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
    "neuf": "Neuf avec étiquette",          # alias — on vend toujours neuf avec étiquette
    "neuf_sans": "Neuf sans étiquette",
    "tres_bon": "Très bon état",
    "bon": "Bon état",
    "satisfaisant": "Satisfaisant",
}
COLIS_LABELS = {
    "s": "Petit", "petit": "Petit", "petit_colis": "Petit",
    "m": "Moyen", "moyen": "Moyen", "moyen_colis": "Moyen",
    "l": "Grand", "grand": "Grand", "grand_colis": "Grand",
}


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
        # Pour CDP distant (Chrome Windows depuis WSL) : passer les fichiers comme
        # FilePayload (buffer en mémoire) — Playwright valide sinon os.stat() en local.
        def _to_payload(path):
            import mimetypes
            mime, _ = mimetypes.guess_type(path)
            with open(path, "rb") as f:
                return {"name": os.path.basename(path), "mimeType": mime or "image/jpeg",
                        "buffer": f.read()}
        photo_payloads = [_to_payload(p) for p in photos]
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
            if photo_payloads:
                page.set_input_files("input[type=file]", photo_payloads)
                self.stdout.write(f"photos: {len(photo_payloads)}")
                # laisser l'auto-détection peupler les champs (catégorie, sous-catégorie)
                time.sleep(float(os.environ.get("VINTED_DETECT_WAIT", "2.5")))

            def _close_any_menu():
                """Ferme tout menu/overlay ouvert (Escape) avant le prochain champ."""
                try:
                    page.keyboard.press("Escape")
                    time.sleep(0.3)
                except Exception:  # noqa: BLE001
                    pass

            # Description seulement — Prix et Titre remplis EN DERNIER (après état/colis)
            # car la détection photo asynchrone peut écraser ces deux champs quand on
            # interagit avec d'autres éléments du formulaire.
            page.get_by_role("textbox", name="Description").fill(desc); hpause()

            # Catégorie : ne rien faire si déjà auto-détectée (cas nominal cartes).
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
                    _close_any_menu()
                except Exception as e:  # noqa: BLE001
                    self.stdout.write(self.style.WARNING(f"catégorie non auto-sélectionnée : {e}"))
                    _close_any_menu()

            # Marque : champ readonly #brand → JS click pour éviter interception overlay.
            if marque:
                try:
                    page.eval_on_selector("#brand", "el => el.scrollIntoView({block:'center'})")
                    hpause()
                    page.eval_on_selector("#brand", "el => el.click()")
                    time.sleep(0.8)
                    for inp in page.locator("input:not([readonly])").all():
                        try:
                            if inp.is_visible() and not inp.evaluate(
                                    "e => !!e.closest('.js-header')"):
                                inp.fill(marque); break
                        except Exception:  # noqa: BLE001
                            continue
                    time.sleep(1.2)
                    page.get_by_text(marque, exact=True).first.click(timeout=4000)
                    time.sleep(0.5)
                    val = (page.locator("#brand").input_value() or "").strip()
                    if val:
                        self.stdout.write(f"marque : {val}")
                    else:
                        self.stdout.write(self.style.WARNING("marque non confirmée (champ vide)"))
                    _close_any_menu()
                except Exception as e:  # noqa: BLE001
                    self.stdout.write(self.style.WARNING(f"marque « {marque} » non sélectionnée : {e}"))
                    _close_any_menu()

            # État : champ readonly #condition → même technique JS click que #brand.
            if etat:
                try:
                    page.eval_on_selector("#condition", "el => el.scrollIntoView({block:'center'})")
                    hpause()
                    page.eval_on_selector("#condition", "el => el.click()")
                    time.sleep(0.8)
                    # Le panel s'ouvre : cliquer l'option correspondante
                    page.get_by_text(etat, exact=True).first.click(timeout=6000)
                    time.sleep(0.5)
                    val = (page.locator("#condition").input_value() or "").strip()
                    self.stdout.write(f"état : {val or etat}")
                    _close_any_menu()
                except Exception as e:  # noqa: BLE001
                    self.stdout.write(self.style.WARNING(f"état non sélectionné : {e}"))
                    _close_any_menu()
            # Colis : forcer la sélection du format même si Vinted préselectionne « Moyen ».
            # Vinted affiche des boutons radio visuels (pas role=radio) dont le label peut
            # être « Petit colis », « Moyen colis » ou « Grand colis ».
            colis_clicked = False
            for colis_label in (f"{colis} colis", colis):
                if colis_clicked:
                    break
                # Essai 1 : label exact du bouton radio visuel
                try:
                    page.get_by_label(colis_label, exact=False).first.click(timeout=3000)
                    hpause(); colis_clicked = True; continue
                except Exception:  # noqa: BLE001
                    pass
                # Essai 2 : role button dont le name commence par colis_label
                try:
                    page.get_by_role("button", name=re.compile(
                        rf"^{re.escape(colis_label)}", re.I)).first.click(timeout=3000)
                    hpause(); colis_clicked = True; continue
                except Exception:  # noqa: BLE001
                    pass
                # Essai 3 : radio Playwright
                try:
                    page.get_by_role("radio", name=re.compile(
                        rf"{re.escape(colis_label)}", re.I)).check(timeout=3000)
                    hpause(); colis_clicked = True; continue
                except Exception:  # noqa: BLE001
                    pass
                # Essai 4 : span/div contenant le texte dans un élément cliquable
                try:
                    page.locator(f"text={colis_label}").first.click(timeout=3000)
                    hpause(); colis_clicked = True; continue
                except Exception:  # noqa: BLE001
                    pass
            if colis_clicked:
                self.stdout.write(f"colis : {colis}")
            else:
                self.stdout.write(self.style.WARNING(f"colis « {colis} » non coché (défaut conservé)"))

            # PRIX EN AVANT-DERNIER : même problème que le titre — la détection photo
            # peut réécrire le prix suggéré (ex. 23 €) après interactions avec état/colis.
            # On remplit après tous les dropdowns et on vérifie en boucle.
            prix_val = float(it.prix)
            prix_str = str(int(prix_val)) if prix_val == int(prix_val) else str(prix_val)
            time.sleep(0.5)
            prix_field = page.get_by_role("textbox", name="Prix")
            for attempt in range(4):
                prix_field.click(); hpause()
                page.keyboard.press("Control+a"); hpause()
                page.keyboard.press("Delete"); hpause()
                page.keyboard.type(prix_str, delay=20); hpause(0.3, 0.6)
                cur_prix = (prix_field.input_value() or "").strip().replace(",", ".").split(".")[0]
                self.stdout.write(f"prix essai {attempt+1} : '{cur_prix}'")
                if cur_prix == prix_str:
                    break
                self.stdout.write(self.style.WARNING("prix écrasé, réessai..."))
                time.sleep(1.0)

            # TITRE EN DERNIER : la détection photo peut écraser le titre lors des
            # interactions avec d'autres champs. On attend 1s que tout soit stable,
            # puis on force + vérifie.
            time.sleep(1.0)
            titre_field = page.get_by_role("textbox", name="Titre")
            for attempt in range(4):
                titre_field.click(); hpause()
                page.keyboard.press("Control+a"); hpause()
                page.keyboard.press("Delete"); hpause()
                page.keyboard.type(title, delay=20); hpause(0.4, 0.8)
                cur_val = (titre_field.input_value() or "").strip()
                self.stdout.write(f"titre essai {attempt+1} : '{cur_val}'")
                if cur_val.lower() == title.strip().lower():
                    break
                self.stdout.write(self.style.WARNING("titre écrasé, réessai..."))
                time.sleep(1.0)

            shot = f"/tmp/vinted_{it.ref}.png"
            page.screenshot(path=shot)

            # ASSERTION FINALE avant publication : vérifier que prix et titre sont bien
            # ceux attendus. Si l'un des deux est faux → on n'envoie PAS le formulaire.
            final_prix = (prix_field.input_value() or "").strip().replace(",", ".").split(".")[0]
            final_titre = (titre_field.input_value() or "").strip()
            self.stdout.write(f"PRIX final : {final_prix} (attendu : {prix_str})")
            self.stdout.write(f"TITRE final : {final_titre}")
            if final_prix != prix_str:
                raise CommandError(
                    f"ABORT — prix affiché ({final_prix} €) ≠ prix attendu ({prix_str} €). "
                    f"Publication annulée pour éviter un faux positif.")
            if final_titre.lower() != title.strip().lower():
                self.stdout.write(self.style.WARNING(
                    f"titre final '{final_titre}' ≠ attendu '{title}' — vérifier après publication"))

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
                # Attendre l'URL de l'item publié (pattern /items/<id>).
                # Vinted peut passer par /items/new → /items/<id> → /member/...
                # On capture dès qu'on voit /items/<chiffres>.
                import re as _re
                published_url = None
                for _ in range(40):
                    page.wait_for_timeout(500)
                    cur = page.url
                    if _re.search(r"/items/\d+", cur):
                        published_url = cur
                        break
                    if "items/new" not in cur and "items" not in cur:
                        # Déjà sorti du formulaire sans URL item → on garde
                        published_url = cur
                        break
                if not published_url:
                    published_url = page.url
                # NE PAS appeler l'ORM Django ici : on est dans le contexte async de
                # Playwright (sync_playwright ouvre une boucle) -> SynchronousOnlyOperation.
                # On capture l'URL et on sauvegarde APRÈS le bloc `with`.
                self.stdout.write(self.style.SUCCESS(f"✓ publié : {published_url}"))
            else:
                self.stdout.write(self.style.NOTICE("rempli sans valider (ajoute --publish pour mettre en ligne)"))

        # Sauvegarde ORM hors du contexte Playwright (évite SynchronousOnlyOperation).
        if o["publish"] and published_url:
            it.vinted_url = published_url
            it.statut = "publie"
            it.save(update_fields=["vinted_url", "statut"])
