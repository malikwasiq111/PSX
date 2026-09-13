// ═══════════════════════════════════════════════════════════════
//  PSX AI ANALYST — Frontend v5.0
//  Multi-panel SPA with Search, Alerts, Watchlist, PDF Export,
//  Dark/Light Mode, Browser Notifications, Signal History
// ═══════════════════════════════════════════════════════════════

const API = location.origin;

// ── State ────────────────────────────────────────────────────
let allStocks = [];
let allNews = [];
let kse100Stocks = [];  // symbols in KSE-100
let kmi30Stocks = [];   // symbols in KMI-30
let currentFilter = "all";
let currentNewsFilter = "all";
let currentDivFilter = "all";
let currentAnnFilter = "all";
let currentPanel = "market";
let currentDetailSymbol = null;
let priceChart = null;
let notificationsEnabled = Notification.permission === "granted";
let shownAlertIds = new Set(JSON.parse(localStorage.getItem("psx_shown_alerts") || "[]"));
let searchTimeout = null;

// ── Helpers ──────────────────────────────────────────────────
function fmt(n, dec = 2) {
  if (n == null || isNaN(n)) return "—";
  return Number(n).toLocaleString("en-PK", { minimumFractionDigits: dec, maximumFractionDigits: dec });
}
function chgClass(v) { return v > 0 ? "up" : v < 0 ? "down" : "flat"; }
function chgArrow(v) { return v > 0 ? "▲" : v < 0 ? "▼" : "–"; }
function signalClass(sig) {
  if (!sig) return "sig-loading";
  return "sig-" + sig.replace(/ /g, "-");
}
function timeSince(isoStr) {
  if (!isoStr) return "—";
  const diff = Math.floor((Date.now() - new Date(isoStr)) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return new Date(isoStr).toLocaleDateString("en-PK", { day: "numeric", month: "short" });
}
function volFmt(v) {
  if (!v) return "—";
  if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
  if (v >= 1e3) return (v / 1e3).toFixed(0) + "K";
  return v.toString();
}

// ══════════════════════════════════════════════════════════════
//  PANEL NAVIGATION
// ══════════════════════════════════════════════════════════════
function navigateTo(panel, data = null) {
  currentPanel = panel;

  // Update nav buttons
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  const activeBtn = document.querySelector(`.nav-btn[data-panel="${panel}"]`);
  if (activeBtn) activeBtn.classList.add("active");

  // Show panel
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  const target = document.getElementById(`panel-${panel}`);
  if (target) target.classList.add("active");

  // Panel-specific actions
  switch (panel) {
    case "market":
      break;
    case "stock-detail":
      if (data) loadStockDetail(data);
      break;
    case "watchlist":
      fetchWatchlist();
      break;
    case "portfolio":
      fetchPortfolio();
      break;
    case "dividends":
      fetchDividends();
      break;
    case "announcements":
      fetchAnnouncements();
      break;
    case "alerts":
      fetchAlerts();
      break;
    case "signals":
      fetchSignalHistory();
      break;
    case "chat":
      fetchChatHistory();
      break;
  }

  // Update URL hash
  window.location.hash = panel === "stock-detail" && data ? `stock/${data}` : panel;
}

// Handle back/forward buttons
window.addEventListener("hashchange", () => {
  const hash = window.location.hash.slice(1);
  if (hash.startsWith("stock/")) {
    navigateTo("stock-detail", hash.split("/")[1]);
  } else if (hash) {
    navigateTo(hash);
  }
});

// ══════════════════════════════════════════════════════════════
//  SET STOCK FILTER (called from topbar index clicks)
// ══════════════════════════════════════════════════════════════
function setStockFilter(filter) {
  currentFilter = filter;
  // Update chip active state
  document.querySelectorAll(".filter-chips:not(.news-chips) .chip").forEach(b => b.classList.remove("active"));
  const targetChip = document.querySelector(`.filter-chips:not(.news-chips) .chip[data-filter="${filter}"]`);
  if (targetChip) targetChip.classList.add("active");

  // Update heading
  const heading = document.querySelector(".stock-panel-header h2");
  if (heading) {
    if (filter === "kse100") heading.textContent = "KSE-100 Stocks";
    else if (filter === "kmi30") heading.textContent = "KMI-30 Stocks";
    else heading.textContent = "All Stocks";
  }

  renderStocks(allStocks);
}

// ══════════════════════════════════════════════════════════════
//  TOP BAR — KSE-100, KMI-30, USD/PKR, Sentiment
// ══════════════════════════════════════════════════════════════
function updateTopBar(market) {
  if (!market) return;
  const { kse100, kmi30, pkr, market_analysis, last_updated } = market;

  // KSE-100
  if (kse100) {
    document.getElementById("kse-value").textContent = kse100.value ? Number(kse100.value).toLocaleString("en-PK", { maximumFractionDigits: 0 }) : "—";
    const chgEl = document.getElementById("kse-change");
    chgEl.textContent = `${chgArrow(kse100.change_pct)} ${Math.abs(kse100.change_pct || 0).toFixed(2)}%`;
    chgEl.className = `kse-change ${chgClass(kse100.change_pct)}`;
  }

  // KMI-30
  if (kmi30) {
    document.getElementById("kmi30-value").textContent = kmi30.value ? Number(kmi30.value).toLocaleString("en-PK", { maximumFractionDigits: 0 }) : "—";
    const kmiChgEl = document.getElementById("kmi30-change");
    kmiChgEl.textContent = `${chgArrow(kmi30.change_pct)} ${Math.abs(kmi30.change_pct || 0).toFixed(2)}%`;
    kmiChgEl.className = `kse-change ${chgClass(kmi30.change_pct)}`;
  }

  // USD/PKR
  if (pkr) {
    document.getElementById("pkr-value").textContent = fmt(pkr.rate, 2);
    const chgEl = document.getElementById("pkr-change");
    chgEl.textContent = `${chgArrow(pkr.change_pct)} ${Math.abs(pkr.change_pct || 0).toFixed(2)}%`;
    chgEl.className = `macro-chg ${pkr.change_pct >= 0 ? "down" : "up"}`;
  }

  // Market Sentiment
  if (market_analysis) {
    const sent = market_analysis.overall_sentiment || "Neutral";
    document.getElementById("market-sentiment").textContent = sent.toUpperCase();
  }

  document.getElementById("update-time").textContent = timeSince(last_updated);
}

// ══════════════════════════════════════════════════════════════
//  MARKET OVERVIEW BANNER
// ══════════════════════════════════════════════════════════════
function renderMarketBanner(ma) {
  if (!ma) return;

  const score = ma.sentiment_score || 0;
  const scoreEl = document.getElementById("banner-score");
  scoreEl.textContent = (score > 0 ? "+" : "") + score;
  scoreEl.className = `banner-score ${score > 0 ? "positive" : score < 0 ? "negative" : "neutral"}`;

  document.getElementById("banner-summary").textContent = ma.summary || "—";

  document.getElementById("banner-tags").innerHTML = (ma.key_drivers || [])
    .map(d => `<span class="banner-tag">⚡ ${d}</span>`).join("");

  document.getElementById("banner-hot").innerHTML = (ma.hot_sectors || [])
    .map(s => `<span class="sec-tag hot">${s}</span>`).join("") || "<span style='color:var(--text-tertiary)'>—</span>";
  document.getElementById("banner-weak").innerHTML = (ma.weak_sectors || [])
    .map(s => `<span class="sec-tag weak">${s}</span>`).join("") || "<span style='color:var(--text-tertiary)'>—</span>";

  const adviceBar = document.getElementById("market-advice-bar");
  if (ma.market_advice || ma.watch_out) {
    adviceBar.innerHTML = `💡 ${ma.market_advice || ""} ${ma.watch_out ? `<br>⚠️ ${ma.watch_out}` : ""}`;
    adviceBar.classList.add("visible");
  }
}

// ══════════════════════════════════════════════════════════════
//  SECTOR STRIP
// ══════════════════════════════════════════════════════════════
function renderSectors(sectors) {
  if (!sectors || !sectors.length) return;
  document.getElementById("sector-strip").innerHTML = sectors.map(s => {
    const chg = s.change_pct || s.avg_change || 0;
    const trend = chg > 0 ? "up" : chg < 0 ? "down" : "flat";
    return `
    <div class="sector-chip ${trend}">
      <span class="sector-chip-name">${s.sector}</span>
      <span class="sector-chip-val ${trend}">${chgArrow(chg)} ${Math.abs(chg).toFixed(2)}%</span>
    </div>`;
  }).join("");
}

// ══════════════════════════════════════════════════════════════
//  STOCK TABLE — with KSE100/KMI30 filtering
// ══════════════════════════════════════════════════════════════
function applyStockFilter(stocks) {
  switch (currentFilter) {
    case "shariah": return stocks.filter(s => s.shariah);
    case "gainers": return [...stocks].sort((a, b) => b.change_pct - a.change_pct).filter(s => s.change_pct > 0);
    case "losers": return [...stocks].sort((a, b) => a.change_pct - b.change_pct).filter(s => s.change_pct < 0);
    case "kse100": return stocks.filter(s => kse100Stocks.includes(s.symbol));
    case "kmi30": return stocks.filter(s => kmi30Stocks.includes(s.symbol));
    default: return stocks;
  }
}

function renderStocks(stocks) {
  const tbody = document.getElementById("stock-tbody");
  const filtered = applyStockFilter(stocks);

  // Update count in header
  const heading = document.querySelector(".stock-panel-header h2");
  if (heading) {
    const label = currentFilter === "kse100" ? "KSE-100" : currentFilter === "kmi30" ? "KMI-30" : currentFilter === "all" ? "All" : currentFilter.charAt(0).toUpperCase() + currentFilter.slice(1);
    heading.textContent = `${label} Stocks (${filtered.length})`;
  }

  if (!filtered.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No stocks found.</td></tr>`;
    return;
  }
  tbody.innerHTML = filtered.map(s => `
    <tr onclick="navigateTo('stock-detail','${s.symbol}')">
      <td>
        <span class="stock-sym">${s.symbol}</span>
        <span class="stock-name-cell">${s.name}</span>
      </td>
      <td><span class="stock-price">₨${fmt(s.price)}</span></td>
      <td><span class="stock-chg ${chgClass(s.change_pct)}">${chgArrow(s.change_pct)} ${Math.abs(s.change_pct).toFixed(2)}%</span></td>
      <td><span class="stock-vol">${volFmt(s.volume)}</span></td>
      <td><span class="signal-badge ${signalClass(s._signal || null)}">${s._signal || "···"}</span></td>
      <td>${s.shariah ? '<span class="halal-badge">Halal</span>' : ""}</td>
    </tr>`).join("");
}

// ══════════════════════════════════════════════════════════════
//  NEWS FEED
// ══════════════════════════════════════════════════════════════
function renderNews(news) {
  const feed = document.getElementById("news-feed");
  const filtered = currentNewsFilter === "all" ? news : news.filter(n => n.sentiment === currentNewsFilter);
  if (!filtered.length) { feed.innerHTML = `<div class="empty-state">No news found.</div>`; return; }
  feed.innerHTML = filtered.map(n => `
    <div class="news-card ${n.sentiment}" onclick="window.open('${n.link}','_blank')">
      <div class="news-title">
        <span class="news-badge ${n.sentiment}">${(n.sentiment || "neutral").toUpperCase()}</span>
        ${n.title}
      </div>
      ${n.market_impact ? `<div style="margin: 4px 0"><span class="news-badge ${n.market_impact === 'market_positive' ? 'positive' : 'negative'}">${n.market_impact === "market_positive" ? "📈 MARKET POSITIVE" : "📉 MARKET NEGATIVE"}</span></div>` : ""}
      <div class="news-meta">
        <span>${n.source}</span>
        <span>·</span>
        <span>${timeSince(n.timestamp)}</span>
        ${(n.related_stocks || []).map(sym =>
    `<span class="news-stock-tag" onclick="event.stopPropagation();navigateTo('stock-detail','${sym}')">${sym}</span>`
  ).join("")}
      </div>
    </div>`).join("");
}

// ══════════════════════════════════════════════════════════════
//  STOCK DETAIL PANEL
// ══════════════════════════════════════════════════════════════
async function loadStockDetail(symbol) {
  currentDetailSymbol = symbol;
  const content = document.getElementById("detail-content");
  content.innerHTML = `<div class="empty-state" style="padding:60px 0"><div class="loading-spinner"></div>Loading ${symbol}...</div>`;
  if (priceChart) { priceChart.destroy(); priceChart = null; }

  try {
    // Fetch all data in parallel
    const [mainRes, liveRes, histRes, insidersRes, reportsRes, annsRes] = await Promise.allSettled([
      fetch(`${API}/api/stocks/${symbol}`),
      fetch(`${API}/api/live/stock/${symbol}`),
      fetch(`${API}/api/live/price-history/${symbol}?days=30`),
      fetch(`${API}/api/live/insiders/${symbol}`),
      fetch(`${API}/api/live/reports/${symbol}`),
      fetch(`${API}/api/live/announcements/${symbol}`),
    ]);

    const main     = mainRes.status === "fulfilled"     ? await mainRes.value.json()     : {};
    const live     = liveRes.status === "fulfilled"     ? await liveRes.value.json()     : {};
    const hist     = histRes.status === "fulfilled"     ? await histRes.value.json()     : {};
    const insiders = insidersRes.status === "fulfilled" ? await insidersRes.value.json() : {};
    const reports  = reportsRes.status === "fulfilled"  ? await reportsRes.value.json()  : {};
    const anns     = annsRes.status === "fulfilled"     ? await annsRes.value.json()     : {};

    if (main.error) {
      content.innerHTML = `<div class="empty-state" style="color:var(--red)">Stock ${symbol} not found</div>`;
      return;
    }
    renderStockDetail(main, live.data || null, hist.data || [], insiders.data || [], reports.data || [], anns.data || []);
  } catch (e) {
    content.innerHTML = `<div class="empty-state" style="color:var(--red)">Error loading data: ${e.message}</div>`;
  }
}

function renderStockDetail({ stock, signal, technical, announcements: legacyAnns, news: related_news }, liveData, priceHistory, insiders, reports, sarmaayaAnns) {
  if (!stock) return;
  const s = stock;
  const sig = signal || {};
  const tech = technical || null;
  // Merge live data from Sarmaaya (richer) with cached data
  const ld = liveData || {};
  const price      = ld.close  || s.price || 0;
  const dayHigh    = ld.high   || s.high  || 0;
  const dayLow     = ld.low    || s.low   || 0;
  const prevClose  = ld.close  ? (ld.close - (ld.change || 0)) : s.prev_close || 0;
  const week52High = ld.high52 || "—";
  const week52Low  = ld.low52  || "—";
  const volume     = ld.volume || s.volume || 0;
  const changePct  = ld.change_percentage || s.change_pct || 0;
  const changeAbs  = ld.change || s.change || 0;
  const sectorName = ld.sectorName || s.sector || "—";
  const logoUrl    = ld.logo || s.logo || "";
  const isShariah  = ld.isshariah || s.shariah || false;
  // Compute market cap from price history (latest entry has marketCap)
  const marketCapRaw = priceHistory.length ? priceHistory[0].marketCap : null;
  const marketCapStr = marketCapRaw ? (marketCapRaw >= 1e12 ? (marketCapRaw/1e12).toFixed(2)+"T" : marketCapRaw >= 1e9 ? (marketCapRaw/1e9).toFixed(2)+"B" : (marketCapRaw/1e6).toFixed(0)+"M") : "—";

  const content = document.getElementById("detail-content");
  content.innerHTML = `
    <!-- Hero -->
    <div class="detail-hero">
      <div class="detail-stock-info">
        ${logoUrl ? `<img src="${logoUrl}" class="detail-logo" alt="${s.symbol}" onerror="this.style.display='none'">` : ""}
        <div>
          <h1>${s.symbol} ${isShariah ? '<span class="halal-badge" style="font-size:12px">Halal ✓</span>' : ""}</h1>
          <div class="detail-stock-meta">${s.name} · <span class="sector-tag-inline">${sectorName}</span></div>
          <div class="detail-stock-meta" style="margin-top:4px;font-size:11px;color:var(--text-tertiary)">${ld.exchangeid || "PSX"} · ISIN: ${ld.isin || "—"}</div>
        </div>
      </div>
      <div class="detail-price-box">
        <div class="detail-price">₨${fmt(price)}</div>
        <div class="detail-price-change ${chgClass(changePct)}">
          ${chgArrow(changePct)} ${Math.abs(changePct).toFixed(2)}% (₨${fmt(Math.abs(changeAbs))})
        </div>
      </div>
    </div>

    <!-- Rich Stats Grid -->
    <div class="detail-stats-grid detail-stats-grid-rich">
      <div class="detail-stat"><div class="detail-stat-label">PREV CLOSE</div><div class="detail-stat-value">₨${fmt(prevClose)}</div></div>
      <div class="detail-stat"><div class="detail-stat-label">DAY OPEN</div><div class="detail-stat-value">₨${fmt(dayLow && dayHigh ? (dayLow+dayHigh)/2 : price)}</div></div>
      <div class="detail-stat"><div class="detail-stat-label">DAY HIGH</div><div class="detail-stat-value" style="color:var(--green)">₨${fmt(dayHigh)}</div></div>
      <div class="detail-stat"><div class="detail-stat-label">DAY LOW</div><div class="detail-stat-value" style="color:var(--red)">₨${fmt(dayLow)}</div></div>
      <div class="detail-stat"><div class="detail-stat-label">VOLUME</div><div class="detail-stat-value">${volFmt(volume)}</div></div>
      <div class="detail-stat"><div class="detail-stat-label">MARKET CAP</div><div class="detail-stat-value">PKR ${marketCapStr}</div></div>
      <div class="detail-stat"><div class="detail-stat-label">52W HIGH</div><div class="detail-stat-value" style="color:var(--green)">₨${fmt(week52High)}</div></div>
      <div class="detail-stat"><div class="detail-stat-label">52W LOW</div><div class="detail-stat-value" style="color:var(--red)">₨${fmt(week52Low)}</div></div>
      <div class="detail-stat"><div class="detail-stat-label">RISK</div><div class="detail-stat-value" style="color:${sig.risk_level==='Low'?'var(--green)':sig.risk_level==='High'?'var(--red)':'var(--amber)'}">${sig.risk_level||"—"}</div></div>
      <div class="detail-stat"><div class="detail-stat-label">HOLD PERIOD</div><div class="detail-stat-value" style="font-size:13px">${sig.holding_period||"—"}</div></div>
    </div>

    <!-- 52-Week Range Bar -->
    ${(week52High !== "—" && week52Low !== "—") ? (() => {
      const lo = parseFloat(week52Low), hi = parseFloat(week52High), cur = parseFloat(price);
      const pct = hi > lo ? Math.round(((cur - lo) / (hi - lo)) * 100) : 50;
      return `<div class="range-bar-card">
        <div class="range-bar-label"><span>52-Week Range</span><span style="color:var(--text-tertiary);font-size:11px">₨${fmt(lo)} — ₨${fmt(hi)}</span></div>
        <div class="range-bar-track"><div class="range-bar-fill" style="width:${pct}%"></div><div class="range-bar-dot" style="left:${pct}%"></div></div>
        <div class="range-bar-labels"><span style="color:var(--red)">52W Low ₨${fmt(lo)}</span><span style="color:var(--text-tertiary)">${pct}% of range</span><span style="color:var(--green)">52W High ₨${fmt(hi)}</span></div>
      </div>`;
    })() : ""}

    <!-- AI Signal -->
    <div class="detail-signal-card">
      <div class="signal-card-header">
        <span class="signal-card-title">AI SIGNAL</span>
        <span class="signal-big ${signalClass(sig.signal)}">${sig.signal||"—"}</span>
      </div>
      <div class="price-targets-row">
        <div class="pt-box"><span class="pt-label">ENTRY</span><span class="pt-val entry">₨${fmt(sig.entry_price)}</span></div>
        <div class="pt-box"><span class="pt-label">TARGET</span><span class="pt-val target">₨${fmt(sig.target_price)}</span></div>
        <div class="pt-box"><span class="pt-label">STOP LOSS</span><span class="pt-val stop">₨${fmt(sig.stop_loss)}</span></div>
      </div>
      <div class="conf-bar">
        <div class="conf-bar-labels"><span>CONFIDENCE</span><span>${sig.confidence||0}%</span></div>
        <div class="conf-bar-track"><div class="conf-bar-fill" style="width:${sig.confidence||0}%"></div></div>
      </div>
      <div class="signal-reasoning">${sig.reasoning||"—"}</div>
      ${sig.technical_summary?`<div style="margin-top:8px;font-size:12px;color:var(--text-tertiary)">📊 ${sig.technical_summary}</div>`:""}
      ${sig.news_summary?`<div style="margin-top:4px;font-size:12px;color:var(--text-tertiary)">📰 ${sig.news_summary}</div>`:""}
      ${sig.key_risk?`<div class="signal-risk-tag risk-${sig.risk_level||'Medium'}">⚠️ ${sig.key_risk}</div>`:""}
    </div>

    <!-- 30-Day Price Chart from Sarmaaya -->
    ${priceHistory.length > 3 ? `
      <div class="chart-card">
        <div class="chart-card-title">30-DAY PRICE & VOLUME CHART</div>
        <div class="chart-container"><canvas id="price-chart"></canvas></div>
      </div>` : (tech && tech.chart_data && tech.chart_data.length > 5 ? `
      <div class="chart-card">
        <div class="chart-card-title">90-DAY PRICE CHART + MA20/MA50</div>
        <div class="chart-container"><canvas id="price-chart"></canvas></div>
      </div>` : "")}

    <!-- Technical Indicators -->
    ${tech ? renderTechPanel(tech) : ""}

    <!-- Insider Trading -->
    ${insiders.length ? `
      <div class="detail-section-title">🔍 INSIDER TRADING</div>
      <div class="insider-table-wrap">
        <table class="insider-table">
          <thead><tr><th>NAME</th><th>POSITION</th><th>ACTION</th><th>QTY</th><th>RATE</th><th>DATE</th></tr></thead>
          <tbody>${insiders.slice(0,10).map(i=>{
            const isB = i.action==="Buy";
            return `<tr>
              <td style="font-weight:600">${i.name||"—"}</td>
              <td style="font-size:11px;color:var(--text-tertiary)">${i.position||"—"}</td>
              <td><span class="insider-badge ${isB?'buy':'sell'}">${isB?"▲ BUY":"▼ SELL"}</span></td>
              <td style="font-family:var(--font-mono)">${(i.quantity||0).toLocaleString()}</td>
              <td style="font-family:var(--font-mono)">₨${fmt(i.rate)}</td>
              <td style="font-size:11px;color:var(--text-tertiary)">${i.date?new Date(i.date).toLocaleDateString("en-PK",{day:"numeric",month:"short",year:"2-digit"}):"—"}</td>
            </tr>`;
          }).join("")}</tbody>
        </table>
      </div>` : ""}

    <!-- Financial Reports -->
    ${reports.length ? `
      <div class="detail-section-title">📄 FINANCIAL REPORTS</div>
      <div class="reports-grid">${reports.map(r=>`
        <div class="report-card">
          <span class="report-type-badge">${r.reportType||"REPORT"}</span>
          <div class="report-period">Period: ${r.periodEnded ? new Date(r.periodEnded).toLocaleDateString("en-PK",{month:"short",year:"numeric"}) : "—"}</div>
          <div class="report-posted">Posted: ${r.postingDate ? new Date(r.postingDate).toLocaleDateString("en-PK",{day:"numeric",month:"short",year:"numeric"}) : "—"}</div>
          ${(r.attachment||[]).find(a=>a.endsWith(".pdf")) ? `<a href="${(r.attachment||[]).find(a=>a.endsWith(".pdf"))}" target="_blank" class="report-link">📥 Download PDF</a>` : ""}
        </div>`).join("")}
      </div>` : ""}

    <!-- PSX Corporate Announcements -->
    ${sarmaayaAnns.length ? `
      <div class="detail-section-title">📢 CORPORATE ANNOUNCEMENTS</div>
      <div class="sarmaaya-anns-list">${sarmaayaAnns.slice(0,12).map(a=>`
        <div class="sarmaaya-ann-item">
          <div class="sann-date">${a.postingDate ? new Date(a.postingDate).toLocaleDateString("en-PK",{day:"numeric",month:"short",year:"numeric"}) : "—"}</div>
          <div class="sann-title">${a.announcementTitle||"—"}</div>
          ${(a.attachments||[]).find(x=>x.endsWith(".pdf")) ? `<a href="${(a.attachments||[]).find(x=>x.endsWith(".pdf"))}" target="_blank" class="dc-link">View PDF →</a>` : ""}
        </div>`).join("")}
      </div>` : (legacyAnns && legacyAnns.length ? `
      <div class="detail-section-title">📢 CORPORATE ANNOUNCEMENTS</div>
      ${legacyAnns.slice(0,6).map(a=>`
        <div class="detail-ann-card">
          <span class="ann-card-type ann-type-${a.type||'general'}">${a.type_label||a.type||'Announcement'}</span>
          <span style="font-size:13px;color:var(--text-primary)">${a.title}</span>
          ${a.amount ? `<span style="font-family:var(--font-mono);font-size:12px;color:var(--green);margin-left:8px">PKR ${a.amount}</span>` : ""}
          ${a.date ? `<span style="font-family:var(--font-mono);font-size:10px;color:var(--text-tertiary);margin-left:8px">${a.date}</span>` : ""}
        </div>`).join("")}` : "")}

    <!-- Related News -->
    ${related_news && related_news.length ? `
      <div class="detail-section-title">📰 RELATED NEWS</div>
      ${related_news.map(n=>`
        <div class="detail-news-item" onclick="window.open('${n.link}','_blank')">
          <span class="news-badge ${n.sentiment}" style="margin-right:6px">${(n.sentiment||"neutral").toUpperCase()}</span>
          ${n.title}
        </div>`).join("")}` : ""}
  `;

  // Draw chart — prefer Sarmaaya 30-day history, fallback to tech chart
  if (priceHistory.length > 3) {
    setTimeout(() => drawSarmaayaChart(priceHistory), 100);
  } else if (tech && tech.chart_data && tech.chart_data.length > 5) {
    setTimeout(() => drawPriceChart(tech), 100);
  }
}

// ── Technical Panel ──────────────────────────────────────────
function renderTechPanel(tech) {
  if (!tech) return "";
  const rsiColor = tech.rsi < 30 ? "var(--green)" : tech.rsi > 70 ? "var(--red)" : "var(--amber)";
  const macdColor = (tech.macd_cross || "").includes("bullish") ? "var(--green)" : "var(--red)";
  const trendColor = tech.trend === "uptrend" ? "var(--green)" : tech.trend === "downtrend" ? "var(--red)" : "var(--amber)";
  const rsiPct = Math.min(100, Math.max(0, tech.rsi || 50));

  return `
    <div class="tech-panel-card">
      <div class="tech-card-header">
        <span class="tech-card-title">TECHNICAL INDICATORS</span>
        <span class="signal-badge ${signalClass(tech.tech_signal)}" style="font-size:12px;padding:5px 14px">${tech.tech_signal}</span>
      </div>
      <div class="tech-indicator-grid">
        <!-- RSI -->
        <div class="tech-indicator">
          <div class="tech-ind-label">RSI (14)</div>
          <div class="tech-ind-value" style="color:${rsiColor}">${tech.rsi}</div>
          <div class="tech-ind-sub">${(tech.rsi_signal || "").toUpperCase().replace(/_/g, " ")}</div>
          <div class="rsi-gauge"><div class="rsi-marker" style="left:${rsiPct}%"></div></div>
          <div class="rsi-labels"><span>Oversold 30</span><span>70 Overbought</span></div>
        </div>
        <!-- MACD -->
        <div class="tech-indicator">
          <div class="tech-ind-label">MACD</div>
          <div class="tech-ind-value" style="color:${macdColor}">${tech.macd}</div>
          <div class="tech-ind-sub">${(tech.macd_cross || "").toUpperCase().replace(/_/g, " ")}</div>
          <div class="tech-ind-sub">Signal: ${tech.macd_signal} | Hist: ${tech.macd_hist}</div>
        </div>
        <!-- MAs -->
        <div class="tech-indicator">
          <div class="tech-ind-label">MOVING AVERAGES</div>
          <div class="tech-ind-value" style="color:${trendColor}">${(tech.trend || "").toUpperCase()}</div>
          <div class="tech-ind-sub">MA20: ₨${tech.ma20}</div>
          ${tech.ma50 ? `<div class="tech-ind-sub">MA50: ₨${tech.ma50}</div>` : ""}
        </div>
        <!-- Bollinger -->
        <div class="tech-indicator">
          <div class="tech-ind-label">BOLLINGER BANDS</div>
          <div class="tech-ind-value" style="color:${tech.bb_pct < 20 ? "var(--green)" : tech.bb_pct > 80 ? "var(--red)" : "var(--blue)"}">${(tech.bb_signal || "").toUpperCase().replace(/_/g, " ")}</div>
          <div class="tech-ind-sub">Position: ${tech.bb_pct}%</div>
          <div class="bb-gauge"><div class="bb-marker" style="left:${Math.min(100, Math.max(0, tech.bb_pct))}%"></div></div>
          <div class="tech-ind-sub">₨${tech.bb_lower} – ₨${tech.bb_upper}</div>
        </div>
        <!-- Volume -->
        <div class="tech-indicator">
          <div class="tech-ind-label">VOLUME</div>
          <div class="tech-ind-value" style="color:${tech.volume_surge ? "var(--green)" : "var(--text-primary)"}">${tech.volume_surge ? "🔥 SURGE" : "Normal"}</div>
          <div class="tech-ind-sub">${tech.volume_ratio}× avg volume</div>
        </div>
        <!-- Score -->
        <div class="tech-indicator">
          <div class="tech-ind-label">COMPOSITE SCORE</div>
          <div class="tech-ind-value" style="color:${tech.tech_score > 0 ? "var(--green)" : tech.tech_score < 0 ? "var(--red)" : "var(--amber)"}">${tech.tech_score > 0 ? "+" : ""}${tech.tech_score} / 8</div>
          <div class="tech-ind-sub">Confidence: ${tech.tech_confidence}%</div>
        </div>
      </div>
      ${tech.cross_signal ? `<div class="cross-alert-box ${tech.cross_signal === 'golden_cross' ? 'golden' : 'death'}">${tech.cross_signal === 'golden_cross' ? "⚡ GOLDEN CROSS — MA20 above MA50 (Strong Bullish)" : "💀 DEATH CROSS — MA20 below MA50 (Strong Bearish)"}</div>` : ""}
      ${(tech.supports && tech.supports.length) || (tech.resistances && tech.resistances.length) ? `
        <div class="sr-grid">
          <div><div class="sr-title">SUPPORT LEVELS</div>${(tech.supports || []).map(s => `<span class="sr-level sr-support">₨${s}</span>`).join("") || "—"}</div>
          <div><div class="sr-title">RESISTANCE LEVELS</div>${(tech.resistances || []).map(r => `<span class="sr-level sr-resistance">₨${r}</span>`).join("") || "—"}</div>
        </div>` : ""}
    </div>`;
}

// ── Chart.js ─────────────────────────────────────────────────
function drawPriceChart(tech) {
  const canvas = document.getElementById("price-chart");
  if (!canvas || !tech.chart_data) return;
  if (priceChart) { priceChart.destroy(); priceChart = null; }

  const isDark = document.documentElement.getAttribute("data-theme") === "dark";
  const gridColor = isDark ? "#2D3748" : "#E2E8F0";
  const textColor = isDark ? "#64748B" : "#94A3B8";

  const labels = tech.chart_data.map(d => d.date.slice(5));
  const closes = tech.chart_data.map(d => d.close);
  const ma20 = tech.ma20_chart || [];
  const ma50 = tech.ma50_chart || [];

  priceChart = new Chart(canvas.getContext("2d"), {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Price", data: closes, borderColor: "#2563EB", backgroundColor: "rgba(37,99,235,0.06)", borderWidth: 2, pointRadius: 0, tension: 0.2, fill: true, order: 1 },
        { label: "MA20", data: ma20, borderColor: "#F59E0B", borderWidth: 1.5, pointRadius: 0, tension: 0.3, fill: false, order: 2 },
        ...(ma50.length ? [{ label: "MA50", data: ma50, borderColor: "#7C3AED", borderWidth: 1.5, pointRadius: 0, tension: 0.3, fill: false, order: 3 }] : []),
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 400 },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: textColor, font: { family: "JetBrains Mono", size: 10 }, boxWidth: 20, padding: 10 } },
        tooltip: {
          backgroundColor: isDark ? "#1A2332" : "#FFFFFF",
          borderColor: gridColor, borderWidth: 1,
          titleColor: isDark ? "#F1F5F9" : "#0F172A",
          bodyColor: textColor,
          titleFont: { family: "JetBrains Mono", size: 11 },
          bodyFont: { family: "JetBrains Mono", size: 11 },
          callbacks: { label: ctx => ` ${ctx.dataset.label}: ₨${ctx.parsed.y?.toFixed(2) ?? "—"}` },
        },
      },
      scales: {
        x: { ticks: { color: textColor, font: { family: "JetBrains Mono", size: 9 }, maxTicksLimit: 8 }, grid: { color: gridColor } },
        y: { ticks: { color: textColor, font: { family: "JetBrains Mono", size: 9 }, callback: v => `₨${Number(v).toLocaleString()}` }, grid: { color: gridColor } },
      },
    },
  });
}

// ── Sarmaaya 30-Day Price+Volume Chart ───────────────────────
function drawSarmaayaChart(history) {
  const canvas = document.getElementById("price-chart");
  if (!canvas || !history || !history.length) return;
  if (priceChart) { priceChart.destroy(); priceChart = null; }

  const isDark = document.documentElement.getAttribute("data-theme") === "dark";
  const gridColor = isDark ? "#2D3748" : "#E2E8F0";
  const textColor = isDark ? "#64748B" : "#94A3B8";

  // History comes newest-first from API — reverse for chart
  const sorted = [...history].reverse();
  const labels  = sorted.map(d => new Date(d.date).toLocaleDateString("en-PK", { day:"numeric", month:"short" }));
  const prices  = sorted.map(d => d.price);
  const volumes = sorted.map(d => d.volume);

  priceChart = new Chart(canvas.getContext("2d"), {
    data: {
      labels,
      datasets: [
        {
          type: "line",
          label: "Price",
          data: prices,
          borderColor: "#2563EB",
          backgroundColor: "rgba(37,99,235,0.06)",
          borderWidth: 2,
          pointRadius: 2,
          tension: 0.25,
          fill: true,
          yAxisID: "yPrice",
          order: 1,
        },
        {
          type: "bar",
          label: "Volume",
          data: volumes,
          backgroundColor: "rgba(99,102,241,0.25)",
          borderRadius: 2,
          yAxisID: "yVol",
          order: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 400 },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: textColor, font: { family: "JetBrains Mono", size: 10 }, boxWidth: 14, padding: 10 } },
        tooltip: {
          backgroundColor: isDark ? "#1A2332" : "#FFFFFF",
          borderColor: gridColor, borderWidth: 1,
          titleColor: isDark ? "#F1F5F9" : "#0F172A",
          bodyColor: textColor,
          titleFont: { family: "JetBrains Mono", size: 11 },
          bodyFont: { family: "JetBrains Mono", size: 10 },
          callbacks: {
            label: ctx => ctx.dataset.label === "Price"
              ? ` Price: ₨${ctx.parsed.y?.toFixed(2) ?? "—"}`
              : ` Volume: ${Number(ctx.parsed.y).toLocaleString()}`,
          },
        },
      },
      scales: {
        x: { ticks: { color: textColor, font: { family: "JetBrains Mono", size: 9 }, maxTicksLimit: 10 }, grid: { color: gridColor } },
        yPrice: { position: "left", ticks: { color: textColor, font: { family: "JetBrains Mono", size: 9 }, callback: v => `₨${Number(v).toLocaleString()}` }, grid: { color: gridColor } },
        yVol: { position: "right", ticks: { color: textColor, font: { family: "JetBrains Mono", size: 9 }, callback: v => volFmt(v) }, grid: { display: false } },
      },
    },
  });
}


//  SEARCH
// ══════════════════════════════════════════════════════════════
document.getElementById("search-input").addEventListener("input", (e) => {
  clearTimeout(searchTimeout);
  const q = e.target.value.trim();
  if (!q) { document.getElementById("search-results").classList.remove("open"); return; }
  searchTimeout = setTimeout(() => searchStocks(q), 250);
});

document.getElementById("search-input").addEventListener("focus", () => {
  const q = document.getElementById("search-input").value.trim();
  if (q) searchStocks(q);
});

document.addEventListener("click", (e) => {
  if (!e.target.closest(".search-wrap")) {
    document.getElementById("search-results").classList.remove("open");
  }
});

async function searchStocks(q) {
  // First try local filter
  const local = allStocks.filter(s =>
    s.symbol.includes(q.toUpperCase()) || (s.name || "").toUpperCase().includes(q.toUpperCase())
  ).slice(0, 12);

  const results = document.getElementById("search-results");
  if (!local.length) {
    results.innerHTML = `<div class="empty-state" style="padding:16px">No results for "${q}"</div>`;
    results.classList.add("open");
    return;
  }

  results.innerHTML = local.map(s => `
    <div class="search-result-item" onclick="navigateTo('stock-detail','${s.symbol}');document.getElementById('search-results').classList.remove('open');document.getElementById('search-input').value='';">
      <div><span class="sr-sym">${s.symbol}</span><span class="sr-name">${s.name}</span></div>
      <div><span class="sr-price stock-chg ${chgClass(s.change_pct)}">₨${fmt(s.price)} ${chgArrow(s.change_pct)}${Math.abs(s.change_pct).toFixed(2)}%</span></div>
    </div>`).join("");
  results.classList.add("open");
}

// ══════════════════════════════════════════════════════════════
//  WATCHLIST
// ══════════════════════════════════════════════════════════════
async function fetchWatchlist() {
  try {
    const res = await fetch(`${API}/api/watchlist`);
    const data = await res.json();
    renderWatchlist(data.stocks || []);
  } catch (e) {
    document.getElementById("watchlist-grid").innerHTML = `<div class="empty-state" style="color:var(--red)">Error loading watchlist</div>`;
  }
}

function renderWatchlist(stocks) {
  const grid = document.getElementById("watchlist-grid");
  if (!stocks.length) {
    grid.innerHTML = `<div class="empty-state">No stocks in your watchlist yet.<br>Click ☆ on any stock to add it.</div>`;
    return;
  }
  grid.innerHTML = stocks.map(s => `
    <div class="wl-card" onclick="navigateTo('stock-detail','${s.symbol}')">
      <button class="wl-remove" onclick="event.stopPropagation();removeFromWatchlist('${s.symbol}')">✕</button>
      <div class="wl-card-top">
        <div>
          <div class="wl-sym">${s.symbol}</div>
          <div class="wl-name">${s.name} · ${s.sector}</div>
        </div>
        <div>
          <div class="wl-price" style="color:var(--text-primary)">₨${fmt(s.price)}</div>
          <div class="wl-change stock-chg ${chgClass(s.change_pct)}">${chgArrow(s.change_pct)} ${Math.abs(s.change_pct).toFixed(2)}%</div>
        </div>
      </div>
      ${s.shariah ? '<span class="halal-badge">Halal</span>' : ""}
    </div>`).join("");
}

async function toggleWatchlistStock() {
  if (!currentDetailSymbol) return;
  const btn = document.getElementById("watchlist-toggle");
  const isActive = btn.classList.contains("active");

  try {
    if (isActive) {
      await fetch(`${API}/api/watchlist/${currentDetailSymbol}`, { method: "DELETE" });
      btn.textContent = "☆ Add to Watchlist";
      btn.classList.remove("active");
    } else {
      await fetch(`${API}/api/watchlist/${currentDetailSymbol}`, { method: "POST" });
      btn.textContent = "★ In Watchlist";
      btn.classList.add("active");
    }
  } catch (e) { console.error("Watchlist toggle error:", e); }
}

async function removeFromWatchlist(symbol) {
  await fetch(`${API}/api/watchlist/${symbol}`, { method: "DELETE" });
  fetchWatchlist();
}

// ══════════════════════════════════════════════════════════════
//  PORTFOLIO
// ══════════════════════════════════════════════════════════════
async function fetchPortfolio() {
  try {
    const res = await fetch(`${API}/api/portfolio`);
    const data = await res.json();
    renderPortfolioSummary(data.summary);
    renderHoldings(data.holdings);
  } catch (e) {
    document.getElementById("port-holdings").innerHTML = `<div class="empty-state" style="color:var(--red)">Error loading portfolio</div>`;
  }
}

function renderPortfolioSummary(s) {
  if (!s) return;
  document.getElementById("port-invested").textContent = `₨${fmt(s.total_invested, 0)}`;
  document.getElementById("port-current").textContent = `₨${fmt(s.total_current, 0)}`;
  document.getElementById("port-count").textContent = s.num_holdings;

  const pnlEl = document.getElementById("port-pnl");
  const retEl = document.getElementById("port-return");
  pnlEl.textContent = `${s.total_pnl >= 0 ? "+" : ""}₨${fmt(Math.abs(s.total_pnl), 0)}`;
  pnlEl.style.color = s.total_pnl >= 0 ? "var(--green)" : "var(--red)";
  retEl.textContent = `${s.total_pnl_pct >= 0 ? "+" : ""}${s.total_pnl_pct.toFixed(2)}%`;
  retEl.style.color = s.total_pnl_pct >= 0 ? "var(--green)" : "var(--red)";
}

function renderHoldings(holdings) {
  const el = document.getElementById("port-holdings");
  if (!holdings || !holdings.length) {
    el.innerHTML = `<div class="empty-state">No holdings yet. Add your first stock below.</div>`;
    return;
  }
  el.innerHTML = holdings.map(h => `
    <div class="holding-card ${h.pnl > 0 ? "profit" : h.pnl < 0 ? "loss" : ""}">
      <div>
        <div class="hc-sym">${h.symbol}</div>
        <div class="hc-name">${h.name || ""} ${h.shariah ? "✓" : ""}</div>
      </div>
      <div><span class="hc-label">SHARES × BUY</span><span class="hc-val">${h.shares} × ₨${fmt(h.buy_price)}</span></div>
      <div><span class="hc-label">CURRENT</span><span class="hc-val ${h.has_live_data ? "stock-chg " + chgClass(h.today_change) : ""}">${h.has_live_data ? `₨${fmt(h.current_price)}` : "—"}</span></div>
      <div><span class="hc-label">P&L</span><span class="hc-val" style="color:${h.pnl >= 0 ? "var(--green)" : "var(--red)"}">${h.pnl != null ? `${h.pnl >= 0 ? "+" : ""}₨${fmt(Math.abs(h.pnl), 0)} (${h.pnl_pct >= 0 ? "+" : ""}${h.pnl_pct?.toFixed(1)}%)` : "—"}</span></div>
      <button class="remove-btn" onclick="removeHolding('${h.symbol}')">✕</button>
    </div>`).join("");
}

async function submitHolding() {
  const symbol = document.getElementById("f-symbol").value.trim().toUpperCase();
  const shares = parseFloat(document.getElementById("f-shares").value);
  const buyPrice = parseFloat(document.getElementById("f-buyprice").value);
  const buyDate = document.getElementById("f-buydate").value;
  const errEl = document.getElementById("form-error");

  if (!symbol) { errEl.textContent = "Enter a stock symbol."; return; }
  if (!shares || shares <= 0) { errEl.textContent = "Enter valid share count."; return; }
  if (!buyPrice || buyPrice <= 0) { errEl.textContent = "Enter valid buy price."; return; }
  errEl.textContent = "";

  try {
    const res = await fetch(`${API}/api/portfolio/add`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, shares, buy_price: buyPrice, buy_date: buyDate || null })
    });
    if ((await res.json()).success) {
      ["f-symbol", "f-shares", "f-buyprice", "f-buydate"].forEach(id => document.getElementById(id).value = "");
      fetchPortfolio();
    }
  } catch (e) { errEl.textContent = "Server error."; }
}

async function removeHolding(symbol) {
  if (!confirm(`Remove ${symbol} from portfolio?`)) return;
  await fetch(`${API}/api/portfolio/${symbol}`, { method: "DELETE" });
  fetchPortfolio();
}

async function fetchPortfolioAdvice() {
  const panel = document.getElementById("port-advice-panel");
  panel.innerHTML = `<div class="empty-state">🤖 Analyzing your portfolio...</div>`;
  try {
    const res = await fetch(`${API}/api/portfolio/advice`);
    const data = await res.json();
    renderPortfolioAdvice(data.advice);
    if (data.portfolio) {
      renderPortfolioSummary(data.portfolio.summary);
      renderHoldings(data.portfolio.holdings);
    }
  } catch (e) { panel.innerHTML = `<div class="empty-state" style="color:var(--red)">Error loading advice</div>`; }
}

function renderPortfolioAdvice(a) {
  const panel = document.getElementById("port-advice-panel");
  if (!a) { panel.innerHTML = `<div class="empty-state">No advice available.</div>`; return; }
  const scoreColor = a.health_score >= 70 ? "var(--green)" : a.health_score >= 40 ? "var(--amber)" : "var(--red)";
  panel.innerHTML = `
    <div class="advice-health-row">
      <div>
        <div class="advice-label">PORTFOLIO HEALTH</div>
        <div class="advice-health-text" style="color:${scoreColor}">${a.overall_health}</div>
      </div>
      <div class="advice-score" style="color:${scoreColor}">${a.health_score}</div>
    </div>
    <div class="advice-summary-box">${a.summary}</div>
    ${a.actions?.length ? `<div style="font-size:12px;font-weight:700;letter-spacing:2px;color:var(--text-tertiary);margin-bottom:8px">STOCK ACTIONS</div>
      ${a.actions.map(act => `
        <div class="advice-action-row">
          <span class="aa-sym">${act.symbol}</span>
          <span class="aa-badge aa-${(act.action || "").replace(/ /g, "-")}">${act.action}</span>
          <span class="aa-reason">${act.reason}</span>
        </div>`).join("")}` : ""}
    ${a.diversification_tip ? `<div class="advice-tip-box">💡 ${a.diversification_tip}</div>` : ""}
    ${a.risk_warning ? `<div class="advice-warning-box">⚠️ ${a.risk_warning}</div>` : ""}`;
}

// ── PDF Export ───────────────────────────────────────────────
async function exportPortfolioPDF() {
  try {
    const res = await fetch(`${API}/api/portfolio/export`);
    const data = await res.json();
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();

    doc.setFontSize(20);
    doc.setTextColor(37, 99, 235);
    doc.text("PSX AI Analyst — Portfolio Report", 14, 22);

    doc.setFontSize(10);
    doc.setTextColor(100);
    doc.text(`Generated: ${new Date().toLocaleString("en-PK")}`, 14, 30);

    const summary = data.portfolio?.summary || {};
    doc.setFontSize(12);
    doc.setTextColor(0);
    doc.text(`Total Invested: PKR ${fmt(summary.total_invested, 0)}`, 14, 42);
    doc.text(`Current Value: PKR ${fmt(summary.total_current, 0)}`, 14, 50);
    doc.text(`Total P&L: PKR ${fmt(summary.total_pnl, 0)} (${summary.total_pnl_pct?.toFixed(2)}%)`, 14, 58);

    const holdings = data.portfolio?.holdings || [];
    if (holdings.length) {
      doc.autoTable({
        startY: 68,
        head: [["Symbol", "Shares", "Buy Price", "Current", "P&L", "P&L %"]],
        body: holdings.map(h => [
          h.symbol, h.shares, `PKR ${fmt(h.buy_price)}`,
          h.current_price ? `PKR ${fmt(h.current_price)}` : "—",
          h.pnl != null ? `PKR ${fmt(h.pnl, 0)}` : "—",
          h.pnl_pct != null ? `${h.pnl_pct.toFixed(2)}%` : "—"
        ]),
        theme: "grid",
        headStyles: { fillColor: [37, 99, 235] },
      });
    }

    doc.save("PSX_Portfolio_Report.pdf");
  } catch (e) {
    alert("Error generating PDF. Make sure you have holdings in your portfolio.");
  }
}

// ══════════════════════════════════════════════════════════════
//  DIVIDENDS
// ══════════════════════════════════════════════════════════════
async function fetchDividends() {
  try {
    const res = await fetch(`${API}/api/dividends`);
    const data = await res.json();
    renderDividendCards(data.data || []);
  } catch (e) {
    document.getElementById("div-grid").innerHTML = `<div class="empty-state" style="color:var(--red)">Error loading dividends</div>`;
  }
}

function renderDividendCards(divs) {
  const grid = document.getElementById("div-grid");
  let filtered = divs;
  if (currentDivFilter !== "all") {
    filtered = divs.filter(d => (d.type || "general") === currentDivFilter);
  }
  if (!filtered.length) {
    grid.innerHTML = `<div class="empty-state">No dividend announcements found.</div>`;
    return;
  }
  grid.innerHTML = filtered.map(d => {
    const type = d.type || "general";
    return `
    <div class="div-card ${type}">
      <div class="dc-top">
        <span class="dc-sym" onclick="navigateTo('stock-detail','${d.symbol}')">${d.symbol}</span>
        <span class="dc-type-badge ann-card-type ann-type-${type}">${d.type_label || type.toUpperCase()}</span>
      </div>
      <div class="dc-title">${d.title || d.subject || "—"}</div>
      ${d.amount ? `<div class="dc-amount">PKR ${d.amount}</div><div class="dc-amount-label">PER SHARE</div>` : ""}
      ${d.advice ? `<div class="dc-advice">${d.advice}</div>` : ""}
      <div class="dc-meta">
        <span>${d.date || "—"}</span>
        ${d.closure_date ? `<span>Closure: ${d.closure_date}</span>` : ""}
        ${d.link ? `<a class="dc-link" href="${d.link}" target="_blank" onclick="event.stopPropagation()">View →</a>` : `<span>${d.source || ""}</span>`}
      </div>
    </div>`;
  }).join("");
}

// ══════════════════════════════════════════════════════════════
//  ANNOUNCEMENTS (no dividends — board meetings, results, bonus only)
// ══════════════════════════════════════════════════════════════
async function fetchAnnouncements() {
  try {
    const res = await fetch(`${API}/api/announcements`);
    const data = await res.json();
    renderAnnouncementCards(data.data || []);
  } catch (e) {
    document.getElementById("ann-grid").innerHTML = `<div class="empty-state" style="color:var(--red)">Error loading announcements</div>`;
  }
}

function renderAnnouncementCards(anns) {
  const grid = document.getElementById("ann-grid");
  let filtered = anns;
  if (currentAnnFilter !== "all") {
    filtered = anns.filter(a => (a.type || "general") === currentAnnFilter);
  }
  if (!filtered.length) {
    grid.innerHTML = `<div class="empty-state">No announcements found for this filter.</div>`;
    return;
  }
  grid.innerHTML = filtered.map(a => {
    const type = a.type || "general";
    return `
    <div class="ann-card ${type}">
      <div class="dc-top">
        <span class="dc-sym" onclick="navigateTo('stock-detail','${a.symbol}')">${a.symbol}</span>
        <span class="dc-type-badge ann-card-type ann-type-${type}">${a.type_label || type.toUpperCase()}</span>
      </div>
      <div class="dc-title">${a.title || "—"}</div>
      ${a.amount ? `<div style="font-family:var(--font-mono);font-size:16px;font-weight:700;color:var(--green);margin-bottom:4px">PKR ${a.amount}</div>` : ""}
      ${a.advice ? `<div class="dc-advice">${a.advice}</div>` : ""}
      <div class="dc-meta">
        <span>${a.date || "—"}</span>
        <span>${a.source || ""}</span>
        ${a.link ? `<a class="dc-link" href="${a.link}" target="_blank" onclick="event.stopPropagation()">View →</a>` : ""}
      </div>
    </div>`;
  }).join("");
}

// ══════════════════════════════════════════════════════════════
//  ALERTS
// ══════════════════════════════════════════════════════════════
function updateAlertConditions() {
  const type = document.getElementById("a-type").value;
  const condSel = document.getElementById("a-condition");
  const targetInp = document.getElementById("a-target");

  switch (type) {
    case "price_above":
      condSel.innerHTML = `<option value="above">Above</option>`;
      targetInp.placeholder = "Target Price (PKR)";
      break;
    case "price_below":
      condSel.innerHTML = `<option value="below">Below</option>`;
      targetInp.placeholder = "Target Price (PKR)";
      break;
    case "signal_change":
      condSel.innerHTML = `<option value="bullish">Bullish Signal</option><option value="bearish">Bearish Signal</option><option value="any">Any Change</option>`;
      targetInp.placeholder = "0 (not used)";
      targetInp.value = "0";
      break;
    case "volume_surge":
      condSel.innerHTML = `<option value="any">Any Surge</option>`;
      targetInp.placeholder = "0 (not used)";
      targetInp.value = "0";
      break;
    case "percent_move":
      condSel.innerHTML = `<option value="any">Any Direction</option>`;
      targetInp.placeholder = "% threshold (e.g. 3)";
      break;
    case "news_alert":
      condSel.innerHTML = `<option value="any">Any Major News</option><option value="positive">Positive Only</option><option value="negative">Negative Only</option>`;
      targetInp.placeholder = "0 (not used)";
      targetInp.value = "0";
      break;
  }
}

async function createAlert() {
  const symbol = document.getElementById("a-symbol").value.trim().toUpperCase();
  const type = document.getElementById("a-type").value;
  const condition = document.getElementById("a-condition").value;
  const target = parseFloat(document.getElementById("a-target").value) || 0;
  const note = document.getElementById("a-note").value.trim();

  if (!symbol) { alert("Enter a stock symbol"); return; }

  try {
    await fetch(`${API}/api/alerts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, type, condition, target_value: target, note })
    });
    ["a-symbol", "a-note"].forEach(id => document.getElementById(id).value = "");
    document.getElementById("a-target").value = "";
    fetchAlerts();
  } catch (e) { alert("Error creating alert"); }
}

async function fetchAlerts() {
  try {
    const [activeRes, triggeredRes] = await Promise.all([
      fetch(`${API}/api/alerts`),
      fetch(`${API}/api/alerts/triggered`),
    ]);
    const activeData = await activeRes.json();
    const triggeredData = await triggeredRes.json();
    renderActiveAlerts(activeData.data || []);
    renderTriggeredAlerts(triggeredData.data || []);
    // Clear badge when user opens alerts panel
    document.getElementById("alert-badge").style.display = "none";
    const ids = (triggeredData.data || []).map(a => String(a.id));
    ids.forEach(id => shownAlertIds.add(id));
    localStorage.setItem("psx_shown_alerts", JSON.stringify([...shownAlertIds].slice(-100)));
  } catch (e) { console.error("Alerts error:", e); }
}

function renderActiveAlerts(alerts) {
  const el = document.getElementById("active-alerts");
  const active = alerts.filter(a => a.active && !a.triggered);
  if (!active.length) {
    el.innerHTML = `<div class="empty-state">No active alerts. Create one above!</div>`;
    return;
  }
  el.innerHTML = active.map(a => `
    <div class="alert-item">
      <span class="ai-sym">${a.symbol}</span>
      <span class="ai-type">${a.type.replace(/_/g, " ").toUpperCase()}</span>
      <span class="ai-detail">${a.condition} ${a.target_value ? `₨${a.target_value}` : ""} ${a.note ? `— ${a.note}` : ""}</span>
      <span class="ai-time">${timeSince(a.created_at)}</span>
      <button class="ai-delete" onclick="deleteAlert('${a.id}')">✕</button>
    </div>`).join("");
}

function renderTriggeredAlerts(triggered) {
  const el = document.getElementById("triggered-alerts");
  if (!triggered.length) {
    el.innerHTML = `<div class="empty-state">No triggered alerts yet</div>`;
    return;
  }
  el.innerHTML = triggered.reverse().map(t => `
    <div class="alert-item triggered">
      <span class="ai-sym">${t.symbol}</span>
      <span class="ai-type">${t.type.replace(/_/g, " ").toUpperCase()}</span>
      <span class="ai-detail">${t.message}</span>
      <span class="ai-time">${timeSince(t.triggered_at)}</span>
    </div>`).join("");
}

async function deleteAlert(id) {
  await fetch(`${API}/api/alerts/${id}`, { method: "DELETE" });
  fetchAlerts();
}

async function clearTriggered() {
  await fetch(`${API}/api/alerts/triggered/clear`, { method: "DELETE" });
  fetchAlerts();
}

// ── Browser Notifications ────────────────────────────────────
function enableNotifications() {
  if (!("Notification" in window)) {
    alert("Your browser doesn't support notifications");
    return;
  }
  if (Notification.permission === "granted") {
    notificationsEnabled = true;
    document.getElementById("enable-notif-btn").textContent = "✅ Notifications Enabled";
    return;
  }
  Notification.requestPermission().then(perm => {
    if (perm === "granted") {
      notificationsEnabled = true;
      document.getElementById("enable-notif-btn").textContent = "✅ Notifications Enabled";
      document.getElementById("enable-notif-btn").style.background = "var(--green)";
    }
  });
}

async function checkTriggeredAlerts() {
  try {
    const res = await fetch(`${API}/api/alerts/triggered`);
    const data = await res.json();
    const all = data.data || [];
    const newOnes = all.filter(a => !shownAlertIds.has(String(a.id)));

    const badge = document.getElementById("alert-badge");
    if (newOnes.length > 0) {
      badge.textContent = newOnes.length;
      badge.style.display = "flex";
      if (Notification.permission === "granted") {
        newOnes.forEach(a => {
          new Notification(`PSX Alert: ${a.symbol}`, {
            body: a.message,
            tag: `alert-${a.id}`,
            requireInteraction: false,
          });
          shownAlertIds.add(String(a.id));
        });
        localStorage.setItem("psx_shown_alerts",
          JSON.stringify([...shownAlertIds].slice(-100)));
      }
    } else {
      badge.style.display = "none";
    }
  } catch (e) { /* silent */ }
}

// ══════════════════════════════════════════════════════════════
//  SIGNAL HISTORY
// ══════════════════════════════════════════════════════════════
async function fetchSignalHistory() {
  try {
    const [histRes, accRes] = await Promise.all([
      fetch(`${API}/api/signals/history`),
      fetch(`${API}/api/signals/accuracy`)
    ]);
    const hist = await histRes.json();
    const acc = await accRes.json();
    renderAccuracyCards(acc);
    renderSignalList(hist.signals || []);
  } catch (e) {
    document.getElementById("accuracy-cards").innerHTML = `<div class="empty-state" style="color:var(--red)">Error loading signal history</div>`;
  }
}

function renderAccuracyCards(stats) {
  const el = document.getElementById("accuracy-cards");
  if (!stats || !stats.total_signals) {
    el.innerHTML = `<div class="empty-state" style="grid-column:1/-1">No signal data yet. Signals are recorded when you view stock details.</div>`;
    return;
  }
  const winColor = stats.win_rate >= 60 ? "var(--green)" : stats.win_rate >= 40 ? "var(--amber)" : "var(--red)";
  const retColor = stats.avg_return >= 0 ? "var(--green)" : "var(--red)";

  el.innerHTML = `
    <div class="acc-card"><div class="acc-card-label">TOTAL SIGNALS</div><div class="acc-card-value" style="color:var(--blue)">${stats.total_signals}</div></div>
    <div class="acc-card"><div class="acc-card-label">WIN RATE</div><div class="acc-card-value" style="color:${winColor}">${stats.win_rate}%</div></div>
    <div class="acc-card"><div class="acc-card-label">AVG RETURN</div><div class="acc-card-value" style="color:${retColor}">${stats.avg_return > 0 ? "+" : ""}${stats.avg_return}%</div></div>
    <div class="acc-card"><div class="acc-card-label">WINS / LOSSES</div><div class="acc-card-value"><span style="color:var(--green)">${stats.wins || 0}</span> / <span style="color:var(--red)">${stats.losses || 0}</span></div></div>
    <div class="acc-card"><div class="acc-card-label">OPEN POSITIONS</div><div class="acc-card-value" style="color:var(--blue)">${stats.open_signals || 0}</div></div>
  `;
}

function renderSignalList(signals) {
  const el = document.getElementById("signal-history-list");
  if (!signals.length) {
    el.innerHTML = `<div class="empty-state">No signals recorded yet. View stock details to generate signals.</div>`;
    return;
  }
  el.innerHTML = signals.map(s => {
    const retColor = (s.return_pct || 0) >= 0 ? "text-green" : "text-red";
    const outcomeClass = s.hit_target ? "outcome-win" : s.hit_stop ? "outcome-loss" : "outcome-open";
    const outcomeText = s.hit_target ? "WIN ✓" : s.hit_stop ? "LOSS ✕" : "OPEN";
    return `
    <div class="sh-item">
      <span class="sh-sym">${s.symbol}</span>
      <span class="signal-badge ${signalClass(s.signal)}">${s.signal}</span>
      <span class="sh-reasoning" title="${s.reasoning || ''}">${s.reasoning || "—"}</span>
      <span class="sh-price">₨${fmt(s.price_at_signal)}</span>
      <span class="sh-return ${retColor}">${s.return_pct != null ? `${s.return_pct > 0 ? "+" : ""}${s.return_pct}%` : "—"}</span>
      <span class="sh-outcome ${outcomeClass}">${outcomeText}</span>
    </div>`;
  }).join("");
}

// ══════════════════════════════════════════════════════════════
//  DARK / LIGHT MODE
// ══════════════════════════════════════════════════════════════
function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute("data-theme") || "light";
  const next = current === "light" ? "dark" : "light";
  html.setAttribute("data-theme", next);
  localStorage.setItem("psx-theme", next);
  document.getElementById("theme-toggle").textContent = next === "dark" ? "☀️" : "🌙";

  // Redraw chart if visible
  if (priceChart && currentPanel === "stock-detail") {
    setTimeout(() => {
      if (currentDetailSymbol) loadStockDetail(currentDetailSymbol);
    }, 100);
  }
}

// Load saved theme
(function initTheme() {
  const saved = localStorage.getItem("psx-theme") || "light";
  document.documentElement.setAttribute("data-theme", saved);
  document.getElementById("theme-toggle").textContent = saved === "dark" ? "☀️" : "🌙";
})();

// ══════════════════════════════════════════════════════════════
//  FILTER EVENT LISTENERS
// ══════════════════════════════════════════════════════════════

// Stock filters (All, KSE100, KMI30, Halal, Gainers, Losers)
document.querySelectorAll(".filter-chips:not(.news-chips) .chip").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".filter-chips:not(.news-chips) .chip").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentFilter = btn.dataset.filter;
    renderStocks(allStocks);
  });
});

// News filters
document.querySelectorAll(".news-chips .chip").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".news-chips .chip").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentNewsFilter = btn.dataset.news;
    renderNews(allNews);
  });
});

// Dividend filters
document.querySelectorAll(".div-filter-row .chip").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".div-filter-row .chip").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentDivFilter = btn.dataset.divfilter;
    fetchDividends();
  });
});

// Announcement filters
document.querySelectorAll(".ann-filter-row .chip").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".ann-filter-row .chip").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentAnnFilter = btn.dataset.annfilter;
    fetchAnnouncements();
  });
});

// ══════════════════════════════════════════════════════════════
//  CHAT ASSISTANT
// ══════════════════════════════════════════════════════════════
let chatHistoryLoaded = false;

async function fetchChatHistory() {
  if (chatHistoryLoaded) return;
  try {
    const res = await fetch(`${API}/api/chat/history`);
    const data = await res.json();
    if (data.history && data.history.length > 0) {
      const container = document.getElementById("chat-messages");
      container.innerHTML = `<div class="chat-msg system-msg"><div class="msg-bubble">👋 Hello! I'm PSX Pro. I have full access to live market data, news, announcements, your portfolio, and latest stock signals. Ask me anything about the PSX!</div></div>`;
      data.history.forEach(msg => appendChatMessage(msg.role, msg.text));
      scrollToChatBottom();
    }
    chatHistoryLoaded = true;
  } catch (e) { console.error("Chat history load error", e); }
}

function appendChatMessage(role, text) {
  const container = document.getElementById("chat-messages");
  const msgDiv = document.createElement("div");
  msgDiv.className = `chat-msg ${role === 'user' ? 'user-msg' : role === 'model' ? 'ai-msg' : 'system-msg'}`;

  // Format basic markdown (bold)
  let formattedText = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Format basic markdown (italics)
  formattedText = formattedText.replace(/\*(.*?)\*/g, '<em>$1</em>');
  // Format newlines
  formattedText = formattedText.replace(/\n/g, '<br>');

  msgDiv.innerHTML = `<div class="msg-bubble">${formattedText}</div>`;
  container.appendChild(msgDiv);
  scrollToChatBottom();
}

function scrollToChatBottom() {
  const container = document.getElementById("chat-messages");
  container.scrollTop = container.scrollHeight;
}

async function sendChatMessage() {
  const input = document.getElementById("chat-input");
  const text = input.value.trim();
  if (!text) return;

  input.value = "";
  input.disabled = true;
  document.getElementById("send-chat-btn").disabled = true;

  appendChatMessage("user", text);

  // Add typing indicator
  const container = document.getElementById("chat-messages");
  const typingDiv = document.createElement("div");
  typingDiv.className = "chat-msg ai-msg";
  typingDiv.id = "chat-typing";
  typingDiv.innerHTML = `<div class="msg-bubble" style="font-family: var(--font-mono); font-size: 13px;">Thinking...</div>`;
  container.appendChild(typingDiv);
  scrollToChatBottom();

  try {
    const res = await fetch(`${API}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text })
    });
    const data = await res.json();

    // Remove typing indicator
    const t = document.getElementById("chat-typing");
    if (t) t.remove();

    appendChatMessage("model", data.reply || "Something went wrong.");
  } catch (e) {
    const t = document.getElementById("chat-typing");
    if (t) t.remove();
    appendChatMessage("system", "Network error. Please try again.");
  } finally {
    input.disabled = false;
    document.getElementById("send-chat-btn").disabled = false;
    input.focus();
  }
}

async function clearChat() {
  if (!confirm("Clear conversation history?")) return;
  try {
    await fetch(`${API}/api/chat/history`, { method: "DELETE" });
    const container = document.getElementById("chat-messages");
    container.innerHTML = `<div class="chat-msg system-msg"><div class="msg-bubble">👋 Hello! I'm PSX Pro. I have full access to live market data, news, announcements, your portfolio, and latest stock signals. Ask me anything about the PSX!</div></div>`;
  } catch (e) { console.error("Clear chat error", e); }
}

// Escape key to go back
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && currentPanel === "stock-detail") navigateTo("market");
});

// ══════════════════════════════════════════════════════════════
//  FETCH INDEX STOCK LISTS (for KSE100/KMI30 filtering)
// ══════════════════════════════════════════════════════════════
async function fetchIndexStockLists() {
  try {
    const [kse100Res, kmi30Res] = await Promise.all([
      fetch(`${API}/api/stocks/index/KSE100`),
      fetch(`${API}/api/stocks/index/KMI30`)
    ]);
    const kse100Data = await kse100Res.json();
    const kmi30Data = await kmi30Res.json();
    kse100Stocks = (kse100Data.data || []).map(s => s.symbol);
    kmi30Stocks = (kmi30Data.data || []).map(s => s.symbol);
    console.log(`📊 Index stocks loaded: KSE100=${kse100Stocks.length}, KMI30=${kmi30Stocks.length}`);
  } catch (e) {
    console.error("Error loading index stock lists:", e);
  }
}

// ══════════════════════════════════════════════════════════════
//  MAIN FETCH & REFRESH LOOP
// ══════════════════════════════════════════════════════════════
async function fetchAll() {
  try {
    const [marketRes, stocksRes, newsRes, sectorsRes] = await Promise.all([
      fetch(`${API}/api/market`),
      fetch(`${API}/api/stocks?limit=500`),
      fetch(`${API}/api/news`),
      fetch(`${API}/api/sectors`),
    ]);
    const market = await marketRes.json();
    const stocks = await stocksRes.json();
    const news = await newsRes.json();
    const sectors = await sectorsRes.json();

    allStocks = stocks.data || [];
    allNews = news.data || [];

    updateTopBar(market);
    renderMarketBanner(market.market_analysis);
    renderSectors(sectors.sectors || sectors.data || []);
    renderStocks(allStocks);
    renderNews(allNews);

    // Check for triggered alerts
    checkTriggeredAlerts();
  } catch (e) {
    console.error("Fetch error:", e);
    document.getElementById("update-time").textContent = "Connection error...";
  }
}

// ── Init ─────────────────────────────────────────────────────
fetchAll();
fetchIndexStockLists();  // Load KSE100/KMI30 symbol lists
setInterval(fetchAll, 30000);
setInterval(fetchIndexStockLists, 300000);  // Refresh index stock lists every 5 min

// Handle initial hash route
const initHash = window.location.hash.slice(1);
if (initHash) {
  if (initHash.startsWith("stock/")) {
    navigateTo("stock-detail", initHash.split("/")[1]);
  } else {
    navigateTo(initHash);
  }
}