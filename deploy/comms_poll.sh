#!/usr/bin/env bash
# Boucle de suivi constant : Telegram (long-poll) + email inbox + veille RP.
# Lance en détaché :  setsid bash deploy/comms_poll.sh >/tmp/comms_poll.log 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
[ -f .env.local ] && source .env.local
export DJANGO_SETTINGS_MODULE=config.settings.dev

echo "[comms_poll] démarré $(date)"
i=0
while true; do
  # Telegram : long-poll 50s (bloquant) → réactif
  python manage.py comms_sync_telegram --timeout 50 >/dev/null 2>&1 || true
  i=$((i+1))
  # toutes les ~5 min (5 cycles), on ré-ingère email + veille RP
  if [ $((i % 5)) -eq 0 ]; then
    python manage.py comms_sync_email >/dev/null 2>&1 || true
    python manage.py veille_sync    >/dev/null 2>&1 || true
    echo "[comms_poll] email+veille sync $(date)"
  fi
done
