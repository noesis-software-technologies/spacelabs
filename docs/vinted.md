# apps/vinted — Assistant Vinted

Deux capacités complémentaires, sans aucun secret en dépôt (identifiants et
tokens vivent en `.env.local`, jamais commité) :

1. **Publication assistée** — de N photos à une annonce en ligne.
2. **Gestion de commandes** — suivi achat / vente / bénéfice + dashboard d'envois.

---

## 1. Publication assistée (`VintedListing`)

Pilotage de Chrome via CDP (Playwright `connect_over_cdp`). On garde un Chrome
lancé avec `--remote-debugging-port=9222`, connecté au compte Vinted ; la
commande s'y attache et remplit `items/new`.

> Réseau : en WSL2 miroir, le CDP répond sur `127.0.0.1:9222` (défaut du script).

### Flux (photos d'abord)

Uploader les photos **en premier** déclenche la reconnaissance produit de
Vinted, qui **pré-sélectionne la catégorie/sous-catégorie** — on saute l'étape
de recherche. Marque, état et colis ne sont pas auto-détectés :

1. upload photos → attente courte de l'auto-détection ;
2. titre / description / prix ;
3. catégorie (déjà remplie dans le cas nominal « carte à collectionner ») ;
4. **marque** : le champ `#brand` ouvre un menu (recherche + suggestions) — on
   clique l'option, on **ne** vise **pas** le rôle « textbox Marque » (il matche
   la barre de recherche de l'entête) ;
5. **état** (ex. « Neuf sans étiquette ») ;
6. **colis** : forcé (Vinted rebascule parfois sur « Moyen » selon la catégorie) ;
7. validation : on ferme le bandeau cookies puis on clique via
   `data-testid=upload-form-save-button` (il y a deux boutons « Ajouter »).

Style rédactionnel imposé (anti « sonne IA ») : trait d'union simple, pas de
mots tout en capitales, puces `-`. Appliqué par `clean_title` / `clean_desc`.

### Commandes

```bash
# 1) intake : N photos → annonce (choisit la photo de référence la plus lisible)
python manage.py vinted_ingest --img a.jpg --img b.jpg --prix 21 --etat neuf_sans --format S

# 2) titre / description (méthode du compte) + champs humains
python manage.py vinted_set <ref> --titre "..." --description "..." --marque Pokémon

# 3) remplir (screenshot de contrôle) puis publier
python manage.py vinted_publish <ref>            # remplit sans valider
python manage.py vinted_publish <ref> --publish  # one-shot : remplit + valide
```

Variables d'ambiance utiles : `CDP_URL`, `VINTED_SPEED` (0.5 = 2× plus vif),
`VINTED_DETECT_WAIT`.

---

## 2. Gestion de commandes (`VintedOrder`)

Une commande vendue = une ligne de suivi. Le **bénéfice n'est jamais saisi** :
c'est une propriété calculée, source unique de vérité.

| Champ | Rôle |
|---|---|
| `plateforme` | place de marché : `vinted` (défaut), `cardmarket`, `ebay` |
| `listing` | FK optionnelle vers l'annonce d'origine |
| `prix_achat` | coût d'acquisition |
| `prix_vente` | prix de vente (net vendeur) |
| `frais` | frais vendeur (port à charge, mise en avant, gradation…) |
| `benefice` *(calc.)* | `prix_vente - prix_achat - frais` |
| `marge_pct` *(calc.)* | bénéfice / prix d'achat |
| `statut_envoi` | `a_preparer → etiquette → expedie → livre → cloture` (ou `probleme`) |
| `transporteur`, `tracking` | suivi colis |
| `date_vente / _expedition / _livraison` | jalons |

### CRUD

- **Admin Django** : `/django-admin/` → *Commandes Vinted* (édition en masse du
  statut d'envoi, du transporteur et du tracking).
- **CLI** :

```bash
# enregistrer une vente (lie l'annonce via sa ref)
python manage.py vinted_order --add --titre "Blaziken ex 016/175" \
    --achat 8 --vente 21 --acheteur <pseudo> --listing <ref> --vendu 2026-09-23

# mettre à jour un envoi
python manage.py vinted_order --id 3 --statut expedie \
    --transporteur Chronopost --tracking XY123 --expedie 2026-09-23

# suivi
python manage.py vinted_order --list                # tout + bénéfice cumulé
python manage.py vinted_order --list --a-expedier   # reste à expédier
```

### Dashboard de vérification des envois

`/vinted/` (auth requise) :

- KPIs : nombre de commandes, ventes cumulées, coût d'achat, **bénéfice net**,
  marge moyenne, nombre à expédier ;
- **À préparer / expédier** : chaque ligne a un mini-formulaire (transporteur +
  n° de suivi) qui passe la commande en « Expédié » ;
- **En transit** + alerte **> 7 jours sans livraison** ;
- **Dernières commandes** : tableau achat / vente / bénéfice / marge / envoi.

---

## Multi-plateforme (CardMarket / eBay)

Le gestionnaire de commandes est déjà **agnostique** grâce au champ `plateforme`
(admin, CLI `--plateforme`, dashboard : compteurs + colonne par plateforme). Le
suivi achat/vente/bénéfice/envoi fonctionne donc à l'identique pour Vinted,
CardMarket et eBay dès aujourd'hui.

Restent à brancher, plateforme par plateforme, deux volets côté publication :
- **import des ventes** (récupérer les commandes payées : API/CSV CardMarket,
  API eBay Sell) pour alimenter les `VintedOrder` automatiquement ;
- **publication d'annonces** (équivalent de `vinted_publish` : API CardMarket /
  API eBay, sans pilotage navigateur puisque ces plateformes exposent une API).

## Sécurité

- Aucun identifiant ni token en dépôt : tout en `.env.local` (gitignoré).
- Aucune donnée personnelle acheteur au-delà du pseudo public Vinted.
- La publication remplit d'abord sans valider (screenshot `/tmp/vinted_<ref>.png`)
  pour contrôle ; `--publish` seulement quand tout est vérifié.
