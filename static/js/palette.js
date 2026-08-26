/* palette.js — palette de commandes ⌘K (Sprint 1 revamp).

   Lanceur au-dessus des contrôles EXISTANTS du cockpit : chaque entrée déclenche
   un bouton/lien déjà présent (comme shortcuts.js), jamais une logique dupliquée.
   Contextuelle : une commande n'apparaît que si sa cible existe dans le DOM —
   donc la palette s'adapte à la page (cockpit, régie, etc.). Aucun WebSocket. */
(function () {
  "use strict";

  const ICONS = {
    terminal: '<path d="m7 11 2-2-2-2"/><path d="M11 13h4"/><rect width="18" height="18" x="3" y="3" rx="2"/>',
    kanban: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M8 7v7"/><path d="M12 7v4"/><path d="M16 7v9"/>',
    swarm: '<circle cx="12" cy="4.5" r="2.5"/><path d="m10.2 6.3-3.9 3.9"/><circle cx="4.5" cy="12" r="2.5"/><path d="M7 12h10"/><circle cx="19.5" cy="12" r="2.5"/><path d="m13.8 17.7 3.9-3.9"/><circle cx="12" cy="19.5" r="2.5"/>',
    message: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    play: '<polygon points="5 3 19 12 5 21 5 3"/>',
    radio: '<circle cx="12" cy="12" r="2"/><path d="M4.93 19.07a10 10 0 0 1 0-14.14M7.76 16.24a6 6 0 0 1 0-8.49m8.48 0a6 6 0 0 1 0 8.49m2.83-11.32a10 10 0 0 1 0 14.14"/>',
    alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    grid: '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/>',
    sparkles: '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3z"/>',
    code: '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
    activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    panelLeft: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/>',
    panelRight: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M15 3v18"/>',
  };

  function click(sel) {
    const el = document.querySelector(sel);
    if (el) el.click();
  }
  function openDockTab(name) {
    const dock = document.getElementById("bridge-dock");
    if (dock && dock.getAttribute("data-open") === "false") click("[data-dock-toggle]");
    click('[data-tab="' + name + '"]');
  }

  // Registre : sel = clic sur un contrôle existant ; run = action composée.
  // avail (optionnel) = sélecteur qui conditionne l'affichage d'une entrée run.
  const COMMANDS = [
    { label: "Terminals", ico: "terminal", color: "var(--claude)", sel: '[data-mode="terminals"]' },
    { label: "Board", ico: "kanban", color: "var(--blue)", sel: '[data-mode="board"]' },
    { label: "Swarm", ico: "swarm", color: "var(--orange)", sel: '[data-mode="swarm"]' },
    { label: "Nouvel agent…", ico: "terminal", color: "var(--claude)", kbd: "N", sel: "[data-agent-new]" },
    { label: "Tout lancer", ico: "play", color: "var(--green)", sel: "[data-spawn-all]" },
    { label: "Grille dense", ico: "grid", color: "var(--orange)", sel: '[data-density-set="dense"]' },
    { label: "Basculer le direct", ico: "radio", color: "var(--blue)", kbd: "G", sel: "[data-live-toggle]" },
    { label: "Panique — couper le direct", ico: "alert", color: "var(--red)", kbd: "!", sel: "[data-panic]" },
    { label: "Régie", ico: "grid", color: "var(--gold)", kbd: "R", sel: '[href*="observer/regie"]' },
    { label: "Panneau : Skills", ico: "sparkles", color: "var(--green)", avail: '[data-tab="skills"]', run: () => openDockTab("skills") },
    { label: "Panneau : Éditeur", ico: "code", color: "var(--gold)", avail: '[data-tab="editor"]', run: () => openDockTab("editor") },
    { label: "Panneau : Bridge (voix)", ico: "activity", color: "var(--blue)", avail: '[data-tab="bridge"]', run: () => openDockTab("bridge") },
    { label: "Afficher / masquer les workspaces", ico: "panelLeft", color: "var(--text-2)", kbd: "⌘B", sel: "[data-rail-toggle]" },
    { label: "Afficher / masquer le panneau", ico: "panelRight", color: "var(--text-2)", kbd: "⌘\\", sel: "[data-dock-toggle]" },
  ];

  function available(cmd) {
    if (cmd.sel) return !!document.querySelector(cmd.sel);
    return !cmd.avail || !!document.querySelector(cmd.avail);
  }

  const overlay = () => document.getElementById("palette");
  const input = () => document.getElementById("palette-input");
  const list = () => document.getElementById("palette-list");

  let index = 0;
  let visible = [];

  function compute() {
    const q = (input().value || "").toLowerCase().trim();
    visible = COMMANDS.filter(available).filter((c) => !q || c.label.toLowerCase().includes(q));
    if (index >= visible.length) index = Math.max(0, visible.length - 1);
  }

  function render() {
    const el = list();
    if (!visible.length) { el.innerHTML = '<div class="pal-empty">Aucun résultat</div>'; return; }
    el.innerHTML = visible.map(function (c, i) {
      const ic = '<span class="pal-ic" style="background:color-mix(in srgb,' + c.color + ' 16%,transparent);color:' + c.color + '">' +
        '<svg class="ds-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + (ICONS[c.ico] || "") + "</svg></span>";
      const kbd = c.kbd ? '<span class="ki">' + c.kbd + "</span>" : "";
      return '<div class="pal-i' + (i === index ? " on" : "") + '" data-idx="' + i + '" role="option">' + ic + "<span>" + c.label + "</span>" + kbd + "</div>";
    }).join("");
  }

  function isOpen() { return overlay().classList.contains("is-open"); }

  function open() {
    overlay().classList.add("is-open");
    index = 0;
    input().value = "";
    compute();
    render();
    setTimeout(function () { input().focus(); }, 0);
  }
  function close() { overlay().classList.remove("is-open"); }

  function move(delta) {
    if (!visible.length) return;
    index = (index + delta + visible.length) % visible.length;
    render();
    const on = list().querySelector(".pal-i.on");
    if (on) on.scrollIntoView({ block: "nearest" });
  }

  function runItem(cmd) {
    close();
    setTimeout(function () { if (cmd.run) cmd.run(); else if (cmd.sel) click(cmd.sel); }, 50);
  }

  // Ouverture / navigation clavier. ⌘K bascule ; les combinaisons méta sont
  // ignorées par shortcuts.js, donc aucun conflit.
  document.addEventListener("keydown", function (event) {
    if ((event.metaKey || event.ctrlKey) && !event.altKey && event.key.toLowerCase() === "k") {
      event.preventDefault();
      isOpen() ? close() : open();
      return;
    }
    if (!isOpen()) return;
    if (event.key === "Escape") { close(); event.preventDefault(); }
    else if (event.key === "ArrowDown") { move(1); event.preventDefault(); }
    else if (event.key === "ArrowUp") { move(-1); event.preventDefault(); }
    else if (event.key === "Enter") { if (visible[index]) runItem(visible[index]); event.preventDefault(); }
  });

  document.addEventListener("input", function (event) {
    if (event.target === input()) { index = 0; compute(); render(); }
  });

  document.addEventListener("click", function (event) {
    if (event.target.closest("[data-palette-open]")) { open(); return; }
    const o = overlay();
    if (event.target === o) { close(); return; }        // clic sur le fond
    const item = event.target.closest(".pal-i");
    if (item && o.contains(item)) {
      const i = Number(item.getAttribute("data-idx"));
      if (visible[i]) runItem(visible[i]);
    }
  });

  document.addEventListener("mouseover", function (event) {
    const item = event.target.closest(".pal-i");
    if (item && overlay().contains(item)) {
      const i = Number(item.getAttribute("data-idx"));
      if (i !== index) { index = i; render(); }
    }
  });
})();
