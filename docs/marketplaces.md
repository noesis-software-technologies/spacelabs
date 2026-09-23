# apps/marketplaces — eBay & CardMarket

Référencement industrialisé des cartes sur **eBay** (vente directe + enchères) et
**CardMarket** (dépôt de stock sur catalogue). Réutilise la carte source de
`apps/vinted` (titre/description/prix/images/état). Le suivi des ventes se fait
dans le gestionnaire de commandes (`apps/vinted`, `VintedOrder.plateforme`).

**Aucun secret en dépôt** : toutes les clés sont des variables d'environnement
lues dans `.env.local` (gitignoré). Les clients échouent proprement (message
« Clés manquantes dans .env.local : … ») tant que les clés ne sont pas fournies.

## Modèle

`MarketListing` — une mise en vente sur une plateforme : `plateforme`
(ebay/cardmarket), `listing_type` (fixed/auction), carte source, prix, prix de
réserve, durée, état, `external_id` (n° annonce/offre), `catalog_id` (produit
CardMarket), `statut` (brouillon/publié/erreur/vendu/clôturé), `message`
(dernière erreur API). CRUD via l'admin Django.

## eBay

Deux familles d'API selon le type de vente :
- **Prix fixe (vente directe)** → Sell/Inventory API (REST) : inventory item →
  offer → publish.
- **Enchères** → Trading API (`AddItem`, ListingType=Chinese) — la Sell API ne
  gère pas les enchères.

### Commandes

```bash
# préparer (brouillon, sans API)
python manage.py ebay_publish --from-vinted <ref> --type fixed   --prix 39 --etat mint
python manage.py ebay_publish --from-vinted <ref> --type auction --prix 1 --reserve 30 --duree 7
# publier réellement (clés requises)
python manage.py ebay_publish --id <MarketListing> --publish
```

### Clés à fournir (`.env.local`)

Compte développeur eBay (developer.ebay.com), une app + un jeton utilisateur :
`EBAY_ENV`, `EBAY_MARKETPLACE` (def. `EBAY_FR`), puis soit `EBAY_OAUTH_TOKEN`
(jeton d'accès utilisateur, le plus simple), soit `EBAY_REFRESH_TOKEN` +
`EBAY_CLIENT_ID` + `EBAY_CLIENT_SECRET`. Pour les **enchères** :
`EBAY_TRADING_TOKEN` (Auth'n'Auth). Pour le **prix fixe** : `EBAY_CATEGORY_ID`,
`EBAY_MERCHANT_LOCATION_KEY` et les 3 policies
(`EBAY_FULFILLMENT_POLICY_ID`, `EBAY_PAYMENT_POLICY_ID`, `EBAY_RETURN_POLICY_ID`,
à créer dans le Seller Hub).

## CardMarket

Catalogue : on rattache la carte à un produit existant puis on dépose du stock.

### Commandes

```bash
# 1) trouver le produit dans le catalogue
python manage.py cardmarket_publish --search "Charizard ex 199/165"
# 2) déposer 1 ex. Near Mint à 39€ sur l'id produit retourné
python manage.py cardmarket_publish --product <idProduct> --prix 39 --condition near_mint --publish
# depuis une carte Vinted (son titre sert de recherche)
python manage.py cardmarket_publish --from-vinted <ref> --prix 39
```

### Clés à fournir (`.env.local`)

« Dedicated app » CardMarket (compte pro) → 4 jetons : `MKM_APP_TOKEN`,
`MKM_APP_SECRET`, `MKM_ACCESS_TOKEN`, `MKM_ACCESS_SECRET`. Plus `MKM_ENV`
(sandbox/production), `MKM_GAME_ID` (6 = Pokémon), `MKM_LANGUAGE_ID`
(7 = japonais). Auth OAuth 1.0a signée à chaque requête.

## État & validation

Le code est écrit d'après les specs eBay (Sell + Trading) et CardMarket (MKM
v2.0). Les flux hors-API (préparation de brouillons, gestion des clés manquantes)
sont testés. Le bout-en-bout API sera validé dès réception des clés — commencer
en `sandbox` avant de basculer en `production`.
