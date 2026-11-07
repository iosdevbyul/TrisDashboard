(function () {
  "use strict";
  var clock = document.getElementById("clock");
  var date = document.getElementById("date");
  var connection = document.getElementById("connection");
  var indicator = document.getElementById("indicator");
  var lastCheck = document.getElementById("last-check");
  var offlineBanner = document.getElementById("offline-banner");
  var request = null;
  var overviewRequest = null;
  var wasOffline = false;
  var lastRequestStarted = 0;
  var lastDataStarted = 0;
  var requestSequence = 0;
  var overviewSequence = 0;
  var overviewRetryTimer = null;
  var consecutiveOverviewFailures = 0;

  function pad(number) { return number < 10 ? "0" + number : String(number); }
  function text(id, value) { document.getElementById(id).textContent = String(value); }

  function tick() {
    var now = new Date();
    clock.textContent = pad(now.getHours()) + ":" + pad(now.getMinutes());
    date.textContent = now.getFullYear() + "." + pad(now.getMonth() + 1) + "." + pad(now.getDate());
  }

  function get(url, callback, timeout) {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", url + (url.indexOf("?") === -1 ? "?" : "&") + "t=" + new Date().getTime(), true);
    xhr.timeout = timeout || 6000;
    var completed = false;
    function finish(online) {
      if (completed) { return; }
      completed = true;
      callback(online, xhr);
    }
    xhr.onreadystatechange = function () {
      if (xhr.readyState === 4) { finish(xhr.status === 200); }
    };
    xhr.onerror = function () { finish(false); };
    xhr.ontimeout = function () { finish(false); };
    try { xhr.send(); } catch (error) { finish(false); }
    return xhr;
  }

  function setConnection(online) {
    if (online) {
      offlineBanner.hidden = true;
      connection.textContent = "Server online";
      text("glance-connection", "Online");
      indicator.className = "indicator online";
      lastCheck.textContent = "Checked " + pad(new Date().getHours()) + ":" + pad(new Date().getMinutes());
      if (wasOffline) {
        wasOffline = false;
        loadOverview(true);
      }
    } else {
      wasOffline = true;
      offlineBanner.hidden = false;
      connection.textContent = "Server offline";
      text("glance-connection", "Offline");
      indicator.className = "indicator offline";
      lastCheck.textContent = "Reconnect automatically every 15 seconds";
    }
  }

  function checkServer() {
    var now = new Date().getTime();
    if (now - lastRequestStarted < 2000) { return; }
    lastRequestStarted = now;
    var sequence = ++requestSequence;
    if (request && request.readyState !== 4) { request.abort(); }
    request = get("/healthz", function (online) {
      if (sequence === requestSequence) { setConnection(online); }
    });
  }

  function statusText(info) {
    if (!info || !info.available) { return "Unavailable"; }
    return info.stale ? "Last known data (stale)" : "Updated " + (info.updated_at ? info.updated_at.replace("T", " ").slice(0, 16) + " UTC" : "recently");
  }

  function showSummary(payload) {
    var names = ["weather", "github", "trello", "portfolio", "fitness"];
    var active = 0;
    var unavailable = 0;
    var stale = 0;
    for (var i = 0; i < names.length; i++) {
      var info = payload[names[i]];
      if (info && info.available) {
        active++;
        if (info.stale) { stale++; }
      } else if (info && info.configured) {
        unavailable++;
      }
    }
    text("glance-sources", active + "/5 ready" +
      (stale ? " · " + stale + " stale" : "") +
      (unavailable ? " · " + unavailable + " unavailable" : ""));
    var now = new Date();
    text("glance-updated", pad(now.getHours()) + ":" + pad(now.getMinutes()));
  }

  function showPortfolio(info) {
    var list = document.getElementById("portfolio-list");
    while (list.firstChild) { list.removeChild(list.firstChild); }
    if (!info || !info.available) {
      text("portfolio-summary", "Not available");
      text("portfolio-updated", info && info.configured ? "Check MacBook snapshot" : "Configure on MacBook");
      return;
    }
    var positions = info.positions || [];
    text("portfolio-summary", positions.length + " holdings");
    for (var i = 0; i < positions.length; i++) {
      var item = positions[i];
      var row = document.createElement("div");
      row.className = "repo-row";
      row.textContent = item.symbol + " · " + item.quantity + " shares" +
        (item.market_value !== null ? " · " + item.market_value + " " + item.currency : " · price unavailable");
      list.appendChild(row);
    }
    var totals = info.totals || {};
    var keys = Object.keys(totals);
    if (keys.length) {
      var total = document.createElement("div");
      total.className = "portfolio-total";
      var parts = [];
      for (var j = 0; j < keys.length; j++) { parts.push(keys[j] + " " + totals[keys[j]]); }
      total.textContent = "Values: " + parts.join(" / ") + (info.valuation_complete ? "" : " (partial)");
      list.appendChild(total);
    }
    var quality = info.quality || {};
    text("portfolio-updated", "Manual prices · Snapshot " + info.as_of.replace("T", " ").slice(0, 16) +
      (quality.outdated ? " · OUTDATED (older than " + quality.threshold_hours + "h)" : ""));
  }

  function showDividends(info) {
    var list = document.getElementById("dividend-list");
    while (list.firstChild) { list.removeChild(list.firstChild); }
    if (!info || !info.available) {
      text("dividend-summary", info && info.configured ? "Unavailable" : "Not configured");
      text("dividend-updated", "Local confirmed-payment file");
      return;
    }
    var totals = info.monthly_totals || {};
    var currencies = Object.keys(totals);
    var label = [];
    for (var i = 0; i < currencies.length; i++) {
      label.push(currencies[i] + " " + totals[currencies[i]]);
    }
    text("dividend-summary", label.length ? label.join(" / ") : "No recorded payments this month");
    var payments = info.recent || [];
    for (var j = 0; j < payments.length; j++) {
      var row = document.createElement("div");
      row.className = "repo-row";
      row.textContent = payments[j].paid_on + " · " + payments[j].symbol +
        " · " + payments[j].amount + " " + payments[j].currency;
      list.appendChild(row);
    }
    text("dividend-updated", "Manual confirmed payments · " + info.month);
  }

  function showAgenda(info) {
    var list = document.getElementById("agenda-list");
    while (list.firstChild) { list.removeChild(list.firstChild); }
    if (!info || !info.available) {
      text("agenda-summary", info && info.configured ? "Unavailable" : "Not configured");
      text("agenda-updated", info && info.configured ? "Check local agenda file" : "Configure on MacBook");
      return;
    }
    text("agenda-summary", info.upcoming_count + " upcoming events");
    var events = info.events || [];
    for (var i = 0; i < events.length; i++) {
      var row = document.createElement("div");
      row.className = "agenda-row";
      row.textContent = events[i].date + (events[i].time ? " " + events[i].time : "") + " · " + events[i].title;
      list.appendChild(row);
    }
    text("agenda-updated", "Local calendar · " + info.window_start + " to " + info.window_end);
  }

  function showFitness(info) {
    var list = document.getElementById("fitness-list");
    while (list.firstChild) { list.removeChild(list.firstChild); }
    if (!info || !info.available) {
      text("fitness-summary", info && info.configured ? "Unavailable" : "Not configured");
      text("fitness-updated", info && info.configured ? "Check MacBook workout file" : "Configure on MacBook");
      return;
    }
    var summary = info.summary;
    text("fitness-summary", summary.sessions + " sessions · " + summary.duration_minutes + " min");
    var total = document.createElement("div");
    total.textContent = "Distance " + summary.distance_km + " km · " + info.period_start + " to " + info.period_end;
    list.appendChild(total);
    var recent = info.recent || [];
    for (var i = 0; i < recent.length; i++) {
      var row = document.createElement("div");
      row.className = "repo-row";
      row.textContent = recent[i].date + " · " + recent[i].type + " · " + recent[i].duration_minutes + " min";
      list.appendChild(row);
    }
    text("fitness-updated", "Local export · Refreshes on page data update");
  }

  function showWeather(info) {
    if (!info || !info.available) {
      text("weather-temp", "Unavailable");
      text("weather-details", "No weather data yet");
    } else {
      text("weather-temp", info.temperature_c + " °C");
      var details = info.location + " · Humidity " + info.humidity_percent + "%";
      if (info.feels_like_c !== null && typeof info.feels_like_c !== "undefined") {
        details += " · Feels " + info.feels_like_c + " °C";
      }
      if (info.today_high_c !== null && typeof info.today_high_c !== "undefined") {
        details += " · High " + info.today_high_c + " °C";
      }
      if (info.today_low_c !== null && typeof info.today_low_c !== "undefined") {
        details += " / Low " + info.today_low_c + " °C";
      }
      if (info.rain_chance_percent !== null && typeof info.rain_chance_percent !== "undefined") {
        details += " · Rain " + info.rain_chance_percent + "%";
      }
      text("weather-details", details);
    }
    text("weather-updated", statusText(info));
  }

  function showGithub(info) {
    var list = document.getElementById("github-list");
    while (list.firstChild) { list.removeChild(list.firstChild); }
    if (!info || !info.available) {
      text("github-summary", "Unavailable");
      text("github-updated", statusText(info));
      return;
    }
    var repos = info.repositories || [];
    var total = 0;
    for (var i = 0; i < repos.length; i++) {
      if (!repos[i].available) {
        var failed = document.createElement("div");
        failed.className = "repo-row";
        failed.textContent = repos[i].repository + " · Unavailable";
        list.appendChild(failed);
        continue;
      }
      total += repos[i].open_pr_count;
      var row = document.createElement("div");
      row.className = "repo-row";
      var ci = repos[i].latest_ci;
      var ciText = "CI unknown";
      if (ci) {
        ciText = ci.status === "completed" ? "CI " + (ci.conclusion || "unknown") : "CI " + ci.status;
      } else {
        ciText = "No workflow runs";
      }
      row.textContent = repos[i].repository + " · " + repos[i].open_pr_count +
        (repos[i].open_pr_count_truncated ? "+ open PRs" : " open PRs") + " · " + ciText;
      list.appendChild(row);
      var previews = repos[i].open_prs || [];
      for (var k = 0; k < previews.length; k++) {
        if (typeof previews[k].url === "string" &&
            previews[k].url.indexOf("https://github.com/") === 0) {
          var link = document.createElement("a");
          link.className = "github-pr-link";
          link.href = previews[k].url;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = "#" + previews[k].number + " " + previews[k].title;
          list.appendChild(link);
        }
      }
    }
    text("github-summary", total + (info.partial ? "+ known open PRs" : " open PRs"));
    text("github-updated", statusText(info));
  }

  function showTrello(info) {
    var list = document.getElementById("trello-list");
    while (list.firstChild) { list.removeChild(list.firstChild); }
    if (!info || !info.available) {
      text("trello-summary", info && info.configured ? "Unavailable" : "Not configured");
      text("trello-updated", info && info.configured ? "Board temporarily unavailable" : "Configure on MacBook");
      return;
    }
    var columns = info.lists || [];
    var total = 0;
    for (var i = 0; i < columns.length; i++) {
      total += columns[i].count;
      var row = document.createElement("div");
      row.className = "repo-row";
      row.textContent = columns[i].name + " · " + columns[i].count + " cards";
      list.appendChild(row);
      var names = columns[i].cards || [];
      if (names.length) {
        var preview = document.createElement("div");
        preview.className = "trello-preview";
        preview.textContent = names.join(" / ");
        list.appendChild(preview);
      }
    }
    text("trello-summary", total + " cards");
    text("trello-updated", statusText(info));
  }

  function showServer(info) {
    if (!info || !info.available) {
      text("server-uptime", "Unavailable");
      text("server-info", "No diagnostics received");
      return;
    }
    var totalMinutes = Math.floor(info.uptime_seconds / 60);
    var days = Math.floor(totalMinutes / 1440);
    var hours = Math.floor((totalMinutes % 1440) / 60);
    var minutes = totalMinutes % 60;
    var uptime = days ? days + "d " + hours + "h" : hours ? hours + "h " + minutes + "m" : minutes + "m";
    text("server-uptime", uptime + " online");
    text("server-info", "MacBook local API reachable");
    text("server-updated", "Server clock: " + String(info.server_time_utc || "").replace("T", " ").slice(0, 16) + " UTC");
  }

  function clearOverviewRetry() {
    if (overviewRetryTimer !== null) {
      clearTimeout(overviewRetryTimer);
      overviewRetryTimer = null;
    }
  }

  function retryOverview() {
    consecutiveOverviewFailures += 1;
    text("glance-updated", "Refresh failed · retry scheduled");
    text("data-refresh-state", "Data refresh failed. Last successful values retained.");
    clearOverviewRetry();
    // A bounded backoff prevents hammering an unavailable MacBook.
    var delays = [30000, 60000, 120000, 180000];
    var delay = delays[Math.min(consecutiveOverviewFailures - 1, delays.length - 1)];
    overviewRetryTimer = setTimeout(function () {
      overviewRetryTimer = null;
      if (!document.hidden) { loadOverview(true); }
    }, delay);
  }

  function loadOverview(force) {
    var now = new Date().getTime();
    if (!force && now - lastDataStarted < 30000) { return; }
    lastDataStarted = now;
    clearOverviewRetry();
    var sequence = ++overviewSequence;
    if (overviewRequest && overviewRequest.readyState !== 4) { overviewRequest.abort(); }
    overviewRequest = get("/api/overview", function (ok, xhr) {
      if (sequence !== overviewSequence) { return; }
      if (!ok) { retryOverview(); return; }
      try {
        var payload = JSON.parse(xhr.responseText);
        if (!payload || typeof payload !== "object" || !payload.server || !payload.weather || !payload.github) {
          throw new Error("Unexpected overview response");
        }
        consecutiveOverviewFailures = 0;
        text("data-refresh-state", "Last overview refresh succeeded.");
        showGithub(payload.github);
        showWeather(payload.weather);
        showTrello(payload.trello);
        showServer(payload.server);
        showPortfolio(payload.portfolio);
        showFitness(payload.fitness);
        showDividends(payload.dividends);
        showAgenda(payload.agenda);
        showSummary(payload);
      } catch (error) {
        text("weather-updated", "Invalid server response");
        text("github-updated", "Invalid server response");
        retryOverview();
      }
    }, 10000);
  }

  tick();
  checkServer();
  loadOverview(true);
  setInterval(tick, 1000);
  setInterval(checkServer, 15000);
  setInterval(loadOverview, 180000);
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) { tick(); checkServer(); loadOverview(true); } else { clearOverviewRetry(); }
  });
}());
