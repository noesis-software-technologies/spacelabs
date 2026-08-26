# AUDIT.md — Sprint 3 (revamp) : presets d'agents configurables

Suite directe du Sprint 2. Les presets ne sont plus en dur : tu peux définir tes
propres agents — sans toucher au code, via le même mécanisme de réglage que le
reste du kit.

## 1. Un réglage, pas du code

`COCKPIT_AGENT_PRESETS` (settings ou JSON d'environnement) remplace la liste
intégrée. C'est le patron déjà en place pour `COCKPIT_ALLOWED_CMDS` : typé, hors du
code. Fourni, il **remplace** les défauts (contrôle total, prévisible) ; vide, on
garde la liste intégrée (Claude/Codex/Cursor/Terminal/Chat). Un exemple de format
est en commentaire dans `base.py`.

## 2. Tolérant mais franc

`get_agent_presets()` normalise chaque entrée (défauts pour couleur, icône,
description ; `kind` par défaut `pty`) et **ignore** les entrées invalides plutôt
que de planter — une coquille sur un agent ne prive pas des autres. Mais disparaître
en silence serait pire : `manage.py check` **signale** chaque entrée écartée
(clé/label manquants, `kind` inconnu, `cmd` manquant pour un pty), avec la raison.
Le check et le chargeur appliquent exactement les mêmes règles. Et si la config ne
produit aucune entrée exploitable, on retombe sur les défauts : jamais de cockpit
sans agent.

## 3. La sécurité ne bouge pas

Un preset configuré reste un preset : il passe par `pane_create`, donc son binaire
est validé par la liste blanche (`resolve_allowed_binary`, Sprint 17). Configurer un
agent ne l'autorise pas à tourner — il faut aussi son binaire dans
`COCKPIT_ALLOWED_CMDS`. Le sélecteur le montre honnêtement : un agent configuré mais
non autorisé apparaît désactivé (« hors liste blanche »).

## 4. Vérifié / non vérifié

**Vérifié offline** : `check` 0 issue ; **523 tests** (515 + 8). Repli sur les
défauts, remplacement, tri des entrées invalides, repli si tout est invalide, rendu
du sélecteur avec un agent configuré, et le system check (erreur si ce n'est pas une
liste, avertissement par entrée mal formée).

**Non vérifié ici** : comme aux sprints précédents, le comportement navigateur
(clic, montage WS/xterm, fermeture modale) n'est pas testable dans ce conteneur.

## 5. Ensuite

Restent, hors fork missions→modes : onglet Browser du dock, ASR streaming, surface
Mémoire. Piste possible : une UI de gestion des presets (au lieu du réglage), pour
les éditer à chaud plutôt qu'en configuration.

---

*(Audits précédents conservés ci-dessous.)*


# AUDIT.md — Sprint 2 (revamp) : presets d'agents

Le cœur, tel que tu l'as posé : des agents distincts qu'on lance sur leurs tâches.
Le kit ne proposait que « Terminal » (pty) et « Chat » (headless). On ajoute des
**presets nommés** — Claude Code, Codex, Cursor, Terminal, Chat — sans percer la
sécurité du Sprint 17.

## 1. Un preset ne déroge pas à la liste blanche

Point de vigilance. Un preset pty déclenche la création par le **pipeline
`pane_create` existant** : son binaire passe donc `resolve_allowed_binary`, la
règle unique durcie au Sprint 17. Concrètement, chaque carte disponible POSTe vers
`pane_create` avec les valeurs du preset (`hx-vals`) et ajoute le pane à
`#pane-grid`. Aucun nouveau chemin d'exécution, aucun contournement.

## 2. Disponible = autorisé ET présent — dit honnêtement

`resolve_allowed_binary` résout via le PATH (comme un shell). Un preset est donc
disponible seulement si son binaire est **dans la liste blanche** ET **résolu sur
l'hôte**. Sinon la carte est **désactivée**, jamais cachée, avec la bonne raison :
« hors liste blanche » (à autoriser) ou « introuvable sur l'hôte » (à installer).
On montre ce qui est possible et ce qu'il reste à configurer. Par défaut la liste
blanche contient `claude`, `bash`, `sh` — Claude Code et Terminal marchent d'emblée
là où `claude` est installé ; Codex/Cursor s'activent en les ajoutant.

## 3. Un seul point d'entrée

« Nouvel agent » (toolbar + état vide) ouvre le sélecteur dans la modale `#modal` ;
les raccourcis `n`/`c` et la commande de palette y mènent aussi. Le sélecteur
remplace les anciens boutons Terminal/Chat — le « Terminal » générique et le
« Chat » sont désormais deux presets parmi les autres. Le contrat du Sprint 0
tient : rien ne vise `#content`, la création ajoute à `#pane-grid`, l'échec de
validation reste dans la modale.

## 4. Vérifié / non vérifié

**Vérifié offline** : `check` 0 issue ; **515 tests** (506 + 5 nouveaux + garde de
marque sur le nouveau gabarit). La disponibilité (liste blanche + PATH, `unlisted`
vs `missing`) est testée sur `bash` (présent) sans supposer qu'un agent nommé soit
installé ; le sélecteur rend les cinq presets, marque les indisponibles, et un
preset disponible crée bien un pane via `pane_create`.

**Non vérifié ici (pas de navigateur)** : le clic réel sur une carte, l'ajout du
pane à la grille et son montage (WS/xterm), la fermeture de la modale. La chaîne
est en place (hx-post → `pane_create` → `paneCreated` → `cockpit-shell.js`), à
confirmer en live — d'autant que `claude` n'est pas installé dans ce conteneur,
donc seul le preset Terminal (bash) y est réellement lançable.

## 5. Ensuite

Restent, hors du fork missions→modes (en pause) : l'onglet Browser du dock, l'ASR
streaming, la surface Mémoire. Et, si utile, des presets configurables par réglages
(binaire/args par agent) plutôt qu'en dur.

---

*(Audits précédents conservés ci-dessous.)*


# AUDIT.md — Sprint 1 (revamp) : la palette de commandes ⌘K

Deuxième greffe sur le shell du Sprint 0. La palette v2 était **absente** du kit
(vrai manque, pas un placeholder). Elle est là — et surtout elle ne duplique
aucune logique.

## 1. Un lanceur au-dessus des contrôles existants

La palette ne réimplémente rien : chaque commande **déclenche un contrôle déjà
présent** dans le cockpit (comme `shortcuts.js`). « Nouveau terminal » clique le
bouton Terminal, « Panique » clique `[data-panic]`, « Board » clique
`[data-mode="board"]`. Deux conséquences :

- zéro divergence : le jour où un bouton change, la palette suit ;
- contextuelle : une commande n'apparaît que si sa cible existe dans le DOM —
  hors cockpit (régie…), la liste se réduit d'elle-même.

15 commandes : les 4 modes, création de pane (terminal/chat), tout lancer, grille
dense, direct, panique, régie, les 3 onglets du dock (Skills/Éditeur/Bridge), et
les deux panneaux coulissants.

## 2. Clavier + souris, fidèle à la maquette

⌘K (ou Ctrl+K) ouvre/ferme ; ↑↓ naviguent, Entrée exécute, Échap ferme, clic sur
le fond ferme. Filtrage au fil de la frappe. Un bouton loupe dans la toolbar
(`[data-palette-open]`) pour la découvrabilité. Les combinaisons méta étant
ignorées par `shortcuts.js`, aucun conflit ; l'exécution attend 50 ms que la
palette se referme (repris de la démo).

## 3. Design porté, pas réinventé

`.pal` et ses enfants viennent du `<style>` de la maquette, sur les alias → `--ds-*`.
`shell.css` compose (overlay ancré haut, carte, liste) ; aucun composant existant
touché. Icônes SVG inline, teintées par commande via `color-mix`.

## 4. Vérifié / non vérifié

**Vérifié offline** : `check` 0 issue ; **506 tests** (503 + 3 nouveaux) ; la
coquille de la palette + le script sont servis, le déclencheur est dans la
toolbar, et **chaque cible déclenchée par la palette existe** dans le cockpit
(sinon une commande cliquerait dans le vide — c'est le test qui compte).

**Non vérifié ici (pas de navigateur)** : l'ouverture réelle au clavier, le
filtrage, la navigation ↑↓, l'exécution des clics. La logique est en place
(délégation d'événements, registre gaté par présence DOM), à confirmer en live.

## 5. Ensuite — un fork produit à trancher

board/swarm/memory **en place dans `#stage`** suppose de décider comment la couche
« missions » du kit (workspace → missions → board/swarm *par mission*) se replie
sur les modes du cockpit, et ce qu'est « Swarm » : le DAG de tâches d'une mission,
ou les agents-panes en réseau comme la démo ? C'est une décision produit (posée en
réponse). Restent aussi l'onglet Browser du dock, l'ASR streaming, la surface
Mémoire.

---

*(Audits précédents conservés ci-dessous.)*


# AUDIT.md — Sprint 0 (revamp) : recomposition du cockpit mono-écran

Décision : **Option A**. On converge vers la maquette v2 — un seul écran (navbar
+ sidebar + en-tête + panneaux coulissants), pas la greffe multi-pages. Ce sprint
pose le **frame** et le **contrat de slots** ; les surfaces (palette, board/swarm
en place, browser, mémoire) s'y brancheront ensuite.

## 1. Le bug : créer un terminal écrasait tout le cockpit

Signalé, reproduit, racine trouvée. `pane_create` (POST) renvoyait **le bon
fragment** — un pane + l'événement `paneCreated` (`apps/workspaces/views.py`).
Mais les boutons Terminal/Chat ciblaient `hx-target="#content" hx-swap="innerHTML"`,
et le formulaire intermédiaire (`_pane_form.html`) postait **lui aussi** vers
`#content`. Résultat : ouvrir un pane remplaçait la toolbar + la grille + le dock
par un formulaire, puis par un pane nu. Le cockpit disparaissait — deux fois.

Ce n'était pas un réglage isolé : le shell vivait *dans* `#content`, sans frame
persistant. Toute action visant `#content` le détruisait. C'est la racine que
l'Option A supprime.

## 2. Le correctif : un frame persistant + des slots nommés

**Règle posée : aucune action in-cockpit ne vise `#content`.**

- Le cockpit (`_workspace_view.html`) est recomposé en colonne : en-tête
  (`.workspace-toolbar`) / scène (`#stage` → `#pane-grid`) / barre de statut,
  avec le dock (`_bridge.html`) en side panel coulissant. `base.html` garde la
  sidebar + la navbar globales (frame persistant, `ds-sidebar` conservé).
- Créer un pane ouvre le formulaire dans un **overlay `#modal`** (GET → `#modal`),
  et le formulaire **ajoute** le pane à `#pane-grid` (`hx-swap="beforeend"`). Le
  fragment renvoyé était déjà bon ; c'était le *ciblage* qui écrasait.
- L'append s'auto-monte : `panes.js` observe déjà la grille (MutationObserver),
  donc le pane ajouté branche son WebSocket + xterm sans hook supplémentaire.
- Erreur de validation : `HX-Retarget: #modal` — l'erreur reste dans la modale
  au lieu de s'ajouter à la grille. Le succès, lui, rend le pane et referme la
  modale (`paneCreated`).

## 3. Ce que la composition apporte (v2)

Sélecteur de mode (terminals | board | swarm | memory) dans l'en-tête, crumb,
barre de statut, panneaux coulissants (sidebar ⌘B, dock ⌘\), overlay modal. Le
design vient de la maquette : les tokens de la démo **sont** les `--ds-*` du kit
(mêmes valeurs), on porte la couche d'alias et la composition — on ne recolore
pas. `shell.css` compose ; il ne redéfinit aucun composant existant.

## 4. Vérifié / non vérifié — honnêtement

**Vérifié offline** : `manage.py check` 0 issue ; **503 tests passent** (498 de
base + 5 nouveaux verrouillant le contrat de slots et le correctif) ; le cockpit
se rend (page complète + fragment htmx) sans erreur de template ; `ds-sidebar`
conservé en page complète, absent du fragment ; le formulaire vise `#pane-grid`,
plus `#content`.

**Non vérifié ici (pas de navigateur dans cet environnement)** : le montage réel
de xterm sur un pane ajouté, le flux WebSocket, l'animation de glissement des
panneaux, les raccourcis ⌘B/⌘\, la densité/colonnes à l'œil. La logique est en
place (MutationObserver, délégation d'événements) mais reste à valider en live —
comme les AUDIT précédents le notent pour le même environnement.

## 5. Ce qui se branche ensuite sur les slots

Les modes board/swarm/memory naviguent encore vers les surfaces existantes
(nav `#content`) : leur **swap en place dans `#stage`** est le prochain sprint.
Idem pour la palette ⌘K, l'onglet Browser du dock, l'ASR streaming et la surface
Mémoire. Le shell a désormais les emplacements ; ce sont des greffes, plus des
refontes.

---

*(Audit du Sprint 17 conservé ci-dessous.)*


# AUDIT.md — Sprint 17 : durcissement

Le sprint que j'avais annoncé et pas fait. Trois volets : la liste blanche des
commandes, le budget mémoire à 16 agents, et la mesure de la boucle chaude.

## 1. Faille : la liste blanche se contournait par un chemin

`spawn()` comparait `os.path.basename(argv[0])`. Donc **`~/evil/claude`,
`./sh`, `/tmp/evil/claude` passaient** : n'importe quel binaire portant un nom
autorisé s'exécutait, d'où qu'il vienne.

Ce n'est pas théorique : `COCKPIT_LAN_TOKEN` expose ce chemin au réseau local.
Un poste compromis pose un fichier dans `~`, et la liste blanche ne sert plus à
rien.

**Règle désormais** : le nom doit être **nu** — aucun séparateur de chemin, pas
de `~`. La résolution passe par le PATH (`shutil.which`), comme un shell, et
c'est le chemin résolu qui part à `execve`. Si un jour un chemin absolu devient
nécessaire, il faudra une liste blanche de *répertoires*, pas un assouplissement
de celle-ci.

## 2. La même règle existait en double — et une seule était durcie

Après correction du manager, le test live montrait que le **formulaire acceptait
toujours** `/tmp/evil/claude` : le pane était créé en base, et refusé seulement
au démarrage. `PtyPaneForm.clean_cmd` avait sa propre implémentation
(`cmd.rsplit("/")[-1]`) — exactement le trou que je venais de fermer ailleurs.

→ `resolve_allowed_binary()` : **une seule règle**, importée par le formulaire
et par le manager. Deux règles pour une politique, c'est comme ça qu'un trou
revient au sprint suivant.

Vérifié en live après correctif : les quatre tentatives refusées **à la saisie**,
`0 pane créé en base`.

## 3. Budget mémoire : mesuré, et vérifié par la configuration

Chaque pane garde un tampon circulaire pour rejouer l'écran à la reconnexion.
Le coût réel est **le produit** `COCKPIT_BUFFER_BYTES × COCKPIT_MAX_PANES` — pas
chaque réglage pris isolément. Deux contrôles Django (`manage.py check`) le
signalent : avertissement à 64 Mo, erreur à 512 Mo. Un troisième refuse un
chemin dans la liste blanche.

Démontré en live : `COCKPIT_BUFFER_BYTES=64Mo` ⇒
`runtime.E001 — 1024 Mo pour 16 agents`, avant tout démarrage.

Configuration livrée : 200 ko × 16 = **3,2 Mo**. Mesuré, pas supposé.

## 4. Performance de la boucle chaude — chiffres

Chaque octet sorti d'un agent traverse `_append_buffer`. Mesuré à 16 agents :

```
3200 diffusions (200 trames × 16 agents) en 4 ms — 1,2 µs par trame
```

Les tests vérifient aussi que le coût reste **linéaire** (un ring buffer recopié
à chaque trame passerait en quadratique) et qu'un pane mort **rend sa mémoire**.
Les bornes sont larges à dessein : le but est d'attraper une régression d'ordre
de grandeur, pas de figer une performance de CI.

Note honnête : la diffusion passe par la channel layer, donc ce chiffre mesure
le tampon, pas le trajet réseau complet jusqu'au navigateur. Un test de charge
bout en bout (16 onglets réels) reste à faire.

## Vérifications

| Vérification | Résultat |
|---|---|
| Suite complète | **495 passed** (473 avant S17, +22) |
| Tests durcissement | 21 verts (6 chemins d'attaque, chaînage, contrôles de config, règle partagée) |
| Tests performance | 4 verts, avec mesures imprimées |
| `manage.py check` | 0 issue |
| **`check --deploy` (prod, vraie clé)** | **0 issue** |
| **Live — binaire planté** | 4 tentatives refusées à la saisie, 0 pane créé |
| **Live — mauvaise config** | `runtime.E001` levée avant démarrage |

## Ce qui reste

- **Charge bout en bout** : 16 onglets navigateur réels, mesure du trajet
  complet (channel layer → WebSocket → xterm). Le tampon est mesuré, pas le
  reste.
- **ASR en streaming** et **envoi vocal direct** à un agent (reportés depuis S13).
- **Thème clair** : passe de contrastes AA.
- **Cloisonnement des `cwd`** : un pane peut encore être lancé dans n'importe
  quel répertoire existant de la machine. C'est cohérent avec un produit
  local-first, mais à revoir si l'exposition LAN devient un usage courant.

## Audit PR1+PR2 (2026-08-26, tête 3c42553)
Constat vérifié par exécution : main rouge (523/524) sur l'import de
`OBSERVER_MAX_TILES` supprimé par le commit full-matrix ; aucune CI.
Décision : c'est le TEST qui s'aligne (le plafond est désormais un réglage,
choix produit du full-matrix) — réintroduire la constante aurait figé la config.
Vérifié offline : `manage.py check` 0 issue ; suite complète 524/524 en 121 s
(env de référence : Django 5.2, sans faster-whisper ni pywinpty, SQLite +
InMemoryChannelLayer). La CI reproduit exactement cet env.
Prochaine étape du backlog : passe docs (ROADMAP périmée) puis Browser dock ∥
ASR streaming ; MODEL_ROUTING (ADR-5) déblocable dès que cette PR est mergée.

## Audit S-R1 MODEL_ROUTING (2026-08-26)
Décisions assumées faute d'arbitrage PO explicite (révocables sans migration) :
D1 = le modèle local reste un endpoint LAN (base_url en fixture/admin) ;
D2 = task_class portée par la Mission (champ prévu S-R2, absent en S-R1).
Bug trouvé et corrigé pendant le sprint : record_usage faisait un
lire-modifier-écrire (perte d'incréments en concurrence) → réécrit en
UPDATE F() atomique ; le test lit la base explicitement (l'accessor inverse
OneToOne sert une instance en cache après get_or_create — comportement ORM).
Vérifié offline : check 0 issue ; suite complète 539/539 (524 baseline + 15
nouveaux) en 120 s. Non vérifiable ici : santé d'un vrai llama-server
(commande backends_health à lancer sur poste), latences réelles.
Seuils 8000/6000 de la fixture : PROVISOIRES — [À CHIFFRER] avec les stats
prompt eval / eval time du serveur local (spec §6).
Reste pour S-R2 : ClaudeBinAdapter (enveloppe du runner headless existant),
champ Mission.task_class, RunLog JSONL branché, événements CockpitConsumer.

## Audit S-R2 (2026-08-26)
Choix d'adaptation consigné : le HeadlessManager est session-long par design ;
ClaudeBinAdapter est donc un ONE-SHOT (stdin fermé après le tour ⇒ exit après
result) qui réutilise argv + events.py — pas de réécriture du manager, pas de
second pipeline de diffusion (chat.event/pane_{id} réutilisés, handler
consumer inchangé). Testé sur le faux binaire existant (protocole réel).
Vérifié offline : check 0 issue ; 544/544 (539 + 5) en 123 s. Non vérifiable
ici : le vrai binaire claude (abonnement) et un vrai llama-server.
Reste S-R3 : statusbar/régie + calage des seuils — TOUJOURS en attente des
stats prompt eval/eval time du llama-server du user.

## Audit S-R3 (2026-08-26) — clôture du chantier ADR-5
Les stats réelles du llama-server n'ayant jamais été fournies, le calage des
seuils devient AUTO-MESURÉ : `manage.py calibrate_thresholds` (à lancer sur le
poste, serveur démarré) remplace les seuils provisoires par des valeurs
dérivées de mesures (règle : prompt/pp_tps + 400/gen_tps ≤ 90 s, borné par le
budget prompt du backend). Math testée ; mesure réseau non exécutable ici.
Comptage de suite vérifié : 524 (baseline) + 25 (models_routing) + 8 (tests de
marque/hygiène paramétrés sur les 2 nouveaux templates) = 557/557.
Chantier MODEL_ROUTING S-R1→S-R3 : COMPLET. Exploitation : 1) backends_health,
2) calibrate_thresholds, 3) déclarer task_class sur les missions, 4) budgets
en admin. Hors périmètre livré tel que spécifié : fallback en cours de
génération, inférence auto de task_class, orchestrateur appris.
