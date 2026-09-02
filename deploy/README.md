# deploy/ — le contrat de déploiement du harnais

`release.yml` ne sait rien de votre infra : il appelle des **hooks** s'ils existent et sont exécutables.
Owner : `@org/eng-managers` (CODEOWNERS).

| Hook | Appelé par | Quand | Variables reçues |
|---|---|---|---|
| `deploy/staging.sh` | job `deploy-staging` | chaque push sur `main` | `DEPLOY_ENV=staging`, `GIT_SHA` |
| `deploy/production.sh` | job `deploy-production` (après approbation de l'environnement `production`) | tag `vX.Y.Z` | `DEPLOY_ENV=production`, `GIT_SHA`, `TAG` |
| `deploy/smoke.sh` | job `smoke-production` | juste après le déploiement prod | `TAG`, `PROD_HEALTH_URL` |

Sans `deploy/smoke.sh`, le smoke test se réduit à `GET $PROD_HEALTH_URL` (variable de dépôt, `harness.config.sh`).
Un hook qui sort en erreur fait échouer le job (et le déploiement suivant attend).

Secrets (clé SSH, token PaaS) : `gh secret set …` puis `env:` dans le job correspondant de `release.yml`.
Le repli d'un déploiement est **le redéploiement du tag précédent** ; le repli d'une fonctionnalité est le flag
(`FLAG_<NOM>=off`, `35-rollout.sh <slug> off`) — ne pas confondre.
