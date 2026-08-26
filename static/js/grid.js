/* Grille de panes SpaceLabs — zoom, densité auto (data-count) et paliers de
   densité (cozy→compact→dense→micro), tout en vanilla par délégation sur
   `document` : fiable sur n'importe quel pane, y compris inséré par htmx.

   - Zoom : un pane en plein écran, les autres masqués.
   - data-count : nombre de panes vivants → colonnes par densité (CSS).
   - data-density : palier de taille (police/hauteur) piloté par CSS vars, pour
     garder 16 agents lisibles sur un seul écran. Persisté en localStorage. */
(function () {
  "use strict";

  /* ── Zoom ─────────────────────────────────────────────────────────── */
  document.addEventListener("click", function (event) {
    const btn = event.target.closest("[data-pane-zoom]");
    if (!btn) return;
    const pane = btn.closest(".pane");
    const grid = pane && pane.closest(".pane-grid");
    if (!pane || !grid) return;
    const wasZoomed = pane.classList.contains("pane--zoomed");
    grid.querySelectorAll(".pane").forEach(function (p) {
      p.classList.remove("pane--zoomed", "pane--hidden");
    });
    grid.classList.remove("pane-grid--zoomed");
    if (!wasZoomed) {
      pane.classList.add("pane--zoomed");
      grid.querySelectorAll(".pane").forEach(function (p) {
        if (p !== pane) p.classList.add("pane--hidden");
      });
      grid.classList.add("pane-grid--zoomed");
    }
  });

  /* ── Densité : cozy / compact / dense / micro ─────────────────────── */
  const DENSITIES = ["cozy", "compact", "dense", "micro"];
  const DENSITY_KEY = "spacelabs.density";
  const COLS_KEY = "spacelabs.cols";

  function savedDensity() {
    try {
      const d = localStorage.getItem(DENSITY_KEY);
      return DENSITIES.indexOf(d) !== -1 ? d : "cozy";
    } catch (_e) {
      return "cozy";
    }
  }
  function applyDensity(view, d) {
    view.setAttribute("data-density", d);
    const label = view.querySelector("[data-density-label]");
    if (label) label.textContent = d;
  }
  function savedCols() {
    try {
      return localStorage.getItem(COLS_KEY) || "auto";
    } catch (_e) {
      return "auto";
    }
  }
  function applySavedToViews() {
    const d = savedDensity();
    document.querySelectorAll(".workspace-view").forEach(function (v) {
      applyDensity(v, d);
    });
    syncSeg(document, "data-density-set", d);
    const cols = savedCols();
    document.querySelectorAll(".pane-grid").forEach(function (g) {
      g.setAttribute("data-cols", cols);
    });
    syncSeg(document, "data-cols-set", cols);
  }

  function syncSeg(root, attr, value) {
    root.querySelectorAll("[" + attr + "]").forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute(attr) === value ? "true" : "false");
    });
  }

  function setDensity(view, d) {
    applyDensity(view, d);
    syncSeg(document, "data-density-set", d);
    try {
      localStorage.setItem(DENSITY_KEY, d);
    } catch (_e) {
      /* localStorage indisponible : densité de session uniquement */
    }
    // panes.js écoute cet événement pour re-dimensionner xterm (contrat S9).
    document.dispatchEvent(new CustomEvent("spacelabs:density", { detail: { density: d } }));
  }

  document.addEventListener("click", function (event) {
    // Segmented control (design system .ds-seg)
    const seg = event.target.closest("[data-density-set]");
    if (seg) {
      const view = document.querySelector(".workspace-view");
      if (view) setDensity(view, seg.getAttribute("data-density-set"));
      return;
    }
    // Rétro-compat : ancien bouton de cycle, si un template le sert encore.
    const btn = event.target.closest("[data-density-cycle]");
    if (btn) {
      const view = document.querySelector(".workspace-view");
      if (!view) return;
      const cur = view.getAttribute("data-density") || "cozy";
      setDensity(view, DENSITIES[(DENSITIES.indexOf(cur) + 1) % DENSITIES.length]);
      return;
    }
    // Colonnes forcées — data-cols lu par le CSS (.pane-grid[data-cols="N"])
    const col = event.target.closest("[data-cols-set]");
    if (col) {
      const value = col.getAttribute("data-cols-set");
      const grid = document.querySelector(".pane-grid");
      if (grid) grid.setAttribute("data-cols", value);
      syncSeg(document, "data-cols-set", value);
      try {
        localStorage.setItem(COLS_KEY, value);
      } catch (_e) {
        /* idem */
      }
      // Le nombre de colonnes change la largeur des panes → xterm doit refit.
      document.dispatchEvent(new CustomEvent("spacelabs:density", { detail: { cols: value } }));
    }
  });

  /* ── Densité auto : data-count = nombre de panes vivants ──────────── */
  function reflow() {
    document.querySelectorAll(".pane-grid").forEach(function (grid) {
      grid.dataset.count = grid.querySelectorAll(".pane").length;
    });
  }

  const mo = new MutationObserver(function (mutations) {
    let changed = false;
    mutations.forEach(function (m) {
      m.addedNodes.forEach(function (n) {
        if (n instanceof Element && (n.classList.contains("pane") || n.classList.contains("workspace-view") || n.querySelector(".pane, .workspace-view"))) changed = true;
      });
      m.removedNodes.forEach(function (n) {
        if (n instanceof Element && (n.classList.contains("pane") || n.querySelector(".pane"))) changed = true;
      });
    });
    if (changed) { reflow(); applySavedToViews(); }
  });

  function start() {
    mo.observe(document.getElementById("content") || document.body, { childList: true, subtree: true });
    reflow();
    applySavedToViews();
  }
  if (document.readyState !== "loading") start();
  else document.addEventListener("DOMContentLoaded", start);
})();
