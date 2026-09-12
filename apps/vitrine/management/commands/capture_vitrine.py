"""
Capture des screenshots mobile de chaque produit de la vitrine.

Usage :
    python manage.py capture_vitrine           # tous les produits
    python manage.py capture_vitrine --slug upvid
    python manage.py capture_vitrine --force   # recapture même si fichier existant
"""
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.vitrine.catalogue import PRODUITS

OUT_DIR = Path(settings.BASE_DIR) / "static" / "vitrine" / "screenshots"

# Viewport mobile standard (iPhone 14 Pro)
MOBILE_W = 390
MOBILE_H = 844


class Command(BaseCommand):
    help = "Capture les screenshots mobile de la vitrine via Playwright"

    def add_arguments(self, parser):
        parser.add_argument("--slug", type=str, help="Capturer un seul slug")
        parser.add_argument("--force", action="store_true", help="Recapturer même si déjà présent")

    def handle(self, *args, **options):
        from playwright.sync_api import sync_playwright

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        cibles = [p for p in PRODUITS if not options["slug"] or p["slug"] == options["slug"]]

        if not cibles:
            self.stderr.write(f"Slug inconnu : {options['slug']}")
            return

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
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
                out_path = OUT_DIR / f"{p['slug']}.jpg"
                if out_path.exists() and not options["force"]:
                    self.stdout.write(f"  skip  {p['slug']} (déjà capturé)")
                    continue

                url = p["url"]
                self.stdout.write(f"  →  {p['slug']}  {url}")
                page = ctx.new_page()
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                    # Laisser le JS s'initialiser
                    time.sleep(1.5)
                    # Masquer les bandeaux cookie pour un rendu propre
                    page.evaluate("""
                        document.querySelectorAll(
                            '[class*="cookie"],[class*="consent"],[id*="cookie"],[id*="consent"],[class*="banner"],[class*="gdpr"]'
                        ).forEach(el => el.style.display = 'none');
                    """)
                    page.screenshot(
                        path=str(out_path),
                        type="jpeg",
                        quality=82,
                        clip={"x": 0, "y": 0, "width": MOBILE_W, "height": MOBILE_H},
                    )
                    self.stdout.write(self.style.SUCCESS(f"  ✓  {p['slug']}"))
                except Exception as exc:
                    self.stderr.write(f"  ✗  {p['slug']} — {exc}")
                finally:
                    page.close()

            ctx.close()
            browser.close()

        self.stdout.write(self.style.SUCCESS(f"\nScreenshots dans {OUT_DIR}"))
