(function () {
  "use strict";
  var key = "tris.dashboard.display.v1";
  var panelNames = ["portfolio", "quotes", "dividends", "agenda", "github", "weather", "trello", "server", "fitness"];
  var settings = {compact: false, dim: false, glance: false, largeText: false, highContrast: false, refreshMinutes: 3, pauseRefresh: false, hidden: [], order: panelNames.slice(0)};

  function store() {
    try { window.localStorage.setItem(key, JSON.stringify(settings)); } catch (error) {}
  }

  function restore() {
    try {
      var saved = JSON.parse(window.localStorage.getItem(key));
      if (saved && typeof saved === "object") {
        settings.compact = saved.compact === true;
        settings.dim = saved.dim === true;
        settings.glance = saved.glance === true;
        settings.largeText = saved.largeText === true;
        settings.highContrast = saved.highContrast === true;
        settings.refreshMinutes = [3, 5, 10].indexOf(saved.refreshMinutes) !== -1 ? saved.refreshMinutes : 3;
        settings.pauseRefresh = saved.pauseRefresh === true;
        if (Object.prototype.toString.call(saved.order) === "[object Array]") {
          var ordered = [];
          for (var j = 0; j < saved.order.length; j++) {
            if (panelNames.indexOf(saved.order[j]) !== -1 && ordered.indexOf(saved.order[j]) === -1) {
              ordered.push(saved.order[j]);
            }
          }
          for (var k = 0; k < panelNames.length; k++) {
            if (ordered.indexOf(panelNames[k]) === -1) { ordered.push(panelNames[k]); }
          }
          settings.order = ordered;
        }
        if (Object.prototype.toString.call(saved.hidden) === "[object Array]") {
          settings.hidden = [];
          for (var i = 0; i < saved.hidden.length; i++) {
            if (panelNames.indexOf(saved.hidden[i]) !== -1 && settings.hidden.indexOf(saved.hidden[i]) === -1) {
              settings.hidden.push(saved.hidden[i]);
            }
          }
        }
      }
    } catch (error) {}
  }

  // Active view is derived from visible panels, not from the last button clicked.
  // That also restores the correct label after a saved layout is reopened.
  var viewPresets = [
    {id: "assets-only-panels", quickId: "quick-view-assets", name: "Assets view", panels: ["portfolio", "quotes", "dividends"]},
    {id: "development-only-panels", quickId: "quick-view-development", name: "Development view", panels: ["github", "trello"]},
    {id: "fitness-only-panels", quickId: "quick-view-fitness", name: "Fitness view", panels: ["fitness", "weather"]},
    {id: "today-only-panels", quickId: "quick-view-today", name: "Today view", panels: ["agenda", "weather", "server"]}
  ];
  function updateActiveView() {
    var visible = [];
    for (var i = 0; i < panelNames.length; i++) {
      if (settings.hidden.indexOf(panelNames[i]) === -1) { visible.push(panelNames[i]); }
    }
    var selected = null;
    for (var j = 0; j < viewPresets.length; j++) {
      var preset = viewPresets[j];
      var matches = visible.length === preset.panels.length;
      for (var k = 0; matches && k < preset.panels.length; k++) {
        if (visible.indexOf(preset.panels[k]) === -1) { matches = false; }
      }
      document.getElementById(preset.id).setAttribute("aria-pressed", matches ? "true" : "false");
      document.getElementById(preset.quickId).setAttribute("aria-pressed", matches ? "true" : "false");
      if (matches) { selected = preset.name; }
    }
    document.getElementById("panel-preset-status").textContent = selected ?
      selected + " · " + visible.length + " panels" :
      (visible.length === panelNames.length ? "All panels · " + visible.length + " panels" :
       visible.length === 0 ? "No panels visible" :
       "Custom panel selection · " + visible.length + " panels");
  }

  function apply() {
    document.body.className = (settings.compact ? "compact" : "") + (settings.dim ? " dimmed" : "") + (settings.glance ? " glance" : "") + (settings.largeText ? " large-text" : "") + (settings.highContrast ? " high-contrast" : "");
    document.getElementById("setting-compact").checked = settings.compact;
    document.getElementById("setting-dim").checked = settings.dim;
    document.getElementById("setting-glance").checked = settings.glance;
    document.getElementById("setting-large-text").checked = settings.largeText;
    document.getElementById("setting-high-contrast").checked = settings.highContrast;
    document.getElementById("setting-refresh-minutes").value = String(settings.refreshMinutes);
    document.getElementById("setting-pause-refresh").checked = settings.pauseRefresh;
    document.getElementById("refresh-cadence").textContent = settings.pauseRefresh ?
      "Automatic data refresh paused · Manual refresh available" :
      "Data refreshes every " + settings.refreshMinutes + " minutes";
    window.trisDashboardRefreshMinutes = settings.refreshMinutes;
    window.trisDashboardRefreshPaused = settings.pauseRefresh;
    document.getElementById("empty-panels").hidden = settings.hidden.length !== panelNames.length;
    var container = document.getElementById("dashboard-modules");
    for (var o = 0; o < settings.order.length; o++) {
      var orderedCard = document.querySelector('[data-panel="' + settings.order[o] + '"]');
      if (orderedCard) { container.appendChild(orderedCard); }
    }
    // Keep the quick-jump sequence aligned with the user-defined card order.
    var jumpBar = document.getElementById("priority-jumps");
    for (var j = 0; j < settings.order.length; j++) {
      var jump = document.getElementById("jump-link-" + settings.order[j]);
      if (jump) { jumpBar.appendChild(jump); }
    }
    for (var p = 0; p < panelNames.length; p++) {
      var position = settings.order.indexOf(panelNames[p]);
      var upButton = document.getElementById("panel-up-" + panelNames[p]);
      var downButton = document.getElementById("panel-down-" + panelNames[p]);
      if (upButton) { upButton.disabled = position === 0; }
      if (downButton) { downButton.disabled = position === settings.order.length - 1; }
    }
    var visibleShortcuts = 0;
    for (var i = 0; i < panelNames.length; i++) {
      var name = panelNames[i];
      var visible = settings.hidden.indexOf(name) === -1;
      var card = document.querySelector('[data-panel="' + name + '"]');
      if (card) { card.hidden = !visible; }
      var toggle = document.getElementById("toggle-" + name);
      if (toggle) { toggle.checked = visible; }
      if (name === "portfolio" || name === "dividends" ||
          name === "github" || name === "fitness" ||
          name === "agenda" || name === "weather" ||
          name === "trello" || name === "server" ||
          name === "quotes") {
        var shortcut = document.getElementById("jump-link-" + name);
        shortcut.hidden = !visible;
        if (visible) { visibleShortcuts++; }
      }
    }
    document.getElementById("priority-jumps-empty").hidden = visibleShortcuts !== 0;
    document.getElementById("priority-jumps-count").textContent =
      visibleShortcuts + " of " + panelNames.length + " shortcuts available";
    updateActiveView();
  }

  function movePanel(name, direction) {
    var index = settings.order.indexOf(name);
    var next = index + direction;
    if (index < 0 || next < 0 || next >= settings.order.length) { return; }
    var swap = settings.order[next];
    settings.order[next] = name;
    settings.order[index] = swap;
    apply(); store();
    document.getElementById("panel-order-status").textContent =
      "Moved " + name + " to position " + (settings.order.indexOf(name) + 1) +
      " of " + settings.order.length;
  }

  function buildControls() {
    var target = document.getElementById("panel-visibility");
    for (var i = 0; i < panelNames.length; i++) {
      (function (name) {
        var label = document.createElement("label");
        var checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.id = "toggle-" + name;
        checkbox.addEventListener("change", function () {
          var index = settings.hidden.indexOf(name);
          if (!checkbox.checked && index === -1) { settings.hidden.push(name); }
          if (checkbox.checked && index !== -1) { settings.hidden.splice(index, 1); }
          apply(); store();
        });
        label.appendChild(checkbox);
        label.appendChild(document.createTextNode(" " + name));
        var up = document.createElement("button");
        up.type = "button";
        up.id = "panel-up-" + name;
        up.textContent = "Move " + name + " up";
        up.addEventListener("click", function () { movePanel(name, -1); });
        var down = document.createElement("button");
        down.type = "button";
        down.id = "panel-down-" + name;
        down.textContent = "Move " + name + " down";
        down.addEventListener("click", function () { movePanel(name, 1); });
        label.appendChild(up);
        label.appendChild(down);
        target.appendChild(label);
      }(panelNames[i]));
    }
  }

  document.getElementById("reset-panel-order").addEventListener("click", function () {
    settings.order = panelNames.slice(0);
    apply(); store();
    document.getElementById("panel-order-status").textContent = "Default panel order restored";
  });

  document.getElementById("settings-button").addEventListener("click", function () {
    var panel = document.getElementById("display-settings");
    panel.hidden = !panel.hidden;
    this.setAttribute("aria-expanded", panel.hidden ? "false" : "true");
    if (panel.hidden && typeof this.focus === "function") { this.focus(); }
    if (!panel.hidden) {
      var firstControl = document.getElementById("setting-compact");
      if (firstControl && typeof firstControl.focus === "function") { firstControl.focus(); }
    }
  });
  document.getElementById("close-display-settings").addEventListener("click", function () {
    document.getElementById("display-settings").hidden = true;
    document.getElementById("settings-button").setAttribute("aria-expanded", "false");
    if (typeof document.getElementById("settings-button").focus === "function") {
      document.getElementById("settings-button").focus();
    }
  });
  document.addEventListener("keydown", function (event) {
    if (event.keyCode === 27 || event.key === "Escape") {
      var panel = document.getElementById("display-settings");
      if (!panel.hidden) {
        panel.hidden = true;
        document.getElementById("settings-button").setAttribute("aria-expanded", "false");
        if (typeof document.getElementById("settings-button").focus === "function") {
          document.getElementById("settings-button").focus();
        }
      }
    }
  });
  document.getElementById("setting-compact").addEventListener("change", function () {
    settings.compact = this.checked; apply(); store();
  });
  document.getElementById("setting-dim").addEventListener("change", function () {
    settings.dim = this.checked; apply(); store();
  });
  document.getElementById("setting-glance").addEventListener("change", function () {
    settings.glance = this.checked; apply(); store();
  });
  document.getElementById("setting-large-text").addEventListener("change", function () {
    settings.largeText = this.checked; apply(); store();
  });
  document.getElementById("setting-high-contrast").addEventListener("change", function () {
    settings.highContrast = this.checked; apply(); store();
  });
  document.getElementById("setting-pause-refresh").addEventListener("change", function () {
    var wasPaused = settings.pauseRefresh;
    settings.pauseRefresh = this.checked;
    apply(); store();
    if (settings.pauseRefresh && typeof window.trisDashboardCancelPendingRetry === "function") {
      window.trisDashboardCancelPendingRetry();
    } else if (wasPaused && !settings.pauseRefresh && typeof window.trisDashboardResumeRefresh === "function") {
      window.trisDashboardResumeRefresh();
    }
  });
  document.getElementById("setting-refresh-minutes").addEventListener("change", function () {
    var minutes = Number(this.value);
    if ([3, 5, 10].indexOf(minutes) !== -1) { settings.refreshMinutes = minutes; }
    apply(); store();
  });
  document.getElementById("focus-panels").addEventListener("click", function () {
    var focus = ["portfolio", "quotes", "dividends", "github", "fitness"];
    settings.hidden = [];
    for (var i = 0; i < panelNames.length; i++) {
      if (focus.indexOf(panelNames[i]) === -1) { settings.hidden.push(panelNames[i]); }
    }
    apply(); store();
  });
  document.getElementById("minimal-panels").addEventListener("click", function () {
    var minimal = ["weather", "agenda", "server"];
    settings.hidden = [];
    for (var i = 0; i < panelNames.length; i++) {
      if (minimal.indexOf(panelNames[i]) === -1) { settings.hidden.push(panelNames[i]); }
    }
    apply(); store();
  });
  function applyVisibilityPreset(visibleNames, title) {
    settings.hidden = [];
    for (var i = 0; i < panelNames.length; i++) {
      if (visibleNames.indexOf(panelNames[i]) === -1) {
        settings.hidden.push(panelNames[i]);
      }
    }
    apply(); store();
  }

  document.getElementById("assets-only-panels").addEventListener("click", function () {
    applyVisibilityPreset(["portfolio", "quotes", "dividends"], "Assets view");
  });
  document.getElementById("development-only-panels").addEventListener("click", function () {
    applyVisibilityPreset(["github", "trello"], "Development view");
  });
  document.getElementById("fitness-only-panels").addEventListener("click", function () {
    applyVisibilityPreset(["fitness", "weather"], "Fitness view");
  });
  document.getElementById("today-only-panels").addEventListener("click", function () {
    applyVisibilityPreset(["agenda", "weather", "server"], "Today view");
  });

  for (var q = 0; q < viewPresets.length; q++) {
    (function (preset) {
      document.getElementById(preset.quickId).addEventListener("click", function () {
        applyVisibilityPreset(preset.panels, preset.name);
      });
    }(viewPresets[q]));
  }

  document.getElementById("show-all-panels").addEventListener("click", function () {
    settings.hidden = [];
    apply(); store();
  });
  document.getElementById("hide-all-panels").addEventListener("click", function () {
    settings.hidden = panelNames.slice(0);
    apply(); store();
  });
  document.getElementById("reset-settings").addEventListener("click", function () {
    var wasPaused = settings.pauseRefresh;
    settings = {compact: false, dim: false, glance: false, largeText: false, highContrast: false, refreshMinutes: 3, pauseRefresh: false, hidden: [], order: panelNames.slice(0)};
    apply(); store();
    if (wasPaused && typeof window.trisDashboardResumeRefresh === "function") {
      window.trisDashboardResumeRefresh();
    }
  });

  buildControls(); restore(); apply();
}());
