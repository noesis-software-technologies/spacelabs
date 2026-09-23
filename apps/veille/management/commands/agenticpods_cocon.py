"""Génère et pousse le cocon sémantique Agentic Pods (agentic-pods.com, blog #19).

1 pilier + 10 clusters (voir docs/cocons_seo_geo.md, Cocon 1). Rédaction via
`claude -p` : ligne éditoriale « agents IA / automatisation agentique » pour
décideurs et ops, HUMANISÉE (aucune trace IA) + couche GEO (réponse directe en
tête, FAQ extractible, entités, listes). Maillage interne par `ref` (résolu à
l'URL même si la cible est créée après), dates rétroactives étalées.

Reprenable : ne pousse que les refs pas encore présentes dans list_drafts.
Détectable (score maison) : refuse une rédaction jugée trop « IA ».

Usage :
  python manage.py agenticpods_cocon            # tout le cocon
  python manage.py agenticpods_cocon --only agents-ia-guide
  python manage.py agenticpods_cocon --dry-run  # génère + score, ne pousse pas
"""
import json
import re
import subprocess

from django.conf import settings
from django.core.management.base import BaseCommand
from apps.veille.models import Blog
from apps.veille import mcp, detector

BLOG_ID = 19
CLAUDE = getattr(settings, "COCKPIT_CLAUDE_BIN", "claude")
PILLAR = "agents-ia-guide"

# Cocon 1 - Agentic Pods (docs/cocons_seo_geo.md). Maillage interne uniquement
# (les liens croisés Noélabs/NSFT seront ajoutés quand leurs MCP seront branchés).
COCON = [
    {
        "ref": PILLAR, "kind": "pilier",
        "title": "Agents IA : le guide complet de l'automatisation agentique",
        "query": "agent IA, automatisation agentique",
        "angle": "Guide pilier de référence : ce qu'est un agent IA, comment il diffère de l'automatisation classique, l'architecture (perception, raisonnement, action, mémoire, outils), les cas d'usage en entreprise, comment démarrer, les risques. Sert de hub qui oriente vers les 10 articles clusters.",
        "links": ["quest-ce-quun-agent-ia", "agent-ia-vs-chatbot-rpa", "deployer-agent-ia-entreprise",
                  "cas-usage-agents-ia", "frameworks-agents-ia", "mcp-model-context-protocol",
                  "orchestration-multi-agents", "roi-automatisation-ia", "securite-agents-ia",
                  "erreurs-projet-agentique"],
        "pub_date": "2026-08-18", "words": "1000 à 1300",
    },
    {
        "ref": "quest-ce-quun-agent-ia", "kind": "cluster",
        "title": "C'est quoi un agent IA ? Définition claire et exemples",
        "query": "c'est quoi un agent IA",
        "angle": "Définition simple et rigoureuse d'un agent IA : un système qui perçoit, décide et agit vers un objectif, en boucle, avec des outils et de la mémoire. Différence avec un simple modèle de langage. Un ou deux exemples concrets.",
        "links": [PILLAR, "agent-ia-vs-chatbot-rpa"],
        "pub_date": "2026-08-21", "words": "600 à 800",
    },
    {
        "ref": "agent-ia-vs-chatbot-rpa", "kind": "cluster",
        "title": "Agent IA, chatbot, RPA : quelles différences ?",
        "query": "agent ia vs chatbot",
        "angle": "Comparatif net entre agent IA, chatbot classique et RPA : autonomie, capacité de décision, adaptation, gestion des cas non prévus. Tableau ou liste comparative claire.",
        "links": [PILLAR, "quest-ce-quun-agent-ia"],
        "pub_date": "2026-08-25", "words": "600 à 800",
    },
    {
        "ref": "deployer-agent-ia-entreprise", "kind": "cluster",
        "title": "Déployer un agent IA en entreprise : la méthode étape par étape",
        "query": "déployer un agent IA",
        "angle": "How-to opérationnel : cadrer un cas d'usage, choisir le périmètre, brancher les données et outils, tester en bac à sable, mettre des garde-fous, passer en production, mesurer. Pour des ops et décideurs.",
        "links": [PILLAR, "cas-usage-agents-ia", "securite-agents-ia"],
        "pub_date": "2026-08-28", "words": "700 à 900",
    },
    {
        "ref": "cas-usage-agents-ia", "kind": "cluster",
        "title": "Cas d'usage des agents IA en entreprise (avec exemples concrets)",
        "query": "cas d'usage agents IA",
        "angle": "Liste inspirante et concrète de cas d'usage par fonction (support, ventes, finance, IT, RH, ops) avec un bénéfice mesurable pour chacun. Éviter le catalogue creux : un exemple parlant par cas.",
        "links": [PILLAR, "deployer-agent-ia-entreprise", "roi-automatisation-ia"],
        "pub_date": "2026-09-01", "words": "700 à 900",
    },
    {
        "ref": "frameworks-agents-ia", "kind": "cluster",
        "title": "Meilleurs frameworks pour agents IA : comparatif 2026",
        "query": "meilleur framework agent IA",
        "angle": "Comparatif des principaux frameworks/outils pour construire des agents (orchestration, outils, mémoire). Critères de choix selon le besoin. Rester factuel, pas de survente.",
        "links": [PILLAR, "orchestration-multi-agents", "mcp-model-context-protocol"],
        "pub_date": "2026-09-04", "words": "700 à 900",
    },
    {
        "ref": "mcp-model-context-protocol", "kind": "cluster",
        "title": "MCP (Model Context Protocol) : à quoi ça sert vraiment ?",
        "query": "qu'est-ce que le MCP",
        "angle": "Définition technique accessible du MCP : un standard pour connecter les modèles aux outils et données. Pourquoi ça compte pour les agents. Schéma mental clair, exemple d'usage.",
        "links": [PILLAR, "frameworks-agents-ia"],
        "pub_date": "2026-09-08", "words": "600 à 800",
    },
    {
        "ref": "orchestration-multi-agents", "kind": "cluster",
        "title": "Orchestration multi-agents : faire collaborer plusieurs agents IA",
        "query": "orchestration multi-agents",
        "angle": "Sujet avancé : patterns d'orchestration (superviseur, pipeline, débat, hiérarchie), quand plusieurs agents valent mieux qu'un, les pièges de coordination et de coût.",
        "links": [PILLAR, "frameworks-agents-ia"],
        "pub_date": "2026-09-11", "words": "700 à 900",
    },
    {
        "ref": "roi-automatisation-ia", "kind": "cluster",
        "title": "ROI de l'automatisation par agents IA : comment le calculer",
        "query": "ROI automatisation IA",
        "angle": "Décision et chiffres : comment estimer le ROI d'un agent (gains de temps, réduction d'erreurs, coûts d'API et de maintenance), une méthode de calcul simple, un exemple chiffré réaliste.",
        "links": [PILLAR, "cas-usage-agents-ia"],
        "pub_date": "2026-09-15", "words": "700 à 900",
    },
    {
        "ref": "securite-agents-ia", "kind": "cluster",
        "title": "Sécurité des agents IA : risques et garde-fous",
        "query": "sécurité des agents IA",
        "angle": "Risques spécifiques aux agents (actions non voulues, injection de prompt, fuite de données, accès excessifs) et les garde-fous concrets (permissions minimales, validation humaine, journalisation, bacs à sable).",
        "links": [PILLAR, "deployer-agent-ia-entreprise"],
        "pub_date": "2026-09-18", "words": "700 à 900",
    },
    {
        "ref": "erreurs-projet-agentique", "kind": "cluster",
        "title": "Projet d'IA agentique : les erreurs qui font tout capoter",
        "query": "erreurs projet IA agent",
        "angle": "Pièges fréquents : cas d'usage flou, périmètre trop large, pas de garde-fous, pas de mesure, sous-estimer la maintenance, confondre démo et production. Ton direct, retours de terrain.",
        "links": [PILLAR, "deployer-agent-ia-entreprise", "roi-automatisation-ia"],
        "pub_date": "2026-09-22", "words": "700 à 900",
    },
]

PROMPT = """Tu es un rédacteur expert pour Agentic Pods (agentic-pods.com), un média sur les agents IA et l'automatisation agentique. Public : décideurs, responsables ops et tech qui veulent comprendre et passer à l'action. Écris un article ORIGINAL en français.

RÔLE DE L'ARTICLE : {kind} du cocon. Sujet et angle : {angle}
REQUÊTE CIBLE (à couvrir naturellement, sans bourrage) : {query}
LONGUEUR : {words} mots.

STRUCTURE GEO (optimisée moteurs génératifs ET SEO) :
- Commence par une RÉPONSE DIRECTE de 2-3 phrases (un court paragraphe d'accroche qui répond tout de suite à l'intention), sans titre au-dessus.
- Ensuite des sections avec des <h2> (et <h3> si utile), des paragraphes courts, au moins une liste à puces « - » claire et extractible.
- Cite des entités nommées et, quand c'est pertinent, un ordre de grandeur chiffré crédible (sans inventer de fausses stats précises).
- Termine par une section <h2>FAQ</h2> avec 3 à 4 questions en <h3> et une réponse courte en <p> chacune (format question/réponse extractible par les IA).

STYLE HUMAIN (l'article doit passer le test d'écriture humaine, aucune trace d'IA) :
- BURSTINESS : varie fortement la longueur des phrases, alterne phrases très courtes et longues, rythme irrégulier.
- Voix affirmée : un avis, une nuance, parfois une petite pointe ; des exemples concrets plutôt que des généralités.
- Bannis les tics d'IA : pas de « plongez dans », « n'hésitez pas », « dans cet article », « il est important de noter », pas de conclusion en « En résumé / En conclusion / Pour finir », pas de transitions génériques répétées.
- N'utilise JAMAIS le tiret cadratin « — » ni « – ». Uniquement le trait d'union simple « - ».
- Aucun mot entièrement en MAJUSCULES (sigles courts comme IA, MCP, RPA, ROI, API tolérés).

MAILLAGE INTERNE OBLIGATOIRE : insère de façon naturelle, dans le corps, les liens internes suivants sous la forme exacte <a data-internal-ref="CLE">ancre descriptive</a> (l'ancre doit être variée et pertinente, jamais l'URL). Clés à placer (une occurrence chacune minimum) :
{links_desc}

Réponds UNIQUEMENT par un objet JSON valide, sans texte autour :
{{"title": "{title}", "body_html": "<article HTML complet avec les liens internes inline>", "meta": "<meta description ~150 caractères, accrocheuse>", "keywords": "<6 à 8 mots-clés minuscules séparés par des virgules>"}}"""


def _claude(prompt, timeout=300):
    try:
        proc = subprocess.run([CLAUDE, "-p", prompt, "--output-format", "json"],
                              capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    out = (proc.stdout or "").strip()
    if not out:
        return None
    try:
        env = json.loads(out)
        out = env.get("result", out) if isinstance(env, dict) else out
    except Exception:  # noqa: BLE001
        pass
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return None


class Command(BaseCommand):
    help = "Génère + pousse le cocon sémantique Agentic Pods (pilier + 10 clusters), humanisé + GEO."

    def add_arguments(self, parser):
        parser.add_argument("--only", default="", help="ne traiter qu'un ref")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--target", type=int, default=45, help="score détecteur max toléré")
        parser.add_argument("--passes", type=int, default=2, help="tentatives de rédaction par article")

    def handle(self, *args, **o):
        b = Blog.objects.get(id=BLOG_ID)
        # refs déjà en base (reprise)
        done = set()
        try:
            ld = mcp.rpc("tools/call", {"name": "list_drafts", "arguments": {}},
                         url=b.mcp_url, token=b.mcp_token, timeout=40, retries=2)
            for d in ((ld.get("result") or {}).get("structuredContent") or {}).get("drafts", []):
                if d.get("ref"):
                    done.add(d["ref"])
        except Exception:  # noqa: BLE001
            pass

        items = [c for c in COCON if not o["only"] or c["ref"] == o["only"]]
        ok = err = 0
        for c in items:
            if c["ref"] in done and not o["only"]:
                self.stdout.write(f"  = {c['ref']} déjà présent, saute"); continue
            links_desc = "\n".join(f'- {r}' for r in c["links"])
            prompt = PROMPT.format(kind=c["kind"], angle=c["angle"], query=c["query"],
                                   words=c["words"], title=c["title"], links_desc=links_desc)
            best, best_s = None, 999
            for _ in range(max(1, o["passes"])):
                data = _claude(prompt)
                body = (data or {}).get("body_html", "")
                if not body or len(body) < 400:
                    continue
                s = detector.score(body)["score"]
                if s < best_s:
                    best, best_s = data, s
                if s <= o["target"]:
                    break
            if not best:
                err += 1
                self.stdout.write(self.style.ERROR(f"  x {c['ref']} rédaction vide")); continue
            if best_s > o["target"]:
                self.stdout.write(self.style.WARNING(f"  ! {c['ref']} score {best_s} > {o['target']} (poussé quand même)"))
            args_ = {
                "title": (best.get("title") or c["title"])[:300],
                "ref": c["ref"],
                "body_html": best["body_html"],
                "meta_description": (best.get("meta") or "")[:300],
                "meta_keywords": (best.get("keywords") or "")[:300],
                "internal_links": [{"text": r.replace("-", " "), "ref": r} for r in c["links"]],
                "pub_date": c["pub_date"],
            }
            if o["dry_run"]:
                ok += 1
                self.stdout.write(f"  DRY {c['ref']} score={best_s} len={len(best['body_html'])}"); continue
            try:
                r = mcp.rpc("tools/call", {"name": "draft_article", "arguments": args_},
                            url=b.mcp_url, token=b.mcp_token, timeout=120, retries=3)
                res = r.get("result") or {}
                if res.get("isError"):
                    err += 1
                    self.stdout.write(self.style.ERROR(f"  x {c['ref']} MCP isError")); continue
                sc = res.get("structuredContent") or {}
                art = sc.get("article_id") or res.get("article_id")
                ok += 1
                self.stdout.write(self.style.SUCCESS(f"  OK {c['ref']} -> #{art} (score {best_s})"))
            except Exception as e:  # noqa: BLE001
                err += 1
                self.stdout.write(self.style.ERROR(f"  x {c['ref']} {type(e).__name__}: {e}"))
        self.stdout.write(self.style.SUCCESS(
            f"FIN cocon Agentic Pods : {ok} ok / {err} err" + (" (DRY-RUN)" if o["dry_run"] else "")))
