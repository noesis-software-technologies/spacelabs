"""Synchronise les avis Vinted vers BoutiqueReview.

Modes :
  1. CDP (Chrome connecté) — lit la page profil Vinted via browser CDP
  2. Token API — appelle l'API interne Vinted avec un access_token
  3. Démo — seed 10 avis réalistes pour le développement

Usage :
  python manage.py sync_vinted_reviews                   # tente CDP, repli démo
  python manage.py sync_vinted_reviews --token <tok>     # via API Vinted
  python manage.py sync_vinted_reviews --demo            # seed démo uniquement
  python manage.py sync_vinted_reviews --username ddorff # surcharge le login Vinted
"""
import datetime
import json

import requests
from django.core.management.base import BaseCommand

from apps.carreaux.models import BoutiqueReview

CDP_URL = "http://127.0.0.1:9222"
VINTED_FR = "https://www.vinted.fr"
DEMO_REVIEWS = [
    {"vinted_id": "demo_001", "auteur": "marjorie_l", "note": 5,
     "commentaire": "Carte reçue parfaitement emballée, conforme à la description. Vendeur très sérieux, je recommande !",
     "date": "2026-09-22"},
    {"vinted_id": "demo_002", "auteur": "pokemon_collector_93", "note": 5,
     "commentaire": "Expédition rapide, carte en état impeccable. Emballage professionnel avec protection rigide. Top !",
     "date": "2026-09-21"},
    {"vinted_id": "demo_003", "auteur": "kylian.tcg", "note": 5,
     "commentaire": "Parfait, carte bien gradée exactement comme annoncé. Communication au top, merci !",
     "date": "2026-09-18"},
    {"vinted_id": "demo_004", "auteur": "amelie_pokefan", "note": 5,
     "commentaire": "Super vendeur, envoi très rapide, carte bien protégée. Je reviendrai !",
     "date": "2026-09-15"},
    {"vinted_id": "demo_005", "auteur": "thibault.cards", "note": 5,
     "commentaire": "Excellent ! Carte reçue en parfait état, emballage très soigné avec toploader et pochette. Merci.",
     "date": "2026-09-10"},
    {"vinted_id": "demo_006", "auteur": "sarah_collection", "note": 5,
     "commentaire": "Vendeur de confiance, transaction parfaite. La carte était encore mieux qu'en photo.",
     "date": "2026-09-05"},
    {"vinted_id": "demo_007", "auteur": "remi_tcg_fr", "note": 5,
     "commentaire": "Très bonne expérience d'achat. Carte arrivée rapidement et bien protégée. Je recommande vivement.",
     "date": "2026-08-30"},
    {"vinted_id": "demo_008", "auteur": "laura.pika", "note": 5,
     "commentaire": "Parfait du début à la fin. Vendeur sympa, réactif et sérieux. Carte au top.",
     "date": "2026-08-25"},
    {"vinted_id": "demo_009", "auteur": "alexis_collector", "note": 5,
     "commentaire": "Encore une fois un achat parfait avec ce vendeur. Fidèle au rendez-vous, qualité au top.",
     "date": "2026-08-20"},
    {"vinted_id": "demo_010", "auteur": "noemie.poke", "note": 5,
     "commentaire": "Livraison ultra rapide et carte impeccable. Ce vendeur sait emballer ses cartes comme un pro !",
     "date": "2026-08-15"},
]


class Command(BaseCommand):
    help = "Synchronise les avis Vinted vers la boutique."

    def add_arguments(self, parser):
        parser.add_argument("--token", help="Access token Vinted (Bearer)")
        parser.add_argument("--username", default="ddorff", help="Login Vinted du vendeur")
        parser.add_argument("--demo", action="store_true", help="Seed avis de démo")

    def handle(self, *args, **o):
        if o["demo"]:
            self._seed_demo()
            return

        if o["token"]:
            ok = self._sync_api(o["token"], o["username"])
            if ok:
                return

        # Tente CDP
        ok = self._sync_cdp(o["username"])
        if not ok:
            self.stdout.write(self.style.WARNING(
                "CDP indisponible et aucun token fourni — seed démo."
            ))
            self._seed_demo()

    def _seed_demo(self):
        created = 0
        for r in DEMO_REVIEWS:
            _, c = BoutiqueReview.objects.update_or_create(
                vinted_id=r["vinted_id"],
                defaults={
                    "auteur": r["auteur"],
                    "note": r["note"],
                    "commentaire": r["commentaire"],
                    "date": datetime.date.fromisoformat(r["date"]),
                    "vinted_url": f"https://www.vinted.fr/member/{r['auteur']}",
                }
            )
            if c:
                created += 1
        self.stdout.write(self.style.SUCCESS(
            f"{created} avis démo créés ({BoutiqueReview.objects.count()} total)."
        ))

    def _sync_api(self, token, username):
        """Récupère les avis via l'API interne Vinted (nécessite un access_token)."""
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "vinted-fr-web/2.12.0",
            "Accept": "application/json",
        }
        try:
            # Résoudre l'ID utilisateur
            r = requests.get(f"{VINTED_FR}/api/v2/users?login={username}",
                             headers=headers, timeout=15)
            data = r.json()
            user_id = data.get("user", {}).get("id")
            if not user_id:
                self.stdout.write(self.style.WARNING(f"User '{username}' introuvable via API."))
                return False

            # Récupérer les feedbacks
            page, synced = 1, 0
            while True:
                rf = requests.get(
                    f"{VINTED_FR}/api/v2/users/{user_id}/feedback",
                    headers=headers, params={"page": page, "per_page": 50}, timeout=15,
                )
                feedbacks = rf.json().get("feedbacks", [])
                if not feedbacks:
                    break
                for f in feedbacks:
                    if f.get("rating", 0) < 1:
                        continue
                    reviewer = f.get("user", {})
                    BoutiqueReview.objects.update_or_create(
                        vinted_id=str(f["id"]),
                        defaults={
                            "auteur": reviewer.get("login", "Acheteur vérifié"),
                            "note": min(5, max(1, f.get("rating", 5))),
                            "commentaire": f.get("feedback", ""),
                            "date": datetime.date.fromisoformat(
                                f["created_at"][:10]) if f.get("created_at") else None,
                            "vinted_url": f"https://www.vinted.fr/member/{reviewer.get('login', '')}",
                        }
                    )
                    synced += 1
                if len(feedbacks) < 50:
                    break
                page += 1

            self.stdout.write(self.style.SUCCESS(f"{synced} avis synchronisés depuis l'API Vinted."))
            return True
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"API Vinted erreur : {e}"))
            return False

    def _sync_cdp(self, username):
        """Récupère les avis via le Chrome CDP connecté à Vinted."""
        try:
            r = requests.get(f"{CDP_URL}/json", timeout=3)
            tabs = r.json()
        except Exception:
            return False

        # Trouve un onglet Vinted
        vinted_tab = next(
            (t for t in tabs if "vinted.fr" in t.get("url", "")), None
        )
        if not vinted_tab:
            return False

        ws_url = vinted_tab.get("webSocketDebuggerUrl", "")
        if not ws_url:
            return False

        try:
            import websocket
            ws = websocket.create_connection(ws_url, timeout=10)
            # Évaluer une requête fetch vers l'API Vinted (même domaine = cookies OK)
            script = f"""
            (async () => {{
                const r = await fetch('/api/v2/users?login={username}', {{credentials:'include'}});
                const d = await r.json();
                const uid = d?.user?.id;
                if (!uid) return null;
                const rf = await fetch(`/api/v2/users/${{uid}}/feedback?per_page=50`, {{credentials:'include'}});
                return await rf.json();
            }})()
            """
            ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                "params": {"expression": script, "awaitPromise": True,
                                           "returnByValue": True}}))
            result = json.loads(ws.recv())
            ws.close()
            data = result.get("result", {}).get("result", {}).get("value")
            if not data or not data.get("feedbacks"):
                return False

            synced = 0
            for f in data["feedbacks"]:
                reviewer = f.get("user", {})
                BoutiqueReview.objects.update_or_create(
                    vinted_id=str(f["id"]),
                    defaults={
                        "auteur": reviewer.get("login", "Acheteur vérifié"),
                        "note": min(5, max(1, f.get("rating", 5))),
                        "commentaire": f.get("feedback", ""),
                        "date": datetime.date.fromisoformat(
                            f["created_at"][:10]) if f.get("created_at") else None,
                        "vinted_url": f"https://www.vinted.fr/member/{reviewer.get('login', '')}",
                    }
                )
                synced += 1
            self.stdout.write(self.style.SUCCESS(f"{synced} avis synchronisés via CDP."))
            return True
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"CDP erreur : {e}"))
            return False
