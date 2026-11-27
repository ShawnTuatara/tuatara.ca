// tuatara TF3 mods site: figure behaviour. The build writes pins, boxes and legends into the page;
// this adds hover linking (pin <-> legend line), the full-size lightbox, the "find it" tabs, and
// ?edit (shows the cursor's x / y in % over a figure and copies a pin line on click).
(function () {
  "use strict";
  document.documentElement.classList.add("js");
  var edit =/[?&]edit\b/.test(location.search);
  var readout = null;
  if (edit) {
    readout = document.createElement("div");
    readout.className = "edit-readout";
    readout.textContent = "edit mode: move over a figure";
    document.body.appendChild(readout);
  }

  function light(fig, n, on) {
    fig.querySelectorAll('[data-n="' + n + '"]').forEach(function (e) { e.classList.toggle("on", on); });
  }

  function lightbox(img) {
    var lb = document.querySelector(".lightbox");
    if (!lb) {
      lb = document.createElement("div");
      lb.className = "lightbox";
      lb.setAttribute("role", "dialog");
      lb.setAttribute("aria-label", "Full-size image");
      lb.tabIndex = -1;
      lb.addEventListener("click", function () { lb.classList.remove("open"); });
      document.addEventListener("keydown", function (ev) { if (ev.key === "Escape") lb.classList.remove("open"); });
      document.body.appendChild(lb);
    }
    lb.innerHTML = "";
    var big = document.createElement("img");
    big.src = img.currentSrc || img.src;
    big.alt = img.alt;
    lb.appendChild(big);
    lb.classList.add("open");
    lb.focus();
  }

  document.querySelectorAll("figure.shot").forEach(function (fig) {
    var frame = fig.querySelector(".shot-frame");
    var img = frame && frame.querySelector("img");
    if (!img) return;
    fig.querySelectorAll(".pin[data-n], .legend li[data-n]").forEach(function (e) {
      var n = e.getAttribute("data-n");
      e.addEventListener("mouseenter", function () { light(fig, n, true); });
      e.addEventListener("mouseleave", function () { light(fig, n, false); });
    });
    img.addEventListener("click", function () { if (!edit) lightbox(img); });

    if (edit) {
      frame.style.cursor = "crosshair";
      var pos = function (ev) {
        var r = img.getBoundingClientRect();
        return {
          x: Math.round((ev.clientX - r.left) / r.width * 1000) / 10,
          y: Math.round((ev.clientY - r.top) / r.height * 1000) / 10
        };
      };
      frame.addEventListener("mousemove", function (ev) { var p = pos(ev); readout.textContent = "x " + p.x + "  y " + p.y; });
      frame.addEventListener("click", function (ev) {
        var p = pos(ev);
        var line = "{ n = ?, x = " + p.x + ", y = " + p.y + ', text = "" }';
        if (navigator.clipboard) navigator.clipboard.writeText(line).catch(function () {});
        readout.textContent = "copied: " + line;
      });
    }
  });

  document.querySelectorAll("img.zoom").forEach(function (img) {
    img.addEventListener("click", function () { lightbox(img); });
  });

  // Before / after pairs: the switch shows one half at a time (arrow keys move between the two).
  document.querySelectorAll(".pair").forEach(function (pair) {
    var tabs = Array.prototype.slice.call(pair.querySelectorAll(".pair-switch [role=tab]"));
    if (tabs.length < 2) return;
    function show(i, focus) {
      tabs.forEach(function (t, k) {
        var on = k === i;
        t.setAttribute("aria-selected", on ? "true" : "false");
        t.tabIndex = on ? 0 : -1;
        var view = document.getElementById(t.getAttribute("aria-controls"));
        if (view) view.classList.toggle("active", on);
      });
      if (focus) tabs[i].focus();
    }
    tabs.forEach(function (t, i) {
      t.addEventListener("click", function () { show(i, false); });
      t.addEventListener("keydown", function (ev) {
        if (ev.key === "ArrowLeft" || ev.key === "ArrowRight") { ev.preventDefault(); show(1 - i, true); }
      });
    });
  });

  // A window's screens: the tabs over a "find it" pane show one screen at a time (arrow keys move along).
  document.querySelectorAll(".view-tabs").forEach(function (bar) {
    var tabs = Array.prototype.slice.call(bar.querySelectorAll("[role=tab]"));
    function show(i, focus) {
      tabs.forEach(function (t, k) {
        var on = k === i;
        t.setAttribute("aria-selected", on ? "true" : "false");
        t.tabIndex = on ? 0 : -1;
        var view = document.getElementById(t.getAttribute("aria-controls"));
        if (view) view.classList.toggle("active", on);
      });
      if (focus) tabs[i].focus();
    }
    tabs.forEach(function (t, i) {
      t.addEventListener("click", function () { show(i, false); });
      t.addEventListener("keydown", function (ev) {
        if (ev.key === "ArrowRight") { ev.preventDefault(); show((i + 1) % tabs.length, true); }
        if (ev.key === "ArrowLeft") { ev.preventDefault(); show((i + tabs.length - 1) % tabs.length, true); }
      });
    });
  });

  // "Find it in the game": one window's features at a time.
  document.querySelectorAll(".where").forEach(function (where) {
    var buttons = where.querySelectorAll(".where-list button");
    var panes = where.querySelectorAll("[data-pane]");
    buttons.forEach(function (b) {
      b.addEventListener("click", function () {
        buttons.forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
        panes.forEach(function (p) { p.hidden = p.getAttribute("data-pane") !== b.getAttribute("data-show"); });
      });
    });
  });
})();
