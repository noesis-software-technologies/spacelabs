/* Raccourcis clavier globaux (Sprint 5). N'agit jamais pendant une saisie
   (input/textarea/contenteditable). Déclenche les mêmes actions que les
   boutons — en simulant leur clic — pour rester une seule source de vérité. */
(function () {
  "use strict";

  function typing(target) {
    if (!target) return false;
    const tag = target.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || target.isContentEditable;
  }

  function click(selector) {
    const el = document.querySelector(selector);
    if (el) { el.click(); return true; }
    return false;
  }

  function focusPane(n) {
    const panes = document.querySelectorAll(".pane");
    const pane = panes[n - 1];
    if (!pane) return;
    pane.scrollIntoView({ behavior: "smooth", block: "center" });
    pane.classList.add("pane--flash");
    setTimeout(function () { pane.classList.remove("pane--flash"); }, 700);
    const input = pane.querySelector("[data-chat-input]");
    if (input) input.focus();
  }

  // Overlay d'aide (construit une fois).
  let overlay = null;
  function buildOverlay() {
    if (overlay) return overlay;
    overlay = document.createElement("div");
    overlay.className = "kbd-overlay";
    overlay.hidden = true;
    overlay.innerHTML =
      '<div class="kbd-panel" role="dialog" aria-label="Raccourcis clavier">' +
      '<h2>Raccourcis</h2><div class="kbd-list">' +
      rows([
        ["Nouveau terminal", "n"],
        ["Nouveau chat", "c"],
        ["Basculer le direct", "g"],
        ["Panique (tout privé)", "!"],
        ["Zoom / dézoom du 1er pane", "z"],
        ["Focus pane 1…9", "1 – 9"],
        ["Régie / confidentialité", "r"],
        ["Dicter (maintenir le micro)", "🎤 fr-FR"],
        ["Afficher / masquer cette aide", "?"],
      ]) +
      "</div></div>";
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) hide();
    });
    document.body.appendChild(overlay);
    return overlay;
  }
  function rows(pairs) {
    return pairs.map(function (p) {
      return '<div class="kbd-row"><span>' + p[0] + "</span><kbd>" + p[1] + "</kbd></div>";
    }).join("");
  }
  function show() { buildOverlay().hidden = false; }
  function hide() { if (overlay) overlay.hidden = true; }
  function toggleHelp() { buildOverlay(); overlay.hidden ? show() : hide(); }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      hide();
      return;
    }
    if (typing(event.target) || event.metaKey || event.ctrlKey || event.altKey) return;

    switch (event.key) {
      case "?":
        event.preventDefault(); toggleHelp(); break;
      case "n":
        if (click("[data-agent-new]")) event.preventDefault();
        break;
      case "c":
        if (click("[data-agent-new]")) event.preventDefault();
        break;
      case "g":
        if (click("[data-live-toggle]")) event.preventDefault();
        break;
      case "!":
        if (click("[data-panic]")) event.preventDefault();
        break;
      case "r":
        if (click("[href*='observer/regie'], [hx-get*='observer/regie']")) event.preventDefault();
        break;
      case "z":
        { const zoom = document.querySelector(".pane [aria-label*='Zoomer']");
          if (zoom) { zoom.click(); event.preventDefault(); } }
        break;
      default:
        if (/^[1-9]$/.test(event.key)) { focusPane(Number(event.key)); event.preventDefault(); }
    }
  });

  // Indice discret.
  const hint = document.createElement("div");
  hint.className = "kbd-hint";
  hint.textContent = "? raccourcis";
  hint.addEventListener("click", toggleHelp);
  document.addEventListener("DOMContentLoaded", function () { document.body.appendChild(hint); });
  if (document.readyState !== "loading") document.body.appendChild(hint);
})();
