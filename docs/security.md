# Security

SpaceLabs is **local-first**: the server runs on your machine and drives your
local `claude`. It is not designed to be exposed naked on the Internet. The
canonical policy lives in [`SECURITY.md`](https://github.com/noesis/spacelabs/blob/main/SECURITY.md);
this is the short version.

## Privacy model

- **Private by default** — a pane is never visible in the observer view until you
  explicitly make it public *and* the live is on.
- **Server-side redaction** — `RedactionRule`s mask sensitive content in the
  public stream, applied identically to terminals and chats. Public buffers are
  purged the moment the live is cut or the pane goes private again — going public
  never reveals the past.
- **Panic button** — cuts the live and flips every pane back to private instantly.

!!! warning
    Redaction is per event/chunk: a secret split across two events could slip
    through. Rule of thumb: **if it's confidential, keep the pane private.**

## Autonomous headless mode

Headless chat runs `claude -p`. For the agent to run tools without an interactive
prompt, Claude Code requires `--dangerously-skip-permissions`. It is **not** on by
default — adding it to `COCKPIT_CLAUDE_HEADLESS_ARGS` is an explicit choice, for
directories you control.

## LAN exposure

For the "TV" view or access from another device, set `COCKPIT_LAN_TOKEN`: the
whole server then requires that shared secret (passed once via `?token=…`, then a
cookie). Add your LAN IP to `ALLOWED_HOSTS`. Per-user auth still applies.

## Reporting a vulnerability

Open a private security advisory on GitHub (see `SECURITY.md`). Please don't
disclose publicly before a fix.
