# Cocons sémantiques SEO/GEO — Agentic Pods · Noélabs · NSFT

Objectif : 3 cocons, zéro cannibalisation (1 intention = 1 URL), maillage interne
+ croisé inter-sites, optimisés SEO **et** GEO (moteurs génératifs : ChatGPT,
Perplexity, AI Overviews).

## Territorialisation (anti-cannibalisation)

Chaque domaine possède une intention distincte. Aucun ne cible le mot-clé d'un autre.

- **Agentic Pods** (agentic-pods.com) → agents IA / automatisation agentique. Cible : décideurs, ops.
- **Noélabs** (noelabs.com) → construire des produits IA (idée → MVP). Cible : founders, PM.
- **NSFT** (nsft.fr) → ingénierie logicielle sur mesure / fondamentaux tech. Cible : CTO, DSI.

Règle de non-chevauchement : le « comment coder » va à NSFT, le « comment
construire un produit IA » à Noélabs, le « comment automatiser avec des agents »
à Agentic Pods. Un même sujet vu sous 3 angles différents = 3 pages non
concurrentes, reliées par des liens croisés.

---

## Cocon 1 — Agentic Pods
**Pilier :** Agents IA : le guide complet de l'automatisation agentique
`/agents-ia-guide` (requête tête : « agent IA », « automatisation agentique »)

| # | Cluster (URL) | Requête cible | Intention | Liens |
|---|---|---|---|---|
| 1 | /quest-ce-quun-agent-ia | c'est quoi un agent IA | définition | → pilier |
| 2 | /agent-ia-vs-chatbot-rpa | agent ia vs chatbot | comparatif | → pilier ; → NSFT /architecture |
| 3 | /deployer-agent-ia-entreprise | déployer un agent IA | how-to | → pilier ; → Noélabs /poc-en-production |
| 4 | /cas-usage-agents-ia | cas d'usage agents IA | liste/inspiration | → pilier |
| 5 | /frameworks-agents-ia | meilleur framework agent IA | best/comparatif | → pilier ; → Noélabs /choisir-son-llm |
| 6 | /mcp-model-context-protocol | qu'est-ce que le MCP | définition tech | → pilier ; → Noélabs /rag-donnees |
| 7 | /orchestration-multi-agents | orchestration multi-agents | avancé | → pilier |
| 8 | /roi-automatisation-ia | ROI automatisation IA | décision/chiffres | → pilier ; → NSFT /prix-logiciel-sur-mesure |
| 9 | /securite-agents-ia | sécurité des agents IA | risques | → pilier ; → NSFT /securite-applicative |
| 10 | /erreurs-projet-agentique | erreurs projet IA agent | pièges | → pilier ; → Noélabs /erreurs-startup-ia |

---

## Cocon 2 — Noélabs
**Pilier :** Construire un produit IA : de l'idée au MVP
`/produit-ia-guide` (requête tête : « créer une application IA », « MVP IA »)

| # | Cluster (URL) | Requête cible | Intention | Liens |
|---|---|---|---|---|
| 1 | /creer-application-ia | créer une application IA | how-to | → pilier |
| 2 | /mvp-ia-rapide | MVP IA en quelques semaines | méthode | → pilier ; → NSFT /cahier-des-charges |
| 3 | /choisir-son-llm | quel LLM choisir | comparatif | → pilier ; → Agentic Pods /frameworks-agents-ia |
| 4 | /cout-developpement-ia | coût développement produit IA | budget | → pilier ; → NSFT /prix-logiciel-sur-mesure |
| 5 | /prototyper-avec-llm | prototype LLM | spike | → pilier |
| 6 | /rag-donnees | RAG brancher ses données | tech | → pilier ; → Agentic Pods /mcp-model-context-protocol |
| 7 | /poc-en-production | passer un POC IA en prod | how-to | → pilier ; → NSFT /ci-cd-devops |
| 8 | /studio-ia-vs-agence | studio IA vs agence dev | comparatif | → pilier ; → NSFT /externaliser-developpement |
| 9 | /roadmap-projet-ia | étapes d'un projet IA | roadmap | → pilier |
| 10 | /erreurs-startup-ia | erreurs founders IA | pièges | → pilier ; → Agentic Pods /erreurs-projet-agentique |

---

## Cocon 3 — NSFT
**Pilier :** Développement logiciel sur mesure : le guide complet
`/developpement-sur-mesure-guide` (requête tête : « développement logiciel sur mesure »)

| # | Cluster (URL) | Requête cible | Intention | Liens |
|---|---|---|---|---|
| 1 | /sur-mesure-vs-saas | sur mesure vs SaaS | comparatif | → pilier |
| 2 | /prix-logiciel-sur-mesure | prix logiciel sur mesure | budget | → pilier ; → Noélabs /cout-developpement-ia |
| 3 | /choisir-stack-technique | choisir sa stack | décision tech | → pilier ; → Agentic Pods /frameworks-agents-ia |
| 4 | /securite-applicative | sécurité application (OWASP, RGPD) | risques | → pilier ; → Agentic Pods /securite-agents-ia |
| 5 | /monolithe-vs-microservices | monolithe vs microservices | architecture | → pilier |
| 6 | /externaliser-developpement | externaliser son dev | décision | → pilier ; → Noélabs /studio-ia-vs-agence |
| 7 | /cahier-des-charges | rédiger un cahier des charges | how-to | → pilier ; → Noélabs /mvp-ia-rapide |
| 8 | /tma-maintenance | maintenance TMA | service | → pilier |
| 9 | /ci-cd-devops | CI/CD DevOps | tech | → pilier ; → Noélabs /poc-en-production |
| 10 | /refonte-legacy | refonte logiciel legacy | how-to | → pilier |

---

## Règles de maillage

- **Interne** : chaque cluster pointe vers son pilier (ancre = requête cible exacte) ; le pilier liste et pointe vers ses 10 clusters ; liens entre clusters complémentaires du même cocon.
- **Croisé inter-sites** : 1 à 2 liens par article vers la page d'un autre domaine, seulement quand l'intention le justifie (voir colonne Liens). Ancres variées, jamais répétées à l'identique. Objectif : autorité thématique partagée sans concurrence.

## Couche GEO (par article)

- Réponse directe en tête (TL;DR / définition en 2-3 phrases).
- Bloc FAQ (3-5 Q/R) → `schema.org/FAQPage`.
- `schema.org/Article` + `Organization` + auteur (E-E-A-T).
- Données chiffrées, entités nommées, listes claires (extractibles par les LLM).
- Format « answer-first » : la réponse avant le contexte.

## Production

Réutilise le moteur Yonkko : rédaction humanisée (prompt anti-détection),
détecteur maison, moisson RSS-direct par site. Un writer par cocon avec la ligne
éditoriale du domaine ; pub_date étalées ; images natives (flux) ou stock.
Branchement dès réception des MCP de noelabs.com et nsft.fr.
