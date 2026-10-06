# CONTINUATION — SpaceLabs / Card show / Alkane

> État après S1 — branche `fix/s1-p0` : R1/R2/R3 corrigés dans le code ; **71/71 tests ciblés verts**, check prod, migrations et collecte réelle validés. [Preuves, configuration et révocation démo](docs/sprints/S1.md). Aucun push ni déploiement. DUCT reste KO, R4–R8 ouverts. Prochain sprint prévu : S2, sur nouvel ordre.

## 1. Identité — 5 lignes

1. Quoi : cockpit d'orchestration d'agents SpaceLabs ; extension pricing card show proposée, absente du code (`README.md:21-32`, recherche REVIEW §Vrac).
2. Pour qui : opérateurs SpaceLabs, équipe card show et équipe de développement — demande utilisateur du 2026-10-06 ; rôles pricing [proposition].
3. URL prod SpaceLabs : [non vérifié] ; destination commerciale demandée : https://alkane.app ; chemin produit [non vérifié].
4. Dépôt : https://github.com/noesis-software-technologies/spacelabs ; SHA audité `21580303ee5b18b12dfba3755a8b834df0b2c909` ; branche main ; branche déployée [non vérifié].
5. Serveur `/home/<slug>` et port gunicorn : [non vérifié] ; legacy réel Daphne/ASGI, port local 8000 (`Makefile:9`), Render `$PORT` (`render.yaml:18`).

## 2. Intention & ordres permanents

- INTENT.md absent : recherche fichiers, REVIEW annexe ; aucune copie verbatim disponible.
- [reconstitué] Piloter une flotte d'agents, un pane par agent, plusieurs workspaces et un mur d'observation ; références `README.md:21-32`, `docs/architecture.md:3-21`.
- [reconstitué] Extension souhaitée : préparer PA, marge, prix souhaité, repli 1 et repli 2 ; valider puis imprimer prix public et QR vers fiche Alkane ; orchestrer les lots depuis SpaceLabs — demande utilisateur 2026-10-06, non implémentée.
- Ordres utilisateur : dépôt fait foi ; toute affirmation exige commande/résultat ou fichier:ligne ; inconnus `[non vérifié]`, suppositions `[hypothèse]`, exigences nouvelles `[proposition]`.
- AGENTS.md/workflow_orchestration absents du checkout audité ; rechercher à nouveau au début de chaque session, ne pas supposer leur absence sur un autre SHA.
- Session de review : lecture seule code, seulement REVIEW.md et CONTINUATION.md, commit `docs: review express + continuation`, 10 min / 3 cycles ; aucune correction incluse.
- Reprises : 15 min / 6 cycles par sprint ; arrêt à budget atteint ; commit + zip + preuves + rapport ; STOP entre sprints.

## 3. État prouvé — review initiale (historique ; résultats S1 en tête)

| Contrôle isolé | Commande exacte | Résultat / durée |
|---|---|---|
| pip check | `DJANGO_SETTINGS_MODULE=config.settings.prod ../review-venv/bin/python -m pip check` | exit 0 ; 0.47 s ; No broken requirements found. |
| deploycheck | `DJANGO_SETTINGS_MODULE=config.settings.prod ../review-venv/bin/python manage.py check --deploy` | exit 1 ; 0.87 s ; ValueError: Missing staticfiles manifest entry for 'vitrine/desktop/astragso.jpg' |
| migrations | `DJANGO_SETTINGS_MODULE=config.settings.prod ../review-venv/bin/python manage.py makemigrations --check --dry-run` | exit 1 ; 0.78 s ; ValueError: Missing staticfiles manifest entry for 'vitrine/desktop/astragso.jpg' |
| tests | `-m pytest -q -p no:cacheprovider` | exit timeout ; 80 s ; 214 points succès et 17 échecs visibles ; suite interrompue, X/Y final [non vérifié] |
| static | `DJANGO_SETTINGS_MODULE=config.settings.prod ../review-venv/bin/python manage.py collectstatic --noinput --dry-run` | exit 0 ; 0.97 s ; 269 static files copied to '/workspace/scratch/add2bb5bf15b/spacelabs/staticfiles'. |


- Environnement initial sans Django ; premier pip check global vert ne prouvait pas l'installation du projet.
- Dépendances de revue dans venv externe ; profil CI sans faster-whisper (`.github/workflows/ci.yml:38-44`). Tentative complète refusée par contrôle de hash, pas contourné.
- Settings prod explicitement imposés pour check/migrations/collectstatic ; SECRET_KEY synthétique de revue, SQLite hors dépôt ; tests sous settings dev, autorun désactivé.
- Pré-vol : KO statique ; 57 lectures, 53 hors syntaxe exacte, 26 noms absents de .env.example ; duct.yaml/CHANNELS_REDIS_URL absents (table détaillée REVIEW).
- GitHub get_repo : pull=true / push=false ; commit local seulement, aucune publication distante.

## 4. Carte produit et cahier des charges complémentaire

- Verdicts structurels : clean = cohérent sur périmètre lu ; changed = extension/écart explicite ; blocked = blocage prouvé ; aucun verdict ne certifie une suite de tests complète.

| Feature | App · urls · vue · template · task/service | Verdict | Tests existants (exécution complète non vérifiée) |
|---|---|---|---|
| Auth/utilisateur | comptes/models.py · comptes/urls.py · LoginView/LogoutView · registration/login.html · bootstrap_demo.py | clean S1 code ; révocation prod [non vérifié] | comptes/tests/test_user.py |
| Workspaces/panes | apps/workspaces/models.py:48,94 · urls.py · views.py · templates/workspaces/detail.html · apps/runtime/services | clean [exécution non vérifiée] | workspaces/tests/test_views.py, test_models.py |
| Missions/board/swarm | apps/tasker/models.py:21,87 · urls.py · views.py:43-99 · templates/tasker/mission_detail.html · tasks.py/runner.py/services.py | blocked concurrence Celery/dispatch R7 | tasker/tests/test_services_s10.py, test_runner_s11.py, test_swarm_s16.py |
| Observer | apps/observer/models.py · urls.py · views.py · templates/observer/observer.html · pipeline.py | clean [exécution non vérifiée] | observer/tests/test_pipeline.py, test_views_and_ops.py |
| Chat/runtime WS | apps/chat/models.py · apps/runtime/routing.py · consumer runtime · templates/workspaces/partials · services/headless_manager.py | clean [exécution non vérifiée] | chat/tests/test_events.py, test_headless_manager.py, runtime/tests/test_consumer_s2.py |
| Ops Celery | apps/ops/models.py · urls.py · views.py · templates/ops · tasks.py/services.py | changed : queues/retry non explicites | ops/tests/test_tasks_and_views.py, test_services.py |
| Skills | apps/skills/models.py · urls.py · views.py · templates/skills · services.py | clean [exécution non vérifiée] | skills/tests/test_skills_s15.py |
| Voix | apps/voice/intents.py · urls.py · views.py · templates/workspaces/partials/_bridge.html · backends | clean structure ; STT réel [non vérifié] | voice/tests/test_bridge_s13.py, test_transcribe_view.py |
| Routage modèles | apps/models_routing/models.py · urls.py · views.py · templates/models_routing/_statusbar.html · services.py | clean S1 auth ; producteurs à configurer | models_routing/tests/test_routing_sr1.py à sr3.py |
| Vitrine | apps/vitrine/catalogue.py · urls.py · views.py · templates/vitrine · aucune task | R1 corrigé S1 ; R6 privé toujours blocked | aucun dossier dédié trouvé |
| Veille/comms | apps/veille et apps/comms models.py · urls.py · views.py · templates/veille et comms · management/commands | changed vs cockpit initial ; décrits README:62-96 ; R3/R8/R9 | aucun dossier dédié trouvé |
| Card show/pricing/QR/Alkane | aucun fichier métier trouvé via recherche REVIEW | blocked : nouvelle extension et contrat Alkane absent | aucun |

### 4.1. Périmètre fonctionnel — [proposition]

| Domaine | Exigence décidée | Critère d'acceptation |
|---|---|---|
| Architecture | App Django isolée `apps/cardshow` liée Workspace/owner ; templates héritent base.html + partials htmx ; services purs pour calcul ; pas de nouvelle SPA ni remplacement du runtime | URLs auth/owner ; migrations additives ; aucun changement au cycle de vie des panes |
| Événement | CardShow : nom, dates, devise, profil impression, workspace ; CardShowItem : identité article physique/lot, référence Alkane stable, nom, état/grade, quantité, version | unicité événement + article physique ; le même produit catalogue peut avoir plusieurs exemplaires distincts |
| Référence Alkane | Conserver identifiant produit et URL canonique fournis ; cible HTTPS sur hôte exact alkane.app ; chemin conservé sans invention | URL absente/invalide → validation et impression bloquées ; ref inexistante → erreur par ligne |
| PA et frais | PA unitaire hors frais + frais unitaires alloués non négatifs ; conserver provenance, date, devise, base de comparaison | Decimal, jamais float ; 2 décimales pour EUR ; aucun mélange devises ou HT/TTC |
| Prix | Prix de vente souhaité, repli 1, repli 2 ; sélection explicite du prix public affiché, souhaité par défaut | `PV_souhaité >= repli1 >= repli2 >= 0`; PA/frais >=0 ; prix public de vente >0 |
| Marge | Coût unitaire C=PA+frais ; marge unitaire M=P−C ; taux de marge M/C ; taux de marque M/P ; calcul pour chacun des 3 paliers | zéro au dénominateur → valeur vide + explication, jamais division par zéro ; arrondi monétaire explicite au centime |
| Base fiscale | Même base de calcul pour P, PA et frais ; conserver base HT/TTC et montant public final séparément si conversion | aucune TVA présumée ni règle automatique de TVA sur marge ; régime fiscal à fournir [non vérifié] ; incohérence bloque validation |
| Gouvernance | Agent prépare une proposition ; responsable pricing valide ; vendeur ne voit que les paliers autorisés ; approbation nominative et motif de toute dérogation | pas de vente sous repli2 ou sous coût sans autorisation explicite ; un prix conseillé n'est jamais publié automatiquement |
| Confidentialité | PA, frais, marges et replis privés ; DTO public allowlist nom/référence/état/prix/devise/URL | aucune donnée privée dans étiquette, HTML public, QR, Observer, logs publics ni payload export public |
| Révision | brouillon → validé → imprimé ; vendu/annulé séparément ; édition d'un prix validé crée une révision brouillon | étiquette = snapshot immuable de révision validée ; modification après impression → réimpression signalée |
| Audit | auteur, horodatage, ancienne/nouvelle valeur, approbation, prix réellement vendu | historique conservé ; suppression logique des fiches utilisées ; FK PROTECT sur ventes/révisions utilisées [proposition] |
| Stock | exemplaire unitaire ou quantité de lot ; réservation puis vente atomiques, version attendue | double vente et quantité négative refusées ; conflit de version visible, pas d'écrasement silencieux |

### 4.2. Impression et QR — [proposition]

- Format MVP : HTML imprimable, taille paramétrée en mm, un profil d'étiquette ; PDF via impression navigateur ; générateur QR local dédié, dépendance à sélectionner et documenter lors du sprint, aucune lib QR prétendue existante.
- Contenu : nom court, référence/exemplaire, état/grade si fourni, prix public validé lisible, devise, QR vers URL canonique ; aucune URL admin/cockpit, aucun token, aucun PA/repli dans le QR.
- Révision : lot d'impression figé, date, prix public et destination mémorisés ; réimpression identique du même snapshot ; changement de prix = nouvelle révision.
- Qualité : marge blanche QR ≥4 modules, contraste noir/blanc, aucun logo sur les modules ; taille ajustée à la densité ; scan physique à taille réelle sur deux téléphones requis.
- Réseau : génération QR et réimpression possibles hors connexion à partir du snapshot ; consultation du produit en ligne exige du réseau ; une vérification locale d'URL ne prouve pas un HTTP 200 Alkane.
- DoD : scan ouvre le bon exemplaire/produit ; prix visible = révision validée ; nom long ne coupe pas le prix/QR ; étiquette devenue obsolète identifiée dans le back-office.

### 4.3. Orchestration SpaceLabs — [proposition]

- Réutiliser Mission/Task et dépendances (`apps/tasker/models.py:21,87,106,116`) : import → contrôle → calcul → validation humaine → préparation impression → export.
- Préserver frontière : décision/DB possible en Celery ; dispatch agents dans processus ASGI qui possède les managers (`apps/tasker/runner.py:5-16`) ; traiter R7 avant automatisation de lot.
- Jobs dédiés : arguments IDs uniquement ; clé unique `(événement, article_physique, révision, opération)` ; queue nommée `cardshow` [proposition] ; statut par ligne, erreurs, progression et reprise sans doublon.
- Transactions courtes et verrouillage sur vente/révision ; lancer effets externes après commit ; retries bornés avec backoff pour erreurs transitoires, refus permanent pour erreur métier.
- Aucun recalcul opaque par LLM : service Decimal déterministe ; agents peuvent proposer et expliquer, validation humaine conserve autorité.
- Stock Alkane : API/auth/version/garanties d'idempotence [non vérifié] ; MVP import CSV + export manuel validé ; SpaceLabs conserve le snapshot événement, Alkane reste référence produit en ligne [proposition].
- Sans synchronisation de stock prouvée : réserver les exemplaires au stand ou suspendre leur vente en ligne par procédure opérateur ; aucune promesse d'absence de double vente cross-système.

### 4.4. Contrat CSV MVP — [proposition]

```text
external_product_id;canonical_url;physical_item_id;name;condition;quantity;currency;price_basis;purchase_price;allocated_costs;desired_price;fallback_1;fallback_2
```

- Import : preview, erreurs par ligne, aucune écriture partielle avant confirmation du lot ; virgule décimale normalisée à l'import, stockage Decimal ; rejeter doublons, devises/bases incompatibles et cellules ambiguës.
- Export public : `external_product_id;physical_item_id;public_price;currency;revision;canonical_url` ; neutraliser cellules de type formule pour ouverture tableur ; PA/replis exclus.
- [non vérifié] ce CSV n'est pas présenté comme format natif Alkane ; adaptateur à construire uniquement depuis contrat fourni.

### 4.5. Recette — [proposition]

| Cas | Résultat attendu |
|---|---|
| PA=80, frais=5, PV=120/R1=110/R2=100, même base | coût 85 ; marges 35/25/15 ; au PV taux marge 41,18%, taux marque 29,17% |
| PA ou frais négatifs ; R1>PV ; R2>R1 | rejet formulaire + service + contraintes pertinentes en base |
| coût=0 / prix=0 | taux correspondant vide ; prix public nul interdit |
| propriétaire étranger ou vendeur sans permission | lecture/écriture privée refusée ; CSRF actif pour toutes mutations UI |
| prix changé après impression | ancien snapshot conservé, nouvelle validation puis réimpression requise |
| QR sans URL canonique ; URL hors alkane.app | impression bloquée ; aucun chemin produit construit arbitrairement |
| double exécution job / deux ventes concurrentes | un effet par clé d'idempotence ; une seule vente acceptée |
| étiquette/QR/export/Observer | aucune occurrence de PA, frais, marges, repli1/repli2 et identifiants privés |

## 5. Démarrer en 2 minutes

- [non vérifié] durée réelle selon réseau ; commandes à exécuter dans une future session, pas exécutées comme déploiement par cette review.
- Prérequis prouvés : Python 3.12 en CI (`.github/workflows/ci.yml:34`) ; Redis via docker-compose.yml ; binaire Claude pour les agents, pas nécessaire à une page pricing.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
export DJANGO_SETTINGS_MODULE=config.settings.dev
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')"
export COCKPIT_TASKER_AUTORUN=False
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

- requirements-dev.txt inclut requirements.txt ; faster-whisper lourd/optionnel : profil CI sans lui documenté `.github/workflows/ci.yml:38-44`.
- Serveur ASGI canonique (`Makefile:9`) : `daphne -b 127.0.0.1 -p 8000 config.asgi:application` ; ne pas convertir en WSGI.
- Redis : `docker compose up -d redis` ; worker : `celery -A config worker -l info` ; beat : `celery -A config beat -l info` (`Makefile:11-12,28-32`). **R7 ouvert : ne pas activer le tick beat en même temps que dispatch ASGI sur des missions réelles avant correction.**
- Compte démo code : `pilote` / `cockpit-local`, superuser (`bootstrap_demo.py:7-16`) ; uniquement local jetable ; ne pas lancer bootstrap_demo sur déploiement public.
- Données card show : aucune fixture existante ; jeu proposé en §4.5 ; données de démo supplémentaires [non vérifié].

## 6. Déployer

| Élément | État prouvé / action décidée |
|---|---|
| Chaîne versionnée | render.yaml:13-17 : pip → migrate → collectstatic → Daphne ; bootstrap public retiré S1 ; répétition prod locale réussie, instance réelle [non vérifié] |
| DUCT/pull SSH/webhook | [non vérifié] chaîne réelle absente ; pas de duct.yaml ni deploy/webhook_listener.py |
| ASGI | conserver Daphne/Channels ; si exigence Gunicorn, worker ASGI compatible et ownership runtime à valider ; Gunicorn WSGI simple interdit pour ce cockpit |
| systemd | aucune unité livrée ; unités futures web ASGI, celery worker, beat, webhook ; `User=<slug>` non-root ; chemin /home/<slug> et port à relever sur serveur |
| Autorité | en production lire `/etc/systemd/system` et `systemctl cat` des noms réellement trouvés ; pas de nom d'unité inventé ; unit_doctor absent |
| Santé | `/healthz` répond JSON status ok (`config/urls.py:11-12,35`), ne teste ni DB/Redis ni websocket ; ajouter smoke login/WS/worker |
| Surface publique | cockpit agents local/LAN (`config/settings/prod.py:3-5`) ; QR cible Alkane seulement ; pas de cockpit exposé comme boutique |

- Avant tout push destiné à DUCT : **Configuration → Environment**, poser secrets/routage puis valider pré-vol ; aucun push/deploy réalisé ici.
- Variables existantes à fournir pour prod : `DJANGO_SETTINGS_MODULE=config.settings.prod`, `SECRET_KEY` unique, `ALLOWED_HOSTS` exact, `REDIS_URL`, base `DATABASE_URL` si hors SQLite, `COCKPIT_LAN_TOKEN` si accès LAN partagé ; `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS` selon terminaison TLS (`base.py`, `prod.py`).
- Toutes les lectures à déclarer dans futur duct.yaml : inventaire complet REVIEW §Pré-vol ; ne pas se limiter à la liste minimale précédente.
- `CHANNELS_REDIS_URL` obligatoire dans futur env.required selon contrat ; actuellement **non lu** : modifier explicitement le mapping Channels au futur sprint, ne pas croire que le déclarer suffit.
- `CSRF_TRUSTED_ORIGINS` actuellement non lu : si déploiement l'exige, ajouter une lecture conforme et les origines exactes ; aucun wildcard proposé.
- Secrets optionnels Veille/Comms/Atmosphere : uniquement si modules activés, noms dans REVIEW ; ne pas réutiliser ces identifiants pour Alkane.
- [non vérifié] sauvegarde, migration rollback, port dédié, domaine SpaceLabs, état réel des unités ; aucun déploiement déclaré prêt.

## 7. Conventions de la stack — non négociables

- Templates : zéro `{# #}` ; test `apps/common/tests/test_templates_hygiene.py:30-40` ; réutiliser base.html et htmx CSRF (`templates/base.html:28`).
- Django/Celery non épinglés à une version exacte ; conserver plages existantes jusqu'à décision documentée (requirements.txt:1,7).
- DUCT : toute lecture variable sous forme exacte `os.environ.get("NOM", "défaut")` ; caster ensuite ; pas de `get("NOM") or défaut` ; tests inclus ; déclarer `.env.example` et `duct.yaml`.
- Secrets : défaut littéral vide puis validation obligatoire fail-closed en prod ; aucun secret réel comme défaut.
- Settings prod via environnement pour web, commandes, worker et beat ; conserver ASGI et managers en mémoire, pas de migration implicite WSGI.
- Migrations additives committées ; invariants métier protégés dans service et DB ; révisions monétaires Decimal.
- Commit + zip par sprint futur ; revue actuelle limitée aux deux Markdown selon contrat utilisateur ; aucune archive/source supplémentaire dans ce commit.

## 8. Problèmes P0/P1 de la review — historique et suivi

- R1/R2/R3 : corrigés dans S1 ; activation et révocation de production non exécutées.
- R4/R5/R6/R7/R8 : ouverts. Les preuves initiales ci-dessous restent attachées au SHA audité, pas aux nouveaux numéros de ligne.

- R1 **P0 · A · apps/vitrine/views.py:14-20; config/settings/prod.py:19-22; render.yaml:15-16** · preuve : `check --deploy` et `makemigrations --check --dry-run` → `ValueError: Missing staticfiles manifest entry for 'vitrine/desktop/astragso.jpg'` sur checkout neuf ; `static()` exécuté à l'import avant collectstatic · correctif : différer la résolution des URL statiques au rendu et tester le boot prod depuis checkout neuf · effort S.
- R2 **P0 · C · render.yaml:17; apps/comptes/management/commands/bootstrap_demo.py:11-16** · preuve : build public appelle `bootstrap_demo`; crée `is_superuser=True` avec mot de passe littéral · correctif : retirer le bootstrap du déploiement public et désactiver/renouveler tout compte ainsi créé · effort S. Instance réellement exposée [non vérifié].
- R3 **P0 · C · apps/models_routing/views.py:128-144; apps/comms/views.py:33-54** · preuve : `@csrf_exempt` + `objects.create(...)`, sans authentification de l'émetteur ; garde LAN inactive si token vide (`apps/common/middleware.py:20-22`) · correctif : exiger authentification runtime et secret webhook Telegram avant écriture, validation et déduplication atomique · effort S. Exploitation distante en production [non vérifié].
- R4 **P1 · B · config/settings/base.py:47-49; apps/comms/management/commands/comms_sync_email.py:53-54; apps/chat/tests/support/fake_claude.py:23** · preuve : pré-vol statique → 53/57 lectures hors forme exacte, 26 variables non documentées dans `.env.example`, `duct.yaml` absent, `CHANNELS_REDIS_URL` absent · correctif : normaliser les lectures avec défaut littéral, déclarer toutes les variables et refuser au boot les secrets vides en prod · effort M.
- R5 **P1 · B · manage.py:7; config/asgi.py:6; config/wsgi.py:5; config/celery.py:6; deploy/comms_poll.sh:8** · preuve : défaut/forçage `config.settings.dev`; `git ls-files deploy` → uniquement 3 scripts/docs Chatwoot/comms, aucune unité ni webhook DUCT · correctif : expliciter settings prod et déploiement ASGI avec utilisateur dédié, worker/beat et webhook authentifié ; documenter exception au Gunicorn WSGI · effort M.
- R6 **P1 · C · apps/vitrine/views.py:51-77; templates/vitrine/savoir_faire.html:306-347** · preuve : vue publique charge le fichier privé et rend équipe/tarifs/KPI sans permission · correctif : contrôler la permission côté vue avant toute lecture/rendu privé · effort S. Présence du fichier privé en prod [non vérifié].
- R7 **P1 · E · apps/tasker/tasks.py:16-18; apps/tasker/services.py:102-105,251-277; config/settings/base.py:246-250** · preuve : Celery `tick_all` appelle `tick`, réserve RUNNING puis ne conserve que `len(...)`; l'envoi reste dans `runner.py:75-80` · correctif : une seule chaîne réclame puis transmet chaque assignment, ou une outbox persistante consommée par ASGI · effort M. Interleaving réel beat/ASGI [non vérifié].
- R8 **P1 · F · templates/veille/articles.html:116,137; apps/common/tests/test_templates_hygiene.py:30-40** · preuve : `rg -n '\{#' templates` → 2 occurrences ; test interdit toute occurrence · correctif : retirer les deux commentaires et exécuter le test d'hygiène · effort S.

## 9. Prochains sprints — chacun ≤15 min / ≤6 cycles

- [proposition] Premier incrément seulement ; pas une promesse de livraison intégrale du card show en 75 minutes. Tout scope excédant le budget reste ouvert avec preuves.
- Gates de publication : activation opérationnelle R1–R3 et correctifs R4–R8 à traiter ; intégration live Alkane bloquée tant que contrat absent. Ne pas masquer ces gates derrière une UI terminée.

| Sprint | Objectif visible utilisateur | DoD vérifiable / périmètre borné |
|---|---|---|
| S1 — P0 (livré dans le code) | Une démo démarre sans compte administrateur public connu ni ingestion anonyme | R1 résolution statique différée + bootstrap public retiré + endpoints R3 refusent requêtes non authentifiées ; tests ciblés des 3 risques ; check prod checkout neuf ; si budget atteint, STOP avec P0 restants, aucun déploiement |
| S2 — fiche minimale | Voir une fiche de calcul pricing avec les 3 paliers | un service Decimal + formulaire Django non persistant de prévisualisation ; exemple 80/5/120/110/100, ordre/négatifs/zéros ; auth et CSRF ; aucune publication |
| S3 — sauvegarde validée | Retrouver et valider une fiche privée | un modèle item/révision minimal + migration + formulaire S2 ; owner, prix validé figé, modification invalide validation ; tests propriétaire/version ; import massif hors scope |
| S4 — étiquette | Imprimer un prix validé avec QR du bon produit | un format HTML imprimable + QR local URL fournie + snapshot ; test absence données privées ; scan physique demandé dans recette, [non vérifié] jusqu'à réalisation |
| S5 — lot orchestration | Voir progression et erreurs d'un petit lot | sous réserve R7 résolu : une Mission import CSV validé → préparation étiquettes, IDs/idempotence, rapport par ligne et export manuel ; pas de synchro stock live |

- Backlog préalable au déploiement : pré-vol DUCT R4/R5, données privées R6, réservation/dispatch R7, hygiène R8 ; prévoir sprints séparés si non résolus, même budget et STOP.
- Après S5 : vente/réservation concurrente, annulation, stock Alkane, PDF natif/multiprofils, fiscalité, rôles affinés ; chacun nouveau sprint autorisé et borné.

## 10. Décisions & pièges

- DECISIONS.md absent : aucun extrait verbatim disponible ; `docs/architecture.md:32-33` mentionne CLAUDE/AUDIT absents et ignorés ; historique non accessible [non vérifié].
- Décision de revue : préserver Django/htmx/Channels/Daphne et Mission/Task ; app métier additive, pas de réécriture stack.
- Panne reproduite puis corrigée S1 : `static()` à l'import avec stockage manifest empêche check/migrations sur checkout neuf ; ne pas confondre collectstatic dry-run réussi avec manifeste généré.
- Panne observée : tests interrompus avec échecs, aucun résultat complet ; ne pas écrire « tests verts » depuis les anciennes docs.
- Piège : main est défaut GitHub, pas preuve de branche prod ; conteneur de revue ≠ machine déployée.
- Piège : django-environ offre des valeurs par défaut mais ne satisfait pas la syntaxe exacte DUCT demandée ; documenter migration de lecture, pas un faux succès.
- Piège : Celery qui réserve un Task ne détient pas le manager de dispatch ; l'envoi est dans runner ASGI (R7).
- Piège : prix de repli/marge internes ne doivent jamais rejoindre le mur Observer public ou la payload QR.
- Piège : taux de marge ≠ taux de marque ; ne pas comparer PA HT à vente TTC ; fiscalité Alkane [non vérifié].

## 11. Bloc de reprise — contrat à coller

```text
REPRISE — SpaceLabs / card show
Repartir du dépôt : git status --short, git log --oneline -15, git branch -a,
puis lire AGENTS.md/workflow_orchestration s'ils existent, REVIEW.md et CONTINUATION.md.
Le dépôt fait foi ; n'utiliser aucune mémoire de session comme preuve.
Vérifier le SHA et l'état non committé avant toute modification ; préserver les changements existants.
Traiter un seul sprint S<n> autorisé. Budget dur : 15 minutes / 6 cycles.
S1 traite les P0 ; ne jamais déployer avec un P0 ouvert.
Préserver Django/htmx/Channels/Daphne, ownership et conventions du §7.
Aucune API, route produit Alkane, variable déployée ou unité système inventée.
Tout constat = commande + résultat ou fichier:ligne ; inconnus [non vérifié], hypothèses [hypothèse].
Livrable : commit + zip du sprint + preuves des contrôles + rapport concis.
Budget atteint : livrer uniquement ce qui est prouvé, marquer le reste [non vérifié].
STOP entre chaque sprint ; pas de push/deploy sans autorisation correspondante.
```
