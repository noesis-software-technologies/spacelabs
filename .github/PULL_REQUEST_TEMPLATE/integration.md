<!--
Gabarit d'INTÉGRATION feature/<epic> → main (Main Dev Team).
CI : job `guard` (profil integration) + `regression` + `flag-check` + `po-gate`.
Le merge ne change RIEN pour les utilisateurs : le flag reste à `off`. La release = paliers de rollout.
Gate PO : un PO/PM listé dans vars.PO_APPROVERS pose le label `po-approved` après démo.
-->

## Épic et suivi
Refs #<numéro de l'épic> — l'épic reste ouvert jusqu'au nettoyage du flag
Closes #<numéro du suivi> — issue de suivi d'intégration (Main Dev Team)

## Périmètre livré
<!-- sous-tâches mergées (#…), ce qui reste hors périmètre, décisions prises en cours de route -->

## Checklist bloquante
- [ ] TICKET: suivi lié (`Closes #…`) et épic référencé (`Refs #…`), toutes les sous-tâches mergées dans `feature/<epic>` et fermées
- [ ] AC: critères d'acceptation de l'épic démontrés au PO (lien démo / enregistrement / environnement)
- [ ] FLAG: le flag de l'épic est déclaré dans `config/feature_flags.yml` à l'état `off` — comportement actuel inchangé une fois mergé
- [ ] TESTS: régression complète verte (job `regression`), migrations réversibles, aucune donnée détruite
- [ ] QA: QA Passed sur `feature/<epic>` — signé par @<qa> le <date> (scénarios bout-en-bout, flag ON et OFF)
- [ ] ROLLBACK: plan de repli écrit ici (couper le flag ; si migration : procédure de rollback testée)
- [ ] ANALYTICS: événements de mesure (North Star + guardrails de l'épic) implémentés et validés par l'analyste du pod
- [ ] DOCS: doc technique et doc support à jour (runbook, aide en ligne)
- [ ] GTM: lancement prêt selon le tier — T1 : plan GTM complet, presse, formation ventes · T2 : notes de release PMM · T3 : entrée CHANGELOG (validé par le PMM)

## Plan de rollout proposé
<!-- ex. : interne (liste blanche) → 10 % → 50 % → 100 %, critère de passage à chaque palier, qui décide, quand -->

## Plan de repli
<!-- commande / PR de kill switch, durée de rétablissement, personne d'astreinte -->
