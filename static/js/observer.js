/* Vue télé — EventSource + xterm read-only. Reconnexion : native SSE
   (retry serveur) ; à chaque (re)connexion le serveur rejoue les buffers
   publics expurgés. Zéro interaction : pas de stdin, pas de contrôle. */
(function () {
  "use strict";

  const b64decode = function (data) {
    const raw = atob(data);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
    return bytes;
  };

  const terms = new Map(); // pane_id -> term
  const gridUrl = document.body.getAttribute("data-grid-url");
  const streamUrl = document.body.getAttribute("data-stream-url");
  const grid = document.getElementById("observer-grid");
  const liveBadge = document.getElementById("live-badge");

  // Compteur d'agents — l'info la plus lue de la vue télé (design system
  // .observer-count). Recalculé à chaque rafraîchissement de grille.
  function updateCount() {
    const el = document.querySelector("[data-observer-count]");
    if (!el) return;
    const n = grid.querySelectorAll(".observer-pane").length;
    const strong = el.querySelector("b");
    if (strong) strong.textContent = String(n);
    el.hidden = n === 0;
  }

  function setLiveBadge(on) {
    liveBadge.setAttribute("data-live", on ? "on" : "off");
    liveBadge.querySelector("[data-live-label]").textContent = on ? "en direct" : "hors direct";
  }

  function mountTerms() {
    terms.forEach(function (term) { term.dispose(); });
    terms.clear();
    grid.querySelectorAll("[data-observer-host]").forEach(function (host) {
      const term = new window.Terminal({
        fontFamily: '"JetBrains Mono", monospace',
        fontSize: 17,                     // lisible à 3 m
        cursorBlink: false,
        disableStdin: true,
        scrollback: 1500,
        theme: {
          background: "#100f0d",
          foreground: "#ece7da",
          cursor: "#100f0d",
          selectionBackground: "rgba(255, 210, 30, 0.35)",
        },
      });
      const fit = new window.FitAddon.FitAddon();
      term.loadAddon(fit);
      term.open(host);
      fit.fit();
      terms.set(host.getAttribute("data-pane-id"), term);
    });
    setLiveBadge(Boolean(grid.querySelector(".observer-panes")));
    updateCount();
  }

  function refreshGrid() {
    fetch(gridUrl)
      .then(function (r) { return r.text(); })
      .then(function (html) {
        grid.innerHTML = html;
        mountTerms();
      });
  }

  function setStatus(paneId, status) {
    const pane = grid.querySelector('.observer-pane[data-pane-id="' + paneId + '"]');
    if (!pane) return;
    pane.setAttribute("data-status", status);
    const dot = pane.querySelector(".ds-status-dot");
    if (dot) dot.setAttribute("data-status", status);
  }

  const source = new EventSource(streamUrl);
  source.addEventListener("stdout", function (event) {
    const msg = JSON.parse(event.data);
    const term = terms.get(String(msg.pane_id));
    if (term) term.write(b64decode(msg.data));
  });
  function chatEl(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function renderChat(paneId, ev) {
    const host = grid.querySelector('[data-observer-chat][data-pane-id="' + paneId + '"]');
    if (!host) return;
    if (ev.kind === "user") {
      const b = chatEl("div", "chat-msg chat-msg--user");
      b.appendChild(chatEl("div", "chat-msg-body", ev.text));
      host.appendChild(b);
    } else if (ev.kind === "assistant") {
      (ev.blocks || []).forEach(function (block) {
        if (block.type === "text") {
          const b = chatEl("div", "chat-msg chat-msg--assistant");
          b.appendChild(chatEl("div", "chat-msg-body", block.text));
          host.appendChild(b);
        } else if (block.type === "tool_use") {
          host.appendChild(chatEl("div", "chat-system", "⚙ " + (block.name || "outil")));
        }
      });
    } else if (ev.kind === "tool_result") {
      host.appendChild(chatEl("div", "chat-system", "✓ résultat"));
    } else if (ev.kind === "result") {
      const secs = ev.duration_ms ? (ev.duration_ms / 1000).toFixed(1) + " s" : "";
      host.appendChild(chatEl("div", "chat-result", "Terminé · " + secs));
    }
    host.scrollTop = host.scrollHeight;
  }
  source.addEventListener("chat", function (event) {
    const msg = JSON.parse(event.data);
    renderChat(String(msg.pane_id), msg.data);
  });
  source.addEventListener("status", function (event) {
    const msg = JSON.parse(event.data);
    setStatus(String(msg.pane_id), msg.status);
  });
  source.addEventListener("panes_changed", refreshGrid);
  source.addEventListener("live", refreshGrid);
  source.addEventListener("standby", refreshGrid);
  source.onopen = refreshGrid; // (re)connexion ⇒ layout frais + replay serveur

  window.addEventListener("resize", function () {
    // refit simple : re-render de la grille suffit pour la vue télé
    terms.forEach(function (_t, id) { void id; });
  });

  refreshGrid();
})();
