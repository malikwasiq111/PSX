// ═══════════════════════════════════════════
//  PSX AI ANALYST — Frontend v3
// ═══════════════════════════════════════════

const API = "http://localhost:8000";

let allStocks = [];
let allNews = [];
let currentFilter = "all";
let currentNewsFilter = "all";
let priceChart = null;   // Chart.js instance

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmt(n, dec = 2) {
  if (n == null || isNaN(n)) return "—";
  return Number(n).toLocaleString("en-PK", { minimumFractionDigits: dec, maximumFractionDigits: dec });
}
function chgClass(v) { return v > 0 ? "chg-up" : v < 0 ? "chg-down" : "chg-flat"; }
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
  return new Date(isoStr).toLocaleTimeString("en-PK", { hour: "2-digit", minute: "2-digit" });
}


// ── Top Bar ───────────────────────────────────────────────────────────────────

function updateTopBar(market) {
  if (!market) return;
  const { kse100, pkr, market_analysis, last_updated } = market;
  if (kse100) {
    document.getElementById("kse-value").textContent = fmt(kse100.value, 0);
    const el = document.getElementById("kse-change");
    el.textContent = `${chgArrow(kse100.change_pct)} ${Math.abs(kse100.change_pct).toFixed(2)}%`;
    el.className = `macro-change ${kse100.change_pct >= 0 ? "up" : "down"}`;
  }
  if (pkr) {
    document.getElementById("pkr-value").textContent = fmt(pkr.rate, 2);
    const el = document.getElementById("pkr-change");
    el.textContent = `${chgArrow(pkr.change_pct)} ${Math.abs(pkr.change_pct).toFixed(2)}%`;
    el.className = `macro-change ${pkr.change_pct >= 0 ? "down" : "up"}`;
  }
  if (market_analysis) {
    const sent = market_analysis.overall_sentiment || "Neutral";
    document.getElementById("market-sentiment").textContent = sent.toUpperCase();
    document.getElementById("sentiment-pill").style.borderColor =
      sent === "Bullish" ? "var(--green-dim)" : sent === "Bearish" ? "var(--red-dim)" : "var(--border)";
  }
  document.getElementById("update-time").textContent = `Updated ${timeSince(last_updated)}`;
}


// ── Market Overview ───────────────────────────────────────────────────────────

function renderMarketOverview(ma) {
  if (!ma) return;
  const score = ma.sentiment_score || 0;
  const scoreEl = document.getElementById("mo-score");
  scoreEl.textContent = (score > 0 ? "+" : "") + score;
  scoreEl.className = `mo-score ${score > 0 ? "positive" : score < 0 ? "negative" : "neutral"}`;
  document.getElementById("mo-summary").textContent = ma.summary || "—";
  document.getElementById("mo-tags").innerHTML = (ma.key_drivers || [])
    .map(d => `<span class="mo-tag">⚡ ${d}</span>`).join("");
  document.getElementById("mo-hot").innerHTML = (ma.hot_sectors || [])
    .map(s => `<span class="sector-tag hot">${s}</span>`).join("") || "<span class='mo-tag'>—</span>";
  document.getElementById("mo-weak").innerHTML = (ma.weak_sectors || [])
    .map(s => `<span class="sector-tag weak">${s}</span>`).join("") || "<span class='mo-tag'>—</span>";
  document.getElementById("mo-advice").innerHTML =
    `💡 ${ma.market_advice || ""} ${ma.watch_out ? `<br>⚠️ ${ma.watch_out}` : ""}`;
}


// ── Sector Row ────────────────────────────────────────────────────────────────

function renderSectors(sectors) {
  document.getElementById("sector-row").innerHTML = sectors.map(s => `
    <div class="sector-card ${s.trend}">
      <span class="sector-name">${s.sector.toUpperCase()}</span>
      <span class="sector-chg ${s.trend}">${chgArrow(s.avg_change)} ${Math.abs(s.avg_change).toFixed(2)}%</span>
    </div>`).join("");
}


// ── Stock Table ───────────────────────────────────────────────────────────────

function applyStockFilter(stocks) {
  switch (currentFilter) {
    case "shariah": return stocks.filter(s => s.shariah);
    case "gainers": return [...stocks].sort((a, b) => b.change_pct - a.change_pct).slice(0, 10);
    case "losers": return [...stocks].sort((a, b) => a.change_pct - b.change_pct).slice(0, 10);
    default: return stocks;
  }
}

function renderStocks(stocks) {
  const tbody = document.getElementById("stock-tbody");
  const filtered = applyStockFilter(stocks);
  if (!filtered.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="loading-row">No stocks found.</td></tr>`;
    return;
  }
  tbody.innerHTML = filtered.map(s => `
    <tr onclick="openStockModal('${s.symbol}')">
      <td><span class="stock-symbol">${s.symbol}</span><span class="stock-name">${s.name}</span></td>
      <td><span class="price-val">₨${fmt(s.price)}</span></td>
      <td class="${chgClass(s.change_pct)}">${chgArrow(s.change_pct)} ${Math.abs(s.change_pct).toFixed(2)}%</td>
      <td><span class="signal-badge ${signalClass(s._signal || null)}">${s._signal || "···"}</span></td>
      <td class="${s.shariah ? "halal-tag" : ""}">${s.shariah ? "✓" : ""}</td>
    </tr>`).join("");
}


// ── News Feed ─────────────────────────────────────────────────────────────────

function renderNews(news) {
  const feed = document.getElementById("news-feed");
  const filtered = currentNewsFilter === "all" ? news
    : news.filter(n => n.sentiment === currentNewsFilter);
  if (!filtered.length) { feed.innerHTML = `<div class="loading-row">No news found.</div>`; return; }
  feed.innerHTML = filtered.map(n => `
    <div class="news-card ${n.sentiment}" onclick="window.open('${n.link}','_blank')">
      <div class="news-top">
        <span class="news-title">${n.title}</span>
        <span class="news-sentiment ${n.sentiment}">${n.sentiment.toUpperCase()}</span>
      </div>
      ${n.market_impact ? `<div><span class="market-impact-tag ${n.market_impact}">
        ${n.market_impact === "market_positive" ? "📈 MARKET POSITIVE" : "📉 MARKET NEGATIVE"}</span></div>` : ""}
      <div class="news-meta">
        <span class="news-source">${n.source}</span>
        <span>${timeSince(n.timestamp)}</span>
        <div class="news-stocks">
          ${(n.related_stocks || []).map(sym =>
    `<span class="news-stock-tag" onclick="event.stopPropagation();openStockModal('${sym}')">${sym}</span>`
  ).join("")}
        </div>
      </div>
    </div>`).join("");
}


// ── Stock Modal ───────────────────────────────────────────────────────────────

async function openStockModal(symbol) {
  document.getElementById("modal-overlay").classList.add("open");
  document.getElementById("stock-modal").classList.add("open");
  document.getElementById("modal-content").innerHTML =
    `<p class="loading-row" style="margin-top:40px">Loading ${symbol}...</p>`;
  if (priceChart) { priceChart.destroy(); priceChart = null; }

  try {
    const res = await fetch(`${API}/api/stocks/${symbol}`);
    const data = await res.json();
    renderModal(data);
  } catch (e) {
    document.getElementById("modal-content").innerHTML =
      `<p class="loading-row" style="color:var(--red)">Error loading data.</p>`;
  }
}

function closeModal() {
  document.getElementById("modal-overlay").classList.remove("open");
  document.getElementById("stock-modal").classList.remove("open");
  if (priceChart) { priceChart.destroy(); priceChart = null; }
}

function renderModal({ stock, signal, technical, related_news, dividends }) {
  if (!stock) return;
  const s = stock;
  const sig = signal || {};
  const tech = technical || null;

  document.getElementById("modal-content").innerHTML = `
    <!-- Header -->
    <div class="modal-symbol">${s.symbol}
      ${s.shariah ? `<span class="halal-tag" style="font-size:14px"> ✓ Halal</span>` : ""}
    </div>
    <div class="modal-name">${s.name} · ${s.sector}</div>

    <!-- Price Row -->
    <div class="modal-price-row">
      <div>
        <div class="modal-price-label">CURRENT PRICE</div>
        <div class="modal-price">₨${fmt(s.price)}</div>
      </div>
      <div>
        <div class="modal-price-label">TODAY</div>
        <div class="modal-price ${chgClass(s.change_pct)}" style="font-size:22px">
          ${chgArrow(s.change_pct)} ${Math.abs(s.change_pct).toFixed(2)}%
        </div>
      </div>
    </div>

    <!-- Stats -->
    <div class="modal-stats">
      <div class="stat-box"><div class="stat-label">PREV CLOSE</div><div class="stat-value">₨${fmt(s.prev_close)}</div></div>
      <div class="stat-box"><div class="stat-label">DAY HIGH</div><div class="stat-value">₨${fmt(s.high)}</div></div>
      <div class="stat-box"><div class="stat-label">DAY LOW</div><div class="stat-value">₨${fmt(s.low)}</div></div>
      <div class="stat-box"><div class="stat-label">VOLUME</div><div class="stat-value">${s.volume ? (s.volume / 1000).toFixed(0) + "K" : "—"}</div></div>
      <div class="stat-box"><div class="stat-label">RISK LEVEL</div>
        <div class="stat-value" style="color:${sig.risk_level === 'Low' ? 'var(--green)' : sig.risk_level === 'High' ? 'var(--red)' : 'var(--amber)'}">
          ${sig.risk_level || "—"}</div></div>
      <div class="stat-box"><div class="stat-label">HOLD PERIOD</div><div class="stat-value" style="font-size:11px">${sig.holding_period || "—"}</div></div>
    </div>

    <!-- AI Signal -->
    <div class="signal-section">
      <div class="signal-header">
        <span class="signal-label">AI SIGNAL (Phase 3)</span>
        <span class="signal-main ${signalClass(sig.signal)}">${sig.signal || "—"}</span>
      </div>
      <div class="price-targets">
        <div class="target-box"><span class="target-label">ENTRY</span><span class="target-val entry">₨${fmt(sig.entry_price)}</span></div>
        <div class="target-box"><span class="target-label">TARGET</span><span class="target-val tp">₨${fmt(sig.target_price)}</span></div>
        <div class="target-box"><span class="target-label">STOP LOSS</span><span class="target-val sl">₨${fmt(sig.stop_loss)}</span></div>
      </div>
      <div class="conf-bar-wrap">
        <div class="conf-bar-label"><span>CONFIDENCE</span><span>${sig.confidence || 0}%</span></div>
        <div class="conf-bar-bg"><div class="conf-bar-fill" style="width:${sig.confidence || 0}%"></div></div>
      </div>
      <div class="signal-reasoning">${sig.reasoning || "—"}</div>
      ${sig.technical_summary || sig.news_summary ? `
        <div class="signal-meta-row">
          ${sig.technical_summary ? `<div class="signal-meta-box"><div class="signal-meta-label">TECHNICALS SAY</div><div class="signal-meta-val">${sig.technical_summary}</div></div>` : ""}
          ${sig.news_summary ? `<div class="signal-meta-box"><div class="signal-meta-label">NEWS SAYS</div><div class="signal-meta-val">${sig.news_summary}</div></div>` : ""}
        </div>` : ""}
      ${sig.key_risk ? `<div style="margin-top:8px;font-family:var(--font-mono);font-size:10px;color:var(--amber)">⚠️ ${sig.key_risk}</div>` : ""}
    </div>

    <!-- Chart -->
    ${tech && tech.chart_data && tech.chart_data.length > 5 ? `
      <div class="chart-section">
        <div class="chart-label">90-DAY PRICE CHART + MA20/MA50</div>
        <div class="chart-wrap"><canvas id="price-chart"></canvas></div>
      </div>` : ""}

    <!-- Technical Indicators -->
    ${tech ? renderTechnicalPanel(tech) : ""}

    <!-- Related Dividends -->
    ${dividends && dividends.length ? `
      <div class="modal-news-title" style="margin-top:14px">DIVIDEND HISTORY</div>
      ${dividends.slice(0, 3).map(d => `
        <div class="modal-news-item">
          <span style="font-family:var(--font-mono);font-size:9px;padding:1px 5px;border-radius:2px;
            background:var(--bg3);color:var(--green);margin-right:6px">${d.type.toUpperCase()}</span>
          ${d.amount_per_share ? `PKR ${d.amount_per_share}/share · ` : ""}
          ${d.book_closure_date ? `Book closure: ${d.book_closure_date} · ` : ""}
          ${d.source}
        </div>`).join("")}` : ""}

    <!-- Related News -->
    ${related_news && related_news.length ? `
      <div class="modal-news-title">RELATED NEWS</div>
      ${related_news.map(n => `
        <div class="modal-news-item" onclick="window.open('${n.link}','_blank')" style="cursor:pointer">
          <span class="news-sentiment ${n.sentiment}" style="margin-right:6px;font-size:8px;padding:1px 5px;border-radius:2px;background:var(--bg3)">${n.sentiment.toUpperCase()}</span>
          ${n.title}
        </div>`).join("")}` : ""}
  `;

  // Draw chart after DOM update
  if (tech && tech.chart_data && tech.chart_data.length > 5) {
    setTimeout(() => drawPriceChart(tech), 100);
  }
}


// ── Technical Indicators Panel ────────────────────────────────────────────────

function renderTechnicalPanel(tech) {
  if (!tech) return "";

  const rsiColor = tech.rsi < 30 ? "var(--green)" : tech.rsi > 70 ? "var(--red)" : "var(--amber)";
  const macdColor = tech.macd_cross.includes("bullish") ? "var(--green)" : "var(--red)";
  const trendColor = tech.trend === "uptrend" ? "var(--green)" : tech.trend === "downtrend" ? "var(--red)" : "var(--amber)";
  const rsiPct = Math.min(100, Math.max(0, tech.rsi));

  // Cross alert
  const crossAlert = tech.cross_signal ? `
    <div class="cross-alert ${tech.cross_signal === 'golden_cross' ? 'golden' : 'death'}">
      ${tech.cross_signal === 'golden_cross' ? "⚡ GOLDEN CROSS — MA20 crossed above MA50 (Strong Bullish)" :
      "💀 DEATH CROSS — MA20 crossed below MA50 (Strong Bearish)"}
    </div>` : "";

  // Support / Resistance
  const srSection = (tech.supports.length || tech.resistances.length) ? `
    <div class="sr-row">
      <div>
        <div class="sr-col-label">SUPPORT LEVELS</div>
        ${tech.supports.map(s => `<span class="sr-level sr-support">₨${s}</span><br>`).join("") || "<span class='sr-level sr-support'>N/A</span>"}
      </div>
      <div>
        <div class="sr-col-label">RESISTANCE LEVELS</div>
        ${tech.resistances.map(r => `<span class="sr-level sr-resistance">₨${r}</span><br>`).join("") || "<span class='sr-level sr-resistance'>N/A</span>"}
      </div>
    </div>` : "";

  return `
    <div class="tech-panel">
      <div class="tech-panel-header">
        <span class="tech-panel-label">TECHNICAL INDICATORS</span>
        <span class="tech-overall ${signalClass(tech.tech_signal)}">${tech.tech_signal}</span>
      </div>

      <div class="tech-grid">

        <!-- RSI -->
        <div class="tech-item">
          <div class="tech-item-label">RSI (14)</div>
          <div class="tech-item-val" style="color:${rsiColor}">${tech.rsi}</div>
          <div class="tech-item-sub">${tech.rsi_signal.toUpperCase()}</div>
          <div class="rsi-bar-wrap">
            <div class="rsi-bar-bg">
              <div class="rsi-bar-marker" style="left:${rsiPct}%"></div>
            </div>
            <div class="rsi-labels"><span>Oversold 30</span><span>70 Overbought</span></div>
          </div>
        </div>

        <!-- MACD -->
        <div class="tech-item">
          <div class="tech-item-label">MACD</div>
          <div class="tech-item-val" style="color:${macdColor}">${tech.macd}</div>
          <div class="tech-item-sub">${tech.macd_cross.toUpperCase().replace(/_/g, " ")}</div>
          <div class="tech-item-sub" style="margin-top:2px">Signal: ${tech.macd_signal} | Hist: ${tech.macd_hist}</div>
        </div>

        <!-- Moving Averages -->
        <div class="tech-item">
          <div class="tech-item-label">MOVING AVERAGES</div>
          <div class="tech-item-val" style="color:${trendColor}">${tech.trend.toUpperCase().replace(/_/g, " ")}</div>
          <div class="tech-item-sub">MA20: ₨${tech.ma20}</div>
          ${tech.ma50 ? `<div class="tech-item-sub">MA50: ₨${tech.ma50}</div>` : ""}
        </div>

        <!-- Bollinger Bands -->
        <div class="tech-item">
          <div class="tech-item-label">BOLLINGER BANDS</div>
          <div class="tech-item-val" style="color:${tech.bb_pct < 20 ? "var(--green)" : tech.bb_pct > 80 ? "var(--red)" : "var(--blue)"}">
            ${tech.bb_signal.toUpperCase().replace(/_/g, " ")}
          </div>
          <div class="tech-item-sub">Position: ${tech.bb_pct}%</div>
          <div class="bb-bar-wrap">
            <div class="bb-bar-bg">
              <div class="bb-bar-marker" style="left:${Math.min(100, Math.max(0, tech.bb_pct))}%"></div>
            </div>
          </div>
          <div class="tech-item-sub" style="margin-top:3px">₨${tech.bb_lower} – ₨${tech.bb_upper}</div>
        </div>

        <!-- Volume -->
        <div class="tech-item">
          <div class="tech-item-label">VOLUME</div>
          <div class="tech-item-val" style="color:${tech.volume_surge ? "var(--green)" : "var(--text)"}">
            ${tech.volume_surge ? "🔥 SURGE" : "Normal"}
          </div>
          <div class="tech-item-sub">${tech.volume_ratio}× avg volume</div>
        </div>

        <!-- Tech Score -->
        <div class="tech-item">
          <div class="tech-item-label">COMPOSITE SCORE</div>
          <div class="tech-item-val" style="color:${tech.tech_score > 0 ? "var(--green)" : tech.tech_score < 0 ? "var(--red)" : "var(--amber)"}">
            ${tech.tech_score > 0 ? "+" : ""}${tech.tech_score} / 8
          </div>
          <div class="tech-item-sub">Confidence: ${tech.tech_confidence}%</div>
        </div>

      </div>

      ${crossAlert}
      ${srSection}
    </div>`;
}


// ── Chart.js Price Chart ──────────────────────────────────────────────────────

function drawPriceChart(tech) {
  const canvas = document.getElementById("price-chart");
  if (!canvas || !tech.chart_data) return;

  const labels = tech.chart_data.map(d => d.date.slice(5)); // MM-DD
  const closes = tech.chart_data.map(d => d.close);
  const ma20 = tech.ma20_chart || [];
  const ma50 = tech.ma50_chart || [];

  if (priceChart) { priceChart.destroy(); priceChart = null; }

  const ctx = canvas.getContext("2d");
  priceChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Price",
          data: closes,
          borderColor: "#58a6ff",
          backgroundColor: "rgba(88,166,255,0.08)",
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.2,
          fill: true,
          order: 1,
        },
        {
          label: "MA20",
          data: ma20,
          borderColor: "#d29922",
          borderWidth: 1,
          pointRadius: 0,
          tension: 0.3,
          fill: false,
          order: 2,
        },
        ...(ma50.length ? [{
          label: "MA50",
          data: ma50,
          borderColor: "#bc8cff",
          borderWidth: 1,
          pointRadius: 0,
          tension: 0.3,
          fill: false,
          order: 3,
        }] : []),
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 300 },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          labels: {
            color: "#8b949e",
            font: { family: "Space Mono", size: 9 },
            boxWidth: 20,
            padding: 8,
          },
        },
        tooltip: {
          backgroundColor: "#161b22",
          borderColor: "#30363d",
          borderWidth: 1,
          titleColor: "#e6edf3",
          bodyColor: "#8b949e",
          titleFont: { family: "Space Mono", size: 10 },
          bodyFont: { family: "Space Mono", size: 10 },
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: ₨${ctx.parsed.y?.toFixed(2) ?? "—"}`,
          },
        },
      },
      scales: {
        x: {
          ticks: { color: "#484f58", font: { family: "Space Mono", size: 8 }, maxTicksLimit: 8 },
          grid: { color: "#21262d" },
        },
        y: {
          ticks: {
            color: "#484f58", font: { family: "Space Mono", size: 8 },
            callback: v => `₨${Number(v).toLocaleString()}`
          },
          grid: { color: "#21262d" },
        },
      },
    },
  });
}


// ── Tab Switching ─────────────────────────────────────────────────────────────

document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const target = btn.dataset.tab;
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-view").forEach(v => v.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${target}`).classList.add("active");
    if (target === "portfolio") fetchPortfolio();
    if (target === "dividends") fetchDividends();
  });
});


// ── Portfolio ─────────────────────────────────────────────────────────────────

async function fetchPortfolio() {
  try {
    const res = await fetch(`${API}/api/portfolio`);
    const data = await res.json();
    renderPortfolioSummary(data.summary);
    renderHoldings(data.holdings);
  } catch (e) {
    document.getElementById("port-holdings").innerHTML =
      `<p class="loading-row" style="color:var(--red)">Error loading portfolio.</p>`;
  }
}

function renderPortfolioSummary(s) {
  if (!s) return;
  document.getElementById("port-invested").textContent = `₨${fmt(s.total_invested, 0)}`;
  document.getElementById("port-current").textContent = `₨${fmt(s.total_current, 0)}`;
  document.getElementById("port-count").textContent = s.num_holdings;
  const pnl = s.total_pnl, pct = s.total_pnl_pct;
  const pnlEl = document.getElementById("port-pnl");
  const pctEl = document.getElementById("port-pnl-pct");
  pnlEl.textContent = `${pnl >= 0 ? "+" : ""}₨${fmt(Math.abs(pnl), 0)}`;
  pnlEl.style.color = pnl >= 0 ? "var(--green)" : "var(--red)";
  pctEl.textContent = `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
  pctEl.style.color = pct >= 0 ? "var(--green)" : "var(--red)";
}

function renderHoldings(holdings) {
  const el = document.getElementById("port-holdings");
  if (!holdings || !holdings.length) {
    el.innerHTML = `<p class="loading-row">No holdings yet. Add your first stock below.</p>`;
    return;
  }
  el.innerHTML = holdings.map(h => {
    const pnlColor = h.pnl >= 0 ? "var(--green)" : "var(--red)";
    return `
    <div class="holding-card ${h.pnl > 0 ? "profit" : h.pnl < 0 ? "loss" : ""}">
      <div>
        <div class="holding-sym">${h.symbol}</div>
        <div class="holding-name">${h.name || ""} ${h.shariah ? "✓" : ""}</div>
      </div>
      <div>
        <span class="holding-col-label">SHARES × BUY</span>
        <span class="holding-col-val">${h.shares} × ₨${fmt(h.buy_price)}</span>
      </div>
      <div>
        <span class="holding-col-label">CURRENT</span>
        <span class="holding-col-val ${h.has_live_data ? chgClass(h.today_change) : ""}">
          ${h.has_live_data ? `₨${fmt(h.current_price)}` : "—"}
          ${h.has_live_data ? `<small style="font-size:9px"> (${h.today_change >= 0 ? "+" : ""}${h.today_change?.toFixed(2)}%)</small>` : ""}
        </span>
      </div>
      <div>
        <span class="holding-col-label">P&L</span>
        <span class="holding-col-val" style="color:${pnlColor}">
          ${h.pnl != null ? `${h.pnl >= 0 ? "+" : ""}₨${fmt(Math.abs(h.pnl), 0)} (${h.pnl_pct >= 0 ? "+" : ""}${h.pnl_pct?.toFixed(1)}%)` : "—"}
        </span>
      </div>
      <button class="btn-remove" onclick="removeHolding('${h.symbol}')">✕</button>
    </div>`;
  }).join("");
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
  panel.innerHTML = `<p class="loading-row" style="padding:40px 0">🤖 Analyzing your portfolio...</p>`;
  try {
    const res = await fetch(`${API}/api/portfolio/advice`);
    const data = await res.json();
    renderPortfolioAdvice(data.advice);
    renderPortfolioSummary(data.portfolio?.summary);
    renderHoldings(data.portfolio?.holdings);
  } catch (e) { panel.innerHTML = `<p class="loading-row" style="color:var(--red)">Error.</p>`; }
}

function renderPortfolioAdvice(a) {
  const panel = document.getElementById("port-advice-panel");
  if (!a) { panel.innerHTML = `<p class="loading-row">No advice available.</p>`; return; }
  const scoreColor = a.health_score >= 70 ? "var(--green)" : a.health_score >= 40 ? "var(--amber)" : "var(--red)";
  panel.innerHTML = `
    <div class="advice-health">
      <div>
        <div class="advice-health-label">PORTFOLIO HEALTH</div>
        <div style="font-family:var(--font-mono);font-weight:700;font-size:16px;color:${scoreColor}">${a.overall_health}</div>
      </div>
      <div class="advice-health-score" style="color:${scoreColor}">${a.health_score}</div>
    </div>
    <div class="advice-summary">${a.summary}</div>
    ${a.actions?.length ? `<div class="advice-actions-title">STOCK ACTIONS</div>
      ${a.actions.map(act => `
        <div class="advice-action">
          <span class="action-sym">${act.symbol}</span>
          <span class="action-badge action-${act.action.replace(" ", "_")}">${act.action}</span>
          <span class="action-reason">${act.reason}</span>
        </div>`).join("")}` : ""}
    ${a.diversification_tip ? `<div class="advice-tip">💡 ${a.diversification_tip}</div>` : ""}
    ${a.risk_warning ? `<div class="advice-warning">⚠️ ${a.risk_warning}</div>` : ""}`;
}


// ── Dividends ─────────────────────────────────────────────────────────────────

async function fetchDividends() {
  try {
    const res = await fetch(`${API}/api/dividends`);
    const data = await res.json();
    renderDividends(data.data || []);
  } catch (e) {
    document.getElementById("div-grid").innerHTML =
      `<p class="loading-row" style="color:var(--red)">Error loading dividends.</p>`;
  }
}

function renderDividends(divs) {
  const grid = document.getElementById("div-grid");
  if (!divs.length) {
    grid.innerHTML = `<div class="div-empty">No dividend announcements found yet.<br>
      <small>Sources: sarmaaya.pk · scstrade.com · Google News</small></div>`;
    return;
  }
  grid.innerHTML = divs.map(d => {
    const type = d.type || "Cash Dividend";
    const typeCls = type.toLowerCase().includes("bonus") ? "bonus" :
      type.toLowerCase().includes("interim") ? "interim" :
        type.toLowerCase().includes("right") ? "right" : "cash";
    return `
    <div class="div-card ${typeCls}">
      <div class="div-card-top">
        <span class="div-symbol" onclick="openStockModal('${d.symbol}')" style="cursor:pointer">${d.symbol}</span>
        <span class="div-type-badge type-${typeCls}">${type.toUpperCase()}</span>
      </div>
      <div class="div-subject">${d.subject || d.company || "—"}</div>
      ${d.amount_per_share ? `<div class="div-amount">PKR ${d.amount_per_share}</div><div class="div-amount-label">PER SHARE</div>` :
        d.percentage ? `<div class="div-amount">${d.percentage}%</div><div class="div-amount-label">RATIO</div>` : ""}
      <div class="div-advice">${d.advice || "—"}</div>
      <div class="div-meta">
        <span>${d.announcement_date || d.date || "—"}</span>
        ${d.book_closure_date ? `<span>Closure: ${d.book_closure_date}</span>` : ""}
        ${d.link ? `<a class="div-link" href="${d.link}" target="_blank">View →</a>` : `<span>${d.source || ""}</span>`}
      </div>
    </div>`;
  }).join("");
}


// ── Filter Listeners ──────────────────────────────────────────────────────────

document.querySelectorAll(".filter-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentFilter = btn.dataset.filter;
    renderStocks(allStocks);
  });
});
document.querySelectorAll(".news-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".news-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentNewsFilter = btn.dataset.news;
    renderNews(allNews);
  });
});
document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });


// ── Main Fetch & Refresh ──────────────────────────────────────────────────────

async function fetchAll() {
  try {
    const [marketRes, stocksRes, newsRes, sectorsRes] = await Promise.all([
      fetch(`${API}/api/market`),
      fetch(`${API}/api/stocks`),
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
    renderMarketOverview(market.market_analysis);
    renderSectors(sectors.data || []);
    renderStocks(allStocks);
    renderNews(allNews);
  } catch (e) {
    console.error("Fetch error:", e);
    document.getElementById("update-time").textContent = "Connection error — retrying...";
  }
}

fetchAll();
setInterval(fetchAll, 30000);