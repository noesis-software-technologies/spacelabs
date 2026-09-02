<!--
Gabarit HOTFIX hotfix/<slug> → main : correctif urgent, périmètre minimal.
CI : `guard` (profil hotfix) + `regression` + `flag-check` + `po-gate` (le PO peut approuver en asynchrone).
Un hotfix reste une PR : Règle 1, rien n'entre dans main sans PR.
-->

## Incident
Closes #<numéro du bug>

## Cause racine et correctif
<!-- symptôme → cause racine (pas un pansement) → ce que change ce correctif → ce qu'il ne change pas -->

## Checklist bloquante
- [ ] TICKET: bug lié (`Closes #…`), sévérité et impact utilisateur décrits
- [ ] TESTS: test de non-régression qui échouait AVANT le correctif et passe APRÈS
- [ ] ROLLBACK: repli décrit (revert de la PR ou flag), personne d'astreinte nommée

## Suivi
<!-- ticket de fond si le correctif est partiel, post-mortem si incident de prod -->
