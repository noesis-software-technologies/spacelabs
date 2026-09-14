"""
Données publiques des compétences SpaceLabs / Noesis.
Ce fichier est committé sur git — aucune information confidentielle ici.
Les détails sensibles (clients, tarifs, KPIs internes) vont dans
SAVOIR_FAIRE_PRIVATE.json à la racine du repo (gitignored).
"""

STACK = [
    # Backend
    {"nom": "Python 3.14",       "cat": "Backend",    "niveau": 5, "couleur": "#4d8dff"},
    {"nom": "Django 5.2 / ASGI", "cat": "Backend",    "niveau": 5, "couleur": "#4d8dff"},
    {"nom": "Daphne / Channels", "cat": "Backend",    "niveau": 4, "couleur": "#4d8dff"},
    {"nom": "PostgreSQL",        "cat": "Backend",    "niveau": 4, "couleur": "#4d8dff"},
    {"nom": "Redis",             "cat": "Backend",    "niveau": 3, "couleur": "#4d8dff"},
    # IA & Agents
    {"nom": "Claude API (Opus/Sonnet/Haiku)", "cat": "IA & Agents", "niveau": 5, "couleur": "#a78bfa"},
    {"nom": "Claude Code",       "cat": "IA & Agents","niveau": 5, "couleur": "#a78bfa"},
    {"nom": "Multi-agent orchestration", "cat": "IA & Agents","niveau": 5, "couleur": "#a78bfa"},
    {"nom": "Whisper / ASR",     "cat": "IA & Agents","niveau": 4, "couleur": "#a78bfa"},
    {"nom": "RAG / Embeddings",  "cat": "IA & Agents","niveau": 4, "couleur": "#a78bfa"},
    # Frontend & 3D
    {"nom": "Three.js / WebGL",  "cat": "Frontend",   "niveau": 4, "couleur": "#7ece4e"},
    {"nom": "Canvas API",        "cat": "Frontend",   "niveau": 5, "couleur": "#7ece4e"},
    {"nom": "JavaScript (ES2024)","cat": "Frontend",  "niveau": 5, "couleur": "#7ece4e"},
    {"nom": "CSS3 / Glassmorphism","cat": "Frontend", "niveau": 5, "couleur": "#7ece4e"},
    {"nom": "HTMX / Alpine.js",  "cat": "Frontend",   "niveau": 4, "couleur": "#7ece4e"},
    # Infra & DevOps
    {"nom": "Docker / Compose",  "cat": "DevOps",     "niveau": 4, "couleur": "#f77615"},
    {"nom": "GitHub Actions CI", "cat": "DevOps",     "niveau": 4, "couleur": "#f77615"},
    {"nom": "SSE / WebSockets",  "cat": "DevOps",     "niveau": 5, "couleur": "#f77615"},
    {"nom": "pytest (597 tests)","cat": "DevOps",     "niveau": 5, "couleur": "#f77615"},
    # Mobile & Data
    {"nom": "PWA / mobile-first","cat": "Mobile",     "niveau": 4, "couleur": "#e07dbd"},
    {"nom": "REST API / JSON",   "cat": "Data",       "niveau": 5, "couleur": "#e0c34a"},
    {"nom": "SQLite / migrations","cat": "Data",      "niveau": 5, "couleur": "#e0c34a"},
]

DOMAINES = [
    {
        "titre": "Orchestration IA multi-agents",
        "desc": "Architecture DAG avec dispatch, retry, budget tokens. Jusqu'à 16 agents Claude Code en parallèle par workspace.",
        "icone": "⬡",
        "couleur": "#a78bfa",
    },
    {
        "titre": "Voice & Streaming live",
        "desc": "Push-to-talk natif, transcription Whisper, diffusion SSE lecture seule zéro-install. Latence < 50 ms.",
        "icone": "◉",
        "couleur": "#7ece4e",
    },
    {
        "titre": "SaaS multi-tenant Django",
        "desc": "Workspaces isolés, RBAC, observateur en lecture, cockpit dense — architecture production-ready.",
        "icone": "▣",
        "couleur": "#4d8dff",
    },
    {
        "titre": "Vitrines & landing 3D",
        "desc": "Constellation canvas, Three.js WebGL, glassmorphism — du design cinématique livré dans Django.",
        "icone": "✦",
        "couleur": "#f77615",
    },
    {
        "titre": "MVP SaaS accéléré",
        "desc": "31 produits livrés dans 20+ verticaux. Stack éprouvée, sprint court, prêt à itérer.",
        "icone": "◈",
        "couleur": "#e07dbd",
    },
    {
        "titre": "Intégrations & API",
        "desc": "Stripe, Twilio, Telegram, S3, OAuth2, Webhooks. Chaque brique connectée proprement.",
        "icone": "⬢",
        "couleur": "#e0c34a",
    },
]

METRIQUES = [
    {"valeur": "31",    "unite": "+",  "label": "Produits lancés",       "couleur": "#a78bfa"},
    {"valeur": "20",    "unite": "+",  "label": "Verticals couverts",    "couleur": "#4d8dff"},
    {"valeur": "597",   "unite": "",   "label": "Tests automatisés",     "couleur": "#7ece4e"},
    {"valeur": "16",    "unite": "×",  "label": "Agents simultanés",     "couleur": "#f77615"},
    {"valeur": "< 50",  "unite": "ms", "label": "Latence stream",        "couleur": "#e07dbd"},
    {"valeur": "100",   "unite": "%",  "label": "Self-hosted / open",    "couleur": "#e0c34a"},
]
