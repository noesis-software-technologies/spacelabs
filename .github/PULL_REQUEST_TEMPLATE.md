<!--
Gabarit sub-feature/<epic>/<task> → feature/<epic>.
La CI (job `guard`, profil sub-feature) exige que chaque ligne « - [x] TOKEN: » soit cochée
et sans placeholder <…>. Ne renomme pas les TOKENs ; complète et coche.
Pour une PR feature/* → main, utilise le gabarit integration.md (scripts/gh/25-open-pr.sh le fait seul).
-->

## Ticket
Closes #<numéro de la sous-tâche>

## Ce que fait cette PR
<!-- 3 lignes max : quoi, pourquoi, ce qui est volontairement hors périmètre -->

## Checklist bloquante
- [ ] TICKET: sous-tâche liée ci-dessus (`Closes #…`), titre de PR préfixé `[<epic>]`
- [ ] AC: chaque critère d'acceptation de la sous-tâche est couvert et démontrable (capture/commande)
- [ ] FLAG: tout le code nouveau est derrière le feature flag de l'épic (état `off`, vérifié en local avec le flag OFF puis ON)
- [ ] TESTS: tests unitaires ajoutés ou mis à jour, `pytest` vert en local, aucune migration non commitée
- [ ] QA: QA Passed — scénario joué par @<qa> le <date> (branche à jour avec `feature/<epic>`)

## Notes pour la revue
<!-- points d'attention, choix techniques, dette assumée (avec ticket), captures -->
