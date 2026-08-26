# Correspondance des tokens — ancien → nouveau

Aucun **nom** de token ni de classe n'a changé. Seules les **valeurs** bougent,
plus quelques ajouts. Rien à modifier dans les templates ni dans Alpine.

## Ce qui change de valeur

| Token | Avant (Hugging Face) | Après (SpaceLabs) | Pourquoi |
|---|---|---|---|
| `--ds-accent` | `48 100% 56%` jaune HF | `26 93% 53%` **#f77615** | L'orange est la couleur de sélection du produit de référence : workspace actif, pane sélectionné, coordinateur du swarm. |
| `--ds-accent-2` | `37 100% 50%` | `26 100% 60%` | Hover / dégradé de la marque, dans la même famille. |
| `--ds-ring` | jaune | orange | Suit l'accent. |
| `--ds-bg` | `45 8% 8%` anthracite chaud | `240 11% 4%` | Noir profond quasi pur : la sortie des agents doit être la seule source de lumière. |
| `--ds-bg-raised` | `45 7% 11%` | `240 10% 6%` | idem |
| `--ds-bg-inset` | `45 9% 6%` | `240 9% 2%` | Fond des terminaux, quasi noir. |
| `--ds-border` | `44 6% 20%` | `240 9% 15%` | Filets plus discrets sur fond noir. |
| `--ds-border-strong` | `44 7% 28%` | `240 10% 20%` | idem |
| `--ds-text` | `44 28% 92%` | `240 12% 94%` | Neutre froid, plus lisible sur noir. |
| `--ds-text-muted` | `44 10% 62%` | `235 7% 68%` | idem |
| `--ds-ok` | `145 55% 42%` | `98 57% 56%` **#7ece4e** | Vert des diffs et du « c'est vert », lisible en 8px. |
| `--ds-warn` | `37 100% 50%` | `48 71% 58%` **#e0c34a** | Or : ne se confond plus avec l'accent, qui était orange lui aussi. |
| `--ds-danger` | `4 72% 52%` | `3 80% 63%` **#ec5f57** | Rouge plus clair, lisible sur noir. |

⚠ **`--ds-warn` était identique à `--ds-accent-2`** (`37 100% 50%`) : un pane
« en attente d'entrée » et un bouton de marque avaient exactement la même
couleur. C'est corrigé — l'or et l'orange sont maintenant distincts.

## Ce qui est ajouté

| Token | Valeur | Usage |
|---|---|---|
| `--ds-text-faint` | `235 5% 45%` | Timestamps, numéros de ligne, placeholders. Manquait : ces éléments utilisaient `--ds-text-muted` et pesaient trop lourd. |
| `--ds-voice`, `--ds-voice-2` | `218 100% 65%` / `217 100% 75%` | Bridge. Seul îlot froid, jamais utilisé pour un état d'agent. |
| `--ds-voice-bg`, `--ds-voice-line` | `224 33% 6%` / `222 31% 15%` | Fond et filets du panneau Bridge. |
| `--ds-agent-{claude,codex,cursor,gemini,opencode}` | 5 teintes | Une couleur par runtime, stable partout : pane, carte board, nœud swarm, avatar. |
| `--ds-purple`, `--ds-cyan`, `--ds-pink` | | Tags de skills, nœuds mémoire. |
| `--ds-shadow-lg` | | **Était référencé par `.kbd-panel` sans être défini** — le fallback masquait le bug. |
| `--ds-dock-w` | `340px` | Dock droit (Browser / Editor / Skills / Bridge). |
| `--ds-pane-*` | 8 tokens | Échelle de densité (voir ci-dessous). |

## Densité — `[data-density]`

Poser l'attribut sur `.workspace-view` (ou `body`). Il pilote 8 variables d'un coup :

| Palier | `--ds-pane-fs` | `--ds-pane-min-h` | Usage |
|---|---|---|---|
| `cozy` (défaut) | 12px | 200px | 1–4 agents |
| `compact` | 11px | 160px | 4–6 agents |
| `dense` | 10px | 128px | 6–12 agents |
| `micro` | 9px | 104px | 12–16 agents, plein écran |

`terminal.css` ne contient plus une seule taille de police en dur pour les
panes : tout descend de ces variables, xterm compris.

## Rappel de discipline

`terminal.css` et `observer.css` ne définissent **aucune couleur en dur**
(vérifié : zéro hexadécimal hors des blocs de tokens). Rethémer le produit =
éditer les `:root` de `design-system.css`, rien d'autre.
