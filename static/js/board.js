/* Board du Tasker — glisser-déposer d'une carte vers une colonne.
   Vanilla + délégation sur document : survit aux swaps htmx (pas d'Alpine,
   pas de ré-init). Le déplacement est POSTé, le serveur renvoie le board. */
(function () {
  "use strict";

  let dragged = null;

  document.addEventListener("dragstart", function (event) {
    const card = event.target.closest(".task-card");
    if (!card) return;
    dragged = card;
    card.setAttribute("data-dragging", "true");
    if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
  });

  document.addEventListener("dragend", function () {
    if (dragged) dragged.removeAttribute("data-dragging");
    document.querySelectorAll("[data-col-drop]").forEach(function (c) {
      c.removeAttribute("data-over");
    });
    dragged = null;
  });

  document.addEventListener("dragover", function (event) {
    const col = event.target.closest("[data-col-drop]");
    if (!col || !dragged) return;
    event.preventDefault();
    col.setAttribute("data-over", "true");
  });

  document.addEventListener("dragleave", function (event) {
    const col = event.target.closest("[data-col-drop]");
    if (col) col.removeAttribute("data-over");
  });

  document.addEventListener("drop", function (event) {
    const col = event.target.closest("[data-col-drop]");
    if (!col || !dragged) return;
    event.preventDefault();
    const board = document.getElementById("mission-board");
    const taskId = dragged.getAttribute("data-task-id");
    const status = col.getAttribute("data-col-drop");
    col.removeAttribute("data-over");
    if (!board || !taskId) return;
    // L'URL est construite depuis celle de la colonne, qui porte task_id=0.
    const template = col.getAttribute("hx-post");
    const url = template.replace(/\/0\/deplacer\/$/, "/" + taskId + "/deplacer/");
    window.htmx.ajax("POST", url, {
      target: "#mission-board",
      swap: "outerHTML",
      values: { status: status },
    });
  });
})();
