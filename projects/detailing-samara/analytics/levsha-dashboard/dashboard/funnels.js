(() => {
  "use strict";

  const data = window.LEVSHA_DATA || { meta: {}, daily_direction_status: [] };
  const rows = data.daily_direction_status || [];
  const ids = [
    "generated-at",
    "data-sources",
    "date-from",
    "date-to",
    "period-caption",
    "funnel-kpi-leads",
    "funnel-kpi-qualified",
    "funnel-kpi-lq",
    "funnel-kpi-deals",
    "funnel-kpi-qs",
    "funnel-kpi-ls",
    "funnel-kpi-won",
    "funnel-kpi-open",
    "funnel-kpi-lost",
    "funnel-kpi-dw",
    "funnel-kpi-do",
    "funnel-kpi-dl",
    "funnel-kpi-lw",
    "funnel-kpi-average-check",
    "funnel-kpi-onec-orders",
    "qualification-note",
    "direction-period-a",
    "direction-period-b",
    "compare-enabled",
    "compare-from",
    "compare-to",
    "comparison-controls",
    "direction-rows",
    "direction-status-filter",
    "status-head",
    "status-rows",
    "footer-range",
  ];
  const els = Object.fromEntries(ids.map((id) => [id, document.getElementById(id)]));
  const number = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
  const money = new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  });
  const percent = new Intl.NumberFormat("ru-RU", {
    style: "percent",
    maximumFractionDigits: 1,
  });
  const shortDate = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short" });
  const fullDate = new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  const allDates = rows.map((row) => row.date).filter(Boolean).sort();
  let compareEnabled = false;
  let comparisonMode = "previous";
  let selectedDirection = "all";
  let funnelSegment = "all";
  let funnelSource = "all";

  function safe(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function setText(id, value) {
    if (els[id]) els[id].textContent = value;
  }

  function isoDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function parseDate(value) {
    return new Date(`${value}T12:00:00`);
  }

  function addDays(date, days) {
    const next = new Date(date);
    next.setDate(next.getDate() + days);
    return next;
  }

  function rowsForPeriod(sourceRows, from, to) {
    return sourceRows.filter((row) => row.date && row.date >= from && row.date <= to);
  }

  function sum(sourceRows, field) {
    return sourceRows.reduce((total, row) => total + Number(row[field] || 0), 0);
  }

  function ratio(top, bottom) {
    return bottom ? top / bottom : 0;
  }

  function metrics(sourceRows) {
    return {
      leads: sum(sourceRows, "leads"),
      qualified: sum(sourceRows, "qualified"),
      deals: sum(sourceRows, "deals"),
      won: sum(sourceRows, "won"),
      open: sum(sourceRows, "open"),
      lost: sum(sourceRows, "lost"),
      wonB24Amount: sum(sourceRows, "won_b24_amount"),
      onecOrders: sum(sourceRows, "onec_orders"),
      onecRevenue: sum(sourceRows, "onec_revenue"),
    };
  }

  function periodLabel(from, to) {
    if (!from || !to) return "—";
    return `${shortDate.format(parseDate(from))} — ${shortDate.format(parseDate(to))}`;
  }

  function pointsDelta(current, previous) {
    if (current === null || previous === null || Number.isNaN(previous)) return "—";
    const delta = (current - previous) * 100;
    const sign = delta > 0 ? "+" : delta < 0 ? "−" : "";
    const value = Math.abs(delta).toLocaleString("ru-RU", { maximumFractionDigits: 1 });
    const state = delta > 0 ? "positive" : delta < 0 ? "negative" : "neutral";
    return `<span class="comparison-delta ${state}">${sign}${value} п.п.</span>`;
  }

  function relativeDelta(current, previous) {
    if (current === null || previous === null) return "—";
    if (previous === 0) {
      if (current === 0) return `<span class="comparison-delta neutral">0%</span>`;
      return `<span class="comparison-delta positive">новое</span>`;
    }
    const delta = (current - previous) / previous;
    const sign = delta > 0 ? "+" : delta < 0 ? "−" : "";
    const value = Math.abs(delta * 100).toLocaleString("ru-RU", { maximumFractionDigits: 1 });
    const state = delta > 0 ? "positive" : delta < 0 ? "negative" : "neutral";
    return `<span class="comparison-delta ${state}">${sign}${value}%</span>`;
  }

  function stackedMetric(primary, comparison, formatter, deltaType = "relative") {
    const formattedPrimary = primary === null ? "—" : formatter(primary);
    if (!compareEnabled) return `<strong class="metric-single">${formattedPrimary}</strong>`;
    const formattedComparison = comparison === null ? "—" : formatter(comparison);
    const delta = deltaType === "points"
      ? pointsDelta(primary, comparison)
      : relativeDelta(primary, comparison);
    return `
      <div class="metric-stack">
        <div class="metric-stack-row primary"><span>A</span><strong>${formattedPrimary}</strong></div>
        <div class="metric-stack-row secondary"><span>B</span><strong>${formattedComparison}</strong></div>
        <div class="metric-stack-delta">${delta}</div>
      </div>`;
  }

  function renderKpis(primaryMetrics, comparisonMetrics) {
    const primaryLq = primaryMetrics.leads
      ? primaryMetrics.qualified / primaryMetrics.leads
      : null;
    const comparisonLq = comparisonMetrics.leads
      ? comparisonMetrics.qualified / comparisonMetrics.leads
      : null;
    const primaryQs = primaryMetrics.qualified
      ? primaryMetrics.deals / primaryMetrics.qualified
      : null;
    const comparisonQs = comparisonMetrics.qualified
      ? comparisonMetrics.deals / comparisonMetrics.qualified
      : null;
    const primaryLs = primaryMetrics.leads
      ? primaryMetrics.deals / primaryMetrics.leads
      : null;
    const comparisonLs = comparisonMetrics.leads
      ? comparisonMetrics.deals / comparisonMetrics.leads
      : null;
    const primaryDw = primaryMetrics.deals ? primaryMetrics.won / primaryMetrics.deals : null;
    const comparisonDw = comparisonMetrics.deals
      ? comparisonMetrics.won / comparisonMetrics.deals
      : null;
    const primaryDo = primaryMetrics.deals ? primaryMetrics.open / primaryMetrics.deals : null;
    const comparisonDo = comparisonMetrics.deals
      ? comparisonMetrics.open / comparisonMetrics.deals
      : null;
    const primaryDl = primaryMetrics.deals ? primaryMetrics.lost / primaryMetrics.deals : null;
    const comparisonDl = comparisonMetrics.deals
      ? comparisonMetrics.lost / comparisonMetrics.deals
      : null;
    const primaryLw = primaryMetrics.leads ? primaryMetrics.won / primaryMetrics.leads : null;
    const comparisonLw = comparisonMetrics.leads
      ? comparisonMetrics.won / comparisonMetrics.leads
      : null;
    const primaryAverageCheck = primaryMetrics.onecOrders
      ? primaryMetrics.onecRevenue / primaryMetrics.onecOrders
      : null;
    const comparisonAverageCheck = comparisonMetrics.onecOrders
      ? comparisonMetrics.onecRevenue / comparisonMetrics.onecOrders
      : null;
    els["funnel-kpi-leads"].innerHTML = stackedMetric(
      primaryMetrics.leads, comparisonMetrics.leads, (value) => number.format(value)
    );
    els["funnel-kpi-qualified"].innerHTML = stackedMetric(
      primaryMetrics.qualified, comparisonMetrics.qualified, (value) => number.format(value)
    );
    els["funnel-kpi-deals"].innerHTML = stackedMetric(
      primaryMetrics.deals, comparisonMetrics.deals, (value) => number.format(value)
    );
    els["funnel-kpi-lq"].innerHTML = stackedMetric(
      primaryLq, comparisonLq, (value) => percent.format(value), "points"
    );
    els["funnel-kpi-qs"].innerHTML = stackedMetric(
      primaryQs, comparisonQs, (value) => percent.format(value), "points"
    );
    els["funnel-kpi-ls"].innerHTML = stackedMetric(
      primaryLs, comparisonLs, (value) => percent.format(value), "points"
    );
    els["funnel-kpi-won"].innerHTML = stackedMetric(
      primaryMetrics.won, comparisonMetrics.won, (value) => number.format(value)
    );
    els["funnel-kpi-open"].innerHTML = stackedMetric(
      primaryMetrics.open, comparisonMetrics.open, (value) => number.format(value)
    );
    els["funnel-kpi-lost"].innerHTML = stackedMetric(
      primaryMetrics.lost, comparisonMetrics.lost, (value) => number.format(value)
    );
    els["funnel-kpi-dw"].innerHTML = stackedMetric(
      primaryDw, comparisonDw, (value) => percent.format(value), "points"
    );
    els["funnel-kpi-do"].innerHTML = stackedMetric(
      primaryDo, comparisonDo, (value) => percent.format(value), "points"
    );
    els["funnel-kpi-dl"].innerHTML = stackedMetric(
      primaryDl, comparisonDl, (value) => percent.format(value), "points"
    );
    els["funnel-kpi-lw"].innerHTML = stackedMetric(
      primaryLw, comparisonLw, (value) => percent.format(value), "points"
    );
    els["funnel-kpi-average-check"].innerHTML = stackedMetric(
      primaryAverageCheck, comparisonAverageCheck, (value) => money.format(value)
    );
    els["funnel-kpi-onec-orders"].innerHTML = stackedMetric(
      primaryMetrics.onecOrders,
      comparisonMetrics.onecOrders,
      (value) => number.format(value)
    );
  }

  function renderStatusDistribution(primaryRows, comparisonRows) {
    const filterRows = (sourceRows) =>
      selectedDirection === "all"
        ? sourceRows
        : sourceRows.filter((row) => row.direction === selectedDirection);
    const primary = filterRows(primaryRows);
    const comparison = filterRows(comparisonRows);
    const primaryTotal = sum(primary, "leads");
    const comparisonTotal = sum(comparison, "leads");
    const statuses = new Set([
      ...primary.map((row) => row.status),
      ...comparison.map((row) => row.status),
    ]);
    const statusRows = [...statuses]
      .map((status) => ({
        status,
        primary: sum(primary.filter((row) => row.status === status), "leads"),
        comparison: sum(comparison.filter((row) => row.status === status), "leads"),
      }))
      .sort(
        (a, b) =>
          b.primary - a.primary ||
          b.comparison - a.comparison ||
          a.status.localeCompare(b.status, "ru")
      );

    els["status-head"].innerHTML = `<tr><th>Текущий статус</th><th>Количество${compareEnabled ? " · A/B/Δ" : ""}</th><th>Доля${compareEnabled ? " · A/B/Δ" : ""}</th></tr>`;

    if (!statusRows.length) {
      els["status-rows"].innerHTML = `<tr><td colspan="3" class="empty-state">Нет данных за выбранный период</td></tr>`;
      return;
    }

    els["status-rows"].innerHTML = statusRows
      .map((row) => {
        const primaryShare = ratio(row.primary, primaryTotal);
        const comparisonShare = comparisonTotal ? row.comparison / comparisonTotal : null;
        return `
          <tr>
            <td>${safe(row.status)}</td>
            <td>${stackedMetric(row.primary, row.comparison, (value) => number.format(value))}</td>
            <td>${stackedMetric(primaryShare, comparisonShare, (value) => percent.format(value), "points")}</td>
          </tr>`;
      })
      .join("");
  }

  function outcomeCell(
    primaryCount,
    comparisonCount,
    primaryDeals,
    comparisonDeals,
    primaryAmount = null,
    comparisonAmount = null
  ) {
    const primaryRate = primaryDeals ? primaryCount / primaryDeals : null;
    const comparisonRate = comparisonDeals ? comparisonCount / comparisonDeals : null;
    const amountBlock = primaryAmount === null && comparisonAmount === null
      ? ""
      : `<div class="direction-outcome-amount">
          <span>сумма Б24</span>
          ${stackedMetric(primaryAmount, comparisonAmount, (value) => money.format(value))}
        </div>`;
    return `
      <div class="direction-outcome-count">${stackedMetric(
        primaryCount,
        comparisonCount,
        (value) => number.format(value)
      )}</div>
      <div class="direction-outcome-share">
        <span>от сделок</span>
        ${stackedMetric(primaryRate, comparisonRate, (value) => percent.format(value), "points")}
      </div>
      ${amountBlock}`;
  }

  function averageCheckCell(primaryMetrics, comparisonMetrics) {
    const primaryAverage = primaryMetrics.onecOrders
      ? primaryMetrics.onecRevenue / primaryMetrics.onecOrders
      : null;
    const comparisonAverage = comparisonMetrics.onecOrders
      ? comparisonMetrics.onecRevenue / comparisonMetrics.onecOrders
      : null;
    return `
      <div class="direction-average-value">${stackedMetric(
        primaryAverage,
        comparisonAverage,
        (value) => money.format(value)
      )}</div>
      <div class="direction-average-orders">
        <span>заказов 1С</span>
        ${stackedMetric(
          primaryMetrics.onecOrders,
          comparisonMetrics.onecOrders,
          (value) => number.format(value)
        )}
      </div>`;
  }

  function renderDirections(primaryRows, comparisonRows) {
    const directions = new Set([
      ...primaryRows.map((row) => row.direction),
      ...comparisonRows.map((row) => row.direction),
    ]);
    const directionRows = [...directions]
      .map((direction) => ({
        direction,
        primary: metrics(primaryRows.filter((row) => row.direction === direction)),
        comparison: metrics(comparisonRows.filter((row) => row.direction === direction)),
      }))
      .sort(
        (a, b) =>
          b.primary.leads - a.primary.leads ||
          b.comparison.leads - a.comparison.leads ||
          a.direction.localeCompare(b.direction, "ru")
      );
    const totals = {
      direction: "Все направления",
      primary: metrics(primaryRows),
      comparison: metrics(comparisonRows),
      total: true,
    };

    if (!primaryRows.length && !comparisonRows.length) {
      els["direction-rows"].innerHTML = `<div class="empty-state">Нет данных за выбранный период</div>`;
    } else {
      els["direction-rows"].innerHTML = [totals, ...directionRows]
        .map((row) => {
          const primaryLq = row.primary.leads
            ? row.primary.qualified / row.primary.leads
            : null;
          const comparisonLq = row.comparison.leads
            ? row.comparison.qualified / row.comparison.leads
            : null;
          const primaryQs = row.primary.qualified
            ? row.primary.deals / row.primary.qualified
            : null;
          const comparisonQs = row.comparison.qualified
            ? row.comparison.deals / row.comparison.qualified
            : null;
          const primaryLw = row.primary.leads
            ? row.primary.won / row.primary.leads
            : null;
          const comparisonLw = row.comparison.leads
            ? row.comparison.won / row.comparison.leads
            : null;
          const label = row.total
            ? `<strong>${safe(row.direction)}</strong>`
            : `<button type="button" class="direction-filter-button${selectedDirection === row.direction ? " active" : ""}" data-direction-filter="${safe(row.direction)}">${safe(row.direction)}</button>`;
          return `
            <div class="direction-board-row${row.total ? " total" : ""}">
              <div class="direction-name">${label}</div>
              <div class="direction-stage-cell leads">${stackedMetric(row.primary.leads, row.comparison.leads, (value) => number.format(value))}</div>
              <div class="direction-conversion-cell">${stackedMetric(primaryLq, comparisonLq, (value) => percent.format(value), "points")}</div>
              <div class="direction-stage-cell qualified">${stackedMetric(row.primary.qualified, row.comparison.qualified, (value) => number.format(value))}</div>
              <div class="direction-conversion-cell">${stackedMetric(primaryQs, comparisonQs, (value) => percent.format(value), "points")}</div>
              <div class="direction-stage-cell deals">${stackedMetric(row.primary.deals, row.comparison.deals, (value) => number.format(value))}</div>
              <div class="direction-outcome-cell won">${outcomeCell(row.primary.won, row.comparison.won, row.primary.deals, row.comparison.deals, row.primary.wonB24Amount, row.comparison.wonB24Amount)}</div>
              <div class="direction-outcome-cell open">${outcomeCell(row.primary.open, row.comparison.open, row.primary.deals, row.comparison.deals)}</div>
              <div class="direction-outcome-cell lost">${outcomeCell(row.primary.lost, row.comparison.lost, row.primary.deals, row.comparison.deals)}</div>
              <div class="direction-average-cell">${averageCheckCell(row.primary, row.comparison)}</div>
              <div class="direction-conversion-cell end-to-end">${stackedMetric(primaryLw, comparisonLw, (value) => percent.format(value), "points")}</div>
            </div>`;
        })
        .join("");
    }

    const allDirections = [...new Set(
      [...primaryRows, ...comparisonRows].map((row) => row.direction)
    )]
      .sort((a, b) => a.localeCompare(b, "ru"));
    if (selectedDirection !== "all" && !allDirections.includes(selectedDirection)) {
      selectedDirection = "all";
    }
    els["direction-status-filter"].innerHTML = [
      `<option value="all">Все направления</option>`,
      ...allDirections.map(
        (direction) => `<option value="${safe(direction)}">${safe(direction)}</option>`
      ),
    ].join("");
    els["direction-status-filter"].value = selectedDirection;
    els["direction-rows"].querySelectorAll("[data-direction-filter]").forEach((button) => {
      button.addEventListener("click", () => {
        selectedDirection = button.dataset.directionFilter;
        render();
      });
    });
    renderStatusDistribution(primaryRows, comparisonRows);
  }

  function render() {
    const from = els["date-from"].value;
    const to = els["date-to"].value;
    if (!from || !to) return;
    const filterRows = (sourceRows) => sourceRows.filter(
      (row) =>
        (funnelSegment === "all" || row.segment === funnelSegment)
        && (funnelSource === "all" || row.source === funnelSource)
    );
    const primaryRows = filterRows(rowsForPeriod(rows, from, to));
    const comparisonFrom = els["compare-from"].value;
    const comparisonTo = els["compare-to"].value;
    const comparisonRows = compareEnabled && comparisonFrom && comparisonTo
      ? filterRows(rowsForPeriod(rows, comparisonFrom, comparisonTo))
      : [];

    setText("period-caption", `${fullDate.format(parseDate(from))} — ${fullDate.format(parseDate(to))}`);
    setText("direction-period-a", periodLabel(from, to));
    setText(
      "direction-period-b",
      compareEnabled ? periodLabel(comparisonFrom, comparisonTo) : "—"
    );
    setText("footer-range", `Период A: ${from} — ${to}`);
    setText(
      "qualification-note",
      [data.meta.qualification_label, data.meta.qualification_description].filter(Boolean).join(". ")
        || "Квал — прокси по текущей стадии Б24"
    );
    renderKpis(metrics(primaryRows), metrics(comparisonRows));
    renderDirections(primaryRows, comparisonRows);
  }

  function setComparisonPreset(name, shouldRender = true) {
    const primaryFrom = els["date-from"].value;
    const primaryTo = els["date-to"].value;
    if (!primaryFrom || !primaryTo) return;
    const from = parseDate(primaryFrom);
    const to = parseDate(primaryTo);
    let comparisonFrom;
    let comparisonTo;

    if (name === "previous-month") {
      comparisonFrom = new Date(from.getFullYear(), from.getMonth() - 1, 1, 12);
      comparisonTo = new Date(from.getFullYear(), from.getMonth(), 0, 12);
    } else {
      const days = Math.round((to - from) / 86400000) + 1;
      comparisonTo = addDays(from, -1);
      comparisonFrom = addDays(comparisonTo, -(days - 1));
      name = "previous";
    }

    comparisonMode = name;
    els["compare-from"].value = isoDate(comparisonFrom);
    els["compare-to"].value = isoDate(comparisonTo);
    document.querySelectorAll("[data-compare-preset]").forEach((button) => {
      button.classList.toggle("active", button.dataset.comparePreset === name);
    });
    if (shouldRender) render();
  }

  function selectPreset(name) {
    if (!allDates.length) return;
    const maxDate = parseDate(data.meta.reporting_through || allDates.at(-1));
    let from = parseDate(allDates[0]);
    const to = maxDate;
    if (name === "week") from = addDays(maxDate, -6);
    if (name === "month") from = new Date(maxDate.getFullYear(), maxDate.getMonth(), 1, 12);
    els["date-from"].value = isoDate(from);
    els["date-to"].value = isoDate(to);
    document.querySelectorAll("[data-preset]").forEach((button) => {
      button.classList.toggle("active", button.dataset.preset === name);
    });
    if (compareEnabled && comparisonMode !== "manual") {
      setComparisonPreset(comparisonMode, false);
    }
    render();
  }

  document.querySelectorAll("[data-preset]").forEach((button) => {
    button.addEventListener("click", () => selectPreset(button.dataset.preset));
  });
  document.querySelectorAll("[data-compare-preset]").forEach((button) => {
    button.addEventListener("click", () => setComparisonPreset(button.dataset.comparePreset));
  });
  els["compare-enabled"].addEventListener("change", () => {
    compareEnabled = els["compare-enabled"].checked;
    els["comparison-controls"].hidden = !compareEnabled;
    if (compareEnabled) setComparisonPreset("previous", false);
    render();
  });
  [els["compare-from"], els["compare-to"]].forEach((input) => {
    input.addEventListener("change", () => {
      comparisonMode = "manual";
      document.querySelectorAll("[data-compare-preset]").forEach((button) => {
        button.classList.remove("active");
      });
      render();
    });
  });
  els["direction-status-filter"].addEventListener("change", () => {
    selectedDirection = els["direction-status-filter"].value;
    render();
  });
  document.querySelectorAll("[data-funnel-segment]").forEach((button) => {
    button.addEventListener("click", () => {
      funnelSegment = button.dataset.funnelSegment;
      document.querySelectorAll("[data-funnel-segment]").forEach((item) => {
        const active = item.dataset.funnelSegment === funnelSegment;
        item.classList.toggle("active", active);
        item.setAttribute("aria-pressed", String(active));
      });
      render();
    });
  });
  document.querySelectorAll("[data-funnel-source]").forEach((button) => {
    button.addEventListener("click", () => {
      funnelSource = button.dataset.funnelSource;
      selectedDirection = "all";
      document.querySelectorAll("[data-funnel-source]").forEach((item) => {
        const active = item.dataset.funnelSource === funnelSource;
        item.classList.toggle("active", active);
        item.setAttribute("aria-pressed", String(active));
      });
      render();
    });
  });
  const primaryPeriodChanged = () => {
    document.querySelectorAll("[data-preset]").forEach((button) => {
      button.classList.remove("active");
    });
    if (compareEnabled && comparisonMode !== "manual") {
      setComparisonPreset(comparisonMode, false);
    }
    render();
  };
  els["date-from"].addEventListener("change", primaryPeriodChanged);
  els["date-to"].addEventListener("change", primaryPeriodChanged);

  setText("generated-at", data.meta.generated_at_display || "—");
  setText("data-sources", data.meta.source_caption || "Данные ещё не загружены");
  if (allDates.length) {
    selectPreset("month");
  } else {
    const today = isoDate(new Date());
    els["date-from"].value = today;
    els["date-to"].value = today;
    render();
  }
})();
