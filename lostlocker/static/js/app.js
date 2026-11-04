/* Progressive enhancements. Every page works without this file. */
(function () {
  "use strict";
  var root = document.documentElement;
  var KEY = "lostlocker.display";

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; }
  }
  function save(prefs) {
    try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch (e) { /* private mode */ }
  }

  // ---- Display settings (theme, text size, high contrast). Applied early by theme-init.js.
  function apply(prefs) {
    ["theme", "text", "contrast"].forEach(function (name) {
      if (prefs[name]) { root.setAttribute("data-" + name, prefs[name]); }
      else { root.removeAttribute("data-" + name); }
    });
  }

  var panel = document.getElementById("settings-panel");
  if (panel) {
    var prefs = load();
    panel.querySelectorAll("input[type=radio]").forEach(function (input) {
      var saved = prefs[input.name] || "";
      input.checked = input.value === saved;
      input.addEventListener("change", function () {
        prefs[input.name] = input.value;
        if (!input.value) { delete prefs[input.name]; }
        save(prefs);
        apply(prefs);
      });
    });
    var reset = document.getElementById("settings-reset");
    if (reset) {
      reset.addEventListener("click", function () {
        prefs = {};
        save(prefs);
        apply(prefs);
        panel.querySelectorAll("input[type=radio]").forEach(function (i) { i.checked = i.value === ""; });
      });
    }
    // Close the settings menu with Escape and return focus to its button.
    var details = panel.closest("details");
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && details && details.open) {
        details.open = false;
        details.querySelector("summary").focus();
      }
    });
  }

  // ---- Photo preview
  var file = document.getElementById("image-upload");
  var preview = document.getElementById("photo-preview");
  if (file && preview && window.URL) {
    file.addEventListener("change", function () {
      var f = file.files && file.files[0];
      if (f && /^image\//.test(f.type)) {
        preview.src = URL.createObjectURL(f);
        preview.hidden = false;
      } else {
        preview.hidden = true;
      }
    });
  }

  // ---- Show / hide password
  document.querySelectorAll("[data-toggle-password]").forEach(function (btn) {
    var input = document.getElementById(btn.getAttribute("data-toggle-password"));
    btn.hidden = false;
    btn.addEventListener("click", function () {
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.setAttribute("aria-pressed", show ? "true" : "false");
      btn.textContent = show ? "Hide" : "Show";
    });
  });

  // ---- Move keyboard focus to the error summary after a failed submit.
  var summary = document.getElementById("error-summary");
  if (summary) { summary.focus(); }

  // ---- Let people press an error link and land on the field (focus, not just scroll).
  document.querySelectorAll("#error-summary a[href^='#']").forEach(function (a) {
    a.addEventListener("click", function (e) {
      var target = document.getElementById(a.getAttribute("href").slice(1));
      if (!target) { return; }
      e.preventDefault();
      var focusable = target.matches("input,select,textarea,button") ? target
        : target.querySelector("input,select,textarea,button");
      (focusable || target).focus();
      target.scrollIntoView({ block: "center" });
    });
  });
})();
