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
    id, checked: false, hidden: false, textContent: "", className: "", style: {},
    children, attributes: {}, href: "",
    get firstChild() { return children.length ? children[0] : null; },
    appendChild(child) { const old = children.indexOf(child); if (old >= 0) children.splice(old, 1); children.push(child); return child; },
    removeChild(child) {
      const index = children.indexOf(child);
      if (index >= 0) children.splice(index, 1);
    },
    addEventListener(name, callback) { handlers[this.id + ":" + name] = callback; },
    setAttribute(name, value) { this.attributes[name] = value; },
    focus() { this.focused = true; }
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
  quotes: { available: false, configured: false },
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
vm.runInContext(fs.readFileSync(path.join(root, "frontend/static/preferences.js"), "utf8"),
  context, {timeout: 1500});
vm.runInContext(fs.readFileSync(path.join(root, "frontend/static/dashboard.js"), "utf8"),
  context, {timeout: 1500});

assert.ok(paths.some((url) => url.startsWith("/healthz")));
assert.ok(paths.some((url) => url.startsWith("/api/overview")));
assert.equal(byId("weather-temp").textContent, "22 °C");
handlers["weather-unit-button:click"]();
assert.equal(byId("weather-temp").textContent, "71.6 °F");
assert.equal(state["tris.dashboard.weather.fahrenheit"], "true");
handlers["weather-unit-button:click"]();
assert.equal(byId("weather-temp").textContent, "22 °C");

response.weather.weather_code = 2;
handlers["document:visibilitychange"]();
assert.match(byId("weather-details").textContent, /Partly cloudy/);
response.weather.wind_kmh = 12;
handlers["document:visibilitychange"]();
assert.match(byId("weather-details").textContent, /Wind 12 km\/h/);
response.weather.humidity_percent = 180;
response.weather.rain_chance_percent = -1;
response.weather.today_high_c = "invalid";
handlers["document:visibilitychange"]();
assert.match(byId("weather-details").textContent, /Humidity unavailable/);
assert.doesNotMatch(byId("weather-details").textContent, /Rain -1|High invalid/);
response.weather.humidity_percent = 40;
response.weather.rain_chance_percent = null;
response.weather.today_high_c = null;
assert.equal(byId("connection").textContent, "Server online");
assert.match(byId("glance-sources").textContent, /2\/8 ready/);
assert.equal(byId("server-uptime").textContent, "30m online");
response.server.uptime_seconds = null;
handlers["document:visibilitychange"]();
assert.equal(byId("server-uptime").textContent, "Uptime unavailable");
response.server.uptime_seconds = 1800;
assert.ok(byId("panel-visibility").children.length >= 8);
const moduleContainer = byId("dashboard-modules");
const initialOrder = moduleContainer.children.map((card) => card.id);
assert.equal(new Set(initialOrder).size, 9);
handlers["panel-up-fitness:click"]();
assert.equal(moduleContainer.children[moduleContainer.children.length - 2].id, "panel-fitness");
assert.match(state["tris.dashboard.display.v1"], /"order":\[/);
handlers["panel-down-fitness:click"]();
assert.equal(moduleContainer.children[moduleContainer.children.length - 1].id, "panel-fitness");
assert.equal(new Set(moduleContainer.children).size, 9);

byId("display-settings").hidden = true;
handlers["settings-button:click"].call(byId("settings-button"));
assert.equal(byId("display-settings").hidden, false);
handlers["document:keydown"]({keyCode: 27});
assert.equal(byId("display-settings").hidden, true);
assert.equal(byId("settings-button").attributes["aria-expanded"], "false");
assert.equal(byId("settings-button").focused, true);
byId("settings-button").focused = false;
handlers["settings-button:click"].call(byId("settings-button"));
handlers["close-display-settings:click"]();
assert.equal(byId("settings-button").focused, true);

handlers["focus-panels:click"]();
assert.equal(byId("panel-weather").hidden, true);
assert.equal(byId("panel-portfolio").hidden, false);
assert.equal(byId("panel-github").hidden, false);
assert.equal(byId("panel-fitness").hidden, false);
handlers["minimal-panels:click"]();
assert.equal(byId("panel-weather").hidden, false);
assert.equal(byId("panel-agenda").hidden, false);
assert.equal(byId("panel-server").hidden, false);
assert.equal(byId("panel-portfolio").hidden, true);
handlers["show-all-panels:click"]();
assert.equal(byId("panel-weather").hidden, false);
assert.equal(byId("panel-portfolio").hidden, false);

// Resetting saved paused state also restarts the dashboard immediately.
byId("setting-pause-refresh").checked = true;
handlers["setting-pause-refresh:change"].call(byId("setting-pause-refresh"));
const beforeResetRefresh = paths.filter((url) => url.startsWith("/api/overview")).length;
handlers["reset-settings:click"]();
assert.equal(window.trisDashboardRefreshPaused, false);
assert.equal(paths.filter((url) => url.startsWith("/api/overview")).length, beforeResetRefresh + 1);

byId("setting-pause-refresh").checked = true;
handlers["setting-pause-refresh:change"].call(byId("setting-pause-refresh"));
assert.equal(window.trisDashboardRefreshPaused, true);
assert.match(byId("refresh-cadence").textContent, /paused/);
const beforePausedForeground = paths.filter((url) => url.startsWith("/api/overview")).length;
handlers["document:visibilitychange"]();
assert.equal(paths.filter((url) => url.startsWith("/api/overview")).length, beforePausedForeground,
  "Foregrounding Safari while paused must not fetch an overview");
clockOffset += 11 * 60000;
const beforePaused = paths.filter((url) => url.startsWith("/api/overview")).length;
periodic.find((entry) => entry.delay === 60000).callback();
assert.equal(paths.filter((url) => url.startsWith("/api/overview")).length, beforePaused);
assert.match(byId("data-refresh-state").textContent, /11 min ago/);
handlers["refresh-button:click"]();
assert.equal(paths.filter((url) => url.startsWith("/api/overview")).length, beforePaused + 1);
byId("setting-pause-refresh").checked = false;
const beforeResume = paths.filter((url) => url.startsWith("/api/overview")).length;
handlers["setting-pause-refresh:change"].call(byId("setting-pause-refresh"));
assert.equal(paths.filter((url) => url.startsWith("/api/overview")).length, beforeResume + 1);
assert.equal(window.trisDashboardRefreshPaused, false);
assert.match(byId("refresh-cadence").textContent, /every 3 minutes/);

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
periodic.find((item) => item.delay === 60000).callback();
assert.equal(paths.length, beforeHiddenPoll);
document.hidden = false;

// Users can adjust the auto-refresh cadence without reloading the page.
byId("setting-refresh-minutes").value = "10";
handlers["setting-refresh-minutes:change"].call(byId("setting-refresh-minutes"));
assert.equal(window.trisDashboardRefreshMinutes, 10);
assert.match(byId("refresh-cadence").textContent, /10 minutes/);
const beforeCadence = paths.filter((url) => url.startsWith("/api/overview")).length;
clockOffset += 6 * 60000;
periodic.find((item) => item.delay === 60000).callback();
assert.equal(paths.filter((url) => url.startsWith("/api/overview")).length, beforeCadence);
clockOffset += 5 * 60000;
periodic.find((item) => item.delay === 60000).callback();
assert.equal(paths.filter((url) => url.startsWith("/api/overview")).length, beforeCadence + 1);
byId("setting-refresh-minutes").value = "3";
handlers["setting-refresh-minutes:change"].call(byId("setting-refresh-minutes"));

// API failure must retain the last rendered values and schedule a bounded retry.
const priorWeather = byId("weather-temp").textContent;
overviewStatus = 503;
handlers["document:visibilitychange"]();
assert.equal(byId("weather-temp").textContent, priorWeather);
assert.match(byId("data-refresh-state").textContent, /failed/i);
assert.match(byId("data-refresh-state").textContent, /Last successful update at \d\d:\d\d/);
const retry = scheduled.find((item) => item.delay === 30000 && !item.cancelled);
assert.ok(retry, "First failed overview should retry after 30 seconds");
assert.match(byId("data-refresh-state").textContent, /retry in 30s/);
// Pausing an already scheduled retry immediately cancels its timer.
byId("setting-pause-refresh").checked = true;
handlers["setting-pause-refresh:change"].call(byId("setting-pause-refresh"));
assert.equal(retry.cancelled, true);
assert.match(byId("data-refresh-state").textContent, /Automatic refresh paused/);
byId("setting-pause-refresh").checked = false;
handlers["setting-pause-refresh:change"].call(byId("setting-pause-refresh"));
// A queued retry must respect pause changes even when its callback fires later.
byId("setting-pause-refresh").checked = true;
handlers["setting-pause-refresh:change"].call(byId("setting-pause-refresh"));
const beforePausedRetry = paths.filter((url) => url.startsWith("/api/overview")).length;
retry.callback();
assert.equal(paths.filter((url) => url.startsWith("/api/overview")).length, beforePausedRetry);
byId("setting-pause-refresh").checked = false;
handlers["setting-pause-refresh:change"].call(byId("setting-pause-refresh"));

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
      reported_at_utc: "2026-11-08T00:00:00+00:00", age_hours: 3.5, outdated: false }
  ]
};
response.valuation = {
  available: true, matched_count: 1, position_count: 1,
  partial: false, totals: { USD: "150.75" }, stale: false
};
retry.callback();
assert.match(byId("quotes-summary").textContent, /^1\/1 quotes reported · Oldest reading 3\.5h ago$/);
assert.match(byId("quotes-list").children[0].textContent, /3\.5h old/);
assert.match(byId("quotes-summary").textContent, /Oldest reading 3\.5h ago/);
response.quotes.quotes[0].outdated = true;
handlers["document:visibilitychange"]();
assert.match(byId("quotes-summary").textContent, /1 outdated/);
response.quotes.quotes[0].outdated = false;
assert.match(byId("portfolio-quote-values").textContent, /USD 150.75/);
assert.match(byId("portfolio-quote-values").textContent, /Not guaranteed live/);
assert.match(byId("glance-sources").textContent, /4\/8 ready/);
response.weather.stale = true;
response.trello = {available:false, configured:true};
handlers["document:visibilitychange"]();
assert.match(byId("source-health-details").textContent, /weather stale/);
response.weather.cache_age_seconds = 901;
handlers["document:visibilitychange"]();
assert.match(byId("weather-updated").textContent, /15 min old/);
response.weather.cache_age_seconds = undefined;
assert.match(byId("source-health-details").textContent, /trello unavailable/);
response.weather.stale = false;
response.trello = {available:false,configured:false};
assert.match(byId("data-refresh-state").textContent, /succeeded at \d\d:\d\d on \d{4}-\d\d-\d\d/i);

// Manual holdings allocation must render independent, bounded percentages.
response.portfolio = { available:true, as_of:"2026-11-08T00:00:00+00:00",
  positions:[{symbol:"JEPQ",quantity:"2",currency:"USD",market_value:"150",price:"75"},
             {symbol:"SCHD",quantity:"1",currency:"USD",market_value:"50",price:"50"}],
  currency_allocations:{USD:[{symbol:"JEPQ",percent:"75.0"},{symbol:"SCHD",percent:"25.0"}]},
  totals:{USD:"200"},valuation_complete:true,quality:{outdated:false}};
handlers["document:visibilitychange"]();
const assetBars = byId("portfolio-list").children.filter((row) => row.className === "allocation-row");
assert.equal(assetBars.length, 2);
assert.equal(assetBars[0].children[1].children[0].style.width, "75%");
assert.equal(assetBars[1].children[1].children[0].style.width, "25%");

// Fitness history count is distinct from the last-seven-day session count.
response.fitness = {
  available: true, summary: {sessions: 2, duration_minutes: 50, distance_km: 5},
  active_days: 2, total_history_count: 48,
  file_updated_utc: "2026-11-09T01:00:00+00:00",
  period_start: "2026-11-02", period_end: "2026-11-08",
  daily: [{date: "2026-11-07", sessions: 1, duration_minutes: 30, distance_km: 3},
          {date: "2026-11-08", sessions: 1, duration_minutes: 60, distance_km: 2}], recent: []
};
handlers["document:visibilitychange"]();
assert.match(byId("fitness-updated").textContent, /48 total recorded sessions/);
assert.match(byId("fitness-updated").textContent, /Local file updated/);
assert.match(byId("fitness-summary").textContent, /2 sessions/);
const bars = byId("fitness-list").children.find((child) => child.className === "workout-bars");
assert.ok(bars);
assert.equal(bars.children[0].children[1].children[0].style.width, "50%");
assert.equal(bars.children[1].children[1].children[0].style.width, "100%");

// Agenda can expand beyond the first eight entries without reloading Safari.
response.agenda = { available:true, window_start:"2026-11-09", window_end:"2026-11-23",
  upcoming_count:10, today_event_count:10, tomorrow_event_count:0,
  events:Array.from({length:10}, (_,i)=>({date:"2026-11-09",title:"Event "+i,time:""})) };
handlers["document:visibilitychange"]();
assert.equal(byId("agenda-toggle").hidden, false);
assert.equal(byId("agenda-list").children.length, 9);
handlers["agenda-toggle:click"]();
assert.equal(byId("agenda-list").children.length, 11);
assert.equal(byId("agenda-toggle").attributes["aria-expanded"], "true");
handlers["agenda-toggle:click"]();
assert.equal(byId("agenda-list").children.length, 9);

// Disclose the event preview cap without implying the whole agenda is visible.
response.agenda = {available:true,window_start:"2026-11-09",window_end:"2026-11-23",
  upcoming_count:45, events_truncated:true,
  events:Array.from({length:30}, (_,i) => ({date:"2026-11-10",title:"Event " + i,time:"09:00"}))};
handlers["document:visibilitychange"]();
assert.match(byId("agenda-updated").textContent, /First 30 of 45 events shown/);
assert.match(byId("agenda-toggle").textContent, /first 30 of 45/);
response.agenda = {available:false,configured:false};

// A 20-result GitHub API page is only a lower bound, not an exact PR count.
response.github = { available: true, repositories: [{
  repository: "owner/busy", available: true, open_pr_count: 20,
  open_pr_count_truncated: true, open_prs: [], latest_ci: null
}] };
handlers["document:visibilitychange"]();
assert.match(byId("github-summary").textContent, /20\+ known open PRs/);
assert.match(byId("github-list").children[0].textContent, /20\+ open PRs/);
assert.equal(byId("github-list").children[1].href, "https://github.com/owner/busy");
response.github.repositories[0].open_prs = [{number:42,title:"Safe PR",url:"https://github.com/malicious.example/bad"}];
handlers["document:visibilitychange"]();
assert.equal(byId("github-list").children[2].href, "https://github.com/owner/busy/pull/42");
response.github.repositories[0].open_prs = [{number:0,title:"Invalid PR",url:"https://github.com/owner/busy/pull/0"}];
handlers["document:visibilitychange"]();
assert.equal(byId("github-list").children.length, 2);
response.github.repositories[0].open_prs = [];
response.github.repositories[0].repository = "owner/evil?access_token=secret";
handlers["document:visibilitychange"]();
assert.equal(byId("github-list").children.length, 1);
response.github.repositories[0].repository = "owner/busy";

// Recorded dividend history is charted separately by currency.
response.dividends = {available:true,month:"2026-11",monthly_totals:{USD:"20"},
  six_month_totals:{USD:"30"},history:[
    {month:"2026-10",totals:{USD:"10"}},
    {month:"2026-11",totals:{USD:"20"}}],recent:[]};
handlers["document:visibilitychange"]();
const dividendChart = byId("dividend-list").children.find((child) => child.className === "dividend-bars");
assert.ok(dividendChart);
assert.equal(dividendChart.children[1].children[1].children[0].style.width, "50%");
assert.equal(dividendChart.children[2].children[1].children[0].style.width, "100%");

// Trello glance summary separates actionable work from completed cards.
response.trello = { available: true, lists: [
  { name: "Next", count: 3, cards: [] },
  { name: "In Progress", count: 1, cards: [] },
  { name: "Done", count: 12, cards: [] }
] };
handlers["document:visibilitychange"]();
assert.match(byId("trello-summary").textContent, /3 Next · 1 In Progress/);
assert.match(byId("trello-summary").textContent, /16 cards/);

// Invalid response JSON must not erase the previous successful market display.
overviewBody = "{invalid-json";
handlers["document:visibilitychange"]();
assert.match(byId("data-refresh-state").textContent, /failed/i);
assert.match(byId("quotes-summary").textContent, /^1\/1 quotes reported · Oldest reading 3\.5h ago$/);
assert.match(byId("portfolio-quote-values").textContent, /USD 150.75/);

// Missing a required source cannot count as a successful overview refresh.
overviewBody = null;
const savedQuotes = response.quotes;
delete response.quotes;
handlers["document:visibilitychange"]();
assert.match(byId("data-refresh-state").textContent, /failed/i);
response.quotes = savedQuotes;

// An incomplete manual snapshot should not block rendering other dashboard cards.
overviewBody = null;
response.portfolio = {available: true, positions: [
  {symbol: "JEPQ", quantity: "2", currency: "USD"}],
  quality: {outdated: false}};
handlers["document:visibilitychange"]();
assert.match(byId("data-refresh-state").textContent, /succeeded/i);
assert.match(byId("portfolio-updated").textContent, /time unavailable/);
assert.match(byId("portfolio-list").children[0].textContent, /price unavailable/);
response.portfolio = {available: false, configured: false};

// An HTTP 200 with an invalid health payload is not an online server.
healthBody = '{"status":"not-ready"}';
clockOffset += 3000;
handlers["document:visibilitychange"]();
assert.equal(byId("connection").textContent, "Server offline");
assert.match(byId("offline-banner").textContent, /Last successful update at \d\d:\d\d on \d{4}-\d\d-\d\d/);
healthBody = '{"status":"ok"}';
clockOffset += 3000;
handlers["document:visibilitychange"]();
assert.equal(byId("connection").textContent, "Server online");

byId("setting-high-contrast").checked = true;
handlers["setting-high-contrast:change"].call(byId("setting-high-contrast"));
assert.match(document.body.className, /high-contrast/);
assert.match(state["tris.dashboard.display.v1"], /"highContrast":true/);

byId("setting-large-text").checked = true;
handlers["setting-large-text:change"].call(byId("setting-large-text"));
assert.match(document.body.className, /large-text/);
assert.match(state["tris.dashboard.display.v1"], /"largeText":true/);

console.log("Frontend success, retry, quote display and invalid-data smoke tests passed.");
