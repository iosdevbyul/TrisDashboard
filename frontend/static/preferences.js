(function () {
  "use strict";
  var key = "tris.dashboard.display.v1";
  var panelNames = ["portfolio", "quotes", "dividends", "agenda", "github", "weather", "trello", "server", "fitness"];
  var settings = {compact: false, dim: false, glance: false, largeText: false, highContrast: false, refreshMinutes: 3, pauseRefresh: false, hidden: [], order: panelNames.slice(0)};

  var savedViewKey = "tris.dashboard.my-view.v1";
  var savedVisible = null;
  var lastResetSettings = null;
  var viewHistory = [];
  var viewHistoryIndex = -1;
  var replayingViewHistory = false;
  var viewHistoryLimit = 10;
  var pinsKey = "tris.dashboard.pins.v1";
  var pinned = [];
  var pinnedOnly = false;
  var panelSearchQuery = "";
  var sourceFilter = "all";
  var sourceStates = null;
  function matchesSourceFilter(name) {
    if (sourceFilter === "all") { return true; }
    if (!sourceStates) { return false; }
    var state = sourceStates[name];
    return sourceFilter === "issues" ? (state === "stale" || state === "unavailable") :
      state === sourceFilter;
  }
  function clearTemporaryFilters() {
    sourceFilter = "all";
    panelSearchQuery = "";
    pinnedOnly = false;
    apply();
  }
  function activeTemporaryFilters() {
    var names = [];
    if (panelSearchQuery !== "") { names.push("Search"); }
    if (sourceFilter !== "all") { names.push("Source: " + sourceFilter); }
    if (pinnedOnly) { names.push("Pinned only"); }
    return names;
  }
  function selectSourceFilter(filter) {
    if (["all", "issues", "unconfigured", "ready"].indexOf(filter) === -1) { return; }
    sourceFilter = filter;
    apply();
  }
  // The source filter is temporary and never changes stored visibility or view history.
  window.trisDashboardSetSourceStates = function (states) {
    sourceStates = states;
    apply();
  };
  // Match fixed display labels only: private card data is never searched or transmitted.
  var panelSearchLabels = {
    portfolio: "portfolio assets holdings investments 포트폴리오 자산 보유 종목 투자",
    quotes: "quotes market stocks prices stock price 시세 주식 주가 가격",
    dividends: "dividends income payments 배당 배당금 수익",
    agenda: "agenda calendar schedule events today 일정 달력 오늘 이벤트",
    github: "github development code repositories 깃허브 개발 코드 저장소",
    weather: "weather forecast temperature 날씨 기온 예보",
    trello: "trello workflow tasks projects 트렐로 업무 할일 작업",
    server: "server macbook health diagnostics 서버 맥북 연결 상태",
    fitness: "fitness workout exercise training 운동 헬스 훈련"
  };
  function matchesPanelSearch(name) {
    if (panelSearchQuery === "") { return true; }
    var terms = panelSearchQuery.split(/\s+/);
    var keywords = panelSearchLabels[name];
    for (var i = 0; i < terms.length; i++) {
      if (keywords.indexOf(terms[i]) === -1) { return false; }
    }
    return true;
  }
  function displayOrder() {
    var result = [];
    for (var i = 0; i < settings.order.length; i++) {
      if (pinned.indexOf(settings.order[i]) !== -1) { result.push(settings.order[i]); }
    }
    for (var j = 0; j < settings.order.length; j++) {
      if (pinned.indexOf(settings.order[j]) === -1) { result.push(settings.order[j]); }
    }
    return result;
  }
  function storePins() {
    try { window.localStorage.setItem(pinsKey, JSON.stringify(pinned)); } catch (error) {}
  }
  function restorePins() {
    try {
      var saved = JSON.parse(window.localStorage.getItem(pinsKey));
      if (Object.prototype.toString.call(saved) !== "[object Array]") { return; }
      for (var i = 0; i < saved.length; i++) {
        if (typeof saved[i] === "string" && panelNames.indexOf(saved[i]) !== -1 &&
            pinned.indexOf(saved[i]) === -1) { pinned.push(saved[i]); }
      }
    } catch (error) {}
  }
  function focusPinnedPanel(name) {
    if (pinned.indexOf(name) === -1) { return; }
    sourceFilter = "all";
    pinnedOnly = false;
    panelSearchQuery = "";
    // Navigation does not change saved user visibility or view history.
    apply();
    var card = document.getElementById("panel-" + name);
    if (settings.hidden.indexOf(name) !== -1) {
      // Hidden favorites stay hidden unless the user explicitly opts to reveal them.
      document.getElementById("pinned-panel-message").textContent =
        name + " is hidden in Display settings. Use Show pinned to reveal it.";
      return;
    }
    if (card && typeof card.focus === "function") { card.focus(); }
  }
  function revealPinnedPanels() {
    if (!pinned.length) { return; }
    settings.hidden = settings.hidden.filter(function (name) { return pinned.indexOf(name) === -1; });
    apply(); store();
  }
  function updatePinManager() {
    var manager = document.getElementById("pinned-panel-actions");
    while (manager.firstChild) { manager.removeChild(manager.firstChild); }
    manager.hidden = pinned.length === 0;
    document.getElementById("clear-all-pins").disabled = pinned.length === 0;
    var ordered = displayOrder();
    for (var i = 0; i < ordered.length; i++) {
      if (pinned.indexOf(ordered[i]) === -1) { continue; }
      (function (name) {
        var view = document.createElement("button");
        view.type = "button";
        view.className = "pinned-jump";
        view.id = "pinned-jump-" + name;
        view.textContent = "Go to " + name;
        view.addEventListener("click", function () { focusPinnedPanel(name); });
        manager.appendChild(view);
        var remove = document.createElement("button");
        remove.type = "button";
        remove.className = "pinned-remove";
        remove.id = "pinned-remove-" + name;
        remove.textContent = "Unpin " + name;
        remove.addEventListener("click", function () { togglePin(name); });
        manager.appendChild(remove);
      }(ordered[i]));
    }
    var reveal = document.createElement("button");
    reveal.type = "button";
    reveal.id = "show-pinned-panels";
    reveal.textContent = "Show pinned";
    reveal.addEventListener("click", revealPinnedPanels);
    manager.appendChild(reveal);
  }
  function togglePin(name) {
    var idx = pinned.indexOf(name);
    if (idx === -1) { pinned.push(name); } else { pinned.splice(idx, 1); }
    if (pinnedOnly && !pinned.length) { pinnedOnly = false; }
    storePins(); apply();
  }
  function buildPinButtons() {
    for (var i = 0; i < panelNames.length; i++) {
      (function (name) {
        var card = document.getElementById("panel-" + name);
        var button = document.createElement("button");
        button.id = "pin-" + name;
        button.type = "button";
        button.className = "pin-panel-button";
        button.addEventListener("click", function () { togglePin(name); });
        card.appendChild(button);
      }(panelNames[i]));
    }
  }
  function firstSearchResult() {
    var ordered = displayOrder();
    for (var i = 0; i < ordered.length; i++) {
      var name = ordered[i];
      if ((sourceFilter === "all" ? settings.hidden.indexOf(name) === -1 : true) &&
          (!pinnedOnly || pinned.indexOf(name) !== -1) &&
          matchesSourceFilter(name) && matchesPanelSearch(name)) {
        return document.getElementById("panel-" + name);
      }
    }
    return null;
  }
  function revealMatchingPanels() {
    if (!panelSearchQuery) { return; }
    var previousLength = settings.hidden.length;
    settings.hidden = settings.hidden.filter(function (name) { return !matchesPanelSearch(name); });
    if (settings.hidden.length !== previousLength) { apply(); store(); }
  }
  // Source health links must reach a panel even when a preset or search hides it.
  window.trisDashboardRevealPanel = function (name) {
    if (panelNames.indexOf(name) === -1) { return; }
    sourceFilter = "all";
    pinnedOnly = false;
    panelSearchQuery = "";
    var hiddenIndex = settings.hidden.indexOf(name);
    if (hiddenIndex !== -1) { settings.hidden.splice(hiddenIndex, 1); store(); }
    apply();
    var panel = document.getElementById("panel-" + name);
    if (panel && typeof panel.focus === "function") { panel.focus(); }
  };
  function clearPanelSearch() {
    if (panelSearchQuery === "") { return; }
    panelSearchQuery = "";
    apply();
    var field = document.getElementById("panel-search-input");
    if (typeof field.focus === "function") { field.focus(); }
  }
  function updateViewHistory() {
    document.getElementById("quick-previous-view").disabled = viewHistoryIndex <= 0;
    document.getElementById("quick-next-view").disabled =
      viewHistoryIndex >= viewHistory.length - 1;
    document.getElementById("clear-view-history").disabled = viewHistory.length <= 1;
    document.getElementById("view-history-status").textContent =
      "View history: " + (viewHistoryIndex + 1) + " of " + viewHistory.length;
  }
  function navigateViewHistory(index) {
    if (index < 0 || index >= viewHistory.length || index === viewHistoryIndex) { return; }
    viewHistoryIndex = index;
    replayingViewHistory = true;
    try {
      applyVisibilityPreset(viewHistory[index], "History view");
    } finally {
      replayingViewHistory = false;
    }
  }
  function readSavedView() {
    try {
      var value = JSON.parse(window.localStorage.getItem(savedViewKey));
      if (Object.prototype.toString.call(value) !== "[object Array]") { return null; }
      var unique = [];
      for (var i = 0; i < value.length; i++) {
        if (typeof value[i] !== "string" || panelNames.indexOf(value[i]) === -1 ||
            unique.indexOf(value[i]) !== -1) { return null; }
        unique.push(value[i]);
      }
      return unique.length ? unique : null;
    } catch (error) { return null; }
  }
  function sameVisible(a, b) {
    if (!a || !b || a.length !== b.length) { return false; }
    for (var i = 0; i < a.length; i++) {
      if (b.indexOf(a[i]) === -1) { return false; }
    }
    return true;
  }
  function currentVisible() {
    var result = [];
    for (var i = 0; i < panelNames.length; i++) {
      if (settings.hidden.indexOf(panelNames[i]) === -1) { result.push(panelNames[i]); }
    }
    return result;
  }
  function updateSavedView() {
    var active = sameVisible(currentVisible(), savedVisible);
    document.getElementById("quick-view-mine").disabled = savedVisible === null;
    document.getElementById("clear-my-view").disabled = savedVisible === null;
    document.getElementById("quick-view-mine").setAttribute("aria-pressed", !pinnedOnly && active ? "true" : "false");
    document.getElementById("saved-view-status").textContent = savedVisible ?
      "Saved view: " + savedVisible.length + " panels" + (active ? " · Active" : " · Different from current") :
      "No saved view";
    document.getElementById("saved-view-preview").textContent = savedVisible ?
      "Saved panels: " + savedVisible.join(", ") : "Saved panels: none";
  }

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
      document.getElementById(preset.quickId).setAttribute("aria-pressed", !pinnedOnly && matches ? "true" : "false");
      if (matches) { selected = preset.name; }
    }
    document.getElementById("quick-view-all").setAttribute("aria-pressed",
      !pinnedOnly && visible.length === panelNames.length ? "true" : "false");
    updateSavedView();
    document.getElementById("panel-preset-status").textContent = selected ?
      selected + " · " + visible.length + " panels" :
      (visible.length === panelNames.length ? "All panels · " + visible.length + " panels" :
       visible.length === 0 ? "No panels visible" :
       "Custom panel selection · " + visible.length + " panels");
  }

  function apply() {
    var visibleNow = currentVisible();
    if (viewHistoryIndex === -1) {
      viewHistory.push(visibleNow.slice(0));
      viewHistoryIndex = 0;
    } else if (!replayingViewHistory &&
               !sameVisible(visibleNow, viewHistory[viewHistoryIndex])) {
      // Visiting a new view after Back discards forward-only history.
      viewHistory = viewHistory.slice(0, viewHistoryIndex + 1);
      viewHistory.push(visibleNow.slice(0));
      if (viewHistory.length > viewHistoryLimit) { viewHistory.shift(); }
      viewHistoryIndex = viewHistory.length - 1;
    }
    updateViewHistory();
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
    var searchField = document.getElementById("panel-search-input");
    searchField.value = panelSearchQuery;
    document.getElementById("panel-search-clear").disabled = panelSearchQuery === "";
    var orderedPanels = displayOrder();
    var container = document.getElementById("dashboard-modules");
    for (var o = 0; o < orderedPanels.length; o++) {
      var orderedCard = document.querySelector('[data-panel="' + orderedPanels[o] + '"]');
      if (orderedCard) { container.appendChild(orderedCard); }
    }
    // Keep the quick-jump sequence aligned with the user-defined card order.
    var jumpBar = document.getElementById("priority-jumps");
    for (var j = 0; j < orderedPanels.length; j++) {
      var jump = document.getElementById("jump-link-" + orderedPanels[j]);
      if (jump) { jumpBar.appendChild(jump); }
    }
    for (var p = 0; p < panelNames.length; p++) {
      var position = settings.order.indexOf(panelNames[p]);
      var upButton = document.getElementById("panel-up-" + panelNames[p]);
      var downButton = document.getElementById("panel-down-" + panelNames[p]);
      if (upButton) { upButton.disabled = position === 0; }
      if (downButton) { downButton.disabled = position === settings.order.length - 1; }
    }
    for (var pn = 0; pn < panelNames.length; pn++) {
      var pinName = panelNames[pn];
      var pinButton = document.getElementById("pin-" + pinName);
      pinButton.textContent = pinned.indexOf(pinName) === -1 ? "Pin panel" : "Unpin panel";
      pinButton.setAttribute("aria-label",
        (pinned.indexOf(pinName) === -1 ? "Pin " : "Unpin ") + pinName);
      pinButton.setAttribute("aria-pressed", pinned.indexOf(pinName) === -1 ? "false" : "true");
    }
    document.getElementById("quick-view-pinned").setAttribute("aria-pressed", pinnedOnly ? "true" : "false");
    updatePinManager();
    document.getElementById("quick-view-pinned").disabled = pinned.length === 0;
    document.getElementById("pinned-panel-count").textContent = pinned.length + " pinned";
    var visibleShortcuts = 0;
    var anyMatchingPanel = false;
    var hiddenMatchingPanels = 0;
    for (var i = 0; i < panelNames.length; i++) {
      var name = panelNames[i];
      var configuredVisible = settings.hidden.indexOf(name) === -1;
      var matchesSearch = matchesPanelSearch(name);
      if (matchesSearch) { anyMatchingPanel = true; }
      if (matchesSearch && !configuredVisible) { hiddenMatchingPanels++; }
      var visible = (sourceFilter === "all" ? configuredVisible : true) &&
        matchesSearch && matchesSourceFilter(name) &&
        (!pinnedOnly || pinned.indexOf(name) !== -1);
      var card = document.querySelector('[data-panel="' + name + '"]');
      if (card) { card.hidden = !visible; }
      var toggle = document.getElementById("toggle-" + name);
      if (toggle) { toggle.checked = configuredVisible; }
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
    document.getElementById("panel-search-reveal").hidden =
      panelSearchQuery === "" || hiddenMatchingPanels === 0;
    document.getElementById("panel-search-reveal").textContent =
      "Show " + hiddenMatchingPanels + " matching hidden " +
      (hiddenMatchingPanels === 1 ? "panel" : "panels");
    var sourceMatching = 0;
    for (var s = 0; s < panelNames.length; s++) {
      if (matchesSourceFilter(panelNames[s])) { sourceMatching++; }
    }
    var filters = ["all", "issues", "unconfigured", "ready"];
    for (var sf = 0; sf < filters.length; sf++) {
      document.getElementById("source-filter-" + filters[sf]).setAttribute(
        "aria-pressed", sourceFilter === filters[sf] ? "true" : "false");
    }
    document.getElementById("source-filter-count").textContent = sourceFilter === "all" ?
      "Showing all configured panels" : sourceMatching + " " + sourceFilter + " sources" +
      (panelSearchQuery ? " · search also applied" : "");
    document.getElementById("source-filter-empty").hidden =
      sourceFilter === "all" || visibleShortcuts !== 0 || pinnedOnly ||
      activeTemporaryFilters().length >= 2;
    document.getElementById("source-filter-empty").textContent = sourceMatching ?
      "No " + sourceFilter + " sources match the current search. Clear the search or choose All." :
      "No " + sourceFilter + " sources. Choose All to restore the dashboard.";
    document.getElementById("priority-jumps-empty").hidden =
      visibleShortcuts !== 0 || panelSearchQuery !== "";
    document.getElementById("priority-jumps-count").textContent =
      visibleShortcuts + " of " + panelNames.length + " shortcuts available";
    var searchActive = panelSearchQuery !== "";
    document.getElementById("panel-search-empty").hidden =
      !searchActive || visibleShortcuts !== 0 || sourceFilter !== "all" ||
      pinnedOnly;
    document.getElementById("panel-search-empty").textContent = anyMatchingPanel ?
      "Matching panels are hidden in Display settings. Show a matching panel or clear search." :
      "No panel matches your search. Try another keyword or clear search.";
    document.getElementById("panel-search-count").textContent = searchActive ?
      visibleShortcuts + " matching visible panels" :
      visibleShortcuts + " panels available";
    var activeFilters = activeTemporaryFilters();
    document.getElementById("filter-summary-status").textContent = activeFilters.length ?
      activeFilters.length + " active filters: " + activeFilters.join(" · ") :
      "No temporary filters";
    document.getElementById("clear-temporary-filters").disabled = activeFilters.length === 0;
    document.getElementById("combined-filter-empty").hidden =
      activeFilters.length < 2 || visibleShortcuts !== 0;
    document.getElementById("combined-filter-empty").textContent =
      "No panels match " + activeFilters.join(" and ") +
      ". Clear all filters to return to your saved panel selection.";
    document.getElementById("pinned-panel-empty").hidden =
      !pinnedOnly || visibleShortcuts !== 0 || activeFilters.length >= 2;
    document.getElementById("pinned-panel-empty").textContent =
      pinned.length ? "Pinned panels are hidden by the current search or source status. Clear the filters or show all panels." :
      "No pinned panels. Pin a panel to create your favorites.";
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

  ["all", "issues", "unconfigured", "ready"].forEach(function (name) {
    document.getElementById("source-filter-" + name).addEventListener("click", function () {
      selectSourceFilter(name);
    });
  });

  document.getElementById("clear-temporary-filters").addEventListener("click", clearTemporaryFilters);
  document.getElementById("panel-search-input").addEventListener("input", function () {
    panelSearchQuery = String(this.value || "").toLowerCase().replace(/^\s+|\s+$/g, "");
    apply();
  });
  document.getElementById("panel-search-clear").addEventListener("click", clearPanelSearch);
  document.getElementById("panel-search-reveal").addEventListener("click", revealMatchingPanels);
  document.getElementById("panel-search-input").addEventListener("keydown", function (event) {
    if (event.keyCode === 13 || event.key === "Enter") {
      var result = firstSearchResult();
      if (result) {
        if (typeof event.preventDefault === "function") { event.preventDefault(); }
        if (typeof result.focus === "function") { result.focus(); }
      }
      return;
    }
    if (event.keyCode === 27 || event.key === "Escape") {
      if (panelSearchQuery !== "") {
        if (typeof event.preventDefault === "function") { event.preventDefault(); }
        clearPanelSearch();
      }
    }
  });

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
    if (((event.keyCode === 191 || event.key === "/") && !event.ctrlKey && !event.metaKey && !event.altKey) ||
        ((event.keyCode === 75 || event.key === "k") && (event.ctrlKey || event.metaKey))) {
      var target = event.target || document.activeElement;
      var editing = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" || target.isContentEditable === true);
      if (!editing) {
        if (typeof event.preventDefault === "function") { event.preventDefault(); }
        document.getElementById("panel-search-input").focus();
        return;
      }
    }
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

  document.getElementById("clear-all-pins").addEventListener("click", function () {
    if (!pinned.length) { return; }
    pinned = [];
    pinnedOnly = false;
    storePins(); apply();
    document.getElementById("pinned-panel-message").textContent = "All pins cleared. Display settings preserved.";
  });
  document.getElementById("quick-view-pinned").addEventListener("click", function () {
    if (!pinned.length) { return; }
    pinnedOnly = !pinnedOnly;
    apply();
  });
  document.getElementById("quick-view-all").addEventListener("click", function () {
    pinnedOnly = false;
    settings.hidden = [];
    apply(); store();
  });
  document.getElementById("quick-view-mine").addEventListener("click", function () {
    if (!savedVisible) { return; }
    applyVisibilityPreset(savedVisible, "My view");
  });
  function saveCurrentView() {
    var visible = currentVisible();
    if (!visible.length) {
      document.getElementById("saved-view-status").textContent =
        "Show at least one panel before saving a view";
      return;
    }
    try {
      window.localStorage.setItem(savedViewKey, JSON.stringify(visible));
      savedVisible = visible;
      updateSavedView();
    } catch (error) {
      document.getElementById("saved-view-status").textContent =
        "Could not save view in this browser";
    }
  }
  document.getElementById("save-my-view").addEventListener("click", saveCurrentView);
  document.getElementById("quick-save-my-view").addEventListener("click", saveCurrentView);
  document.getElementById("quick-previous-view").addEventListener("click", function () {
    navigateViewHistory(viewHistoryIndex - 1);
  });
  document.getElementById("quick-next-view").addEventListener("click", function () {
    navigateViewHistory(viewHistoryIndex + 1);
  });
  document.getElementById("clear-view-history").addEventListener("click", function () {
    viewHistory = [currentVisible().slice(0)];
    viewHistoryIndex = 0;
    updateViewHistory();
  });
  document.getElementById("clear-my-view").addEventListener("click", function () {
    if (!savedVisible) { return; }
    try {
      window.localStorage.removeItem(savedViewKey);
      savedVisible = null;
      updateSavedView();
    } catch (error) {
      document.getElementById("saved-view-status").textContent =
        "Could not delete saved view";
    }
  });

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
    // Save an in-memory undo snapshot; keep independently managed favorites.
    lastResetSettings = JSON.parse(JSON.stringify(settings));
    sourceFilter = "all";
    pinnedOnly = false;
    settings = {compact: false, dim: false, glance: false, largeText: false, highContrast: false, refreshMinutes: 3, pauseRefresh: false, hidden: [], order: panelNames.slice(0)};
    apply(); store();
    document.getElementById("undo-display-reset").disabled = false;
    document.getElementById("display-reset-status").textContent =
      "Display reset. Pinned favorites and My view were kept. Undo is available.";
    if (wasPaused && typeof window.trisDashboardResumeRefresh === "function") {
      window.trisDashboardResumeRefresh();
    }
  });
  document.getElementById("undo-display-reset").addEventListener("click", function () {
    if (!lastResetSettings) { return; }
    var wasPaused = settings.pauseRefresh;
    settings = lastResetSettings;
    lastResetSettings = null;
    apply(); store();
    document.getElementById("undo-display-reset").disabled = true;
    document.getElementById("display-reset-status").textContent =
      "Previous display preferences restored. Pinned favorites and My view are unchanged.";
    if (wasPaused && !settings.pauseRefresh &&
        typeof window.trisDashboardResumeRefresh === "function") {
      window.trisDashboardResumeRefresh();
    } else if (settings.pauseRefresh &&
               typeof window.trisDashboardCancelPendingRetry === "function") {
      window.trisDashboardCancelPendingRetry();
    }
  });

  buildControls(); restore(); restorePins(); buildPinButtons(); apply();
  savedVisible = readSavedView(); updateSavedView();
}());
