#!/usr/bin/env bash
# 10-new-epic.sh — « préparer le terrain » d'un épic (rôle : Tech Lead / Main Dev Team).
#
#   1. vérifie que l'épic porte le label `epic:approved` (posé par le leadership produit)
#   2. crée la branche d'intégration feature/<slug> depuis main (ou la reprend si elle existe)
#   3. 1er commit = déclaration du feature flag <slug>_v1 à OFF dans config/feature_flags.yml (Règle 3)
#   4. crée une issue `sub-task` par --task, rattachée à l'épic (sub-issue GitHub + case dans l'épic)
#   5. pose le label tier:N (lu dans le formulaire, ou --tier) et crée l'issue de SUIVI D'INTÉGRATION
#      (label `tracking`, Main Dev Team) — c'est elle que la PR d'intégration ferme ; l'épic reste ouvert
#      jusqu'au nettoyage du flag
#   6. imprime la commande suivante pour chaque sub-team
#
# Usage :
#   scripts/gh/10-new-epic.sh --epic 42 --slug billing-dashboard --pod growth \
#       --task "DB migrations" --task "Billing API" --task "UI dashboard"
#
#   # ou en créant l'épic au passage (il restera à faire approuver : label epic:approved)
#   scripts/gh/10-new-epic.sh --title "Multi-tenant billing dashboard" --slug billing-dashboard --pod growth ...
#
# Options : --force (passer outre l'absence de epic:approved — à éviter), --assignee <login>, --tier 1|2|3
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

EPIC="" TITLE="" SLUG="" POD="" ASSIGNEE="" FORCE="false" TIER=""
TASKS=()

usage() { sed -n '2,20p' "$0"; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --epic)     EPIC="$2"; shift 2 ;;
    --title)    TITLE="$2"; shift 2 ;;
    --slug)     SLUG="$(slug "$2")"; shift 2 ;;
    --pod)      POD="$(slug "$2")"; shift 2 ;;
    --task)     TASKS+=("$2"); shift 2 ;;
    --assignee) ASSIGNEE="$2"; shift 2 ;;
    --tier)     TIER="$2"; shift 2 ;;
    --force)    FORCE="true"; shift ;;
    -h|--help)  usage ;;
    *) die "option inconnue : $1" ;;
  esac
done

[ -n "$SLUG" ] || die "--slug <kebab-case> requis (nom de la branche feature/<slug>)"
[ -n "$POD" ]  || die "--pod <slug> requis (un des : ${PODS[*]})"
printf '%s\n' "${PODS[@]}" | grep -qx -- "$POD" || warn "pod '$POD' absent de harness.config.sh (PODS)"
[ -n "$EPIC" ] || [ -n "$TITLE" ] || die "--epic <numéro> ou --title <titre> requis"
[ -z "$TIER" ] || [[ "$TIER" =~ ^[123]$ ]] || die "--tier doit valoir 1, 2 ou 3"

FLAG="$(flag_name "$SLUG")"
BRANCH="feature/$SLUG"

# --- 0. Épic : création si nécessaire --------------------------------------------
if [ -z "$EPIC" ]; then
  log "création de l'épic « $TITLE »"
  body="$(cat <<EOF
<!-- Épic créé par scripts/gh/10-new-epic.sh — complète les sections via le formulaire d'issue « Épic (PM) » si besoin -->
**Pod** : $POD
**Feature flag** : \`$FLAG\` (OFF par défaut)
**Branche d'intégration** : \`$BRANCH\`

## Problème utilisateur
_à compléter par le PM_

## North Star metric · Guardrails · Non-goals
_à compléter par le PM avant approbation_

### Tier de lancement

${TIER:-2}

## Sous-tâches
EOF
)"
  args=(--title "[EPIC] $TITLE" --label epic --label "pod:$POD" --body "$body")
  [ -n "$ASSIGNEE" ] && args+=(--assignee "$ASSIGNEE")
  url="$(gh issue create "${args[@]}")"
  EPIC="$(number_from_url "$url")"
  ok "épic #$EPIC créé : $url"
fi

# --- 1. Gate leadership produit ----------------------------------------------------
if issue_has_label "$EPIC" "epic:approved"; then
  ok "épic #$EPIC approuvé (epic:approved)"
elif [ "$FORCE" = "true" ]; then
  warn "épic #$EPIC NON approuvé — poursuite forcée (--force)"
else
  die "épic #$EPIC sans label epic:approved. Demande l'approbation au leadership produit (Director PM / GPM) :
    gh issue edit $EPIC --add-label epic:approved   # à lancer par un membre de @$ORG/product-leadership
  ou relance avec --force (à éviter : c'est le gate « le what et le when » de l'organigramme)."
fi

# --- 2. Branche d'intégration --------------------------------------------------------
require_clean_tree
git fetch --quiet origin
if remote_branch_exists "$BRANCH"; then
  log "branche $BRANCH existe déjà sur origin — reprise"
  git switch --quiet "$BRANCH" 2>/dev/null || git switch --quiet --track "origin/$BRANCH"
  git pull --quiet --ff-only origin "$BRANCH"
else
  git switch --quiet -c "$BRANCH" "origin/$DEFAULT_BRANCH"
  ok "branche $BRANCH créée depuis origin/$DEFAULT_BRANCH"
fi

# --- 3. Règle 3 : le 1er commit déclare le flag à OFF -----------------------------------
set +e
python3 "$HARNESS_ROOT/scripts/ci/flags_registry.py" add \
  --name "$FLAG" --epic "#$EPIC" --pod "$POD" --owner "@$ORG/pod-$POD" \
  --max-age "$FLAG_MAX_AGE_DAYS"
rc=$?
set -e
case $rc in
  0) git add config/feature_flags.yml
     git commit --quiet -m "chore(flags): declare $FLAG (off) for epic #$EPIC"
     ok "commit flag $FLAG (off)" ;;
  3) log "flag $FLAG déjà déclaré — pas de nouveau commit" ;;
  *) die "flags_registry.py add a échoué (code $rc)" ;;
esac
git push --quiet -u origin "$BRANCH"
ok "branche $BRANCH poussée"

# --- 4. Sous-tâches -----------------------------------------------------------------------
created=()
for task in "${TASKS[@]}"; do
  tslug="$(slug "$task")"
  tbody="$(cat <<EOF
Épic parent : #$EPIC · Pod : $POD · Flag : \`$FLAG\`

**Branche** : \`sub-feature/$SLUG/$tslug\` → PR vers \`$BRANCH\`
Démarrer : \`scripts/gh/20-new-subfeature.sh $SLUG $tslug <numéro de cette issue>\`

## Critères d'acceptation
- [ ] _à compléter par le PM / APM (Given / When / Then)_

## Definition of Done
- [ ] code derrière \`$FLAG\` (OFF) · tests unitaires · revue code owner · **QA Passed** signé dans la PR
EOF
)"
  url="$(gh issue create --title "[$SLUG] $task" --label sub-task --label "pod:$POD" --body "$tbody")"
  n="$(number_from_url "$url")"
  created+=("$n|$tslug|$task")
  # Rattachement natif (sub-issues) ; en cas d'échec (plan/API), la case dans l'épic suffit
  sub_id="$(gh api "repos/$REPO/issues/$n" -q .id)"
  gh api -X POST "repos/$REPO/issues/$EPIC/sub_issues" -F sub_issue_id="$sub_id" >/dev/null 2>&1 \
    || warn "sub-issue non rattachée (API indisponible ?) — la case de suivi dans l'épic fait foi"
  ok "sous-tâche #$n « $task »"
  if [ -n "$PROJECT_NUMBER" ]; then
    gh project item-add "$PROJECT_NUMBER" --owner "$ORG" --url "$url" >/dev/null 2>&1 \
      || warn "non ajoutée au projet #$PROJECT_NUMBER (scope 'project' ? gh auth refresh -s project)"
  fi
done

if [ ${#created[@]} -gt 0 ]; then
  epic_body="$(gh issue view "$EPIC" --json body -q .body)"
  add=""
  for c in "${created[@]}"; do
    IFS='|' read -r n _ task <<<"$c"
    add+=$'\n'"- [ ] #$n — $task"
  done
  gh issue edit "$EPIC" --body "$epic_body$add" >/dev/null && ok "cases de suivi ajoutées à l'épic #$EPIC"
fi

# --- 5. Tier de lancement + issue de suivi d'intégration (Main Dev Team) ---------------------
TIER="${TIER:-$(issue_tier "$EPIC")}"
issue_has_label "$EPIC" "tier:$TIER" || gh issue edit "$EPIC" --add-label "tier:$TIER" >/dev/null 2>&1 \
  || warn "label tier:$TIER non posé (05-sync-labels.sh ?)"
TRACK="$(tracking_issue_of "$EPIC")"
if [ -z "$TRACK" ]; then
  tbody="$(cat <<EOF
Épic : #$EPIC · Pod : $POD · Tier : $TIER · Flag : \`$FLAG\` · Branche : \`$BRANCH\`
Owner : Main Dev Team (tech lead). Cette issue est fermée par la PR d'intégration (\`Closes #…\`) ;
l'épic reste ouvert jusqu'au nettoyage du flag.

## Phases
- [ ] Fondations posées sur \`$BRANCH\` derrière \`$FLAG\` (modèles, contrat d'API, squelette de vue, points d'injection)
- [ ] Toutes les sous-tâches mergées (QA Passed signé sur chaque PR)
- [ ] Conflits d'intégration résolus (responsable : tech lead)
- [ ] Événements de mesure validés par l'analyste (North Star + guardrails)
- [ ] PR d'intégration ouverte (\`scripts/gh/25-open-pr.sh $EPIC\` depuis \`$BRANCH\`) — checklist complète
- [ ] Go/No-Go : \`scripts/gh/32-go-no-go.sh $SLUG\` → GO
- [ ] Go PO (\`po-approved\`) → merge → staging
- [ ] Tag de release (\`scripts/gh/40-release.sh\`) → prod, flag OFF · smoke test prod (QA)
- [ ] Paliers : interne → 10 → 50 → 100 (\`scripts/gh/35-rollout.sh $SLUG …\`) · lancement PMM à 100
- [ ] Revue post-launch (J+7 à J+14) · verdict · PR de nettoyage du flag · rétrospective de release (ProdOps)
EOF
)"
  args=(--title "[$SLUG] Suivi d'intégration" --label tracking --label "pod:$POD" --label "tier:$TIER" --body "$tbody")
  [ -n "$ASSIGNEE" ] && args+=(--assignee "$ASSIGNEE")
  turl="$(gh issue create "${args[@]}")"
  TRACK="$(number_from_url "$turl")"
  tid="$(gh api "repos/$REPO/issues/$TRACK" -q .id)"
  gh api -X POST "repos/$REPO/issues/$EPIC/sub_issues" -F sub_issue_id="$tid" >/dev/null 2>&1 || true
  epic_body="$(gh issue view "$EPIC" --json body -q .body)"
  gh issue edit "$EPIC" --body "$epic_body"$'\n'"**Suivi d'intégration** : #$TRACK" >/dev/null
  ok "issue de suivi #$TRACK créée (tier $TIER)"
else
  log "issue de suivi #$TRACK déjà référencée dans l'épic"
fi

# --- 6. Suite -----------------------------------------------------------------------------
cat <<EOF

────────────────────────────────────────────────────────────
Terrain préparé pour l'épic #$EPIC
  branche   : $BRANCH   (protégée par le ruleset harness-feature)
  flag      : $FLAG = off   (config/feature_flags.yml)
  suivi     : #$TRACK (tier $TIER)   — fermé par la PR d'intégration
Commandes suivantes, par sub-team :
EOF
for c in "${created[@]}"; do
  IFS='|' read -r n tslug task <<<"$c"
  printf '  #%s %-32s scripts/gh/20-new-subfeature.sh %s %s %s\n' "$n" "« $task »" "$SLUG" "$tslug" "$n"
done
echo "────────────────────────────────────────────────────────────"
