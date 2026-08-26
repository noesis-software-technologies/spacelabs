/* Shell persistant SpaceLabs — singletons uniquement (Blueprint §2.5).
   - CockpitSocket : client WS unique, multiplexé par pane_id, reconnexion
     exponentielle, re-attach automatique des panes après reconnexion.
   - Toasts : délégation d'événements (htmx HX-Trigger + événement custom).
   - Thème : bascule clair/sombre persistée (localStorage, état UI pur).
   Aucun autre fichier ne crée de WebSocket ni ne re-bind après swap. */
(function () {
  "use strict";

  /* ── Thème ─────────────────────────────────────────────────────────── */
  const THEME_KEY = "spacelabs.theme";
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
  }
  applyTheme(localStorage.getItem(THEME_KEY) || "dark");
  document.addEventListener("click", function (event) {
    const toggle = event.target.closest("[data-theme-toggle]");
    if (!toggle) return;
    const next =
      document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    localStorage.setItem(THEME_KEY, next);
    applyTheme(next);
  });

  /* ── Toasts (hôte dans le shell, jamais swappé) ───────────────────── */
  function toast(message, variant) {
    const host = document.getElementById("toasts");
    if (!host) return;
    const el = document.createElement("div");
    el.className = "ds-toast" + (variant === "danger" ? " ds-toast--danger" : "");
    el.setAttribute("role", "status");
    el.textContent = message;
    host.appendChild(el);
    setTimeout(function () {
      el.remove();
    }, 5000);
  }
  document.body.addEventListener("cockpit:toast", function (event) {
    toast(event.detail.message, event.detail.variant);
  });

  /* ── CockpitSocket — singleton WS ─────────────────────────────────── */
  const CockpitSocket = {
    ws: null,
    state: "closed", // closed | connecting | open
    retry: 0,
    handlers: new Map(), // pane_id -> handler({op, ...})
    pending: [],

    url: function () {
      const proto = location.protocol === "https:" ? "wss://" : "ws://";
      return proto + location.host + "/ws/cockpit/";
    },

    connect: function () {
      if (this.ws && (this.state === "open" || this.state === "connecting")) return;
      this.state = "connecting";
      this._render();
      const ws = new WebSocket(this.url());
      this.ws = ws;
      const self = this;
      ws.onopen = function () {
        self.state = "open";
        self.retry = 0;
        self._render();
        // Re-attache tous les panes connus (replay serveur → état reconstruit)
        self.handlers.forEach(function (_handler, paneId) {
          self.send({ op: "attach", pane_id: paneId });
        });
        self.pending.splice(0).forEach(function (msg) {
          ws.send(JSON.stringify(msg));
        });
        document.body.dispatchEvent(new CustomEvent("cockpit:open"));
      };
      ws.onmessage = function (event) {
        let msg;
        try {
          msg = JSON.parse(event.data);
        } catch (_err) {
          return;
        }
        if (msg.op === "error" && !msg.pane_id) {
          toast(msg.message, "danger");
          return;
        }
        const handler = msg.pane_id ? self.handlers.get(msg.pane_id) : null;
        if (handler) {
          handler(msg);
        } else if (self.onGlobal && !msg.pane_id) {
          self.onGlobal(msg);
        } else if (msg.op === "error") {
          toast(msg.message, "danger");
        }
      };
      ws.onclose = function () {
        self.state = "closed";
        self._render();
        self.retry += 1;
        const delay = Math.min(8000, 400 * Math.pow(2, self.retry));
        setTimeout(function () {
          self.connect();
        }, delay);
      };
      ws.onerror = function () {
        ws.close();
      };
    },

    send: function (msg) {
      if (this.state === "open") {
        this.ws.send(JSON.stringify(msg));
      } else {
        this.pending.push(msg);
        this.connect();
      }
    },

    register: function (paneId, handler) {
      this.handlers.set(paneId, handler);
    },
    unregister: function (paneId) {
      this.handlers.delete(paneId);
    },

    onGlobal: null, // messages sans pane_id (live/panic) — posé par la surface

    _render: function () {
      const el = document.getElementById("ws-state");
      if (!el) return;
      el.setAttribute("data-state", this.state);
      const label = el.querySelector("[data-ws-label]");
      if (label) {
        label.textContent =
          this.state === "open" ? "connecté" : this.state === "connecting" ? "connexion…" : "hors ligne";
      }
    },
  };

  // Lecture du jeton CSRF (cookie Django) pour les fetch hors htmx.
  CockpitSocket.csrfToken = function () {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  };

  window.CockpitSocket = CockpitSocket;
  CockpitSocket.connect();

  /* ── Alpine × htmx (Blueprint §2.5) ───────────────────────────────────
     Alpine 3 initialise lui-même les sous-arbres insérés par htmx
     (MutationObserver du shell). Le garde-fou htmx.onLoad→initTree n'est
     requis QUE si un mode de swap contourne l'observer — l'appeler ici
     systématiquement provoquerait des doubles inits, que le blueprint
     interdit. Aucun mode de swap exotique en Sprint 1 : pas de garde-fou. */
})();
