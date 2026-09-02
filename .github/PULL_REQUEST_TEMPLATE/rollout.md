<!--
Gabarit de PALIER DE ROLLOUT release/<epic>-<palier> → main : c'est la release produit.
Seul config/feature_flags.yml change. CI : `guard` (profil rollout) + `regression` + `flag-check` + `po-gate`.
Créé par scripts/gh/35-rollout.sh <epic> <palier>.
-->

## Épic
Refs #<numéro de l'épic>

## Palier
<!-- interne (liste blanche) | 10 % | 25 % | 50 % | 100 % | OFF (repli) — et le palier précédent -->

## Checklist bloquante
- [ ] TICKET: épic référencé (`Refs #…`), palier précédent observé au moins <durée> sans dégradation
- [ ] FLAG: seul `config/feature_flags.yml` change dans cette PR (état / pourcentage / liste blanche)
- [ ] ROLLBACK: repli = PR `scripts/gh/35-rollout.sh <epic> off` ou variable d'environnement `FLAG_<NOM>=off` + redémarrage (personne d'astreinte nommée)
- [ ] ANALYTICS: tableau de bord North Star + guardrails ouvert, seuils d'alerte et de retour arrière écrits ci-dessous

## Critères de passage au palier suivant
<!-- métrique, seuil, durée d'observation, qui décide (PM du pod) -->
