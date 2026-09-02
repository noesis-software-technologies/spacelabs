#!/usr/bin/env bash
# 32-go-no-go.sh — tableau de bord Go/No-Go automatique d'un épic (rôle : Head of ProdOps, avant la réunion).
#
#   1. lit le registre sur origin/feature/<slug> (épic, flag, pod) — ou --epic N
#   2. collecte via gh : épic, sous-issues, PR ouvertes, PR d'intégration (checklist, checks, revues), bugs ouverts
#   3. scripts/ci/go_no_go.py rend le verdict par tier (1 majeur · 2 standard · 3 mineur)
#   4. publie le rapport en commentaire de la PR d'intégration et pose le label `go` ou `no-go`
#
# Usage : scripts/gh/32-go-no-go.sh <slug> [--epic N] [--dry-run]
#   --dry-run : affiche le rapport sans commenter ni labelliser
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

SLUG="" EPIC="" DRY_RUN="false"
while [ $# -gt 0 ]; do
  case "$1" in
    --epic)    EPIC="${2#\#}"; shift 2 ;;
    --dry-run) DRY_RUN="true"; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 1 ;;
    *) SLUG="$(slug "$1")"; shift ;;
  esac
done
[ -n "$SLUG" ] || die "usage : 32-go-no-go.sh <slug> [--epic N] [--dry-run]"
BRANCH="feature/$SLUG"
FLAG="$(flag_name "$SLUG")"

git fetch --quiet origin
remote_branch_exists "$BRANCH" || die "origin/$BRANCH introuvable — le terrain n'est pas préparé (10-new-epic.sh)"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# --- 1. Registre de la branche d'intégration → épic / pod --------------------------------------
git show "origin/$BRANCH:config/feature_flags.yml" >"$tmp/registry.yml" 2>/dev/null || echo "flags: []" >"$tmp/registry.yml"
read -r reg_epic reg_pod < <(python3 - "$tmp/registry.yml" "$FLAG" <<'PY'
import sys, yaml
flags = (yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}).get("flags") or []
f = next((x for x in flags if x.get("name") == sys.argv[2]), None)
print((str(f.get("epic", "")).lstrip("#") if f else ""), (f.get("pod", "") if f else ""))
PY
)
EPIC="${EPIC:-$reg_epic}"
[ -n "$EPIC" ] || die "épic introuvable pour $FLAG dans le registre de $BRANCH — précise --epic N"
POD="${reg_pod:-}"

# --- 2. Collecte -------------------------------------------------------------------------------
log "collecte GitHub pour l'épic #$EPIC ($BRANCH, flag $FLAG)"
gh issue view "$EPIC" --json number,title,labels,body >"$tmp/epic.json"
gh api "repos/$REPO/issues/$EPIC/sub_issues" --paginate >"$tmp/subs.json" 2>/dev/null || echo "[]" >"$tmp/subs.json"
gh pr list --state open --limit 200 --json number,headRefName,isDraft >"$tmp/open_prs.json"
gh pr list --state open --head "$BRANCH" --json number,url,body,labels,isDraft,reviewDecision,statusCheckRollup >"$tmp/ipr.json"
gh issue list --label bug --state open --limit 200 --json number,title,body,labels >"$tmp/bugs.json"

python3 - "$tmp" "$SLUG" "$FLAG" "$POD" "$EPIC" <<'PY' >"$tmp/input.json"
import json, sys, yaml
from pathlib import Path
d = Path(sys.argv[1]); slug, flag, pod, epic = sys.argv[2:6]
def load(name, default):
    try:
        return json.loads((d / name).read_text(encoding="utf-8") or "null") or default
    except json.JSONDecodeError:
        return default
subs = load("subs.json", [])
if subs and "sub_issues" not in (d / "subs.json").read_text(encoding="utf-8")[:20] and isinstance(subs, dict):
    subs = subs.get("sub_issues", [])
# l'API sub_issues renvoie des objets issue complets : on ne garde que le nécessaire
subs = [{"number": s.get("number"), "title": s.get("title", ""), "state": s.get("state", ""),
         "labels": [l.get("name") if isinstance(l, dict) else l for l in s.get("labels", [])]} for s in subs]
ipr = load("ipr.json", [])
registry = (yaml.safe_load((d / "registry.yml").read_text(encoding="utf-8")) or {}).get("flags") or []
print(json.dumps({
    "epic": load("epic.json", {}), "slug": slug, "flag": flag, "pod": pod,
    "sub_issues": subs, "open_prs": load("open_prs.json", []),
    "integration_pr": ipr[0] if ipr else None, "bugs": load("bugs.json", []),
    "registry_head": registry,
}, ensure_ascii=False))
PY

# --- 3. Verdict ----------------------------------------------------------------------------------
set +e
report="$(python3 "$HARNESS_ROOT/scripts/ci/go_no_go.py" --input "$tmp/input.json")"
rc=$?
set -e
[ $rc -le 1 ] || { printf '%s\n' "$report"; die "go_no_go.py : données invalides"; }
printf '%s\n\n' "$report"

# --- 4. Publication ------------------------------------------------------------------------------
if [ "$DRY_RUN" = "true" ]; then
  log "[dry-run] rapport non publié"
  exit $rc
fi
pr="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); p=d.get("integration_pr"); print(p["number"] if p else "")' "$tmp/input.json")"
if [ -z "$pr" ]; then
  warn "pas de PR d'intégration ouverte : rapport affiché seulement (ouvre-la avec 25-open-pr.sh depuis $BRANCH)"
  exit $rc
fi
if [ $rc -eq 0 ]; then add="go"; remove="no-go"; else add="no-go"; remove="go"; fi
gh pr edit "$pr" --add-label "$add" >/dev/null 2>&1 || warn "label $add non posé (05-sync-labels.sh ?)"
gh pr edit "$pr" --remove-label "$remove" >/dev/null 2>&1 || true
GITHUB_REPOSITORY="$REPO" "$HARNESS_ROOT/scripts/ci/upsert_comment.sh" "$pr" "<!-- harness:go-no-go -->" "$report" >/dev/null \
  && ok "rapport publié sur la PR #$pr (label $add)"
exit $rc
