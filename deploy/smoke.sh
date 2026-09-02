#!/usr/bin/env bash
# deploy/smoke.sh — smoke test QA de la production après déploiement (flags OFF : rien n'a changé pour les
# utilisateurs, on vérifie que le service répond). Remplacer / compléter par les scénarios du pod.
set -euo pipefail
url="${PROD_HEALTH_URL:-}"
[ -n "$url" ] || { echo "::notice::PROD_HEALTH_URL non défini : smoke test prod non exécuté"; exit 0; }
code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$url" || echo 000)"
echo "$url → HTTP $code"
[ "$code" = "200" ] || { echo "::error::prod en échec${TAG:+ après $TAG} — redéployer le tag précédent"; exit 1; }
# scénarios supplémentaires (ex.) : curl -fsS "$url/../api/v1/ping" ; pytest -m smoke --base-url "$url"
