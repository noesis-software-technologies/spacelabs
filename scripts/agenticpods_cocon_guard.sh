#!/usr/bin/env bash
# Finit le cocon Agentic Pods s'il reste des refs à pousser. Auto-réparant :
# relancé par cron toutes les 5 min, protégé par flock (pas de chevauchement).
# La commande est reprenable (saute les refs déjà présentes dans list_drafts).
set -euo pipefail
cd /home/noesis/spacelabs
set -a; . ./.env.local 2>/dev/null || true; set +a
PY=/home/noesis/spacelabs/.venv/bin/python

REMAIN=$($PY manage.py shell -c "
from apps.veille.models import Blog
from apps.veille import mcp
b=Blog.objects.get(id=19)
cocon={'agents-ia-guide','quest-ce-quun-agent-ia','agent-ia-vs-chatbot-rpa','deployer-agent-ia-entreprise','cas-usage-agents-ia','frameworks-agents-ia','mcp-model-context-protocol','orchestration-multi-agents','roi-automatisation-ia','securite-agents-ia','erreurs-projet-agentique'}
try:
    ld=mcp.rpc('tools/call',{'name':'list_drafts','arguments':{}},url=b.mcp_url,token=b.mcp_token,timeout=40,retries=2)
    have={d.get('ref') for d in ((ld.get('result') or {}).get('structuredContent') or {}).get('drafts',[]) if d.get('ref')}
except Exception:
    have=set()
print(len(cocon-have))
" 2>/dev/null | tail -1)

if [ "${REMAIN:-0}" = "0" ]; then
  echo "$(date -Is) cocon complet, rien à faire"
  exit 0
fi
echo "$(date -Is) reste $REMAIN articles, run..."
$PY manage.py agenticpods_cocon --passes 1 >> /tmp/agenticpods_cocon.log 2>&1
echo "$(date -Is) run terminé"
