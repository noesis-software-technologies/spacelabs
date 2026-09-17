# SpaceLabs

🌍 **English** · [Français](README.md)

[![CI](https://github.com/noesis/spacelabs/actions/workflows/ci.yml/badge.svg)](https://github.com/noesis/spacelabs/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-informational.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Django 5.2](https://img.shields.io/badge/django-5.2-092E20.svg)](https://www.djangoproject.com/)
[![Ruff](https://img.shields.io/badge/lint-ruff-orange.svg)](https://github.com/astral-sh/ruff)

**The local-first web cockpit to pilot a fleet of AI agents from your browser.**

Dozens of agents coding, testing and shipping in parallel on your machine. You
watch them out of the corner of your eye, step in when *you* decide, and take
back the wheel at any moment.

![SpaceLabs cockpit — 6 agents in parallel](docs/screenshots/braingod_running.png)

---

## The goal

AI dev agents are autonomous now. The problem is no longer *launching* one — it's
**piloting a fleet**:

- where is each agent? in which repo? on which task?
- which one finished, which one is stuck, which one is drifting?
- how do you take back control without losing context?

SpaceLabs answers these three questions with one principle: **one pane per agent,
a wall of agents per screen**. The agents' output is the content; the UI is a
frame and gets out of the way.

## What it does

| Capability | Detail |
|---|---|
| **Real-time terminal panes** | True PTY in the browser (WebSocket + Channels), buffer replayed on reconnect |
| **Session resume** | Refresh, browser crash, server restart: the grid restores, history returns, `--continue` picks up exactly where it left off |
| **Multi-workspace** | Several projects side by side, per-workspace and per-account caps |
| **Headless chat** | `stream-json` conversational mode: bubbles, collapsible tools, cost/duration, full persistence |
| **Spectator view** | `/observer/` — anonymous read-only SSE, server-side redaction of private panes, built for live streaming |
| **Voice command** | Push-to-talk (fr-FR) per pane; optional 100% offline via CrisperWhisper |
| **Missions & Tasker** | Declarative orchestration: a Master Tasker distributes work to agents |
| **Ops** | Celery + beat: zombie reaper, usage snapshots, archival, boot reconciliation |

![Guillaume Studio — second workspace, independent sessions](docs/screenshots/guillaume_studio.png)

## Web surfaces

| URL | Role |
|---|---|
| `/dashboard/` | **Central dashboard** — sidebar + live KPI tiles, light/dark theme |
| `/` | Public landing — neural constellation (Three.js) |
| `/vitrine/` | Product showcase — animated portfolio, desktop focus |
| `/veille/` | **Editorial monitoring** — press releases → blog constellation *13 Atmosphère* |
| `/comms/` | **Unified inbox** — Email + Telegram, AI triage (priority / needs-reply) |
| `/observer/` | Live spectator view |
| `/cockpit/` | Multi-agent workspaces |
| `/django-admin/` | Admin |

## No API key

SpaceLabs spawns the CLI binaries already authenticated on **your** machine
(`claude`, or any CLI in your allowlist — e.g. `openclaw`). No middleman, no token
in transit: your subscriptions, your credits, your credentials stay with you
(`~/.claude`, etc.). The `COCKPIT_ALLOWED_CMDS` allowlist alone decides what can
be spawned.

## Get started

```bash
make setup    # deps + migrations + local user "pilote"
make redis    # (optional in dev) Redis via docker compose
make run      # daphne on http://127.0.0.1:8000
```

Simplified install (no `make`):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py bootstrap_demo        # creates user "pilote"
python manage.py runserver 0.0.0.0:8000 --settings=config.settings.dev
```

Then open **http://localhost:8000/dashboard/**. Log in with `pilote` /
`cockpit-local` (change it). The cockpit page opens a terminal pane running
`COCKPIT_DEFAULT_CMD` in a real PTY — close the tab, come back: the session
continues and history is replayed.

Config: copy `.env.example` → `.env`. Key vars: `COCKPIT_DEFAULT_CMD`,
`COCKPIT_ALLOWED_CMDS`, `COCKPIT_MAX_PANES`, `COCKPIT_OWNER_MAX_PANES`,
`REDIS_URL`, `ALLOWED_HOSTS`, `LANGUAGE_CODE` (`fr` default / `en`).

### "Full matrix" mode (streaming)

To follow 13+ agents at once and broadcast the screen live:

```bash
# .env
COCKPIT_OWNER_MAX_PANES=16
COCKPIT_OBSERVER_MAX_TILES=16
```

Then enable live mode and share `/observer/` — public tiles redacted,
placeholders for private ones, panic button.

![Observer — real-time spectator view](docs/screenshots/observer_matrix.png)

## Architecture in brief

- **Django 5.2 + Channels/Daphne** — ASGI, WebSockets, SSE
- **In-house PTY core** — spawn, replay, resume, clean kill, per-user isolation
- **MTI + polymorphic registry** — `PtyPane` / `HeadlessPane`, dispatch without `isinstance`
- **Celery** — ops from the database, single source of truth
- **Two-theme design system** — deliberate density, peripheral-readable state (see `BRAND.md`)

![Light theme](docs/screenshots/light_theme.png)

## Security — read before exposing anything

This cockpit **runs processes with your user rights**:

- **never** expose it on the Internet — trusted LAN only;
- `COCKPIT_ALLOWED_CMDS` is the allowlist: only put binaries you own;
- `--dangerously-skip-permissions` removes the agent's guardrails: an explicit
  choice, for directories you control (see `SECURITY.md`);
- the spectator view is **private by default**: nothing leaves without enabling
  live mode.

## Docs

Full docs (MkDocs Material): `pip install mkdocs-material && mkdocs serve`, or see
[`docs/`](docs/). Changelog in [`CHANGELOG.md`](CHANGELOG.md), roadmap in
[`ROADMAP.md`](ROADMAP.md).

## Contributing

Contributions welcome — read [`CONTRIBUTING.md`](CONTRIBUTING.md) and
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md), then open an issue.

## License

MIT — see [LICENSE](LICENSE).
