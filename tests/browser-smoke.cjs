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
    this.status = 200;
    this.readyState = 4;
    this.responseText = JSON.stringify(this.url.startsWith("/api/overview") ? response : {status:"ok"});
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
  document, window, XMLHttpRequest, Date, JSON, Object, Math, String,
  setInterval: () => 1, setTimeout: () => 2, clearTimeout: () => {}
});
vm.runInContext(fs.readFileSync(path.join(root, "frontend/static/dashboard.js"), "utf8"),
  context, {timeout: 1500});
vm.runInContext(fs.readFileSync(path.join(root, "frontend/static/preferences.js"), "utf8"),
  context, {timeout: 1500});

assert.ok(paths.some((url) => url.startsWith("/healthz")));
assert.ok(paths.some((url) => url.startsWith("/api/overview")));
assert.equal(byId("weather-temp").textContent, "22 °C");
assert.equal(byId("connection").textContent, "Server online");
assert.match(byId("glance-sources").textContent, /2\/7 ready/);
assert.equal(byId("server-uptime").textContent, "30m online");
assert.ok(byId("panel-visibility").children.length >= 8);

byId("setting-compact").checked = true;
handlers["setting-compact:change"].call(byId("setting-compact"));
assert.match(document.body.className, /compact/);
assert.ok(state["tris.dashboard.display.v1"]);
handlers["refresh-button:click"]();
assert.ok(paths.includes("reload"));

console.log("Frontend JavaScript smoke test passed.");
