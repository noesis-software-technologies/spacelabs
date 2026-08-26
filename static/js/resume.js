/* Reprise de session (Sprint 6). Les panes flaggés resume_pending (posé au
   boot quand COCKPIT_RESUME_ON_BOOT) portent un bouton « Reprendre ». Ce
   module : (1) reprend en un clic, (2) reprend automatiquement à la connexion
   si la reprise auto est active, (3) masque la barre une fois lancé. */
(function () {
  "use strict";

  function autoOn() {
    return document.body.getAttribute("data-resume-on-boot") === "1";
  }

  function resumePane(button) {
    const pane = button.closest(".pane");
    if (!pane) return;
    const chatHost = pane.querySelector("[data-chat-host]");
    const ptyHost = pane.querySelector("[data-pane-host]");
    if (button.hasAttribute("data-chat-resume") && chatHost) {
      window.CockpitSocket.send({ op: "chat_start", pane_id: chatHost.getAttribute("data-pane-id"), resume: true });
    } else if (ptyHost) {
      // Réutilise l'op respawn(continue) — même chemin que le bouton relancer.
      window.CockpitSocket.send({ op: "spawn", pane_id: ptyHost.getAttribute("data-pane-id"), continue: true });
    }
    const bar = button.closest("[data-resume-bar]");
    if (bar) bar.hidden = true;
  }

  document.addEventListener("click", function (e) {
    const btn = e.target.closest("[data-chat-resume], [data-resume-auto]");
    if (btn) resumePane(btn);
  });

  // Reprise auto : à chaque (re)connexion, si activée, on relance les flaggés.
  document.body.addEventListener("cockpit:open", function () {
    if (!autoOn()) return;
    document.querySelectorAll("[data-resume-auto]").forEach(function (btn) {
      const bar = btn.closest("[data-resume-bar]");
      if (bar && !bar.hidden) resumePane(btn);
    });
  });
})();
