# SpaceLabs

Cockpit web **local-first** pour piloter des sessions [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) (et autres CLI)
depuis un navigateur : panes terminal temps réel, reprise de session après
coupure, multi-workspaces à venir. Pensé pour le multi-projets et le live
coding (vue spectateur expurgée — Sprint 3).

Aucune clé API : SpaceLabs **spawne le binaire `claude` de ta machine**,
qui utilise l'authentification de ton abonnement (`~/.claude`). Le serveur
doit donc tourner sur la machine où tu es loggé.

## Démarrer

```bash
make setup    # dépendances + migrations + utilisateur local « pilote »
make redis    # (optionnel en dev) démarre Redis via docker compose
make run      # daphne sur http://127.0.0.1:8000
```

Connexion : `pilote` / `cockpit-local` (change-le). La page cockpit ouvre un
pane terminal qui lance `COCKPIT_DEFAULT_CMD` (par défaut `claude`) dans un
vrai PTY — ferme l'onglet, reviens : la session continue et l'historique est
rejoué.

## ⚠️ Sécurité — à lire avant d'exposer quoi que ce soit

- Ce cockpit **exécute des process avec tes droits utilisateur**. Ne l'expose
  **jamais** sur Internet. LAN de confiance uniquement (la « vue télé »).
- Les commandes spawnables sont restreintes par la liste blanche
  `COCKPIT_ALLOWED_CMDS` — n'y mets que des binaires que tu assumes.
- Si tu utilises `claude --dangerously-skip-permissions` pour l'autonomie,
  tu retires les garde-fous de Claude Code : fais-le en connaissance de
  cause, sur des repos jetables ou sauvegardés.
- Accès authentifié obligatoire (WS compris) ; le mode observateur public
  (expurgé) est un flux séparé, read-only, à venir au Sprint 3.

## Configuration

Copie `.env.example` → `.env`. Variables clés : `COCKPIT_DEFAULT_CMD`,
`COCKPIT_ALLOWED_CMDS`, `COCKPIT_MAX_PANES`, `REDIS_URL`, `ALLOWED_HOSTS`
(ajoute l'IP LAN de la machine pour la vue télé).

## État — Sprint 2

- ✅ Fondations (S1) : Django 5.2 + Channels/Daphne, noyau PTY (spawn, replay, reprise, kill propre, liste blanche, isolation par user), design system 2 thèmes
- ✅ Workspaces & panes persistés (MTI + registre polymorphe), CRUD htmx, sidebar dynamique
- ✅ Grille multi-panes (splits auto, zoom), « Tout lancer », labels d'agents auto
- ✅ F5 ⇒ grille restaurée + sessions rattachées ; restart serveur détecté, relance `--continue` pour `claude`
- ✅ Vue spectateur `/observer/` (SSE, anonyme, read-only, plein écran) : panes publics expurgés par RedactionRules serveur, placeholders pour le privé, mode live + bouton panique — **privé par défaut**
- ✅ Chat headless `claude -p --output-format stream-json` : pane conversationnel (bulles, outils repliables, coût/durée), persistance intégrale en `EventLog`, boutons d'amorce, **même pipeline public/privé** que les terminaux
- ✅ Exploitation : Celery + beat (instantanés d'usage → jauges de la sidebar, faucheur de zombies, purge/archivage d'EventLog, détection MCP → bouton `/mcp`), raccourcis clavier, **réconciliation au démarrage** du serveur
- ✅ **Commande vocale** : push-to-talk par pane (Web Speech API `fr-FR`), transcript éditable, envoi en stdin (PTY) ou dans le composer (chat)
- ✅ **Accès LAN** protégé par jeton partagé optionnel · **reprise de session fidèle** au redémarrage (`--resume` par id : le chat reprend exactement où il en était)

**Version 0.1.0 — prête à publier.** Voir `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`.

## Commande vocale

Maintiens le micro d'un pane pour dicter (fr-FR). Le transcript s'affiche en
direct et reste éditable : pour un chat il remplit le composer (tu relis, tu
envoies) ; pour un terminal, une barre éditable envoie la commande en stdin.
Sans support navigateur (Firefox), les micros disparaissent — aucune casse.

### Deux moteurs de reconnaissance

- **Navigateur** (défaut, `COCKPIT_STT_BACKEND=webspeech`) : Web Speech API,
  zéro dépendance — mais Chrome envoie l'audio à Google, et Firefox n'est pas
  supporté.
- **Serveur, verbatim, offline** (`COCKPIT_STT_BACKEND=crisperwhisper`) :
  [CrisperWhisper](https://github.com/nyrahealth/CrisperWhisper) via
  faster-whisper. Le navigateur capture l'audio, le serveur le transcrit
  (fillers, hésitations, faux départs inclus) — rien ne sort de ta machine.
  Prérequis : `pip install faster-whisper`, **ffmpeg**, GPU recommandé.

## Exploitation (Celery)

Les tâches périodiques tournent dans des processus séparés de Daphne :

```
make worker   # exécute les tâches (faucheur, snapshots, scan MCP, archivage)
make beat     # planifie les tâches (voir CELERY_BEAT_SCHEDULE)
```

Elles travaillent **uniquement depuis la base** (source de vérité partagée entre
Daphne et le worker). Au démarrage, Daphne réconcilie les panes orphelins d'une
exécution précédente (marqués « terminés ») et publie un battement de cœur ;
le faucheur s'appuie dessus pour ne jamais tuer une session vivante.

Raccourcis clavier : `?` affiche l'aide (nouveau terminal/chat, direct, panique,
zoom, focus pane 1-9…).

## Sécurité — mode chat headless

Le mode chat lance `claude -p` sur **ta** machine (auth OAuth de ton
abonnement, pas d'API). Pour que les agents exécutent des outils sans invite
interactive, Claude Code a besoin de `--dangerously-skip-permissions`. Il
n'est **pas** activé par défaut. Si tu l'ajoutes à
`COCKPIT_CLAUDE_HEADLESS_ARGS`, tu autorises l'agent à agir sans confirmation :
à ne faire que sur des répertoires que tu maîtrises. Le serveur doit tourner
sur la machine où tu es loggé (la « télé » n'est qu'un navigateur LAN).

## Licence

MIT — voir [LICENSE](LICENSE).
