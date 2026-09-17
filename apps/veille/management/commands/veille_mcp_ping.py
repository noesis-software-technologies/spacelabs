"""Teste la connexion au MCP 13 Atmosphère (procédure de mise en route).

Reproduit le protocole de test du guide :
  a) sans token  → 401 (ou 503 si MCP désactivé côté serveur)
  b) initialize  → serverInfo + protocolVersion
  c) tools/list  → liste des outils exposés

Aucune écriture : lecture/handshake seulement. Requiert ATMOSPHERE_MCP_TOKEN
(dans .env.local) pour les étapes b/c.

  python manage.py veille_mcp_ping
"""
import requests
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Vérifie la connexion/sécurité du MCP 13 Atmosphère (handshake, tools/list)."

    def add_arguments(self, parser):
        parser.add_argument("--timeout", type=int, default=20)

    def _post(self, url, method, timeout, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return requests.post(url, timeout=timeout, headers=headers,
                             json={"jsonrpc": "2.0", "id": 1, "method": method})

    def handle(self, *args, **o):
        url = settings.ATMOSPHERE_MCP_URL
        token = settings.ATMOSPHERE_MCP_TOKEN
        self.stdout.write(f"Endpoint : {url}")

        # a) sécurité : sans token
        try:
            r = self._post(url, "tools/list", o["timeout"])
            tag = {401: "OK (protégé)", 503: "MCP désactivé côté serveur (pas de token configuré)"}.get(
                r.status_code, "inattendu")
            self.stdout.write(f"a) sans token → HTTP {r.status_code}  [{tag}]")
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"a) endpoint injoignable : {e}"))
            return

        if not token:
            self.stdout.write(self.style.WARNING(
                "\nATMOSPHERE_MCP_TOKEN absent : ajoute-le dans .env.local pour tester le handshake."))
            return

        # b) initialize
        try:
            r = self._post(url, "initialize", o["timeout"], token)
            self.stdout.write(f"b) initialize → HTTP {r.status_code}")
            if r.ok:
                info = (r.json().get("result") or {})
                self.stdout.write(f"   serverInfo={info.get('serverInfo')} protocol={info.get('protocolVersion')}")
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"b) échec : {e}"))
            return

        # c) tools/list
        try:
            r = self._post(url, "tools/list", o["timeout"], token)
            self.stdout.write(f"c) tools/list → HTTP {r.status_code}")
            if r.ok:
                tools = ((r.json().get("result") or {}).get("tools")) or []
                self.stdout.write("   outils : " + ", ".join(t.get("name", "?") for t in tools))
                self.stdout.write(self.style.SUCCESS("\nMCP joignable et authentifié. veille_publish --send est prêt."))
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"c) échec : {e}"))
