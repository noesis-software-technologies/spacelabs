SHELL := /bin/bash
PY ?= python3

.PHONY: help init lint test verify

help:
	@echo "make init    — applique ORG de harness.config.sh dans .github/CODEOWNERS"
	@echo "make lint    — bash -n, shellcheck, actionlint (si installés), ruff, YAML, formulaires d'issues"
	@echo "make test    — pytest (scripts CI + module de flags)"
	@echo "make verify  — lint + test (à passer avant tout « terminé »)"

init:
	@source ./harness.config.sh && \
	  sed -i.bak -E "s#@[A-Za-z0-9_-]+/#@$$ORG/#g" .github/CODEOWNERS && rm -f .github/CODEOWNERS.bak && \
	  echo "CODEOWNERS → @$$ORG/* ; pense à scripts/gh/50-push-vars.sh après un git push"

lint:
	@for f in scripts/gh/*.sh scripts/ci/*.sh harness.config.sh; do bash -n "$$f" || exit 1; done; echo "bash -n OK"
	@if command -v shellcheck >/dev/null; then shellcheck -x -P SCRIPTDIR scripts/gh/*.sh scripts/ci/*.sh && echo "shellcheck OK"; else echo "shellcheck absent (pip install shellcheck-py)"; fi
	@if command -v actionlint >/dev/null; then actionlint .github/workflows/*.yml && echo "actionlint OK"; else echo "actionlint absent (https://github.com/rhysd/actionlint)"; fi
	@$(PY) -m ruff check . && $(PY) -m ruff format --check . >/dev/null && echo "ruff OK"
	@$(PY) -c 'import glob,yaml; [yaml.safe_load(open(f, encoding="utf-8")) for f in glob.glob(".github/**/*.yml", recursive=True)+["config/feature_flags.yml"]]; print("YAML OK")'
	@$(PY) -c 'import glob,yaml; \
	  [ (lambda d: [(i["type"], i.get("attributes",{}).get("label") if i["type"]!="markdown" else True) for i in d["body"]])(yaml.safe_load(open(f, encoding="utf-8"))) for f in glob.glob(".github/ISSUE_TEMPLATE/*.yml") if not f.endswith("config.yml")]; print("formulaires OK")'
	@$(PY) scripts/ci/flags_registry.py check --code-root . >/dev/null && echo "flag-check OK"

test:
	@$(PY) -m pytest -q

verify: lint test
	@echo "✅ harnais vérifié"

install-workflows:  ## Déplacer les workflows du harnais vers .github/workflows + rescoper ci.yml (droits Workflows requis)
	@git mv harness/workflows/*.yml .github/workflows/
	@python3 - <<'PY'
	import pathlib
	p = pathlib.Path(".github/workflows/ci.yml"); s = p.read_text(encoding="utf-8")
	old = "on:\n  push:\n    branches: [main]\n  pull_request:\n"
	new = ("# Depuis le harnais de release, les PR sont testées par ci-sub-feature / ci-integration :\n"
	       "# ce workflow reste le filet de sécurité post-merge sur main (+ lancement manuel).\n"
	       "on:\n  push:\n    branches: [main]\n  workflow_dispatch:\n")
	if old in s: p.write_text(s.replace(old, new, 1), encoding="utf-8"); print("ci.yml rescopé")
	else: print("ci.yml déjà rescopé ou modifié — vérifier à la main")
	PY
	@rm -f harness/workflows/README.md && rmdir harness/workflows harness 2>/dev/null || true
	@git add -A && echo "→ git commit -m 'chore(harness): activer les workflows' && git push"
