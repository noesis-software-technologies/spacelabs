#!/usr/bin/env bash
# Quotidien : moisson RSS-direct One Piece -> réécriture humanisée -> push image native.
set -euo pipefail
cd /home/noesis/spacelabs
set -a; . ./.env.local 2>/dev/null || true; set +a
PY=/home/noesis/spacelabs/.venv/bin/python
echo "=== $(date -Is) daily ==="
$PY manage.py veille_scrape_onepiece_rss --limit 100
$PY manage.py yonkko_rewrite_all --limit 60
