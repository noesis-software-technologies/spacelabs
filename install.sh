#!/usr/bin/env bash
# SpaceLabs — installation locale en une commande (idempotent).
# Usage : bash install.sh   (depuis la racine du dépôt, sur Ubuntu/WSL/macOS)
set -euo pipefail
cd "$(dirname "$0")"

echo "== SpaceLabs — installation locale =="

# 1) Python
PY=""
for c in python3.12 python3.13 python3; do command -v "$c" >/dev/null 2>&1 && { PY="$c"; break; }; done
[ -n "$PY" ] || { echo "❌ Python 3.12+ requis (introuvable)."; exit 1; }
echo "• Python : $($PY --version)"

# 2) venv + dépendances
[ -d .venv ] || "$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
echo "• Dépendances…"
pip install -r requirements.txt >/dev/null

# 3) .env (SECRET_KEY générée) — jamais commité
if [ ! -f .env ]; then
  cp .env.example .env
  SECRET="$(python -c 'import secrets;print(secrets.token_urlsafe(50))')"
  if grep -q '^SECRET_KEY=' .env; then
    sed -i.bak "s#^SECRET_KEY=.*#SECRET_KEY=${SECRET}#" .env && rm -f .env.bak
  else
    echo "SECRET_KEY=${SECRET}" >> .env
  fi
  echo "• .env créé (SECRET_KEY générée)."
fi
touch .env.local  # secrets locaux (IMAP / MCP / Pexels / Meta)

# 4) base + démo
python manage.py migrate --noinput
python manage.py bootstrap_demo || true

cat <<'EOF'

✅ SpaceLabs installé.

Démarrer :
  source .venv/bin/activate
  python manage.py runserver 0.0.0.0:8000 --settings=config.settings.dev

→ http://localhost:8000/   ·   connexion : pilote / cockpit-local

Secrets (facultatifs) à mettre dans .env.local :
  VEILLE_IMAP_USER / VEILLE_IMAP_PASS   (veille éditoriale)
  ATMOSPHERE_MCP_TOKEN                  (publication blog)
  PEXELS_API_KEY                        (images libres de droit)
Voir docs/INSTALL.md pour le bootstrap complet (modèle local, OpenClaw, WhatsApp/Chatwoot).
EOF
