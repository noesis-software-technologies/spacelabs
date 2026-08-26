# BRAND.md — SpaceLabs

Charte de marque du produit. Elle fait autorité sur `static/css/design-system.css` :
si les deux divergent, c'est le CSS qui a tort.

> **Ce document remplace la direction v1 (« OpenCockpeet »).** Cette v1 visait une
> ambiance « Claude dev » : crème chaud, anthracite tiède, titres en serif,
> accent jaune Hugging Face. SpaceLabs va ailleurs — §9 dit quoi et pourquoi.

---

## 1. Ce que le produit est

Un **cockpit d'agents** : *n* instances Claude Code qui travaillent en parallèle
sous la conduite d'un Master Tasker, sur la machine de l'utilisateur.

Trois conséquences directes sur la forme :

1. **La sortie des agents est le contenu.** L'interface est un cadre, pas un
   décor. Elle s'efface.
2. **La densité est une fonctionnalité.** 16 agents doivent tenir sur un écran.
   Tout élément de chrome se justifie ou disparaît.
3. **L'état doit se lire en périphérie.** On surveille un mur d'agents du coin
   de l'œil : un statut se lit à la couleur et au mouvement, pas à la lecture.

**Ton de voix** : direct, technique, sans esbroufe. On tutoie. On dit ce qui
s'est passé (« 2 agents ajoutés »), pas ce qu'on espère (« opération réussie ! »).
Jamais d'exclamation, jamais d'emoji dans l'interface.

---

## 2. Typographie

| Rôle | Token | Police | Usage |
|---|---|---|---|
| Titres | `--ds-font-display` | Inter 700, `letter-spacing: -0.02em` | Titres de page, noms de mission, marque |
| Texte | `--ds-font-sans` | Inter 400/500/600 | Libellés, descriptions, boutons |
| Machine | `--ds-font-mono` | JetBrains Mono | Sorties d'agents, chemins, états, coûts, clés de tâches, raccourcis |

**Règle du mono** : tout ce qui vient de la machine ou peut être copié-collé est
en mono. Un chemin, un statut, une clé `T1`, un coût, un binding clavier. Le
reste est en sans.

**Pas de serif.** `--ds-font-serif` reste déclaré (les woff2 sont livrés) mais
n'est utilisé nulle part. C'était la direction v1 ; la réintroduire demande de
modifier ce document d'abord.

---

## 3. Couleur

### L'accent

`--ds-accent: 26 93% 53%` — **#f77615**, orange SpaceLabs.

C'est la couleur de **la sélection et de l'attention** : workspace actif, pane
sélectionné, coordinateur du swarm, marque, anneau qui respire. Rien d'autre.
Un bouton orange dit « c'est ici que ça se passe », pas « clique-moi ».

### Les neutres — noir profond

`--ds-bg: 240 11% 4%` · `--ds-bg-raised: 240 10% 6%` · `--ds-bg-inset: 240 9% 2%`

Noir bleuté quasi pur. Le fond ne doit **jamais** rivaliser avec la sortie d'un
terminal. Trois plans seulement : fond d'app, surface élevée (sidebar, dock,
cartes), creux (terminaux).

### Les états — sémantique fixe, jamais décorative

| Token | Couleur | Signifie |
|---|---|---|
| `--ds-ok` | #7ece4e vert | ça tourne / c'est vert / ajout de diff |
| `--ds-warn` | #e0c34a or | attend une entrée humaine |
| `--ds-danger` | #ec5f57 rouge | mort, échec, stop, suppression |
| `--ds-voice` | #4d8dff bleu | **la machine écoute** (Bridge) |

**Le bleu voix est le seul îlot froid du produit.** Il ne décrit jamais un état
d'agent — sinon « j'écoute » et « ça marche » se confondent. Symétriquement,
le rouge n'est jamais utilisé pour l'écoute, seulement pour l'échec.

### Identité des agents

`--ds-agent-{claude,codex,cursor,gemini,opencode}` — une teinte par runtime,
**stable partout** : glyphe de pane, carte de board, nœud de swarm, avatar. Un
utilisateur doit pouvoir dire « le rose » et se faire comprendre.

---

## 4. Densité

`[data-density]` sur un conteneur pilote 8 variables d'un coup.

| Palier | Corps | Hauteur mini | Pour |
|---|---|---|---|
| `cozy` | 12px | 200px | 1–4 agents |
| `compact` | 11px | 160px | 4–6 agents |
| `dense` | 10px | 128px | 6–12 agents |
| `micro` | 9px | 104px | 12–16 agents, plein écran |

**Aucune taille de police de pane n'est écrite en dur.** À `dense` et `micro`,
les actions de pane s'effacent et ne réapparaissent qu'au survol ou au focus :
à 16 panes, sept boutons par en-tête saturent l'écran.

---

## 5. Géométrie et élévation

- Rayons : `--ds-radius-sm: 6px` (contrôles) · `--ds-radius: 10px` (cartes,
  champs) · `--ds-radius-lg: 16px` (panes, colonnes, panneaux).
- Ombres : `--ds-shadow` (cartes, toasts), `--ds-shadow-lg` (overlays). Rien
  d'autre. Une ombre marque une **superposition**, pas une hiérarchie.
- Largeurs de référence : `--ds-sidebar-w: 248px`, `--ds-dock-w: 340px`,
  `--ds-topbar-h: 52px`.

---

## 6. Mouvement

`--ds-motion-tap: 150ms` (retour d'appui) · `--ds-motion-card: 260ms` (apparition)
· `--ds-motion-page: 340ms` (navigation) · `--ds-motion-glow: 2400ms` (respiration).
Courbe unique : `--ds-ease-out`.

**La signature du produit** : l'anneau du pane qui *respire* quand l'agent
travaille. C'est le seul mouvement continu autorisé — il porte une information
(ça travaille) et se lit à trois mètres.

**`prefers-reduced-motion` est respecté partout** : la respiration devient un
halo statique, jamais une disparition de l'information.

---

## 7. La marque

Pastille hexagonale à dégradé orange (`--ds-accent` → `--ds-accent-2`) portant
un éclair. L'hexagone dit « module », l'éclair dit « exécution ».

- `.ds-brand-mark` (26px) — sidebar, vue télé
- `.ds-brand-mark--lg` (34px) — écrans d'accueil
- `.ds-brand-mark--ghost` — sur fond déjà coloré : orange sur voile orange

Le nom s'écrit **SpaceLabs**, un seul mot, deux capitales. Jamais « Spacelabs »,
jamais « Space Labs », jamais « le cockpit ».

---

## 8. Iconographie

Traits uniquement, `currentColor`, `stroke-width: 1.75` (2 en `--xs`), coins et
jonctions arrondis, grille 24. Jamais de remplissage sauf dans la marque.
`.ds-icon` / `--sm` (16) / `--xs` (13).

---

## 9. Ce qui a changé depuis la v1, et pourquoi

| Élément | v1 « OpenCockpeet » | SpaceLabs | Raison |
|---|---|---|---|
| Accent | jaune HF `48 100% 56%` | **orange #f77615** | Couleur de sélection du produit de référence |
| Fond | anthracite chaud `45 8% 8%` | **noir bleuté `240 11% 4%`** | La sortie des agents doit être la seule source de lumière |
| Titres | Source Serif 4 | **Inter resserré** | « Sobriété studieuse » ≠ cockpit dense. Le serif coûte de la hauteur de ligne |
| Thème clair | crème chaud | **neutre froid** | La crème jurait avec l'accent orange |
| `--ds-warn` | `37 100% 50%` | `48 71% 58%` | **Était identique à `--ds-accent-2`** : un pane « attend une entrée » ressemblait à un bouton de marque |
| Voix | rouge (`--ds-danger`) | **bleu `--ds-voice`** | Le rouge est réservé à l'échec ; « j'écoute » n'est pas une panne |
| Nom produit | « le cockpit » | **SpaceLabs** | — |

---

## 10. Comment appliquer la charte

**Rethémer = éditer les `:root` de `design-system.css`, rien d'autre.**
`terminal.css`, `observer.css` et `tasker.css` ne contiennent **aucune couleur
en dur** — c'est vérifié par un test.

Ajouter une surface :

1. Réutiliser les classes existantes avant d'en créer (`.ds-btn`, `.ds-badge`,
   `.ds-seg`, `.ds-card`, `.ds-status-dot`, `.ds-agent-dot`).
2. Nouvelle classe → uniquement des `hsl(var(--ds-*))`, jamais un hexadécimal.
3. Un état = un `data-attribute` (`data-status`, `data-density`, `data-level`),
   pas une classe modificatrice — le serveur et Alpine posent des attributs.
4. Mouvement continu → prévoir la variante `prefers-reduced-motion`.

Les tests `apps/common/tests/test_brand.py` verrouillent ces règles.
