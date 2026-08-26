/* Bridge — commande vocale et texte du cockpit.
   Reconnaissance : Web Speech si le navigateur sait, sinon saisie texte. Le
   serveur ne reçoit que du TEXTE : il ne fait pas la différence entre une
   phrase dictée et une phrase tapée (voice.js gère déjà le STT serveur).
   Vanilla + délégation : survit aux swaps htmx. */
(function () {
  "use strict";

  function root() { return document.querySelector("[data-bridge]"); }

  function setState(state, hint) {
    const el = root();
    if (!el) return;
    const orb = el.querySelector("[data-bridge-orb]");
    const label = el.querySelector("[data-bridge-state]");
    const hintEl = el.querySelector("[data-bridge-hint]");
    if (orb) orb.setAttribute("data-state", state);
    if (label) {
      label.setAttribute("data-state", state);
      label.textContent = {
        standby: "VEILLE", listening: "ÉCOUTE", thinking: "TRAITEMENT", speaking: "RÉPONSE",
      }[state] || state.toUpperCase();
    }
    if (hintEl && hint) hintEl.textContent = hint;
  }

  let seq = 0;
  function log(who, text) {
    const el = root();
    if (!el) return;
    const box = el.querySelector("[data-bridge-log]");
    if (!box) return;
    seq += 1;
    const msg = document.createElement("div");
    msg.className = "bridge-msg";
    msg.setAttribute("data-who", who);
    msg.innerHTML =
      '<span class="bridge-msg-n"></span><span class="bridge-msg-bar"></span>' +
      '<div class="bridge-body"><div class="bridge-msg-who"></div>' +
      '<div class="bridge-msg-text"></div></div>';
    msg.querySelector(".bridge-msg-n").textContent = "#" + seq;
    msg.querySelector(".bridge-msg-who").textContent = who === "bridge" ? "BRIDGE" : "VOUS";
    msg.querySelector(".bridge-msg-text").textContent = text;
    box.appendChild(msg);
    box.scrollTop = box.scrollHeight;
  }

  function csrf() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function send(text) {
    const el = root();
    if (!el || !text.trim()) return;
    log("you", text);
    setState("thinking", "Routage de l'intention…");
    const body = new URLSearchParams({
      text: text,
      workspace: el.getAttribute("data-workspace") || "",
    });
    fetch(el.getAttribute("data-command-url"), {
      method: "POST",
      headers: { "X-CSRFToken": csrf(), "Content-Type": "application/x-www-form-urlencoded" },
      body: body,
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        setState("speaking", data.understood ? "Fait" : "Non compris");
        log("bridge", data.reply || "…");
        // Une action peut avoir changé la grille : on la rafraîchit.
        if (data.understood && window.htmx) {
          document.body.dispatchEvent(new CustomEvent("workspacesChanged"));
        }
        setTimeout(function () { setState("standby", "Cliquer pour parler"); }, 1200);
      })
      .catch(function () {
        setState("standby", "Erreur réseau");
        log("bridge", "Impossible de joindre le cockpit.");
      });
  }

  /* Saisie texte — toujours disponible, même sans micro. */
  document.addEventListener("submit", function (event) {
    const form = event.target.closest("[data-bridge-form]");
    if (!form) return;
    event.preventDefault();
    const input = form.querySelector("[data-bridge-input]");
    if (!input) return;
    send(input.value);
    input.value = "";
  });

  /* Micro — Web Speech quand c'est disponible, sinon on invite à écrire. */
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recog = null;

  document.addEventListener("click", function (event) {
    if (!event.target.closest("[data-bridge-orb]")) return;
    if (!Recognition) {
      setState("standby", "Micro indisponible — écris ta commande");
      return;
    }
    if (recog) { recog.stop(); recog = null; setState("standby", "Cliquer pour parler"); return; }
    recog = new Recognition();
    recog.lang = "fr-FR";
    recog.interimResults = true;
    recog.continuous = false;
    setState("listening", "Parle…");
    recog.onresult = function (e) {
      let text = "";
      for (let i = 0; i < e.results.length; i += 1) text += e.results[i][0].transcript;
      const el = root();
      const input = el && el.querySelector("[data-bridge-input]");
      if (input) input.value = text;
      if (e.results[e.results.length - 1].isFinal) {
        recog = null;
        if (input) input.value = "";
        send(text);
      }
    };
    recog.onerror = function () { recog = null; setState("standby", "Micro indisponible"); };
    recog.onend = function () { if (recog) { recog = null; setState("standby", "Cliquer pour parler"); } };
    recog.start();
  });
})();
