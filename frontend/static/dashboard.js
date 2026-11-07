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

  function pad(number) { return number < 10 ? "0" + number : String(number); }
  function text(id, value) { document.getElementById(id).textContent = String(value); }

  function tick() {
    var now = new Date();
    clock.textContent = pad(now.getHours()) + ":" + pad(now.getMinutes());
    date.textContent = now.getFullYear() + "." + pad(now.getMonth() + 1) + "." + pad(now.getDate());
  }

  function get(url, callback) {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", url + (url.indexOf("?") === -1 ? "?" : "&") + "t=" + new Date().getTime(), true);
    xhr.timeout = 6000;
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

  function showWeather(info) {
    if (!info || !info.available) {
      text("weather-temp", "Unavailable");
      text("weather-details", "No weather data yet");
    } else {
      text("weather-temp", info.temperature_c + " °C");
      text("weather-details", info.location + " · Humidity " + info.humidity_percent + "%");
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
    }
    text("github-summary", total + " open PRs");
    text("github-updated", statusText(info));
  }

  function loadOverview(force) {
    var now = new Date().getTime();
    if (!force && now - lastDataStarted < 30000) { return; }
    lastDataStarted = now;
    if (overviewRequest && overviewRequest.readyState !== 4) { overviewRequest.abort(); }
    overviewRequest = get("/api/overview", function (ok, xhr) {
      if (!ok) { return; }
      try {
        var payload = JSON.parse(xhr.responseText);
        showGithub(payload.github);
        showWeather(payload.weather);
      } catch (error) {
        text("weather-updated", "Invalid server response");
        text("github-updated", "Invalid server response");
      }
    });
  }

  tick();
  checkServer();
  loadOverview(true);
  setInterval(tick, 1000);
  setInterval(checkServer, 15000);
  setInterval(loadOverview, 180000);
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) { tick(); checkServer(); loadOverview(true); }
  });
}());
