# Git & GitHub — le pas-à-pas d'un développeur de sub-team

Tout ce dont tu as besoin pour livrer une sous-tâche sans casser le harnais. Les commandes se lancent
depuis la racine du clone (Git Bash sous Windows, terminal sous macOS/Linux). Prérequis une fois pour
toutes : `gh auth login` (GitHub CLI) et `python3` dans le PATH.

## 1. Démarrer une sous-tâche (issue #57 de l'épic `billing-dashboard`)

```bash
git switch main && git pull                                   # repart d'un état propre
scripts/gh/20-new-subfeature.sh billing-dashboard billing-api 57
```
Tu es maintenant sur `sub-feature/billing-dashboard/billing-api`, créée depuis `feature/billing-dashboard`
et liée à l'issue #57 (visible dans « Development » à droite de l'issue).

## 2. Boucle de travail

```bash
git status                                   # voir ce qui a changé
git add -A                                   # tout mettre dans le prochain commit
git commit -m "feat(billing-dashboard): endpoint GET /billing/summary"
git push                                     # envoyer sur GitHub (à chaque étape, pas seulement à la fin)
```
Messages de commit : `feat(<epic>): …`, `fix(<epic>): …`, `test(<epic>): …`, `chore: …`. Petits commits, souvent.

## 3. Ouvrir la PR

```bash
scripts/gh/25-open-pr.sh 57 --draft    # dès le premier commit : brouillon visible par la Main Dev Team et le PO
scripts/gh/25-open-pr.sh 57            # base = feature/billing-dashboard, description pré-remplie avec « Closes #57 »
scripts/gh/25-open-pr.sh 57 --web      # variante : finir dans le navigateur
```
Ouvre tôt en brouillon : les commentaires arrivent pendant que tu codes, pas après. Un brouillon avec une
checklist incomplète n'est pas rouge ; clique « Ready for review » quand c'est prêt, la CI redevient stricte.
Puis dans GitHub, dans la description de la PR :
1. remplir « Ce que fait cette PR » (3 lignes) ;
2. cocher `TICKET`, `AC`, `FLAG`, `TESTS` quand c'est **vrai** (la CI relit la description à chaque édition) ;
3. laisser `QA:` à la QA — elle remplace `@<qa>` et `<date>` par son nom et signe.
Les reviewers sont assignés automatiquement (CODEOWNERS). Le bouton « Merge » reste gris tant que les checks
`guard · lint · unit-tests · qa-smoke` ne sont pas verts et qu'un code owner n'a pas approuvé.

## 4. Corriger après une revue

```bash
# … modifications …
git add -A && git commit -m "fix(billing-dashboard): retour de revue — validation du tenant" && git push
```
La PR se met à jour toute seule. Réponds à chaque commentaire et clique « Resolve conversation » : le merge
exige que tous les fils soient résolus.

## 5. Récupérer les avancées de `feature/*` (d'autres sous-tâches ont été mergées)

```bash
git fetch origin
git merge origin/feature/billing-dashboard      # crée un commit de fusion, sans réécrire ton historique
git push
```
Pourquoi `merge` et pas `rebase` : pas de `push --force`, pas de risque de perdre du travail ; le squash au
merge de la PR efface de toute façon les commits intermédiaires.

## 6. Résoudre un conflit

```bash
git status                       # liste les fichiers « both modified »
# ouvre chaque fichier, garde la bonne version entre <<<<<<< et >>>>>>>, enlève les marqueurs
git add <fichier>                # pour chaque fichier résolu
git commit                       # valide la fusion (message proposé par git)
git push
```
Dans le doute, demande au tech lead **avant** de commiter la résolution — un conflit mal résolu passe les
tests unitaires et casse en intégration.

## 7. Les « oups »

| Situation | Commande |
|---|---|
| J'ai commité sur la mauvaise branche (pas encore poussé) | `git switch -c sub-feature/<epic>/<task>` puis `git switch <mauvaise-branche> && git reset --hard origin/<mauvaise-branche>` |
| Annuler mon dernier commit local, garder les fichiers | `git reset --soft HEAD~1` |
| Jeter toutes mes modifications non commitées | `git restore .` (irréversible) |
| Mettre de côté pour changer de branche | `git stash` … `git stash pop` |
| Voir ce que la CI reproche | onglet **Checks** de la PR, ou `gh pr checks` |
| Relancer la CI sans nouveau commit | modifier la description de la PR (événement `edited`) ou `gh run rerun <id>` |
| Ma branche est en retard, le bouton « Update branch » apparaît | clique-le (c'est un merge de la base), ou §5 |

## 8. Après le merge

La branche est supprimée automatiquement sur GitHub. En local :
```bash
git switch main && git pull && git fetch --prune && git branch -d sub-feature/billing-dashboard/billing-api
```

## 9. Ce que tu ne fais jamais

- `git push --force` sur une branche partagée (`feature/*`, `main`) — le ruleset le refuse de toute façon ;
- cocher `QA:` toi-même ;
- coder hors du flag de l'épic « parce que c'est petit » ;
- commiter `config/feature_flags.yml` dans une `sub-feature` (l'état d'un flag change par PR de palier, sur `main`).
