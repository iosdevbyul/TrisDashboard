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
        if (!window.trisDashboardRefreshPaused &&
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
    if (request && request.readyState !== 4) { return; }
    var now = new Date().getTime();
    if (now - lastRequestStarted < 2000) { return; }
    lastRequestStarted = now;
    var sequence = ++requestSequence;
    if (request && request.readyState !== 4) { request.abort(); }
    request = get("/healthz", function (online, xhr) {
      if (online) {
        try { online = JSON.parse(xhr.responseText).status === "ok"; }
        catch (error) { online = false; }
      }
      if (sequence === requestSequence) { setConnection(online); }
    });
  }

  function statusText(info) {
    if (!info || !info.available) { return "Unavailable"; }
    return info.stale ? "Last known data (stale)" +
      (typeof info.cache_age_seconds === "number" && isFinite(info.cache_age_seconds) &&
       info.cache_age_seconds >= 0 ? " · " + Math.floor(info.cache_age_seconds / 60) + " min old" : "") :
      "Updated " + (info.updated_at ? info.updated_at.replace("T", " ").slice(0, 16) + " UTC" : "recently");
  }

  function showSummary(payload) {
    var names = ["weather", "github", "trello", "portfolio", "fitness", "dividends", "agenda", "quotes"];
    var active = 0;
    var unavailable = 0;
    var stale = 0;
    var sourceIssues = [];
    for (var i = 0; i < names.length; i++) {
      var info = payload[names[i]];
      if (info && info.available) {
        active++;
        if (info.stale || (info.quality && info.quality.outdated)) {
          stale++;
          var age = info.cache_age_seconds;
          sourceIssues.push(names[i] + " stale" +
            (typeof age === "number" && isFinite(age) && age >= 0 ?
              " (" + Math.floor(age / 60) + " min old)" : ""));
        }
      } else if (info && info.configured !== false) {
        unavailable++;
        sourceIssues.push(names[i] + " unavailable");
      }
    }
    text("source-health-details", sourceIssues.length ? "Needs attention: " + sourceIssues.join(" · ") :
      "No stale or unavailable configured sources.");
    text("glance-sources", active + "/" + names.length + " ready" +
      (stale ? " · " + stale + " stale" : "") +
      (unavailable ? " · " + unavailable + " unavailable" : ""));
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
    var rows = info.quotes || [];
    if (!rows.length) {
      var noQuotes = document.createElement("div");
      noQuotes.className = "repo-row";
      noQuotes.textContent = "No provider quotes returned. No prices have been inferred.";
      list.appendChild(noQuotes);
    }
    var successful = 0;
    var outdated = 0;
    var oldestHours = null;
    for (var i = 0; i < rows.length; i++) {
      var line = document.createElement("div");
      line.className = "repo-row";
      if (rows[i].price && rows[i].reported_at_utc) {
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
        line.textContent = rows[i].symbol + " · Quote unavailable";
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
    var positions = info.positions || [];
    text("portfolio-summary", positions.length + " holdings");
    if (!positions.length) {
      var noPositions = document.createElement("div");
      noPositions.className = "repo-row";
      noPositions.textContent = "No holdings in the manual snapshot.";
      list.appendChild(noPositions);
    }
    for (var i = 0; i < positions.length; i++) {
      var item = positions[i];
      var row = document.createElement("div");
      row.className = "repo-row";
      row.textContent = item.symbol + " · " + item.quantity + " shares" +
        (item.market_value !== null && typeof item.market_value !== "undefined" ?
          " · " + item.market_value + " " + item.currency : " · price unavailable");
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
      var symbols = zeroQuantity[zeroCurrencies[z]];
      if (!symbols || !symbols.length) { continue; }
      var zeroRow = document.createElement("div");
      zeroRow.className = "repo-row";
      zeroRow.textContent = "Review zero-quantity positions · " +
        zeroCurrencies[z] + ": " + symbols.join(", ") + " (manual snapshot)";
      list.appendChild(zeroRow);
    }
    var allocations = info.currency_allocations || {};
    var allocationCurrencies = Object.keys(allocations);
    for (var c = 0; c < allocationCurrencies.length; c++) {
      var shares = allocations[allocationCurrencies[c]];
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
      var largestRow = document.createElement("div");
      largestRow.className = "repo-row";
      var lc = largestCurrencies[lh];
      largestRow.textContent = "Largest manually valued holding · " + lc + " " +
        largestHoldings[lc].symbol + " (" + largestHoldings[lc].market_value + ")";
      list.appendChild(largestRow);
    }
    if (valuation && valuation.available) {
      var totalsLabel = [];
      var quoteKeys = Object.keys(valuation.totals || {});
      for (var v = 0; v < quoteKeys.length; v++) {
        totalsLabel.push(quoteKeys[v] + " " + valuation.totals[quoteKeys[v]]);
      }
      quotePanel.textContent = "Source-stamped quote value (" +
        valuation.matched_count + "/" + valuation.position_count + " holdings)" +
        (valuation.partial ? " · PARTIAL" : "") +
        (valuation.stale ? " · Cached stale" : "") +
        ": " + totalsLabel.join(" / ") + " · Not guaranteed live";
    } else {
      quotePanel.textContent = "Quote-based valuation unavailable (manual snapshot unchanged)";
    }
    var quality = info.quality || {};
    text("portfolio-updated", "Manual prices · Snapshot " +
      (typeof info.as_of === "string" ? info.as_of.replace("T", " ").slice(0, 16) : "time unavailable") +
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
    if (info.record_count === 0) {
      var noPayments = document.createElement("div");
      noPayments.className = "repo-row";
      noPayments.textContent = "No confirmed dividend payments recorded. Add a local payment history file.";
      list.appendChild(noPayments);
    }
    var paymentCounts = info.monthly_payment_counts || {};
    var countCurrencies = Object.keys(paymentCounts);
    for (var pc = 0; pc < countCurrencies.length; pc++) {
      var paymentLine = document.createElement("div");
      paymentLine.className = "repo-row";
      paymentLine.textContent = "Confirmed " + info.month + " payments · " + countCurrencies[pc] +
        " " + paymentCounts[countCurrencies[pc]] + " entries";
      list.appendChild(paymentLine);
    }
    var monthlyPayers = info.monthly_unique_paying_symbols || {};
    var payerCurrencies = Object.keys(monthlyPayers);
    for (var up = 0; up < payerCurrencies.length; up++) {
      var payerCount = monthlyPayers[payerCurrencies[up]];
      if (typeof payerCount !== "number" || !isFinite(payerCount) || payerCount < 0) { continue; }
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
    if (historicCurrencies.length) {
      var sixMonth = document.createElement("div");
      sixMonth.className = "portfolio-total";
      var sixMonthParts = [];
      for (var s = 0; s < historicCurrencies.length; s++) {
        sixMonthParts.push(historicCurrencies[s] + " " + sixMonthTotals[historicCurrencies[s]]);
      }
      sixMonth.textContent = "Confirmed last 6 months: " + sixMonthParts.join(" / ");
      list.appendChild(sixMonth);
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
    var history = info.history || [];
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
        var amount = Number((history[mm].totals || {})[currency] || 0);
        var barRow = document.createElement("div");
        barRow.className = "dividend-bar-row";
        var caption = document.createElement("span");
        caption.textContent = history[mm].month + " · " + amount;
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
    lastAgendaInfo = info;
    var toggle = document.getElementById("agenda-toggle");
    var list = document.getElementById("agenda-list");
    while (list.firstChild) { list.removeChild(list.firstChild); }
    if (!info || !info.available) {
      toggle.hidden = true;
      text("agenda-summary", info && info.configured ? "Unavailable" : "Not configured");
      text("agenda-updated", info && info.configured ? "Check local agenda file" : "Configure on MacBook");
      return;
    }
    var nextIn = info.next_event_in_days;
    var nextLabel = typeof nextIn === "number" && nextIn >= 0 ?
      " · Next " + (nextIn === 0 ? "today" : nextIn === 1 ? "tomorrow" : "in " + nextIn + " days") : "";
    var busiest = info.busiest_upcoming_day;
    var busiestLabel = busiest && typeof busiest.date === "string" ?
      " · Busiest " + busiest.date + " (" + busiest.events + ")" : "";
    var freeLabel = typeof info.first_free_day_in_next_seven === "string" ?
      " · First free " + info.first_free_day_in_next_seven :
      (typeof info.first_free_day_in_next_seven !== "undefined" ? " · No free day in next 7" : "");
    var todayCount = typeof info.today_event_count === "number" ?
      " · " + info.today_event_count + " today" : "";
    var tomorrowCount = typeof info.tomorrow_event_count === "number" ?
      " · " + info.tomorrow_event_count + " tomorrow" : "";
    var busyDays = typeof info.next_seven_busy_days === "number" ?
      " · " + info.next_seven_busy_days + " busy days" : "";
    var weekCount = typeof info.next_seven_days_count === "number" ?
      " · " + info.next_seven_days_count + " in next 7 days" : "";
    var conflicts = typeof info.conflicting_time_slots === "number" && info.conflicting_time_slots > 0 ?
      " · " + info.conflicting_time_slots + " overlapping time slots" : "";
    text("agenda-summary", info.upcoming_count + " upcoming events" + todayCount + tomorrowCount + weekCount + busyDays + conflicts + busiestLabel + freeLabel + nextLabel);
    if (typeof info.conflicting_time_slots === "number" &&
        isFinite(info.conflicting_time_slots) && info.conflicting_time_slots > 0 &&
        typeof info.conflicting_event_count === "number" &&
        isFinite(info.conflicting_event_count) && info.conflicting_event_count >= 2) {
      var conflictRow = document.createElement("div");
      conflictRow.className = "repo-row";
      conflictRow.textContent = "Review overlapping schedule · " +
        info.conflicting_time_slots + " shared time slots, " +
        info.conflicting_event_count + " events";
      list.appendChild(conflictRow);
    }
    if (info.next_event && typeof info.next_event.title === "string") {
      var nextRow = document.createElement("div");
      nextRow.className = "repo-row";
      nextRow.textContent = "Next scheduled: " + info.next_event.title + " · " +
        info.next_event.date + (info.next_event.time ? " " + info.next_event.time : "");
      list.appendChild(nextRow);
    }
    if (info.next_timed_event && typeof info.next_timed_event.title === "string" &&
        typeof info.next_timed_event.date === "string" &&
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
    var dailyCounts = info.next_seven_daily_counts || [];
    if (dailyCounts.length) {
      var dailyCountLine = document.createElement("div");
      dailyCountLine.className = "repo-row";
      var countParts = [];
      for (var dc = 0; dc < dailyCounts.length; dc++) {
        var item = dailyCounts[dc];
        if (item && typeof item.date === "string" &&
            typeof item.events === "number" && isFinite(item.events) && item.events >= 0) {
          countParts.push(item.date.slice(5) + " " + item.events);
        }
      }
      if (countParts.length) {
        dailyCountLine.textContent = "Next 7 calendar days · " + countParts.join(" · ");
        list.appendChild(dailyCountLine);
      }
    }
    var events = info.events || [];
    if (info.upcoming_count === 0) {
      var noEvents = document.createElement("div");
      noEvents.className = "repo-row";
      noEvents.textContent = "No upcoming events in the 14-day calendar window.";
      list.appendChild(noEvents);
    }
    var visibleEventCount = agendaExpanded ? events.length : Math.min(8, events.length);
    toggle.hidden = events.length <= 8;
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
    var daily = info.daily || [];
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
    var recent = info.recent || [];
    for (var i = 0; i < recent.length; i++) {
      var row = document.createElement("div");
      row.className = "repo-row";
      row.textContent = recent[i].date + " · " + recent[i].type + " · " + recent[i].duration_minutes + " min";
      list.appendChild(row);
    }
    var updated = "Local export · Refreshes on page data update";
    if (info.file_updated_utc) {
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
    var repos = info.repositories || [];
    if (!repos.length) {
      var noRepos = document.createElement("div");
      noRepos.className = "repo-row";
      noRepos.textContent = "No GitHub repositories returned by the configured provider.";
      list.appendChild(noRepos);
    }
    var total = 0;
    var truncated = false;
    for (var i = 0; i < repos.length; i++) {
      if (!repos[i].available) {
        var failed = document.createElement("div");
        failed.className = "repo-row";
        failed.textContent = repos[i].repository + " · Unavailable";
        list.appendChild(failed);
        continue;
      }
      total += repos[i].open_pr_count;
      if (repos[i].open_pr_count_truncated) { truncated = true; }
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
      var previews = repos[i].open_prs || [];
      for (var k = 0; k < previews.length; k++) {
        if (typeof repoName === "string" &&
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
    var columns = info.lists || [];
    if (!columns.length) {
      var noLists = document.createElement("div");
      noLists.className = "repo-row";
      noLists.textContent = "No Trello lists returned for the configured board.";
      list.appendChild(noLists);
    }
    var total = 0;
    var nextCount = 0;
    var progressCount = 0;
    for (var i = 0; i < columns.length; i++) {
      total += columns[i].count;
      var listName = String(columns[i].name || "").toLowerCase().replace(/^\s+|\s+$/g, "");
      if (listName === "next") { nextCount += columns[i].count; }
      if (listName === "in progress") { progressCount += columns[i].count; }
      var row = document.createElement("div");
      row.className = "repo-row";
      row.textContent = columns[i].name + " · " + columns[i].count +
        (columns[i].count_truncated ? "+ cards (limit reached)" : " cards");
      list.appendChild(row);
      var names = columns[i].cards || [];
      if (names.length) {
        var preview = document.createElement("div");
        preview.className = "trello-preview";
        preview.textContent = names.join(" / ");
        list.appendChild(preview);
      }
    }
    var anyTruncated = false;
    for (var t = 0; t < columns.length; t++) {
      if (columns[t].count_truncated) { anyTruncated = true; }
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
    text("server-updated", "Server clock: " + String(info.server_time_utc || "").replace("T", " ").slice(0, 16) + " UTC");
  }

  function updateLastSuccessAge() {
    if (!lastSuccessfulOverviewAt || consecutiveOverviewFailures ||
        (overviewRequest && overviewRequest.readyState !== 4)) { return; }
    var elapsed = Math.max(0, Math.floor((new Date().getTime() - lastSuccessfulOverviewAt) / 60000));
    text("data-refresh-state", "Last overview refresh succeeded at " + lastSuccessfulOverview +
      " · " + elapsed + " min ago.");
  }

  function clearOverviewRetry() {
    if (overviewRetryTimer !== null) {
      clearTimeout(overviewRetryTimer);
      overviewRetryTimer = null;
    }
  }

  window.trisDashboardResumeRefresh = function () {
    if (!document.hidden) { loadOverview(true); }
  };

  window.trisDashboardCancelPendingRetry = function () {
    clearOverviewRetry();
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
    overviewRetryTimer = setTimeout(function () {
      overviewRetryTimer = null;
      if (!document.hidden && !window.trisDashboardRefreshPaused) { loadOverview(true); }
    }, delay);
  }

  function loadOverview(force) {
    if (!force && overviewRequest && overviewRequest.readyState !== 4) { return; }
    var now = new Date().getTime();
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
        new Date().getTime() - lastDataStarted >= interval * 60000) {
      loadOverview(false);
    }
  }, 60000);
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) {
      tick(); checkServer();
      if (!window.trisDashboardRefreshPaused &&
          (!overviewRequest || overviewRequest.readyState === 4)) { loadOverview(true); }
    } else { clearOverviewRetry(); }
  });
}());
