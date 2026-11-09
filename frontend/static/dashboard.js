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
  var suppressNextReconnectRefresh = false;
  var overviewSequence = 0;
  var overviewRetryTimer = null;
  var overviewRetryGeneration = 0;
  var consecutiveOverviewFailures = 0;
  var lastSuccessfulOverview = null;
  var lastSuccessfulOverviewAt = 0;
  var refreshButton = document.getElementById("refresh-button");
  var weatherFahrenheit = false;
  var lastWeatherInfo = null;
  try { weatherFahrenheit = window.localStorage.getItem("tris.dashboard.weather.fahrenheit") === "true"; }
  catch (error) {}
  var agendaExpanded = false;
  var lastAgendaInfo = null;

  function pad(number) { return number < 10 ? "0" + number : String(number); }

  function validCalendarDate(value) {
    if (typeof value !== "string" ||
        !/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(value)) { return false; }
    var year = Number(value.slice(0, 4));
    var month = Number(value.slice(5, 7));
    var day = Number(value.slice(8, 10));
    if (year < 1 || month < 1 || month > 12 || day < 1 || day > 31) { return false; }
    var dateValue = new Date(Date.UTC(year, month - 1, day));
    return dateValue.getUTCFullYear() === year &&
      dateValue.getUTCMonth() + 1 === month && dateValue.getUTCDate() === day;
  }
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
        if (!suppressNextReconnectRefresh && !document.hidden &&
            !window.trisDashboardRefreshPaused &&
            (!overviewRequest || overviewRequest.readyState === 4)) { loadOverview(true); }
      }
    } else {
      wasOffline = true;
      offlineBanner.hidden = false;
      offlineBanner.textContent = "MacBook server is unreachable. " +
        (lastSuccessfulOverview ? "Last successful update at " + lastSuccessfulOverview + ". Showing saved screen values." :
        "No dashboard data has been loaded yet.");
      connection.textContent = "Server offline";
      text("glance-connection", "Offline");
      indicator.className = "indicator offline";
      lastCheck.textContent = "Reconnect automatically every 15 seconds";
    }
  }

  function checkServer() {
    if (document.hidden) { return false; }
    if (request && request.readyState !== 4) { return true; }
    var now = new Date().getTime();
    if (now < lastRequestStarted) { lastRequestStarted = 0; }
    if (now - lastRequestStarted < 2000) { return false; }
    lastRequestStarted = now;
    var sequence = ++requestSequence;
    if (request && request.readyState !== 4) { request.abort(); }
    request = get("/healthz", function (online, xhr) {
      if (online) {
        try { online = JSON.parse(xhr.responseText).status === "ok"; }
        catch (error) { online = false; }
      }
      if (sequence === requestSequence) {
        setConnection(online);
        suppressNextReconnectRefresh = false;
      }
    });
    return true;
  }

  function statusText(info) {
    if (!info || !info.available) { return "Unavailable"; }
    return info.stale ? "Last known data (stale)" +
      (typeof info.cache_age_seconds === "number" && isFinite(info.cache_age_seconds) &&
       info.cache_age_seconds >= 0 ? " · " + Math.floor(info.cache_age_seconds / 60) + " min old" : "") :
      "Updated " + (typeof info.updated_at === "string" ?
        info.updated_at.replace("T", " ").slice(0, 16) + " UTC" : "recently");
  }

  var sourceMarkers = {};
  function showSummary(payload) {
    var names = ["weather", "github", "trello", "portfolio", "fitness", "dividends", "agenda", "quotes"];
    var active = 0;
    var unavailable = 0;
    var stale = 0;
    var unconfigured = 0;
    var sourceIssues = [];
    var issues = document.getElementById("source-health-links");
    while (issues.firstChild) { issues.removeChild(issues.firstChild); }
    for (var i = 0; i < names.length; i++) {
      var name = names[i];
      var info = payload[name];
      var state = "unavailable";
      var label = "Unavailable";
      if (info && info.available) {
        active++;
        state = "ready";
        label = "Ready";
        if (info.stale || (info.quality && info.quality.outdated)) {
          stale++;
          state = "stale";
          label = "Stale";
          var age = info.cache_age_seconds;
          if (typeof age === "number" && isFinite(age) && age >= 0) {
            label += " · " + Math.floor(age / 60) + " min old";
          }
        }
      } else if (info && info.configured === false) {
        unconfigured++;
        state = "unconfigured";
        label = "Not configured";
      } else {
        unavailable++;
      }
      var card = document.getElementById("panel-" + name);
      var marker = sourceMarkers[name];
      if (!marker) {
        marker = document.createElement("small");
        marker.id = "source-state-" + name;
        card.appendChild(marker);
        sourceMarkers[name] = marker;
      }
      marker.className = "source-state source-state-" + state;
      marker.textContent = "Source: " + label;
      if (state === "stale" || state === "unavailable") {
        var staleAge = info && info.cache_age_seconds;
        sourceIssues.push(name + (state === "stale" ? " stale" +
          (typeof staleAge === "number" && isFinite(staleAge) && staleAge >= 0 ?
            " (" + Math.floor(staleAge / 60) + " min old)" : "") : " unavailable"));
        (function (panelName, statusLabel) {
          var link = document.createElement("a");
          link.id = "source-health-link-" + panelName;
          link.href = "#panel-" + panelName;
          link.className = "source-health-link";
          link.textContent = panelName + " · " + statusLabel;
          link.addEventListener("click", function () {
            if (typeof window.trisDashboardRevealPanel === "function") {
              window.trisDashboardRevealPanel(panelName);
            }
          });
          issues.appendChild(link);
        }(name, label));
      }
    }
    issues.hidden = sourceIssues.length === 0;
    text("source-health-details", sourceIssues.length ?
      "Needs attention: " + sourceIssues.length + " sources · " + sourceIssues.join(" · ") +
      " · Select a source below to inspect it." :
      "No stale or unavailable configured sources.");
    text("glance-sources", active + "/" + names.length + " ready" +
      (stale ? " · " + stale + " stale" : "") +
      (unavailable ? " · " + unavailable + " unavailable" : "") +
      (unconfigured ? " · " + unconfigured + " not configured" : ""));
    var now = new Date();
    text("glance-updated", pad(now.getHours()) + ":" + pad(now.getMinutes()));
  }

  function showQuotes(info) {
    var list = document.getElementById("quotes-list");
    while (list.firstChild) { list.removeChild(list.firstChild); }
    if (!info || !info.available) {
      text("quotes-summary", info && info.configured ? "Provider unavailable" : "Not configured");
      text("quotes-updated", "Optional source · no live pricing guarantee");
      return;
    }
    var validQuotes = Object.prototype.toString.call(info.quotes) === "[object Array]";
    var rows = validQuotes ? info.quotes : [];
    if (!validQuotes) {
      var invalidQuotes = document.createElement("div");
      invalidQuotes.className = "repo-row";
      invalidQuotes.textContent = "Quote list invalid. Provider data could not be displayed.";
      list.appendChild(invalidQuotes);
    }
    if (validQuotes && !rows.length) {
      var noQuotes = document.createElement("div");
      noQuotes.className = "repo-row";
      noQuotes.textContent = "No provider quotes returned. No prices have been inferred.";
      list.appendChild(noQuotes);
    }
    var successful = 0;
    var outdated = 0;
    var oldestHours = null;
    for (var i = 0; i < rows.length; i++) {
      if (!rows[i] || typeof rows[i] !== "object") {
        var invalidQuoteRow = document.createElement("div");
        invalidQuoteRow.className = "repo-row";
        invalidQuoteRow.textContent = "Quote entry unavailable";
        list.appendChild(invalidQuoteRow);
        continue;
      }
      var line = document.createElement("div");
      line.className = "repo-row";
      var numericPrice = Number(rows[i].price);
      if (rows[i].price !== null && rows[i].price !== "" &&
          typeof rows[i].price !== "boolean" && isFinite(numericPrice) &&
          numericPrice > 0 &&
          typeof rows[i].reported_at_utc === "string" &&
          /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}/.test(rows[i].reported_at_utc)) {
        successful++;
        if (typeof rows[i].age_hours === "number" && isFinite(rows[i].age_hours) && rows[i].age_hours >= 0) {
          oldestHours = oldestHours === null ? rows[i].age_hours : Math.max(oldestHours, rows[i].age_hours);
        }
        if (rows[i].outdated) { outdated++; }
        line.textContent = rows[i].symbol + " · " + rows[i].price + " " + rows[i].currency +
          " · " + rows[i].reported_at_utc.replace("T", " ").slice(0, 16) + " UTC" +
          (typeof rows[i].age_hours === "number" && isFinite(rows[i].age_hours) && rows[i].age_hours >= 0 ?
            " · " + rows[i].age_hours + "h old" : "") +
          (rows[i].outdated ? " · OUTDATED" : "");
      } else {
        line.textContent = (rows[i] && typeof rows[i].symbol === "string" ?
          rows[i].symbol : "Unknown symbol") + " · Quote unavailable";
      }
      list.appendChild(line);
    }
    if (rows.length && successful === 0) {
      var noReportedPrices = document.createElement("div");
      noReportedPrices.className = "repo-row";
      noReportedPrices.textContent = "No usable price with a provider timestamp. Valuation stays unavailable.";
      list.appendChild(noReportedPrices);
    }
    text("quotes-summary", successful + "/" + rows.length + " quotes reported" +
      (outdated ? " · " + outdated + " outdated" : "") +
      (oldestHours !== null ? " · Oldest reading " + oldestHours + "h ago" : ""));
    text("quotes-updated", "Twelve Data · Provider timestamps · not guaranteed real-time" +
      (info.stale ? " · Cached stale" : ""));
  }

  function showPortfolio(info, valuation) {
    var list = document.getElementById("portfolio-list");
    while (list.firstChild) { list.removeChild(list.firstChild); }
    var quotePanel = document.getElementById("portfolio-quote-values");
    while (quotePanel.firstChild) { quotePanel.removeChild(quotePanel.firstChild); }
    if (!info || !info.available) {
      text("portfolio-summary", "Not available");
      quotePanel.textContent = "Quote-based valuation unavailable";
      text("portfolio-updated", info && info.configured ? "Check MacBook snapshot" : "Configure on MacBook");
      return;
    }
    var validPositions = Object.prototype.toString.call(info.positions) === "[object Array]";
    var originalPositions = validPositions ? info.positions : [];
    if (!validPositions) {
      var invalidPositions = document.createElement("div");
      invalidPositions.className = "repo-row";
      invalidPositions.textContent = "Portfolio holdings list invalid. Check the manual snapshot file.";
      list.appendChild(invalidPositions);
    }
    var positions = originalPositions.filter(function (position) {
      return position && typeof position === "object" &&
        typeof position.symbol === "string" && position.symbol.length > 0 &&
        position.quantity !== null && position.quantity !== "" &&
        isFinite(Number(position.quantity)) && Number(position.quantity) >= 0;
    });
    if (positions.length !== originalPositions.length) {
      var invalidHolding = document.createElement("div");
      invalidHolding.className = "repo-row";
      invalidHolding.textContent = "Skipped " + (originalPositions.length - positions.length) +
        " invalid holding entries.";
      list.appendChild(invalidHolding);
    }
    text("portfolio-summary", positions.length + " holdings");
    if (validPositions && !positions.length) {
      var noPositions = document.createElement("div");
      noPositions.className = "repo-row";
      noPositions.textContent = "No holdings in the manual snapshot.";
      list.appendChild(noPositions);
    }
    for (var i = 0; i < positions.length; i++) {
      var item = positions[i];
      var row = document.createElement("div");
      row.className = "repo-row";
      var knownValue = item.market_value !== null &&
        typeof item.market_value !== "undefined" &&
        item.market_value !== "" && typeof item.market_value !== "boolean" &&
        isFinite(Number(item.market_value)) && Number(item.market_value) >= 0 &&
        typeof item.currency === "string" && item.currency.length > 0;
      row.textContent = item.symbol + " · " + item.quantity + " shares" +
        (knownValue ? " · " + item.market_value + " " + item.currency :
          " · price unavailable");
      list.appendChild(row);
    }
    var totals = info.totals || {};
    var keys = Object.keys(totals);
    if (keys.length) {
      var total = document.createElement("div");
      total.className = "portfolio-total";
      var parts = [];
      var invalidValueCount = 0;
      for (var j = 0; j < keys.length; j++) {
        var manualTotal = totals[keys[j]];
        if (manualTotal === null || manualTotal === "" ||
            typeof manualTotal === "boolean" ||
            !isFinite(Number(manualTotal)) || Number(manualTotal) < 0) {
          invalidValueCount++;
          continue;
        }
        parts.push(keys[j] + " " + manualTotal);
      }
      if (parts.length) {
        total.textContent = "Values: " + parts.join(" / ") +
          (info.valuation_complete && !invalidValueCount ? "" : " (partial)");
        list.appendChild(total);
      }
      if (invalidValueCount) {
        var invalidValues = document.createElement("div");
        invalidValues.className = "repo-row";
        invalidValues.textContent = "Excluded " + invalidValueCount +
          " invalid manual valuation totals.";
        list.appendChild(invalidValues);
      }
    }
    var priceCoverage = info.price_coverage_by_currency || {};
    var coverageKeys = Object.keys(priceCoverage);
    for (var pk = 0; pk < coverageKeys.length; pk++) {
      var currencyKey = coverageKeys[pk];
      var coverage = priceCoverage[currencyKey];
      if (!coverage || typeof coverage.total !== "number" || typeof coverage.priced !== "number" ||
          !isFinite(coverage.total) || !isFinite(coverage.priced) ||
          coverage.total < 0 || coverage.priced < 0 || coverage.priced > coverage.total) { continue; }
      var coverageLine = document.createElement("div");
      coverageLine.className = "repo-row";
      coverageLine.textContent = "Manual price coverage · " + currencyKey + " " +
        coverage.priced + "/" + coverage.total + " holdings priced";
      list.appendChild(coverageLine);
    }
    var pricePercent = info.price_coverage_percent_by_currency || {};
    var percentCurrencies = Object.keys(pricePercent);
    for (var pp = 0; pp < percentCurrencies.length; pp++) {
      var percentValue = pricePercent[percentCurrencies[pp]];
      if (typeof percentValue !== "number" || !isFinite(percentValue) ||
          percentValue < 0 || percentValue > 100) { continue; }
      var percentLine = document.createElement("div");
      percentLine.className = "repo-row";
      percentLine.textContent = "Manual price completeness · " +
        percentCurrencies[pp] + " " + percentValue + "% (not live quotes)";
      list.appendChild(percentLine);
      var coverageBar = document.createElement("div");
      coverageBar.className = "allocation-row";
      var coverageCaption = document.createElement("span");
      coverageCaption.textContent = "Price coverage " + percentCurrencies[pp];
      var coverageTrack = document.createElement("span");
      coverageTrack.className = "allocation-track";
      var coverageFill = document.createElement("span");
      coverageFill.className = "allocation-fill";
      coverageFill.style.width = percentValue + "%";
      coverageTrack.appendChild(coverageFill);
      coverageBar.appendChild(coverageCaption);
      coverageBar.appendChild(coverageTrack);
      list.appendChild(coverageBar);
    }
    var zeroQuantity = info.zero_quantity_symbols_by_currency || {};
    var zeroCurrencies = Object.keys(zeroQuantity);
    for (var z = 0; z < zeroCurrencies.length; z++) {
      var rawSymbols = zeroQuantity[zeroCurrencies[z]];
      if (Object.prototype.toString.call(rawSymbols) !== "[object Array]") {
        var invalidZeroList = document.createElement("div");
        invalidZeroList.className = "repo-row";
        invalidZeroList.textContent = "Zero-quantity symbol list unavailable · " + zeroCurrencies[z];
        list.appendChild(invalidZeroList);
        continue;
      }
      var symbols = rawSymbols.filter(function (symbol) {
        return typeof symbol === "string" && symbol.length > 0;
      });
      if (symbols.length !== rawSymbols.length) {
        var invalidZeroSymbols = document.createElement("div");
        invalidZeroSymbols.className = "repo-row";
        invalidZeroSymbols.textContent = "Skipped " + (rawSymbols.length - symbols.length) +
          " invalid zero-quantity symbols · " + zeroCurrencies[z];
        list.appendChild(invalidZeroSymbols);
      }
      if (!symbols.length) { continue; }
      var zeroRow = document.createElement("div");
      zeroRow.className = "repo-row";
      zeroRow.textContent = "Review zero-quantity positions · " +
        zeroCurrencies[z] + ": " + symbols.join(", ") + " (manual snapshot)";
      list.appendChild(zeroRow);
    }
    var allocations = info.currency_allocations || {};
    var allocationCurrencies = Object.keys(allocations);
    for (var c = 0; c < allocationCurrencies.length; c++) {
      var rawShares = allocations[allocationCurrencies[c]];
      if (Object.prototype.toString.call(rawShares) !== "[object Array]") {
        var invalidAllocation = document.createElement("div");
        invalidAllocation.className = "repo-row";
        invalidAllocation.textContent = "Allocation unavailable · " + allocationCurrencies[c];
        list.appendChild(invalidAllocation);
        continue;
      }
      var shares = rawShares.filter(function (share) {
        return share && typeof share === "object" &&
          typeof share.symbol === "string" &&
          share.percent !== null && share.percent !== "" &&
          isFinite(Number(share.percent)) &&
          Number(share.percent) >= 0 && Number(share.percent) <= 100;
      });
      if (shares.length !== rawShares.length) {
        var skippedShares = document.createElement("div");
        skippedShares.className = "repo-row";
        skippedShares.textContent = "Skipped " + (rawShares.length - shares.length) +
          " invalid allocation entries · " + allocationCurrencies[c];
        list.appendChild(skippedShares);
      }
      var allocationLine = document.createElement("div");
      allocationLine.className = "repo-row";
      var breakdown = [];
      for (var a = 0; a < shares.length; a++) {
        breakdown.push(shares[a].symbol + " " + shares[a].percent + "%");
      }
      allocationLine.textContent = "Manual " + allocationCurrencies[c] + " allocation: " + breakdown.join(" · ");
      list.appendChild(allocationLine);
      for (var ai = 0; ai < shares.length; ai++) {
        var percent = Number(shares[ai].percent);
        if (!isFinite(percent) || percent < 0 || percent > 100) { continue; }
        var barRow = document.createElement("div");
        barRow.className = "allocation-row";
        var caption = document.createElement("span");
        caption.textContent = shares[ai].symbol + " · " + shares[ai].percent + "%";
        var track = document.createElement("span");
        track.className = "allocation-track";
        var fill = document.createElement("span");
        fill.className = "allocation-fill";
        fill.style.width = percent + "%";
        track.appendChild(fill);
        barRow.appendChild(caption);
        barRow.appendChild(track);
        list.appendChild(barRow);
      }
    }
    var concentration = info.top_three_concentration_percent || {};
    var concentrationCurrencies = Object.keys(concentration);
    for (var cc = 0; cc < concentrationCurrencies.length; cc++) {
      var concentrationRow = document.createElement("div");
      concentrationRow.className = "repo-row";
      concentrationRow.textContent = "Top 3 manual holdings · " + concentrationCurrencies[cc] +
        " " + concentration[concentrationCurrencies[cc]] + "% of priced holdings";
      list.appendChild(concentrationRow);
    }
    var missingPrices = info.unpriced_positions_by_currency || {};
    var missingCurrencies = Object.keys(missingPrices);
    for (var mp = 0; mp < missingCurrencies.length; mp++) {
      var missingLine = document.createElement("div");
      missingLine.className = "repo-row";
      missingLine.textContent = "Manual price missing · " + missingCurrencies[mp] + " " +
        missingPrices[missingCurrencies[mp]] + " holdings (excluded from manual valuation)" +
        ((info.unpriced_symbols_by_currency || {})[missingCurrencies[mp]] &&
         (info.unpriced_symbols_by_currency || {})[missingCurrencies[mp]].length ?
          " · " + (info.unpriced_symbols_by_currency || {})[missingCurrencies[mp]].join(", ") : "");
      list.appendChild(missingLine);
    }
    var largestHoldings = info.largest_holdings || {};
    var largestCurrencies = Object.keys(largestHoldings);
    for (var lh = 0; lh < largestCurrencies.length; lh++) {
      var lc = largestCurrencies[lh];
      var largest = largestHoldings[lc];
      if (!largest || typeof largest !== "object" ||
          typeof largest.symbol !== "string" || !largest.symbol ||
          largest.market_value === null || largest.market_value === "" ||
          typeof largest.market_value === "boolean" ||
          !isFinite(Number(largest.market_value)) ||
          Number(largest.market_value) < 0) { continue; }
      var largestRow = document.createElement("div");
      largestRow.className = "repo-row";
      largestRow.textContent = "Largest manually valued holding · " + lc + " " +
        largest.symbol + " (" + largest.market_value + ")";
      list.appendChild(largestRow);
    }
    if (valuation && valuation.available) {
      var totalsLabel = [];
      var quoteKeys = Object.keys(valuation.totals || {});
      var invalidQuoteTotals = 0;
      for (var v = 0; v < quoteKeys.length; v++) {
        var quoteTotal = valuation.totals[quoteKeys[v]];
        if (quoteTotal === null || quoteTotal === "" ||
            typeof quoteTotal === "boolean" ||
            !isFinite(Number(quoteTotal)) || Number(quoteTotal) < 0) {
          invalidQuoteTotals++;
          continue;
        }
        totalsLabel.push(quoteKeys[v] + " " + quoteTotal);
      }
      var matched = valuation.matched_count;
      var positionCount = valuation.position_count;
      var validCoverage = typeof matched === "number" && isFinite(matched) &&
        matched >= 0 && Math.floor(matched) === matched &&
        typeof positionCount === "number" && isFinite(positionCount) &&
        positionCount >= matched && Math.floor(positionCount) === positionCount;
      quotePanel.textContent = "Source-stamped quote value (" +
        (validCoverage ? matched + "/" + positionCount : "coverage unknown") + " holdings)" +
        (valuation.partial || invalidQuoteTotals || !validCoverage ? " · PARTIAL" : "") +
        (valuation.stale ? " · Cached stale" : "") +
        ": " + (totalsLabel.length ? totalsLabel.join(" / ") : "no valid totals") +
        " · Not guaranteed live";
    } else {
      quotePanel.textContent = "Quote-based valuation unavailable (manual snapshot unchanged)";
    }
    var quality = info.quality || {};
    text("portfolio-updated", "Manual prices · Snapshot " +
      (typeof info.as_of === "string" ? info.as_of.replace("T", " ").slice(0, 16) : "time unavailable") +
      (quality.outdated ? " · OUTDATED" +
        (typeof quality.threshold_hours === "number" &&
         isFinite(quality.threshold_hours) && quality.threshold_hours > 0 ?
         " (older than " + quality.threshold_hours + "h)" : " (threshold unavailable)") : ""));
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
    var invalidTotals = 0;
    for (var i = 0; i < currencies.length; i++) {
      var totalValue = totals[currencies[i]];
      if (totalValue === null || totalValue === "" ||
          typeof totalValue === "boolean" ||
          !isFinite(Number(totalValue)) || Number(totalValue) < 0) {
        invalidTotals++;
        continue;
      }
      label.push(currencies[i] + " " + totalValue);
    }
    text("dividend-summary", label.length ? label.join(" / ") :
      (invalidTotals ? "Payment totals unavailable" : "No recorded payments this month"));
    if (invalidTotals) {
      var invalidTotalRow = document.createElement("div");
      invalidTotalRow.className = "repo-row";
      invalidTotalRow.textContent = "Excluded " + invalidTotals +
        " invalid monthly dividend totals.";
      list.appendChild(invalidTotalRow);
    }
    if (info.record_count === 0) {
      var noPayments = document.createElement("div");
      noPayments.className = "repo-row";
      noPayments.textContent = "No confirmed dividend payments recorded. Add a local payment history file.";
      list.appendChild(noPayments);
    }
    var paymentCounts = info.monthly_payment_counts || {};
    var countCurrencies = Object.keys(paymentCounts);
    for (var pc = 0; pc < countCurrencies.length; pc++) {
      var paidCount = paymentCounts[countCurrencies[pc]];
      if (typeof paidCount !== "number" || !isFinite(paidCount) ||
          paidCount < 0 || Math.floor(paidCount) !== paidCount) { continue; }
      var paymentLine = document.createElement("div");
      paymentLine.className = "repo-row";
      paymentLine.textContent = "Confirmed " + info.month + " payments · " + countCurrencies[pc] +
        " " + paidCount + " entries";
      list.appendChild(paymentLine);
    }
    var monthlyPayers = info.monthly_unique_paying_symbols || {};
    var payerCurrencies = Object.keys(monthlyPayers);
    for (var up = 0; up < payerCurrencies.length; up++) {
      var payerCount = monthlyPayers[payerCurrencies[up]];
      if (typeof payerCount !== "number" || !isFinite(payerCount) ||
          payerCount < 0 || Math.floor(payerCount) !== payerCount) { continue; }
      var uniquePayerLine = document.createElement("div");
      uniquePayerLine.className = "repo-row";
      uniquePayerLine.textContent = "Distinct confirmed payers this month · " +
        payerCurrencies[up] + " " + payerCount + " holdings";
      list.appendChild(uniquePayerLine);
    }
    if (typeof info.days_since_last_confirmed_payment === "number" &&
        isFinite(info.days_since_last_confirmed_payment) &&
        info.days_since_last_confirmed_payment >= 0) {
      var daysSincePayment = document.createElement("div");
      daysSincePayment.className = "repo-row";
      daysSincePayment.textContent = "Days since most recent confirmed payment · " +
        info.days_since_last_confirmed_payment + " days (not a payout forecast)";
      list.appendChild(daysSincePayment);
    }
    if (info.last_confirmed_payment && typeof info.last_confirmed_payment.paid_on === "string" &&
        typeof info.last_confirmed_payment.symbol === "string" &&
        typeof info.last_confirmed_payment.amount === "string" &&
        typeof info.last_confirmed_payment.currency === "string") {
      var lastPayment = document.createElement("div");
      lastPayment.className = "repo-row";
      lastPayment.textContent = "Latest confirmed payment · " + info.last_confirmed_payment.paid_on +
        " · " + info.last_confirmed_payment.symbol + " · " +
        info.last_confirmed_payment.amount + " " + info.last_confirmed_payment.currency;
      list.appendChild(lastPayment);
    }
    var currentTop = info.monthly_top_payers || {};
    var topCurrencies = Object.keys(currentTop);
    for (var tp = 0; tp < topCurrencies.length; tp++) {
      var payerRow = document.createElement("div");
      payerRow.className = "repo-row";
      payerRow.textContent = "Highest confirmed payer this month · " + topCurrencies[tp] + " " +
        currentTop[topCurrencies[tp]].symbol + " (" + currentTop[topCurrencies[tp]].amount + ")";
      list.appendChild(payerRow);
    }
    var sixMonthTotals = info.six_month_totals || {};
    var historicCurrencies = Object.keys(sixMonthTotals);
    var sixMonthParts = [];
    var invalidSixMonthTotals = 0;
    for (var s = 0; s < historicCurrencies.length; s++) {
      var sixMonthValue = sixMonthTotals[historicCurrencies[s]];
      if (sixMonthValue === null || sixMonthValue === "" ||
          typeof sixMonthValue === "boolean" || !isFinite(Number(sixMonthValue)) ||
          Number(sixMonthValue) < 0) {
        invalidSixMonthTotals++;
        continue;
      }
      sixMonthParts.push(historicCurrencies[s] + " " + sixMonthValue);
    }
    if (sixMonthParts.length) {
      var sixMonth = document.createElement("div");
      sixMonth.className = "portfolio-total";
      sixMonth.textContent = "Confirmed last 6 months: " + sixMonthParts.join(" / ");
      list.appendChild(sixMonth);
    }
    if (invalidSixMonthTotals) {
      var invalidSixMonthRow = document.createElement("div");
      invalidSixMonthRow.className = "repo-row";
      invalidSixMonthRow.textContent = "Excluded " + invalidSixMonthTotals +
        " invalid six-month dividend totals.";
      list.appendChild(invalidSixMonthRow);
    }
    var dividendSymbols = info.six_month_paying_symbols || {};
    var dividendMonths = info.six_month_paid_months || {};
    var coverageCurrencies = Object.keys(dividendSymbols);
    for (var cv = 0; cv < coverageCurrencies.length; cv++) {
      var coverageCurrency = coverageCurrencies[cv];
      var coverageRow = document.createElement("div");
      coverageRow.className = "repo-row";
      coverageRow.textContent = "Confirmed 6-month coverage · " + coverageCurrency +
        " " + dividendSymbols[coverageCurrency] + " paying holdings · " +
        (dividendMonths[coverageCurrency] || 0) + " months with payments";
      list.appendChild(coverageRow);
      var monthsPaid = dividendMonths[coverageCurrency];
      if (typeof monthsPaid === "number" && isFinite(monthsPaid) &&
          monthsPaid >= 0 && monthsPaid <= 6) {
        var paidMonthsBar = document.createElement("div");
        paidMonthsBar.className = "allocation-row";
        var paidMonthsCaption = document.createElement("span");
        paidMonthsCaption.textContent = coverageCurrency + " · " + monthsPaid + "/6 months with payments";
        var paidMonthsTrack = document.createElement("span");
        paidMonthsTrack.className = "allocation-track";
        var paidMonthsFill = document.createElement("span");
        paidMonthsFill.className = "allocation-fill";
        paidMonthsFill.style.width = Math.round(monthsPaid * 100 / 6) + "%";
        paidMonthsTrack.appendChild(paidMonthsFill);
        paidMonthsBar.appendChild(paidMonthsCaption);
        paidMonthsBar.appendChild(paidMonthsTrack);
        list.appendChild(paidMonthsBar);
      }
    }
    var observed = info.observed_monthly_average || {};
    var observedCurrencies = Object.keys(observed);
    if (observedCurrencies.length) {
      var observedRow = document.createElement("div");
      observedRow.className = "repo-row";
      var observedParts = [];
      for (var o = 0; o < observedCurrencies.length; o++) {
        observedParts.push(observedCurrencies[o] + " " + observed[observedCurrencies[o]]);
      }
      observedRow.textContent = "Recorded monthly average (6 calendar months, current month partial): " + observedParts.join(" / ");
      list.appendChild(observedRow);
    }
    var completed = info.completed_month_average || {};
    var completedCurrencies = Object.keys(completed);
    if (completedCurrencies.length) {
      var completedLine = document.createElement("div");
      completedLine.className = "repo-row";
      var completedParts = [];
      for (var ci = 0; ci < completedCurrencies.length; ci++) {
        completedParts.push(completedCurrencies[ci] + " " + completed[completedCurrencies[ci]]);
      }
      completedLine.textContent = "Average of last 5 completed calendar months: " + completedParts.join(" / ");
      list.appendChild(completedLine);
    }
    var change = info.completed_month_change || {};
    var changeCurrencies = Object.keys(change);
    for (var dc = 0; dc < changeCurrencies.length; dc++) {
      var changeRow = document.createElement("div");
      changeRow.className = "repo-row";
      var changeItem = change[changeCurrencies[dc]];
      changeRow.textContent = "Confirmed completed-month change · " + changeCurrencies[dc] +
        " " + changeItem.latest_month + " vs " + changeItem.previous_month +
        " · " + changeItem.difference +
        (changeItem.percentage !== null && typeof changeItem.percentage !== "undefined" ?
         " (" + changeItem.percentage + "%)" : " (prior month zero; percent unavailable)");
      list.appendChild(changeRow);
    }
    var bestMonths = info.best_completed_months || {};
    var bestCurrencies = Object.keys(bestMonths);
    for (var bi = 0; bi < bestCurrencies.length; bi++) {
      var bestRow = document.createElement("div");
      bestRow.className = "repo-row";
      bestRow.textContent = "Highest recorded completed month · " + bestCurrencies[bi] + " " +
        bestMonths[bestCurrencies[bi]].amount + " (" + bestMonths[bestCurrencies[bi]].month + ")";
      list.appendChild(bestRow);
    }
    var symbolTotals = info.six_month_by_symbol || [];
    var symbolMonths = info.six_month_payment_months || [];
    if (symbolTotals.length) {
      var symbolHeading = document.createElement("div");
      symbolHeading.className = "agenda-group";
      symbolHeading.textContent = "Confirmed payments by holding · last 6 months";
      list.appendChild(symbolHeading);
      for (var sb = 0; sb < symbolTotals.length; sb++) {
        var symbolRow = document.createElement("div");
        symbolRow.className = "repo-row";
        var coverage = "";
        for (var sm = 0; sm < symbolMonths.length; sm++) {
          if (symbolMonths[sm].symbol === symbolTotals[sb].symbol &&
              symbolMonths[sm].currency === symbolTotals[sb].currency) {
            coverage = " · Paid in " + symbolMonths[sm].paid_months + "/6 months";
            break;
          }
        }
        symbolRow.textContent = symbolTotals[sb].symbol + " · " + symbolTotals[sb].amount +
          " " + symbolTotals[sb].currency +
          (typeof symbolTotals[sb].currency_share_percent === "string" ?
           " · " + symbolTotals[sb].currency_share_percent + "% of " + symbolTotals[sb].currency + " payments" : "") + coverage;
        list.appendChild(symbolRow);
      }
    }
    var validHistory = Object.prototype.toString.call(info.history) === "[object Array]";
    var originalHistory = validHistory ? info.history : [];
    if (!validHistory) {
      var invalidHistory = document.createElement("div");
      invalidHistory.className = "repo-row";
      invalidHistory.textContent = "Dividend history list invalid. Check the confirmed payment file.";
      list.appendChild(invalidHistory);
    }
    var history = originalHistory.filter(function (month) {
      return month && typeof month === "object" &&
        typeof month.month === "string" && month.totals &&
        typeof month.totals === "object" &&
        Object.prototype.toString.call(month.totals) !== "[object Array]";
    });
    if (history.length !== originalHistory.length) {
      var invalidMonth = document.createElement("div");
      invalidMonth.className = "repo-row";
      invalidMonth.textContent = "Skipped " + (originalHistory.length - history.length) +
        " invalid dividend history entries.";
      list.appendChild(invalidMonth);
    }
    var maxByCurrency = {};
    for (var h = 0; h < history.length; h++) {
      var monthValues = history[h].totals || {};
      var monthCurrencies = Object.keys(monthValues);
      for (var k = 0; k < monthCurrencies.length; k++) {
        var numericAmount = Number(monthValues[monthCurrencies[k]]);
        if (isFinite(numericAmount) && numericAmount >= 0) {
          maxByCurrency[monthCurrencies[k]] = Math.max(maxByCurrency[monthCurrencies[k]] || 0, numericAmount);
        }
      }
    }
    var chartCurrencies = Object.keys(maxByCurrency);
    for (var cc = 0; cc < chartCurrencies.length; cc++) {
      var currency = chartCurrencies[cc];
      var chart = document.createElement("div");
      chart.className = "dividend-bars";
      var title = document.createElement("div");
      title.textContent = "Recorded " + currency + " payments by month";
      chart.appendChild(title);
      for (var mm = 0; mm < history.length; mm++) {
        var rawAmount = (history[mm].totals || {})[currency];
        var amount = rawAmount === null || typeof rawAmount === "undefined" ? 0 : Number(rawAmount);
        var validAmount = isFinite(amount) && amount >= 0;
        if (!validAmount) { amount = 0; }
        var barRow = document.createElement("div");
        barRow.className = "dividend-bar-row";
        var caption = document.createElement("span");
        caption.textContent = history[mm].month + " · " +
          (validAmount ? amount : "Invalid amount (excluded)");
        var track = document.createElement("span");
        track.className = "dividend-bar-track";
        var fill = document.createElement("span");
        fill.className = "dividend-bar-fill";
        fill.style.width = (maxByCurrency[currency] > 0 ? Math.round(100 * amount / maxByCurrency[currency]) : 0) + "%";
        track.appendChild(fill);
        barRow.appendChild(caption);
        barRow.appendChild(track);
        chart.appendChild(barRow);
      }
      list.appendChild(chart);
    }
    for (var h = 0; h < history.length; h++) {
      var monthlyRow = document.createElement("div");
      monthlyRow.className = "repo-row";
      var monthTotals = history[h].totals || {};
      var monthlyKeys = Object.keys(monthTotals);
      var monthlyAmounts = [];
      for (var m = 0; m < monthlyKeys.length; m++) {
        monthlyAmounts.push(monthlyKeys[m] + " " + monthTotals[monthlyKeys[m]]);
      }
      monthlyRow.textContent = history[h].month + " · " +
        (monthlyAmounts.length ? monthlyAmounts.join(" / ") : "No recorded payments");
      list.appendChild(monthlyRow);
    }
    var originalPayments = Object.prototype.toString.call(info.recent) === "[object Array]" ?
      info.recent : [];
    var payments = originalPayments.filter(function (payment) {
      return payment && typeof payment === "object" &&
        typeof payment.paid_on === "string" && typeof payment.symbol === "string" &&
        typeof payment.amount === "string" && typeof payment.currency === "string";
    });
    if (payments.length !== originalPayments.length) {
      var skippedPayments = document.createElement("div");
      skippedPayments.className = "repo-row";
      skippedPayments.textContent = "Skipped " + (originalPayments.length - payments.length) +
        " invalid recent dividend entries.";
      list.appendChild(skippedPayments);
    }
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
    lastAgendaInfo = info;
    var toggle = document.getElementById("agenda-toggle");
    var detailExpanded = document.getElementById("agenda-detail-toggle").getAttribute ?
      document.getElementById("agenda-detail-toggle").getAttribute("aria-expanded") !== "false" :
      document.getElementById("agenda-detail-toggle").attributes["aria-expanded"] !== "false";
    var list = document.getElementById("agenda-list");
    while (list.firstChild) { list.removeChild(list.firstChild); }
    if (!info || !info.available) {
      toggle.hidden = true;
      text("agenda-summary", info && info.configured ? "Unavailable" : "Not configured");
      text("agenda-updated", info && info.configured ? "Check local agenda file" : "Configure on MacBook");
      return;
    }
    var nextIn = info.next_event_in_days;
    var nextLabel = typeof nextIn === "number" && isFinite(nextIn) &&
      nextIn >= 0 && Math.floor(nextIn) === nextIn ?
      " · Next " + (nextIn === 0 ? "today" : nextIn === 1 ? "tomorrow" : "in " + nextIn + " days") : "";
    var busiest = info.busiest_upcoming_day;
    var busiestLabel = busiest && typeof busiest.date === "string" ?
      " · Busiest " + busiest.date + " (" + busiest.events + ")" : "";
    var freeLabel = typeof info.first_free_day_in_next_seven === "string" ?
      " · First free " + info.first_free_day_in_next_seven :
      (typeof info.first_free_day_in_next_seven !== "undefined" ? " · No free day in next 7" : "");
    function validCount(value) {
      return typeof value === "number" && isFinite(value) &&
        value >= 0 && Math.floor(value) === value;
    }
    var todayCount = validCount(info.today_event_count) ?
      " · " + info.today_event_count + " today" : "";
    var tomorrowCount = validCount(info.tomorrow_event_count) ?
      " · " + info.tomorrow_event_count + " tomorrow" : "";
    var busyDays = validCount(info.next_seven_busy_days) &&
      info.next_seven_busy_days <= 7 ?
      " · " + info.next_seven_busy_days + " busy days" : "";
    var weekCount = validCount(info.next_seven_days_count) ?
      " · " + info.next_seven_days_count + " in next 7 days" : "";
    var conflicts = validCount(info.conflicting_time_slots) &&
      info.conflicting_time_slots > 0 ?
      " · " + info.conflicting_time_slots + " overlapping time slots" : "";
    text("agenda-summary", (validCount(info.upcoming_count) ?
      info.upcoming_count : "Unknown") + " upcoming events" + todayCount + tomorrowCount + weekCount + busyDays + conflicts + busiestLabel + freeLabel + nextLabel);
    if (validCount(info.conflicting_time_slots) &&
        info.conflicting_time_slots > 0 &&
        validCount(info.conflicting_event_count) &&
        info.conflicting_event_count >= 2) {
      var conflictRow = document.createElement("div");
      conflictRow.className = "repo-row";
      conflictRow.textContent = "Review overlapping schedule · " +
        info.conflicting_time_slots + " shared time slots, " +
        info.conflicting_event_count + " events";
      list.appendChild(conflictRow);
    }
    if (info.next_event && typeof info.next_event.title === "string" &&
        validCalendarDate(info.next_event.date)) {
      var nextRow = document.createElement("div");
      nextRow.className = "repo-row";
      nextRow.textContent = "Next scheduled: " + info.next_event.title + " · " +
        info.next_event.date + (info.next_event.time ? " " + info.next_event.time : "");
      list.appendChild(nextRow);
    }
    if (info.next_timed_event && typeof info.next_timed_event.title === "string" &&
        validCalendarDate(info.next_timed_event.date) &&
        typeof info.next_timed_event.time === "string" && info.next_timed_event.time) {
      var nextTimedRow = document.createElement("div");
      nextTimedRow.className = "repo-row";
      nextTimedRow.textContent = "Next timed event: " + info.next_timed_event.title +
        " · " + info.next_timed_event.date + " " + info.next_timed_event.time;
      list.appendChild(nextTimedRow);
    }
    if (typeof info.next_seven_free_days === "number" &&
        isFinite(info.next_seven_free_days) &&
        info.next_seven_free_days >= 0 && info.next_seven_free_days <= 7) {
      var openDays = document.createElement("div");
      openDays.className = "repo-row";
      openDays.textContent = "Days without scheduled events (next 7) · " +
        info.next_seven_free_days;
      list.appendChild(openDays);
    }
    var dailyCounts = Object.prototype.toString.call(info.next_seven_daily_counts) ===
      "[object Array]" ? info.next_seven_daily_counts : [];
    if (dailyCounts.length) {
      var dailyCountLine = document.createElement("div");
      dailyCountLine.className = "repo-row";
      var countParts = [];
      for (var dc = 0; dc < dailyCounts.length; dc++) {
        var item = dailyCounts[dc];
        if (item && validCalendarDate(item.date) &&
            typeof item.events === "number" && isFinite(item.events) &&
            item.events >= 0 && Math.floor(item.events) === item.events) {
          countParts.push(item.date.slice(5) + " " + item.events);
        }
      }
      if (countParts.length) {
        dailyCountLine.textContent = "Next 7 calendar days · " + countParts.join(" · ");
        list.appendChild(dailyCountLine);
      }
    }
    var validEvents = Object.prototype.toString.call(info.events) === "[object Array]";
    var originalEvents = validEvents ? info.events : [];
    var events = originalEvents.filter(function (entry) {
      return entry && typeof entry === "object" &&
        typeof entry.date === "string" &&
        validCalendarDate(entry.date) &&
        typeof entry.title === "string";
    });
    if (events.length !== originalEvents.length) {
      var invalidEvent = document.createElement("div");
      invalidEvent.className = "repo-row";
      invalidEvent.textContent = "Skipped " + (originalEvents.length - events.length) +
        " invalid calendar events.";
      list.appendChild(invalidEvent);
    }
    if (!validEvents) {
      var invalidEvents = document.createElement("div");
      invalidEvents.className = "repo-row";
      invalidEvents.textContent = "Agenda events list invalid. Check local calendar file.";
      list.appendChild(invalidEvents);
    }
    if (validEvents && info.upcoming_count === 0) {
      var noEvents = document.createElement("div");
      noEvents.className = "repo-row";
      noEvents.textContent = "No upcoming events in the 14-day calendar window.";
      list.appendChild(noEvents);
    }
    var visibleEventCount = agendaExpanded ? events.length : Math.min(8, events.length);
    toggle.hidden = !detailExpanded || events.length <= 8;
    toggle.textContent = agendaExpanded ? "Show fewer events" : "Show more events";
    if (info.events_truncated) {
      toggle.textContent += " (first " + events.length + " of " + info.upcoming_count + ")";
    }
    toggle.setAttribute("aria-expanded", agendaExpanded ? "true" : "false");
    var todayDate = info.window_start;
    var tomorrowDate = "";
    if (typeof todayDate === "string" && /^\d{4}-\d{2}-\d{2}$/.test(todayDate)) {
      var parts = todayDate.split("-");
      var nextDay = new Date(Date.UTC(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]) + 1));
      tomorrowDate = nextDay.getUTCFullYear() + "-" + pad(nextDay.getUTCMonth() + 1) + "-" + pad(nextDay.getUTCDate());
    }
    var lastGroup = "";
    for (var i = 0; i < visibleEventCount; i++) {
      var group = events[i].date === todayDate ? "Today" :
        events[i].date === tomorrowDate ? "Tomorrow" : "Upcoming";
      if (group !== lastGroup) {
        var heading = document.createElement("div");
        heading.className = "agenda-group";
        heading.textContent = group;
        list.appendChild(heading);
        lastGroup = group;
      }
      var row = document.createElement("div");
      row.className = "agenda-row";
      row.textContent = events[i].date + (events[i].time ? " " + events[i].time : "") + " · " + events[i].title;
      list.appendChild(row);
    }
    text("agenda-updated", "Local calendar · " + info.window_start + " to " + info.window_end +
      (info.events_truncated ? " · First " + events.length + " of " + info.upcoming_count + " events shown" : ""));
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
    if (!summary || typeof summary !== "object" ||
        typeof summary.sessions !== "number" || !isFinite(summary.sessions) ||
        summary.sessions < 0 || Math.floor(summary.sessions) !== summary.sessions ||
        typeof summary.duration_minutes !== "number" ||
        !isFinite(summary.duration_minutes) || summary.duration_minutes < 0 ||
        typeof summary.distance_km !== "number" ||
        !isFinite(summary.distance_km) || summary.distance_km < 0) {
      text("fitness-summary", "Workout summary unavailable");
      text("fitness-updated", "Invalid workout summary · Check local export");
      var invalidSummary = document.createElement("div");
      invalidSummary.className = "repo-row";
      invalidSummary.textContent = "Workout totals cannot be displayed from this export.";
      list.appendChild(invalidSummary);
      return;
    }
    text("fitness-summary", summary.sessions + " sessions · " + summary.duration_minutes + " min");
    if (summary.sessions === 0) {
      var noWorkouts = document.createElement("div");
      noWorkouts.className = "repo-row";
      noWorkouts.textContent = "No workouts recorded in the last 7 days.";
      list.appendChild(noWorkouts);
    }
    var total = document.createElement("div");
    total.textContent = "Distance " + summary.distance_km + " km · " +
      (typeof info.active_days === "number" ? "Active " + info.active_days + "/7 days · " : "") +
      (typeof info.rest_days === "number" ? info.rest_days + " rest days · " : "") +
      info.period_start + " to " + info.period_end;
    list.appendChild(total);
    if (typeof info.active_day_percent === "number" &&
        isFinite(info.active_day_percent) &&
        info.active_day_percent >= 0 && info.active_day_percent <= 100) {
      var activeCoverageRow = document.createElement("div");
      activeCoverageRow.className = "allocation-row";
      var activeCoverageCaption = document.createElement("span");
      activeCoverageCaption.textContent = "Active days (last 7) · " + info.active_day_percent + "%";
      var activeCoverageTrack = document.createElement("span");
      activeCoverageTrack.className = "allocation-track";
      var activeCoverageFill = document.createElement("span");
      activeCoverageFill.className = "allocation-fill";
      activeCoverageFill.style.width = info.active_day_percent + "%";
      activeCoverageTrack.appendChild(activeCoverageFill);
      activeCoverageRow.appendChild(activeCoverageCaption);
      activeCoverageRow.appendChild(activeCoverageTrack);
      list.appendChild(activeCoverageRow);
    }
    if (info.longest_session && typeof info.longest_session.duration_minutes === "number") {
      var longestRow = document.createElement("div");
      longestRow.className = "repo-row";
      longestRow.textContent = "Longest session (last 7 days) · " + info.longest_session.type +
        " · " + info.longest_session.duration_minutes + " min · " + info.longest_session.date;
      list.appendChild(longestRow);
    }
    if (info.peak_active_day && typeof info.peak_active_day.duration_minutes === "number") {
      var peakInfo = document.createElement("div");
      peakInfo.className = "repo-row";
      peakInfo.textContent = "Most active day (last 7): " + info.peak_active_day.date +
        " · " + info.peak_active_day.duration_minutes + " min";
      list.appendChild(peakInfo);
    }
    if (typeof info.average_active_day_minutes === "number") {
      var averageLine = document.createElement("div");
      averageLine.className = "repo-row";
      averageLine.textContent = "Average on active days · " + info.average_active_day_minutes + " min";
      list.appendChild(averageLine);
    }
    if (typeof info.average_active_day_km === "number") {
      var distanceAverage = document.createElement("div");
      distanceAverage.className = "repo-row";
      distanceAverage.textContent = "Average distance per active day · " + info.average_active_day_km + " km";
      list.appendChild(distanceAverage);
    }
    if (typeof info.average_session_minutes === "number") {
      var perSession = document.createElement("div");
      perSession.className = "repo-row";
      perSession.textContent = "Average per workout session · " + info.average_session_minutes + " min";
      list.appendChild(perSession);
    }
    if (typeof info.longest_streak_days === "number") {
      var streak = document.createElement("div");
      streak.className = "repo-row";
      streak.textContent = "7-day window: longest " + info.longest_streak_days +
        " consecutive active days · Through today " + (info.ongoing_streak_days || 0) + " days";
      list.appendChild(streak);
    }
    if (typeof info.longest_rest_streak_days === "number" &&
        isFinite(info.longest_rest_streak_days) &&
        info.longest_rest_streak_days >= 0 && info.longest_rest_streak_days <= 7) {
      var restStreak = document.createElement("div");
      restStreak.className = "repo-row";
      restStreak.textContent = "Longest consecutive rest period (last 7 days) · " +
        info.longest_rest_streak_days + " days";
      list.appendChild(restStreak);
    }
    if (typeof info.ongoing_rest_streak_days === "number" &&
        isFinite(info.ongoing_rest_streak_days) &&
        info.ongoing_rest_streak_days >= 0 && info.ongoing_rest_streak_days <= 7) {
      var restingNow = document.createElement("div");
      restingNow.className = "repo-row";
      restingNow.textContent = "Consecutive rest days through today (7-day window) · " +
        info.ongoing_rest_streak_days + " days";
      list.appendChild(restingNow);
    }
    if (typeof info.days_since_last_workout_in_week === "number" &&
        isFinite(info.days_since_last_workout_in_week) &&
        info.days_since_last_workout_in_week >= 0 &&
        info.days_since_last_workout_in_week <= 6) {
      var lastWorkout = document.createElement("div");
      lastWorkout.className = "repo-row";
      lastWorkout.textContent = "Last recorded workout (7-day window) · " +
        info.days_since_last_workout_in_week + " days ago";
      list.appendChild(lastWorkout);
    }
    if (info.dominant_activity && typeof info.dominant_activity.type === "string") {
      var dominant = document.createElement("div");
      dominant.className = "repo-row";
      dominant.textContent = "Most time spent on · " + info.dominant_activity.type +
        " · " + info.dominant_activity.duration_minutes + " min (last 7 days)";
      list.appendChild(dominant);
    }
    var activities = info.activity_breakdown || [];
    for (var a = 0; a < activities.length; a++) {
      var activityLine = document.createElement("div");
      activityLine.className = "repo-row";
      activityLine.textContent = activities[a].type + " · " + activities[a].sessions +
        " sessions · " + activities[a].duration_minutes + " min · " +
        activities[a].distance_km + " km" +
        (typeof activities[a].session_share_percent === "number" ?
          " · " + activities[a].session_share_percent + "% of sessions" : "") +
        (typeof activities[a].time_share_percent === "number" ?
          " · " + activities[a].time_share_percent + "% of workout time" : "");
      list.appendChild(activityLine);
    }
    var validDaily = Object.prototype.toString.call(info.daily) === "[object Array]";
    var originalDaily = validDaily ? info.daily : [];
    if (!validDaily) {
      var invalidDaily = document.createElement("div");
      invalidDaily.className = "repo-row";
      invalidDaily.textContent = "Daily workout list invalid. Check the local workout export.";
      list.appendChild(invalidDaily);
    }
    var daily = originalDaily.filter(function (entry) {
      return entry && typeof entry === "object" && validCalendarDate(entry.date) &&
        typeof entry.duration_minutes === "number" && isFinite(entry.duration_minutes) &&
        entry.duration_minutes >= 0 &&
        typeof entry.sessions === "number" && isFinite(entry.sessions) &&
        entry.sessions >= 0 && Math.floor(entry.sessions) === entry.sessions &&
        typeof entry.distance_km === "number" && isFinite(entry.distance_km) &&
        entry.distance_km >= 0;
    });
    if (daily.length !== originalDaily.length) {
      var invalidDay = document.createElement("div");
      invalidDay.className = "repo-row";
      invalidDay.textContent = "Skipped " + (originalDaily.length - daily.length) +
        " invalid daily workout entries.";
      list.appendChild(invalidDay);
    }
    var peakMinutes = 0;
    for (var peak = 0; peak < daily.length; peak++) {
      if (typeof daily[peak].duration_minutes === "number" &&
          isFinite(daily[peak].duration_minutes) && daily[peak].duration_minutes > peakMinutes) {
        peakMinutes = daily[peak].duration_minutes;
      }
    }
    if (daily.length) {
      var chart = document.createElement("div");
      chart.className = "workout-bars";
      for (var day = 0; day < daily.length; day++) {
        var value = daily[day].duration_minutes;
        var safeMinutes = typeof value === "number" && isFinite(value) && value > 0 ? value : 0;
        var line = document.createElement("div");
        line.className = "workout-bar-row";
        var label = document.createElement("span");
        label.textContent = daily[day].date.slice(5) + " · " + safeMinutes + " min";
        var track = document.createElement("span");
        track.className = "workout-bar-track";
        var fill = document.createElement("span");
        fill.className = "workout-bar-fill";
        fill.style.width = (peakMinutes ? Math.round(safeMinutes * 100 / peakMinutes) : 0) + "%";
        track.appendChild(fill);
        line.appendChild(label);
        line.appendChild(track);
        chart.appendChild(line);
      }
      list.appendChild(chart);
    }
    for (var d = 0; d < daily.length; d++) {
      var dayLine = document.createElement("div");
      dayLine.className = "repo-row";
      dayLine.textContent = daily[d].date + " · " + daily[d].sessions +
        " sessions · " + daily[d].duration_minutes + " min · " +
        daily[d].distance_km + " km";
      list.appendChild(dayLine);
    }
    var originalRecent = Object.prototype.toString.call(info.recent) === "[object Array]" ?
      info.recent : [];
    var recent = originalRecent.filter(function (workout) {
      return workout && typeof workout === "object" &&
        validCalendarDate(workout.date) && typeof workout.type === "string" &&
        typeof workout.duration_minutes === "number" &&
        isFinite(workout.duration_minutes) && workout.duration_minutes >= 0;
    });
    if (recent.length !== originalRecent.length) {
      var skippedRecent = document.createElement("div");
      skippedRecent.className = "repo-row";
      skippedRecent.textContent = "Skipped " + (originalRecent.length - recent.length) +
        " invalid recent workout entries.";
      list.appendChild(skippedRecent);
    }
    for (var i = 0; i < recent.length; i++) {
      var row = document.createElement("div");
      row.className = "repo-row";
      row.textContent = recent[i].date + " · " + recent[i].type + " · " + recent[i].duration_minutes + " min";
      list.appendChild(row);
    }
    var updated = "Local export · Refreshes on page data update";
    if (typeof info.file_updated_utc === "string" &&
        /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}/.test(info.file_updated_utc)) {
      updated = "Local file updated " + info.file_updated_utc.replace("T", " ").slice(0, 16) +
        " UTC" + (info.file_older_than_week ? " · FILE OVER 7 DAYS OLD" : "");
    }
    if (typeof info.total_history_count === "number") {
      updated += " · " + info.total_history_count + " total recorded sessions";
    }
    text("fitness-updated", updated);
  }

  function weatherDescription(code) {
    if (code === 0) { return "Clear sky"; }
    if (code === 1 || code === 2) { return "Partly cloudy"; }
    if (code === 3) { return "Overcast"; }
    if (code === 45 || code === 48) { return "Fog"; }
    if (code >= 51 && code <= 57) { return "Drizzle"; }
    if (code >= 61 && code <= 67) { return "Rain"; }
    if (code >= 71 && code <= 77) { return "Snow"; }
    if (code >= 80 && code <= 82) { return "Rain showers"; }
    if (code >= 85 && code <= 86) { return "Snow showers"; }
    if (code >= 95 && code <= 99) { return "Thunderstorm"; }
    return "Conditions unavailable";
  }

  function temperature(value) {
    if (typeof value !== "number" || !isFinite(value)) { return "Unavailable"; }
    return (weatherFahrenheit ? Math.round((value * 9 / 5 + 32) * 10) / 10 : value) +
      (weatherFahrenheit ? " °F" : " °C");
  }

  function showWeather(info) {
    lastWeatherInfo = info;
    document.getElementById("weather-unit-button").textContent = weatherFahrenheit ? "Switch to °C" : "Switch to °F";
    if (!info || !info.available) {
      text("weather-temp", "Unavailable");
      text("weather-details", "No weather data yet");
    } else {
      text("weather-temp", temperature(info.temperature_c));
      var humidity = typeof info.humidity_percent === "number" && isFinite(info.humidity_percent) &&
        info.humidity_percent >= 0 && info.humidity_percent <= 100 ?
        info.humidity_percent + "%" : "unavailable";
      var details = info.location + " · " + weatherDescription(info.weather_code) +
        " · Humidity " + humidity;
      if (typeof info.wind_kmh === "number" && isFinite(info.wind_kmh) && info.wind_kmh >= 0) {
        details += " · Wind " + info.wind_kmh + " km/h";
      }
      if (typeof info.feels_like_c === "number" && isFinite(info.feels_like_c)) {
        details += " · Feels " + temperature(info.feels_like_c);
      }
      if (typeof info.today_high_c === "number" && isFinite(info.today_high_c)) {
        details += " · High " + temperature(info.today_high_c);
      }
      if (typeof info.today_low_c === "number" && isFinite(info.today_low_c)) {
        details += " / Low " + temperature(info.today_low_c);
      }
      if (typeof info.rain_chance_percent === "number" && isFinite(info.rain_chance_percent) &&
          info.rain_chance_percent >= 0 && info.rain_chance_percent <= 100) {
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
    var validRepositories = Object.prototype.toString.call(info.repositories) === "[object Array]";
    var repos = validRepositories ? info.repositories : [];
    if (!validRepositories) {
      var invalidRepositories = document.createElement("div");
      invalidRepositories.className = "repo-row";
      invalidRepositories.textContent = "GitHub repository list invalid. Check provider response.";
      list.appendChild(invalidRepositories);
    }
    if (validRepositories && !repos.length) {
      var noRepos = document.createElement("div");
      noRepos.className = "repo-row";
      noRepos.textContent = "No GitHub repositories returned by the configured provider.";
      list.appendChild(noRepos);
    }
    var total = 0;
    var truncated = !validRepositories;
    for (var i = 0; i < repos.length; i++) {
      if (!repos[i] || typeof repos[i] !== "object") {
        var invalidRepository = document.createElement("div");
        invalidRepository.className = "repo-row";
        invalidRepository.textContent = "Repository entry unavailable";
        list.appendChild(invalidRepository);
        truncated = true;
        continue;
      }
      if (!repos[i].available) {
        var failed = document.createElement("div");
        failed.className = "repo-row";
        failed.textContent = repos[i].repository + " · Unavailable";
        list.appendChild(failed);
        truncated = true;
        continue;
      }
      var prCount = repos[i].open_pr_count;
      if (typeof prCount !== "number" || !isFinite(prCount) ||
          prCount < 0 || Math.floor(prCount) !== prCount) {
        var invalidPR = document.createElement("div");
        invalidPR.className = "repo-row";
        invalidPR.textContent = String(repos[i].repository || "Repository") +
          " · PR count unavailable";
        list.appendChild(invalidPR);
        truncated = true;
        continue;
      }
      total += prCount;
      if (repos[i].open_pr_count_truncated) { truncated = true; }
      var row = document.createElement("div");
      row.className = "repo-row";
      var ci = repos[i].latest_ci;
      var ciText = "CI unknown";
      if (ci && typeof ci === "object") {
        if (ci.status === "completed") {
          var conclusions = ["success", "failure", "cancelled", "skipped", "timed_out",
            "action_required", "neutral", "stale", "startup_failure"];
          ciText = "CI " + (conclusions.indexOf(ci.conclusion) !== -1 ?
            ci.conclusion : "unknown");
        } else if (ci.status === "queued" || ci.status === "in_progress" ||
                   ci.status === "waiting" || ci.status === "pending" ||
                   ci.status === "requested") {
          ciText = "CI " + ci.status;
        }
      } else if (!ci) {
        ciText = "No workflow runs";
      }
      row.textContent = repos[i].repository + " · " + repos[i].open_pr_count +
        (repos[i].open_pr_count_truncated ? "+ open PRs" : " open PRs") + " · " + ciText;
      list.appendChild(row);
      var repoName = repos[i].repository;
      if (typeof repoName === "string" && /^[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+$/.test(repoName)) {
        var repositoryLink = document.createElement("a");
        repositoryLink.className = "github-pr-link";
        repositoryLink.href = "https://github.com/" + repoName;
        repositoryLink.target = "_blank";
        repositoryLink.rel = "noopener noreferrer";
        repositoryLink.textContent = "Open repository · " + repoName;
        list.appendChild(repositoryLink);
      }
      var rawPreviews = repos[i].open_prs;
      var previews = Object.prototype.toString.call(rawPreviews) === "[object Array]" ?
        rawPreviews : [];
      if (rawPreviews && Object.prototype.toString.call(rawPreviews) !== "[object Array]") {
        var invalidPreviews = document.createElement("div");
        invalidPreviews.className = "repo-row";
        invalidPreviews.textContent = "PR preview unavailable · " + repoName;
        list.appendChild(invalidPreviews);
      }
      for (var k = 0; k < previews.length; k++) {
        if (previews[k] && typeof previews[k] === "object" &&
            typeof repoName === "string" &&
            /^[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+$/.test(repoName) &&
            typeof previews[k].number === "number" && isFinite(previews[k].number) &&
            previews[k].number > 0 && Math.floor(previews[k].number) === previews[k].number) {
          var link = document.createElement("a");
          link.className = "github-pr-link";
          link.href = "https://github.com/" + repoName + "/pull/" + previews[k].number;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = "#" + previews[k].number + " " + previews[k].title;
          list.appendChild(link);
        }
      }
    }
    text("github-summary", total + (info.partial || truncated ? "+ known open PRs" : " open PRs"));
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
    var validLists = Object.prototype.toString.call(info.lists) === "[object Array]";
    var columns = validLists ? info.lists : [];
    if (!validLists) {
      var invalidLists = document.createElement("div");
      invalidLists.className = "repo-row";
      invalidLists.textContent = "Trello list response invalid. Check board data.";
      list.appendChild(invalidLists);
    }
    if (validLists && !columns.length) {
      var noLists = document.createElement("div");
      noLists.className = "repo-row";
      noLists.textContent = "No Trello lists returned for the configured board.";
      list.appendChild(noLists);
    }
    var total = 0;
    var nextCount = 0;
    var progressCount = 0;
    for (var i = 0; i < columns.length; i++) {
      if (!columns[i] || typeof columns[i] !== "object") {
        var invalidList = document.createElement("div");
        invalidList.className = "repo-row";
        invalidList.textContent = "Trello list entry unavailable";
        list.appendChild(invalidList);
        continue;
      }
      var cardCount = columns[i].count;
      if (typeof cardCount !== "number" || !isFinite(cardCount) ||
          cardCount < 0 || Math.floor(cardCount) !== cardCount) {
        var invalidCards = document.createElement("div");
        invalidCards.className = "repo-row";
        invalidCards.textContent = String(columns[i].name || "List") +
          " · Card count unavailable";
        list.appendChild(invalidCards);
        continue;
      }
      total += cardCount;
      var listName = String(columns[i].name || "").toLowerCase().replace(/^\s+|\s+$/g, "");
      if (listName === "next") { nextCount += cardCount; }
      if (listName === "in progress") { progressCount += cardCount; }
      var row = document.createElement("div");
      row.className = "repo-row";
      row.textContent = columns[i].name + " · " + cardCount +
        (columns[i].count_truncated ? "+ cards (limit reached)" : " cards");
      list.appendChild(row);
      var rawNames = columns[i].cards;
      if (rawNames && Object.prototype.toString.call(rawNames) !== "[object Array]") {
        var invalidCardPreview = document.createElement("div");
        invalidCardPreview.className = "repo-row";
        invalidCardPreview.textContent = "Card preview unavailable · " + columns[i].name;
        list.appendChild(invalidCardPreview);
      } else {
        var names = Object.prototype.toString.call(rawNames) === "[object Array]" ?
          rawNames.filter(function (name) { return typeof name === "string"; }) : [];
        if (names.length) {
          var preview = document.createElement("div");
          preview.className = "trello-preview";
          preview.textContent = names.join(" / ");
          list.appendChild(preview);
        }
      }
    }
    var anyTruncated = false;
    for (var t = 0; t < columns.length; t++) {
      if (columns[t] && columns[t].count_truncated) { anyTruncated = true; }
    }
    text("trello-summary", total + (anyTruncated ? "+ known cards" : " cards") +
      " · " + nextCount + " Next · " + progressCount + " In Progress");
    text("trello-updated", statusText(info));
  }

  function showServer(info) {
    if (!info || !info.available) {
      text("server-uptime", "Unavailable");
      text("server-info", "No diagnostics received");
      return;
    }
    if (typeof info.uptime_seconds !== "number" ||
        !isFinite(info.uptime_seconds) || info.uptime_seconds < 0) {
      text("server-uptime", "Uptime unavailable");
      text("server-info", "MacBook local API reachable");
      text("server-updated", "Server clock unavailable");
      return;
    }
    var totalMinutes = Math.floor(info.uptime_seconds / 60);
    var days = Math.floor(totalMinutes / 1440);
    var hours = Math.floor((totalMinutes % 1440) / 60);
    var minutes = totalMinutes % 60;
    var uptime = days ? days + "d " + hours + "h" : hours ? hours + "h " + minutes + "m" : minutes + "m";
    text("server-uptime", uptime + " online");
    text("server-info", "MacBook local API reachable");
    var serverClock = info.server_time_utc;
    text("server-updated", typeof serverClock === "string" &&
      /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}/.test(serverClock) ?
      "Server clock: " + serverClock.replace("T", " ").slice(0, 16) + " UTC" :
      "Server clock unavailable");
  }

  function updateLastSuccessAge() {
    if (document.hidden || wasOffline || window.trisDashboardRefreshPaused ||
        !lastSuccessfulOverviewAt || consecutiveOverviewFailures ||
        (overviewRequest && overviewRequest.readyState !== 4)) { return; }
    var elapsedMs = new Date().getTime() - lastSuccessfulOverviewAt;
    if (elapsedMs < 0) {
      text("data-refresh-state", "Last overview refresh succeeded at " +
        lastSuccessfulOverview + " · Device clock changed; elapsed time unavailable.");
      return;
    }
    var elapsed = Math.floor(elapsedMs / 60000);
    text("data-refresh-state", "Last overview refresh succeeded at " + lastSuccessfulOverview +
      " · " + elapsed + " min ago.");
  }

  function clearOverviewRetry() {
    overviewRetryGeneration++;
    if (overviewRetryTimer !== null) {
      clearTimeout(overviewRetryTimer);
      overviewRetryTimer = null;
    }
  }

  function cancelActiveHealthCheck() {
    if (request && request.readyState !== 4) {
      requestSequence++;
      request.abort();
      request = null;
    }
  }

  function cancelActiveOverview() {
    if (overviewRequest && overviewRequest.readyState !== 4) {
      overviewSequence++;
      overviewRequest.abort();
      overviewRequest = null;
      refreshButton.disabled = false;
      refreshButton.textContent = "Refresh now";
      refreshButton.setAttribute("aria-busy", "false");
    }
  }

  window.trisDashboardResumeRefresh = function () {
    if (!document.hidden) { loadOverview(true); }
  };

  window.trisDashboardCancelPendingRetry = function () {
    clearOverviewRetry();
    cancelActiveOverview();
    text("data-refresh-state", "Automatic refresh paused · Manual refresh available.");
  };

  function retryOverview() {
    consecutiveOverviewFailures += 1;
    text("glance-updated", "Refresh failed");
    text("data-refresh-state", "Data refresh failed. " +
      (lastSuccessfulOverview ? "Last successful update at " + lastSuccessfulOverview + "." :
       "No successful update yet."));
    clearOverviewRetry();
    if (document.hidden) {
      text("data-refresh-state", "Data refresh failed. Tab hidden; refresh resumes on return.");
      return;
    }
    if (window.trisDashboardRefreshPaused) {
      text("data-refresh-state", "Data refresh failed. Automatic retry paused; use Refresh now.");
      return;
    }
    // A bounded backoff prevents hammering an unavailable MacBook.
    var delays = [30000, 60000, 120000, 180000];
    var delay = delays[Math.min(consecutiveOverviewFailures - 1, delays.length - 1)];
    text("data-refresh-state", "Data refresh failed · retry in " + (delay / 1000) +
      "s. " + (lastSuccessfulOverview ? "Last successful update at " + lastSuccessfulOverview + "." :
      "No successful update yet."));
    var retryGeneration = overviewRetryGeneration;
    overviewRetryTimer = setTimeout(function () {
      if (retryGeneration !== overviewRetryGeneration) { return; }
      overviewRetryTimer = null;
      if (!document.hidden && !window.trisDashboardRefreshPaused) { loadOverview(true); }
    }, delay);
  }

  function loadOverview(force) {
    if (!force && overviewRequest && overviewRequest.readyState !== 4) { return; }
    var now = new Date().getTime();
    if (now < lastDataStarted) { lastDataStarted = 0; }
    if (!force && now - lastDataStarted < 30000) { return; }
    lastDataStarted = now;
    refreshButton.disabled = true;
    refreshButton.textContent = "Refreshing...";
    refreshButton.setAttribute("aria-busy", "true");
    clearOverviewRetry();
    var sequence = ++overviewSequence;
    if (overviewRequest && overviewRequest.readyState !== 4) { overviewRequest.abort(); }
    overviewRequest = get("/api/overview", function (ok, xhr) {
      if (sequence !== overviewSequence) { return; }
      refreshButton.disabled = false;
      refreshButton.textContent = "Refresh now";
      refreshButton.setAttribute("aria-busy", "false");
      if (!ok) { retryOverview(); return; }
      try {
        var payload = JSON.parse(xhr.responseText);
        if (!payload || typeof payload !== "object" ||
            !payload.server || !payload.weather || !payload.github ||
            !payload.trello || !payload.portfolio || !payload.fitness ||
            !payload.dividends || !payload.agenda || !payload.quotes) {
          throw new Error("Unexpected overview response");
        }
        showGithub(payload.github);
        showWeather(payload.weather);
        showTrello(payload.trello);
        showServer(payload.server);
        showPortfolio(payload.portfolio, payload.valuation);
        showQuotes(payload.quotes);
        showFitness(payload.fitness);
        showDividends(payload.dividends);
        showAgenda(payload.agenda);
        showSummary(payload);
        consecutiveOverviewFailures = 0;
        var refreshedAt = new Date();
        lastSuccessfulOverviewAt = refreshedAt.getTime();
        lastSuccessfulOverview = pad(refreshedAt.getHours()) + ":" + pad(refreshedAt.getMinutes()) +
          " on " + refreshedAt.getFullYear() + "-" + pad(refreshedAt.getMonth() + 1) + "-" + pad(refreshedAt.getDate());
        text("data-refresh-state", "Last overview refresh succeeded at " + lastSuccessfulOverview + ".");
      } catch (error) {
        retryOverview();
      }
    }, 10000);
  }

  // Each dense panel can be collapsed independently on narrow Safari displays.
  // Preserve the selection across reloads while keeping summary and timestamps visible.
  var detailControllers = [];
  function updateDetailCount() {
    var expanded = 0;
    for (var i = 0; i < detailControllers.length; i++) {
      if (detailControllers[i].isExpanded()) { expanded++; }
    }
    text("detail-visibility-count", expanded + " of " + detailControllers.length +
      " panels showing details");
  }

  function bindDetailToggle(panelName, targetIds) {
    var button = document.getElementById(panelName + "-detail-toggle");
    var key = "tris.dashboard.details." + panelName;
    var expanded = true;
    try { expanded = window.localStorage.getItem(key) !== "collapsed"; }
    catch (error) {}
    function applyDetailVisibility() {
      for (var i = 0; i < targetIds.length; i++) {
        document.getElementById(targetIds[i]).hidden = !expanded;
      }
      button.textContent = expanded ? "Hide details" : "Show details";
      button.setAttribute("aria-expanded", expanded ? "true" : "false");
      if (panelName === "agenda" && lastAgendaInfo) {
        showAgenda(lastAgendaInfo);
      }
      updateDetailCount();
    }
    function setExpanded(value) {
      expanded = value;
      applyDetailVisibility();
      try { window.localStorage.setItem(key, expanded ? "expanded" : "collapsed"); }
      catch (error) {}
    }
    detailControllers.push({
      isExpanded: function () { return expanded; },
      setExpanded: setExpanded
    });
    button.addEventListener("click", function () { setExpanded(!expanded); });
    applyDetailVisibility();
  }

  bindDetailToggle("portfolio", ["portfolio-list", "portfolio-quote-values"]);
  bindDetailToggle("dividends", ["dividend-list"]);
  bindDetailToggle("github", ["github-list"]);
  bindDetailToggle("fitness", ["fitness-list"]);
  bindDetailToggle("quotes", ["quotes-list"]);
  bindDetailToggle("trello", ["trello-list"]);
  bindDetailToggle("weather", ["weather-details"]);
  bindDetailToggle("server", ["server-info"]);
  bindDetailToggle("agenda", ["agenda-list", "agenda-toggle"]);

  function setAllDetails(expanded) {
    for (var i = 0; i < detailControllers.length; i++) {
      detailControllers[i].setExpanded(expanded);
    }
  }
  document.getElementById("expand-all-details").addEventListener("click", function () {
    setAllDetails(true);
  });
  document.getElementById("collapse-all-details").addEventListener("click", function () {
    setAllDetails(false);
  });

  document.getElementById("agenda-toggle").addEventListener("click", function () {
    agendaExpanded = !agendaExpanded;
    if (lastAgendaInfo) { showAgenda(lastAgendaInfo); }
  });

  document.getElementById("weather-unit-button").addEventListener("click", function () {
    weatherFahrenheit = !weatherFahrenheit;
    try { window.localStorage.setItem("tris.dashboard.weather.fahrenheit", String(weatherFahrenheit)); }
    catch (error) {}
    showWeather(lastWeatherInfo);
  });

  document.getElementById("refresh-button").addEventListener("click", function () {
    consecutiveOverviewFailures = 0;
    text("data-refresh-state", "Refreshing dashboard data...");
    checkServer();
    loadOverview(true);
  });

  tick();
  checkServer();
  if (!window.trisDashboardRefreshPaused) {
    loadOverview(true);
  } else {
    text("data-refresh-state", "Automatic refresh paused · Press Refresh now to load data.");
  }
  setInterval(tick, 1000);
  setInterval(function () { if (!document.hidden) { checkServer(); } }, 15000);
  setInterval(function () {
    updateLastSuccessAge();
    var interval = window.trisDashboardRefreshMinutes || 3;
    if (!document.hidden && !window.trisDashboardRefreshPaused &&
        overviewRetryTimer === null &&
        (new Date().getTime() < lastDataStarted ||
         new Date().getTime() - lastDataStarted >= interval * 60000)) {
      loadOverview(false);
    }
  }, 60000);
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) {
      tick();
      suppressNextReconnectRefresh = true;
      if (!checkServer()) { suppressNextReconnectRefresh = false; }
      if (!window.trisDashboardRefreshPaused &&
          (!overviewRequest || overviewRequest.readyState === 4)) { loadOverview(true); }
    } else {
      clearOverviewRetry();
      cancelActiveHealthCheck();
      cancelActiveOverview();
      text("data-refresh-state", "Tab hidden · Automatic data requests suspended.");
    }
  });
}());
