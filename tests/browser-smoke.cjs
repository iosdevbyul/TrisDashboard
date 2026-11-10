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
let deferNextOverview = false;
let deferNextHealth = false;
const pendingHealthChecks = [];
const pendingOverviews = [];
class TestDate extends Date {
  constructor(...args) { super(...(args.length ? args : [Date.now() + clockOffset])); }
}

function element(id = "") {
  const children = [];
  const result = {
    id, value: "", checked: false, hidden: false, textContent: "", className: "", style: {},
    children, attributes: {}, href: "",
    get firstChild() { return children.length ? children[0] : null; },
    appendChild(child) { const old = children.indexOf(child); if (old >= 0) children.splice(old, 1); children.push(child); child.parentNode = this; if (child.id) elements.set(child.id, child); return child; },
    removeChild(child) {
      const index = children.indexOf(child);
      if (index >= 0) children.splice(index, 1);
      if (child.parentNode === this) { child.parentNode = null; }
    },
    addEventListener(name, callback) { handlers[this.id + ":" + name] = callback; },
    setAttribute(name, value) { this.attributes[name] = value; },
    focus() { this.focused = true; },
    select() { this.selected = true; }
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
    if (!isOverview && deferNextHealth) {
      deferNextHealth = false;
      this.readyState = 1;
      pendingHealthChecks.push(this);
      return;
    }
    if (isOverview && deferNextOverview) {
      deferNextOverview = false;
      this.readyState = 1;
      pendingOverviews.push(this);
      return;
    }
    this.status = isOverview ? overviewStatus : 200;
    this.readyState = 4;
    this.responseText = isOverview && overviewBody !== null
      ? overviewBody
      : (isOverview ? JSON.stringify(response) : (healthBody === null ? '{"status":"ok"}' : healthBody));
    if (this.onreadystatechange) this.onreadystatechange();
  }
  abort() { this.aborted = true; this.readyState = 4; }
}

const state = {};
const window = {
  localStorage: {
    getItem: (key) => Object.prototype.hasOwnProperty.call(state,key) ? state[key] : null,
    setItem: (key, value) => { state[key] = value; },
    removeItem: (key) => { delete state[key]; }
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
assert.equal(byId("panel-up-portfolio").disabled,true);
assert.equal(byId("panel-down-fitness").disabled,true);
assert.equal(byId("panel-up-fitness").disabled,false);
const jumpContainer = byId("priority-jumps");
assert.equal(jumpContainer.children.length,9);
const defaultJumpOrder = ["portfolio","quotes","dividends","agenda","github","weather","trello","server","fitness"].map(x => "jump-link-" + x);
assert.deepEqual(jumpContainer.children.map(x => x.id),defaultJumpOrder);
// Move a non-edge panel: both cards and shortcut links must move in lockstep.
handlers["panel-up-quotes:click"]();
assert.equal(moduleContainer.children[0].id,"panel-quotes");
assert.equal(jumpContainer.children[0].id,"jump-link-quotes");
assert.equal(byId("panel-up-quotes").disabled,true);
assert.equal(byId("panel-up-portfolio").disabled,false);
assert.match(byId("panel-order-status").textContent,/Moved quotes to position 1 of 9/);
assert.match(state["tris.dashboard.display.v1"],/"order":\["quotes","portfolio"/);
// Restore only the order, preserving unrelated display preferences and visibility.
handlers["reset-panel-order:click"]();
assert.deepEqual(moduleContainer.children.map(x=>x.id),initialOrder);
assert.deepEqual(jumpContainer.children.map(x=>x.id),defaultJumpOrder);
assert.equal(byId("panel-up-portfolio").disabled,true);
assert.equal(byId("panel-down-fitness").disabled,true);
assert.equal(byId("panel-order-status").textContent,"Default panel order restored");

byId("display-settings").hidden = true;
handlers["settings-button:click"].call(byId("settings-button"));
assert.equal(byId("display-settings").hidden, false);
assert.equal(byId("setting-compact").focused, true);
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
handlers["hide-all-panels:click"]();
assert.equal(byId("empty-panels").hidden, false);
handlers["show-all-panels:click"]();
assert.equal(byId("empty-panels").hidden, true);
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
assert.match(byId("data-refresh-state").textContent, /Automatic refresh paused/);
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
// Cancelled retry closures never refresh; resume with an explicit manual request.
retry.callback();
handlers["refresh-button:click"]();
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
assert.match(byId("source-health-details").textContent, /weather stale \(15 min old\)/);
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
assert.match(byId("github-summary").textContent,/20\+ known open PRs/);
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

// Newly exposed local summary metrics render without changing legacy layouts.
response.portfolio = {available: true, positions: [],
  price_coverage_by_currency: {USD: {priced: 1, total: 2}, KRW: {priced: 1, total: 1}},
  totals: {}, quality: {outdated: false}};
response.dividends = {available: true, month: "2026-11", monthly_totals: {},
  monthly_unique_paying_symbols: {USD: 2}, history: [], recent: []};
response.fitness = {available: true, summary: {sessions: 0, duration_minutes: 0, distance_km: 0},
  period_start: "2026-11-03", period_end: "2026-11-09", longest_rest_streak_days: 7,
  daily: [], recent: []};
response.agenda = {available: true, upcoming_count: 2,
  window_start: "2026-11-09", window_end: "2026-11-23",
  next_timed_event: {date: "2026-11-10", time: "09:30", title: "Standup"},
  events: []};
handlers["document:visibilitychange"]();
assert.ok(byId("portfolio-list").children.some((row) =>
  /Manual price coverage · USD 1\/2 holdings priced/.test(row.textContent)));
assert.ok(byId("dividend-list").children.some((row) =>
  /Distinct confirmed payers this month · USD 2 holdings/.test(row.textContent)));
assert.ok(byId("fitness-list").children.some((row) =>
  /Longest consecutive rest period \(last 7 days\) · 7 days/.test(row.textContent)));
assert.ok(byId("agenda-list").children.some((row) =>
  /Next timed event: Standup · 2026-11-10 09:30/.test(row.textContent)));

// Missing optional fields from an older API response never produce phantom rows.
delete response.portfolio.price_coverage_by_currency;
delete response.dividends.monthly_unique_paying_symbols;
delete response.fitness.longest_rest_streak_days;
delete response.agenda.next_timed_event;
handlers["document:visibilitychange"]();
assert.ok(!byId("portfolio-list").children.some((row) => /Manual price coverage/.test(row.textContent)));
assert.ok(!byId("dividend-list").children.some((row) => /Distinct confirmed payers/.test(row.textContent)));
assert.ok(!byId("fitness-list").children.some((row) => /Longest consecutive rest period/.test(row.textContent)));
assert.ok(!byId("agenda-list").children.some((row) => /Next timed event:/.test(row.textContent)));

// Actionable local insights use the optional API fields without requiring a new browser.
response.agenda = {available:true, upcoming_count:1, window_start:"2026-11-09",
  window_end:"2026-11-23", events:[],
  next_seven_daily_counts:[{date:"2026-11-09",events:1},{date:"2026-11-10",events:0}]};
response.fitness = {available:true,summary:{sessions:1,duration_minutes:20,distance_km:0},
  period_start:"2026-11-03",period_end:"2026-11-09",daily:[],recent:[],
  days_since_last_workout_in_week:2};
response.dividends = {available:true,month:"2026-11",monthly_totals:{},history:[],recent:[],
  last_confirmed_payment:{paid_on:"2026-11-04",symbol:"JEPQ",amount:"5",currency:"USD"}};
response.portfolio = {available:true,positions:[],totals:{},quality:{outdated:false},
  zero_quantity_symbols_by_currency:{USD:["SCHD"]}};
handlers["document:visibilitychange"]();
assert.ok(byId("agenda-list").children.some((row) => /Next 7 calendar days · 11-09 1 · 11-10 0/.test(row.textContent)));
assert.ok(byId("fitness-list").children.some((row) => /Last recorded workout \(7-day window\) · 2 days ago/.test(row.textContent)));
assert.ok(byId("dividend-list").children.some((row) => /Latest confirmed payment · 2026-11-04 · JEPQ · 5 USD/.test(row.textContent)));
assert.ok(byId("portfolio-list").children.some((row) => /Review zero-quantity positions · USD: SCHD/.test(row.textContent)));
delete response.agenda.next_seven_daily_counts;
delete response.fitness.days_since_last_workout_in_week;
delete response.dividends.last_confirmed_payment;
delete response.portfolio.zero_quantity_symbols_by_currency;
handlers["document:visibilitychange"]();
assert.ok(!byId("agenda-list").children.some((row) => /Next 7 calendar days/.test(row.textContent)));
assert.ok(!byId("fitness-list").children.some((row) => /Last recorded workout \(7-day window\)/.test(row.textContent)));
assert.ok(!byId("dividend-list").children.some((row) => /Latest confirmed payment/.test(row.textContent)));
assert.ok(!byId("portfolio-list").children.some((row) => /Review zero-quantity positions/.test(row.textContent)));

// Optional contextual statistics are additive and validated before display.
response.agenda = {available:true,upcoming_count:0,window_start:"2026-11-09",
  window_end:"2026-11-23",events:[],next_seven_free_days:7};
response.fitness = {available:true,summary:{sessions:0,duration_minutes:0,distance_km:0},
  period_start:"2026-11-03",period_end:"2026-11-09",daily:[],recent:[],
  ongoing_rest_streak_days:7};
response.dividends = {available:true,month:"2026-11",monthly_totals:{},
  history:[],recent:[],days_since_last_confirmed_payment:5};
response.portfolio = {available:true,positions:[],totals:{},quality:{outdated:false},
  price_coverage_percent_by_currency:{USD:50}};
handlers["document:visibilitychange"]();
assert.ok(byId("agenda-list").children.some((row) => /Days without scheduled events \(next 7\) · 7/.test(row.textContent)));
assert.ok(byId("fitness-list").children.some((row) => /Consecutive rest days through today \(7-day window\) · 7 days/.test(row.textContent)));
assert.ok(byId("dividend-list").children.some((row) => /Days since most recent confirmed payment · 5 days/.test(row.textContent)));
assert.ok(byId("portfolio-list").children.some((row) => /Manual price completeness · USD 50%/.test(row.textContent)));
delete response.agenda.next_seven_free_days;
delete response.fitness.ongoing_rest_streak_days;
delete response.dividends.days_since_last_confirmed_payment;
delete response.portfolio.price_coverage_percent_by_currency;
handlers["document:visibilitychange"]();
assert.ok(!byId("agenda-list").children.some((row) => /Days without scheduled events/.test(row.textContent)));
assert.ok(!byId("fitness-list").children.some((row) => /Consecutive rest days through today/.test(row.textContent)));
assert.ok(!byId("dividend-list").children.some((row) => /Days since most recent confirmed payment/.test(row.textContent)));
assert.ok(!byId("portfolio-list").children.some((row) => /Manual price completeness/.test(row.textContent)));

// Visual coverage and conflict details use validated provider values only.
response.portfolio = {available:true,positions:[],totals:{},quality:{outdated:false},
  price_coverage_percent_by_currency:{USD:50}};
response.dividends = {available:true,month:"2026-11",monthly_totals:{},
  six_month_paying_symbols:{USD:2},six_month_paid_months:{USD:3},
  history:[],recent:[]};
response.fitness = {available:true,summary:{sessions:3,duration_minutes:75,distance_km:0},
  active_day_percent:42.9,period_start:"2026-11-03",period_end:"2026-11-09",
  daily:[],recent:[]};
response.agenda = {available:true,upcoming_count:3,window_start:"2026-11-09",
  window_end:"2026-11-23",conflicting_time_slots:1,conflicting_event_count:2,events:[]};
handlers["document:visibilitychange"]();
const manualCoverageBar = byId("portfolio-list").children.find((row) =>
  row.className === "allocation-row" && /Price coverage USD/.test(row.children[0].textContent));
assert.ok(manualCoverageBar);
assert.equal(manualCoverageBar.children[1].children[0].style.width,"50%");
const paymentCoverageBar = byId("dividend-list").children.find((row) =>
  row.className === "allocation-row" && /3\/6 months with payments/.test(row.children[0].textContent));
assert.ok(paymentCoverageBar);
assert.equal(paymentCoverageBar.children[1].children[0].style.width,"50%");
const activeCoverageBar = byId("fitness-list").children.find((row) =>
  row.className === "allocation-row" && /Active days \(last 7\) · 42.9%/.test(row.children[0].textContent));
assert.ok(activeCoverageBar);
assert.equal(activeCoverageBar.children[1].children[0].style.width,"42.9%");
assert.ok(byId("agenda-list").children.some((row) =>
  /Review overlapping schedule · 1 shared time slots, 2 events/.test(row.textContent)));
// Invalid percentages and incomplete conflict counters must be ignored.
response.portfolio.price_coverage_percent_by_currency.USD = 120;
response.dividends.six_month_paid_months.USD = -1;
response.fitness.active_day_percent = -5;
delete response.agenda.conflicting_event_count;
handlers["document:visibilitychange"]();
assert.ok(!byId("portfolio-list").children.some((row) => row.className === "allocation-row"));
assert.ok(!byId("dividend-list").children.some((row) => row.className === "allocation-row"));
assert.ok(!byId("fitness-list").children.some((row) => row.className === "allocation-row"));
assert.ok(!byId("agenda-list").children.some((row) => /Review overlapping schedule/.test(row.textContent)));

// Empty configured sources must explain their absence without inventing data.
response.quotes = {available:true,quotes:[]};
response.portfolio = {available:true,positions:[],totals:{},quality:{outdated:false}};
response.fitness = {available:true,summary:{sessions:0,duration_minutes:0,distance_km:0},
  period_start:"2026-11-03",period_end:"2026-11-09",daily:[],recent:[]};
response.agenda = {available:true,upcoming_count:0,window_start:"2026-11-09",
  window_end:"2026-11-23",events:[]};
handlers["document:visibilitychange"]();
assert.match(byId("quotes-list").children[0].textContent,/No provider quotes returned/);
assert.match(byId("portfolio-list").children[0].textContent,/No holdings in the manual snapshot/);
assert.ok(byId("fitness-list").children.some(row => /No workouts recorded in the last 7 days/.test(row.textContent)));
assert.ok(byId("agenda-list").children.some(row => /No upcoming events in the 14-day calendar window/.test(row.textContent)));
// Once actual records arrive, no obsolete empty-state rows may remain.
response.quotes.quotes = [{symbol:"JEPQ",currency:"USD",price:"50",
  reported_at_utc:"2026-11-09T01:00:00Z",age_hours:1,outdated:false}];
response.portfolio.positions = [{symbol:"JEPQ",currency:"USD",quantity:"1",market_value:"50"}];
response.fitness.summary.sessions = 1;
response.agenda.upcoming_count = 1;
response.agenda.events = [{date:"2026-11-09",time:"",title:"Work"}];
handlers["document:visibilitychange"]();
assert.ok(!byId("quotes-list").children.some(row => /No provider quotes returned/.test(row.textContent)));
assert.ok(!byId("portfolio-list").children.some(row => /No holdings in the manual snapshot/.test(row.textContent)));
assert.ok(!byId("fitness-list").children.some(row => /No workouts recorded in the last 7 days/.test(row.textContent)));
assert.ok(!byId("agenda-list").children.some(row => /No upcoming events in the 14-day calendar window/.test(row.textContent)));

// Distinguish an available provider with no usable data from a provider outage.
response.quotes = {available:true,quotes:[
  {symbol:"JEPQ",currency:"USD",price:null,reported_at_utc:null}]};
response.dividends = {available:true,month:"2026-11",monthly_totals:{},
  record_count:0,history:[],recent:[]};
response.github = {available:true,repositories:[]};
response.trello = {available:true,lists:[]};
handlers["document:visibilitychange"]();
assert.ok(byId("quotes-list").children.some(row =>
  /No usable price with a provider timestamp/.test(row.textContent)));
assert.ok(byId("dividend-list").children.some(row =>
  /No confirmed dividend payments recorded/.test(row.textContent)));
assert.ok(byId("github-list").children.some(row =>
  /No GitHub repositories returned/.test(row.textContent)));
assert.ok(byId("trello-list").children.some(row =>
  /No Trello lists returned/.test(row.textContent)));
// Empty-state messages must disappear after usable records are delivered.
response.quotes.quotes = [{symbol:"JEPQ",currency:"USD",price:"50",
  reported_at_utc:"2026-11-09T00:00:00Z"}];
response.dividends.record_count = 1;
response.github.repositories = [{available:true,repository:"owner/repo",
  open_pr_count:0,open_prs:[]}];
response.trello.lists = [{name:"Next",count:1,cards:[]}];
handlers["document:visibilitychange"]();
assert.ok(!byId("quotes-list").children.some(row => /No usable price with a provider timestamp/.test(row.textContent)));
assert.ok(!byId("dividend-list").children.some(row => /No confirmed dividend payments recorded/.test(row.textContent)));
assert.ok(!byId("github-list").children.some(row => /No GitHub repositories returned/.test(row.textContent)));
assert.ok(!byId("trello-list").children.some(row => /No Trello lists returned/.test(row.textContent)));

// Damaged provider metadata must not make aggregate summaries NaN or mask clock errors.
response.github = {available:true,repositories:[
  {repository:"owner/bad",available:true,open_pr_count:"unknown",open_prs:[]},
  {repository:"owner/good",available:true,open_pr_count:2,open_prs:[]}
]};
response.trello = {available:true,lists:[
  {name:"Next",count:"broken",cards:[]},
  {name:"In Progress",count:1,cards:[]}
]};
response.quotes = {available:true,quotes:[
  {symbol:"JEPQ",currency:"USD",price:"50",reported_at_utc:123},
  {symbol:"SCHD",currency:"USD",price:"40",reported_at_utc:"2026-11-09T03:00:00Z"}
]};
response.server.server_time_utc = {invalid:true};
handlers["document:visibilitychange"]();
assert.equal(byId("github-summary").textContent,"2+ known open PRs");
assert.ok(byId("github-list").children.some(row => /PR count unavailable/.test(row.textContent)));
assert.match(byId("trello-summary").textContent,/^1 cards · 0 Next · 1 In Progress$/);
assert.ok(byId("trello-list").children.some(row => /Card count unavailable/.test(row.textContent)));
assert.match(byId("quotes-summary").textContent,/^1\/2 quotes reported/);
assert.match(byId("quotes-list").children[0].textContent,/Quote unavailable/);
assert.equal(byId("server-updated").textContent,"Server clock unavailable");
response.github.repositories[0].open_pr_count = 3;
response.trello.lists[0].count = 2;
response.quotes.quotes[0].reported_at_utc = "2026-11-09T03:01:00Z";
response.server.server_time_utc = "2026-11-09T03:02:00Z";
handlers["document:visibilitychange"]();
assert.match(byId("github-summary").textContent,/^5 open PRs$/);
assert.match(byId("trello-summary").textContent,/^3 cards · 2 Next · 1 In Progress$/);
assert.match(byId("quotes-summary").textContent,/^2\/2 quotes reported/);
assert.match(byId("server-updated").textContent,/Server clock: 2026-11-09 03:02 UTC/);

// A malformed entry in one provider must not reject the entire overview response.
response.weather = {available:true,temperature_c:22,location:"Test City",updated_at:123};
response.github = {available:true,repositories:[null,
  {available:true,repository:"owner/good",open_pr_count:2,open_prs:[]}]};
response.trello = {available:true,lists:[null,{name:"Next",count:3,cards:[]}]};
response.quotes = {available:true,quotes:[null,{symbol:"JEPQ",currency:"USD",
  price:"50",reported_at_utc:"2026-11-09T03:00:00Z"}]};
handlers["document:visibilitychange"]();
assert.match(byId("weather-updated").textContent,/Updated recently/);
assert.equal(byId("github-summary").textContent,"2+ known open PRs");
assert.ok(byId("github-list").children.some(row =>
  /Repository entry unavailable/.test(row.textContent)));
assert.match(byId("trello-summary").textContent,/3 cards · 3 Next/);
assert.ok(byId("trello-list").children.some(row =>
  /Trello list entry unavailable/.test(row.textContent)));
assert.match(byId("quotes-summary").textContent,/1\/2 quotes reported/);
assert.ok(byId("quotes-list").children.some(row =>
  /Quote entry unavailable/.test(row.textContent)));
assert.match(byId("data-refresh-state").textContent,/Last overview refresh succeeded/);
// Recovery on next overview must clear invalid-entry notices.
response.weather.updated_at = "2026-11-09T03:00:00Z";
response.github.repositories.shift();
response.trello.lists.shift();
response.quotes.quotes.shift();
handlers["document:visibilitychange"]();
assert.ok(!byId("github-list").children.some(row => /Repository entry unavailable/.test(row.textContent)));
assert.ok(!byId("trello-list").children.some(row => /Trello list entry unavailable/.test(row.textContent)));
assert.ok(!byId("quotes-list").children.some(row => /Quote entry unavailable/.test(row.textContent)));
assert.match(byId("weather-updated").textContent,/Updated 2026-11-09 03:00 UTC/);

// Malformed collection shapes must not break the overall overview refresh.
response.quotes = {available:true,quotes:{invalid:"not an array"}};
response.github = {available:true,repositories:{invalid:"not an array"}};
response.trello = {available:true,lists:"not an array"};
response.agenda = {available:true,upcoming_count:1,window_start:"2026-11-09",
  window_end:"2026-11-23",events:{invalid:"not an array"}};
handlers["document:visibilitychange"]();
assert.ok(byId("quotes-list").children.some(row => /Quote list invalid/.test(row.textContent)));
assert.ok(byId("github-list").children.some(row => /GitHub repository list invalid/.test(row.textContent)));
assert.ok(byId("trello-list").children.some(row => /Trello list response invalid/.test(row.textContent)));
assert.ok(byId("agenda-list").children.some(row => /Agenda events list invalid/.test(row.textContent)));
assert.ok(!byId("quotes-list").children.some(row => /No provider quotes returned/.test(row.textContent)));
assert.ok(!byId("github-list").children.some(row => /No GitHub repositories returned/.test(row.textContent)));
assert.ok(!byId("trello-list").children.some(row => /No Trello lists returned/.test(row.textContent)));
assert.match(byId("data-refresh-state").textContent,/Last overview refresh succeeded/);
// Recover on the next payload, with explicit empty arrays then with populated arrays.
response.quotes.quotes = [];
response.github.repositories = [];
response.trello.lists = [];
response.agenda.events = [];
response.agenda.upcoming_count = 0;
handlers["document:visibilitychange"]();
assert.ok(!byId("quotes-list").children.some(row => /Quote list invalid/.test(row.textContent)));
assert.ok(!byId("github-list").children.some(row => /GitHub repository list invalid/.test(row.textContent)));
assert.ok(!byId("trello-list").children.some(row => /Trello list response invalid/.test(row.textContent)));
assert.ok(!byId("agenda-list").children.some(row => /Agenda events list invalid/.test(row.textContent)));
assert.ok(byId("quotes-list").children.some(row => /No provider quotes returned/.test(row.textContent)));
assert.ok(byId("github-list").children.some(row => /No GitHub repositories returned/.test(row.textContent)));
assert.ok(byId("trello-list").children.some(row => /No Trello lists returned/.test(row.textContent)));
assert.ok(byId("agenda-list").children.some(row => /No upcoming events/.test(row.textContent)));

// Damaged local file entries must be skipped, preserving valid sibling records.
response.portfolio = {available:true,positions:[
  null,{symbol:"JEPQ",currency:"USD",quantity:3,market_value:"150"}],
  totals:{USD:"150"},quality:{outdated:false}};
response.dividends = {available:true,month:"2026-11",monthly_totals:{},
  history:[null,{month:"2026-11",totals:{USD:"20"}}],recent:[]};
response.fitness = {available:true,summary:{sessions:1,duration_minutes:30,distance_km:1},
  period_start:"2026-11-03",period_end:"2026-11-09",
  daily:[null,{date:"2026-11-09",sessions:1,duration_minutes:30,distance_km:1}],
  recent:[]};
response.agenda = {available:true,upcoming_count:2,window_start:"2026-11-09",
  window_end:"2026-11-23",events:[null,{date:"2026-11-09",time:"",title:"Meeting"}]};
handlers["document:visibilitychange"]();
assert.ok(byId("portfolio-list").children.some(row => /Skipped 1 invalid holding/.test(row.textContent)));
assert.ok(byId("portfolio-list").children.some(row => /JEPQ · 3 shares/.test(row.textContent)));
assert.ok(byId("dividend-list").children.some(row => /Skipped 1 invalid dividend history/.test(row.textContent)));
assert.ok(byId("dividend-list").children.some(row => /2026-11 · USD 20/.test(row.textContent)));
assert.ok(byId("fitness-list").children.some(row => /Skipped 1 invalid daily workout/.test(row.textContent)));
assert.ok(byId("fitness-list").children.some(row => /2026-11-09 · 1 sessions/.test(row.textContent)));
assert.ok(byId("agenda-list").children.some(row => /Skipped 1 invalid calendar events/.test(row.textContent)));
assert.ok(byId("agenda-list").children.some(row => /Meeting/.test(row.textContent)));
assert.match(byId("data-refresh-state").textContent,/Last overview refresh succeeded/);
response.portfolio.positions.shift();
response.dividends.history.shift();
response.fitness.daily.shift();
response.agenda.events.shift();
handlers["document:visibilitychange"]();
assert.ok(!byId("portfolio-list").children.some(row => /Skipped 1 invalid holding/.test(row.textContent)));
assert.ok(!byId("dividend-list").children.some(row => /Skipped 1 invalid dividend history/.test(row.textContent)));
assert.ok(!byId("fitness-list").children.some(row => /Skipped 1 invalid daily workout/.test(row.textContent)));
assert.ok(!byId("agenda-list").children.some(row => /Skipped 1 invalid calendar events/.test(row.textContent)));

// Invalid local collection shapes are distinct from legitimately empty exports.
response.portfolio = {available:true,positions:{broken:true},totals:{},
  quality:{outdated:false}};
response.dividends = {available:true,month:"2026-11",monthly_totals:{},
  history:{broken:true},recent:[]};
response.fitness = {available:true,summary:{sessions:0,duration_minutes:0,distance_km:0},
  period_start:"2026-11-03",period_end:"2026-11-09",daily:"invalid",recent:[]};
response.agenda = {available:true,upcoming_count:2,window_start:"2026-11-09",
  window_end:"2026-11-23",events:[
    {date:"invalid date",time:"",title:"Bad"},
    {date:"2026-11-09",time:"",title:"Valid"}]};
handlers["document:visibilitychange"]();
assert.ok(byId("portfolio-list").children.some(row => /Portfolio holdings list invalid/.test(row.textContent)));
assert.ok(!byId("portfolio-list").children.some(row => /No holdings in the manual snapshot/.test(row.textContent)));
assert.ok(byId("dividend-list").children.some(row => /Dividend history list invalid/.test(row.textContent)));
assert.ok(byId("fitness-list").children.some(row => /Daily workout list invalid/.test(row.textContent)));
assert.ok(byId("agenda-list").children.some(row => /Skipped 1 invalid calendar events/.test(row.textContent)));
assert.ok(byId("agenda-list").children.some(row => /Valid/.test(row.textContent)));
assert.ok(!byId("agenda-list").children.some(row => /Bad/.test(row.textContent)));
assert.match(byId("data-refresh-state").textContent,/Last overview refresh succeeded/);
// A later valid response must remove every corruption warning.
response.portfolio.positions = [];
response.dividends.history = [];
response.fitness.daily = [];
response.agenda.events = [{date:"2026-11-09",time:"",title:"Valid"}];
response.agenda.upcoming_count = 1;
handlers["document:visibilitychange"]();
assert.ok(!byId("portfolio-list").children.some(row => /Portfolio holdings list invalid/.test(row.textContent)));
assert.ok(byId("portfolio-list").children.some(row => /No holdings in the manual snapshot/.test(row.textContent)));
assert.ok(!byId("dividend-list").children.some(row => /Dividend history list invalid/.test(row.textContent)));
assert.ok(!byId("fitness-list").children.some(row => /Daily workout list invalid/.test(row.textContent)));
assert.ok(!byId("agenda-list").children.some(row => /Skipped 1 invalid calendar events/.test(row.textContent)));

// Domain validity: nonpositive quotes, negative payments, impossible dates and distances.
response.quotes = {available:true,quotes:[
  {symbol:"ZERO",currency:"USD",price:"0",reported_at_utc:"2026-11-09T00:00:00Z"},
  {symbol:"NEG",currency:"USD",price:"-10",reported_at_utc:"2026-11-09T00:00:00Z"},
  {symbol:"GOOD",currency:"USD",price:"15.5",reported_at_utc:"2026-11-09T00:00:00Z"}]};
response.dividends = {available:true,month:"2026-11",monthly_totals:{},
  history:[{month:"2026-10",totals:{USD:"20"}},
    {month:"2026-11",totals:{USD:"-10"}}],recent:[]};
response.fitness = {available:true,summary:{sessions:1,duration_minutes:30,distance_km:2},
  period_start:"2026-11-03",period_end:"2026-11-09",
  daily:[{date:"2026-11-31",sessions:1,duration_minutes:20,distance_km:1},
    {date:"2026-11-08",sessions:1,duration_minutes:20,distance_km:-3},
    {date:"2026-11-09",sessions:1,duration_minutes:30,distance_km:2}],recent:[]};
response.agenda = {available:true,upcoming_count:2,window_start:"2026-11-09",
  window_end:"2026-11-23",events:[
    {date:"2026-11-31",time:"",title:"Impossible"},
    {date:"2026-11-09",time:"",title:"Valid"}]};
handlers["document:visibilitychange"]();
assert.match(byId("quotes-summary").textContent,/^1\/3 quotes reported/);
assert.ok(byId("quotes-list").children.filter(row => /Quote unavailable/.test(row.textContent)).length === 2);
const usdChart = byId("dividend-list").children.find(row => row.className === "dividend-bars");
assert.ok(usdChart);
assert.equal(usdChart.children[2].children[1].children[0].style.width,"0%");
assert.match(usdChart.children[2].children[0].textContent,/Invalid amount/);
assert.ok(byId("fitness-list").children.some(row => /Skipped 2 invalid daily workout entries/.test(row.textContent)));
assert.ok(byId("fitness-list").children.some(row => /2026-11-09 · 1 sessions/.test(row.textContent)));
assert.ok(byId("agenda-list").children.some(row => /Skipped 1 invalid calendar events/.test(row.textContent)));
assert.ok(!byId("agenda-list").children.some(row => /Impossible/.test(row.textContent)));
assert.match(byId("data-refresh-state").textContent,/Last overview refresh succeeded/);
response.quotes.quotes[0].price = "12";
response.quotes.quotes[1].price = "10";
response.dividends.history[1].totals.USD = "10";
response.fitness.daily = [response.fitness.daily[2]];
response.agenda.events = [response.agenda.events[1]];
response.agenda.upcoming_count = 1;
handlers["document:visibilitychange"]();
assert.match(byId("quotes-summary").textContent,/^3\/3 quotes reported/);
const repairedChart = byId("dividend-list").children.find(row => row.className === "dividend-bars");
assert.equal(repairedChart.children[2].children[1].children[0].style.width,"50%");
assert.ok(!byId("fitness-list").children.some(row => /Skipped 2 invalid daily/.test(row.textContent)));
assert.ok(!byId("agenda-list").children.some(row => /Skipped 1 invalid calendar/.test(row.textContent)));

// Secondary panels: invalid allocation, recent payment, workout and PR preview rows
// must not prevent a successful overview refresh or hide valid sibling records.
response.portfolio = {available:true,positions:[],totals:{},quality:{outdated:false},
  currency_allocations:{USD:[null,{symbol:"JEPQ",percent:70},{symbol:"BAD",percent:140}]}};
response.dividends = {available:true,month:"2026-11",monthly_totals:{},history:[],
  recent:[null,{paid_on:"2026-11-07",symbol:"JEPQ",amount:"25",currency:"USD"}]};
response.fitness = {available:true,summary:{sessions:1,duration_minutes:30,distance_km:2},
  period_start:"2026-11-03",period_end:"2026-11-09",daily:[],
  recent:[null,{date:"2026-11-09",type:"Running",duration_minutes:30}]};
response.github = {available:true,repositories:[{available:true,repository:"owner/repo",
  open_pr_count:1,open_prs:[null,{number:42,title:"Fix flow"}]}]};
handlers["document:visibilitychange"]();
assert.ok(byId("portfolio-list").children.some(row => /Skipped 2 invalid allocation entries/.test(row.textContent)));
assert.ok(byId("portfolio-list").children.some(row => /JEPQ · 70%/.test(row.children[0]?.textContent || row.textContent)));
assert.ok(byId("dividend-list").children.some(row => /Skipped 1 invalid recent dividend/.test(row.textContent)));
assert.ok(byId("dividend-list").children.some(row => /JEPQ · 25 USD/.test(row.textContent)));
assert.ok(byId("fitness-list").children.some(row => /Skipped 1 invalid recent workout/.test(row.textContent)));
assert.ok(byId("fitness-list").children.some(row => /Running · 30 min/.test(row.textContent)));
assert.ok(byId("github-list").children.some(row => /#42 Fix flow/.test(row.textContent)));
assert.match(byId("data-refresh-state").textContent,/Last overview refresh succeeded/);
response.portfolio.currency_allocations.USD = [null];
response.dividends.recent = [];
response.fitness.recent = [];
response.github.repositories[0].open_prs = {broken:true};
handlers["document:visibilitychange"]();
assert.ok(byId("github-list").children.some(row => /PR preview unavailable/.test(row.textContent)));
assert.match(byId("data-refresh-state").textContent,/Last overview refresh succeeded/);

// Metadata must not crash overview updates or display invented provenance.
response.trello = {available:true,lists:[{name:"Next",count:2,cards:{bad:true}},
  {name:"In Progress",count:2,cards:[null,"Real task"]}]};
response.fitness = {available:true,summary:null,period_start:"2026-11-03",
  period_end:"2026-11-09",daily:[],recent:[],file_updated_utc:123};
response.portfolio = {available:true,positions:[],totals:{},
  quality:{outdated:true,threshold_hours:"not numeric"}};
handlers["document:visibilitychange"]();
assert.ok(byId("trello-list").children.some(row => /Card preview unavailable · Next/.test(row.textContent)));
assert.ok(byId("trello-list").children.some(row => row.className === "trello-preview" && row.textContent === "Real task"));
assert.match(byId("fitness-summary").textContent,/Workout summary unavailable/);
assert.match(byId("fitness-updated").textContent,/Invalid workout summary/);
assert.match(byId("portfolio-updated").textContent,/OUTDATED \(threshold unavailable\)/);
assert.match(byId("data-refresh-state").textContent,/Last overview refresh succeeded/);
response.fitness.summary = {sessions:1,duration_minutes:30,distance_km:2};
handlers["document:visibilitychange"]();
assert.match(byId("fitness-summary").textContent,/1 sessions · 30 min/);
assert.doesNotMatch(byId("fitness-updated").textContent,/Local file updated 123/);
response.fitness.file_updated_utc = "2026-11-09T04:30:00Z";
response.portfolio.quality.threshold_hours = 24;
response.trello.lists[0].cards = ["Next task"];
handlers["document:visibilitychange"]();
assert.match(byId("fitness-updated").textContent,/Local file updated 2026-11-09 04:30 UTC/);
assert.match(byId("portfolio-updated").textContent,/OUTDATED \(older than 24h\)/);
assert.ok(!byId("trello-list").children.some(row => /Card preview unavailable/.test(row.textContent)));

// Reject incorrect totals/counts and unrecognized CI states without losing valid data.
response.portfolio = {available:true,positions:[
  {symbol:"BAD",currency:"USD",quantity:-5,market_value:null},
  {symbol:"GOOD",currency:"USD",quantity:"3",market_value:"150"}],
  totals:{USD:"150"},quality:{outdated:false}};
response.dividends = {available:true,month:"2026-11",
  monthly_totals:{USD:"-10",KRW:"2000"},history:[],recent:[]};
response.agenda = {available:true,upcoming_count:-1,
  today_event_count:-4,tomorrow_event_count:2.5,
  next_seven_busy_days:10,next_seven_days_count:3,
  next_event_in_days:1.5,
  window_start:"2026-11-09",window_end:"2026-11-23",events:[]};
response.github = {available:true,repositories:[{
  available:true,repository:"owner/repo",open_pr_count:1,open_prs:[],
  latest_ci:{status:"completed",conclusion:{invalid:true}}}]};
handlers["document:visibilitychange"]();
assert.match(byId("portfolio-summary").textContent,/^1 holdings$/);
assert.ok(byId("portfolio-list").children.some(row => /Skipped 1 invalid holding/.test(row.textContent)));
assert.match(byId("dividend-summary").textContent,/KRW 2000/);
assert.doesNotMatch(byId("dividend-summary").textContent,/USD/);
assert.ok(byId("dividend-list").children.some(row => /Excluded 1 invalid monthly dividend totals/.test(row.textContent)));
assert.match(byId("agenda-summary").textContent,/Unknown upcoming events/);
assert.doesNotMatch(byId("agenda-summary").textContent,/-4 today|2.5 tomorrow|10 busy days|Next in 1.5/);
assert.match(byId("github-list").children[0].textContent,/CI unknown/);
assert.match(byId("data-refresh-state").textContent,/Last overview refresh succeeded/);
response.portfolio.positions[0].quantity = "2";
response.dividends.monthly_totals.USD = "10";
response.agenda.upcoming_count = 3;
response.agenda.today_event_count = 1;
response.agenda.tomorrow_event_count = 2;
response.agenda.next_seven_busy_days = 3;
response.agenda.next_event_in_days = 1;
response.github.repositories[0].latest_ci = {status:"completed",conclusion:"success"};
handlers["document:visibilitychange"]();
assert.match(byId("portfolio-summary").textContent,/^2 holdings$/);
assert.match(byId("dividend-summary").textContent,/USD 10/);
assert.match(byId("agenda-summary").textContent,/3 upcoming events · 1 today · 2 tomorrow/);
assert.match(byId("github-list").children[0].textContent,/CI success/);

// Financial totals must not show invalid source amounts; partial GitHub counts
// must not be presented as comprehensive, and agenda conflicts must be integers.
response.portfolio = {available:true,positions:[
  {symbol:"JEPQ",quantity:"2",currency:"USD",market_value:"-20"},
  {symbol:"SCHD",quantity:"3",currency:"USD",market_value:"75"}],
  totals:{USD:"75"},quality:{outdated:false}};
response.dividends = {available:true,month:"2026-11",monthly_totals:{},
  history:[],recent:[],six_month_totals:{USD:"-50",KRW:"2000"}};
response.agenda = {available:true,upcoming_count:1,window_start:"2026-11-09",
  window_end:"2026-11-23",events:[{date:"2026-11-09",title:"Meeting",time:""}],
  conflicting_time_slots:1.5,conflicting_event_count:2};
response.github = {available:true,repositories:[
  {available:false,repository:"owner/offline"},
  {available:true,repository:"owner/good",open_pr_count:2,open_prs:[]}]};
handlers["document:visibilitychange"]();
assert.ok(byId("portfolio-list").children.some(row => /JEPQ · 2 shares · price unavailable/.test(row.textContent)));
assert.ok(byId("portfolio-list").children.some(row => /SCHD · 3 shares · 75 USD/.test(row.textContent)));
assert.ok(byId("dividend-list").children.some(row => /Confirmed last 6 months: KRW 2000/.test(row.textContent)));
assert.ok(byId("dividend-list").children.some(row => /Excluded 1 invalid six-month dividend totals/.test(row.textContent)));
assert.doesNotMatch(byId("agenda-summary").textContent,/overlapping time slots/);
assert.ok(!byId("agenda-list").children.some(row => /Review overlapping schedule/.test(row.textContent)));
assert.match(byId("github-summary").textContent,/2\+ known open PRs/);
assert.match(byId("data-refresh-state").textContent,/Last overview refresh succeeded/);
response.portfolio.positions[0].market_value = "40";
response.dividends.six_month_totals.USD = "50";
response.agenda.conflicting_time_slots = 1;
response.github.repositories[0] = {available:true,repository:"owner/offline",
  open_pr_count:1,open_prs:[]};
handlers["document:visibilitychange"]();
assert.ok(byId("portfolio-list").children.some(row => /JEPQ · 2 shares · 40 USD/.test(row.textContent)));
assert.ok(byId("dividend-list").children.some(row => /Confirmed last 6 months: USD 50 \/ KRW 2000/.test(row.textContent)));
assert.ok(byId("agenda-list").children.some(row => /Review overlapping schedule/.test(row.textContent)));
assert.match(byId("github-summary").textContent,/^3 open PRs$/);

// Validate secondary numerical and list metadata without breaking the overview.
response.portfolio = {available:true,positions:[],totals:{},quality:{outdated:false},
  zero_quantity_symbols_by_currency:{USD:[null,"JEPQ",""]},
  largest_holdings:{USD:null,KRW:{symbol:"BAD",market_value:"-10"},
    EUR:{symbol:"GOOD",market_value:"120"}}};
response.dividends = {available:true,month:"2026-11",monthly_totals:{},
  monthly_payment_counts:{USD:-1,KRW:2.5,EUR:3},
  history:[],recent:[]};
response.agenda = {available:true,upcoming_count:0,window_start:"2026-11-09",
  window_end:"2026-11-23",events:[],
  next_seven_daily_counts:[null,{date:"2026-11-31",events:2},
    {date:"2026-11-09",events:1.5},{date:"2026-11-10",events:2}]};
handlers["document:visibilitychange"]();
assert.ok(byId("portfolio-list").children.some(row => /Skipped 2 invalid zero-quantity symbols/.test(row.textContent)));
assert.ok(byId("portfolio-list").children.some(row => /Review zero-quantity positions · USD: JEPQ/.test(row.textContent)));
assert.ok(!byId("portfolio-list").children.some(row => /Largest manually valued holding · USD|Largest manually valued holding · KRW/.test(row.textContent)));
assert.ok(byId("portfolio-list").children.some(row => /Largest manually valued holding · EUR GOOD \(120\)/.test(row.textContent)));
assert.ok(byId("dividend-list").children.some(row => /EUR 3 entries/.test(row.textContent)));
assert.ok(!byId("dividend-list").children.some(row => /USD -1 entries|KRW 2.5 entries/.test(row.textContent)));
assert.ok(byId("agenda-list").children.some(row => /Next 7 calendar days · 11-10 2/.test(row.textContent)));
assert.match(byId("data-refresh-state").textContent,/Last overview refresh succeeded/);
response.portfolio.zero_quantity_symbols_by_currency.USD = ["JEPQ"];
response.portfolio.largest_holdings.USD = {symbol:"SCHD",market_value:"50"};
response.dividends.monthly_payment_counts.USD = 4;
response.agenda.next_seven_daily_counts = [{date:"2026-11-09",events:1}];
handlers["document:visibilitychange"]();
assert.ok(!byId("portfolio-list").children.some(row => /Skipped 2 invalid zero-quantity symbols/.test(row.textContent)));
assert.ok(byId("portfolio-list").children.some(row => /Largest manually valued holding · USD SCHD \(50\)/.test(row.textContent)));
assert.ok(byId("dividend-list").children.some(row => /USD 4 entries/.test(row.textContent)));
assert.ok(byId("agenda-list").children.some(row => /Next 7 calendar days · 11-09 1/.test(row.textContent)));

// In-flight data is cancelled when backgrounded and when auto-refresh is paused.
deferNextOverview = true;
handlers["refresh-button:click"]();
const hiddenRequest = pendingOverviews.pop();
assert.ok(hiddenRequest && !hiddenRequest.aborted);
assert.equal(byId("refresh-button").disabled,true);
document.hidden = true;
handlers["document:visibilitychange"]();
assert.equal(hiddenRequest.aborted,true);
assert.equal(byId("refresh-button").disabled,false);
assert.match(byId("data-refresh-state").textContent,/Tab hidden/);
// Stale completion after cancellation cannot replace the last rendered data.
const savedHealth = byId("glance-sources").textContent;
hiddenRequest.status = 200;
hiddenRequest.responseText = "{invalid";
hiddenRequest.onreadystatechange();
assert.equal(byId("glance-sources").textContent,savedHealth);
document.hidden = false;
handlers["document:visibilitychange"]();
deferNextOverview = true;
handlers["refresh-button:click"]();
const pausedRequest = pendingOverviews.pop();
byId("setting-pause-refresh").checked = true;
handlers["setting-pause-refresh:change"].call(byId("setting-pause-refresh"));
assert.equal(pausedRequest.aborted,true);
assert.equal(byId("refresh-button").disabled,false);
assert.match(byId("data-refresh-state").textContent,/Automatic refresh paused/);
byId("setting-pause-refresh").checked = false;
handlers["setting-pause-refresh:change"].call(byId("setting-pause-refresh"));
// Manual refresh restarts backoff at the first retry after a repeated outage.
overviewStatus = 503;
handlers["document:visibilitychange"]();
const followupRetry = scheduled.filter(item => item.delay === 30000 && !item.cancelled).pop();
assert.ok(followupRetry,"manual failure must schedule first retry");
handlers["refresh-button:click"]();
const restartedRetry = scheduled.filter(item => item.delay === 30000 && !item.cancelled).pop();
assert.ok(restartedRetry && restartedRetry !== followupRetry);
overviewStatus = 200;
handlers["refresh-button:click"]();
// Wall clock going backwards should not block health checks or periodic overview.
clockOffset += 61 * 60000;
periodic.find(item => item.delay === 60000).callback();
clockOffset -= 120 * 60000;
const beforeClockRollback = paths.filter(url => url.startsWith("/api/overview")).length;
periodic.find(item => item.delay === 60000).callback();
assert.equal(paths.filter(url => url.startsWith("/api/overview")).length,beforeClockRollback + 1);
const healthBefore = paths.filter(url => url.startsWith("/healthz")).length;
handlers["document:visibilitychange"]();
assert.ok(paths.filter(url => url.startsWith("/healthz")).length > healthBefore);

// Health polling cannot survive a background transition or alter hidden state.
clockOffset += 3000;
deferNextHealth = true;
periodic.find(item => item.delay === 15000).callback();
const delayedHealth = pendingHealthChecks.pop();
assert.ok(delayedHealth && !delayedHealth.aborted);
document.hidden = true;
handlers["document:visibilitychange"]();
assert.equal(delayedHealth.aborted,true);
const hiddenConnection = byId("connection").textContent;
delayedHealth.readyState = 4;
delayedHealth.status = 503;
delayedHealth.responseText = '{"status":"error"}';
delayedHealth.onreadystatechange();
assert.equal(byId("connection").textContent,hiddenConnection);
const beforeHiddenHealth = paths.filter(url => url.startsWith("/healthz")).length;
periodic.find(item => item.delay === 15000).callback();
assert.equal(paths.filter(url => url.startsWith("/healthz")).length,beforeHiddenHealth);
// A reconnect notification while backgrounded must not fetch overview data.
const beforeHiddenOverview = paths.filter(url => url.startsWith("/api/overview")).length;
delayedHealth.status = 200;
delayedHealth.responseText = '{"status":"ok"}';
delayedHealth.onreadystatechange();
assert.equal(paths.filter(url => url.startsWith("/api/overview")).length,beforeHiddenOverview);
document.hidden = false;
clockOffset += 3000;
handlers["document:visibilitychange"]();
assert.ok(paths.filter(url => url.startsWith("/healthz")).length > beforeHiddenHealth);
// A cancelled timeout callback firing late must not trigger a redundant refresh.
overviewStatus = 503;
handlers["refresh-button:click"]();
const obsoleteRetry = scheduled.filter(item => item.delay === 30000 && !item.cancelled).pop();
assert.ok(obsoleteRetry);
overviewStatus = 200;
handlers["refresh-button:click"]();
assert.equal(obsoleteRetry.cancelled,true);
const beforeObsoleteCallback = paths.filter(url => url.startsWith("/api/overview")).length;
obsoleteRetry.callback();
assert.equal(paths.filter(url => url.startsWith("/api/overview")).length,beforeObsoleteCallback);

// Foreground health recovery must not cause a second overview request.
clockOffset += 3000;
healthBody = '{"status":"error"}';
periodic.find(item => item.delay === 15000).callback();
assert.equal(byId("connection").textContent,"Server offline");
healthBody = '{"status":"ok"}';
clockOffset += 3000; // The health poll is throttled for two seconds.
const beforeForegroundOverview = paths.filter(url => url.startsWith("/api/overview")).length;
handlers["document:visibilitychange"]();
assert.equal(paths.filter(url => url.startsWith("/api/overview")).length,beforeForegroundOverview + 1);
assert.equal(byId("connection").textContent,"Server online");
// Hidden status must remain visible while minute ticker continues running.
document.hidden = true;
handlers["document:visibilitychange"]();
const hiddenStatus = byId("data-refresh-state").textContent;
periodic.find(item => item.delay === 60000).callback();
assert.equal(byId("data-refresh-state").textContent,hiddenStatus);
document.hidden = false;
handlers["document:visibilitychange"]();
// Pause status must remain visible instead of turning into a success-age label.
byId("setting-pause-refresh").checked = true;
handlers["setting-pause-refresh:change"].call(byId("setting-pause-refresh"));
const pausedStatus = byId("data-refresh-state").textContent;
periodic.find(item => item.delay === 60000).callback();
assert.equal(byId("data-refresh-state").textContent,pausedStatus);
byId("setting-pause-refresh").checked = false;
handlers["setting-pause-refresh:change"].call(byId("setting-pause-refresh"));
// When the wall clock rolls behind the last success, age cannot be called 0 minutes.
clockOffset -= 2 * 60 * 60000;
deferNextOverview = true;
periodic.find(item => item.delay === 60000).callback();
assert.match(byId("data-refresh-state").textContent,/Device clock changed; elapsed time unavailable/);
const clockRollbackRequest = pendingOverviews.pop();
assert.ok(clockRollbackRequest);
document.hidden = true;
handlers["document:visibilitychange"]();
assert.equal(clockRollbackRequest.aborted,true);
clockOffset += 2 * 60 * 60000;
document.hidden = false;
handlers["document:visibilitychange"]();
healthBody = null;

// Foreground recovery: a throttled health check cannot leave reconnect suppression stuck.
clockOffset += 3000;
healthBody = '{"status":"ok"}';
periodic.find(item => item.delay === 15000).callback();
handlers["document:visibilitychange"](); // health check is throttled; overview still refreshes
clockOffset += 3000;
healthBody = '{"status":"error"}';
periodic.find(item => item.delay === 15000).callback();
assert.equal(byId("connection").textContent,"Server offline");
healthBody = '{"status":"ok"}';
clockOffset += 3000;
const recoveredOverviewCount = paths.filter(url => url.startsWith("/api/overview")).length;
periodic.find(item => item.delay === 15000).callback();
assert.equal(byId("connection").textContent,"Server online");
assert.equal(paths.filter(url => url.startsWith("/api/overview")).length,recoveredOverviewCount + 1);
// While disconnected, the age ticker must not hide the offline state.
clockOffset += 3000;
healthBody = '{"status":"error"}';
periodic.find(item => item.delay === 15000).callback();
const offlineRefreshMessage = byId("data-refresh-state").textContent;
periodic.find(item => item.delay === 60000).callback();
assert.equal(byId("data-refresh-state").textContent,offlineRefreshMessage);
// Existing in-flight health checks should be reused on foreground, not duplicated.
healthBody = '{"status":"ok"}';
clockOffset += 3000;
deferNextHealth = true;
periodic.find(item => item.delay === 15000).callback();
const reusedHealth = pendingHealthChecks.pop();
assert.ok(reusedHealth && !reusedHealth.aborted);
const beforeReusedHealth = paths.filter(url => url.startsWith("/healthz")).length;
const beforeReusedOverview = paths.filter(url => url.startsWith("/api/overview")).length;
handlers["document:visibilitychange"]();
assert.equal(paths.filter(url => url.startsWith("/healthz")).length,beforeReusedHealth);
assert.equal(paths.filter(url => url.startsWith("/api/overview")).length,beforeReusedOverview + 1);
reusedHealth.readyState = 4;
reusedHealth.status = 200;
reusedHealth.responseText = '{"status":"ok"}';
reusedHealth.onreadystatechange();
assert.equal(byId("connection").textContent,"Server online");
assert.equal(paths.filter(url => url.startsWith("/api/overview")).length,beforeReusedOverview + 1);
healthBody = null;

// Aggregate totals and next-event previews must disclose invalid source records.
response.portfolio = {available:true,positions:[],totals:{USD:"-10",KRW:"2000"},
  valuation_complete:true,quality:{outdated:false}};
response.valuation = {available:true,matched_count:10,position_count:2,
  partial:false,stale:false,totals:{USD:"NaN",KRW:"5000"}};
response.dividends = {available:true,month:"2026-11",monthly_totals:{},
  monthly_unique_paying_symbols:{USD:2.5,KRW:3},history:[],recent:[]};
response.agenda = {available:true,upcoming_count:1,window_start:"2026-11-09",
  window_end:"2026-11-23",events:[{date:"2026-11-09",title:"Valid",time:""}],
  next_event:{date:"2026-11-31",title:"Impossible"},
  next_timed_event:{date:"2026-11-31",title:"Impossible timed",time:"10:00"}};
handlers["document:visibilitychange"]();
assert.ok(byId("portfolio-list").children.some(row => /Values: KRW 2000 \(partial\)/.test(row.textContent)));
assert.ok(byId("portfolio-list").children.some(row => /Excluded 1 invalid manual valuation totals/.test(row.textContent)));
assert.match(byId("portfolio-quote-values").textContent,/coverage unknown holdings\) · PARTIAL/);
assert.match(byId("portfolio-quote-values").textContent,/KRW 5000/);
assert.doesNotMatch(byId("portfolio-quote-values").textContent,/USD NaN/);
assert.ok(byId("dividend-list").children.some(row => /KRW 3 holdings/.test(row.textContent)));
assert.ok(!byId("dividend-list").children.some(row => /USD 2.5 holdings/.test(row.textContent)));
assert.ok(!byId("agenda-list").children.some(row => /Next scheduled: Impossible|Next timed event: Impossible/.test(row.textContent)));
response.portfolio.totals.USD = "100";
response.valuation.matched_count = 2;
response.valuation.totals.USD = "100";
response.dividends.monthly_unique_paying_symbols.USD = 2;
response.agenda.next_event.date = "2026-11-09";
response.agenda.next_timed_event.date = "2026-11-09";
handlers["document:visibilitychange"]();
assert.ok(byId("portfolio-list").children.some(row => /Values: USD 100 \/ KRW 2000$/.test(row.textContent)));
assert.match(byId("portfolio-quote-values").textContent,/2\/2 holdings\)/);
assert.ok(byId("dividend-list").children.some(row => /USD 2 holdings/.test(row.textContent)));
assert.ok(byId("agenda-list").children.some(row => /Next scheduled: Impossible/.test(row.textContent)));

// Four long detail groups can be collapsed independently without hiding summaries.
// The portfolio disclosure controls both manual holdings and quoted valuation.
for (const panel of ["portfolio","dividends","github","fitness"]) {
  assert.equal(byId(panel + "-detail-toggle").attributes["aria-expanded"],"true");
  assert.equal(byId(panel + "-detail-toggle").textContent,"Hide details");
}
const portfolioSummaryBefore = byId("portfolio-summary").textContent;
handlers["portfolio-detail-toggle:click"]();
assert.equal(byId("portfolio-list").hidden,true);
assert.equal(byId("portfolio-quote-values").hidden,true);
assert.equal(byId("portfolio-detail-toggle").attributes["aria-expanded"],"false");
assert.equal(byId("portfolio-detail-toggle").textContent,"Show details");
assert.equal(state["tris.dashboard.details.portfolio"],"collapsed");
assert.equal(byId("portfolio-summary").textContent,portfolioSummaryBefore);
handlers["dividends-detail-toggle:click"]();
handlers["github-detail-toggle:click"]();
handlers["fitness-detail-toggle:click"]();
assert.equal(byId("dividend-list").hidden,true);
assert.equal(byId("github-list").hidden,true);
assert.equal(byId("fitness-list").hidden,true);
assert.equal(byId("dividends-detail-toggle").attributes["aria-expanded"],"false");
assert.equal(state["tris.dashboard.details.github"],"collapsed");
assert.equal(state["tris.dashboard.details.fitness"],"collapsed");
handlers["refresh-button:click"]();
assert.equal(byId("portfolio-list").hidden,true);
assert.equal(byId("dividend-list").hidden,true);
assert.equal(byId("github-list").hidden,true);
assert.equal(byId("fitness-list").hidden,true);
for (const panel of ["portfolio","dividends","github","fitness"]) {
  handlers[panel + "-detail-toggle:click"]();
  assert.equal(byId(panel + "-detail-toggle").attributes["aria-expanded"],"true");
  assert.equal(state["tris.dashboard.details." + panel],"expanded");
}
assert.equal(byId("portfolio-quote-values").hidden,false);
assert.equal(byId("fitness-list").hidden,false);

// Four additional detail disclosures must keep headline values and freshness visible.
const extraDetails = [
  ["quotes","quotes-list","quotes-summary","quotes-updated"],
  ["trello","trello-list","trello-summary","trello-updated"],
  ["weather","weather-details","weather-temp","weather-updated"],
  ["server","server-info","server-uptime","server-updated"]
];
for (const [panel,detail,summary,updated] of extraDetails) {
  const headline = byId(summary).textContent;
  const freshness = byId(updated).textContent;
  assert.equal(byId(panel + "-detail-toggle").attributes["aria-expanded"],"true");
  handlers[panel + "-detail-toggle:click"]();
  assert.equal(byId(detail).hidden,true);
  assert.equal(byId(panel + "-detail-toggle").attributes["aria-expanded"],"false");
  assert.equal(byId(panel + "-detail-toggle").textContent,"Show details");
  assert.equal(state["tris.dashboard.details." + panel],"collapsed");
  assert.equal(byId(summary).textContent,headline);
  assert.equal(byId(updated).textContent,freshness);
}
handlers["refresh-button:click"]();
for (const [panel,detail] of extraDetails) {
  assert.equal(byId(detail).hidden,true);
  handlers[panel + "-detail-toggle:click"]();
  assert.equal(byId(detail).hidden,false);
  assert.equal(byId(panel + "-detail-toggle").attributes["aria-expanded"],"true");
  assert.equal(state["tris.dashboard.details." + panel],"expanded");
}
assert.equal(byId("portfolio-list").hidden,false);
assert.equal(byId("fitness-list").hidden,false);

// Bulk detail controls and agenda disclosure are independent of event pagination.
assert.equal(byId("detail-visibility-count").textContent,"9 of 9 panels showing details");
const agendaHeadline = byId("agenda-summary").textContent;
handlers["agenda-detail-toggle:click"]();
assert.equal(byId("agenda-list").hidden,true);
assert.equal(byId("agenda-toggle").hidden,true);
assert.equal(byId("agenda-summary").textContent,agendaHeadline);
assert.equal(byId("agenda-detail-toggle").attributes["aria-expanded"],"false");
assert.equal(state["tris.dashboard.details.agenda"],"collapsed");
assert.equal(byId("detail-visibility-count").textContent,"8 of 9 panels showing details");
handlers["refresh-button:click"]();
assert.equal(byId("agenda-list").hidden,true);
assert.equal(byId("agenda-toggle").hidden,true);
handlers["collapse-all-details:click"]();
for (const panel of ["portfolio","dividends","github","fitness","quotes","trello","weather","server","agenda"]) {
  assert.equal(byId(panel + "-detail-toggle").attributes["aria-expanded"],"false");
  assert.equal(state["tris.dashboard.details." + panel],"collapsed");
}
assert.equal(byId("portfolio-quote-values").hidden,true);
assert.equal(byId("detail-visibility-count").textContent,"0 of 9 panels showing details");
handlers["expand-all-details:click"]();
for (const panel of ["portfolio","dividends","github","fitness","quotes","trello","weather","server","agenda"]) {
  assert.equal(byId(panel + "-detail-toggle").attributes["aria-expanded"],"true");
  assert.equal(state["tris.dashboard.details." + panel],"expanded");
}
assert.equal(byId("agenda-list").hidden,false);
assert.equal(byId("agenda-toggle").hidden,true); // One event does not need pagination.
assert.equal(byId("portfolio-quote-values").hidden,false);
assert.equal(byId("detail-visibility-count").textContent,"9 of 9 panels showing details");

// Four native anchor shortcuts must always target real, visible priority cards.
const priorityShortcuts = ["portfolio","dividends","github","fitness"];
for (const panel of priorityShortcuts) {
  assert.ok(html.includes('id="panel-' + panel + '"'));
  assert.ok(html.includes('href="#panel-' + panel + '"'));
  assert.equal(byId("jump-link-" + panel).hidden,false);
}
assert.equal(byId("priority-jumps-empty").hidden,true);
// Focus preset keeps all priority shortcuts available.
handlers["focus-panels:click"]();
for (const panel of priorityShortcuts) {
  assert.equal(byId("jump-link-" + panel).hidden,false);
}
// Minimal preset retains links to its visible weather, agenda and server panels.
handlers["minimal-panels:click"]();
for (const panel of priorityShortcuts) {
  assert.equal(byId("jump-link-" + panel).hidden,true);
}
for (const panel of ["agenda","weather","server"]) {
  assert.equal(byId("jump-link-" + panel).hidden,false);
}
assert.equal(byId("jump-link-trello").hidden,true);
assert.equal(byId("priority-jumps-empty").hidden,true);
// Hiding and restoring every card synchronizes native shortcut visibility.
handlers["show-all-panels:click"]();
assert.equal(byId("priority-jumps-empty").hidden,true);
for (const panel of priorityShortcuts) {
  assert.equal(byId("jump-link-" + panel).hidden,false);
}
handlers["hide-all-panels:click"]();
for (const panel of priorityShortcuts) {
  assert.equal(byId("jump-link-" + panel).hidden,true);
}
assert.equal(byId("priority-jumps-empty").hidden,false);
handlers["reset-settings:click"]();
for (const panel of priorityShortcuts) {
  assert.equal(byId("jump-link-" + panel).hidden,false);
}
assert.equal(byId("priority-jumps-empty").hidden,true);

// Four additional quick jumps target visible panels and follow display presets.
const secondaryShortcuts = ["agenda","weather","trello","server"];
for (const panel of secondaryShortcuts) {
  assert.ok(html.includes('id="panel-' + panel + '"'));
  assert.ok(html.includes('href="#panel-' + panel + '"'));
  assert.equal(byId("jump-link-" + panel).hidden,false);
}
handlers["focus-panels:click"]();
for (const panel of secondaryShortcuts) {
  assert.equal(byId("jump-link-" + panel).hidden,true);
}
for (const panel of priorityShortcuts) {
  assert.equal(byId("jump-link-" + panel).hidden,false);
}
handlers["minimal-panels:click"]();
for (const panel of ["agenda","weather","server"]) {
  assert.equal(byId("jump-link-" + panel).hidden,false);
}
assert.equal(byId("jump-link-trello").hidden,true);
assert.equal(byId("priority-jumps-empty").hidden,true);
handlers["hide-all-panels:click"]();
for (const panel of secondaryShortcuts) {
  assert.equal(byId("jump-link-" + panel).hidden,true);
}
assert.equal(byId("priority-jumps-empty").hidden,false);
handlers["show-all-panels:click"]();
for (const panel of secondaryShortcuts) {
  assert.equal(byId("jump-link-" + panel).hidden,false);
}
assert.equal(byId("priority-jumps-empty").hidden,true);
handlers["reset-settings:click"]();

// Final Quotes jump, keyboard shortcut to nav, native top return and count.
assert.ok(html.includes('id="panel-quotes"'));
assert.ok(html.includes('id="jump-link-quotes" href="#panel-quotes"'));
assert.ok(html.includes('href="#priority-jumps" class="skip-link skip-navigation"'));
assert.ok(html.includes('id="priority-jumps" tabindex="-1"'));
assert.ok(html.includes('id="back-to-top" href="#page-top"'));
assert.ok(html.includes('id="page-top"'));
assert.equal(byId("jump-link-quotes").hidden,false);
assert.equal(byId("priority-jumps-count").textContent,"9 of 9 shortcuts available");
handlers["minimal-panels:click"]();
assert.equal(byId("jump-link-quotes").hidden,true);
assert.equal(byId("priority-jumps-count").textContent,"3 of 9 shortcuts available");
handlers["focus-panels:click"]();
assert.equal(byId("jump-link-quotes").hidden,false);
assert.equal(byId("priority-jumps-count").textContent,"5 of 9 shortcuts available");
handlers["hide-all-panels:click"]();
assert.equal(byId("priority-jumps-count").textContent,"0 of 9 shortcuts available");
assert.equal(byId("priority-jumps-empty").hidden,false);
handlers["show-all-panels:click"]();
assert.equal(byId("priority-jumps-count").textContent,"9 of 9 shortcuts available");
assert.equal(byId("priority-jumps-empty").hidden,true);

// Four single-focus view presets preserve saved card ordering and refresh preferences.
const defaultOrderBeforePreset = moduleContainer.children.map(card => card.id);
byId("setting-refresh-minutes").value = "10";
handlers["setting-refresh-minutes:change"].call(byId("setting-refresh-minutes"));
const presetCases = [
  ["assets-only-panels",["portfolio","quotes","dividends"],"Assets view"],
  ["development-only-panels",["github","trello"],"Development view"],
  ["fitness-only-panels",["fitness","weather"],"Fitness view"],
  ["today-only-panels",["agenda","weather","server"],"Today view"]
];
for (const [action,visible,label] of presetCases) {
  handlers[action + ":click"]();
  assert.equal(byId("panel-preset-status").textContent,label + " · " + visible.length + " panels");
  assert.equal(byId("priority-jumps-count").textContent,visible.length + " of 9 shortcuts available");
  for (const panel of ["portfolio","quotes","dividends","agenda","github","weather","trello","server","fitness"]) {
    const shouldShow = visible.includes(panel);
    assert.equal(byId("panel-" + panel).hidden,!shouldShow);
    assert.equal(byId("jump-link-" + panel).hidden,!shouldShow);
    assert.equal(byId("toggle-" + panel).checked,shouldShow);
  }
  assert.equal(byId("setting-refresh-minutes").value,"10");
  assert.equal(window.trisDashboardRefreshMinutes,10);
  assert.deepEqual(moduleContainer.children.map(card => card.id),defaultOrderBeforePreset);
}
handlers["show-all-panels:click"]();
byId("setting-refresh-minutes").value = "3";
handlers["setting-refresh-minutes:change"].call(byId("setting-refresh-minutes"));

// Active view always reflects actual saved visibility, not the last button clicked.
const viewButtons = [
  ["assets-only-panels","Assets view"],
  ["development-only-panels","Development view"],
  ["fitness-only-panels","Fitness view"],
  ["today-only-panels","Today view"]
];
for (const [action,label] of viewButtons) {
  handlers[action + ":click"]();
  assert.match(byId("panel-preset-status").textContent,new RegExp(label));
  for (const [other] of viewButtons) {
    assert.equal(byId(other).attributes["aria-pressed"],other === action ? "true" : "false");
  }
}
const dynamicFitnessToggle = byId("panel-visibility").children
  .map(label => label.children[0]).find(input => input.id === "toggle-fitness");
assert.ok(dynamicFitnessToggle);
dynamicFitnessToggle.checked = true;
handlers["toggle-fitness:change"]();
assert.match(byId("panel-preset-status").textContent,/Custom panel selection · 4 panels/);
for (const [action] of viewButtons) {
  assert.equal(byId(action).attributes["aria-pressed"],"false");
}
handlers["hide-all-panels:click"]();
assert.equal(byId("panel-preset-status").textContent,"No panels visible");
handlers["show-all-panels:click"]();
assert.equal(byId("panel-preset-status").textContent,"All panels · 9 panels");
handlers["assets-only-panels:click"]();
const savedView = JSON.parse(state["tris.dashboard.display.v1"]);
assert.deepEqual(savedView.hidden.sort(),["agenda","fitness","github","server","trello","weather"].sort());
assert.equal(byId("assets-only-panels").attributes["aria-pressed"],"true");
handlers["reset-settings:click"]();
assert.equal(byId("panel-preset-status").textContent,"All panels · 9 panels");

// Four one-tap view controls work outside Display settings and mirror pressed state.
const quickViewCases = [
  ["assets","assets-only-panels",["portfolio","quotes","dividends"]],
  ["development","development-only-panels",["github","trello"]],
  ["fitness","fitness-only-panels",["fitness","weather"]],
  ["today","today-only-panels",["agenda","weather","server"]]
];
const beforeQuickOrder = moduleContainer.children.map(card => card.id);
byId("display-settings").hidden = true;
for (const [name,settingId,visible] of quickViewCases) {
  assert.ok(html.includes('id="quick-view-' + name + '" aria-pressed="false"'));
  handlers["quick-view-" + name + ":click"]();
  assert.equal(byId("display-settings").hidden,true);
  assert.equal(byId("quick-view-" + name).attributes["aria-pressed"],"true");
  assert.equal(byId(settingId).attributes["aria-pressed"],"true");
  assert.equal(byId("priority-jumps-count").textContent,visible.length + " of 9 shortcuts available");
  for (const panel of ["portfolio","quotes","dividends","agenda","github","weather","trello","server","fitness"]) {
    assert.equal(byId("panel-" + panel).hidden,!visible.includes(panel));
  }
  for (const [other] of quickViewCases) {
    assert.equal(byId("quick-view-" + other).attributes["aria-pressed"],other === name ? "true" : "false");
  }
  assert.deepEqual(moduleContainer.children.map(card => card.id),beforeQuickOrder);
}
handlers["assets-only-panels:click"]();
assert.equal(byId("quick-view-assets").attributes["aria-pressed"],"true");
handlers["show-all-panels:click"]();
for (const [name] of quickViewCases) {
  assert.equal(byId("quick-view-" + name).attributes["aria-pressed"],"false");
}
assert.equal(byId("priority-jumps-count").textContent,"9 of 9 shortcuts available");

// Saved custom view: explicit save, one-tap restore, All view and delete.
assert.equal(byId("quick-view-mine").disabled,true);
assert.equal(byId("clear-my-view").disabled,true);
assert.equal(byId("quick-view-all").attributes["aria-pressed"],"true");
handlers["assets-only-panels:click"]();
handlers["save-my-view:click"]();
assert.equal(byId("saved-view-status").textContent,"Saved view: 3 panels · Active");
assert.equal(byId("quick-view-mine").disabled,false);
assert.equal(byId("quick-view-mine").attributes["aria-pressed"],"true");
assert.deepEqual(JSON.parse(state["tris.dashboard.my-view.v1"]),["portfolio","quotes","dividends"]);
handlers["quick-view-today:click"]();
assert.equal(byId("quick-view-mine").attributes["aria-pressed"],"false");
handlers["quick-view-mine:click"]();
assert.equal(byId("quick-view-mine").attributes["aria-pressed"],"true");
assert.equal(byId("panel-portfolio").hidden,false);
assert.equal(byId("panel-weather").hidden,true);
handlers["quick-view-all:click"]();
assert.equal(byId("quick-view-all").attributes["aria-pressed"],"true");
assert.equal(byId("priority-jumps-count").textContent,"9 of 9 shortcuts available");
assert.equal(byId("quick-view-mine").attributes["aria-pressed"],"false");
handlers["hide-all-panels:click"]();
handlers["save-my-view:click"]();
assert.equal(byId("saved-view-status").textContent,"Show at least one panel before saving a view");
assert.deepEqual(JSON.parse(state["tris.dashboard.my-view.v1"]),["portfolio","quotes","dividends"]);
handlers["quick-view-mine:click"]();
assert.equal(byId("priority-jumps-count").textContent,"3 of 9 shortcuts available");
handlers["clear-my-view:click"]();
assert.equal(byId("quick-view-mine").disabled,true);
assert.equal(byId("clear-my-view").disabled,true);
assert.equal(byId("quick-view-mine").attributes["aria-pressed"],"false");
assert.equal(byId("saved-view-status").textContent,"No saved view");
assert.equal(state["tris.dashboard.my-view.v1"],undefined);
handlers["show-all-panels:click"]();

// Quick-save, previous-view history, saved panel preview and change comparison.
assert.equal(byId("quick-previous-view").disabled,false);
handlers["assets-only-panels:click"]();
assert.equal(byId("quick-previous-view").disabled,false);
handlers["quick-save-my-view:click"]();
assert.deepEqual(JSON.parse(state["tris.dashboard.my-view.v1"]),["portfolio","quotes","dividends"]);
assert.equal(byId("saved-view-preview").textContent,"Saved panels: portfolio, quotes, dividends");
assert.equal(byId("saved-view-status").textContent,"Saved view: 3 panels · Active");
handlers["quick-view-today:click"]();
assert.equal(byId("saved-view-status").textContent,"Saved view: 3 panels · Different from current");
assert.equal(byId("saved-view-preview").textContent,"Saved panels: portfolio, quotes, dividends");
assert.equal(byId("quick-previous-view").disabled,false);
handlers["quick-previous-view:click"]();
assert.equal(byId("saved-view-status").textContent,"Saved view: 3 panels · Active");
assert.equal(byId("panel-portfolio").hidden,false);
assert.equal(byId("panel-weather").hidden,true);
// Forward returns to the view just left; history is not modified by replay.
assert.equal(byId("quick-next-view").disabled,false);
handlers["quick-next-view:click"]();
assert.equal(byId("panel-weather").hidden,false);
assert.equal(byId("panel-portfolio").hidden,true);
assert.equal(byId("quick-next-view").disabled,true);
handlers["clear-my-view:click"]();
assert.equal(byId("saved-view-preview").textContent,"Saved panels: none");
handlers["quick-view-all:click"]();

// Bounded view history: back/forward, branch invalidation, readable status and clear.
handlers["assets-only-panels:click"]();
handlers["quick-view-today:click"]();
handlers["quick-view-fitness:click"]();
assert.equal(byId("quick-previous-view").disabled,false);
assert.equal(byId("quick-next-view").disabled,true);
assert.match(byId("view-history-status").textContent,/View history: \d+ of \d+/);
handlers["quick-previous-view:click"]();
assert.equal(byId("panel-agenda").hidden,false);
assert.equal(byId("panel-fitness").hidden,true);
assert.equal(byId("quick-next-view").disabled,false);
handlers["quick-previous-view:click"]();
handlers["quick-view-development:click"]();
assert.equal(byId("quick-next-view").disabled,true);
assert.equal(byId("panel-github").hidden,false);
assert.equal(byId("panel-agenda").hidden,true);
// Repeated identical selection does not add another history entry.
const historyBeforeRepeat = byId("view-history-status").textContent;
handlers["quick-view-development:click"]();
assert.equal(byId("view-history-status").textContent,historyBeforeRepeat);
// A clear retains the visible layout and resets both navigation directions.
handlers["clear-view-history:click"]();
assert.equal(byId("view-history-status").textContent,"View history: 1 of 1");
assert.equal(byId("quick-previous-view").disabled,true);
assert.equal(byId("quick-next-view").disabled,true);
assert.equal(byId("clear-view-history").disabled,true);
assert.equal(byId("panel-github").hidden,false);
// History max length should never exceed ten entries even after many view switches.
for (let i = 0; i < 15; i++) {
  handlers[i % 2 ? "quick-view-assets:click" : "quick-view-fitness:click"]();
}
assert.equal(byId("view-history-status").textContent,"View history: 10 of 10");
assert.equal(byId("quick-next-view").disabled,true);
handlers["clear-view-history:click"]();
handlers["quick-view-all:click"]();

// Panel title search is transient, respects selected views, and synchronizes quick links.
assert.equal(byId("panel-search-count").textContent,"9 panels available");
const settingsBeforeSearch = state["tris.dashboard.display.v1"];
byId("panel-search-input").value = " GitHub ";
handlers["panel-search-input:input"].call(byId("panel-search-input"));
assert.equal(byId("panel-search-input").value,"github");
assert.equal(byId("panel-search-count").textContent,"1 matching visible panels");
assert.equal(byId("panel-github").hidden,false);
assert.equal(byId("jump-link-github").hidden,false);
assert.equal(byId("panel-fitness").hidden,true);
assert.equal(byId("jump-link-fitness").hidden,true);
assert.equal(byId("toggle-fitness").checked,true);
assert.equal(byId("panel-search-clear").disabled,false);
assert.equal(byId("panel-search-empty").hidden,true);
assert.equal(state["tris.dashboard.display.v1"],settingsBeforeSearch);
// Search never overrides the selected preset; filter is intersected with it.
handlers["quick-view-fitness:click"]();
assert.equal(byId("panel-search-count").textContent,"0 matching visible panels");
assert.equal(byId("panel-search-empty").hidden,false);
assert.equal(byId("priority-jumps-count").textContent,"0 of 9 shortcuts available");
assert.equal(byId("toggle-fitness").checked,true);
assert.equal(byId("priority-jumps-empty").hidden,true);
byId("panel-search-input").value = "workout";
handlers["panel-search-input:input"].call(byId("panel-search-input"));
assert.equal(byId("panel-search-count").textContent,"1 matching visible panels");
assert.equal(byId("panel-fitness").hidden,false);
assert.equal(byId("panel-weather").hidden,true);
handlers["panel-search-clear:click"]();
assert.equal(byId("panel-search-clear").disabled,true);
assert.equal(byId("panel-search-input").value,"");
assert.equal(byId("panel-search-input").focused,true);
assert.equal(byId("panel-search-count").textContent,"2 panels available");
assert.equal(byId("panel-search-empty").hidden,true);
assert.equal(byId("panel-weather").hidden,false);
handlers["quick-view-all:click"]();
assert.equal(byId("panel-search-count").textContent,"9 panels available");

// Multi-term AND search, Korean labels, keyboard reset, and hidden-match guidance.
handlers["quick-view-all:click"]();
byId("panel-search-input").value = "stock price";
handlers["panel-search-input:input"].call(byId("panel-search-input"));
assert.equal(byId("panel-search-count").textContent,"1 matching visible panels");
assert.equal(byId("panel-quotes").hidden,false);
assert.equal(byId("panel-portfolio").hidden,true);
byId("panel-search-input").value = "운동";
handlers["panel-search-input:input"].call(byId("panel-search-input"));
assert.equal(byId("panel-fitness").hidden,false);
assert.equal(byId("panel-quotes").hidden,true);
assert.equal(byId("panel-search-count").textContent,"1 matching visible panels");
byId("panel-search-input").value = "개발 깃허브";
handlers["panel-search-input:input"].call(byId("panel-search-input"));
assert.equal(byId("panel-github").hidden,false);
assert.equal(byId("panel-trello").hidden,true);
handlers["quick-view-fitness:click"]();
assert.equal(byId("panel-search-empty").hidden,false);
assert.match(byId("panel-search-empty").textContent,/hidden in Display settings/);
byId("panel-search-input").value = "keywordthatdoesnotexist";
handlers["panel-search-input:input"].call(byId("panel-search-input"));
assert.match(byId("panel-search-empty").textContent,/No panel matches/);
const beforeSearchClearState = state["tris.dashboard.display.v1"];
let preventedSearchEscape = false;
handlers["panel-search-input:keydown"]({keyCode:27,preventDefault(){preventedSearchEscape=true;}});
assert.equal(preventedSearchEscape,true);
assert.equal(byId("panel-search-input").value,"");
assert.equal(byId("panel-search-clear").disabled,true);
assert.equal(byId("panel-weather").hidden,false);
assert.equal(byId("panel-search-empty").hidden,true);
assert.equal(state["tris.dashboard.display.v1"],beforeSearchClearState);
handlers["quick-view-all:click"]();

// Keyboard search navigation respects input focus, configured order and hidden panels.
handlers["quick-view-all:click"]();
let shortcutPrevented = false;
handlers["document:keydown"]({keyCode:191, target:{tagName:"BODY"}, preventDefault(){shortcutPrevented=true;}});
assert.equal(shortcutPrevented,true);
assert.equal(byId("panel-search-input").focused,true);
shortcutPrevented = false;
handlers["document:keydown"]({keyCode:191, target:{tagName:"INPUT"}, preventDefault(){shortcutPrevented=true;}});
assert.equal(shortcutPrevented,false);
handlers["document:keydown"]({keyCode:75,ctrlKey:true,target:{tagName:"BODY"},preventDefault(){shortcutPrevented=true;}});
assert.equal(shortcutPrevented,true);
byId("panel-search-input").value = "개발";
handlers["panel-search-input:input"].call(byId("panel-search-input"));
assert.equal(byId("panel-github").hidden,false);
let enterPrevented = false;
handlers["panel-search-input:keydown"]({keyCode:13,preventDefault(){enterPrevented=true;}});
assert.equal(enterPrevented,true);
assert.equal(byId("panel-github").focused,true);
handlers["quick-view-fitness:click"]();
assert.equal(byId("panel-search-reveal").hidden,false);
assert.match(byId("panel-search-reveal").textContent,/Show 1 matching hidden panel/);
const visibilityBeforeReveal = JSON.parse(state["tris.dashboard.display.v1"]);
assert.ok(visibilityBeforeReveal.hidden.includes("github"));
handlers["panel-search-reveal:click"]();
assert.equal(byId("panel-github").hidden,false);
assert.equal(byId("panel-search-reveal").hidden,true);
assert.equal(JSON.parse(state["tris.dashboard.display.v1"]).hidden.includes("github"),false);
handlers["panel-search-clear:click"]();
assert.equal(byId("panel-search-reveal").hidden,true);
handlers["quick-view-all:click"]();
byId("panel-search-input").value="no such module";
handlers["panel-search-input:input"].call(byId("panel-search-input"));
enterPrevented=false;
handlers["panel-search-input:keydown"]({keyCode:13,preventDefault(){enterPrevented=true;}});
assert.equal(enterPrevented,false);
handlers["panel-search-clear:click"]();

// Actionable source health: ready, stale, unavailable, unconfigured, and recovery.
handlers["quick-view-all:click"]();
response.weather.stale = true;
response.weather.cache_age_seconds = 121;
response.portfolio = {available:false,configured:false};
response.github.available = false;
response.github.configured = true;
handlers["document:visibilitychange"]();
assert.match(byId("source-state-weather").textContent,/Stale · 2 min old/);
assert.match(byId("source-state-github").textContent,/Unavailable/);
assert.match(byId("source-state-portfolio").textContent,/Not configured/);
assert.equal(byId("source-health-links").hidden,false);
assert.equal(byId("source-health-links").children.length,2);
assert.match(byId("source-health-details").textContent,/2 sources/);
assert.match(byId("glance-sources").textContent,/not configured/);
handlers["quick-view-fitness:click"]();
assert.equal(byId("panel-github").hidden,true);
byId("panel-search-input").value = "운동";
handlers["panel-search-input:input"].call(byId("panel-search-input"));
assert.equal(byId("panel-github").hidden,true);
const issueGithubLink = byId("source-health-links").children.find(link=>link.href==="#panel-github");
handlers[issueGithubLink.id + ":click"]();
assert.equal(byId("panel-github").hidden,false);
assert.equal(byId("panel-github").focused,true);
assert.equal(byId("panel-search-input").value,"");
assert.equal(JSON.parse(state["tris.dashboard.display.v1"]).hidden.includes("github"),false);
response.weather.stale = false;
response.github.available = true;
handlers["document:visibilitychange"]();
assert.equal(byId("source-health-links").hidden,true);
assert.equal(byId("source-health-links").children.length,0);
assert.match(byId("source-state-weather").textContent,/Ready/);
assert.match(byId("source-state-github").textContent,/Ready/);
assert.equal(byId("source-health-details").textContent,"No stale or unavailable configured sources.");
handlers["quick-view-all:click"]();

// Source-status quick views are transient, live-updating, and search-aware.
handlers["quick-view-all:click"]();
const beforeSourceFilterSetting = state["tris.dashboard.display.v1"];
const sourceHistoryBefore = byId("view-history-status").textContent;
response.weather.stale=true;
response.weather.cache_age_seconds=120;
response.github.available=false;
response.github.configured=true;
response.portfolio={available:false,configured:false};
handlers["document:visibilitychange"]();
handlers["source-filter-issues:click"]();
assert.equal(byId("source-filter-issues").attributes["aria-pressed"],"true");
assert.equal(byId("panel-weather").hidden,false);
assert.equal(byId("panel-github").hidden,false);
assert.equal(byId("panel-portfolio").hidden,true);
assert.equal(byId("panel-trello").hidden,true);
assert.equal(byId("source-filter-count").textContent,"2 issues sources");
assert.equal(byId("source-filter-empty").hidden,true);
assert.equal(state["tris.dashboard.display.v1"],beforeSourceFilterSetting);
assert.equal(byId("view-history-status").textContent,sourceHistoryBefore);
handlers["source-filter-unconfigured:click"]();
assert.equal(byId("panel-portfolio").hidden,false);
assert.equal(byId("panel-weather").hidden,true);
assert.match(byId("source-filter-count").textContent,/unconfigured sources/);
handlers["source-filter-ready:click"]();
assert.equal(byId("panel-github").hidden,true);
assert.equal(byId("panel-server").hidden,true); // server is not a source filter member
handlers["source-filter-issues:click"]();
byId("panel-search-input").value="운동";
handlers["panel-search-input:input"].call(byId("panel-search-input"));
assert.equal(byId("source-filter-empty").hidden,true);
assert.equal(byId("combined-filter-empty").hidden,false);
assert.match(byId("combined-filter-empty").textContent,/Search and Source: issues/);
handlers["panel-search-clear:click"]();
response.weather.stale=false;
response.github.available=true;
handlers["document:visibilitychange"]();
assert.equal(byId("source-filter-empty").hidden,false);
assert.match(byId("source-filter-empty").textContent,/No issues sources/);
assert.equal(byId("source-filter-count").textContent,"0 issues sources");
handlers["source-filter-all:click"]();
assert.equal(byId("source-filter-empty").hidden,true);
assert.equal(byId("source-filter-all").attributes["aria-pressed"],"true");
assert.equal(byId("panel-weather").hidden,false);
assert.equal(byId("panel-portfolio").hidden,false);
assert.equal(state["tris.dashboard.display.v1"],beforeSourceFilterSetting);
assert.equal(byId("view-history-status").textContent,sourceHistoryBefore);
// Pinned favorite cards: visible priority order, transient solo view, saved state, reset.
handlers["source-filter-all:click"]();
handlers["quick-view-all:click"]();
const pinnedSettingsBefore = state["tris.dashboard.display.v1"];
const pinnedHistoryBefore = byId("view-history-status").textContent;
const firstPanelBeforePins = byId("dashboard-modules").children[0].id;
assert.equal(byId("quick-view-pinned").disabled,true);
handlers["pin-fitness:click"]();
handlers["pin-weather:click"]();
assert.equal(byId("pin-fitness").attributes["aria-pressed"],"true");
assert.equal(byId("pin-weather").attributes["aria-pressed"],"true");
assert.equal(byId("dashboard-modules").children[0].id,"panel-weather");
assert.equal(byId("dashboard-modules").children[1].id,"panel-fitness");
assert.equal(byId("priority-jumps").children.findIndex(child=>child.id==="jump-link-weather") <
  byId("priority-jumps").children.findIndex(child=>child.id==="jump-link-portfolio"),true);
assert.equal(byId("pinned-panel-count").textContent,"2 pinned");
assert.deepEqual(JSON.parse(state["tris.dashboard.pins.v1"]),["fitness","weather"]);
assert.equal(state["tris.dashboard.display.v1"],pinnedSettingsBefore);
assert.equal(byId("view-history-status").textContent,pinnedHistoryBefore);
handlers["quick-view-pinned:click"]();
assert.equal(byId("panel-weather").hidden,false);
assert.equal(byId("panel-fitness").hidden,false);
assert.equal(byId("panel-portfolio").hidden,true);
assert.equal(byId("quick-view-pinned").attributes["aria-pressed"],"true");
byId("panel-search-input").value="stocks";
handlers["panel-search-input:input"].call(byId("panel-search-input"));
assert.equal(byId("pinned-panel-empty").hidden,true);
assert.equal(byId("combined-filter-empty").hidden,false);
assert.match(byId("combined-filter-empty").textContent,/Search and Pinned only/);
handlers["panel-search-clear:click"]();
assert.equal(byId("pinned-panel-empty").hidden,true);
handlers["pin-fitness:click"]();
assert.deepEqual(JSON.parse(state["tris.dashboard.pins.v1"]),["weather"]);
handlers["pin-weather:click"]();
assert.equal(byId("quick-view-pinned").disabled,true);
assert.equal(byId("quick-view-pinned").attributes["aria-pressed"],"false");
assert.equal(byId("dashboard-modules").children[0].id,firstPanelBeforePins);
assert.equal(state["tris.dashboard.display.v1"],pinnedSettingsBefore);
assert.equal(byId("view-history-status").textContent,pinnedHistoryBefore);
handlers["pin-github:click"]();
assert.match(state["tris.dashboard.pins.v1"],/github/);
handlers["reset-settings:click"]();
assert.deepEqual(JSON.parse(state["tris.dashboard.pins.v1"]),["github"]);
assert.equal(byId("pin-github").attributes["aria-pressed"],"true");
assert.match(byId("display-reset-status").textContent,/Pinned favorites and My view were kept/);
// The standalone Clear pins action, not Reset display, owns favorite deletion.
handlers["clear-all-pins:click"]();
assert.deepEqual(JSON.parse(state["tris.dashboard.pins.v1"]),[]);
assert.equal(byId("pin-github").attributes["aria-pressed"],"false");

// Manage hidden favorites independently of saved presets and recover with explicit action.
handlers["quick-view-all:click"]();
const pinsPreservedSettings=state["tris.dashboard.display.v1"];
const pinsPreservedHistory=byId("view-history-status").textContent;
assert.equal(byId("clear-all-pins").disabled,true);
handlers["pin-github:click"]();
assert.equal(byId("pinned-panel-actions").hidden,false);
assert.equal(byId("clear-all-pins").disabled,false);
assert.ok(byId("pinned-panel-actions").children.some(child=>child.id==="pinned-jump-github"));
assert.ok(byId("pinned-panel-actions").children.some(child=>child.id==="pinned-remove-github"));
handlers["quick-view-pinned:click"]();
assert.equal(byId("quick-view-all").attributes["aria-pressed"],"false");
assert.equal(byId("quick-view-pinned").attributes["aria-pressed"],"true");
handlers["quick-view-pinned:click"]();
handlers["quick-view-fitness:click"]();
assert.equal(byId("panel-github").hidden,true);
handlers["pinned-jump-github:click"]();
assert.match(byId("pinned-panel-message").textContent,/hidden in Display settings/);
assert.equal(byId("panel-github").hidden,true);
assert.equal(byId("quick-view-pinned").attributes["aria-pressed"],"false");
handlers["show-pinned-panels:click"]();
assert.equal(byId("panel-github").hidden,false);
assert.equal(JSON.parse(state["tris.dashboard.display.v1"]).hidden.includes("github"),false);
handlers["pinned-jump-github:click"]();
assert.equal(byId("panel-github").focused,true);
handlers["pinned-remove-github:click"]();
assert.equal(byId("clear-all-pins").disabled,true);
assert.equal(byId("pinned-panel-actions").hidden,true);
handlers["pin-weather:click"]();
handlers["pin-fitness:click"]();
assert.equal(byId("pinned-panel-actions").children.length,5);
handlers["clear-all-pins:click"]();
assert.deepEqual(JSON.parse(state["tris.dashboard.pins.v1"]),[]);
assert.equal(byId("pinned-panel-actions").hidden,true);
assert.equal(byId("quick-view-pinned").disabled,true);
assert.match(byId("pinned-panel-message").textContent,/All pins cleared/);
assert.equal(byId("view-history-status").textContent !== "",true);
handlers["quick-view-all:click"]();

// Temporary filter summary, multi-filter empty guidance and one-tap recovery.
handlers["quick-view-all:click"]();
handlers["source-filter-all:click"]();
handlers["clear-temporary-filters:click"]();
assert.equal(byId("clear-temporary-filters").disabled,true);
assert.equal(byId("filter-summary-status").textContent,"No temporary filters");
const originalDisplayState = state["tris.dashboard.display.v1"];
const originalPinsState = state["tris.dashboard.pins.v1"];
const originalViewHistory = byId("view-history-status").textContent;
byId("panel-search-input").value="개발";
handlers["panel-search-input:input"].call(byId("panel-search-input"));
assert.equal(byId("filter-summary-status").textContent,"1 active filters: Search");
assert.equal(byId("clear-temporary-filters").disabled,false);
handlers["source-filter-issues:click"]();
assert.equal(byId("filter-summary-status").textContent,"2 active filters: Search · Source: issues");
assert.equal(byId("combined-filter-empty").hidden,false);
assert.match(byId("combined-filter-empty").textContent,/Clear all filters/);
assert.equal(byId("source-filter-empty").hidden,true);
assert.equal(byId("panel-search-empty").hidden,true);
assert.equal(byId("pinned-panel-empty").hidden,true);
handlers["clear-temporary-filters:click"]();
assert.equal(byId("filter-summary-status").textContent,"No temporary filters");
assert.equal(byId("clear-temporary-filters").disabled,true);
assert.equal(byId("combined-filter-empty").hidden,true);
assert.equal(byId("panel-search-input").value,"");
assert.equal(byId("source-filter-all").attributes["aria-pressed"],"true");
assert.equal(byId("priority-jumps-count").textContent,"9 of 9 shortcuts available");
assert.equal(state["tris.dashboard.display.v1"],originalDisplayState);
assert.equal(state["tris.dashboard.pins.v1"],originalPinsState);
assert.equal(byId("view-history-status").textContent,originalViewHistory);
// Pinned-only is also included in summary without changing saved favorites.
handlers["pin-github:click"]();
handlers["quick-view-pinned:click"]();
assert.equal(byId("filter-summary-status").textContent,"1 active filters: Pinned only");
handlers["clear-temporary-filters:click"]();
assert.equal(byId("quick-view-pinned").attributes["aria-pressed"],"false");
assert.match(state["tris.dashboard.pins.v1"],/github/);
handlers["pin-github:click"]();
handlers["quick-view-all:click"]();

// Safe reset preserves separate favorites and My view, and supports one undo.
handlers["quick-view-all:click"]();
handlers["quick-view-fitness:click"]();
byId("setting-large-text").checked = true;
handlers["setting-large-text:change"].call(byId("setting-large-text"));
byId("setting-refresh-minutes").value = "10";
handlers["setting-refresh-minutes:change"].call(byId("setting-refresh-minutes"));
handlers["pin-weather:click"]();
handlers["quick-save-my-view:click"]();
const beforeSafetyReset = state["tris.dashboard.display.v1"];
const beforeSafetyPins = state["tris.dashboard.pins.v1"];
const beforeSafetyView = state["tris.dashboard.my-view.v1"];
handlers["reset-settings:click"]();
assert.equal(byId("undo-display-reset").disabled,false);
assert.equal(byId("setting-large-text").checked,false);
assert.equal(byId("setting-refresh-minutes").value,"3");
assert.equal(byId("panel-fitness").hidden,false);
assert.equal(byId("panel-portfolio").hidden,false);
assert.equal(state["tris.dashboard.pins.v1"],beforeSafetyPins);
assert.equal(state["tris.dashboard.my-view.v1"],beforeSafetyView);
assert.match(byId("display-reset-status").textContent,/Undo is available/);
handlers["undo-display-reset:click"]();
assert.equal(byId("undo-display-reset").disabled,true);
assert.equal(state["tris.dashboard.display.v1"],beforeSafetyReset);
assert.equal(byId("setting-large-text").checked,true);
assert.equal(byId("setting-refresh-minutes").value,"10");
assert.equal(byId("panel-portfolio").hidden,true);
assert.equal(byId("panel-fitness").hidden,false);
assert.equal(state["tris.dashboard.pins.v1"],beforeSafetyPins);
assert.equal(state["tris.dashboard.my-view.v1"],beforeSafetyView);
assert.match(byId("display-reset-status").textContent,/Previous display preferences restored/);
handlers["clear-all-pins:click"]();
handlers["reset-settings:click"]();

// Offline JSON backup preview, explicit consent, bounded input and undo.
handlers["quick-view-fitness:click"]();
handlers["pin-weather:click"]();
handlers["quick-save-my-view:click"]();
byId("setting-large-text").checked=true;
handlers["setting-large-text:change"].call(byId("setting-large-text"));
byId("setting-refresh-minutes").value="10";
handlers["setting-refresh-minutes:change"].call(byId("setting-refresh-minutes"));
const expectedExportState = state["tris.dashboard.display.v1"];
const expectedExportPins = state["tris.dashboard.pins.v1"];
const expectedExportMyView = state["tris.dashboard.my-view.v1"];
handlers["export-layout:click"]();
const exportedLayout = JSON.parse(byId("layout-backup-json").value);
assert.equal(exportedLayout.version,1);
assert.equal(JSON.stringify(exportedLayout.display),expectedExportState);
assert.deepEqual(exportedLayout.pins,JSON.parse(expectedExportPins));
assert.deepEqual(exportedLayout.myView,JSON.parse(expectedExportMyView));
assert.equal(byId("layout-backup-json").value.includes("api_key"),false);
assert.equal(byId("clear-layout-json").disabled,false);
assert.equal(byId("select-layout-json").disabled,false);
assert.match(byId("layout-editor-count").textContent,/ \/ 16,000 characters/);
handlers["select-layout-json:click"]();
assert.equal(byId("layout-backup-json").selected,true);

handlers["reset-settings:click"]();
handlers["clear-all-pins:click"]();
handlers["clear-my-view:click"]();
const beforeRestoreSettings = state["tris.dashboard.display.v1"];
const beforeRestorePins = state["tris.dashboard.pins.v1"];
const beforeRestoreView = state["tris.dashboard.my-view.v1"];
assert.equal(byId("import-layout").disabled,true);
handlers["preview-layout:click"]();
assert.match(byId("layout-preview-status").textContent,/Preview: 2 visible panels; 1 pins/);
assert.match(byId("layout-preview-status").textContent,/Changes: display; pins; My view;/);

assert.equal(byId("import-layout").disabled,true);
assert.equal(byId("confirm-layout-import").disabled,false);
byId("confirm-layout-import").checked=true;
handlers["confirm-layout-import:change"].call(byId("confirm-layout-import"));
assert.equal(byId("import-layout").disabled,false);
handlers["import-layout:click"]();
assert.equal(state["tris.dashboard.display.v1"],expectedExportState);
assert.equal(state["tris.dashboard.pins.v1"],expectedExportPins);
assert.equal(state["tris.dashboard.my-view.v1"],expectedExportMyView);
assert.equal(byId("setting-large-text").checked,true);
assert.equal(byId("setting-refresh-minutes").value,"10");
assert.equal(byId("panel-portfolio").hidden,true);
assert.equal(byId("panel-fitness").hidden,false);
assert.equal(byId("pin-weather").attributes["aria-pressed"],"true");
assert.equal(byId("import-layout").disabled,true);
assert.equal(byId("undo-layout-import").disabled,false);
handlers["undo-layout-import:click"]();
assert.equal(state["tris.dashboard.display.v1"],beforeRestoreSettings);
assert.equal(state["tris.dashboard.pins.v1"],beforeRestorePins);
assert.equal(state["tris.dashboard.my-view.v1"],beforeRestoreView);
assert.equal(byId("undo-layout-import").disabled,true);
assert.match(byId("layout-backup-status").textContent,/Previous display settings/);
// Invalid, huge and unsupported inputs are rejected without mutation.
for (const invalid of ["{broken","x".repeat(16001),
  JSON.stringify({version:2,display:exportedLayout.display,pins:[],myView:null}),
  JSON.stringify({version:1,display:exportedLayout.display,pins:["unknown"],myView:null})]) {
  byId("layout-backup-json").value=invalid;
  handlers["layout-backup-json:input"]();
  handlers["preview-layout:click"]();
  assert.match(byId("layout-preview-status").textContent,/Backup rejected/);
  assert.equal(byId("import-layout").disabled,true);
  assert.equal(state["tris.dashboard.display.v1"],beforeRestoreSettings);
  assert.equal(state["tris.dashboard.pins.v1"],beforeRestorePins);
}
// Editing a validated preview invalidates consent and prevents stale imports.
byId("layout-backup-json").value=JSON.stringify(exportedLayout);
handlers["layout-backup-json:input"]();
handlers["preview-layout:click"]();
byId("confirm-layout-import").checked=true;
handlers["confirm-layout-import:change"].call(byId("confirm-layout-import"));
byId("layout-backup-json").value="{}";
handlers["layout-backup-json:input"]();
assert.equal(byId("import-layout").disabled,true);
handlers["import-layout:click"]();
assert.match(byId("layout-backup-status").textContent,/preview and confirmation required/);
assert.equal(state["tris.dashboard.display.v1"],beforeRestoreSettings);
handlers["clear-layout-json:click"]();
assert.equal(byId("layout-backup-json").value,"");
assert.equal(byId("select-layout-json").disabled,true);
assert.equal(byId("clear-layout-json").disabled,true);
assert.equal(byId("layout-editor-count").textContent,"0 / 16,000 characters");
assert.equal(byId("import-layout").disabled,true);
assert.equal(state["tris.dashboard.display.v1"],beforeRestoreSettings);
// Strict schema: unknown root and display fields are not accepted.
const safeBackup = {version:1,display:JSON.parse(state["tris.dashboard.display.v1"]),
  pins:JSON.parse(state["tris.dashboard.pins.v1"]),
  myView:state["tris.dashboard.my-view.v1"] ? JSON.parse(state["tris.dashboard.my-view.v1"]) : null};
for (const bad of [Object.assign({},safeBackup,{unexpected:"extra"}),
  Object.assign({},safeBackup,{display:Object.assign({},safeBackup.display,{apiKey:"extra"})})]) {
  byId("layout-backup-json").value=JSON.stringify(bad);
  handlers["layout-backup-json:input"]();
  handlers["preview-layout:click"]();
  assert.match(byId("layout-preview-status").textContent,/Unexpected or missing backup fields/);
  assert.equal(byId("confirm-layout-import").disabled,true);
  assert.equal(state["tris.dashboard.display.v1"],beforeRestoreSettings);
}
// Exact backup of the current layout cannot create a no-op restore.
byId("layout-backup-json").value=JSON.stringify(safeBackup);
handlers["layout-backup-json:input"]();
handlers["preview-layout:click"]();
assert.match(byId("layout-preview-status").textContent,/Nothing to restore/);
assert.equal(byId("import-layout").disabled,true);
assert.equal(byId("confirm-layout-import").disabled,true);
// Altering the current layout after preview must invalidate restore consent.
byId("layout-backup-json").value=JSON.stringify(exportedLayout);
handlers["layout-backup-json:input"]();
handlers["preview-layout:click"]();
assert.equal(byId("confirm-layout-import").disabled,false);
byId("confirm-layout-import").checked=true;
handlers["confirm-layout-import:change"].call(byId("confirm-layout-import"));
handlers["quick-view-fitness:click"]();
const changedAfterPreview = state["tris.dashboard.display.v1"];
handlers["import-layout:click"]();
assert.match(byId("layout-backup-status").textContent,/settings changed after preview/);
assert.equal(state["tris.dashboard.display.v1"],changedAfterPreview);
assert.equal(byId("import-layout").disabled,true);
assert.equal(byId("confirm-layout-import").disabled,true);
handlers["quick-view-all:click"]();

// Selective restore: each section can be imported independently and undone.
const restoreScopeIds=["restore-scope-display","restore-scope-pins","restore-scope-my-view"];
const restoreStorageKeys=["tris.dashboard.display.v1","tris.dashboard.pins.v1","tris.dashboard.my-view.v1"];
for (let section=0;section<restoreScopeIds.length;section++) {
  const before=restoreStorageKeys.map(key=>state[key]);
  byId("layout-backup-json").value=JSON.stringify(exportedLayout);
  handlers["layout-backup-json:input"]();
  for (let i=0;i<restoreScopeIds.length;i++) {
    byId(restoreScopeIds[i]).checked=(i===section);
    handlers[restoreScopeIds[i]+":change"]();
  }
  handlers["preview-layout:click"]();
  assert.equal(byId("confirm-layout-import").disabled,false);
  byId("confirm-layout-import").checked=true;
  handlers["confirm-layout-import:change"].call(byId("confirm-layout-import"));
  handlers["import-layout:click"]();
  for (let i=0;i<restoreStorageKeys.length;i++) {
    assert.equal(state[restoreStorageKeys[i]],i===section ?
      [expectedExportState,expectedExportPins,expectedExportMyView][i] : before[i]);
  }
  assert.equal(byId("undo-layout-import").disabled,false);
  handlers["undo-layout-import:click"]();
  restoreStorageKeys.forEach((key,i)=>assert.equal(state[key],before[i]));
}
// No scope selected cannot stage a restore.
for (const id of restoreScopeIds) { byId(id).checked=false; handlers[id+":change"](); }
handlers["preview-layout:click"]();
assert.match(byId("layout-preview-status").textContent,/Select at least one section/);
assert.equal(byId("import-layout").disabled,true);
// Changing scopes after consent blocks stale approval, even without an input event.
byId(restoreScopeIds[0]).checked=true;
handlers[restoreScopeIds[0]+":change"]();
handlers["preview-layout:click"]();
assert.equal(byId("confirm-layout-import").disabled,false);
byId("confirm-layout-import").checked=true;
handlers["confirm-layout-import:change"].call(byId("confirm-layout-import"));
byId(restoreScopeIds[1]).checked=true;
handlers["import-layout:click"]();
assert.match(byId("layout-backup-status").textContent,/preview and confirmation required/);
assert.equal(byId("import-layout").disabled,true);
for (const id of restoreScopeIds) { byId(id).checked=true; handlers[id+":change"](); }

// Restore scope shortcuts are live, guard confirmation, and show exact changes.
handlers["restore-scope-none:click"]();
assert.equal(byId("restore-scope-none").disabled,true);
assert.equal(byId("restore-scope-all").disabled,false);
assert.match(byId("restore-scope-summary").textContent,/0 of 3 sections selected/);
assert.equal(byId("confirm-layout-import").disabled,true);
handlers["preview-layout:click"]();
assert.match(byId("layout-preview-status").textContent,/Select at least one section/);
handlers["restore-scope-all:click"]();
assert.equal(byId("restore-scope-all").disabled,true);
assert.equal(byId("restore-scope-none").disabled,false);
assert.match(byId("restore-scope-summary").textContent,/3 of 3 sections selected/);
byId("layout-backup-json").value=JSON.stringify(exportedLayout);
handlers["layout-backup-json:input"]();
handlers["preview-layout:click"]();
assert.match(byId("layout-preview-changes").textContent,/Display: hide portfolio, quotes/);
assert.match(byId("layout-preview-changes").textContent,/Pins: add weather/);
assert.match(byId("layout-preview-changes").textContent,/My view: save/);
byId("confirm-layout-import").checked=true;
handlers["confirm-layout-import:change"].call(byId("confirm-layout-import"));
assert.equal(byId("import-layout").disabled,false);
handlers["restore-scope-none:click"]();
assert.equal(byId("import-layout").disabled,true);
assert.equal(byId("layout-preview-changes").textContent,"Detailed changes appear after preview.");
assert.equal(state["tris.dashboard.pins.v1"],beforeRestorePins);
byId("restore-scope-pins").checked=true;
handlers["restore-scope-pins:change"]();
assert.match(byId("restore-scope-summary").textContent,/1 of 3 sections selected: pins/);
handlers["preview-layout:click"]();
assert.equal(byId("layout-preview-changes").textContent,"Pins: add weather");
handlers["restore-scope-all:click"]();
assert.equal(byId("confirm-layout-import").disabled,true);

// Backup editor draft protection: two-step replace, cancellation, live preview state.
const originalBackupDraft = "{\"my draft\":true}";
byId("layout-backup-json").value=originalBackupDraft;
handlers["layout-backup-json:input"]();
assert.equal(byId("preview-layout").disabled,false);
handlers["export-layout:click"]();
assert.equal(byId("layout-backup-json").value,originalBackupDraft);
assert.equal(byId("export-layout").textContent,"Replace existing JSON");
assert.equal(byId("cancel-backup-overwrite").disabled,false);
handlers["cancel-backup-overwrite:click"]();
assert.equal(byId("layout-backup-json").value,originalBackupDraft);
assert.equal(byId("export-layout").textContent,"Create backup JSON");
handlers["export-layout:click"]();
byId("layout-backup-json").value=originalBackupDraft+" edited";
handlers["layout-backup-json:input"]();
assert.equal(byId("cancel-backup-overwrite").disabled,true);
handlers["export-layout:click"]();
assert.equal(byId("layout-backup-json").value,originalBackupDraft+" edited");
handlers["export-layout:click"]();
assert.equal(JSON.parse(byId("layout-backup-json").value).version,1);
assert.equal(byId("export-layout").textContent,"Create backup JSON");
assert.equal(byId("cancel-backup-overwrite").disabled,true);
assert.equal(byId("cancel-layout-preview").disabled,true);
byId("layout-backup-json").value=JSON.stringify(exportedLayout);
handlers["layout-backup-json:input"]();
handlers["preview-layout:click"]();
assert.equal(byId("cancel-layout-preview").disabled,false);
assert.equal(byId("confirm-layout-import").disabled,false);
handlers["cancel-layout-preview:click"]();
assert.equal(byId("confirm-layout-import").disabled,true);
assert.equal(byId("import-layout").disabled,true);
assert.equal(byId("cancel-layout-preview").disabled,true);
assert.equal(byId("layout-backup-json").value,JSON.stringify(exportedLayout));
byId("layout-backup-json").value="";
handlers["layout-backup-json:input"]();
assert.equal(byId("preview-layout").disabled,true);
handlers["preview-layout:click"]();
assert.match(byId("layout-preview-status").textContent,/Paste or create backup JSON/);
byId("layout-backup-json").value="x".repeat(16001);
handlers["layout-backup-json:input"]();
assert.equal(byId("preview-layout").disabled,true);
assert.match(byId("layout-editor-count").textContent,/exceeds restore limit/);
assert.equal(state["tris.dashboard.display.v1"],beforeRestoreSettings);

// Visible-panel navigation respects display order, filters, favorites and keyboard input.
handlers["clear-temporary-filters:click"]();
handlers["quick-view-all:click"]();
assert.equal(byId("navigate-previous-panel").disabled,true);
assert.equal(byId("navigate-next-panel").disabled,false);
assert.match(byId("panel-navigation-status").textContent,/9 visible panels/);
handlers["navigate-next-panel:click"]();
assert.equal(byId("panel-portfolio").focused,true);
assert.match(byId("panel-navigation-status").textContent,/portfolio .* 1 of 9/);
handlers["navigate-next-panel:click"]();
assert.equal(byId("panel-quotes").focused,true);
handlers["navigate-previous-panel:click"]();
assert.match(byId("panel-navigation-status").textContent,/portfolio .* 1 of 9/);
assert.equal(byId("navigate-previous-panel").disabled,true);
// Only the filtered matching card is navigable; no hidden panels are focused.
byId("panel-search-input").value="fitness";
handlers["panel-search-input:input"].call(byId("panel-search-input"));
assert.match(byId("panel-navigation-status").textContent,/No panel selected .* 1 visible panels/);
assert.equal(byId("navigate-previous-panel").disabled,true);
handlers["navigate-next-panel:click"]();
assert.equal(byId("panel-fitness").focused,true);
assert.equal(byId("navigate-next-panel").disabled,true);
assert.match(byId("panel-navigation-status").textContent,/fitness .* 1 of 1/);
// Alt+Left/Right navigation leaves editable elements and defaults untouched.
handlers["panel-search-clear:click"]();
let preventedPanelNav=false;
handlers["document:keydown"]({keyCode:39,altKey:true,target:{tagName:"INPUT"},preventDefault(){preventedPanelNav=true;}});
assert.equal(preventedPanelNav,false);
handlers["document:keydown"]({keyCode:37,altKey:true,target:{tagName:"DIV"},preventDefault(){preventedPanelNav=true;}});
assert.equal(preventedPanelNav,true);
assert.match(byId("panel-navigation-status").textContent,/server .* 8 of 9/);
preventedPanelNav=false;
handlers["document:keydown"]({keyCode:39,altKey:true,target:{tagName:"DIV"},preventDefault(){preventedPanelNav=true;}});
assert.equal(preventedPanelNav,true);
assert.match(byId("panel-navigation-status").textContent,/fitness .* 9 of 9/);
// Favorites float to front and invalidating filters never changes saved layout.
const originalPanelStorage=state["tris.dashboard.display.v1"];
handlers["pin-weather:click"]();
assert.match(byId("panel-navigation-status").textContent,/fitness .* 9 of 9/);
byId("panel-search-input").value="weather";
handlers["panel-search-input:input"].call(byId("panel-search-input"));
assert.match(byId("panel-navigation-status").textContent,/1 visible panels/);
handlers["navigate-next-panel:click"]();
assert.match(byId("panel-navigation-status").textContent,/weather .* 1 of 1/);
handlers["panel-search-clear:click"]();
assert.match(byId("panel-navigation-status").textContent,/weather .* 1 of 9/);
assert.equal(state["tris.dashboard.display.v1"],originalPanelStorage);
handlers["pin-weather:click"]();

console.log("Frontend success, retry, quote display and invalid-data smoke tests passed.");
