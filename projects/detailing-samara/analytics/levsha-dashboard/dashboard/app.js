(() => {
  "use strict";

  const data = window.LEVSHA_DATA || {
    meta: {},
    daily_funnel: [],
    daily_sales: [],
    daily_ads: [],
    daily_keywords: [],
    daily_ad_details: [],
    quality: {},
  };

  const els = Object.fromEntries(
    [
      "generated-at",
      "data-sources",
      "date-from",
      "date-to",
      "period-caption",
      "kpi-deals",
      "kpi-success",
      "kpi-success-share",
      "kpi-cr",
      "kpi-booked",
      "revenue-label",
      "kpi-revenue",
      "revenue-note",
      "revenue-per-deal-label",
      "kpi-revenue-per-deal",
      "segment-revenue-label",
      "segment-revenue-per-deal-label",
      "segment-rows",
      "weekly-chart",
      "channel-note",
      "channel-revenue-label",
      "channel-rows",
      "keyword-coverage",
      "keyword-rows",
      "quality-list",
      "footer-range",
    ].map((id) => [id, document.getElementById(id)])
  );

  const money = new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  });
  const number = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
  const percent = new Intl.NumberFormat("ru-RU", {
    style: "percent",
    maximumFractionDigits: 1,
  });
  const shortDate = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short" });
  const fullDate = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", year: "numeric" });
  let channelSegment = "all";
  const expandedChannels = new Set();
  const expandedCampaigns = new Set();
  const expandedAdGroups = new Set();

  const allDates = [
    ...data.daily_funnel.map((row) => row.date),
    ...data.daily_sales.map((row) => row.date),
    ...data.daily_ads.map((row) => row.date),
    ...(data.daily_keywords || []).map((row) => row.date),
    ...(data.daily_ad_details || []).map((row) => row.date),
  ].filter(Boolean).sort();

  function safe(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
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

  function inRange(date, from, to) {
    return date >= from && date <= to;
  }

  function sum(rows, field) {
    return rows.reduce((total, row) => total + Number(row[field] || 0), 0);
  }

  function ratio(top, bottom) {
    return bottom ? top / bottom : 0;
  }

  function addDays(date, days) {
    const next = new Date(date);
    next.setDate(next.getDate() + days);
    return next;
  }

  function mondayOf(value) {
    const date = parseDate(value);
    const day = date.getDay();
    date.setDate(date.getDate() - (day === 0 ? 6 : day - 1));
    return isoDate(date);
  }

  function grouped(rows, keyFn) {
    const map = new Map();
    rows.forEach((row) => {
      const key = keyFn(row);
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(row);
    });
    return map;
  }

  function rowsForPeriod(rows, from, to) {
    return rows.filter((row) => row.date && inRange(row.date, from, to));
  }

  function funnelMetrics(rows) {
    return {
      deals: sum(rows, "deals"),
      success: sum(rows, "success"),
      booked: sum(rows, "booked"),
      b24Amount: sum(rows, "b24_amount"),
      attributedRevenue: sum(rows, "attributed_revenue"),
    };
  }

  function revenueFor(segment, funnelRows, salesRows) {
    if (data.meta.revenue_mode === "onec") {
      return sum(salesRows.filter((row) => segment === "all" || row.segment === segment), "revenue");
    }
    return sum(funnelRows.filter((row) => segment === "all" || row.segment === segment), "b24_amount");
  }

  function segmentFunnel(segment, rows) {
    return funnelMetrics(rows.filter((row) => segment === "all" || row.segment === segment));
  }

  function setText(id, value) {
    if (els[id]) els[id].textContent = value;
  }

  function renderSegments(funnelRows, salesRows) {
    const segmentDefs = [
      ["all", "Всего"],
      ["new", "Только новые"],
      ["repeat", "Только повторные"],
    ];

    els["segment-rows"].innerHTML = segmentDefs
      .map(([key, label]) => {
        const metrics = segmentFunnel(key, funnelRows);
        const revenue = revenueFor(key, funnelRows, salesRows);
        return `
          <tr>
            <td><span class="segment-name">${safe(label)}</span></td>
            <td>${number.format(metrics.deals)}</td>
            <td>${number.format(metrics.success)}</td>
            <td>${number.format(metrics.booked)}</td>
            <td>${percent.format(ratio(metrics.success, metrics.deals))}</td>
            <td>${money.format(revenue)}</td>
            <td>${metrics.deals ? money.format(revenue / metrics.deals) : "—"}</td>
          </tr>`;
      })
      .join("");
  }

  function renderWeekly(funnelRows) {
    const weeks = [...grouped(funnelRows, (row) => mondayOf(row.date)).entries()]
      .map(([week, rows]) => ({ week, ...funnelMetrics(rows) }))
      .sort((a, b) => a.week.localeCompare(b.week));

    if (!weeks.length) {
      els["weekly-chart"].innerHTML = '<div class="empty-state">Нет данных за выбранный период</div>';
      return;
    }

    const maxValue = Math.max(...weeks.map((week) => week.deals), 1);
    els["weekly-chart"].innerHTML = weeks
      .map((week) => {
        const start = parseDate(week.week);
        const end = addDays(start, 6);
        const dealsHeight = Math.max(2, (week.deals / maxValue) * 180);
        const successHeight = Math.max(2, (week.success / maxValue) * 180);
        return `
          <div class="week-column">
            <div class="week-value">${number.format(week.deals)} / ${number.format(week.success)}</div>
            <div class="week-bars">
              <div class="bar deals" style="height:${dealsHeight}px" title="Сделок: ${week.deals}"></div>
              <div class="bar success" style="height:${successHeight}px" title="Успех + в работе: ${week.success}"></div>
            </div>
            <div class="week-label">${shortDate.format(start)}–${shortDate.format(end)}</div>
          </div>`;
      })
      .join("");
  }

  function normalizedChannel(value) {
    return value || "Источник не указан";
  }

  function hierarchyKey(...values) {
    return values.map((value) => String(value || "")).join("\u241f");
  }

  function adBreakdown(detailRows) {
    return [...grouped(detailRows, (row) => row.ad_id || `title:${row.ad_title || ""}`).values()]
      .map((rows) => ({
        id: rows[0].ad_id || "",
        title: rows.find((row) => row.ad_title)?.ad_title || "",
        spend: sum(rows, "spend"),
        impressions: sum(rows, "impressions"),
        clicks: sum(rows, "clicks"),
        conversions: sum(rows, "leads"),
      }))
      .sort((a, b) => b.conversions - a.conversions || b.spend - a.spend || a.id.localeCompare(b.id));
  }

  function adGroupBreakdown(detailRows) {
    return [...grouped(detailRows, (row) => row.ad_group_id || `name:${row.ad_group || ""}`).values()]
      .map((rows) => ({
        id: rows[0].ad_group_id || "",
        name: rows.find((row) => row.ad_group)?.ad_group || "Без названия группы",
        spend: sum(rows, "spend"),
        impressions: sum(rows, "impressions"),
        clicks: sum(rows, "clicks"),
        conversions: sum(rows, "leads"),
        ads: adBreakdown(rows),
      }))
      .sort((a, b) => b.conversions - a.conversions || b.spend - a.spend || a.name.localeCompare(b.name, "ru"));
  }

  function campaignBreakdown(adsRows, detailRows) {
    return [...grouped(adsRows, (row) => `${row.campaign_id || ""}\u241f${row.campaign || ""}`).values()]
      .map((rows) => {
        const id = rows[0].campaign_id || "";
        const name = rows[0].campaign || "Без названия кампании";
        const matchingDetails = detailRows.filter((row) =>
          id ? row.campaign_id === id : row.campaign === name
        );
        return {
          id,
          name,
          spend: sum(rows, "spend"),
          spendBasis: rows.find((row) => row.spend_basis)?.spend_basis || "",
          impressions: sum(rows, "impressions"),
          clicks: sum(rows, "clicks"),
          conversions: sum(rows, "leads"),
          conversionsAvailable: rows.some((row) => row.conversions_available),
          conversionLabel: rows.find((row) => row.conversion_label)?.conversion_label || "Конверсии кабинета",
          conversionDefinition:
            rows.find((row) => row.conversion_definition)?.conversion_definition || "",
          groups: adGroupBreakdown(matchingDetails),
        };
      })
      .sort((a, b) => b.spend - a.spend || b.clicks - a.clicks || a.name.localeCompare(b.name));
  }

  function performanceCells(item, conversionsAvailable) {
    const ctr = ratio(item.clicks, item.impressions);
    const cpc = item.clicks ? money.format(item.spend / item.clicks) : "—";
    const conversions = conversionsAvailable ? number.format(item.conversions) : "—";
    const cpa = conversionsAvailable && item.conversions
      ? money.format(item.spend / item.conversions)
      : "—";
    return `
      <td>${item.spend ? money.format(item.spend) : "—"}</td>
      <td>${item.impressions ? number.format(item.impressions) : "—"}</td>
      <td>${item.clicks ? number.format(item.clicks) : "—"}</td>
      <td>${item.impressions ? percent.format(ctr) : "—"}</td>
      <td>${cpc}</td>
      <td>${conversions}</td>
      <td>${cpa}</td>`;
  }

  function renderAdDetails(channel, campaign, group) {
    const rows = group.ads
      .map((ad) => {
        const title = ad.title || (ad.id ? `Объявление ${ad.id}` : "Объявление без названия");
        return `
          <tr>
            <td>
              <strong>${safe(title)}</strong>
              ${ad.id ? `<small class="campaign-id">ID ${safe(ad.id)}</small>` : ""}
            </td>
            ${performanceCells(ad, campaign.conversionsAvailable)}
          </tr>`;
      })
      .join("");

    return `
      <tr class="ad-detail-row">
        <td colspan="8">
          <div class="hierarchy-detail ad-detail">
            <div class="hierarchy-detail-heading">
              <strong>Объявления · ${safe(group.name)}</strong>
              <span>${number.format(group.ads.length)} объявлений</span>
            </div>
            <div class="campaign-table-wrap">
              <table class="ad-table">
                <thead>
                  <tr>
                    <th>Объявление</th>
                    <th>Расход с НДС</th>
                    <th>Показы</th>
                    <th>Клики</th>
                    <th>CTR</th>
                    <th>CPC</th>
                    <th>${safe(campaign.conversionLabel)}</th>
                    <th>CPA лида</th>
                  </tr>
                </thead>
                <tbody>${rows}</tbody>
              </table>
            </div>
          </div>
        </td>
      </tr>`;
  }

  function renderGroupDetails(channel, campaign) {
    const rows = campaign.groups
      .map((group) => {
        const key = hierarchyKey(channel, campaign.id, campaign.name, group.id, group.name);
        const expanded = expandedAdGroups.has(key);
        const control = group.ads.length
          ? `<button
               type="button"
               class="channel-toggle hierarchy-toggle"
               data-group-detail-toggle="${safe(key)}"
               aria-expanded="${expanded}"
             >
               <span class="channel-chevron" aria-hidden="true">›</span>
               <span>
                 <strong>${safe(group.name)}</strong>
                 <small>${group.id ? `ID ${safe(group.id)} · ` : ""}${number.format(group.ads.length)} объявлений</small>
               </span>
             </button>`
          : `<span><strong>${safe(group.name)}</strong>${group.id ? `<small class="campaign-id">ID ${safe(group.id)}</small>` : ""}</span>`;
        const summary = `
          <tr class="hierarchy-summary-row${expanded ? " expanded" : ""}">
            <td>${control}</td>
            ${performanceCells(group, campaign.conversionsAvailable)}
          </tr>`;
        return summary + (expanded ? renderAdDetails(channel, campaign, group) : "");
      })
      .join("");

    return `
      <tr class="group-detail-row">
        <td colspan="8">
          <div class="hierarchy-detail group-detail">
            <div class="hierarchy-detail-heading">
              <strong>Группы · ${safe(campaign.name)}</strong>
              <span>${number.format(campaign.groups.length)} групп</span>
            </div>
            <div class="campaign-table-wrap">
              <table class="group-table">
                <thead>
                  <tr>
                    <th>Группа</th>
                    <th>Расход с НДС</th>
                    <th>Показы</th>
                    <th>Клики</th>
                    <th>CTR</th>
                    <th>CPC</th>
                    <th>${safe(campaign.conversionLabel)}</th>
                    <th>CPA лида</th>
                  </tr>
                </thead>
                <tbody>${rows}</tbody>
              </table>
            </div>
          </div>
        </td>
      </tr>`;
  }

  function renderCampaignDetails(channel, campaigns) {
    const conversionLabel = campaigns[0]?.conversionLabel || "Конверсии кабинета";
    const conversionDefinition = campaigns[0]?.conversionDefinition || "";
    const groupCount = campaigns.reduce((total, campaign) => total + campaign.groups.length, 0);
    const adCount = campaigns.reduce(
      (total, campaign) => total + campaign.groups.reduce((sum, group) => sum + group.ads.length, 0),
      0
    );
    const rows = campaigns
      .map((campaign) => {
        const key = hierarchyKey(channel, campaign.id, campaign.name);
        const expanded = expandedCampaigns.has(key);
        const adTotal = campaign.groups.reduce((total, group) => total + group.ads.length, 0);
        const control = campaign.groups.length
          ? `<button
               type="button"
               class="channel-toggle hierarchy-toggle"
               data-campaign-detail-toggle="${safe(key)}"
               aria-expanded="${expanded}"
             >
               <span class="channel-chevron" aria-hidden="true">›</span>
               <span>
                 <strong>${safe(campaign.name)}</strong>
                 <small>${campaign.id ? `ID ${safe(campaign.id)} · ` : ""}${number.format(campaign.groups.length)} групп · ${number.format(adTotal)} объявлений</small>
               </span>
             </button>`
          : `<span><strong>${safe(campaign.name)}</strong>${campaign.id ? `<small class="campaign-id">ID ${safe(campaign.id)}</small>` : ""}</span>`;
        const summary = `
          <tr class="hierarchy-summary-row${expanded ? " expanded" : ""}">
            <td>${control}</td>
            ${performanceCells(campaign, campaign.conversionsAvailable)}
          </tr>`;
        return summary + (expanded ? renderGroupDetails(channel, campaign) : "");
      })
      .join("");

    return `
      <tr class="campaign-detail-row">
        <td colspan="12">
          <div class="campaign-detail">
            <div class="campaign-detail-heading">
              <strong>Кампании · ${safe(channel)}</strong>
              <span>${number.format(campaigns.length)} кампаний${groupCount ? ` · ${number.format(groupCount)} групп · ${number.format(adCount)} объявлений` : ""}. Данные рекламного кабинета${
                conversionDefinition ? `; ${safe(conversionLabel)} — ${safe(conversionDefinition)}` : ""
              }; без привязки к новым и повторным до передачи UTM в Б24</span>
            </div>
            <div class="campaign-table-wrap">
              <table class="campaign-table">
                <thead>
                  <tr>
                    <th>Кампания</th>
                    <th>Расход с НДС</th>
                    <th>Показы</th>
                    <th>Клики</th>
                    <th>CTR</th>
                    <th>CPC</th>
                    <th>${safe(conversionLabel)}</th>
                    <th>CPA лида</th>
                  </tr>
                </thead>
                <tbody>${rows}</tbody>
              </table>
            </div>
          </div>
        </td>
      </tr>`;
  }

  function renderChannels(funnelRows, salesRows, adsRows, adDetailRows) {
    const revenueMode = data.meta.revenue_mode === "onec";
    const roiMargin = Number(data.meta.roi_margin || 0.3);
    const segmentFunnelRows = funnelRows.filter(
      (row) => channelSegment === "all" || row.segment === channelSegment
    );
    const segmentSalesRows = salesRows.filter(
      (row) => channelSegment === "all" || row.segment === channelSegment
    );
    const channels = new Set([
      ...segmentFunnelRows.map((row) => normalizedChannel(row.source)),
      ...segmentSalesRows.map((row) => normalizedChannel(row.source)),
      ...adsRows.map((row) => normalizedChannel(row.platform)),
    ]);

    const rows = [...channels]
      .map((channel) => {
        const funnel = funnelMetrics(
          segmentFunnelRows.filter((row) => normalizedChannel(row.source) === channel)
        );
        const sales = segmentSalesRows.filter((row) => normalizedChannel(row.source) === channel);
        const ads = adsRows.filter((row) => normalizedChannel(row.platform) === channel);
        const details = adDetailRows.filter((row) => normalizedChannel(row.platform) === channel);
        const revenue = revenueMode ? sum(sales, "revenue") : funnel.b24Amount;
        return {
          channel,
          ...funnel,
          revenue,
          orders: sum(sales, "orders"),
          spend: sum(ads, "spend"),
          spendBasis: ads.find((row) => row.spend_basis)?.spend_basis || "",
          impressions: sum(ads, "impressions"),
          clicks: sum(ads, "clicks"),
          leads: sum(ads, "leads"),
          campaigns: campaignBreakdown(ads, details),
        };
      })
      .sort((a, b) => b.revenue - a.revenue || b.deals - a.deals);

    if (!rows.length) {
      els["channel-rows"].innerHTML = '<tr><td colspan="12" class="empty-state">Нет данных за выбранный период</td></tr>';
      return;
    }

    els["channel-rows"].innerHTML = rows
      .map((row) => {
        const leadBase = row.deals;
        const sql = row.spend && leadBase ? money.format(row.spend / leadBase) : "—";
        const cac = revenueMode && row.spend > 0 && row.orders > 0
          ? money.format(row.spend / row.orders)
          : "—";
        const roas = revenueMode && row.spend > 0 && row.revenue > 0
          ? `${(row.revenue / row.spend).toFixed(2)}×`
          : "—";
        const roi = revenueMode && row.spend > 0 && row.revenue > 0
          ? percent.format((row.revenue * roiMargin - row.spend) / row.spend)
          : "—";
        const expanded = expandedChannels.has(row.channel);
        const groupCount = row.campaigns.reduce((total, campaign) => total + campaign.groups.length, 0);
        const adCount = row.campaigns.reduce(
          (total, campaign) => total + campaign.groups.reduce((sum, group) => sum + group.ads.length, 0),
          0
        );
        const campaignControl = row.campaigns.length
          ? `<button
               type="button"
               class="channel-toggle"
               data-channel-toggle="${safe(row.channel)}"
               aria-expanded="${expanded}"
             >
               <span class="channel-chevron" aria-hidden="true">›</span>
               <span>
                 <strong>${safe(row.channel)}</strong>
                 <small>${number.format(row.campaigns.length)} кампаний${groupCount ? ` · ${number.format(groupCount)} групп · ${number.format(adCount)} объявлений` : ""}</small>
               </span>
             </button>`
          : `<strong>${safe(row.channel)}</strong>`;
        const summaryRow = `
          <tr class="channel-summary-row${expanded ? " expanded" : ""}">
            <td>${campaignControl}</td>
            <td>${
              row.spend
                ? `${money.format(row.spend)}${
                    row.spendBasis ? `<small class="cell-note">${safe(row.spendBasis)}</small>` : ""
                  }`
                : "—"
            }</td>
            <td>${row.impressions ? number.format(row.impressions) : "—"}</td>
            <td>${row.clicks ? number.format(row.clicks) : "—"}</td>
            <td>${number.format(row.deals)}</td>
            <td>${number.format(row.success)}</td>
            <td>${percent.format(ratio(row.success, row.deals))}</td>
            <td>${money.format(row.revenue)}</td>
            <td>${sql}</td>
            <td>${cac}</td>
            <td>${roas}</td>
            <td>${roi}</td>
          </tr>`;
        return summaryRow + (expanded ? renderCampaignDetails(row.channel, row.campaigns) : "");
      })
      .join("");

    els["channel-rows"].querySelectorAll("[data-channel-toggle]").forEach((button) => {
      button.addEventListener("click", () => {
        const channel = button.dataset.channelToggle;
        if (expandedChannels.has(channel)) expandedChannels.delete(channel);
        else expandedChannels.add(channel);
        renderChannels(funnelRows, salesRows, adsRows, adDetailRows);
      });
    });
    els["channel-rows"].querySelectorAll("[data-campaign-detail-toggle]").forEach((button) => {
      button.addEventListener("click", () => {
        const key = button.dataset.campaignDetailToggle;
        if (expandedCampaigns.has(key)) expandedCampaigns.delete(key);
        else expandedCampaigns.add(key);
        renderChannels(funnelRows, salesRows, adsRows, adDetailRows);
      });
    });
    els["channel-rows"].querySelectorAll("[data-group-detail-toggle]").forEach((button) => {
      button.addEventListener("click", () => {
        const key = button.dataset.groupDetailToggle;
        if (expandedAdGroups.has(key)) expandedAdGroups.delete(key);
        else expandedAdGroups.add(key);
        renderChannels(funnelRows, salesRows, adsRows, adDetailRows);
      });
    });
  }

  function renderKeywords(keywordRows, adsRows) {
    const yandexAds = adsRows.filter((row) => row.platform === "Яндекс Директ");
    const totalLeads = sum(yandexAds, "leads");
    const attributedRows = keywordRows.filter((row) => String(row.keyword || "").trim());
    const attributedLeads = sum(attributedRows, "leads");
    const blankRows = keywordRows.filter((row) => !String(row.keyword || "").trim());
    const autotargetLeads = sum(
      blankRows.filter((row) => String(row.condition_type || "").toLocaleLowerCase("ru-RU").includes("автотаргет")),
      "leads"
    );
    const otherUnattributedLeads = Math.max(0, totalLeads - attributedLeads - autotargetLeads);

    setText(
      "keyword-coverage",
      totalLeads
        ? `${number.format(attributedLeads)} из ${number.format(totalLeads)} лидов привязаны к ключевым фразам; ${number.format(autotargetLeads)} — автотаргетинг${
            otherUnattributedLeads ? `; ${number.format(otherUnattributedLeads)} — без фразы` : ""
          }`
        : "Нет лидов Яндекса за выбранный период"
    );

    const rows = [...grouped(attributedRows, (row) => row.keyword.trim().toLocaleLowerCase("ru-RU")).values()]
      .map((items) => ({
        keyword: items[0].keyword,
        impressions: sum(items, "impressions"),
        clicks: sum(items, "clicks"),
        spend: sum(items, "spend"),
        leads: sum(items, "leads"),
      }))
      .filter((row) => row.leads > 0)
      .sort(
        (a, b) =>
          b.leads - a.leads ||
          ratio(a.spend, a.leads) - ratio(b.spend, b.leads) ||
          a.keyword.localeCompare(b.keyword, "ru")
      )
      .slice(0, 10);

    if (!rows.length) {
      els["keyword-rows"].innerHTML = '<tr><td colspan="8" class="empty-state">Нет ключевых фраз с лидами за выбранный период</td></tr>';
      return;
    }

    els["keyword-rows"].innerHTML = rows
      .map(
        (row, index) => `
          <tr>
            <td><span class="keyword-rank">${index + 1}</span></td>
            <td class="keyword-name">${safe(row.keyword)}</td>
            <td><strong>${number.format(row.leads)}</strong></td>
            <td>${money.format(row.spend)}</td>
            <td>${money.format(row.spend / row.leads)}</td>
            <td>${number.format(row.clicks)}</td>
            <td>${percent.format(ratio(row.leads, row.clicks))}</td>
            <td>${number.format(row.impressions)}</td>
          </tr>`
      )
      .join("");
  }

  function qualityItem(label, value, state = "") {
    return `<div class="quality-item ${state}"><span>${safe(label)}</span><strong>${safe(value)}</strong></div>`;
  }

  function renderQuality() {
    const q = data.quality || {};
    const matchState = q.onec_orders && q.matched_orders / q.onec_orders >= 0.95 ? "good" : q.onec_orders ? "warning" : "";
    const items = [
      qualityItem("Сделок в базе Б24", number.format(q.b24_deals || 0), q.b24_deals ? "good" : "warning"),
      qualityItem("Строк 1С", number.format(q.onec_rows || 0), q.onec_rows ? "good" : "warning"),
      qualityItem("Заказов 1С без коррекций", number.format(q.onec_orders || 0)),
      qualityItem("Сопоставлено с Б24", number.format(q.matched_orders || 0), matchState),
      qualityItem("По заказ-наряду", number.format(q.matched_by_order || 0)),
      qualityItem("По телефону", number.format(q.matched_by_phone || 0)),
      qualityItem("Ручных связок", number.format(q.matched_by_manual || 0)),
      qualityItem("Не сопоставлено", number.format(q.unmatched_orders || 0), q.unmatched_orders ? "warning" : "good"),
      qualityItem("Неоднозначное сопоставление", number.format(q.ambiguous_orders || 0), q.ambiguous_orders ? "warning" : "good"),
      qualityItem("Успешных без заказ-наряда", number.format(q.success_without_order || 0), q.success_without_order ? "warning" : "good"),
      qualityItem("Строк рекламы", number.format(q.ads_rows || 0), q.ads_rows ? "good" : "warning"),
      qualityItem("Последний импорт", q.last_import_at || "—"),
    ];
    els["quality-list"].innerHTML = items.join("");
  }

  function render() {
    const from = els["date-from"].value;
    const to = els["date-to"].value;
    if (!from || !to) return;

    const funnelRows = rowsForPeriod(data.daily_funnel, from, to);
    const salesRows = rowsForPeriod(data.daily_sales, from, to);
    const adsRows = rowsForPeriod(data.daily_ads, from, to);
    const keywordRows = rowsForPeriod(data.daily_keywords || [], from, to);
    const adDetailRows = rowsForPeriod(data.daily_ad_details || [], from, to);
    const total = funnelMetrics(funnelRows);
    const revenue = revenueFor("all", funnelRows, salesRows);
    const revenueMode = data.meta.revenue_mode === "onec";
    const attributionRate = Number(data.meta.attribution_match_rate || 0);
    const roiMargin = Number(data.meta.roi_margin || 0.3);

    setText("period-caption", `${fullDate.format(parseDate(from))} — ${fullDate.format(parseDate(to))}`);
    setText("footer-range", `Период: ${from} — ${to}`);
    setText("kpi-deals", number.format(total.deals));
    setText("kpi-success", number.format(total.success));
    setText("kpi-success-share", `${number.format(total.success)} из ${number.format(total.deals)} сделок`);
    setText("kpi-cr", percent.format(ratio(total.success, total.deals)));
    setText("kpi-booked", number.format(total.booked));
    setText("revenue-label", revenueMode ? "Фактическая выручка 1С" : "Сумма сделок Б24");
    setText("segment-revenue-label", revenueMode ? "Выручка 1С" : "Сумма Б24");
    setText("revenue-per-deal-label", revenueMode ? "Выручка на сделку" : "Сумма Б24 / сделку");
    setText("segment-revenue-per-deal-label", revenueMode ? "Выручка / сделку" : "Сумма Б24 / сделку");
    setText(
      "channel-revenue-label",
      revenueMode ? "Выручка 1С (связано)" : "Сумма Б24"
    );
    setText(
      "channel-note",
      revenueMode
        ? `С Б24 связано ${percent.format(attributionRate)} заказов 1С; CAC/ROAS/ROI считаются по каналу при наличии расхода и связанной продажи; ROI — при марже ${percent.format(roiMargin)}`
        : "Заявки — сделки Б24; до загрузки 1С сумма Б24 справочно, CAC/ROAS/ROI не считаются"
    );
    setText("kpi-revenue", money.format(revenue));
    setText(
      "revenue-note",
      revenueMode
        ? `по дате реализации 1С; с Б24 связано ${percent.format(attributionRate)}`
        : "временно, до первой выгрузки 1С"
    );
    setText("kpi-revenue-per-deal", total.deals ? money.format(revenue / total.deals) : "—");

    renderSegments(funnelRows, salesRows);
    renderWeekly(funnelRows);
    renderChannels(funnelRows, salesRows, adsRows, adDetailRows);
    renderKeywords(keywordRows, adsRows);
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
    render();
  }

  document.querySelectorAll("[data-preset]").forEach((button) => {
    button.addEventListener("click", () => selectPreset(button.dataset.preset));
  });
  document.querySelectorAll("[data-channel-segment]").forEach((button) => {
    button.addEventListener("click", () => {
      channelSegment = button.dataset.channelSegment;
      document.querySelectorAll("[data-channel-segment]").forEach((item) => {
        const active = item.dataset.channelSegment === channelSegment;
        item.classList.toggle("active", active);
        item.setAttribute("aria-pressed", String(active));
      });
      render();
    });
  });
  const primaryPeriodChanged = () => {
    document.querySelectorAll("[data-preset]").forEach((button) => button.classList.remove("active"));
    render();
  };
  els["date-from"].addEventListener("change", primaryPeriodChanged);
  els["date-to"].addEventListener("change", primaryPeriodChanged);

  setText("generated-at", data.meta.generated_at_display || "—");
  setText("data-sources", data.meta.source_caption || "Данные ещё не загружены");
  renderQuality();

  if (allDates.length) {
    selectPreset("month");
  } else {
    const today = isoDate(new Date());
    els["date-from"].value = today;
    els["date-to"].value = today;
    render();
  }
})();
