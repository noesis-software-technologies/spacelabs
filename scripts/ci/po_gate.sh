#!/usr/bin/env bash
# po_gate.sh — gate Go/No-Go du PO/PM sur une PR → main (Règle 2, dernière gate humaine avant main).
#
#   1. le label `po-approved` doit être présent sur la PR
#   2. si vars.PO_APPROVERS est renseigné : le DERNIER poseur du label doit en faire partie,
#      sinon le label est retiré (un dev ne peut pas s'auto-approuver)
#   3. absent/invalide → label `needs-po-review`, commentaire taguant les PO, webhook Slack, exit 1
#   4. label `no-go` (verdict de scripts/gh/32-go-no-go.sh) → merge bloqué tant qu'un GO n'a pas été rejoué
#   5. épic tier 1 (label `tier:1` sur la PR) → label `exec-approved` requis, posé par un EXEC_APPROVERS
#
# Env (fournis par le workflow) : GH_TOKEN GITHUB_REPOSITORY PR LABEL PO_APPROVERS PO_HANDLES
#                                 EVENT_ACTION EVENT_LABEL EVENT_SENDER PR_URL PR_TITLE [SLACK_WEBHOOK_URL]
set -euo pipefail

: "${PR:?PR manquant}" "${GITHUB_REPOSITORY:?}"
LABEL="${LABEL:-po-approved}"
repo="$GITHUB_REPOSITORY"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
marker="<!-- harness:po-gate -->"

notify() { # $1 = message markdown
  "$here/upsert_comment.sh" "$PR" "$marker" "$1" || echo "::warning::commentaire impossible"
  if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
    payload="$(jq -n --arg t "$(printf '%s\n%s' "$1" "${PR_URL:-}")" '{text: $t}')"
    curl -sS -X POST -H 'Content-type: application/json' --data "$payload" "$SLACK_WEBHOOK_URL" >/dev/null \
      || echo "::warning::Slack injoignable"
  fi
}

labels="$(gh pr view "$PR" --repo "$repo" --json labels -q '.labels[].name')"

# Dernier poseur d'un label : événement courant si c'est lui, sinon la timeline de la PR
last_labeler() { # $1 = label
  if [ "${EVENT_ACTION:-}" = "labeled" ] && [ "${EVENT_LABEL:-}" = "$1" ] && [ -n "${EVENT_SENDER:-}" ]; then
    printf '%s' "$EVENT_SENDER"
  else
    gh api "repos/$repo/issues/$PR/timeline?per_page=100" \
      -q "[.[] | select(.event == \"labeled\" and .label.name == \"$1\")] | last | .actor.login // empty" 2>/dev/null || true
  fi
}
# $1 = login, $2 = liste "a, @b, c" → 0 si $1 en fait partie (insensible à la casse)
in_list() {
  local allowed
  allowed="$(tr ',' '\n' <<<"$2" | sed -E 's/^[[:space:]]*@?//; s/[[:space:]]*$//' | grep -v '^$')"
  [ -n "$1" ] && grep -qix -- "$1" <<<"$allowed"
}

if grep -qx -- "no-go" <<<"$labels"; then
  notify "⛔ Le dernier **Go/No-Go** de cet épic est **NO-GO** (label \`no-go\`). Corrigez les points ⛔ du rapport puis relancez \`scripts/gh/32-go-no-go.sh <slug>\` — le label \`go\` remplacera \`no-go\` et cette gate se relancera."
  echo "::error::label no-go présent — merge bloqué"
  exit 1
fi

if grep -qx -- "tier:1" <<<"$labels"; then
  if ! grep -qx -- "exec-approved" <<<"$labels"; then
    notify "🏛️ **Lancement majeur (tier 1)** — sign-off exécutif requis : un CTO / CPO listé dans \`EXEC_APPROVERS\` (${EXEC_APPROVERS:-à renseigner}) pose le label \`exec-approved\` sur cette PR."
    echo "::error::tier 1 sans exec-approved — merge bloqué"
    exit 1
  fi
  if [ -n "${EXEC_APPROVERS:-}" ]; then
    exec_actor="$(last_labeler exec-approved)"
    if ! in_list "$exec_actor" "$EXEC_APPROVERS"; then
      gh pr edit "$PR" --repo "$repo" --remove-label exec-approved >/dev/null 2>&1 || true
      notify "⛔ Le label \`exec-approved\` a été posé par @${exec_actor:-inconnu}, qui n'est pas dans \`EXEC_APPROVERS\`. Label retiré."
      echo "::error::exec-approved posé par un non-approbateur (${exec_actor:-inconnu})"
      exit 1
    fi
  fi
fi

if ! grep -qx -- "$LABEL" <<<"$labels"; then
  gh pr edit "$PR" --repo "$repo" --add-label needs-po-review >/dev/null 2>&1 || true
  notify "⏳ **Go PO requis** — ${PO_HANDLES:-@PO} : cette PR vers \`main\` (« ${PR_TITLE:-}») attend votre revue.
Après démo des critères d'acceptation, posez le label \`$LABEL\` pour débloquer le merge (le check \`po-gate\` se relance seul).
Rappel : un nouveau commit retire le label — la validation porte sur un état précis du code."
  echo "::error::label $LABEL absent — merge bloqué"
  exit 1
fi

actor="$(last_labeler "$LABEL")"

if [ -n "${PO_APPROVERS:-}" ]; then
  if ! in_list "$actor" "$PO_APPROVERS"; then
    gh pr edit "$PR" --repo "$repo" --remove-label "$LABEL" >/dev/null 2>&1 || true
    gh pr edit "$PR" --repo "$repo" --add-label needs-po-review >/dev/null 2>&1 || true
    notify "⛔ Le label \`$LABEL\` a été posé par @${actor:-inconnu}, qui n'est pas dans la liste des approbateurs PO (\`PO_APPROVERS\`). Label retiré.
${PO_HANDLES:-@PO} : à vous de le poser après démo."
    echo "::error::$LABEL posé par un non-approbateur (${actor:-inconnu})"
    exit 1
  fi
fi

gh pr edit "$PR" --repo "$repo" --remove-label needs-po-review >/dev/null 2>&1 || true
"$here/upsert_comment.sh" "$PR" "$marker" "✅ **Go PO** posé par @${actor:-?} — gate \`po-gate\` verte. Merge possible dès que les autres checks sont verts." >/dev/null || true
echo "✅ go PO (${actor:-label présent})"
