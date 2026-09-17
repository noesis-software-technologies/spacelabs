# Podcast Studio — Setup Concept

**Session :** 2026-09-07
**Conversation :** podcast studio

## Dimensions

| Axe | Valeur |
|-----|--------|
| Longueur | 390 cm |
| Profondeur | 280 cm |
| Hauteur | ~240 cm |

## Layout

```
[MUR ÉCRAN / LATTES BOIS] ←── 390 cm ──→ [MUR CAMÉRAS]
         x=0                                    x=390cm
┌─────────────────────────────────────────────────────┐
│  ▐██▌ Écran TV                    📱📱📱📱 Phones  │  z=280
│                                    (tripods)         │
│  🪑   Fauteuil 1     🎙            caméras         │
│  🪑   Fauteuil 2     🎙            ×4 angles       │
│  [table basse]                                       │
│                                                      │  z=0
│                          💻 PC Régie (mur arrière) │
└─────────────────────────────────────────────────────┘
```

## Éléments

### Mur Écran (x=0)
- Lattes bois verticales sur toute la hauteur (déco, fond visuel)
- Écran TV monté au mur (~65"+ recommandé)
- Lumière d'ambiance derrière les lattes optionnel (LED strip)

### Zone hôtes (côté x=0)
- 2 fauteuils directement au mur (dos aux lattes)
- Table basse entre les deux
- 2 micros sur pieds/perches

### PC Régie (mur arrière ou latéral)
- Ordinateur + écran de monitoring
- Câbles vers la TV et les périphériques

### Mur caméra (x=390cm)
- 4 téléphones sur trépieds à différentes hauteurs/angles
- Vue frontale (face aux hôtes)
- Vue ¾ possible si rotation des trépieds

## Contraintes

- Profondeur 280 cm = limitée → hôtes au mur pour maximiser la distance de prise de vue
- Distance hôtes ↔ caméras : ~330–360 cm (excellent pour smartphones en 4K)
- Lattes bois = fond scénique propre, pas besoin de fond séparé

## Fichier 3D

`/home/noesis/.openclaw/workspace/media/podcast_studio_3d.html`
(Ouvrir dans un navigateur, Three.js interactif)

## Chaîne de capture / streaming (Blackmagic Camera + VDO.Ninja + OBS)

**Objectif :** rendu pro depuis 4 smartphones (Blackmagic Camera) vers OBS/multistream.

### Vidéo (par caméra)
1. Blackmagic Camera en **clean feed** : LUT appliquée, shutter 1/48–1/50, ISO/BB réglés, overlays masqués.
2. **VDO.Ninja Screen Share** du clean feed (l'app Blackmagic possède la caméra → pas d'accès direct au flux gradé).
   - Publisher phone : `vdo.ninja/?push=CAM1&screenshare&bitrate=6000&codec=h264&quality=0`
   - OBS : Source navigateur `vdo.ninja/?view=CAM1`, 1920×1080, 30 fps.
3. Option "money shot" : 1 phone principal via **USB-C→HDMI→carte d'acquisition (Cam Link)** = image pristine sans compression.

### Audio (priorité podcast)
- Micros → **interface audio dédiée** (Rødecaster / USB) → OBS en direct.
- **Ne pas** router l'audio via VDO.Ninja (compression, latence, désync). L'audio interface est la référence, la vidéo se cale dessus.

### Réseau & thermique
- 4 flux WebRTC 1080p → **5 GHz solide ou LAN** (USB-C ethernet sur les phones si possible).
- **Cible 1080p** (pas 4K) sur long live pour éviter le throttling thermique.
- Verrouiller **25 ou 30 fps** partout ; vérifier le **lip-sync** (offset audio par scène OBS si besoin).

### Pièges
- **Clean feed ≠ gradé** : vérifier qu'il sort la LUT et pas le log/flat.
- **Latences inégales** entre cams : OK pour couper, mais caler sur l'audio maître.

### OBS
- Scène **« Podcast »** : 4 sources navigateur (angles) + audio interface + lower-thirds, en **Mode Studio** pour switcher.
- Scène **« Vitrine »** (capture desktop `http://localhost:8000/vitrine/`) en intermède.
- Sortie : multistream Twitch/Kick existant (cf. `spacelabs-live-runbook.md`).
