/* Runs in <head> so the saved theme / text size / contrast apply before first paint (no flash). */
(function () {
  try {
    var prefs = JSON.parse(localStorage.getItem("lostlocker.display")) || {};
    var root = document.documentElement;
    ["theme", "text", "contrast"].forEach(function (name) {
      if (prefs[name]) { root.setAttribute("data-" + name, prefs[name]); }
    });
  } catch (e) { /* ignore: defaults apply */ }
})();
