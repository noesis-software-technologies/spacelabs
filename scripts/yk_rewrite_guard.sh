#!/usr/bin/env bash
# Relance le run de réécriture One Piece s'il reste des items et qu'aucun run ne tourne.
set -euo pipefail
cd /home/noesis/spacelabs
set -a; . ./.env.local 2>/dev/null || true; set +a
PY=/home/noesis/spacelabs/.venv/bin/python
# déjà en cours ?
if pgrep -f "python manage.py yonkko_rewrite_all" | grep -qv "$$"; then
  exit 0
fi
# reste-t-il des items ?
REMAIN=$($PY manage.py shell -c "from apps.veille.models import PressItem; print(PressItem.objects.filter(categorie='onepiece',statut='nouveau').count())" 2>/dev/null | tail -1)
if [ "${REMAIN:-0}" = "0" ]; then
  exit 0
fi
setsid nohup $PY manage.py yonkko_rewrite_all --limit 220 >> /tmp/yk_rewrite.log 2>&1 < /dev/null &
echo "$(date -Is) relancé (restants=$REMAIN)"
