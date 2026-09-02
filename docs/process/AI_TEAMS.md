# Plusieurs équipes (humaines et IA) sur un même dépôt — le protocole

Le harnais existe pour qu'on puisse répartir un produit entre plusieurs sous-équipes — y compris des
équipes d'agents IA qui ouvrent des PR — sans perdre la cohérence de la sortie. Les gates font la police ;
ce document fixe les règles de coexistence que les gates ne peuvent pas vérifier.

## 1. Une équipe = une identité, un périmètre, une trace

- Chaque équipe (humaine ou IA) travaille sous **son** login GitHub. Pas de commits anonymes : `user.name`
  identifie l'équipe (`Team-A`, `swarm`, `claude-harness`…).
- Une équipe **s'annonce avant de commencer** : elle s'assigne la sous-tâche (ou commente « je prends »)
  sur l'issue. Une sous-tâche = une équipe. Deux équipes sur la même issue = arbitrage du tech lead.
- **Toute la communication passe par GitHub** (issues, PR, commentaires). Aucune décision dans un canal
  privé : n'importe quelle équipe doit pouvoir reconstruire le contexte en lisant le dépôt.

## 2. Avant de commencer une session de travail

1. `git fetch origin` — l'état du monde est `origin/main` + les issues ouvertes, pas ta copie locale ni
   ta mémoire de la veille : **le dépôt avance entre tes sessions**, par les autres équipes.
2. Lire l'épic, son issue de suivi (`tracking`) et les PR ouvertes : quelqu'un couvre peut-être déjà la tâche.
3. Vérifier sa sous-tâche : assignée à ton équipe, critères d'acceptation remplis par le PM.
4. Créer/reprendre **sa** branche : `scripts/gh/20-new-subfeature.sh <epic> <task> <issue>` — jamais la
   branche d'une autre équipe.

## 3. Pendant le travail

- **On ne pousse jamais sur la branche d'une autre équipe**, on ne la rebase pas, on ne la « répare » pas.
  Si son travail te bloque : commentaire sur sa PR, ou issue, et le tech lead arbitre.
- **Jamais de force push** sur une branche partagée (`feature/*`, `main`) — les rulesets le refusent, la
  règle vaut aussi pour les branches où ils ne s'appliquent pas encore.
- Récupérer les avancées : `git merge origin/feature/<epic>` (pas de rebase de branches publiées).
- Les **fichiers du harnais** (`.github/`, `scripts/`, `harness.config.sh`, `docs` de process) appartiennent
  à ProdOps : une équipe ne les modifie pas dans une PR de feature — PR séparée, label `harness`.
- Un agent IA suit les mêmes checklists qu'un humain et **ne coche jamais** `QA:` ni ne pose `po-approved`,
  `exec-approved`, `epic:approved` : ces signatures sont humaines par construction.

## 4. Quand deux équipes se marchent dessus quand même

| Symptôme | Règle |
|---|---|
| Conflit de merge dans `feature/*` | résolu par le **tech lead** (Main Dev Team), pas par la sub-team |
| Deux PR modifient le même fichier | la première mergée gagne ; la seconde fait `git merge origin/feature/<epic>` et adapte |
| Une équipe a besoin d'un changement dans le socle (modèles, contrat d'API) | issue vers la Main Dev Team, qui livre sur `feature/*` via sa propre `sub-feature/<epic>/scaffold-…` |
| Une migration Django de chaque côté | numéros en conflit : la seconde équipe renumérote la sienne (`makemigrations --check` en CI le détecte) |
| Un fichier généré / vendored diverge | il a UN owner (CODEOWNERS) ; les autres ne le régénèrent pas |

## 5. Adoption sur un dépôt déjà actif

Tant que les rulesets (`scripts/gh/30-protect-branches.sh`) ne sont pas posés, les checks du harnais sont
**consultatifs** : une PR rouge reste mergeable, le commentaire explique quoi corriger. Les branches
historiques hors convention (`feat/*`…) finissent leur vie normalement ; **tout travail nouveau** part d'un
épic et suit la convention. Poser les rulesets est la décision qui rend les gates bloquantes — elle se prend
quand les équipes ont adopté le flux, pas avant.
