(function () {
  "use strict";
  var key = "tris.dashboard.display.v1";
  var panelNames = ["portfolio", "dividends", "github", "weather", "trello", "server", "fitness"];
  var settings = {compact: false, dim: false, glance: false, hidden: []};

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

  function apply() {
    document.body.className = (settings.compact ? "compact" : "") + (settings.dim ? " dimmed" : "") + (settings.glance ? " glance" : "");
    document.getElementById("setting-compact").checked = settings.compact;
    document.getElementById("setting-dim").checked = settings.dim;
    document.getElementById("setting-glance").checked = settings.glance;
    for (var i = 0; i < panelNames.length; i++) {
      var name = panelNames[i];
      var visible = settings.hidden.indexOf(name) === -1;
      var card = document.querySelector('[data-panel="' + name + '"]');
      if (card) { card.hidden = !visible; }
      var toggle = document.getElementById("toggle-" + name);
      if (toggle) { toggle.checked = visible; }
    }
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
        target.appendChild(label);
      }(panelNames[i]));
    }
  }

  document.getElementById("settings-button").addEventListener("click", function () {
    var panel = document.getElementById("display-settings");
    panel.hidden = !panel.hidden;
    this.setAttribute("aria-expanded", panel.hidden ? "false" : "true");
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
  document.getElementById("reset-settings").addEventListener("click", function () {
    settings = {compact: false, dim: false, glance: false, hidden: []}; apply(); store();
  });
  document.getElementById("refresh-button").addEventListener("click", function () {
    window.location.reload();
  });
  buildControls(); restore(); apply();
}());
