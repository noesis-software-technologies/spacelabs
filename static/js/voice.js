/* Commande vocale (Sprint 6 + 7) — push-to-talk par pane, transcript éditable.

   Deux backends, choisis par le serveur (body[data-stt-backend]) :
   - "webspeech"      : reconnaissance CÔTÉ NAVIGATEUR (Web Speech API fr-FR).
   - "crisperwhisper"/"fake" : capture MediaRecorder → POST /voice/transcribe/
     → transcript verbatim renvoyé par le serveur (CrisperWhisper).

   Dans les deux cas, mêmes cibles : pane chat → composer ; pane PTY → barre
   éditable puis stdin. Dégradation gracieuse si l'API requise manque. */
(function () {
  "use strict";

  const body = document.body;
  const BACKEND = (body.getAttribute("data-stt-backend") || "webspeech");
  const SERVER_SIDE = BACKEND === "crisperwhisper" || BACKEND === "fake";
  const TRANSCRIBE_URL = body.getAttribute("data-transcribe-url") || "/voice/transcribe/";

  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const canServer = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  const supported = SERVER_SIDE ? canServer : !!SR;

  if (!supported) {
    ready(hideAllMics);
    return;
  }
  function hideAllMics() {
    document.querySelectorAll("[data-voice]").forEach(function (b) { b.hidden = true; });
  }
  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }
  function b64(str) { return btoa(unescape(encodeURIComponent(str))); }
  function toast(message, variant) {
    body.dispatchEvent(new CustomEvent("cockpit:toast", { detail: { message: message, variant: variant || "info" } }));
  }

  let active = null; // { button, stop }

  /* ── Résolution de la cible d'un micro ─────────────────────────────── */
  function sinkFor(button) {
    const pane = button.closest(".pane");
    if (!pane) return null;
    if (button.getAttribute("data-voice") === "chat") {
      const input = pane.querySelector("[data-chat-input]");
      return input ? { kind: "chat", input: input, pane: pane } : null;
    }
    const bar = pane.querySelector("[data-voice-bar]");
    const input = bar && bar.querySelector("[data-voice-input]");
    if (!bar || !input) return null;
    return { kind: "pty", input: input, bar: bar, pane: pane };
  }
  function placeText(sink, text, opts) {
    if (sink.kind === "chat") {
      const base = (opts && opts.base) || "";
      sink.input.value = base + text;
      sink.input.dispatchEvent(new Event("input", { bubbles: true }));
    } else {
      sink.bar.hidden = false;
      sink.input.value = text;
      sink.input.focus();
    }
  }

  /* ── Backend navigateur (Web Speech API) ───────────────────────────── */
  function startWebSpeech(button, sink) {
    const rec = new SR();
    rec.lang = "fr-FR";
    rec.interimResults = true;
    rec.continuous = true;
    const base = sink.kind === "chat" && sink.input.value ? sink.input.value.trimEnd() + " " : "";
    let finalText = "";
    if (sink.kind === "pty") { sink.bar.hidden = false; sink.input.focus(); }
    rec.onresult = function (e) {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalText += t; else interim += t;
      }
      placeText(sink, finalText + interim, { base: base });
    };
    rec.onerror = function (e) {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") toast("Micro refusé.", "danger");
      else if (e.error !== "no-speech" && e.error !== "aborted") toast("Reconnaissance : " + e.error, "danger");
    };
    rec.onend = function () { clearActive(button); };
    try { rec.start(); } catch (e) { /* déjà démarré */ }
    return function stop() { try { rec.stop(); } catch (e) {} };
  }

  /* ── Backend serveur (MediaRecorder → CrisperWhisper) ──────────────── */
  function startServer(button, sink) {
    let recorder = null, stream = null;
    const chunks = [];
    let stopped = false;

    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (s) {
      if (stopped) { s.getTracks().forEach(function (t) { t.stop(); }); return; }
      stream = s;
      recorder = new MediaRecorder(s);
      recorder.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
      recorder.onstop = function () {
        stream.getTracks().forEach(function (t) { t.stop(); });
        const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        sendAudio(blob, sink, button);
      };
      recorder.start();
      if (sink.kind === "pty") { sink.bar.hidden = false; }
    }).catch(function (err) {
      clearActive(button);
      toast(err && err.name === "NotAllowedError" ? "Micro refusé — autorise l'accès." : "Micro indisponible.", "danger");
    });

    return function stop() {
      stopped = true;
      if (recorder && recorder.state !== "inactive") recorder.stop();
      else clearActive(button);
    };
  }

  function sendAudio(blob, sink, button) {
    button.classList.add("voice--processing");
    if (sink.kind === "chat") { /* laisse le texte existant */ }
    else { sink.input.value = "transcription…"; }
    const fd = new FormData();
    fd.append("audio", blob, "audio.webm");
    fetch(TRANSCRIBE_URL, {
      method: "POST",
      headers: { "X-CSRFToken": window.CockpitSocket.csrfToken() },
      body: fd,
    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        button.classList.remove("voice--processing");
        if (!res.ok) { toast(res.j.error || "Transcription échouée.", "danger"); if (sink.kind === "pty") sink.input.value = ""; return; }
        const base = sink.kind === "chat" && sink._base ? sink._base : "";
        placeText(sink, res.j.text || "", { base: base });
      })
      .catch(function () {
        button.classList.remove("voice--processing");
        toast("Transcription indisponible (réseau).", "danger");
        if (sink.kind === "pty") sink.input.value = "";
      });
  }

  /* ── Push-to-talk : maintien = enregistre, relâche = stoppe ────────── */
  function begin(button) {
    const sink = sinkFor(button);
    if (!sink) return;
    if (active) active.stop();
    if (sink.kind === "chat") sink._base = sink.input.value ? sink.input.value.trimEnd() + " " : "";
    button.classList.add("voice--listening");
    button.setAttribute("aria-pressed", "true");
    const stop = SERVER_SIDE ? startServer(button, sink) : startWebSpeech(button, sink);
    active = { button: button, stop: stop };
  }
  function clearActive(button) {
    button.classList.remove("voice--listening");
    button.setAttribute("aria-pressed", "false");
    active = null;
  }
  function hold(button) {
    let holding = false;
    button.addEventListener("pointerdown", function (e) { e.preventDefault(); holding = true; begin(button); });
    const release = function () { if (holding) { holding = false; if (active) active.stop(); } };
    button.addEventListener("pointerup", release);
    button.addEventListener("pointerleave", release);
    button.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        if (active && active.button === button) active.stop(); else begin(button);
      }
    });
  }

  function wire(root) {
    (root || document).querySelectorAll("[data-voice]").forEach(function (b) {
      if (!b._wired) { b._wired = true; hold(b); }
    });
  }

  /* Envoi stdin depuis la barre de dictée PTY (Entrée ou bouton). */
  document.addEventListener("keydown", function (e) {
    const input = e.target.closest("[data-voice-input]");
    if (!input || e.key !== "Enter") return;
    e.preventDefault();
    sendPty(input);
  });
  document.addEventListener("click", function (e) {
    const send = e.target.closest("[data-voice-send]");
    if (send) sendPty(send.closest("[data-voice-bar]").querySelector("[data-voice-input]"));
    const close = e.target.closest("[data-voice-close]");
    if (close) close.closest("[data-voice-bar]").hidden = true;
  });
  function sendPty(input) {
    const pane = input.closest(".pane");
    const host = pane && pane.querySelector("[data-pane-host]");
    const text = input.value.trim();
    if (host && text && text !== "transcription…") {
      window.CockpitSocket.send({ op: "stdin", pane_id: host.getAttribute("data-pane-id"), data: b64(text + "\n") });
    }
    input.value = "";
    input.closest("[data-voice-bar]").hidden = true;
  }

  const mo = new MutationObserver(function (muts) {
    muts.forEach(function (m) { m.addedNodes.forEach(function (n) { if (n instanceof Element) wire(n); }); });
  });
  ready(function () {
    wire(document);
    mo.observe(document.getElementById("content") || document.body, { childList: true, subtree: true });
  });
})();
