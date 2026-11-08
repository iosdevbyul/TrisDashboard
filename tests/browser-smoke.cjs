// Deterministic, network-free JavaScript smoke test for the dashboard's DOM contract.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const root = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(root, "frontend/index.html"), "utf8");
const elements = new Map();
const handlers = {};
const paths = [];
const scheduled = [];
const periodic = [];
let overviewStatus = 200;
let overviewBody = null;
let healthBody = null;
let clockOffset = 0;
class TestDate extends Date {
  constructor(...args) { super(...(args.length ? args : [Date.now() + clockOffset])); }
}

function element(id = "") {
  const children = [];
  const result = {
    id, checked: false, hidden: false, textContent: "", className: "",
    children, attributes: {}, href: "",
    get firstChild() { return children.length ? children[0] : null; },
    appendChild(child) { children.push(child); return child; },
    removeChild(child) {
      const index = children.indexOf(child);
      if (index >= 0) children.splice(index, 1);
    },
    addEventListener(name, callback) { handlers[id + ":" + name] = callback; },
    setAttribute(name, value) { this.attributes[name] = value; }
  };
  return result;
}

function byId(id) {
  if (!elements.has(id)) {
    assert.ok(html.includes('id="' + id + '"') || id.startsWith("toggle-") || id.startsWith("panel-"),
      "Missing HTML element: " + id);
    elements.set(id, element(id));
  }
  return elements.get(id);
}

const response = {
  weather: { available: true, temperature_c: 22, location: "Test City", humidity_percent: 40 },
  github: { available: true, repositories: [] },
  trello: { available: false, configured: false },
  portfolio: { available: false, configured: false },
  dividends: { available: false, configured: false },
  fitness: { available: false, configured: false },
  agenda: { available: false, configured: false },
  server: { available: true, uptime_seconds: 1800, server_time_utc: "2026-11-08T00:00:00+00:00" }
};

const document = {
  body: element("body"), hidden: false,
  getElementById: byId,
  querySelector(selector) {
    const match = selector.match(/^\[data-panel="([^"]+)"\]$/);
    if (!match) return null;
    assert.ok(html.includes('data-panel="' + match[1] + '"'));
    return byId("panel-" + match[1]);
  },
  createElement: (name) => element(name),
  createTextNode: (value) => ({ textContent: value }),
  addEventListener: (name, callback) => { handlers["document:" + name] = callback; }
};

class XMLHttpRequest {
  open(method, url) { this.url = url; }
  send() {
    paths.push(this.url);
    const isOverview = this.url.startsWith("/api/overview");
    this.status = isOverview ? overviewStatus : 200;
    this.readyState = 4;
    this.responseText = isOverview && overviewBody !== null
      ? overviewBody
      : (isOverview ? JSON.stringify(response) : (healthBody === null ? '{"status":"ok"}' : healthBody));
    if (this.onreadystatechange) this.onreadystatechange();
  }
  abort() { this.readyState = 4; }
}

const state = {};
const window = {
  localStorage: {
    getItem: () => null,
    setItem: (key, value) => { state[key] = value; }
  },
  location: { reload() { paths.push("reload"); } }
};

const context = vm.createContext({
  document, window, XMLHttpRequest, Date: TestDate, JSON, Object, Math, String,
  setInterval: (callback, delay) => { periodic.push({callback, delay}); return periodic.length; },
  setTimeout: (callback, delay) => {
    scheduled.push({ callback, delay, cancelled: false });
    return scheduled.length;
  },
  clearTimeout: (id) => {
    if (scheduled[id - 1]) scheduled[id - 1].cancelled = true;
  }
});
vm.runInContext(fs.readFileSync(path.join(root, "frontend/static/dashboard.js"), "utf8"),
  context, {timeout: 1500});
vm.runInContext(fs.readFileSync(path.join(root, "frontend/static/preferences.js"), "utf8"),
  context, {timeout: 1500});

assert.ok(paths.some((url) => url.startsWith("/healthz")));
assert.ok(paths.some((url) => url.startsWith("/api/overview")));
assert.equal(byId("weather-temp").textContent, "22 °C");
response.weather.weather_code = 2;
handlers["document:visibilitychange"]();
assert.match(byId("weather-details").textContent, /Partly cloudy/);
assert.equal(byId("connection").textContent, "Server online");
assert.match(byId("glance-sources").textContent, /2\/8 ready/);
assert.equal(byId("server-uptime").textContent, "30m online");
assert.ok(byId("panel-visibility").children.length >= 8);

handlers["focus-panels:click"]();
assert.equal(byId("panel-weather").hidden, true);
assert.equal(byId("panel-portfolio").hidden, false);
assert.equal(byId("panel-github").hidden, false);
assert.equal(byId("panel-fitness").hidden, false);
handlers["show-all-panels:click"]();
assert.equal(byId("panel-weather").hidden, false);

byId("setting-compact").checked = true;
handlers["setting-compact:change"].call(byId("setting-compact"));
assert.match(document.body.className, /compact/);
assert.ok(state["tris.dashboard.display.v1"]);
const beforeRefresh = paths.filter((url) => url.startsWith("/api/overview")).length;
handlers["refresh-button:click"]();
assert.equal(paths.filter((url) => url.startsWith("/api/overview")).length, beforeRefresh + 1);
assert.equal(paths.includes("reload"), false);

// Backgrounded iPad Safari must not send periodic health or overview requests.
const beforeHiddenPoll = paths.length;
document.hidden = true;
periodic.find((item) => item.delay === 15000).callback();
periodic.find((item) => item.delay === 180000).callback();
assert.equal(paths.length, beforeHiddenPoll);
document.hidden = false;

// API failure must retain the last rendered values and schedule a bounded retry.
const priorWeather = byId("weather-temp").textContent;
overviewStatus = 503;
handlers["document:visibilitychange"]();
assert.equal(byId("weather-temp").textContent, priorWeather);
assert.match(byId("data-refresh-state").textContent, /failed/i);
assert.match(byId("data-refresh-state").textContent, /Last successful update at \d\d:\d\d/);
const retry = scheduled.find((item) => item.delay === 30000 && !item.cancelled);
assert.ok(retry, "First failed overview should retry after 30 seconds");

// On successful retry, the quote and partial valuation cards must render safely.
overviewStatus = 200;
response.portfolio = {
  available: true, as_of: "2026-11-08T00:00:00+00:00",
  positions: [{ symbol: "JEPQ", currency: "USD", quantity: "3",
                market_value: null, price: null }],
  totals: {}, valuation_complete: false, quality: { outdated: false }
};
response.quotes = {
  available: true, provider: "Twelve Data", quotes: [
    { symbol: "JEPQ", currency: "USD", price: "50.25",
      reported_at_utc: "2026-11-08T00:00:00+00:00", outdated: false }
  ]
};
response.valuation = {
  available: true, matched_count: 1, position_count: 1,
  partial: false, totals: { USD: "150.75" }, stale: false
};
retry.callback();
assert.equal(byId("quotes-summary").textContent, "1/1 quotes reported");
assert.match(byId("portfolio-quote-values").textContent, /USD 150.75/);
assert.match(byId("portfolio-quote-values").textContent, /Not guaranteed live/);
assert.match(byId("glance-sources").textContent, /4\/8 ready/);
assert.match(byId("data-refresh-state").textContent, /succeeded at \d\d:\d\d/i);

// A 20-result GitHub API page is only a lower bound, not an exact PR count.
response.github = { available: true, repositories: [{
  repository: "owner/busy", available: true, open_pr_count: 20,
  open_pr_count_truncated: true, open_prs: [], latest_ci: null
}] };
handlers["document:visibilitychange"]();
assert.match(byId("github-summary").textContent, /20\+ known open PRs/);
assert.match(byId("github-list").children[0].textContent, /20\+ open PRs/);

// Invalid response JSON must not erase the previous successful market display.
overviewBody = "{invalid-json";
handlers["document:visibilitychange"]();
assert.match(byId("data-refresh-state").textContent, /failed/i);
assert.equal(byId("quotes-summary").textContent, "1/1 quotes reported");
assert.match(byId("portfolio-quote-values").textContent, /USD 150.75/);

// An HTTP 200 with an invalid health payload is not an online server.
healthBody = '{"status":"not-ready"}';
clockOffset += 3000;
handlers["document:visibilitychange"]();
assert.equal(byId("connection").textContent, "Server offline");
healthBody = '{"status":"ok"}';
clockOffset += 3000;
handlers["document:visibilitychange"]();
assert.equal(byId("connection").textContent, "Server online");

console.log("Frontend success, retry, quote display and invalid-data smoke tests passed.");
