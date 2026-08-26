/* Dock — bascule d'onglets et glisser-déposer d'une skill sur un agent.
   Vanilla, délégation sur document : survit aux swaps htmx. */
(function () {
  "use strict";

  const TITLES = { bridge: "Bridge", skills: "Skills", editor: "Éditeur" };

  function showTab(name) {
    document.querySelectorAll("[data-dock-slot]").forEach(function (panel) {
      panel.hidden = panel.getAttribute("data-dock-slot") !== name;
    });
    document.querySelectorAll("[data-tab]").forEach(function (tab) {
      tab.setAttribute("aria-selected", tab.getAttribute("data-tab") === name ? "true" : "false");
    });
    const title = document.querySelector("[data-dock-title]");
    if (title) title.textContent = TITLES[name] || name;
  }

  document.addEventListener("click", function (event) {
    const tab = event.target.closest("[data-tab]");
    if (tab) showTab(tab.getAttribute("data-tab"));
  });

  /* ── Glisser une skill sur un agent ── */
  let dragged = null;

  document.addEventListener("dragstart", function (event) {
    const skill = event.target.closest("[data-skill]");
    if (!skill) return;
    dragged = skill;
    if (event.dataTransfer) event.dataTransfer.effectAllowed = "copy";
  });

  document.addEventListener("dragend", function () {
    dragged = null;
    document.querySelectorAll(".pane[data-skill-target]").forEach(function (p) {
      p.removeAttribute("data-skill-target");
    });
  });

  document.addEventListener("dragover", function (event) {
    if (!dragged) return;
    const pane = event.target.closest(".pane");
    if (!pane) return;
    event.preventDefault();
    pane.setAttribute("data-skill-target", "true");
  });

  document.addEventListener("dragleave", function (event) {
    const pane = event.target.closest(".pane");
    if (pane) pane.removeAttribute("data-skill-target");
  });

  document.addEventListener("drop", function (event) {
    if (!dragged) return;
    const pane = event.target.closest(".pane");
    if (!pane) return;
    event.preventDefault();
    pane.removeAttribute("data-skill-target");
    const url = dragged.getAttribute("data-apply-url");
    const host = pane.querySelector("[data-pane-id]");
    const paneId = (host && host.getAttribute("data-pane-id")) || pane.id.replace(/^pane-/, "");
    dragged = null;
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    fetch(url, {
      method: "POST",
      headers: { "X-CSRFToken": m ? m[1] : "", "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ pane: paneId }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        document.body.dispatchEvent(new CustomEvent("cockpit:toast", {
          detail: { message: data.reply, variant: data.ok ? "accent" : "danger" },
        }));
      })
      .catch(function () {
        document.body.dispatchEvent(new CustomEvent("cockpit:toast", {
          detail: { message: "Envoi impossible.", variant: "danger" },
        }));
      });
  });
})();
