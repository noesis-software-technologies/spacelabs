# Cahier des charges — IKARU

### Messagerie omnicanale centralisée pour Hikaru Distribution

*Version dédiée du produit SpaceLabs, adaptée au négoce de cartes et produits Pokémon (retail FR + grossiste JP).*
*Éditeur : Noésis Software Technologies · Contact : spacelabs.ai.pro@gmail.com · Date : 18/09/2026*

---

## 1. Contexte & enjeux

Hikaru Distribution reçoit **chaque jour un flux dispersé de sollicitations** provenant de revendeurs (boutiques FR) et de grossistes (JP), sur des canaux hétérogènes :

- **Instagram DM**, **WhatsApp**, **e-mail**, **Telegram**, **Messenger**, éventuellement **SMS**.
- Des demandes de natures très variées : disponibilité produit, **prix**, envoi de la **mercuriale** (grille tarifaire grossiste), **références** exactes, **devis**, **précommandes**, **suivi d'expédition**, **litiges**, **MOQ**, ouverture de compte revendeur…
- Une part importante en **japonais** (grossistes) et le reste en **français**.

**Douleurs actuelles :** messages éparpillés → risque d'oubli (= commande perdue), temps passé à jongler entre applications, réponses incohérentes selon qui répond, barrière de langue JP, ressaisie manuelle des prix/références, aucune vision consolidée de la charge ni des coûts.

## 2. Objectifs (mesurables)

| Objectif | Cible |
|---|---|
| Aucun message entrant non traité | 100 % des messages triés < 5 min |
| Délai de première réponse | Réduit à < 15 min en heures ouvrées |
| Temps de traitement par message | −60 % grâce aux brouillons IA |
| Canaux centralisés dans une seule boîte | Instagram, WhatsApp, e-mail, Telegram |
| Réponses bilingues cohérentes | FR + JP, ton de marque unifié |

## 3. Périmètre fonctionnel — les 20 tâches omnicanales

> Pour chaque tâche : **canaux** · **exemple entrant** · **action IKARU** · **gain**.

1. **Disponibilité / restock**
   Canaux : WhatsApp, Instagram, e-mail. Ex. FR : « Vous avez restocké les ETB 30th FR ? ». Action : triage prioritaire + brouillon de réponse IA avec l'état de stock à valider. Gain : réponse immédiate, pas de vente ratée.
2. **Demande de prix**
   Canaux : tous. Ex. FR : « Prix pour un lot de 10 ETB ? ». Action : lookup tarif + brouillon chiffré. Gain : plus de ressaisie, cohérence tarifaire.
3. **Envoi de la mercuriale**
   Canaux : e-mail, WhatsApp. Ex. JP : « 卸価格表を送ってください ». Action : réponse type + **pièce jointe mercuriale (PDF)** automatiquement proposée. Gain : envoi en 1 clic, toujours la bonne version.
4. **Recherche de référence produit**
   Canaux : WhatsApp, Telegram. Ex. FR : « La réf ETB-SV08-FR est dispo ? ». Action : résolution de la référence + dispo. Gain : zéro erreur de référence.
5. **Devis grossiste**
   Canaux : e-mail, WhatsApp, Telegram. Ex. FR : « Devis pour 3 displays Prismatic + 2 cartons ETB ». Action : brouillon de devis structuré (qté, PU, total). Gain : devis normalisés et rapides.
6. **Précommande**
   Canaux : tous. Ex. FR : « Précommander 4 cartons Prismatic Evolutions, délai et acompte ? ». Action : réponse avec conditions + création d'un suivi précommande. Gain : pipeline de précommandes maîtrisé.
7. **Suivi de commande / expédition**
   Canaux : WhatsApp, e-mail. Ex. JP : « 発送状況を教えてください。追跡番号は？ ». Action : récupération du statut + n° de suivi dans le brouillon. Gain : moins de relances entrantes.
8. **Réclamation / facture**
   Canaux : e-mail. Ex. FR : « Il manque la facture de septembre ». Action : priorité haute + brouillon avec la pièce. Gain : traitement rapide des litiges administratifs.
9. **MOQ (quantité minimale de commande)**
   Canaux : Instagram, e-mail. Ex. JP : « ブースターBOXのMOQと価格は？ ». Action : réponse type MOQ + tarif dégressif. Gain : réponses homogènes aux grossistes.
10. **Négociation de volume**
    Canaux : WhatsApp, e-mail. Ex. FR : « Sur 20 cartons, quel geste commercial ? ». Action : brouillon encadré par une grille de remises (à valider). Gain : marges protégées, cohérence commerciale.
11. **Onboarding / KYC nouveau revendeur**
    Canaux : e-mail, Instagram. Ex. JP : « 卸アカウントを開設したいです。必要書類は？ ». Action : envoi de la checklist documents + ouverture d'un dossier. Gain : onboarding standardisé.
12. **Réponse bilingue JP**
    Transverse. Action : détection de langue + brouillon **en japonais** dans le ton de la marque. Gain : lève la barrière de langue sans traducteur.
13. **Réponse bilingue FR**
    Transverse. Action : brouillon FR homogène. Gain : cohérence de marque.
14. **Relance devis / panier en attente**
    Canaux : WhatsApp, e-mail. Action : détection des devis sans réponse + brouillon de relance programmée. Gain : taux de transformation amélioré.
15. **Notification de réassort**
    Canaux : sortant (Instagram/WhatsApp/e-mail). Action : liste des clients en attente d'une réf + brouillon de notification de réassort. Gain : écoulement rapide des arrivages.
16. **Litige livraison**
    Canaux : Instagram, WhatsApp. Ex. FR : « Colis arrivé abîmé, 2 ETB écrasés ». Action : priorité haute + procédure SAV pré-remplie. Gain : résolution rapide, satisfaction client.
17. **Prise de commande**
    Canaux : tous. Action : extraction produits/quantités du message → brouillon de confirmation de commande. Gain : moins de ressaisie, moins d'erreurs.
18. **Upsell / cross-sell**
    Canaux : WhatsApp, Instagram. Ex. FR : « Vous avez aussi des sleeves et toploaders ? ». Action : suggestion d'articles complémentaires dans le brouillon. Gain : panier moyen en hausse.
19. **FAQ produits**
    Canaux : Telegram, Instagram. Ex. FR : « Différence display FR vs JP pour Écarlate & Violet ? ». Action : réponse depuis une base de connaissances produit. Gain : décharge le support des questions récurrentes.
20. **Reporting quotidien**
    Transverse. Action : synthèse de fin de journée (messages reçus/traités par canal, en attente, litiges, coûts IA). Gain : pilotage et visibilité de la charge.

## 4. Avantages les plus récurrents (top 5)

1. **Zéro message perdu** — la centralisation multicanale + le triage automatique éliminent le risque d'oubli (impact direct sur le CA).
2. **−60 % de temps par message** — les brouillons IA prêts à valider (dispo, prix, mercuriale, suivi) suppriment la ressaisie.
3. **Barrière de langue levée (JP)** — réponses en japonais cohérentes, sans traducteur ni délai.
4. **Cohérence tarifaire & de marque** — prix/mercuriale/ton unifiés quel que soit l'agent.
5. **Pilotage & coûts** — vision consolidée de la charge et **du coût IA (tokens)**, imputable par client.

## 5. Exigences techniques & non-fonctionnelles

- **Centralisation multicanale** : Instagram, WhatsApp, e-mail, Telegram (Messenger/SMS en option).
- **Intégration Meta** : réception Instagram/WhatsApp via **webhook** (déjà opérationnel côté SpaceLabs : vérification + abonnement `messages`). Publication d'app (App Review) requise pour les messages de tiers en production.
- **Réponses IA validées avant envoi** : aucun message sortant automatique — l'humain valide (bouton Copier / Régénérer / Envoyer).
- **Bilingue JP/FR** : détection de langue + génération dans la langue du client.
- **Pièces jointes** : envoi de la **mercuriale (PDF)** et documents (factures, devis).
- **Suivi & statuts** : nouveau / à répondre / traité, priorités, par canal.
- **Tableau de bord** : charge par canal + **suivi des coûts en tokens** (imputation par client/rush).
- **Option modèle local (on-premise)** : inférence sur machine du client, **données non exfiltrées** — déjà éprouvée (llama.cpp / modèle local).
- **Sécurité / RGPD** : secrets hors dépôt, journalisation, minimisation des données, hébergement au choix.

## 6. Livrables & planning

| Jalon | Contenu | Délai indicatif |
|---|---|---|
| **J0 — Cadrage** | Canaux, ton de marque, catalogue/mercuriale, règles de prix | Semaine 1 |
| **J1 — Pilote** | Inbox unifié + 1 canal social + brouillons IA FR/JP | Semaines 2-3 |
| **J2 — Extension** | Tous canaux + mercuriale + suivi commandes | Semaines 4-5 |
| **J3 — Production** | App Meta publiée, formation, tableau de bord coûts | Semaine 6 |

## 7. Critères d'acceptation

- 100 % des messages des canaux branchés apparaissent dans l'inbox unifié.
- Un brouillon IA pertinent est proposé pour ≥ 80 % des messages « à répondre ».
- Réponses JP validées par un locuteur de référence sur un échantillon.
- Envoi de la mercuriale en 1 action depuis un message.
- Tableau de bord affichant charge + coût tokens par client.

## 8. Hypothèses & points à confirmer avec Hikaru

- Catalogue produits + **mercuriale** à jour (source de vérité prix/références).
- Grille de remises volume (pour cadrer la négociation).
- Numéro **WhatsApp Business** rattaché à l'app Meta (pour WhatsApp en production).
- Périmètre exact des canaux (Messenger/SMS ?).
- Hébergement souhaité : cloud vs **on-premise** (données JP/UE).
- Volumétrie quotidienne réelle par canal (dimensionnement).

---

*IKARU — fork dédié de SpaceLabs. Ce document sert de base de cadrage et de feuille de route ; les montants et volumes seront affinés lors du cadrage (J0).*
