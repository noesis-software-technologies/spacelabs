# SpaceLabs × Poké Poké — Proposition de déploiement

*Préparé par Noésis Software Technologies — SpaceLabs. Contact : spacelabs.ai.pro@gmail.com*
*Date : 18/09/2026 · Référent : Guillaume Barbat*

---

## 1. Le constat

Une enseigne food comme **Poké Poké** vit sur trois fronts qui mangent du temps :

- **Les messages clients** arrivent partout — Instagram DM, WhatsApp, mail — et un message raté = une commande ou une résa perdue.
- **La présence de contenu** (posts, actus, nouveautés carte) demande de la régularité que le rush de service laisse rarement.
- **Le suivi** (qui a répondu quoi, quel canal, quel coût) est éclaté.

## 2. Ce que SpaceLabs met en place

**a) Inbox unifié + réponses IA (validées avant envoi)**
Tous les DM Instagram / WhatsApp / mails atterrissent dans **une seule boîte**, triés automatiquement (*prioritaire / à répondre / reste*). Un **brouillon de réponse IA** est proposé dans le ton de la marque — vous **validez d'un clic**. Zéro message oublié.

**b) Veille & calendrier éditorial**
Rédaction **humanisée** de contenus (actus, nouveautés, événements), catégorisés et **planifiés** sur un calendrier, avec inter-maillage et visuels. Le contenu tourne sans y penser.

**c) Cockpit d'agents**
Des agents (type Claude Code) pilotables pour automatiser les tâches internes récurrentes, avec un **espace dédié par projet** (ex. l'espace « Valentin » déjà provisionné).

**d) Lecture des coûts**
Tableau de bord de consommation par espace / projet — vous voyez ce qui est consommé et où.

## 3. Déploiement

- **Installation en quelques minutes** (`install.sh`, idempotent), sur une machine du client.
- Option **100 % on-premise** avec **modèle local** (aucune clé API, données qui ne sortent pas) — déjà éprouvé.
- Branchement des canaux (Instagram / WhatsApp) via Meta Business — **webhook déjà opérationnel** côté SpaceLabs.

## 4. Prochaines étapes

1. **Cadrage (30 min)** — besoins précis Poké Poké, canaux à brancher, ton de marque.
2. **Pilote** sur un périmètre réduit (inbox + 1 canal social).
3. **Mise en production** + formation courte.

## 5. Investissement

*À affiner ensemble lors du cadrage — selon canaux, volume et option locale/cloud.*

---

> **Prochaine action : caler 30 min de cadrage.**
