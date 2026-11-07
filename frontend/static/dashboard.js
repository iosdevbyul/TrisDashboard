(function () {
  "use strict";
  var clock = document.getElementById("clock");
  var date = document.getElementById("date");
  var connection = document.getElementById("connection");
  var indicator = document.getElementById("indicator");
  var request = null;

  function pad(number) { return number < 10 ? "0" + number : String(number); }

  function tick() {
    var now = new Date();
    clock.textContent = pad(now.getHours()) + ":" + pad(now.getMinutes());
    date.textContent = now.getFullYear() + "." + pad(now.getMonth() + 1) + "." + pad(now.getDate());
  }

  function setConnection(online) {
    connection.textContent = online ? "Server online" : "Server offline";
    indicator.className = "indicator " + (online ? "online" : "offline");
  }

  function checkServer() {
    if (request && request.readyState !== 4) { request.abort(); }
    var xhr = new XMLHttpRequest();
    request = xhr;
    xhr.open("GET", "/healthz?t=" + new Date().getTime(), true);
    xhr.timeout = 5000;
    xhr.onreadystatechange = function () {
      if (xhr.readyState === 4 && request === xhr) {
        setConnection(xhr.status === 200);
      }
    };
    xhr.onerror = function () { if (request === xhr) { setConnection(false); } };
    xhr.ontimeout = function () { if (request === xhr) { setConnection(false); } };
    xhr.send();
  }

  tick();
  checkServer();
  setInterval(tick, 1000);
  setInterval(checkServer, 15000);
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) { tick(); checkServer(); }
  });
}());
