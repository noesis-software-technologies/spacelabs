# Workflows du harnais — parqués ici en attendant la permission « Workflows » du token

Le token fine-grained qui a poussé cette branche n'a que la permission **Contents** : GitHub refuse toute
écriture sous `.github/workflows/` sans la permission **Workflows** (c'est une protection, pas un bug).
Les 6 workflows du harnais attendent donc ici, et `ci.yml` n'est pas encore rescopé.

Activation (l'un ou l'autre) :
- ajouter au token les permissions listées dans `docs/process/HARNESS.md` §Token, puis demander à Claude de
  terminer (il fera le `git mv`, le rescope de `ci.yml`, la PR, les labels et les variables) ;
- ou, à la main sur cette branche : `make -f harness.mk install-workflows` puis `git push`.
