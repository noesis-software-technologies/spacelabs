/* cockpit-shell.js — chrome du cockpit recomposé (Sprint 0, Option A).

   Rôle : la COMPOSITION, pas le temps réel (ça reste dans shell.js / panes.js).
   - overlay modal : ouverture par htmx (#modal), fermeture sur succès/échap/clic
   - panneaux coulissants : sidebar (⌘B) et dock (⌘\)
   - miroir de densité dans la barre de statut
   Aucune création de WebSocket ici. Délégation d'événements → survit aux swaps. */
(function () {
  "use strict";

  const modal = () => document.getElementById("modal");

  function closeModal() {
    const m = modal();
    if (m) m.innerHTML = "";
  }

  // La création d'un pane rend le fragment dans #pane-grid ET émet paneCreated :
  // on referme la modale et on retire l'état vide au premier pane.
  document.body.addEventListener("paneCreated", function () {
    closeModal();
    const empty = document.getElementById("pane-grid-empty");
    if (empty) empty.remove();
  });

  // Clic : fermeture de modale (bouton ou fond), toggles de panneaux.
  document.addEventListener("click", function (event) {
    if (event.target.closest("[data-modal-close]")) { closeModal(); return; }
    const m = modal();
    if (m && event.target === m) { closeModal(); return; } // clic sur le fond

    const rail = event.target.closest("[data-rail-toggle]");
    if (rail) {
      const collapsed = document.body.classList.toggle("rail-collapsed");
      rail.setAttribute("aria-pressed", collapsed ? "false" : "true");
      return;
    }
    const dockBtn = event.target.closest("[data-dock-toggle]");
    if (dockBtn) {
      toggleDock(dockBtn);
      return;
    }
  });

  function toggleDock(btn) {
    const dock = document.getElementById("bridge-dock") || document.querySelector(".dock");
    if (!dock) return;
    const open = dock.getAttribute("data-open") !== "false";
    dock.setAttribute("data-open", open ? "false" : "true");
    const control = btn || document.querySelector("[data-dock-toggle]");
    if (control) control.setAttribute("aria-pressed", open ? "false" : "true");
  }

  // Raccourcis : ⌘/Ctrl+B (sidebar), ⌘/Ctrl+\ (dock), Échap (modale).
  // shortcuts.js ignore les combinaisons méta : aucun conflit.
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      const m = modal();
      if (m && m.innerHTML.trim()) { closeModal(); event.preventDefault(); }
      return;
    }
    if (!(event.metaKey || event.ctrlKey) || event.altKey) return;
    const k = event.key.toLowerCase();
    if (k === "b") {
      const rail = document.querySelector("[data-rail-toggle]");
      const collapsed = document.body.classList.toggle("rail-collapsed");
      if (rail) rail.setAttribute("aria-pressed", collapsed ? "false" : "true");
      event.preventDefault();
    } else if (k === "\\") {
      toggleDock(null);
      event.preventDefault();
    }
  });

  // Miroir de densité dans la barre de statut (grid.js émet spacelabs:density).
  document.addEventListener("spacelabs:density", function () {
    const view = document.querySelector(".workspace-view");
    const sb = document.querySelector("[data-sb-panes]");
    if (!view || !sb) return;
    const density = view.getAttribute("data-density") || "cozy";
    sb.textContent = sb.textContent.replace(/·\s*\S+\s*$/, "· " + density);
  });
})();
