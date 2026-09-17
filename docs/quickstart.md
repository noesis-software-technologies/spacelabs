# Quickstart

SpaceLabs runs **on the machine where you're logged into Claude Code** — it spawns
the local `claude` binary (OAuth in `~/.claude`).

## Requirements

- Python 3.12+
- The `claude` CLI installed and authenticated (`claude` runs interactively)
- Redis is only needed for production (channel layer) and Celery

## Install

```bash
git clone https://github.com/noesis/spacelabs && cd spacelabs
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env                 # localhost works as-is
python manage.py migrate
python manage.py bootstrap_demo      # creates user "pilote" / "cockpit-local"
make run                             # daphne on http://127.0.0.1:8000
```

Open <http://127.0.0.1:8000/> and log in with **pilote / cockpit-local**.

## Web surfaces

| URL | Role |
|---|---|
| `/dashboard/` | Central dashboard — KPI tiles, light/dark theme |
| `/` | Public landing — neural constellation (Three.js) |
| `/vitrine/` | Product showcase — animated portfolio |
| `/observer/` | Live spectator view (anonymous, read-only) |
| `/cockpit/` | Multi-agent workspaces |
| `/django-admin/` | Admin |

## Production bits (optional)

```bash
make redis     # Redis via docker compose (channel layer + Celery broker)
make worker    # Celery ops tasks
make beat      # periodic scheduler
```

## Language

The UI ships in French by default (its primary audience). Set `LANGUAGE_CODE=en`
in `.env` for English; the gettext infrastructure lives in `locale/`.

## Tests

```bash
make test      # pytest
make check     # migrations up to date + Django check + pytest
ruff check .   # lint
```
