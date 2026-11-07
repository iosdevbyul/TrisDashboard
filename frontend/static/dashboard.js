(function () {
  "use strict";
  var clock = document.getElementById("clock");
  var date = document.getElementById("date");
  var connection = document.getElementById("connection");
  var indicator = document.getElementById("indicator");
  var lastCheck = document.getElementById("last-check");
  var offlineBanner = document.getElementById("offline-banner");
  var request = null;
  var consecutiveFailures = 0;
  var wasOffline = false;
  var lastRequestStarted = 0;
  var requestSequence = 0;

  function pad(number) { return number < 10 ? "0" + number : String(number); }

  function tick() {
    var now = new Date();
    clock.textContent = pad(now.getHours()) + ":" + pad(now.getMinutes());
    date.textContent = now.getFullYear() + "." + pad(now.getMonth() + 1) + "." + pad(now.getDate());
  }

  function setConnection(online) {
    if (online) {
      consecutiveFailures = 0;
      offlineBanner.hidden = true;
      connection.textContent = "Server online";
      indicator.className = "indicator online";
      lastCheck.textContent = "Checked " + pad(new Date().getHours()) + ":" + pad(new Date().getMinutes());
      if (wasOffline) {
        wasOffline = false;
        // Recover server-rendered assets that might have changed during an outage.
        window.location.reload();
      }
    } else {
      consecutiveFailures += 1;
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
    if (request && request.readyState !== 4) { request.abort(); }
    var xhr = new XMLHttpRequest();
    var sequence = ++requestSequence;
    var completed = false;
    request = xhr;

    function complete(online) {
      if (completed || sequence !== requestSequence) { return; }
      completed = true;
      setConnection(online);
    }

    xhr.open("GET", "/healthz?t=" + now, true);
    xhr.timeout = 5000;
    xhr.onreadystatechange = function () {
      if (xhr.readyState === 4) { complete(xhr.status === 200); }
    };
    xhr.onerror = function () { complete(false); };
    xhr.ontimeout = function () { complete(false); };
    try { xhr.send(); } catch (error) { complete(false); }
  }

  tick();
  checkServer();
  setInterval(tick, 1000);
  setInterval(checkServer, 15000);
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) { tick(); checkServer(); }
  });
}());
