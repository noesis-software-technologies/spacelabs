#!/usr/bin/env bash
set -euo pipefail
cd /home/noesis/spacelabs
set -a; . ./.env.local 2>/dev/null || true; set +a
PY=/home/noesis/spacelabs/.venv/bin/python
pgrep -f "python manage.py yonkko_cover_pexels" >/dev/null && exit 0
REMAIN=$($PY manage.py shell -c "from apps.veille.models import PressItem; print(PressItem.objects.filter(categorie='onepiece',cover_url='').exclude(mcp_article_id='').count())" 2>/dev/null | tail -1)
[ "${REMAIN:-0}" = "0" ] && exit 0
setsid nohup $PY manage.py yonkko_cover_pexels --limit 300 >> /tmp/yk_cover.log 2>&1 < /dev/null &
echo "$(date -Is) cover relancé (restants=$REMAIN)"
