# SpaceLabs

**The local-first web cockpit to pilot a fleet of AI agents from your browser.**

Dozens of agents coding, testing and shipping in parallel on your machine.
You watch them out of the corner of your eye, step in when *you* decide, and
take back the wheel at any moment.

![SpaceLabs cockpit — 6 agents in parallel](screenshots/braingod_running.png)

---

## Why

AI dev agents are autonomous now. The problem is no longer *launching* one — it's
**piloting a fleet**: where is each agent, in which repo, on which task? Which one
finished, which one is stuck, which one is drifting? How do you take back control
without losing context?

SpaceLabs answers with one principle: **one pane per agent, a wall of agents per
screen**. The agents' output is the content; the UI is a frame that gets out of
the way.

## What it does

| Capability | Detail |
|---|---|
| **Real-time terminal panes** | True PTY in the browser (WebSocket + Channels), buffer replayed on reconnect |
| **Session resume** | Refresh, crash, server restart: the grid restores, history returns, `--continue` picks up exactly where it left off |
| **Multi-workspace** | Several projects side by side, per-workspace and per-account caps |
| **Headless chat** | `stream-json` conversational mode: bubbles, collapsible tools, cost/duration, full persistence |
| **Spectator view** | `/observer/` — anonymous read-only SSE, server-side redaction of private panes, built for live streaming |
| **Voice command** | Push-to-talk per pane; optional 100% offline via CrisperWhisper |
| **Missions & Tasker** | Declarative orchestration: a Master Tasker distributes work to agents |
| **Ops** | Celery + beat: zombie reaper, usage snapshots, archival, boot reconciliation |

## No API key

SpaceLabs drives your **local `claude` binary** through your existing Claude Code
subscription (OAuth in `~/.claude`). No API key, no per-token billing — the
cockpit is a frame around the CLI you already run.

## Next steps

- [Quickstart](quickstart.md) — running in a couple of minutes.
- [Architecture](architecture.md) — how the pieces fit.
- [Security](security.md) — the privacy model and safe exposure.
