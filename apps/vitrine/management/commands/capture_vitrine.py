"""
Capture des screenshots de chaque produit de la vitrine.

Usage :
    python manage.py capture_vitrine              # mobile, tous les produits
    python manage.py capture_vitrine --desktop    # desktop pleine page (focus carrousel)
    python manage.py capture_vitrine --slug upvid
    python manage.py capture_vitrine --force      # recapture même si fichier existant
"""
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.vitrine.catalogue import PRODUITS

OUT_DIR_MOBILE = Path(settings.BASE_DIR) / "static" / "vitrine" / "screenshots"
OUT_DIR_DESKTOP = Path(settings.BASE_DIR) / "static" / "vitrine" / "desktop"

# Viewport mobile standard (iPhone 14 Pro)
MOBILE_W = 390
MOBILE_H = 844

# Viewport desktop
DESKTOP_W = 1280
DESKTOP_H = 800
# Hauteur max capturée en pleine page (évite les pages infinies)
DESKTOP_MAX_H = 2600


class Command(BaseCommand):
    help = "Capture les screenshots (mobile ou desktop) de la vitrine via Playwright"

    def add_arguments(self, parser):
        parser.add_argument("--slug", type=str, help="Capturer un seul slug")
        parser.add_argument("--force", action="store_true", help="Recapturer même si déjà présent")
        parser.add_argument(
            "--desktop",
            action="store_true",
            help="Capture desktop pleine page (dossier static/vitrine/desktop/)",
        )

    def handle(self, *args, **options):
        from playwright.sync_api import sync_playwright

        desktop = options["desktop"]
        out_dir = OUT_DIR_DESKTOP if desktop else OUT_DIR_MOBILE
        out_dir.mkdir(parents=True, exist_ok=True)

        cibles = [p for p in PRODUITS if not options["slug"] or p["slug"] == options["slug"]]
        if not cibles:
            self.stderr.write(f"Slug inconnu : {options['slug']}")
            return

        ok = fail = 0
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            if desktop:
                ctx = browser.new_context(
                    viewport={"width": DESKTOP_W, "height": DESKTOP_H},
                    device_scale_factor=1,
                )
            else:
                ctx = browser.new_context(
                    viewport={"width": MOBILE_W, "height": MOBILE_H},
                    device_scale_factor=2,
                    is_mobile=True,
                    has_touch=True,
                    user_agent=(
                        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
                    ),
                )

            for p in cibles:
                out_path = out_dir / f"{p['slug']}.jpg"
                if out_path.exists() and not options["force"]:
                    self.stdout.write(f"  skip  {p['slug']} (déjà capturé)")
                    continue

                url = p["url"]
                self.stdout.write(f"  →  {p['slug']}  {url}")
                page = ctx.new_page()
                try:
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                    if resp is not None and resp.status >= 400:
                        raise RuntimeError(f"HTTP {resp.status}")
                    time.sleep(1.5)
                    # Masquer les bandeaux cookie pour un rendu propre
                    page.evaluate("""
                        document.querySelectorAll(
                            '[class*="cookie"],[class*="consent"],[id*="cookie"],[id*="consent"],[class*="banner"],[class*="gdpr"]'
                        ).forEach(el => el.style.display = 'none');
                    """)
                    if desktop:
                        # Pleine page, plafonnée à DESKTOP_MAX_H
                        h = page.evaluate("Math.round(document.body.scrollHeight)") or DESKTOP_H
                        h = max(DESKTOP_H, min(int(h), DESKTOP_MAX_H))
                        page.screenshot(
                            path=str(out_path),
                            type="jpeg",
                            quality=80,
                            clip={"x": 0, "y": 0, "width": DESKTOP_W, "height": h},
                        )
                    else:
                        page.screenshot(
                            path=str(out_path),
                            type="jpeg",
                            quality=82,
                            clip={"x": 0, "y": 0, "width": MOBILE_W, "height": MOBILE_H},
                        )
                    ok += 1
                    self.stdout.write(self.style.SUCCESS(f"  ✓  {p['slug']}"))
                except Exception as exc:
                    fail += 1
                    self.stderr.write(f"  ✗  {p['slug']} — {exc}")
                finally:
                    page.close()

            ctx.close()
            browser.close()

        self.stdout.write(self.style.SUCCESS(f"\n{ok} OK, {fail} échec(s) — dossier {out_dir}"))
