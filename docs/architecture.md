# Architecture

SpaceLabs is a Django 5 + Channels (ASGI/Daphne) application. Clear boundaries:
**htmx** for CRUD/navigation, **WebSocket** for runtime streams, **Alpine** for
local UI state, **SSE** for the anonymous observer.

## Apps

| App | Responsibility |
|---|---|
| `apps/comptes` | User model, demo bootstrap |
| `apps/common` | htmx helpers, middleware (LAN token), context processors, brand tests |
| `apps/runtime` | Real-time core: `PaneManager` (PTY), `HeadlessManager` (`claude -p` stream-json), the single WebSocket consumer, lifespan & boot bring-up |
| `apps/workspaces` | Polymorphic `Pane` model (MTI) + type registry, CRUD |
| `apps/observer` | Anonymous SSE view + privacy pipeline (redaction) |
| `apps/chat` | `EventLog` (full persistence) + event parsing |
| `apps/ops` | Celery ops: usage gauges, zombie reaper, archival, MCP detection, reconciliation |
| `apps/tasker` | Missions / Master Tasker orchestration graph |
| `apps/vitrine` | Animated product showcase |
| `apps/veille` | Editorial monitoring — press releases → categorization → blog dispatch |
| `apps/comms` | Unified multi-channel inbox (email/telegram/…) + AI triage |
| `apps/vinted` | Vinted assist — photo→listing publishing (CDP) + order manager (buy/sell/profit + shipping dashboard). See [vinted.md](vinted.md) |

## Adding a pane type

`Pane` is polymorphic (multi-table inheritance) with a **registry**
(`apps/workspaces/registry`). A new type = a `Pane` subclass, a registry entry
(label, partial, form) and a runtime if needed. The public/private pipeline and
base UI are inherited — no core changes.

## Living documents

- `CLAUDE.md` — living architecture map.
- `AUDIT.md` — sprint journal, decisions and verification evidence.
- `BRAND.md` — brand charter, locked by tests in `apps/common/tests/test_brand.py`.
