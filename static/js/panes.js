/* Surface « panes » — remplace terminal.js (S1).
   Chaque hôte [data-pane-host] porte data-pane-id (pk DB) et data-status :
   la corrélation WS est structurelle (le pane existe avant le spawn), le
   slot onSpawned a disparu. Montage/démontage par MutationObserver,
   actions par délégation — zéro re-binding après swap htmx. */
(function () {
  "use strict";

  const b64encode = function (text) {
    return btoa(String.fromCharCode.apply(null, new TextEncoder().encode(text)));
  };
  const b64decode = function (data) {
    const raw = atob(data);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
    return bytes;
  };

  const mounted = new Map(); // host -> { term, fit, paneId, resizeObserver, handler }

  function termTheme() {
    // Les terminaux restent sombres dans les deux thèmes (fond --ds-bg-inset).
    return {
      background: "#100f0d",
      foreground: "#ece7da",
      cursor: "#ffd21e",
      selectionBackground: "rgba(255, 210, 30, 0.35)",
    };
  }

  function setStatus(host, status) {
    const pane = host.closest(".pane");
    if (!pane) return;
    pane.setAttribute("data-status", status);
    host.setAttribute("data-status", status);
    const dot = pane.querySelector(".ds-status-dot");
    if (dot) dot.setAttribute("data-status", status);
    const label = pane.querySelector("[data-pane-status-label]");
    if (label) {
      label.textContent = status === "dead" ? "terminé" : status === "running" ? "en cours" : "prêt";
    }
  }

  function mount(host) {
    if (mounted.has(host) || !host.getAttribute("data-pane-id")) return;
    const paneId = host.getAttribute("data-pane-id");
    const term = new window.Terminal({
      fontFamily: '"JetBrains Mono", monospace',
      fontSize: 13,
      cursorBlink: true,
      scrollback: 4000,
      theme: termTheme(),
    });
    const fit = new window.FitAddon.FitAddon();
    term.loadAddon(fit);
    term.open(host);
    fit.fit();

    const entry = { term: term, fit: fit, paneId: paneId };
    mounted.set(host, entry);

    term.onData(function (data) {
      window.CockpitSocket.send({ op: "stdin", pane_id: paneId, data: b64encode(data) });
    });

    const resizeObserver = new ResizeObserver(function () {
      setTermFontSize(term, paneFontSize(host));  // suit le palier de densité
      fit.fit();
      window.CockpitSocket.send({ op: "resize", pane_id: paneId, cols: term.cols, rows: term.rows });
    });
    resizeObserver.observe(host);
    entry.resizeObserver = resizeObserver;

    entry.handler = function (msg) {
      if (msg.op === "stdout") {
        term.write(b64decode(msg.data));
      } else if (msg.op === "status") {
        setStatus(host, msg.status);
        if (msg.status === "dead") {
          term.write("\r\n\u001b[33m[session terminée — bouton ↻ pour relancer]\u001b[0m\r\n");
        }
      } else if (msg.op === "visibility") {
        const badge = host.closest(".pane").querySelector("[data-pane-public-badge]");
        const eye = host.closest(".pane").querySelector("[data-pane-visibility]");
        if (badge) badge.hidden = !msg.public;
        if (eye) eye.setAttribute("data-public", msg.public ? "1" : "0");
      } else if (msg.op === "error") {
        document.body.dispatchEvent(
          new CustomEvent("cockpit:toast", { detail: { message: msg.message, variant: "danger" } })
        );
      }
    };
    window.CockpitSocket.register(paneId, entry.handler);

    // idle → premier lancement ; running (DB) → attach (rejoue ou détecte le
    // périmé côté serveur) ; dead → on attend le clic ↻.
    const status = host.getAttribute("data-status") || "idle";
    if (status === "idle") {
      window.CockpitSocket.send({
        op: "spawn", pane_id: paneId, cols: term.cols, rows: term.rows,
      });
    } else if (status === "running") {
      window.CockpitSocket.send({ op: "attach", pane_id: paneId });
    } else {
      term.write("\u001b[2m[session interrompue — ↻ pour reprendre]\u001b[0m\r\n");
    }
  }

  function unmount(host) {
    const entry = mounted.get(host);
    if (!entry) return;
    window.CockpitSocket.unregister(entry.paneId);
    if (entry.resizeObserver) entry.resizeObserver.disconnect();
    entry.term.dispose();
    mounted.delete(host);
  }

  // Acks « live »/« panic » : sans pane_id — traités globalement.
  window.CockpitSocket.onGlobal = function (msg) {
    if (msg.op !== "live") return;
    const btn = document.querySelector("[data-live-toggle]");
    if (btn) {
      btn.setAttribute("data-live", msg.live ? "1" : "0");
      const label = btn.querySelector("[data-live-toggle-label]");
      if (label) label.textContent = msg.live ? "En direct" : "Hors direct";
      const dot = btn.querySelector(".ds-status-dot");
      if (dot) dot.setAttribute("data-status", msg.live ? "running" : "idle");
    }
    if (msg.panic) {
      document.querySelectorAll("[data-pane-public-badge]").forEach(function (b) { b.hidden = true; });
      document.querySelectorAll("[data-pane-visibility]").forEach(function (e) { e.setAttribute("data-public", "0"); });
      document.body.dispatchEvent(new CustomEvent("cockpit:toast", {
        detail: { message: "Panique : direct coupé, tous les panes sont privés.", variant: "danger" },
      }));
    }
  };

  const observer = new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
      mutation.addedNodes.forEach(function (node) {
        if (!(node instanceof Element)) return;
        if (node.matches("[data-pane-host]")) mount(node);
        node.querySelectorAll("[data-pane-host]").forEach(mount);
      });
      mutation.removedNodes.forEach(function (node) {
        if (!(node instanceof Element)) return;
        if (node.matches("[data-pane-host]")) unmount(node);
        node.querySelectorAll("[data-pane-host]").forEach(unmount);
      });
    });
  });
  observer.observe(document.getElementById("content") || document.body, {
    childList: true,
    subtree: true,
  });
  document.querySelectorAll("[data-pane-host]").forEach(mount);

  // Densité changée (grid.js) → police + dimensions de tous les terminaux.
  document.addEventListener("spacelabs:density", function () {
    mounted.forEach(function (entry, host) {
      setTermFontSize(entry.term, paneFontSize(host));
      entry.fit.fit();
      window.CockpitSocket.send({ op: "resize", pane_id: entry.paneId, cols: entry.term.cols, rows: entry.term.rows });
    });
  });

  /* Actions — délégation sur document. */
  document.addEventListener("click", function (event) {
    const killBtn = event.target.closest("[data-pane-kill]");
    if (killBtn) {
      const host = killBtn.closest(".pane") && killBtn.closest(".pane").querySelector("[data-pane-host]");
      if (host) {
        window.CockpitSocket.send({ op: "kill", pane_id: host.getAttribute("data-pane-id") });
      }
      return;
    }
    const respawnBtn = event.target.closest("[data-pane-respawn]");
    if (respawnBtn) {
      const host = respawnBtn.closest(".pane") && respawnBtn.closest(".pane").querySelector("[data-pane-host]");
      const entry = host && mounted.get(host);
      if (!host || !entry) return;
      const wasDead = host.getAttribute("data-status") === "dead";
      entry.term.reset();
      window.CockpitSocket.send({
        op: "spawn",
        pane_id: entry.paneId,
        cols: entry.term.cols,
        rows: entry.term.rows,
        continue: wasDead, // claude ⇒ reprise de conversation (--continue)
      });
      entry.term.focus();
      return;
    }
    const visBtn = event.target.closest("[data-pane-visibility]");
    if (visBtn) {
      const host = visBtn.closest(".pane") && visBtn.closest(".pane").querySelector("[data-pane-host]");
      if (host) {
        window.CockpitSocket.send({
          op: "set_visibility",
          pane_id: host.getAttribute("data-pane-id"),
          public: visBtn.getAttribute("data-public") !== "1",
        });
      }
      return;
    }
    const liveBtn = event.target.closest("[data-live-toggle]");
    if (liveBtn) {
      window.CockpitSocket.send({ op: "set_live", live: liveBtn.getAttribute("data-live") !== "1" });
      return;
    }
    const panicBtn = event.target.closest("[data-panic]");
    if (panicBtn) {
      window.CockpitSocket.send({ op: "panic" });
      return;
    }
    const spawnAll = event.target.closest("[data-spawn-all]");
    if (spawnAll) {
      mounted.forEach(function (entry, host) {
        if (host.getAttribute("data-status") !== "running") {
          entry.term.reset();
          window.CockpitSocket.send({
            op: "spawn",
            pane_id: entry.paneId,
            cols: entry.term.cols,
            rows: entry.term.rows,
            continue: host.getAttribute("data-status") === "dead",
          });
        }
      });
    }
  });
})();
