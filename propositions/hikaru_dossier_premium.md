# IKARU — Dossier client premium

### Messagerie omnicanale centralisée, à réponses IA validées, bilingue FR / JP

**Préparé pour Hikaru Distribution**
*Éditeur : Noésis Software Technologies — plateforme SpaceLabs*
*Contact : spacelabs.ai.pro@gmail.com · Date : 18/09/2026*
*Déclinaison dédiée du produit SpaceLabs, adaptée au négoce de cartes et produits Pokémon (retail FR + grossiste JP).*

---

## 1. Résumé exécutif

Hikaru Distribution vend vite, sur plusieurs canaux, dans deux langues. C'est une force commerciale — et un point de fuite silencieux : chaque message reçu sur Instagram, WhatsApp, e-mail ou Telegram qui n'est pas vu, pas trié, ou pas répondu à temps représente une commande, une précommande ou un compte revendeur qui part ailleurs.

**IKARU** est une déclinaison dédiée de la plateforme SpaceLabs conçue pour ce problème précis. Tous vos canaux convergent dans **une seule boîte**, triée automatiquement par priorité. Pour chaque message, l'IA propose un **brouillon de réponse prêt à valider** — dans la bonne langue (français ou japonais), au ton de la marque, avec le bon prix, la bonne référence, la bonne mercuriale. **Vous validez d'un clic. Rien n'est envoyé automatiquement.**

Résultat visé, présenté comme **estimation de cadrage** (hypothèses explicitées en section 5) :

- **Zéro message perdu** — 100 % des messages des canaux branchés centralisés et triés en moins de 5 minutes.
- **Environ −60 % de temps de traitement par message** grâce aux brouillons pré-remplis (dispo, prix, mercuriale, suivi).
- **Barrière de langue JP levée** — réponses en japonais cohérentes, sans traducteur ni délai.
- **Pilotage complet** — vision consolidée de la charge par canal et du **coût IA en tokens**, imputable par client.

Deux garanties de confiance dès le départ : le **webhook Meta (Instagram / WhatsApp) est déjà opérationnel** côté SpaceLabs, et une **option 100 % locale (on-premise)** permet de traiter les données de vos partenaires JP et UE **sans qu'elles quittent votre machine**.

> **Prochaine action recommandée : un cadrage de 30 minutes** pour brancher un premier canal et lancer un pilote.

---

## 2. Le problème Hikaru — le coût invisible du multicanal

Hikaru Distribution reçoit **chaque jour un flux dispersé de sollicitations**, de deux populations aux attentes différentes :

- des **revendeurs FR** (boutiques) qui veulent une réponse rapide sur la dispo, le prix, la réf ;
- des **grossistes JP** qui écrivent en japonais et attendent une mercuriale, un MOQ, un devis structuré.

Ces demandes arrivent sur **Instagram DM, WhatsApp, e-mail, Telegram, Messenger, parfois SMS**, et portent sur des sujets hétérogènes : disponibilité, prix, **mercuriale** (grille tarifaire grossiste), références exactes, devis, précommandes, suivi d'expédition, litiges, MOQ, ouverture de compte revendeur.

### Où l'argent se perd

| Point de friction | Conséquence directe |
|---|---|
| Messages éparpillés sur 4-6 applications | Un message oublié = **une commande perdue** |
| Jonglage permanent entre outils | Temps commercial dilué, attention fragmentée |
| Réponses variables selon qui répond | Incohérence de prix et de ton, image affaiblie |
| Sollicitations en japonais | Latence, dépendance à un traducteur, risque d'erreur |
| Ressaisie manuelle prix / références | Erreurs de devis, lenteur, marge non maîtrisée |
| Aucune vue consolidée de la charge ni des coûts | Impossible de piloter, de prioriser, d'anticiper le rush |

**Le nœud du problème :** ce n'est pas un manque d'effort, c'est un manque de **centralisation** et d'**assistance**. Le premier canal qui déborde pendant un pic d'arrivage (restock, précommande d'un set attendu) est précisément celui où se trouvent les plus grosses commandes. La perte n'est pas visible dans un tableau — elle se lit dans les ventes qui ne se sont jamais faites.

---

## 3. La solution IKARU — vision produit

IKARU n'est pas un chatbot. C'est un **poste de pilotage commercial omnicanal** qui met un humain aux commandes, assisté par l'IA à chaque message. Quatre principes structurent le produit.

**a) Centralisation — une seule boîte.**
Instagram DM, WhatsApp, e-mail et Telegram (Messenger / SMS en option) atterrissent au même endroit, triés automatiquement en *prioritaire / à répondre / reste*. Fini le jonglage entre applications ; la charge devient lisible et gouvernable.

**b) IA validée avant envoi — jamais d'automatisme aveugle.**
Pour chaque message, IKARU prépare un **brouillon** au ton de la marque, avec les bonnes données (stock, prix, référence, suivi). L'humain garde la main : boutons **Copier / Régénérer / Envoyer**. **Aucun message sortant automatique.** Vous gagnez la vitesse de l'IA sans en subir les dérapages.

**c) Bilingue FR / JP nativement.**
Détection automatique de la langue entrante, génération de la réponse **dans la langue du client** — un japonais idiomatique et cohérent pour vos grossistes, un français homogène pour vos revendeurs. La barrière de langue disparaît sans traducteur ni délai.

**d) Souveraineté des données — option on-premise.**
IKARU fonctionne en cloud **ou** en **100 % local** : inférence sur une machine que vous contrôlez, **aucune clé API, aucune donnée exfiltrée** — une architecture déjà éprouvée côté SpaceLabs (modèle local type llama.cpp). Vos prix, vos partenaires, vos flux JP restent chez vous.

À cela s'ajoute une **lecture des coûts** en continu : consommation IA en tokens, imputable par client ou par période de rush — pour que la performance reste maîtrisée financièrement.

---

## 4. Les 20 tâches omnicanales

### 4.1 Tableau synthétique

Légende : **Canaux** — WA (WhatsApp), IG (Instagram), Mail, Tel (Telegram), *tous*, *sortant*, *transverse*.

| # | Tâche | Canaux | Exemple entrant (FR / JP) | Action IKARU | Gain |
|---|---|---|---|---|---|
| 1 | Disponibilité / restock | WA · IG · Mail | FR : « Vous avez restocké les ETB 30th FR ? » | Triage prioritaire + brouillon avec état de stock à valider | Réponse immédiate, pas de vente ratée |
| 2 | Demande de prix | *tous* | FR : « Prix pour un lot de 10 ETB ? » | Lookup tarif + brouillon chiffré | Fin de la ressaisie, cohérence tarifaire |
| 3 | Envoi de la mercuriale | Mail · WA | JP : « 卸価格表を送ってください » | Réponse type + **PJ mercuriale (PDF)** proposée | Envoi en 1 clic, toujours la bonne version |
| 4 | Recherche de référence produit | WA · Tel | FR : « La réf ETB-SV08-FR est dispo ? » | Résolution de la référence + dispo | Zéro erreur de référence |
| 5 | Devis grossiste | Mail · WA · Tel | FR : « Devis 3 displays Prismatic + 2 cartons ETB » | Brouillon de devis structuré (qté, PU, total) | Devis normalisés et rapides |
| 6 | Précommande | *tous* | FR : « Précommander 4 cartons Prismatic, délai et acompte ? » | Réponse conditions + création d'un suivi précommande | Pipeline de précommandes maîtrisé |
| 7 | Suivi commande / expédition | WA · Mail | JP : « 発送状況を教えてください。追跡番号は？ » | Statut + n° de suivi dans le brouillon | Moins de relances entrantes |
| 8 | Réclamation / facture | Mail | FR : « Il manque la facture de septembre » | Priorité haute + brouillon avec la pièce | Traitement rapide des litiges administratifs |
| 9 | MOQ (quantité minimale) | IG · Mail | JP : « ブースターBOXのMOQと価格は？ » | Réponse type MOQ + tarif dégressif | Réponses homogènes aux grossistes |
| 10 | Négociation de volume | WA · Mail | FR : « Sur 20 cartons, quel geste commercial ? » | Brouillon encadré par une grille de remises (à valider) | Marges protégées, cohérence commerciale |
| 11 | Onboarding / KYC revendeur | Mail · IG | JP : « 卸アカウントを開設したいです。必要書類は？ » | Checklist documents + ouverture d'un dossier | Onboarding standardisé |
| 12 | Réponse bilingue JP | *transverse* | — | Détection de langue + brouillon **en japonais** au ton de marque | Barrière de langue levée |
| 13 | Réponse bilingue FR | *transverse* | — | Brouillon FR homogène | Cohérence de marque |
| 14 | Relance devis / panier en attente | WA · Mail | — | Détection des devis sans réponse + relance programmée | Taux de transformation amélioré |
| 15 | Notification de réassort | *sortant* | — | Liste des clients en attente d'une réf + brouillon de notif | Écoulement rapide des arrivages |
| 16 | Litige livraison | IG · WA | FR : « Colis abîmé, 2 ETB écrasés » | Priorité haute + procédure SAV pré-remplie | Résolution rapide, satisfaction client |
| 17 | Prise de commande | *tous* | — | Extraction produits/quantités → brouillon de confirmation | Moins de ressaisie, moins d'erreurs |
| 18 | Upsell / cross-sell | WA · IG | FR : « Vous avez aussi sleeves et toploaders ? » | Suggestion d'articles complémentaires dans le brouillon | Panier moyen en hausse |
| 19 | FAQ produits | Tel · IG | FR : « Différence display FR vs JP pour Écarlate & Violet ? » | Réponse depuis une base de connaissances produit | Décharge le support des questions récurrentes |
| 20 | Reporting quotidien | *transverse* | — | Synthèse de fin de journée (reçus/traités, en attente, litiges, coûts IA) | Pilotage et visibilité de la charge |

### 4.2 Focus détaillé — le top 5 récurrent

Ces cinq tâches concentrent l'essentiel du volume quotidien et de la valeur créée.

**① Disponibilité / restock (tâche 1) — le point de contact le plus critique.**
Un client qui demande « c'est restocké ? » est un client prêt à acheter *maintenant*. IKARU classe ces messages en priorité haute et propose un brouillon avec l'état de stock. Le délai de réponse chute ; la fenêtre d'achat ne se referme pas. C'est le levier le plus direct sur le chiffre d'affaires.

**② Demande de prix (tâche 2) — la fin de la ressaisie.**
Le prix est demandé partout, tout le temps, souvent en lot. IKARU va chercher le tarif et prépare un brouillon chiffré cohérent, quel que soit l'agent qui traite le message. Plus d'erreurs de saisie, plus d'écarts de prix d'un interlocuteur à l'autre — une image de sérieux vis-à-vis des revendeurs comme des grossistes.

**③ Envoi de la mercuriale (tâche 3) — un clic, toujours la bonne version.**
Pour les grossistes JP, la mercuriale est le document d'entrée en relation. IKARU détecte la demande (y compris en japonais : « 卸価格表を送ってください »), rédige la réponse d'accompagnement et **joint automatiquement le PDF à jour**. Fini les envois de versions obsolètes ou la recherche du bon fichier.

**④ Réponse bilingue JP (tâche 12) — parler japonais sans traducteur.**
Transversale à tous les canaux, c'est la capacité qui débloque le segment grossiste. IKARU détecte le japonais entrant et génère une réponse idiomatique dans le ton de la marque. Vous répondez à un partenaire d'Osaka aussi vite qu'à une boutique de Lyon — sans intermédiaire, sans latence, sans perte de nuance commerciale.

**⑤ Devis grossiste (tâche 5) — des devis normalisés en minutes.**
IKARU structure automatiquement le brouillon de devis (quantités, prix unitaires, total) à partir d'un message parfois brouillon (« 3 displays Prismatic + 2 cartons ETB »). Le commercial valide et envoie. Les devis deviennent rapides, homogènes et sans erreur de calcul — un gain net sur le cycle de vente grossiste.

---

## 5. Bénéfices & ROI

> **Cadre méthodologique.** Les chiffres ci-dessous sont des **hypothèses de cadrage**, à confirmer avec la volumétrie réelle de Hikaru lors du J0. Ils illustrent l'ordre de grandeur du gain, pas une garantie contractuelle.

### 5.1 Objectifs mesurables visés

| Objectif | Cible |
|---|---|
| Aucun message entrant non traité | 100 % des messages triés < 5 min |
| Délai de première réponse | < 15 min en heures ouvrées |
| Temps de traitement par message | ≈ −60 % grâce aux brouillons IA |
| Canaux centralisés dans une seule boîte | Instagram, WhatsApp, e-mail, Telegram |
| Réponses bilingues cohérentes | FR + JP, ton de marque unifié |

### 5.2 Estimation du temps gagné (illustratif)

**Hypothèses de travail (à valider) :**

- Volume : **120 messages / jour** tous canaux confondus (revendeurs + grossistes).
- Temps moyen actuel par message (lecture, recherche prix/réf, rédaction, éventuelle traduction) : **4 minutes**.
- Réduction via brouillons IA pré-remplis validés d'un clic : **−60 %**, soit ≈ 2,4 min économisées par message.

**Projection :**

| Indicateur | Sans IKARU | Avec IKARU | Gain |
|---|---|---|---|
| Temps / message | 4,0 min | ≈ 1,6 min | −2,4 min |
| Temps quotidien (120 msg) | 8,0 h | ≈ 3,2 h | **≈ 4,8 h / jour** |
| Sur 22 jours ouvrés | ≈ 176 h | ≈ 70 h | **≈ 106 h / mois** |

Soit l'équivalent d'un **temps plein commercial** rendu à des tâches à plus forte valeur (négociation, sourcing, développement grossistes JP). *Ces valeurs se recalculent avec vos chiffres réels au cadrage.*

### 5.3 Impact commercial

- **Taux de réponse.** Zéro message perdu + première réponse < 15 min : la probabilité de convertir un message chaud (restock, précommande) augmente mécaniquement. Un message répondu dans le quart d'heure surclasse une réponse le lendemain.
- **Panier moyen.** Les suggestions d'upsell / cross-sell intégrées au brouillon (sleeves, toploaders, produits complémentaires) élèvent le panier sans effort de rédaction.
- **Rétention & confiance.** Cohérence tarifaire, réponses JP idiomatiques, devis propres : une image de distributeur fiable qui fidélise revendeurs et grossistes.
- **Marge protégée.** La négociation de volume est encadrée par une grille de remises — l'IA ne concède jamais au-delà de vos règles.

### 5.4 Les 5 bénéfices les plus récurrents

1. **Zéro message perdu** — centralisation + triage automatique éliminent l'oubli (impact direct sur le CA).
2. **≈ −60 % de temps par message** — brouillons prêts à valider (dispo, prix, mercuriale, suivi).
3. **Barrière de langue JP levée** — réponses japonaises cohérentes, sans traducteur ni délai.
4. **Cohérence tarifaire & de marque** — prix, mercuriale et ton unifiés quel que soit l'agent.
5. **Pilotage & coûts** — vision consolidée de la charge et du coût IA (tokens), imputable par client.

---

## 6. Architecture & sécurité

IKARU repose sur une architecture éprouvée sur la plateforme SpaceLabs, pensée pour la fiabilité et la souveraineté des données.

**Centralisation multicanale.**
Réception unifiée d'Instagram, WhatsApp, e-mail et Telegram (Messenger / SMS en option), avec statuts (*nouveau / à répondre / traité*), priorités et vue par canal.

**Intégration Meta — déjà opérationnelle.**
Réception Instagram / WhatsApp via **webhook** déjà en place côté SpaceLabs (vérification + abonnement à l'événement `messages`). La mise en production des messages de tiers requiert la publication de l'app (App Review Meta) et un numéro **WhatsApp Business** rattaché — étapes intégrées au planning.

**Réponses IA validées avant envoi.**
Aucun envoi automatique. Chaque réponse est un brouillon soumis à l'humain (**Copier / Régénérer / Envoyer**). C'est le garde-fou qui rend l'IA utilisable en contexte commercial réel.

**Bilingue FR / JP.**
Détection de langue à l'entrée, génération dans la langue du client. Validation possible des réponses JP par un locuteur de référence sur un échantillon en phase pilote.

**Pièces jointes.**
Envoi de la **mercuriale (PDF)** et de documents (factures, devis) directement depuis un message, en une action.

**Option 100 % locale (on-premise).**
Inférence sur machine du client, **aucune donnée exfiltrée, aucune clé API** — architecture déjà éprouvée (modèle local). Idéale pour les données sensibles FR/UE et les échanges grossistes JP. Installation rapide et idempotente (`install.sh`) sur une machine du client.

**Sécurité & RGPD.**
Secrets hors dépôt, journalisation, minimisation des données, hébergement au choix (cloud ou on-premise). Le mode local garantit que les données ne franchissent pas votre périmètre.

**Suivi des coûts.**
Tableau de bord de charge par canal et de **consommation IA en tokens**, imputable par client ou par période — la performance reste financièrement lisible.

---

## 7. Déploiement

Un déploiement progressif, du pilote à la production, avec une **démo live IKARU déjà disponible** pour matérialiser la solution dès le premier échange.

| Jalon | Contenu | Délai indicatif |
|---|---|---|
| **J0 — Cadrage** | Canaux, ton de marque, catalogue / mercuriale, règles de prix | Semaine 1 |
| **J1 — Pilote** | Inbox unifié + 1 canal social + brouillons IA FR / JP | Semaines 2-3 |
| **J2 — Extension** | Tous canaux + mercuriale + suivi commandes | Semaines 4-5 |
| **J3 — Production** | App Meta publiée, formation, tableau de bord coûts | Semaine 6 |

**Déjà en place aujourd'hui :**

- Webhook Meta (Instagram / WhatsApp) opérationnel côté SpaceLabs.
- Option modèle local éprouvée (données non exfiltrées).
- Installation idempotente en quelques minutes sur une machine du client.
- Démo live IKARU présentable en cadrage.

**Critères d'acceptation :**

- 100 % des messages des canaux branchés apparaissent dans l'inbox unifié.
- Un brouillon IA pertinent est proposé pour ≥ 80 % des messages « à répondre ».
- Réponses JP validées par un locuteur de référence sur un échantillon.
- Envoi de la mercuriale en 1 action depuis un message.
- Tableau de bord affichant charge + coût tokens par client.

---

## 8. Modalités & prochaines étapes

L'investissement (canaux, volume, option locale vs cloud) est **affiné ensemble au cadrage** — il dépend directement de votre volumétrie réelle et du périmètre choisi.

**Points à confirmer avec Hikaru (préparés pour le J0) :**

- Catalogue produits + **mercuriale** à jour (source de vérité prix / références).
- Grille de remises volume (pour cadrer la négociation).
- Numéro **WhatsApp Business** rattaché à l'app Meta.
- Périmètre exact des canaux (Messenger / SMS ?).
- Hébergement souhaité : cloud vs **on-premise** (données JP / UE).
- Volumétrie quotidienne réelle par canal (dimensionnement).

**Prochaine étape — un cadrage de 30 minutes** pour cerner vos besoins, brancher un premier canal et lancer un pilote.

> **Appel à l'action : réservons 30 minutes cette semaine.**
> Un simple rappel téléphonique suffit à démarrer.
> **Contact : spacelabs.ai.pro@gmail.com**

---

## 9. Annexe — glossaire

- **Mercuriale** — grille tarifaire destinée aux grossistes / revendeurs (prix par référence, souvent au format PDF). Document d'entrée en relation avec un grossiste.
- **MOQ** *(Minimum Order Quantity)* — quantité minimale de commande exigée pour un produit ou un tarif dégressif.
- **On-premise** — exécution du logiciel et de l'IA sur une machine contrôlée par le client, sans dépendance au cloud : les données ne sortent pas du périmètre de l'entreprise.
- **Webhook** — mécanisme par lequel un service tiers (ici Meta pour Instagram / WhatsApp) notifie IKARU en temps réel de l'arrivée d'un message, sans que l'application ait à interroger le service en boucle.

---

*IKARU — déclinaison dédiée de SpaceLabs. Ce dossier consolide la proposition de déploiement et le cahier des charges omnicanal. Les montants et volumes sont affinés lors du cadrage (J0) ; les estimations de ROI sont des hypothèses de travail, non des engagements contractuels.*
