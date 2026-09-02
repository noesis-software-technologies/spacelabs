# shellcheck shell=bash
# ============================================================================
# harness.config.sh — SOURCE UNIQUE DE VÉRITÉ du harnais de release.
#
# Sourcé par scripts/gh/*.sh et par `make init`.
# Les workflows GitHub Actions ne lisent PAS ce fichier : ils lisent des
# variables de dépôt (Settings → Secrets and variables → Actions → Variables).
# `scripts/gh/50-push-vars.sh` pousse les valeurs ci-dessous vers ces variables
# pour qu'il n'y ait qu'un seul endroit à modifier.
# ============================================================================

# --- Organisation GitHub (slug, sans @) -------------------------------------
ORG="noesis-software-technologies"

# --- Branche tronc -------------------------------------------------------------
DEFAULT_BRANCH="main"

# --- Pods (squads) ---------------------------------------------------------------
# Un label `pod:<slug>` et une équipe GitHub `pod-<slug>` par entrée.
# Slugs en kebab-case (a-z, 0-9, tirets).
PODS=(spacelabs)

# --- Équipes GitHub par discipline (organigramme → CODEOWNERS) -----------------
# Format : "slug|description|permission sur le dépôt (pull|triage|push|maintain|admin)"
TEAMS=(
  "cpo-office|Executive Leadership — CPO / VP Product, CTO / VP Engineering|maintain"
  "product-leadership|Director of PM, Principal PM, Group PM — valident les épics|push"
  "product-managers|Senior PM / PM / APM des pods — owners des épics, posent po-approved|push"
  "design|Product Design Lead, Senior UX, User Researcher|push"
  "eng-managers|Engineering Managers — qualité, déblocage, déploiement prod|maintain"
  "tech-leads|Technical Leads / Architectes — fondations, revue finale du code|maintain"
  "frontend|Frontend developers|push"
  "backend|Backend developers|push"
  "qa|QA / Automation engineers — signent QA Passed|push"
  "data-analysts|Product Data Analysts — plan de mesure, revue post-launch|push"
  "pmm|Product Marketing Managers — positionnement, lancement|push"
  "prodops|Head of Product Operations — owner du harnais (.github, scripts)|admin"
  "data-platform|Data Engineers / Data Scientists — pipelines partagés|push"
)

# --- Handles cités dans les commentaires automatiques (avec @, séparés par des espaces)
PO_HANDLES="@noesis-software-technologies"          # PO/PM notifiés quand une PR d'intégration attend le go
QA_HANDLES="@noesis-software-technologies"          # QA taggé quand la ligne QA: n'est pas signée
PMM_HANDLES="@noesis-software-technologies"        # PMM notifié à la création d'une release

# --- Approbateurs habilités à poser le label `po-approved` ----------------------
# Logins GitHub séparés par des virgules, SANS @. Vide = la présence du label suffit
# (moins sûr : n'importe qui avec le droit triage peut le poser).
PO_APPROVERS="noesis-software-technologies"

# --- Gate PO stricte : un nouveau commit sur une PR → main retire `po-approved`
PO_GATE_STRICT="true"
EXEC_APPROVERS=""                   # logins CTO / CPO qui posent `exec-approved` sur les PR → main d'un épic tier 1 (vide = présence du label suffit)

# --- Hygiène des feature flags -------------------------------------------------
FLAG_MAX_AGE_DAYS=90                 # au-delà : issue `flag:cleanup` ouverte automatiquement
POST_LAUNCH_REVIEW_DAYS=7            # J+N après le palier 100 : issue `post-launch` (revue + rétrospective) ouverte automatiquement
PROD_HEALTH_URL=""                   # URL de santé de la prod (ex. https://app.example.com/healthz) — smoke test QA après déploiement

# --- Revues requises -----------------------------------------------------------
REVIEWS_SUBFEATURE=1                 # sub-feature/* → feature/*
REVIEWS_MAIN=2                       # feature/* → main

# --- Tests end-to-end (Playwright) sur les PR → main ("true" pour activer)
E2E_ENABLED="false"

# --- GitHub Project (numéro du projet d'organisation) — vide = désactivé --------
PROJECT_NUMBER=""

# --- Django (utilisé par les jobs de test) ---------------------------------------
DJANGO_SETTINGS_MODULE="config.settings.dev"
