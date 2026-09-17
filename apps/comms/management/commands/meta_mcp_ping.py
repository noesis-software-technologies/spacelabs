"""Teste la connexion au MCP Meta Business (WhatsApp / Instagram).

Générique : lit META_MCP_URL + META_MCP_TOKEN (.env.local). Reproduit le
handshake MCP (initialize → tools/list). Lecture seule : aucune action sur le
compte Meta. Utile pour valider l'endpoint + l'auth avant de brancher les canaux.

  python manage.py meta_mcp_ping
  python manage.py meta_mcp_ping --url https://mcp.facebook.com/<chemin>
"""
import requests
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Handshake de connexion au MCP Meta (lecture seule)."

    def add_arguments(self, parser):
        parser.add_argument("--url", default="", help="Override de META_MCP_URL.")
        parser.add_argument("--timeout", type=int, default=20)

    def _post(self, url, token, method, timeout):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return requests.post(url, timeout=timeout, headers=headers,
                             json={"jsonrpc": "2.0", "id": 1, "method": method})

    def handle(self, *args, **o):
        url = o["url"] or settings.META_MCP_URL
        token = settings.META_MCP_TOKEN
        self.stdout.write(f"Endpoint : {url}")
        if not token:
            self.stdout.write(self.style.WARNING(
                "META_MCP_TOKEN absent : mets-le dans .env.local avant de tester l'auth."))
        for method in ("initialize", "tools/list"):
            try:
                r = self._post(url, token, method, o["timeout"])
                self.stdout.write(f"{method} → HTTP {r.status_code}")
                self.stdout.write("  " + r.text[:300])
            except requests.RequestException as e:
                self.stdout.write(self.style.ERROR(f"{method} → échec : {e}"))
