# REVIEW — SpaceLabs / préparation card show

> Mise à jour S1 (2026-10-06) : R1/R2/R3 corrigés dans le code, 71 tests ciblés verts ; preuves et limites dans [docs/sprints/S1.md](docs/sprints/S1.md). Les constats ci-dessous restent le snapshot historique du SHA audité. Aucune correction appliquée à une production réelle.

| En-tête | Valeur |
|---|---|
| Projet | noesis-software-technologies/spacelabs |
| SHA audité | `21580303ee5b18b12dfba3755a8b834df0b2c909` |
| Date | 2026-10-06, Europe/Paris ; horloge du conteneur divergente, date de session retenue |
| Branche auditée | `main`, origin/HEAD → origin/main |
| Branche déployée | [non vérifié] aucun serveur ni état de déploiement fourni ; branche par défaut ≠ preuve de prod |
| Budget | 9 min 50 s environ, sous plafond 10 min ; 3 cycles : faits → review → écriture/commit ; aucun sprint de correction |
| Contrat | Sources/templates/migrations/settings inchangés ; seuls REVIEW.md et CONTINUATION.md livrés |
| Accès GitHub | `github.get_repo(noesis-software-technologies/spacelabs)` → public, default_branch=main, pull=true, push=false ; commit local, aucun push |

## Cycle 1 — faits bruts

| Commande | Résultat |
|---|---|
| `git status --short` initial | vide, exit 0 |
| `git log --oneline -15` | 15 commits conservés en annexe ; HEAD 2158030 |
| `git branch -a` | main + 9 refs distantes (dont origin/HEAD) ; liste exacte en annexe |
| `cat requirements.txt` | Django>=5.2,<5.3 ; celery>=5.4 : pas de version exacte épinglée ; contraintes de plage conservées |
| `pip check` environnement initial | exit 0, No broken requirements found ; Django absent, ce succès ne valide pas le projet |
| `DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py check --deploy` initial | exit 1, ModuleNotFoundError django |
| `… makemigrations --check --dry-run` initial | exit 1, ModuleNotFoundError django |
| `python manage.py test` initial | exit 1 en 0,02 s, aucun test exécuté |
| `… collectstatic --noinput --dry-run` initial | exit 1, ModuleNotFoundError django |
| Installation isolée complète | `python -m venv ../review-venv` puis `pip install -r requirements.txt -r requirements-dev.txt` : échec de vérification SHA256 d'un paquet non identifié ; aucun hash désactivé |
| Installation profil CI | requirements sans faster-whisper + pytest-django/pytest-asyncio/factory-boy/django-debug-toolbar, conforme `.github/workflows/ci.yml:38-44` ; venv hors dépôt ; résultat des commandes ci-dessous fait foi |
| Carte routes | 12 fichiers urls.py, 76 appels path statiques, tableau complet ci-dessous ; WebSocket séparé dans apps/runtime/routing.py |
| `rg -n '\{#' templates` | 2 occurrences, articles.html:116,137 ; attendu 0 |
| `rg -n '\|safe|mark_safe' templates apps` | 3 `safe` ; aucun mark_safe dans le scan Python/HTML ; provenance catalogue Python, exploit XSS [non vérifié] |
| `rg -n 'csrf_exempt' apps` | 2 vues exemptes et leurs imports ; R3 |
| `rg -n 'raw\(|cursor.execute' apps config` | aucun résultat dans scan Python/HTML |
| Écritures sans login/permission | 2 endpoints R3 ; mutations observer authentifiées manuellement, ne pas les déclarer vulnérables sur absence de décorateur |
| Variables sans défaut / settings dev | 8 lectures os.environ.get à un argument ; 4 entrypoints par défaut dev + script comms force dev |
| Cookies sécurisés | prod.py:29-30 True en dur ; durcissement TLS, accès direct HTTP incompatible [hypothèse] |
| Secrets littéraux | scan de signatures clés/tokens : aucun candidat ; bootstrap_demo.py:15 mot de passe fixe ; scan non exhaustif |
| TODO/FIXME | matches TODO = enum Task.Status.TODO, pas une preuve de travail oublié ; aucun FIXME dans scan |
| Pré-vol DUCT | KO statique : pas de tools/duct_preflight.py/preflight.py/duct.yaml ; reproduction des règles ci-dessous |
| Déploiement | render.yaml démo publique Daphne + Redis ; deploy/ = comms_poll.sh + Chatwoot README/setup ; aucune unité systemd ni webhook_listener.py |
| Autorité serveur | [non vérifié] `/etc/systemd/system` de la production inaccessible ; unités vivantes feraient foi ; aucun unit_doctor trouvé |
| Instructions dépôt | recherche AGENTS.md/workflow_orchestration/INTENT/ROADMAP/DECISIONS → aucun fichier ; ordres utilisateur appliqués |

| Contrôle isolé | Commande exacte | Résultat / durée |
|---|---|---|
| pip check | `DJANGO_SETTINGS_MODULE=config.settings.prod ../review-venv/bin/python -m pip check` | exit 0 ; 0.47 s ; No broken requirements found. |
| deploycheck | `DJANGO_SETTINGS_MODULE=config.settings.prod ../review-venv/bin/python manage.py check --deploy` | exit 1 ; 0.87 s ; ValueError: Missing staticfiles manifest entry for 'vitrine/desktop/astragso.jpg' |
| migrations | `DJANGO_SETTINGS_MODULE=config.settings.prod ../review-venv/bin/python manage.py makemigrations --check --dry-run` | exit 1 ; 0.78 s ; ValueError: Missing staticfiles manifest entry for 'vitrine/desktop/astragso.jpg' |
| tests | `-m pytest -q -p no:cacheprovider` | exit timeout ; 80 s ; 214 points succès et 17 échecs visibles ; suite interrompue, X/Y final [non vérifié] |
| static | `DJANGO_SETTINGS_MODULE=config.settings.prod ../review-venv/bin/python manage.py collectstatic --noinput --dry-run` | exit 0 ; 0.97 s ; 269 static files copied to '/workspace/scratch/add2bb5bf15b/spacelabs/staticfiles'. |


## Cycle 2 — findings (risque prod puis effort, 10 maximum)

- R1 **P0 · A · apps/vitrine/views.py:14-20; config/settings/prod.py:19-22; render.yaml:15-16** · preuve : `check --deploy` et `makemigrations --check --dry-run` → `ValueError: Missing staticfiles manifest entry for 'vitrine/desktop/astragso.jpg'` sur checkout neuf ; `static()` exécuté à l'import avant collectstatic · correctif : différer la résolution des URL statiques au rendu et tester le boot prod depuis checkout neuf · effort S.
- R2 **P0 · C · render.yaml:17; apps/comptes/management/commands/bootstrap_demo.py:11-16** · preuve : build public appelle `bootstrap_demo`; crée `is_superuser=True` avec mot de passe littéral · correctif : retirer le bootstrap du déploiement public et désactiver/renouveler tout compte ainsi créé · effort S. Instance réellement exposée [non vérifié].
- R3 **P0 · C · apps/models_routing/views.py:128-144; apps/comms/views.py:33-54** · preuve : `@csrf_exempt` + `objects.create(...)`, sans authentification de l'émetteur ; garde LAN inactive si token vide (`apps/common/middleware.py:20-22`) · correctif : exiger authentification runtime et secret webhook Telegram avant écriture, validation et déduplication atomique · effort S. Exploitation distante en production [non vérifié].
- R4 **P1 · B · config/settings/base.py:47-49; apps/comms/management/commands/comms_sync_email.py:53-54; apps/chat/tests/support/fake_claude.py:23** · preuve : pré-vol statique → 53/57 lectures hors forme exacte, 26 variables non documentées dans `.env.example`, `duct.yaml` absent, `CHANNELS_REDIS_URL` absent · correctif : normaliser les lectures avec défaut littéral, déclarer toutes les variables et refuser au boot les secrets vides en prod · effort M.
- R5 **P1 · B · manage.py:7; config/asgi.py:6; config/wsgi.py:5; config/celery.py:6; deploy/comms_poll.sh:8** · preuve : défaut/forçage `config.settings.dev`; `git ls-files deploy` → uniquement 3 scripts/docs Chatwoot/comms, aucune unité ni webhook DUCT · correctif : expliciter settings prod et déploiement ASGI avec utilisateur dédié, worker/beat et webhook authentifié ; documenter exception au Gunicorn WSGI · effort M.
- R6 **P1 · C · apps/vitrine/views.py:51-77; templates/vitrine/savoir_faire.html:306-347** · preuve : vue publique charge le fichier privé et rend équipe/tarifs/KPI sans permission · correctif : contrôler la permission côté vue avant toute lecture/rendu privé · effort S. Présence du fichier privé en prod [non vérifié].
- R7 **P1 · E · apps/tasker/tasks.py:16-18; apps/tasker/services.py:102-105,251-277; config/settings/base.py:246-250** · preuve : Celery `tick_all` appelle `tick`, réserve RUNNING puis ne conserve que `len(...)`; l'envoi reste dans `runner.py:75-80` · correctif : une seule chaîne réclame puis transmet chaque assignment, ou une outbox persistante consommée par ASGI · effort M. Interleaving réel beat/ASGI [non vérifié].
- R8 **P1 · F · templates/veille/articles.html:116,137; apps/common/tests/test_templates_hygiene.py:30-40** · preuve : `rg -n '\{#' templates` → 2 occurrences ; test interdit toute occurrence · correctif : retirer les deux commentaires et exécuter le test d'hygiène · effort S.
- R9 **P2 · D · apps/veille/views.py:17-19,55-56,84-86** · preuve : une requête `b.items.all()` par blog, un count par catégorie et une recherche par lien · correctif : précharger/agréger ces listes et borner le nombre de requêtes par un test · effort S.
- R10 **P2 · H · README.md:179; docs/architecture.md:32-33; .gitignore:14-17** · preuve : liens vers ROADMAP/CLAUDE/AUDIT, fichiers absents du checkout et ignorés · correctif : publier un document de reprise versionné et corriger les liens vers les documents disponibles · effort S.

## Vrac

- A : installation initiale rejetée par contrôle hash ; paquet incriminé et cause [non vérifié], ne pas contourner l'intégrité.
- B : Channels prouvé `config/settings/base.py:61`; Redis partagé `prod.py:15`; contrat CHANNELS_REDIS_URL à ajouter explicitement au futur env.required.
- C : CSRF htmx global `templates/base.html:28`; middleware CSRF `config/settings/base.py:87` ; ALLOWED_HOSTS via env `base.py:49`, DEBUG=False `prod.py:9`; aucun CSRF_TRUSTED_ORIGINS trouvé, nécessité dépend du proxy [non vérifié].
- C : upload voix limité à 25 Mio et login/POST `apps/voice/views.py:18,29-35` ; contrôle codec complet [non vérifié].
- C : `|safe` dans landing_showroom.html:272, vitrine_v2.html:93, savoir_faire.html:377 ; proposition `json_script` avant alimentation externe.
- C : comms et veille partagent toutes les données entre utilisateurs authentifiés (`comms/views.py:16`, `veille/views.py:111`) ; séparation multi-équipe attendue [non vérifié], ne pas copier pour pricing privé.
- D : unicité workspace owner/slug `apps/workspaces/models.py:71`, tâche mission/key `apps/tasker/models.py:116`, ext_id messages `apps/comms/models.py:19` ; CASCADE workspace/panes/tasks, planner SET_NULL (`tasker/models.py:36,64,101,147,149`).
- D : Telegram exists puis create (`comms/views.py:48-50`) ; concurrence → IntegrityError [hypothèse, non testée].
- E : cinq tâches Celery sans arguments ORM (`apps/ops/tasks.py`, `apps/tasker/tasks.py`), beat déclaré `base.py:245-267`; aucune queue/retry/backoff explicite dans ces fichiers ; idempotence externe exhaustive [non vérifié].
- F : un seul templates/base.html ; partials et états vides présents (`templates/tasker/partials/_mission_list.html:19-20`, `_board.html:71-72`) ; rendu des messages Django [non vérifié].
- G : aucune occurrence alkane/card.show/pricing/prix.vente/prix.achat/QR.code dans apps/config/templates/docs/README ; fonctionnalité nouvelle, cahier complémentaire dans CONTINUATION §4.
- H : aucun dossier tests Veille/Comms/Vitrine dans inventaire ; code mort exhaustif [non vérifié].

## Pré-vol DUCT reproduit — règles et preuves

- Périmètre : `git ls-files '*.py'`, tests inclus ; AST des appels `os.environ.get`, `os.getenv`, `env` et méthodes de django-environ dans config/settings ; aucun os.environ[] / alias lecteur relevé par grep complémentaire.
- Forme acceptée : seulement `os.environ.get("NOM", "défaut")`, deux constantes chaînes, aucun fallback `or`.
- Résultat : 57 lectures / 52 noms ; 53 lectures non conformes ; django-environ typé reste valable pour Django mais hors contrat DUCT exact.
- `.env.example` : déclarations actives ET exemples commentés reconnus ; 26 noms absents. `DJANGO_SETTINGS_MODULE` consommé par Django, pas un faux positif variable inutilisée.
- `duct.yaml` absent : aucune variable attestée dans env.required ; CHANNELS_REDIS_URL absent ; avertissements variables déclarées mais non lues : [].
- `apps/veille/redaction.py` : `env.get` traite du JSON, exclu après inspection ; ne pas compter ces clés comme variables système.

| Variable manquante de .env.example | Action proposée |
|---|---|
| `ATMOSPHERE_MCP_TOKEN` | documenter défaut / caractère secret, déclarer DUCT |
| `ATMOSPHERE_MCP_URL` | documenter défaut / caractère secret, déclarer DUCT |
| `COCKPIT_AGENT_PRESETS` | documenter défaut / caractère secret, déclarer DUCT |
| `COCKPIT_MCP_AUTH_PATTERNS` | documenter défaut / caractère secret, déclarer DUCT |
| `COCKPIT_OWNER_MAX_PANES` | documenter défaut / caractère secret, déclarer DUCT |
| `COCKPIT_PRIMING_PROMPTS` | documenter défaut / caractère secret, déclarer DUCT |
| `COCKPIT_REAP_EVERY_SECONDS` | documenter défaut / caractère secret, déclarer DUCT |
| `COCKPIT_SNAPSHOT_EVERY_SECONDS` | documenter défaut / caractère secret, déclarer DUCT |
| `COCKPIT_STT_FAKE_TRANSCRIPT` | documenter défaut / caractère secret, déclarer DUCT |
| `COCKPIT_TASKER_AUTORUN` | documenter défaut / caractère secret, déclarer DUCT |
| `COCKPIT_TASKER_PLAN_TIMEOUT_SECONDS` | documenter défaut / caractère secret, déclarer DUCT |
| `COCKPIT_TASKER_TASK_TIMEOUT_SECONDS` | documenter défaut / caractère secret, déclarer DUCT |
| `COCKPIT_TASKER_TICK_SECONDS` | documenter défaut / caractère secret, déclarer DUCT |
| `COMMS_IMAP_FOLDER` | documenter défaut / caractère secret, déclarer DUCT |
| `COMMS_IMAP_HOST` | documenter défaut / caractère secret, déclarer DUCT |
| `COMMS_IMAP_PASS` | documenter défaut / caractère secret, déclarer DUCT |
| `COMMS_IMAP_USER` | documenter défaut / caractère secret, déclarer DUCT |
| `COMMS_TG_TOKEN` | documenter défaut / caractère secret, déclarer DUCT |
| `DATABASE_URL` | documenter défaut / caractère secret, déclarer DUCT |
| `DEBUG` | documenter défaut / caractère secret, déclarer DUCT |
| `FAKE_CLAUDE_ARGV_LOG` | documenter défaut / caractère secret, déclarer DUCT |
| `PEXELS_API_KEY` | documenter défaut / caractère secret, déclarer DUCT |
| `VEILLE_IMAP_FROM` | documenter défaut / caractère secret, déclarer DUCT |
| `VEILLE_IMAP_HOST` | documenter défaut / caractère secret, déclarer DUCT |
| `VEILLE_IMAP_PASS` | documenter défaut / caractère secret, déclarer DUCT |
| `VEILLE_IMAP_USER` | documenter défaut / caractère secret, déclarer DUCT |

| Lecture | Variable | Forme exacte conforme |
|---|---|---|
| `apps/chat/tests/support/fake_claude.py:23` | `FAKE_CLAUDE_ARGV_LOG` | non |
| `apps/comms/management/commands/comms_sync_email.py:55` | `COMMS_IMAP_HOST` | oui |
| `apps/comms/management/commands/comms_sync_email.py:56` | `COMMS_IMAP_FOLDER` | oui |
| `apps/comms/management/commands/comms_sync_email.py:53` | `COMMS_IMAP_USER` | non |
| `apps/comms/management/commands/comms_sync_email.py:53` | `VEILLE_IMAP_USER` | non |
| `apps/comms/management/commands/comms_sync_email.py:54` | `COMMS_IMAP_PASS` | non |
| `apps/comms/management/commands/comms_sync_email.py:54` | `VEILLE_IMAP_PASS` | non |
| `apps/comms/management/commands/comms_sync_telegram.py:33` | `COMMS_TG_TOKEN` | non |
| `apps/veille/management/commands/veille_sync.py:143` | `VEILLE_IMAP_USER` | non |
| `apps/veille/management/commands/veille_sync.py:144` | `VEILLE_IMAP_PASS` | non |
| `apps/veille/management/commands/veille_sync.py:145` | `VEILLE_IMAP_HOST` | oui |
| `apps/veille/management/commands/veille_sync.py:146` | `VEILLE_IMAP_FROM` | oui |
| `config/settings/base.py:47` | `SECRET_KEY` | non |
| `config/settings/base.py:48` | `DEBUG` | non |
| `config/settings/base.py:49` | `ALLOWED_HOSTS` | non |
| `config/settings/base.py:125` | `LANDING_DEFAULT` | non |
| `config/settings/base.py:128` | `ATMOSPHERE_MCP_URL` | non |
| `config/settings/base.py:129` | `ATMOSPHERE_MCP_TOKEN` | non |
| `config/settings/base.py:132` | `PEXELS_API_KEY` | non |
| `config/settings/base.py:144` | `LANGUAGE_CODE` | non |
| `config/settings/base.py:150` | `TIME_ZONE` | non |
| `config/settings/base.py:165` | `REDIS_URL` | non |
| `config/settings/base.py:166` | `REDIS_URL` | non |
| `config/settings/base.py:171` | `COCKPIT_MAX_PANES` | non |
| `config/settings/base.py:173` | `COCKPIT_OWNER_MAX_PANES` | non |
| `config/settings/base.py:174` | `COCKPIT_BUFFER_BYTES` | non |
| `config/settings/base.py:176` | `COCKPIT_OBSERVER_MAX_TILES` | non |
| `config/settings/base.py:177` | `COCKPIT_DEFAULT_CMD` | non |
| `config/settings/base.py:180` | `COCKPIT_ALLOWED_CMDS` | non |
| `config/settings/base.py:186` | `COCKPIT_AGENT_PRESETS` | non |
| `config/settings/base.py:208` | `COCKPIT_CLAUDE_BIN` | non |
| `config/settings/base.py:212` | `COCKPIT_CLAUDE_HEADLESS_ARGS` | non |
| `config/settings/base.py:218` | `COCKPIT_HEARTBEAT_STALE_SECONDS` | non |
| `config/settings/base.py:219` | `COCKPIT_EVENTLOG_RETENTION_DAYS` | non |
| `config/settings/base.py:220` | `COCKPIT_EVENTLOG_ARCHIVE_DIR` | non |
| `config/settings/base.py:221` | `COCKPIT_MCP_AUTH_PATTERNS` | non |
| `config/settings/base.py:222` | `COCKPIT_USAGE_CMD` | non |
| `config/settings/base.py:226` | `COCKPIT_RESUME_ON_BOOT` | non |
| `config/settings/base.py:228` | `COCKPIT_LAN_TOKEN` | non |
| `config/settings/base.py:229` | `COCKPIT_TASKER_TASK_TIMEOUT_SECONDS` | non |
| `config/settings/base.py:230` | `COCKPIT_TASKER_PLAN_TIMEOUT_SECONDS` | non |
| `config/settings/base.py:232` | `COCKPIT_TASKER_AUTORUN` | non |
| `config/settings/base.py:237` | `COCKPIT_STT_BACKEND` | non |
| `config/settings/base.py:238` | `COCKPIT_STT_MODEL` | non |
| `config/settings/base.py:239` | `COCKPIT_STT_DEVICE` | non |
| `config/settings/base.py:240` | `COCKPIT_STT_COMPUTE_TYPE` | non |
| `config/settings/base.py:241` | `COCKPIT_STT_LANGUAGE` | non |
| `config/settings/base.py:242` | `COCKPIT_STT_FAKE_TRANSCRIPT` | non |
| `config/settings/base.py:269` | `COCKPIT_PRIMING_PROMPTS` | non |
| `config/settings/base.py:116` | `DATABASE_URL` | non |
| `config/settings/base.py:249` | `COCKPIT_TASKER_TICK_SECONDS` | non |
| `config/settings/base.py:253` | `COCKPIT_SNAPSHOT_EVERY_SECONDS` | non |
| `config/settings/base.py:257` | `COCKPIT_REAP_EVERY_SECONDS` | non |
| `config/settings/prod.py:10` | `SECRET_KEY` | non |
| `config/settings/prod.py:25` | `SECURE_SSL_REDIRECT` | non |
| `config/settings/prod.py:26` | `SECURE_HSTS_SECONDS` | non |
| `config/settings/prod.py:15` | `REDIS_URL` | non |

## Carte complète des routes HTTP

- Auth listée au niveau vue ; garde LAN éventuelle supplémentaire `apps/common/middleware.py:18-35` ; public ne signifie pas exposé sur Internet.
- Routes incluses conservées avec leurs sous-routes ; routes conditionnelles debug et médias : `config/urls.py:41-47`.

| App | Route | Vue | Auth requise | Preuve |
|---|---|---|---|---|
| comms | `/comms/` | `views.inbox` | login_required | `apps/comms/urls.py:8` ; `apps/comms/views.py:15` |
| comms | `/comms/telegram/webhook/` | `views.telegram_webhook` | publique (garde LAN globale éventuelle) | `apps/comms/urls.py:9` ; `apps/comms/views.py:34` |
| comptes | `/auth/login/` | `auth_views.LoginView.as_view(template_name='registration/login.html')` | LoginView / LogoutView Django (CSRF middleware) | `apps/comptes/urls.py:7` ; `apps/comptes/urls.py:7` |
| comptes | `/auth/logout/` | `auth_views.LogoutView.as_view()` | LoginView / LogoutView Django (CSRF middleware) | `apps/comptes/urls.py:8` ; `apps/comptes/urls.py:8` |
| models_routing | `/routage/statusbar/<slug:slug>/` | `views.statusbar_fragment` | login_required | `apps/models_routing/urls.py:8` ; `apps/models_routing/views.py:23` |
| models_routing | `/routage/runs/` | `views.runs_panel` | login_required | `apps/models_routing/urls.py:9` ; `apps/models_routing/views.py:42` |
| models_routing | `/routage/openclaw-stats/` | `views.openclaw_stats` | login_required | `apps/models_routing/urls.py:10` ; `apps/models_routing/views.py:52` |
| models_routing | `/routage/openclaw-stats/stream/` | `views.openclaw_stats_stream` | login_required | `apps/models_routing/urls.py:11` ; `apps/models_routing/views.py:102` |
| models_routing | `/routage/openclaw-stats/log/` | `views.openclaw_log_exchange` | publique (garde LAN globale éventuelle) | `apps/models_routing/urls.py:12` ; `apps/models_routing/views.py:130` |
| observer | `/observer/` | `views.observer_page` | publique (garde LAN globale éventuelle) | `apps/observer/urls.py:8` ; `apps/observer/views.py:37` |
| observer | `/observer/grille/` | `views.observer_grid` | publique (garde LAN globale éventuelle) | `apps/observer/urls.py:9` ; `apps/observer/views.py:77` |
| observer | `/observer/stream/` | `views.observer_stream` | publique (garde LAN globale éventuelle) | `apps/observer/urls.py:10` ; `apps/observer/views.py:81` |
| observer | `/observer/regie/` | `views.regie` | login_required | `apps/observer/urls.py:11` ; `apps/observer/views.py:130` |
| observer | `/observer/regie/regles/nouvelle/` | `views.rule_create` | request.auser() + owner + POST | `apps/observer/urls.py:12` ; `apps/observer/views.py:156` |
| observer | `/observer/regie/regles/<int:rule_id>/supprimer/` | `views.rule_delete` | request.auser() + owner + POST | `apps/observer/urls.py:13` ; `apps/observer/views.py:176` |
| ops | `/ops/jauges/` | `views.gauges` | login_required | `apps/ops/urls.py:8` ; `apps/ops/views.py:16` |
| ops | `/ops/mcp/<int:alert_id>/resoudre/` | `views.resolve_mcp` | login_required | `apps/ops/urls.py:9` ; `apps/ops/views.py:41` |
| skills | `/skills/w/<slug:slug>/` | `views.panel` | login_required | `apps/skills/urls.py:8` ; `apps/skills/views.py:15` |
| skills | `/skills/<int:pk>/appliquer/` | `views.apply` | login_required | `apps/skills/urls.py:9` ; `apps/skills/views.py:25` |
| tasker | `/missions/w/<slug:slug>/` | `views.mission_list` | login_required | `apps/tasker/urls.py:8` ; `apps/tasker/views.py:44` |
| tasker | `/missions/w/<slug:slug>/nouvelle/` | `views.mission_create` | login_required | `apps/tasker/urls.py:9` ; `apps/tasker/views.py:53` |
| tasker | `/missions/<int:pk>/` | `views.mission` | login_required | `apps/tasker/urls.py:10` ; `apps/tasker/views.py:68` |
| tasker | `/missions/<int:pk>/swarm/` | `views.swarm` | login_required | `apps/tasker/urls.py:11` ; `apps/tasker/views.py:119` |
| tasker | `/missions/<int:pk>/etat/` | `views.mission_state` | login_required | `apps/tasker/urls.py:12` ; `apps/tasker/views.py:106` |
| tasker | `/missions/<int:pk>/planifier/` | `views.mission_plan` | login_required | `apps/tasker/urls.py:13` ; `apps/tasker/views.py:141` |
| tasker | `/missions/<int:pk>/supprimer/` | `views.mission_delete` | login_required | `apps/tasker/urls.py:14` ; `apps/tasker/views.py:186` |
| tasker | `/missions/<int:pk>/taches/` | `views.task_create` | login_required | `apps/tasker/urls.py:15` ; `apps/tasker/views.py:77` |
| tasker | `/missions/<int:pk>/taches/<int:task_id>/deplacer/` | `views.task_move` | login_required | `apps/tasker/urls.py:16` ; `apps/tasker/views.py:91` |
| veille | `/veille/` | `views.dashboard` | login_required | `apps/veille/urls.py:8` ; `apps/veille/views.py:16` |
| veille | `/veille/articles/` | `views.articles` | login_required | `apps/veille/urls.py:9` ; `apps/veille/views.py:43` |
| veille | `/veille/articles/<int:pk>/` | `views.article_detail` | login_required | `apps/veille/urls.py:10` ; `apps/veille/views.py:74` |
| veille | `/veille/articles/<int:pk>/edit/` | `views.article_edit` | login_required | `apps/veille/urls.py:11` ; `apps/veille/views.py:95` |
| veille | `/veille/articles/<int:pk>/save/` | `views.article_save` | login_required | `apps/veille/urls.py:12` ; `apps/veille/views.py:109` |
| veille | `/veille/articles/<int:pk>/quick/` | `views.article_quick` | login_required | `apps/veille/urls.py:13` ; `apps/veille/views.py:174` |
| veille | `/veille/articles/<int:pk>/publish/` | `views.article_publish` | login_required | `apps/veille/urls.py:14` ; `apps/veille/views.py:194` |
| veille | `/veille/articles/<int:pk>/publish-related/` | `views.article_publish_related` | login_required | `apps/veille/urls.py:15` ; `apps/veille/views.py:238` |
| veille | `/veille/mcp/status-refresh/` | `views.mcp_status_refresh` | login_required | `apps/veille/urls.py:16` ; `apps/veille/views.py:257` |
| vitrine | `/vitrine/` | `views.vitrine` | publique (garde LAN globale éventuelle) | `apps/vitrine/urls.py:8` ; `apps/vitrine/views.py:37` |
| vitrine | `/vitrine/constellation/` | `views.vitrine_v2` | publique (garde LAN globale éventuelle) | `apps/vitrine/urls.py:9` ; `apps/vitrine/views.py:82` |
| vitrine | `/vitrine/savoir-faire/` | `views.savoir_faire` | publique (garde LAN globale éventuelle) | `apps/vitrine/urls.py:10` ; `apps/vitrine/views.py:51` |
| voice | `/voice/transcribe/` | `views.transcribe` | login_required | `apps/voice/urls.py:8` ; `apps/voice/views.py:23` |
| voice | `/voice/commande/` | `views.command` | login_required | `apps/voice/urls.py:9` ; `apps/voice/views.py:47` |
| workspaces | `/cockpit/` | `views.home` | login_required | `apps/workspaces/urls.py:8` ; `apps/workspaces/views.py:40` |
| workspaces | `/cockpit/nouveau/` | `views.create` | login_required | `apps/workspaces/urls.py:9` ; `apps/workspaces/views.py:83` |
| workspaces | `/cockpit/sidebar/` | `views.sidebar` | login_required | `apps/workspaces/urls.py:10` ; `apps/workspaces/views.py:194` |
| workspaces | `/cockpit/<slug:slug>/fichiers/` | `views.explorer` | login_required | `apps/workspaces/urls.py:11` ; `apps/workspaces/views.py:203` |
| workspaces | `/cockpit/<slug:slug>/fichier/` | `views.file_view` | login_required | `apps/workspaces/urls.py:12` ; `apps/workspaces/views.py:222` |
| workspaces | `/cockpit/<slug:slug>/` | `views.detail` | login_required | `apps/workspaces/urls.py:13` ; `apps/workspaces/views.py:49` |
| workspaces | `/cockpit/<slug:slug>/renommer/` | `views.update` | login_required | `apps/workspaces/urls.py:14` ; `apps/workspaces/views.py:100` |
| workspaces | `/cockpit/<slug:slug>/supprimer/` | `views.delete` | login_required | `apps/workspaces/urls.py:15` ; `apps/workspaces/views.py:117` |
| workspaces | `/cockpit/<slug:slug>/agents/` | `views.agent_picker` | login_required | `apps/workspaces/urls.py:16` ; `apps/workspaces/views.py:168` |
| workspaces | `/cockpit/<slug:slug>/panes/<str:kind>/nouveau/` | `views.pane_create` | login_required | `apps/workspaces/urls.py:17` ; `apps/workspaces/views.py:132` |
| workspaces | `/cockpit/<slug:slug>/panes/<int:pane_id>/supprimer/` | `views.pane_delete` | login_required | `apps/workspaces/urls.py:18` ; `apps/workspaces/views.py:180` |
| workspaces | `/cockpit/<slug:slug>/historique/` | `views.history_flux` | login_required | `apps/workspaces/urls.py:19` ; `apps/workspaces/views.py:242` |
| workspaces | `/cockpit/<slug:slug>/obsidian/` | `views.obsidian_export` | login_required | `apps/workspaces/urls.py:20` ; `apps/workspaces/views.py:276` |
| config | `/` | `landing` | publique (garde LAN globale éventuelle) | `config/urls.py:16` ; `config/urls.py:16` |
| config | `/v2/` | `TemplateView.as_view(template_name='landing_v2.html')` | publique (garde LAN globale éventuelle) | `config/urls.py:17` ; `config/urls.py:17` |
| config | `/v3/` | `TemplateView.as_view(template_name='landing_v3.html')` | publique (garde LAN globale éventuelle) | `config/urls.py:18` ; `config/urls.py:18` |
| config | `/v4/` | `TemplateView.as_view(template_name='landing_v4.html')` | publique (garde LAN globale éventuelle) | `config/urls.py:19` ; `config/urls.py:19` |
| config | `/v5/` | `TemplateView.as_view(template_name='landing_v5.html')` | publique (garde LAN globale éventuelle) | `config/urls.py:20` ; `config/urls.py:20` |
| config | `/v6/` | `TemplateView.as_view(template_name='landing_v6.html')` | publique (garde LAN globale éventuelle) | `config/urls.py:21` ; `config/urls.py:21` |
| config | `/auth/` | `include('apps.comptes.urls')` | voir sous-routes | `config/urls.py:22` ; `config/urls.py:22` |
| config | `/cockpit/` | `include('apps.workspaces.urls')` | voir sous-routes | `config/urls.py:23` ; `config/urls.py:23` |
| config | `/observer/` | `include('apps.observer.urls')` | voir sous-routes | `config/urls.py:24` ; `config/urls.py:24` |
| config | `/ops/` | `include('apps.ops.urls')` | voir sous-routes | `config/urls.py:25` ; `config/urls.py:25` |
| config | `/missions/` | `include('apps.tasker.urls')` | voir sous-routes | `config/urls.py:26` ; `config/urls.py:26` |
| config | `/skills/` | `include('apps.skills.urls')` | voir sous-routes | `config/urls.py:27` ; `config/urls.py:27` |
| config | `/voice/` | `include('apps.voice.urls')` | voir sous-routes | `config/urls.py:28` ; `config/urls.py:28` |
| config | `/routage/` | `include('apps.models_routing.urls')` | voir sous-routes | `config/urls.py:29` ; `config/urls.py:29` |
| config | `/vitrine/` | `include('apps.vitrine.urls')` | voir sous-routes | `config/urls.py:30` ; `config/urls.py:30` |
| config | `/veille/` | `include('apps.veille.urls')` | voir sous-routes | `config/urls.py:31` ; `config/urls.py:31` |
| config | `/comms/` | `include('apps.comms.urls')` | voir sous-routes | `config/urls.py:32` ; `config/urls.py:32` |
| config | `/dashboard/` | `spacelabs_dashboard` | login_required (config/dashboard_view.py:6) | `config/urls.py:33` ; `config/urls.py:33` |
| config | `/django-admin/` | `admin.site.urls` | admin Django staff | `config/urls.py:34` ; `config/urls.py:34` |
| config | `/healthz` | `healthz` | publique (garde LAN globale éventuelle) | `config/urls.py:35` ; `config/urls.py:35` |
| config | `/__debug__/` | `include('debug_toolbar.urls')` | voir sous-routes | `config/urls.py:42` ; `config/urls.py:42` |

## Non vérifié — limites explicites

| Point | Motif |
|---|---|
| Branche/URL prod, slug /home/<slug>, port dédié, unités actives, webhook réel | pas d'accès serveur fourni ; ne pas assimiler conteneur de revue au serveur |
| Exploitation sécurité en prod et comptes réellement présents | audit statique, pas d'écriture distante |
| API, auth, données, stock et URL canonique produit Alkane | dépôt Alkane et contrat d'API non fournis ; aucun chemin produit inventé |
| Pré-vol officiel DUCT | script/manifest absents ; contrôle statique reproduit, pas un déploiement validé |
| Réseau Redis, workers/beat et WebSocket en prod | services non lancés ; tests isolés seulement |
| Schéma réel prod / données / backup / concurrence réelle | aucune base de production consultée |
| STT faster-whisper | dépendance optionnelle exclue du profil CI ; aucune transcription réelle |
| Exécution nouvelle revue après correctifs | aucun correctif de code autorisé dans cette session |

## Annexe — commandes et sorties conservées

### instructions

Commande : `rg --files --hidden -g '!**/.git/**' -g 'AGENTS.md' -g '*workflow*' -g 'INTENT.md' -g 'ROADMAP.md' -g 'DECISIONS.md'`

Exit : 1 ; durée : 0.02 s.

```text
(sortie vide)
```

### status

Commande : `git status --short`

Exit : 0 ; durée : 0.07 s.

```text
(sortie vide)
```

### log

Commande : `git log --oneline -15`

Exit : 0 ; durée : 0.01 s.

```text
2158030 Merge pull request #5 from noesis-software-technologies/feat/headless-default-opus-4-6
12b348a feat(veille): panneau de suivi publication + cascade récursive de la constellation
61ecc13 feat(veille): cohérence de la constellation — suggérer/pousser les articles liés manquants
e9d9c7a feat(veille): quick-view pop-up + suppression image + reorder + publication draft depuis l'UI
a66bb8e fix(veille): meta_keywords envoyé en chaîne au MCP (le serveur attend str, pas list)
a96b35e feat(veille): fallback images libres de droit Pexels (veille_pexels)
540d477 feat(veille): veille_mcp_ping — test de connexion/sécurité du MCP 13 Atmosphère
0c18a43 feat(veille): panneau de revue avant publication (cover, galerie drag-n-drop, date, slugs)
6646e0f feat(veille): veille_draft rapporte le coût/usage claude par lot
d6933ad feat(veille): client de publication MCP 13 Atmosphère (veille_publish)
03a1048 feat(veille): veille_draft ignore les communiqués sans corps (option --allow-empty pour forcer)
10274af chore(settings): charge .env.local (secrets locaux : IMAP veille/comms) après .env
4e39b49 feat(veille): ingestion robuste des mails — fallback HTML, pièces jointes image, liens
437f501 feat(veille): SEO/méta, sauvegarde locale des images, inter-maillage, export MCP
f0621bf feat(veille): article list view + image de référence + carrousel

```

### branches

Commande : `git branch -a`

Exit : 0 ; durée : 0.01 s.

```text
* main
  remotes/origin/HEAD -> origin/main
  remotes/origin/chore/release-harness
  remotes/origin/feat/headless-default-opus-4-6
  remotes/origin/feat/model-routing-sr1
  remotes/origin/feat/model-routing-sr2
  remotes/origin/feat/model-routing-sr3
  remotes/origin/feat/workspace-mohamed-history-rag-obsidian
  remotes/origin/fix/main-green-ci
  remotes/origin/main

```

### sha

Commande : `git rev-parse HEAD`

Exit : 0 ; durée : 0.01 s.

```text
21580303ee5b18b12dfba3755a8b834df0b2c909

```

### requirements

Commande : `cat requirements.txt`

Exit : 0 ; durée : 0.01 s.

```text
Django>=5.2,<5.3
channels>=4.2
channels-redis>=4.2
daphne>=4.1
django-htmx>=1.19
django-environ>=0.11
celery>=5.4
redis>=5.0
whitenoise>=6.7
ptyprocess>=0.7 ; sys_platform != "win32"    # PTY POSIX (Linux/macOS)
pywinpty>=2.0 ; sys_platform == "win32"       # PTY Windows (ConPTY)
faster-whisper>=1.0  # STT serveur (CrisperWhisper) — Sprint 7, optionnel
httpx>=0.27  # adapter OpenAI-compatible (ADR-5, models_routing)

```

### pip

Commande : `pip check`

Exit : 0 ; durée : 0.86 s.

```text
No broken requirements found.

```

### settings

Commande : `cat config/settings/prod.py`

Exit : 0 ; durée : 0.01 s.

```text
"""Prod locale durcie — `manage.py check --deploy` doit être vert avec ce module.

« Prod » = l'instance qui tourne pendant les lives, exposée au LAN uniquement.
Le cockpit spawne des process avec les droits de l'utilisateur : ne JAMAIS
l'exposer sur Internet (voir README, section Sécurité).
"""
from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = env("SECRET_KEY")  # noqa: F405 — obligatoire, pas de défaut en prod

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [env("REDIS_URL")]},  # noqa: F405
    },
}

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# HTTPS/HSTS : servi en LAN derrière un reverse proxy TLS local (ex. caddy).
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)  # noqa: F405
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

```

### deploycheck

Commande : `DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py check --deploy`

Exit : 1 ; durée : 0.03 s.

```text
Traceback (most recent call last):
  File "/workspace/scratch/add2bb5bf15b/spacelabs/manage.py", line 14, in <module>
    main()
  File "/workspace/scratch/add2bb5bf15b/spacelabs/manage.py", line 8, in main
    from django.core.management import execute_from_command_line
ModuleNotFoundError: No module named 'django'

```

### migrations

Commande : `DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py makemigrations --check --dry-run`

Exit : 1 ; durée : 0.02 s.

```text
Traceback (most recent call last):
  File "/workspace/scratch/add2bb5bf15b/spacelabs/manage.py", line 14, in <module>
    main()
  File "/workspace/scratch/add2bb5bf15b/spacelabs/manage.py", line 8, in main
    from django.core.management import execute_from_command_line
ModuleNotFoundError: No module named 'django'

```

### tests

Commande : `python manage.py test`

Exit : 1 ; durée : 0.02 s.

```text
Traceback (most recent call last):
  File "/workspace/scratch/add2bb5bf15b/spacelabs/manage.py", line 14, in <module>
    main()
  File "/workspace/scratch/add2bb5bf15b/spacelabs/manage.py", line 8, in main
    from django.core.management import execute_from_command_line
ModuleNotFoundError: No module named 'django'

```

### static

Commande : `DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py collectstatic --noinput --dry-run`

Exit : 1 ; durée : 0.02 s.

```text
Traceback (most recent call last):
  File "/workspace/scratch/add2bb5bf15b/spacelabs/manage.py", line 14, in <module>
    main()
  File "/workspace/scratch/add2bb5bf15b/spacelabs/manage.py", line 8, in main
    from django.core.management import execute_from_command_line
ModuleNotFoundError: No module named 'django'

```

### routes

Commande : `rg -n '' -g urls.py`

Exit : 1 ; durée : 0.01 s.

```text
(sortie vide)
```

### greps

Commande : `rg -n '\{#|\|safe|mark_safe|csrf_exempt|raw\(|cursor.execute|os.environ.get\(|config.settings.dev|SESSION_COOKIE_SECURE|CSRF_COOKIE_SECURE|TODO|FIXME' --glob '*.py' --glob '*.html' --glob '!**/migrations/**'`

Exit : 1 ; durée : 0.01 s.

```text
(sortie vide)
```

### preflightfiles

Commande : `rg --files --hidden -g '!**/.git/**' | rg '(preflight|duct.yaml|env.example|deploy/|unit_doctor)'`

Exit : 0 ; durée : 0.02 s.

```text
deploy/chatwoot/README.md
deploy/comms_poll.sh
deploy/chatwoot/setup.sh

```

### deployfiles

Commande : `find deploy -maxdepth 3 -type f`

Exit : 0 ; durée : 0.01 s.

```text
deploy/comms_poll.sh
deploy/chatwoot/setup.sh
deploy/chatwoot/README.md

```

### intent

Commande : `rg -n 'workflow_orchestration|INTENT|ROADMAP|DECISIONS' .github docs README.md`

Exit : 0 ; durée : 0.01 s.

```text
README.md:179:[`ROADMAP.md`](ROADMAP.md). Contributions bienvenues — lire

```

### instructions-corrected

Commande : `rg --files --hidden -g '!**/.git/**' -g 'AGENTS.md' -g '*workflow*' -g 'INTENT.md' -g 'ROADMAP.md' -g 'DECISIONS.md' .`

Exit : 1 ; durée : 0.02 s.

```text
(sortie vide)
```

### routes-corrected

Commande : `rg -n '' -g urls.py .`

Exit : 0 ; durée : 0.02 s.

```text
./apps/vitrine/urls.py:1:from django.urls import path
./apps/vitrine/urls.py:2:
./apps/vitrine/urls.py:3:from . import views
./apps/vitrine/urls.py:4:
./apps/vitrine/urls.py:5:app_name = "vitrine"
./apps/vitrine/urls.py:6:
./apps/vitrine/urls.py:7:urlpatterns = [
./apps/vitrine/urls.py:8:    path("", views.vitrine, name="index"),
./apps/vitrine/urls.py:9:    path("constellation/", views.vitrine_v2, name="v2"),
./apps/vitrine/urls.py:10:    path("savoir-faire/", views.savoir_faire, name="savoir_faire"),
./apps/vitrine/urls.py:11:]
./apps/skills/urls.py:1:from django.urls import path
./apps/skills/urls.py:2:
./apps/skills/urls.py:3:from . import views
./apps/skills/urls.py:4:
./apps/skills/urls.py:5:app_name = "skills"
./apps/skills/urls.py:6:
./apps/skills/urls.py:7:urlpatterns = [
./apps/skills/urls.py:8:    path("w/<slug:slug>/", views.panel, name="panel"),
./apps/skills/urls.py:9:    path("<int:pk>/appliquer/", views.apply, name="apply"),
./apps/skills/urls.py:10:]
./apps/voice/urls.py:1:from django.urls import path
./apps/voice/urls.py:2:
./apps/voice/urls.py:3:from . import views
./apps/voice/urls.py:4:
./apps/voice/urls.py:5:app_name = "voice"
./apps/voice/urls.py:6:
./apps/voice/urls.py:7:urlpatterns = [
./apps/voice/urls.py:8:    path("transcribe/", views.transcribe, name="transcribe"),
./apps/voice/urls.py:9:    path("commande/", views.command, name="command"),
./apps/voice/urls.py:10:]
./apps/observer/urls.py:1:from django.urls import path
./apps/observer/urls.py:2:
./apps/observer/urls.py:3:from . import views
./apps/observer/urls.py:4:
./apps/observer/urls.py:5:app_name = "observer"
./apps/observer/urls.py:6:
./apps/observer/urls.py:7:urlpatterns = [
./apps/observer/urls.py:8:    path("", views.observer_page, name="page"),
./apps/observer/urls.py:9:    path("grille/", views.observer_grid, name="grid"),
./apps/observer/urls.py:10:    path("stream/", views.observer_stream, name="stream"),
./apps/observer/urls.py:11:    path("regie/", views.regie, name="regie"),
./apps/observer/urls.py:12:    path("regie/regles/nouvelle/", views.rule_create, name="rule_create"),
./apps/observer/urls.py:13:    path("regie/regles/<int:rule_id>/supprimer/", views.rule_delete, name="rule_delete"),
./apps/observer/urls.py:14:]
./apps/comms/urls.py:1:from django.urls import path
./apps/comms/urls.py:2:
./apps/comms/urls.py:3:from . import views
./apps/comms/urls.py:4:
./apps/comms/urls.py:5:app_name = "comms"
./apps/comms/urls.py:6:
./apps/comms/urls.py:7:urlpatterns = [
./apps/comms/urls.py:8:    path("", views.inbox, name="inbox"),
./apps/comms/urls.py:9:    path("telegram/webhook/", views.telegram_webhook, name="telegram_webhook"),
./apps/comms/urls.py:10:]
./apps/workspaces/urls.py:1:from django.urls import path
./apps/workspaces/urls.py:2:
./apps/workspaces/urls.py:3:from . import views
./apps/workspaces/urls.py:4:
./apps/workspaces/urls.py:5:app_name = "workspaces"
./apps/workspaces/urls.py:6:
./apps/workspaces/urls.py:7:urlpatterns = [
./apps/workspaces/urls.py:8:    path("", views.home, name="home"),
./apps/workspaces/urls.py:9:    path("nouveau/", views.create, name="create"),
./apps/workspaces/urls.py:10:    path("sidebar/", views.sidebar, name="sidebar"),
./apps/workspaces/urls.py:11:    path("<slug:slug>/fichiers/", views.explorer, name="explorer"),
./apps/workspaces/urls.py:12:    path("<slug:slug>/fichier/", views.file_view, name="file"),
./apps/workspaces/urls.py:13:    path("<slug:slug>/", views.detail, name="detail"),
./apps/workspaces/urls.py:14:    path("<slug:slug>/renommer/", views.update, name="update"),
./apps/workspaces/urls.py:15:    path("<slug:slug>/supprimer/", views.delete, name="delete"),
./apps/workspaces/urls.py:16:    path("<slug:slug>/agents/", views.agent_picker, name="agent_picker"),
./apps/workspaces/urls.py:17:    path("<slug:slug>/panes/<str:kind>/nouveau/", views.pane_create, name="pane_create"),
./apps/workspaces/urls.py:18:    path("<slug:slug>/panes/<int:pane_id>/supprimer/", views.pane_delete, name="pane_delete"),
./apps/workspaces/urls.py:19:    path("<slug:slug>/historique/", views.history_flux, name="history_flux"),
./apps/workspaces/urls.py:20:    path("<slug:slug>/obsidian/", views.obsidian_export, name="obsidian_export"),
./apps/workspaces/urls.py:21:]
./apps/veille/urls.py:1:from django.urls import path
./apps/veille/urls.py:2:
./apps/veille/urls.py:3:from . import views
./apps/veille/urls.py:4:
./apps/veille/urls.py:5:app_name = "veille"
./apps/veille/urls.py:6:
./apps/veille/urls.py:7:urlpatterns = [
./apps/veille/urls.py:8:    path("", views.dashboard, name="dashboard"),
./apps/veille/urls.py:9:    path("articles/", views.articles, name="articles"),
./apps/veille/urls.py:10:    path("articles/<int:pk>/", views.article_detail, name="article_detail"),
./apps/veille/urls.py:11:    path("articles/<int:pk>/edit/", views.article_edit, name="article_edit"),
./apps/veille/urls.py:12:    path("articles/<int:pk>/save/", views.article_save, name="article_save"),
./apps/veille/urls.py:13:    path("articles/<int:pk>/quick/", views.article_quick, name="article_quick"),
./apps/veille/urls.py:14:    path("articles/<int:pk>/publish/", views.article_publish, name="article_publish"),
./apps/veille/urls.py:15:    path("articles/<int:pk>/publish-related/", views.article_publish_related, name="article_publish_related"),
./apps/veille/urls.py:16:    path("mcp/status-refresh/", views.mcp_status_refresh, name="mcp_status_refresh"),
./apps/veille/urls.py:17:]
./apps/comptes/urls.py:1:from django.contrib.auth import views as auth_views
./apps/comptes/urls.py:2:from django.urls import path
./apps/comptes/urls.py:3:
./apps/comptes/urls.py:4:app_name = "comptes"
./apps/comptes/urls.py:5:
./apps/comptes/urls.py:6:urlpatterns = [
./apps/comptes/urls.py:7:    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
./apps/comptes/urls.py:8:    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
./apps/comptes/urls.py:9:]
./apps/models_routing/urls.py:1:from django.urls import path
./apps/models_routing/urls.py:2:
./apps/models_routing/urls.py:3:from . import views
./apps/models_routing/urls.py:4:
./apps/models_routing/urls.py:5:app_name = "models_routing"
./apps/models_routing/urls.py:6:
./apps/models_routing/urls.py:7:urlpatterns = [
./apps/models_routing/urls.py:8:    path("statusbar/<slug:slug>/", views.statusbar_fragment, name="statusbar"),
./apps/models_routing/urls.py:9:    path("runs/", views.runs_panel, name="runs"),
./apps/models_routing/urls.py:10:    path("openclaw-stats/", views.openclaw_stats, name="openclaw_stats"),
./apps/models_routing/urls.py:11:    path("openclaw-stats/stream/", views.openclaw_stats_stream, name="openclaw_stats_stream"),
./apps/models_routing/urls.py:12:    path("openclaw-stats/log/", views.openclaw_log_exchange, name="openclaw_log"),
./apps/models_routing/urls.py:13:]
./config/urls.py:1:from django.conf import settings
./config/urls.py:2:from django.contrib import admin
./config/urls.py:3:from django.http import JsonResponse
./config/urls.py:4:from django.urls import include, path
./config/urls.py:5:from django.views.generic import TemplateView
./config/urls.py:6:
./config/urls.py:7:from apps.vitrine.views import landing
./config/urls.py:8:from config.dashboard_view import spacelabs_dashboard
./config/urls.py:9:
./config/urls.py:10:
./config/urls.py:11:def healthz(_request):
./config/urls.py:12:    return JsonResponse({"status": "ok"})
./config/urls.py:13:
./config/urls.py:14:
./config/urls.py:15:urlpatterns = [
./config/urls.py:16:    path("", landing, name="landing"),
./config/urls.py:17:    path("v2/", TemplateView.as_view(template_name="landing_v2.html"), name="landing_v2"),
./config/urls.py:18:    path("v3/", TemplateView.as_view(template_name="landing_v3.html"), name="landing_v3"),
./config/urls.py:19:    path("v4/", TemplateView.as_view(template_name="landing_v4.html"), name="landing_v4"),
./config/urls.py:20:    path("v5/", TemplateView.as_view(template_name="landing_v5.html"), name="landing_v5"),
./config/urls.py:21:    path("v6/", TemplateView.as_view(template_name="landing_v6.html"), name="landing_v6"),
./config/urls.py:22:    path("auth/", include("apps.comptes.urls")),
./config/urls.py:23:    path("cockpit/", include("apps.workspaces.urls")),
./config/urls.py:24:    path("observer/", include("apps.observer.urls")),
./config/urls.py:25:    path("ops/", include("apps.ops.urls")),
./config/urls.py:26:    path("missions/", include("apps.tasker.urls")),
./config/urls.py:27:    path("skills/", include("apps.skills.urls")),
./config/urls.py:28:    path("voice/", include("apps.voice.urls")),
./config/urls.py:29:    path("routage/", include("apps.models_routing.urls")),
./config/urls.py:30:    path("vitrine/", include("apps.vitrine.urls")),
./config/urls.py:31:    path("veille/", include("apps.veille.urls")),
./config/urls.py:32:    path("comms/", include("apps.comms.urls")),
./config/urls.py:33:    path("dashboard/", spacelabs_dashboard, name="dashboard"),
./config/urls.py:34:    path("django-admin/", admin.site.urls),
./config/urls.py:35:    path("healthz", healthz, name="healthz"),
./config/urls.py:36:]
./config/urls.py:37:
./config/urls.py:38:# La toolbar n'est montée que si l'APP est activée (settings dev), pas
./config/urls.py:39:# simplement si le paquet est importable — sinon `check --deploy` en prod
./config/urls.py:40:# charge des modèles hors INSTALLED_APPS et explose.
./config/urls.py:41:if "debug_toolbar" in settings.INSTALLED_APPS:
./config/urls.py:42:    urlpatterns = [path("__debug__/", include("debug_toolbar.urls"))] + urlpatterns
./config/urls.py:43:
./config/urls.py:44:# Sert les médias téléchargés en local pendant le dev (images des communiqués).
./config/urls.py:45:if settings.DEBUG:
./config/urls.py:46:    from django.conf.urls.static import static as _static
./config/urls.py:47:    urlpatterns += _static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
./apps/ops/urls.py:1:from django.urls import path
./apps/ops/urls.py:2:
./apps/ops/urls.py:3:from . import views
./apps/ops/urls.py:4:
./apps/ops/urls.py:5:app_name = "ops"
./apps/ops/urls.py:6:
./apps/ops/urls.py:7:urlpatterns = [
./apps/ops/urls.py:8:    path("jauges/", views.gauges, name="gauges"),
./apps/ops/urls.py:9:    path("mcp/<int:alert_id>/resoudre/", views.resolve_mcp, name="resolve_mcp"),
./apps/ops/urls.py:10:]
./apps/tasker/urls.py:1:from django.urls import path
./apps/tasker/urls.py:2:
./apps/tasker/urls.py:3:from . import views
./apps/tasker/urls.py:4:
./apps/tasker/urls.py:5:app_name = "tasker"
./apps/tasker/urls.py:6:
./apps/tasker/urls.py:7:urlpatterns = [
./apps/tasker/urls.py:8:    path("w/<slug:slug>/", views.mission_list, name="missions"),
./apps/tasker/urls.py:9:    path("w/<slug:slug>/nouvelle/", views.mission_create, name="mission_create"),
./apps/tasker/urls.py:10:    path("<int:pk>/", views.mission, name="mission"),
./apps/tasker/urls.py:11:    path("<int:pk>/swarm/", views.swarm, name="swarm"),
./apps/tasker/urls.py:12:    path("<int:pk>/etat/", views.mission_state, name="mission_state"),
./apps/tasker/urls.py:13:    path("<int:pk>/planifier/", views.mission_plan, name="mission_plan"),
./apps/tasker/urls.py:14:    path("<int:pk>/supprimer/", views.mission_delete, name="mission_delete"),
./apps/tasker/urls.py:15:    path("<int:pk>/taches/", views.task_create, name="task_create"),
./apps/tasker/urls.py:16:    path("<int:pk>/taches/<int:task_id>/deplacer/", views.task_move, name="task_move"),
./apps/tasker/urls.py:17:]

```

### greps-corrected

Commande : `rg -n '\{#|\|safe|mark_safe|csrf_exempt|raw\(|cursor.execute|os.environ.get\(|config.settings.dev|SESSION_COOKIE_SECURE|CSRF_COOKIE_SECURE|TODO|FIXME' --glob '*.py' --glob '*.html' --glob '!**/migrations/**' .`

Exit : 0 ; durée : 0.05 s.

```text
./manage.py:7:    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
./config/celery.py:6:os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
./config/asgi.py:6:os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
./config/settings/prod.py:29:SESSION_COOKIE_SECURE = True
./config/settings/prod.py:30:CSRF_COOKIE_SECURE = True
./templates/veille/articles.html:116:    </div>{# /arts-main #}
./templates/veille/articles.html:137:    </div>{# /arts-layout #}
./config/wsgi.py:5:os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
./apps/models_routing/views.py:14:from django.views.decorators.csrf import csrf_exempt
./apps/models_routing/views.py:128:@csrf_exempt
./templates/vitrine/vitrine_v2.html:93:const PRODUITS = {{ produits_json|safe }};
./templates/landing_showroom.html:272:const PRODUITS = {{ produits_json|safe }};
./apps/chat/tests/support/fake_claude.py:23:_argv_log = os.environ.get("FAKE_CLAUDE_ARGV_LOG")
./apps/tasker/models.py:89:        TODO = "todo", "à faire"
./apps/tasker/models.py:99:    BOARD_COLUMNS = [Status.TODO, Status.READY, Status.RUNNING, Status.REVIEW, Status.DONE]
./apps/tasker/models.py:105:    status = models.CharField(max_length=10, choices=Status.choices, default=Status.TODO)
./apps/tasker/planner.py:158:        mission.tasks.filter(status__in=[Task.Status.TODO, Task.Status.READY]).delete()
./templates/vitrine/savoir_faire.html:377:  const PRODUITS = {{ produits_json|safe }};
./apps/tasker/services.py:28:    """Passe en READY les tâches TODO dont toutes les dépendances sont finies.
./apps/tasker/services.py:35:    for task in mission.tasks.filter(status=Task.Status.TODO).prefetch_related("depends_on"):
./apps/tasker/services.py:154:        t.status in (Task.Status.READY, Task.Status.RUNNING, Task.Status.TODO) for t in tasks
./apps/veille/management/commands/veille_sync.py:143:        user = os.environ.get("VEILLE_IMAP_USER")
./apps/veille/management/commands/veille_sync.py:144:        pw = os.environ.get("VEILLE_IMAP_PASS")
./apps/veille/management/commands/veille_sync.py:145:        host = os.environ.get("VEILLE_IMAP_HOST", "imap.gmail.com")
./apps/veille/management/commands/veille_sync.py:146:        frm = os.environ.get("VEILLE_IMAP_FROM", "therese")
./apps/tasker/tests/test_swarm_s16.py:24:def _t(mission, key, deps=(), status=Task.Status.TODO, order=0):
./apps/tasker/tests/test_services_s10.py:65:    assert t2.status == Task.Status.TODO, "T2 ne doit pas partir avant T1"
./apps/tasker/tests/test_services_s10.py:119:    _task(mission, "T1")  # reste TODO : refresh_ready non appelé
./apps/comms/management/commands/comms_sync_telegram.py:33:        token = os.environ.get("COMMS_TG_TOKEN")
./apps/comms/management/commands/comms_sync_email.py:53:        user = os.environ.get("COMMS_IMAP_USER") or os.environ.get("VEILLE_IMAP_USER")
./apps/comms/management/commands/comms_sync_email.py:54:        pw = os.environ.get("COMMS_IMAP_PASS") or os.environ.get("VEILLE_IMAP_PASS")
./apps/comms/management/commands/comms_sync_email.py:55:        host = os.environ.get("COMMS_IMAP_HOST", "imap.gmail.com")
./apps/comms/management/commands/comms_sync_email.py:56:        folder = os.environ.get("COMMS_IMAP_FOLDER", "INBOX")
./apps/comms/views.py:8:from django.views.decorators.csrf import csrf_exempt
./apps/comms/views.py:33:@csrf_exempt
./apps/common/tests/test_templates_hygiene.py:5:``{# … #}`` de Django est **mono-ligne uniquement**. Un commentaire qui court
./apps/common/tests/test_templates_hygiene.py:10:La convention du projet est donc : **zéro `{# #}` dans les templates**. Les
./apps/common/tests/test_templates_hygiene.py:32:    """Aucun `{#` : le mono-ligne est toléré par Django, le multi-ligne fuit.
./apps/common/tests/test_templates_hygiene.py:38:    assert "{#" not in text, (
./apps/common/tests/test_templates_hygiene.py:40:        "Un `{# … #}` sur plusieurs lignes s'affiche dans la page. "
./apps/common/tests/test_templates_hygiene.py:49:    assert Template("{# une ligne #}X").render(Context({})) == "X"
./apps/common/tests/test_templates_hygiene.py:50:    rendered = Template("{# ligne un\nligne deux #}X").render(Context({}))

```

### preflightfiles-corrected

Commande : `rg --files --hidden -g '!**/.git/**' . | rg '(preflight|duct.yaml|env.example|deploy/|unit_doctor)'`

Exit : 0 ; durée : 0.02 s.

```text
./deploy/chatwoot/README.md
./deploy/chatwoot/setup.sh
./deploy/comms_poll.sh

```

### csrfheaders

Commande : `rg -n 'hx-headers|csrf_token|CSRF_TRUSTED_ORIGINS' templates config .github`

Exit : 0 ; durée : 0.01 s.

```text
templates/observer/partials/_rule_form.html:2:  {% csrf_token %}
templates/base.html:28:<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'
templates/base.html:80:        {% csrf_token %}
templates/workspaces/partials/_workspace_form.html:8:      {% csrf_token %}
templates/workspaces/partials/_pane_form.html:13:    {% csrf_token %}
templates/workspaces/partials/_confirm_delete.html:8:      {% csrf_token %}
templates/registration/login.html:73:      {% csrf_token %}
templates/tasker/partials/_mission_list.html:25:    {% csrf_token %}
templates/tasker/partials/_board.html:98:    {% csrf_token %}

```

### celery-entrypoints

Commande : `cat config/celery.py config/asgi.py config/wsgi.py`

Exit : 0 ; durée : 0.01 s.

```text
"""Plomberie Celery (J0). Les tâches métier arrivent au Sprint 5."""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("spacelabs")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
"""ASGI natif dès J0 ([REALTIME]=oui) — HTTP + WebSocket."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from apps.runtime import routing  # noqa: E402
from apps.runtime.lifespan import LifespanApp  # noqa: E402
from apps.runtime.startup import on_server_boot  # noqa: E402

# Réconciliation + démarrage du battement, dès l'import de ce module dans le
# processus serveur (robuste, indépendant du support 'lifespan' du serveur).
on_server_boot()

application = ProtocolTypeRouter(
    {
        # Réconciliation + battement de cœur au (dé)marrage de Daphne (S5).
        "lifespan": LifespanApp(),
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(routing.websocket_urlpatterns))
        ),
    }
)
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
application = get_wsgi_application()

```

### deploy-authority

Commande : `git ls-files deploy; git ls-files '*duct*' '*preflight*' '*unit_doctor*' '*service*'`

Exit : 0 ; durée : 0.01 s.

```text
deploy/chatwoot/README.md
deploy/chatwoot/setup.sh
deploy/comms_poll.sh
apps/models_routing/services.py
apps/ops/services.py
apps/ops/tests/test_services.py
apps/runtime/services/__init__.py
apps/runtime/services/headless_manager.py
apps/runtime/services/pane_manager.py
apps/runtime/services/pty_backend.py
apps/skills/services.py
apps/tasker/services.py
apps/tasker/tests/test_services_s10.py
apps/workspaces/services/__init__.py
apps/workspaces/services/files.py

```

- Note de collecte : les greps initiaux sans chemin explicite dans subprocess ont lu stdin vide ; les variantes `*-corrected` avec `.` font foi. Aucune absence déduite des variantes initiales.

## Annexe — vérifications après installation

### pip check

`DJANGO_SETTINGS_MODULE=config.settings.prod ../review-venv/bin/python -m pip check` ; exit 0 ; 0.47 s

```text
No broken requirements found.

```

### deploycheck

`DJANGO_SETTINGS_MODULE=config.settings.prod ../review-venv/bin/python manage.py check --deploy` ; exit 1 ; 0.87 s

```text
Traceback (most recent call last):
  File "/workspace/scratch/add2bb5bf15b/spacelabs/manage.py", line 14, in <module>
    main()
  File "/workspace/scratch/add2bb5bf15b/spacelabs/manage.py", line 10, in main
    execute_from_command_line(sys.argv)
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/core/management/__init__.py", line 442, in execute_from_command_line
    utility.execute()
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/core/management/__init__.py", line 436, in execute
    self.fetch_command(subcommand).run_from_argv(self.argv)
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/core/management/base.py", line 420, in run_from_argv
    self.execute(*args, **cmd_options)
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/core/management/base.py", line 464, in execute
    output = self.handle(*args, **options)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/core/management/commands/check.py", line 81, in handle
    self.check(
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/core/management/base.py", line 496, in check
    all_issues = checks.run_checks(
                 ^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/core/checks/registry.py", line 89, in run_checks
    new_errors = check(app_configs=app_configs, databases=databases)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/core/checks/urls.py", line 136, in check_custom_error_handlers
    handler = resolver.resolve_error_handler(status_code)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/urls/resolvers.py", line 732, in resolve_error_handler
    callback = getattr(self.urlconf_module, "handler%s" % view_type, None)
                       ^^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/utils/functional.py", line 47, in __get__
    res = instance.__dict__[self.name] = self.func(instance)
                                         ^^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/urls/resolvers.py", line 711, in urlconf_module
    return import_module(self.urlconf_name)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/importlib/__init__.py", line 90, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 999, in exec_module
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "/workspace/scratch/add2bb5bf15b/spacelabs/config/urls.py", line 7, in <module>
    from apps.vitrine.views import landing
  File "/workspace/scratch/add2bb5bf15b/spacelabs/apps/vitrine/views.py", line 17, in <module>
    "shot": static(f"vitrine/desktop/{p['slug']}.jpg"),
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/templatetags/static.py", line 179, in static
    return StaticNode.handle_simple(path)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/templatetags/static.py", line 129, in handle_simple
    return staticfiles_storage.url(path)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/staticfiles/storage.py", line 204, in url
    return self._url(self.stored_name, name, force)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/staticfiles/storage.py", line 183, in _url
    hashed_name = hashed_name_func(*args)
                  ^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/staticfiles/storage.py", line 518, in stored_name
    raise ValueError(
ValueError: Missing staticfiles manifest entry for 'vitrine/desktop/astragso.jpg'

```

### migrations

`DJANGO_SETTINGS_MODULE=config.settings.prod ../review-venv/bin/python manage.py makemigrations --check --dry-run` ; exit 1 ; 0.78 s

```text
Traceback (most recent call last):
  File "/workspace/scratch/add2bb5bf15b/spacelabs/manage.py", line 14, in <module>
    main()
  File "/workspace/scratch/add2bb5bf15b/spacelabs/manage.py", line 10, in main
    execute_from_command_line(sys.argv)
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/core/management/__init__.py", line 442, in execute_from_command_line
    utility.execute()
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/core/management/__init__.py", line 436, in execute
    self.fetch_command(subcommand).run_from_argv(self.argv)
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/core/management/base.py", line 420, in run_from_argv
    self.execute(*args, **cmd_options)
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/core/management/base.py", line 461, in execute
    self.check(**check_kwargs)
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/core/management/base.py", line 496, in check
    all_issues = checks.run_checks(
                 ^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/core/checks/registry.py", line 89, in run_checks
    new_errors = check(app_configs=app_configs, databases=databases)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/core/checks/urls.py", line 136, in check_custom_error_handlers
    handler = resolver.resolve_error_handler(status_code)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/urls/resolvers.py", line 732, in resolve_error_handler
    callback = getattr(self.urlconf_module, "handler%s" % view_type, None)
                       ^^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/utils/functional.py", line 47, in __get__
    res = instance.__dict__[self.name] = self.func(instance)
                                         ^^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/urls/resolvers.py", line 711, in urlconf_module
    return import_module(self.urlconf_name)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/importlib/__init__.py", line 90, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 999, in exec_module
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "/workspace/scratch/add2bb5bf15b/spacelabs/config/urls.py", line 7, in <module>
    from apps.vitrine.views import landing
  File "/workspace/scratch/add2bb5bf15b/spacelabs/apps/vitrine/views.py", line 17, in <module>
    "shot": static(f"vitrine/desktop/{p['slug']}.jpg"),
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/templatetags/static.py", line 179, in static
    return StaticNode.handle_simple(path)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/templatetags/static.py", line 129, in handle_simple
    return staticfiles_storage.url(path)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/staticfiles/storage.py", line 204, in url
    return self._url(self.stored_name, name, force)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/staticfiles/storage.py", line 183, in _url
    hashed_name = hashed_name_func(*args)
                  ^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/staticfiles/storage.py", line 518, in stored_name
    raise ValueError(
ValueError: Missing staticfiles manifest entry for 'vitrine/desktop/astragso.jpg'

```

### tests

`-m pytest -q -p no:cacheprovider` ; exit timeout ; 80 s

```text
..............F..F...................................................... [ 11%]
........................................................................ [ 22%]
............................................................FF.....FF... [ 34%]
FFFFF..FF.FFF.F
```

### static

`DJANGO_SETTINGS_MODULE=config.settings.prod ../review-venv/bin/python manage.py collectstatic --noinput --dry-run` ; exit 0 ; 0.97 s

```text
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/flumet.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/astragso.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/titanreliability.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/piiitch.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/bodyboard.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/reelay.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/corpusclip.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/signalnest.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/fleetdeck.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/scrollingua.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/socialnest.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/gentabs.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/treetop.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/callflow.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/montblanc.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/coachmatch.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/retardmaxxin.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/walletop.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/gettestforge.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/rimbup.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/leadingpoint.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/mckp.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/viraldm.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/sportpass.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/frontiere.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/leon.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/vocalis.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/kloz.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/reelay-blog.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/propulse.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/desktop/foncierops.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/flumet.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/astragso.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/titanreliability.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/piiitch.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/bodyboard.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/reelay.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/corpusclip.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/signalnest.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/dopr.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/fleetdeck.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/scrollingua.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/socialnest.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/katanakungfu.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/gentabs.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/treetop.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/callflow.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/montblanc.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/coachmatch.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/pricerhub.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/retardmaxxin.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/biorl.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/walletop.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/gettestforge.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/rimbup.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/o9n.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/leadingpoint.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/mckp.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/streakx.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/viraldm.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/sportpass.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/frontiere.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/leon.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/vocalis.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/cdcnails.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/deepdive.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/upvid.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/kloz.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/reelay-blog.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/propulse.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/foncierops.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vitrine/screenshots/kimchi.jpg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/fonts/source-serif-4/source-serif-4-latin-600-normal.woff2'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/fonts/source-serif-4/source-serif-4-latin-700-normal.woff2'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/fonts/inter/inter-latin-700-normal.woff2'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/fonts/inter/inter-latin-500-normal.woff2'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/fonts/inter/inter-latin-600-normal.woff2'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/fonts/inter/inter-latin-400-normal.woff2'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/fonts/jetbrains-mono/jetbrains-mono-latin-600-normal.woff2'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/fonts/jetbrains-mono/jetbrains-mono-latin-400-normal.woff2'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/js/panes.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/js/dock.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/js/voice.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/js/observer.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/js/board.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/js/shortcuts.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/js/grid.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/js/resume.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/js/chat.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/js/palette.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/js/shell.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/js/cockpit-shell.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/js/bridge.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/css/observer.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/css/shell.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/css/design-system.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/css/tasker.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/css/terminal.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vendor/htmx/htmx.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vendor/alpine/alpine.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vendor/xterm/xterm.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vendor/xterm/addon-fit.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/spacelabs/static/vendor/xterm/xterm.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/icon-no.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/icon-deletelink.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/tooltag-arrowright.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/search.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/icon-clock.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/icon-addlink.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/tooltag-add.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/icon-yes.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/icon-alert.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/LICENSE'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/inline-delete.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/README.txt'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/sorting-icons.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/icon-unknown.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/icon-hidelink.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/selector-icons.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/calendar-icons.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/icon-viewlink.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/icon-unknown-alt.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/icon-calendar.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/icon-changelink.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/gis/move_vertex_off.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/img/gis/move_vertex_on.svg'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/jquery.init.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/urlify.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/nav_sidebar.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/autocomplete.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/filters.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/SelectFilter2.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/popup_response.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/core.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/cancel.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/calendar.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/inlines.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/SelectBox.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/theme.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/unusable_password_field.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/actions.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/prepopulate_init.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/prepopulate.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/change_form.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/admin/DateTimeShortcuts.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/admin/RelatedObjectLookups.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/jquery/jquery.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/jquery/LICENSE.txt'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/jquery/jquery.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/xregexp/xregexp.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/xregexp/xregexp.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/xregexp/LICENSE.txt'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/select2.full.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/LICENSE.md'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/select2.full.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/mk.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/bg.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/af.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/sv.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/hi.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/fr.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/ja.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/id.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/km.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/is.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/vi.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/ca.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/uk.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/de.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/et.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/zh-CN.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/fi.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/ms.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/sr-Cyrl.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/sr.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/tr.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/pt-BR.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/gl.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/hsb.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/en.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/th.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/da.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/ko.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/bn.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/nl.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/cs.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/hr.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/lv.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/ar.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/lt.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/el.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/es.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/ka.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/ne.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/hy.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/ps.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/eu.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/sk.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/tk.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/zh-TW.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/pt.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/sl.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/az.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/he.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/pl.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/nb.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/ro.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/hu.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/ru.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/bs.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/fa.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/sq.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/dsb.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/js/vendor/select2/i18n/it.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/css/widgets.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/css/base.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/css/responsive.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/css/responsive_rtl.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/css/dashboard.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/css/dark_mode.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/css/changelists.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/css/forms.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/css/autocomplete.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/css/unusable_password_field.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/css/login.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/css/rtl.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/css/nav_sidebar.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/css/vendor/select2/select2.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/css/vendor/select2/LICENSE-SELECT2.md'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django/contrib/admin/static/admin/css/vendor/select2/select2.min.css'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/htmax-4.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/django-htmx.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/htmx-2.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/htmx-2.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/htmax-4.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/htmx-4.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/htmx-4.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-preload-4.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-sse-4.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-head-2.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-upsert-4.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-targets-4.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-preload-2.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-prompt-4.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-head-2.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-sse-2.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/htmx-2-compat-4.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-targets-4.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-preload-4.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-ws-4.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-ws-2.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-preload-2.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/htmx-2-compat-4.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-ws-2.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-sse-4.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-ptag-4.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-browser-indicator-4.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-download-4.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-prompt-4.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-optimistic-4.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-browser-indicator-4.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-head-4.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-ptag-4.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-sse-2.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-head-4.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-download-4.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-ws-4.min.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-optimistic-4.js'
Pretending to copy '/workspace/scratch/add2bb5bf15b/review-venv/lib/python3.12/site-packages/django_htmx/static/django_htmx/ext/hx-upsert-4.min.js'

269 static files copied to '/workspace/scratch/add2bb5bf15b/spacelabs/staticfiles'.

```

