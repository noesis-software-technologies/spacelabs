/* Surface « chat » (headless) — pendant de panes.js pour les panes de type
   chat. Monte sur [data-chat-host], parle au singleton CockpitSocket par
   pane_id, rend les événements normalisés en bulles. Attach ⇒ replay
   EventLog (F5/reconnexion durable). Actions par délégation. */
(function () {
  "use strict";

  const mounted = new Map(); // host -> { paneId, log, input, handler, tools }

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  function scrollLog(log) {
    log.scrollTop = log.scrollHeight;
  }

  function renderText(log, role, text) {
    const bubble = el("div", "chat-msg chat-msg--" + role);
    bubble.appendChild(el("div", "chat-msg-body", text));
    log.appendChild(bubble);
  }

  function renderToolUse(entry, block) {
    // Bloc repliable : nom + input JSON. Mémorisé par id pour y accrocher le résultat.
    const details = document.createElement("details");
    details.className = "chat-tool";
    details.open = false;
    const summary = el("summary", "chat-tool-summary");
    summary.appendChild(el("span", "chat-tool-name", block.name || "outil"));
    summary.appendChild(el("span", "chat-tool-hint", "outil"));
    details.appendChild(summary);
    const pre = el("pre", "chat-tool-input", JSON.stringify(block.input || {}, null, 2));
    details.appendChild(pre);
    const result = el("pre", "chat-tool-result");
    result.hidden = true;
    details.appendChild(result);
    entry.log.appendChild(details);
    if (block.id) entry.tools.set(block.id, result);
  }

  function renderResult(log, event) {
    const foot = el("div", "chat-result");
    const cost = typeof event.cost_usd === "number" ? "$" + event.cost_usd.toFixed(4) : "—";
    const secs = event.duration_ms ? (event.duration_ms / 1000).toFixed(1) + " s" : "—";
    foot.textContent = "Terminé · " + secs + " · " + cost + " · " + (event.num_turns || 0) + " tours";
    if (event.is_error) foot.classList.add("chat-result--error");
    log.appendChild(foot);
  }

  function renderEvent(entry, event) {
    const log = entry.log;
    if (event.kind === "user") {
      renderText(log, "user", event.text);
    } else if (event.kind === "assistant") {
      (event.blocks || []).forEach(function (block) {
        if (block.type === "text") renderText(log, "assistant", block.text);
        else if (block.type === "tool_use") renderToolUse(entry, block);
      });
    } else if (event.kind === "tool_result") {
      const target = entry.tools.get(event.tool_use_id);
      if (target) {
        target.hidden = false;
        target.textContent = event.content;
      } else {
        renderText(log, "assistant", event.content);
      }
    } else if (event.kind === "system") {
      log.appendChild(el("div", "chat-system", "session démarrée · " + (event.model || "claude")));
    } else if (event.kind === "result") {
      renderResult(log, event);
    }
    scrollLog(log);
  }

  function setStatus(host, status) {
    const pane = host.closest(".pane");
    if (!pane) return;
    pane.setAttribute("data-status", status);
    const dot = pane.querySelector(".ds-status-dot");
    if (dot) dot.setAttribute("data-status", status);
    const label = pane.querySelector("[data-pane-status-label]");
    if (label) label.textContent = status === "dead" ? "terminé" : status === "running" ? "en cours" : "prêt";
  }

  function mount(host) {
    if (mounted.has(host) || !host.getAttribute("data-pane-id")) return;
    const paneId = host.getAttribute("data-pane-id");
    const entry = {
      paneId: paneId,
      log: host.querySelector("[data-chat-log]"),
      input: host.querySelector("[data-chat-input]"),
      tools: new Map(),
    };
    mounted.set(host, entry);

    entry.handler = function (msg) {
      if (msg.op === "chat_replay") {
        entry.log.replaceChildren();
        entry.tools.clear();
        (msg.events || []).forEach(function (item) { renderEvent(entry, item.event); });
      } else if (msg.op === "chat_event") {
        renderEvent(entry, msg.event);
      } else if (msg.op === "chat_status") {
        setStatus(host, msg.status);
      } else if (msg.op === "chat_reset") {
        entry.log.replaceChildren();
        entry.tools.clear();
        setStatus(host, "dead");
      } else if (msg.op === "error") {
        document.body.dispatchEvent(new CustomEvent("cockpit:toast", {
          detail: { message: msg.message, variant: "danger" },
        }));
      }
    };
    window.CockpitSocket.register(paneId, entry.handler);
    window.CockpitSocket.send({ op: "chat_attach", pane_id: paneId });
  }

  function unmount(host) {
    const entry = mounted.get(host);
    if (!entry) return;
    window.CockpitSocket.unregister(entry.paneId);
    mounted.delete(host);
  }

  function sendFrom(host) {
    const entry = mounted.get(host);
    if (!entry) return;
    const text = entry.input.value.trim();
    if (!text) return;
    window.CockpitSocket.send({ op: "chat_send", pane_id: entry.paneId, text: text });
    entry.input.value = "";
    entry.input.focus();
  }

  const observer = new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
      mutation.addedNodes.forEach(function (node) {
        if (!(node instanceof Element)) return;
        if (node.matches("[data-chat-host]")) mount(node);
        node.querySelectorAll("[data-chat-host]").forEach(mount);
      });
      mutation.removedNodes.forEach(function (node) {
        if (!(node instanceof Element)) return;
        if (node.matches("[data-chat-host]")) unmount(node);
        node.querySelectorAll("[data-chat-host]").forEach(unmount);
      });
    });
  });
  observer.observe(document.getElementById("content") || document.body, {
    childList: true, subtree: true,
  });
  document.querySelectorAll("[data-chat-host]").forEach(mount);

  /* Actions — délégation. */
  document.addEventListener("click", function (event) {
    const send = event.target.closest("[data-chat-send]");
    if (send) {
      sendFrom(send.closest("[data-chat-host]"));
      return;
    }
    const primer = event.target.closest("[data-primer]");
    if (primer) {
      const host = primer.closest("[data-chat-host]");
      const entry = host && mounted.get(host);
      if (entry) {
        entry.input.value = primer.getAttribute("data-primer");
        entry.input.focus();
      }
      return;
    }
    const kill = event.target.closest("[data-chat-kill]");
    if (kill) {
      const host = kill.closest(".pane") && kill.closest(".pane").querySelector("[data-chat-host]");
      if (host) window.CockpitSocket.send({ op: "chat_kill", pane_id: host.getAttribute("data-pane-id") });
      return;
    }
    const reset = event.target.closest("[data-chat-reset]");
    if (reset) {
      const host = reset.closest(".pane") && reset.closest(".pane").querySelector("[data-chat-host]");
      if (host && window.confirm("Nouvelle conversation ? L'historique Claude de ce pane sera oublié.")) {
        window.CockpitSocket.send({ op: "chat_reset", pane_id: host.getAttribute("data-pane-id") });
      }
      return;
    }
    const mcp = event.target.closest("[data-chat-mcp]");
    if (mcp) {
      const host = mcp.closest(".pane") && mcp.closest(".pane").querySelector("[data-chat-host]");
      if (host) window.CockpitSocket.send({ op: "chat_send", pane_id: host.getAttribute("data-pane-id"), text: "/mcp" });
      // Marquer l'alerte résolue côté serveur, puis retirer le bouton.
      fetch(mcp.getAttribute("data-alert-url"), {
        method: "POST",
        headers: { "X-CSRFToken": window.CockpitSocket.csrfToken() },
      }).then(function () { mcp.remove(); });
    }
  });

  // Entrée = envoyer, Maj+Entrée = nouvelle ligne.
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Enter" || event.shiftKey) return;
    const input = event.target.closest("[data-chat-input]");
    if (!input) return;
    event.preventDefault();
    sendFrom(input.closest("[data-chat-host]"));
  });
})();
