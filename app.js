"use strict";
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const n = (v, d = 2) => v == null || isNaN(v) ? "—" : Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const cls = v => v > 0 ? "up" : v < 0 ? "dn" : "fl";
const pct = v => v == null ? "—" : `${v > 0 ? "▲" : v < 0 ? "▼" : ""} ${Math.abs(v).toFixed(2)}%`;
const vol = v => !v ? "—" : v >= 1e6 ? (v / 1e6).toFixed(2) + "M" : v >= 1e3 ? (v / 1e3).toFixed(1) + "K" : v;
const api = async (u, o) => { try { const r = await fetch("/api" + u, o); if (!r.ok) throw new Error(r.status); return await r.json(); } catch (e) { return null; } };
const send = (u, m, b) => api(u, { method: m, headers: { "Content-Type": "application/json" }, body: b ? JSON.stringify(b) : undefined });
const toast = m => { const t = document.createElement("div"); t.className = "toast"; t.innerHTML = m; $("#toasts").append(t); setTimeout(() => t.remove(), 6000); };
const I = d => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
const ROUTES = [
  ["", "Overview", I('<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>')],
  ["markets", "Markets", I('<path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/>')],
  ["compare", "Compare", I('<path d="M4 20V10M10 20V4M16 20v-7M22 20V8"/>')],
  ["watchlist", "Watchlist", I('<path d="M12 3l2.8 5.7 6.2.9-4.5 4.4 1 6.2L12 17.3 6.5 20.2l1-6.2L3 9.6l6.2-.9z"/>')],
  ["portfolio", "Portfolio", I('<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2"/>')],
  ["calendar", "Corporate", I('<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M3 10h18M8 2v4M16 2v4"/>')],
  ["alerts", "Alerts", I('<path d="M6 8a6 6 0 0112 0c0 7 3 9 3 9H3s3-2 3-9M10 21a2 2 0 004 0"/>')],
];
let charts = [], stocks = [], lastRoute = 0, timer = null, prices = {};
const kill = () => { charts.forEach(c => c.destroy()); charts = []; };
const css = k => getComputedStyle(document.documentElement).getPropertyValue(k).trim();

/* ── shell ── */
$("#nav").insertAdjacentHTML("beforeend", ROUTES.map(([h, l, i]) => `<a href="#/${h}" data-r="${h}">${i}<span>${l}</span></a>`).join(""));
function movePill(h) {
  const i = Math.max(0, ROUTES.findIndex(r => r[0] === h)), a = $(`#nav a[data-r="${ROUTES[i][0]}"]`);
  document.querySelectorAll("#nav a").forEach(x => x.classList.toggle("on", x === a));
  $("#pill").style.transform = `translateY(${a.offsetTop}px)`; return i;
}
$("#theme").onclick = () => { const t = document.documentElement.dataset.theme === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = t; localStorage.setItem("psx-theme", t); route(true); };
document.documentElement.dataset.theme = localStorage.getItem("psx-theme") || "dark";

/* ── router with directional slide ── */
async function route(soft) {
  const [, seg = "", arg] = location.hash.replace("#", "").split("/");
  const idx = movePill(seg === "stock" ? "markets" : seg), v = $("#view");
  kill(); clearInterval(timer);
  if (!soft) { v.className = "view"; void v.offsetWidth; v.className = "view " + (idx >= lastRoute ? "in-r" : "in-l"); }
  lastRoute = idx; window.scrollTo(0, 0);
  const page = { "": Overview, markets: Markets, compare: Compare, watchlist: Watchlist, portfolio: Portfolio, calendar: Corporate, alerts: Alerts, stock: Stock }[seg] || Overview;
  v.innerHTML = '<div class="grid g4">' + '<div class="skel" style="height:110px"></div>'.repeat(4) + '</div><div class="skel" style="height:320px;margin-top:16px"></div>';
  const rf = await page(v, arg && decodeURIComponent(arg).toUpperCase());
  if (typeof rf === "function") timer = setInterval(async () => { if (!document.hidden) await rf(); }, 30000);
}
addEventListener("hashchange", () => route()); addEventListener("resize", () => movePill(location.hash.split("/")[1] || ""));

/* ── shared pieces ── */
const kpi = (l, val, c, s = "") => `<div class="card kpi hov"><div class="lbl">${l}</div><div class="val num">${val}</div><div class="chg num ${cls(c)}">${pct(c)} <span class="fl" style="font-weight:400">${s}</span></div></div>`;
const rowS = s => `<div class="row" onclick="location.hash='#/stock/${esc(s.symbol)}'"><div><div class="sym">${esc(s.symbol)}</div><div class="nm">${esc(s.name || s.sector || "")}</div></div><div class="r num"><div>${n(s.price)}</div><div class="${cls(s.change_pct)}" style="font-size:12px">${pct(s.change_pct)}</div></div></div>`;
const sigChip = s => `<span class="chip ${/BUY/.test(s) ? "up" : /SELL/.test(s) ? "dn" : ""}">${esc(s || "—")}</span>`;
function spark(el, labels, data, color, fill = true) {
  const ctx = el.getContext("2d"), g = ctx.createLinearGradient(0, 0, 0, el.height || 300);
  g.addColorStop(0, color + "55"); g.addColorStop(1, color + "00");
  charts.push(new Chart(el, { type: "line", data: { labels, datasets: [{ data, borderColor: color, backgroundColor: g, fill, tension: .3, pointRadius: 0, borderWidth: 2 }] },
    options: { responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: "index" }, plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { grid: { color: css("--bd") }, ticks: { color: css("--t3") } } } } }));
}
function heat(h) {
  const col = c => { const a = Math.min(1, Math.abs(c) / 4), g = c >= 0 ? "25,140,95" : "210,60,90"; return `rgba(${g},${.35 + a * .65})`; };
  return `<div class="hm">${(h?.sectors || []).map(s => { const w = s.stocks.reduce((a, x) => a + x.weight, 0); return `<div class="hm-s" style="--w:${Math.max(1, Math.round(w / 40))}"><h3>${esc(s.sector)}</h3><div class="hm-t">${s.stocks.map(t => `<a class="tile" href="#/stock/${esc(t.symbol)}" style="--w:${Math.max(1, Math.round(t.weight / 40))};background:${col(t.change_pct)}" title="${esc(t.symbol)} ${n(t.price)}"><b>${esc(t.symbol)}</b><span>${t.change_pct > 0 ? "+" : ""}${n(t.change_pct)}%</span></a>`).join("")}</div></div>`; }).join("") || '<div class="empty">Heatmap loads once index constituents arrive…</div>'}</div>`;
}

const hbar = (l, val, mx, href, unit = "%") => `<a class="hb" ${href ? `href="${href}"` : ""}><span>${esc(l)}</span><div class="hbt ${cls(val)}"><i style="width:${Math.min(100, Math.abs(val) / mx * 100)}%"></i></div><b class="num ${cls(val)}">${val > 0 ? "+" : ""}${n(val)}${unit}</b></a>`;
const sectorCard = d => { const L = (d.sectors || []).filter(s => s.sector && typeof s.change_pct === "number").sort((a, b) => b.change_pct - a.change_pct), mx = Math.max(1, ...L.map(s => Math.abs(s.change_pct)));
  return `<div class="card"><h2>Sector performance</h2>${L.slice(0, 12).map(s => hbar(s.sector, s.change_pct, mx)).join("") || '<div class="empty">Loading…</div>'}</div>`; };
const contribCard = d => { const L = (d.contributors || []).slice().sort((a, b) => b.contribution - a.contribution), pick = L.length > 10 ? [...L.slice(0, 5), ...L.slice(-5)] : L, mx = Math.max(1, ...pick.map(s => Math.abs(s.contribution)));
  return `<div class="card"><h2>What moved the KSE-100 <span class="chip">points</span></h2>${pick.map(s => hbar(s.symbol, s.contribution, mx, "#/stock/" + s.symbol, "")).join("") || '<div class="empty">Loading…</div>'}</div>`; };

/* ── pages ── */
async function Overview(v) { const r = () => Overview0(v); await r(); return r; }
async function Overview0(v) {
  kill(); const d = await api("/overview"); if (!d || !d.kse100) { v.innerHTML = '<div class="card empty">Waiting for first market refresh… this page retries automatically.</div>'; setTimeout(() => location.hash === "#/" && route(true), 4000); return; }
  const a = d.analysis || {}, b = d.breadth, tot = b.up + b.down + b.flat || 1, h = await api("/heatmap?index=KSE100");
  v.innerHTML = `<div class="head"><div><h1>Market Overview</h1><div class="sub">${d.market_open ? "Market is open" : "Market closed"} · KSE-100 ${esc(a.overall_sentiment || "")} (${a.sentiment_score ?? 0})</div></div></div>
  <div class="grid g4">${kpi("KSE-100", n(d.kse100.value), d.kse100.change_pct, n(d.kse100.change))}${kpi("KMI-30", n(d.kmi30?.value), d.kmi30?.change_pct)}${kpi("USD / PKR", n(d.pkr?.rate), d.pkr?.change_pct)}
  <div class="card kpi hov"><div class="lbl">Market breadth</div><div class="val num"><span class="up">${b.up}</span> / <span class="dn">${b.down}</span></div><div class="bar"><i style="width:${b.up / tot * 100}%;background:var(--up)"></i><i style="width:${b.flat / tot * 100}%;background:var(--t3)"></i><i style="width:${b.down / tot * 100}%;background:var(--dn)"></i></div></div></div>
  <div class="grid g3" style="margin-top:16px"><div class="card"><h2>KSE-100 · 30 days</h2><div class="cv"><canvas id="ix"></canvas></div></div>
  <div class="card"><h2>Market read</h2><p>${esc(a.summary || "")}</p><p class="sub" style="margin-top:10px">${esc(a.market_advice || "")}</p><div style="margin-top:12px;display:flex;gap:6px;flex-wrap:wrap">${(a.hot_sectors || []).map(s => `<span class="chip up">🔥 ${esc(s)}</span>`).join("")}${(a.weak_sectors || []).map(s => `<span class="chip dn">${esc(s)}</span>`).join("")}</div></div></div>
  <div class="card" style="margin-top:16px"><h2>Heatmap · KSE-100 <a class="chip" href="#/markets">Full view →</a></h2>${heat(h)}</div>
  <div class="grid g2" style="margin-top:16px;grid-template-columns:repeat(auto-fit,minmax(340px,1fr))">${sectorCard(d)}${contribCard(d)}</div>
  <div class="grid g4" style="margin-top:16px;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))"><div class="card"><h2>Top gainers</h2>${d.gainers.map(rowS).join("")}</div><div class="card"><h2>Top losers</h2>${d.losers.map(rowS).join("")}</div><div class="card"><h2>Most active</h2>${d.active.map(rowS).join("") || '<div class="empty">Loading…</div>'}</div></div>`;
  const hs = d.history?.KSE100 || []; if (hs.length) spark($("#ix"), hs.map(x => x.date), hs.map(x => x.close), d.kse100.change_pct >= 0 ? css("--up") : css("--dn"));
}

async function Markets(v) {
  const [r, h] = await Promise.all([api("/stocks?limit=600"), api("/heatmap?index=KSE100")]); stocks = r?.data || [];
  let mode = "table", filter = "all", q = "", sort = ["symbol", 1], shown = 100, cur = [];
  const draw = () => {
    let L = stocks.filter(s => (filter === "all" || (filter === "halal" ? s.shariah : filter === "up" ? s.change_pct > 0 : s.change_pct < 0)) && (s.symbol + s.name).toLowerCase().includes(q));
    L.sort((a, b) => (a[sort[0]] > b[sort[0]] ? 1 : -1) * sort[1]); cur = L;
    $("#mk").innerHTML = mode === "heat" ? `<div class="card">${heat(h)}</div>` : `<div class="tw flow"><table><thead><tr>${[["symbol", "Symbol"], ["sector", "Sector"], ["price", "Price"], ["change", "Chg"], ["change_pct", "Chg %"]].map(([k, l]) => `<th data-k="${k}">${l}${sort[0] === k ? (sort[1] > 0 ? " ↑" : " ↓") : ""}</th>`).join("")}<th>Halal</th></tr></thead><tbody>${L.slice(0, shown).map(s => `<tr onclick="location.hash='#/stock/${esc(s.symbol)}'" class="${prices[s.symbol] < s.price ? "flash-up" : prices[s.symbol] > s.price ? "flash-dn" : ""}"><td><b>${esc(s.symbol)}</b> <span class="fl" style="font-size:12px">${esc((s.name || "").slice(0, 28))}</span></td><td class="fl">${esc(s.sector)}</td><td class="num">${n(s.price)}</td><td class="num ${cls(s.change)}">${n(s.change)}</td><td class="num ${cls(s.change_pct)}">${pct(s.change_pct)}</td><td>${s.shariah ? '<span class="chip up">✓</span>' : ""}</td></tr>`).join("")}</tbody></table></div>${L.length > shown ? `<button class="btn" id="more" style="margin:14px auto;display:block">Show more (${L.length - shown} left)</button>` : ""}`;
    stocks.forEach(s => prices[s.symbol] = s.price);
    const mb = $("#more"); if (mb) { mb.onclick = () => { shown += 100; draw(); }; new IntersectionObserver(es => es[0].isIntersecting && mb.click(), { rootMargin: "500px" }).observe(mb); }
    document.querySelectorAll("th[data-k]").forEach(t => t.onclick = () => { sort = [t.dataset.k, sort[0] === t.dataset.k ? -sort[1] : 1]; draw(); });
  };
  v.innerHTML = `<div class="head"><div><h1>Markets</h1><div class="sub">${stocks.length} listed securities</div></div><div style="display:flex;gap:10px;flex-wrap:wrap"><input id="q" placeholder="Filter…"><div class="seg" id="f">${[["all", "All"], ["halal", "Halal"], ["up", "Gainers"], ["dn", "Losers"]].map(([k, l], i) => `<button data-f="${k}" class="${i ? "" : "on"}">${l}</button>`).join("")}</div><button class="btn" id="csv">⬇ CSV</button><div class="seg" id="m"><button data-m="table" class="on">Table</button><button data-m="heat">Heatmap</button></div></div></div><div id="mk"></div>`;
  $("#q").oninput = e => { q = e.target.value.toLowerCase(); shown = 100; draw(); };
  $("#f").onclick = e => { if (e.target.dataset.f) { filter = e.target.dataset.f; shown = 100; document.querySelectorAll("#f button").forEach(b => b.classList.toggle("on", b === e.target)); draw(); } };
  $("#m").onclick = e => { if (e.target.dataset.m) { mode = e.target.dataset.m; document.querySelectorAll("#m button").forEach(b => b.classList.toggle("on", b === e.target)); draw(); } };
  $("#csv").onclick = () => { const rows = [["Symbol", "Name", "Sector", "Price", "Change", "Change %", "Halal"], ...cur.map(s => [s.symbol, s.name, s.sector, s.price, s.change, s.change_pct, s.shariah ? "Yes" : "No"])];
    const b = new Blob([rows.map(r => r.map(x => `"${String(x ?? "").replace(/"/g, '""')}"`).join(",")).join("\n")], { type: "text/csv" }), a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "psx-markets.csv"; a.click(); URL.revokeObjectURL(a.href); };
  draw(); updateTape();
  return async () => { stocks = (await api("/stocks?limit=600"))?.data || stocks; draw(); };
}

const fd = x => x ? new Date(x).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "—";
const pdf = a => { const l = Array.isArray(a) ? a : a ? [a] : []; return l.find(x => /\.pdf(\?|$)/i.test(x)) || l[0] || ""; };
const docRow = (date, title, url, tag) => `<${url ? `a href="${esc(url)}" target="_blank" rel="noopener"` : 'div style="cursor:default"'} class="row">${tag || ""}<div style="flex:1"><div>${esc(title)}</div><div class="fl num" style="font-size:12px">${esc(date)}</div></div>${url ? '<span class="chip">📥 PDF</span>' : ""}</${url ? "a" : "div"}>`;

async function Stock(v, sym) {
  const [d, live, ins, rep, ann, wlr] = await Promise.all([api("/stocks/" + sym), api("/live/stock/" + sym), api("/live/insiders/" + sym), api("/live/reports/" + sym), api("/live/announcements/" + sym), api("/watchlist")]);
  if (!d) { v.innerHTML = `<div class="card empty">The server could not load ${esc(sym)} (see the terminal for the error). <br><br><button class="btn p" onclick="route(true)">Retry</button></div>`; return; }
  if (!d.stock) { v.innerHTML = `<div class="card empty">${esc(sym)} isn't in the current market list yet. If the server just started, wait a minute and retry.<br><br><button class="btn p" onclick="route(true)">Retry</button></div>`; return; }
  const s = d.stock, t = d.technical || {}, g = d.signal || {}, L = live?.data || {}, wl = wlr?.stocks?.some(x => x.symbol === sym), T = t.chart_data || [], bt = t.backtest;
  const arr = x => Array.isArray(x) ? x : [];
  const row = (r, k, f) => `<tr><td class="fl">${r}</td>${["BUY", "SELL", "HOLD"].map(x => `<td class="num">${f(bt[x])}</td>`).join("")}</tr>`;
  const edge = bt && bt.BUY.avg != null ? bt.BUY.avg - bt.baseline : null;
  v.innerHTML = `<div class="head"><div style="display:flex;gap:14px;align-items:center">${L.logo ? `<img src="${esc(L.logo)}" alt="" style="width:46px;height:46px;border-radius:12px;background:#fff;object-fit:contain;padding:4px" onerror="this.remove()">` : ""}<div><h1>${esc(sym)} <span class="chip">${esc(L.sectorName || s.sector)}</span> ${s.shariah ? '<span class="chip up">Halal</span>' : ""}</h1><div class="sub">${esc(s.name)}</div></div></div>
  <div style="display:flex;gap:10px;align-items:center"><div style="text-align:right"><div class="num" style="font-size:28px;font-weight:700">${n(s.price)}</div><div class="num ${cls(s.change_pct)}">${n(s.change)} (${pct(s.change_pct)})</div></div><button class="btn" id="wl">${wl ? "★ Watching" : "☆ Watch"}</button><a class="btn p" href="#/alerts/${esc(sym)}">+ Alert</a></div></div>
  <div class="grid g3"><div class="card"><h2>Price & volume <span class="seg" id="tf">${[[22, "1M"], [66, "3M"], [130, "6M"], [999, "1Y"]].map(([k, l], i) => `<button data-k="${k}" class="${i == 1 ? "on" : ""}">${l}</button>`).join("")}</span></h2>${T.length ? '<div class="cv"><canvas id="pc"></canvas></div>' : '<div class="empty">Price history could not be loaded for this symbol.</div>'}</div>
  <div class="card"><h2>Signal ${g.available ? sigChip(g.signal) : '<span class="chip">NO DATA</span>'}</h2>${g.available ? `<div class="split"><div><div class="fl">Confidence</div><b class="num">${g.confidence}%</b></div><div><div class="fl">Risk</div><b>${esc(g.risk_level)}</b></div><div><div class="fl">Target</div><b class="num up">${n(g.target_price)}</b></div><div><div class="fl">Stop</div><b class="num dn">${n(g.stop_loss)}</b></div></div><p class="sub" style="margin-top:12px">${esc(g.reasoning)}</p><p class="sub">${esc(g.technical_summary)}</p>
  <p class="fl" style="font-size:11.5px;margin-top:10px">Built from RSI, MACD, trend, Bollinger, volume and MA crosses, plus news tone. Not financial advice.</p>` : `<p class="sub">${esc(g.reasoning || "Not enough price history to compute indicators for this stock.")}</p>`}</div></div>
  ${bt ? `<div class="card" style="margin-top:16px"><h2>How has this signal performed on ${esc(sym)}? <span class="chip">${bt.days} days · ${bt.horizon}-day forward return</span></h2><div class="tw" style="max-height:none"><table><thead><tr><th></th><th>BUY days</th><th>SELL days</th><th>HOLD days</th></tr></thead><tbody>${row("Occurrences", 0, x => x.n)}${row("Avg return after", 0, x => x.avg == null ? "—" : `<span class="${cls(x.avg)}">${x.avg > 0 ? "+" : ""}${x.avg}%</span>`)}${row("Hit rate", 0, x => x.hit == null ? "—" : x.hit + "%")}</tbody></table></div>
  <p class="sub" style="margin-top:10px">Average ${bt.horizon}-day move on any day: <b class="num">${bt.baseline > 0 ? "+" : ""}${bt.baseline}%</b>. ${edge == null ? "" : edge > 0.5 ? `BUY signals beat that by ${edge.toFixed(1)} points on this stock.` : "BUY signals have shown no clear edge on this stock — treat the signal with caution."} Past results don't guarantee future ones.</p></div>` : ""}
  <div class="grid" style="margin-top:16px;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))">
  <div class="card"><h2>Indicators</h2>${t.rsi == null ? '<div class="empty">Not enough history</div>' : [["RSI (14)", t.rsi + " · " + (t.rsi_signal || "").replace(/_/g, " ")], ["MACD", (t.macd_cross || "").replace(/_/g, " ")], ["Trend", t.trend], ["Bollinger %B", t.bb_pct], ["Volume vs avg", t.volume_ratio + "×"], ["MA cross", (t.cross_signal || "none").replace(/_/g, " ")], ["Bars analysed", t.bars + " (to " + t.last_date + ")"]].map(([a, b]) => `<div class="lvl"><span class="fl">${a}</span><b class="num">${esc(b)}</b></div>`).join("")}</div>
  <div class="card"><h2>Levels</h2>${arr(t.resistances).map(x => `<div class="lvl"><span class="fl">Resistance</span><b class="num dn">${n(x)}</b></div>`).join("")}<div class="lvl"><span>Last</span><b class="num">${n(s.price)}</b></div>${arr(t.supports).map(x => `<div class="lvl"><span class="fl">Support</span><b class="num up">${n(x)}</b></div>`).join("")}${t.high52 ? `<div class="lvl"><span class="fl">52-week range</span><b class="num">${n(t.low52)} – ${n(t.high52)}</b></div>` : ""}</div>
  <div class="card"><h2>Performance & risk</h2>${t.perf ? [["1 month", t.perf.ret_1m, 1], ["3 months", t.perf.ret_3m, 1], ["6 months", t.perf.ret_6m, 1], ["1 year", t.perf.ret_1y, 1], ["Volatility (annual)", t.perf.volatility, 0], ["Max drawdown (1y)", t.perf.max_drawdown, 1]].map(([a, b, c]) => `<div class="lvl"><span class="fl">${a}</span><b class="num ${c && b != null ? cls(b) : ""}">${b == null ? "—" : (c && b > 0 ? "+" : "") + b + "%"}</b></div>`).join("") : '<div class="empty">Not enough history</div>'}</div>
  <div class="card"><h2>Sector peers <a class="chip" href="#/compare/${esc(sym)},${esc((arr(d.peers)[0] || {}).symbol || "")}">Compare →</a></h2>${arr(d.peers).map(rowS).join("") || '<div class="empty">No peers</div>'}</div>
  <div class="card"><h2>Payouts & board meetings</h2>${arr(d.announcements).map(a => docRow(fd(a.date), a.title + (a.advice ? " — " + a.advice : ""), a.link, `<span class="chip ${a.type === "dividend" ? "up" : a.type === "bonus" ? "am" : ""}">${esc((a.type_label || a.type).replace(/[^\w ]/g, "").trim())}</span>`)).join("") || '<div class="empty">None in the current window</div>'}</div></div>
  <div class="grid" style="margin-top:16px;grid-template-columns:repeat(auto-fit,minmax(380px,1fr))">
  <div class="card"><h2>Company announcements <span class="chip">12 months</span></h2>${arr(ann?.data).slice(0, 15).map(a => docRow(fd(a.postingDate), a.announcementTitle || "Announcement", pdf(a.attachments))).join("") || '<div class="empty">No announcements</div>'}</div>
  <div class="card"><h2>Financial reports</h2>${arr(rep?.data).map(r => docRow(`Period ${fd(r.periodEnded)} · posted ${fd(r.postingDate)}`, r.reportType || "Report", pdf(r.attachment))).join("") || '<div class="empty">No reports</div>'}</div></div>
  <div class="grid" style="margin-top:16px;grid-template-columns:repeat(auto-fit,minmax(380px,1fr))"><div class="card"><h2>Insider activity</h2>${arr(ins?.data).length ? `<div class="tw" style="max-height:340px"><table><thead><tr><th>Name</th><th>Action</th><th>Qty</th><th>Rate</th><th>Date</th></tr></thead><tbody>${arr(ins.data).slice(0, 15).map(i => `<tr style="cursor:default"><td title="${esc(i.position)}"><b>${esc(i.name)}</b><div class="fl" style="font-size:11px">${esc(i.position)}</div></td><td><span class="chip ${i.action === "Buy" ? "up" : "dn"}">${i.action === "Buy" ? "▲ BUY" : "▼ SELL"}</span></td><td class="num">${n(i.quantity, 0)}</td><td class="num">${n(i.rate)}</td><td class="num">${fd(i.date)}</td></tr>`).join("")}</tbody></table></div>` : '<div class="empty">No insider trades reported</div>'}</div>
  <div class="card"><h2>News</h2>${arr(d.news).map(x => docRow(x.source || "", x.title, x.link, `<span class="chip ${x.sentiment === "positive" ? "up" : x.sentiment === "negative" ? "dn" : ""}">${esc(x.sentiment)}</span>`)).join("") || '<div class="empty">No linked news</div>'}</div></div>`;
  $("#wl").onclick = async () => { await send("/watchlist/" + sym, wl ? "DELETE" : "POST"); route(true); };
  const draw = nb => { if (!T.length) return; charts.forEach(c => c.destroy()); charts = []; const k = T.slice(-nb), sl = a => (a || []).slice(-nb), ac = css("--ac");
    const g2 = $("#pc").getContext("2d").createLinearGradient(0, 0, 0, 300); g2.addColorStop(0, ac + "55"); g2.addColorStop(1, ac + "00");
    const ds = [{ type: "line", label: "Price", data: k.map(x => x.close), borderColor: ac, backgroundColor: g2, fill: true, tension: .25, pointRadius: 0, borderWidth: 2, order: 1 }];
    [[t.ma20_chart, "MA20", "#f5b942"], [t.ma50_chart, "MA50", "#a78bfa"]].forEach(([m, l, col]) => m?.length && ds.push({ type: "line", label: l, data: sl(m), borderColor: col, borderWidth: 1.3, pointRadius: 0, fill: false, tension: .25, order: 1 }));
    ds.push({ type: "bar", label: "Volume", data: k.map(x => x.volume), backgroundColor: css("--t3") + "55", yAxisID: "v", order: 2 });
    charts.push(new Chart($("#pc"), { data: { labels: k.map(x => x.date), datasets: ds }, options: { responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: "index" }, plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { position: "right", grid: { color: css("--bd") }, ticks: { color: css("--t3") } }, v: { display: false, max: Math.max(...k.map(x => x.volume), 1) * 4 } } } })); };
  draw(66);
  $("#tf").onclick = e => { const b = e.target.closest("button"); if (!b) return; document.querySelectorAll("#tf button").forEach(x => x.classList.toggle("on", x === b)); draw(+b.dataset.k); };
}

async function Watchlist(v) {
  let L = [];
  const draw = async () => { L = (await api("/watchlist"))?.stocks || [];
    v.innerHTML = `<div class="head"><div><h1>Watchlist</h1><div class="sub">${L.length} stocks · refreshes every 30 s</div></div><div class="form"><input id="wa" placeholder="Add symbol e.g. OGDC" style="width:190px"><button class="btn p" id="wb">Add</button></div></div>
    ${L.length ? `<div class="tw flow"><table><thead><tr><th>Symbol</th><th>Sector</th><th>Price</th><th>Chg %</th><th></th></tr></thead><tbody>${L.map(s => `<tr onclick="location.hash='#/stock/${esc(s.symbol)}'"><td><b>${esc(s.symbol)}</b> <span class="fl" style="font-size:12px">${esc((s.name || "").slice(0, 28))}</span></td><td class="fl">${esc(s.sector)}</td><td class="num">${n(s.price)}</td><td class="num ${cls(s.change_pct)}">${pct(s.change_pct)}</td><td><a class="btn" style="padding:3px 10px" href="#/alerts/${esc(s.symbol)}" onclick="event.stopPropagation()">🔔</a> <button class="btn d" data-rm="${esc(s.symbol)}" style="padding:3px 10px">✕</button></td></tr>`).join("")}</tbody></table></div>` : '<div class="card empty">Your watchlist is empty. Use “☆ Watch” on any stock page, or add a symbol above.</div>'}`;
    $("#wb").onclick = async () => { const x = $("#wa").value.trim().toUpperCase(); if (x) { await send("/watchlist/" + x, "POST"); draw(); } };
    $("#wa").onkeydown = e => e.key === "Enter" && $("#wb").click();
    v.querySelectorAll("[data-rm]").forEach(b => b.onclick = async e => { e.stopPropagation(); await send("/watchlist/" + b.dataset.rm, "DELETE"); draw(); }); };
  await draw(); return async () => { if (!document.activeElement || document.activeElement.tagName !== "INPUT") await draw(); };
}

async function Portfolio(v) {
  const [p, adv, ph] = await Promise.all([api("/portfolio"), api("/portfolio/advice"), api("/portfolio/history")]); const S = p?.summary || {}, H = p?.holdings || [], A = adv?.advice || {};
  v.innerHTML = `<div class="head"><div><h1>Portfolio</h1><div class="sub">${S.num_holdings || 0} holdings</div></div></div>
  <div class="grid g4">${kpi("Value", "₨ " + n(S.total_current, 0), S.total_pnl_pct, "all-time")}${kpi("Invested", "₨ " + n(S.total_invested, 0), 0)}${kpi("P&L", "₨ " + n(S.total_pnl, 0), S.total_pnl_pct)}<div class="card kpi"><div class="lbl">Health score</div><div class="val num">${A.health_score ?? "—"}</div><div class="fl">${esc(A.overall_health || "")}</div></div></div>
  <div class="grid g3" style="margin-top:16px"><div class="card"><h2>Performance <span class="chip">daily snapshots</span></h2><div class="cv"><canvas id="pf"></canvas></div></div><div class="card"><h2>Allocation</h2><div class="cv"><canvas id="al"></canvas></div></div></div><div class="card" style="margin-top:16px"><h2>Add / update holding</h2><div class="form"><input id="hs" placeholder="Symbol"><input id="hn" type="number" placeholder="Shares"><input id="hp" type="number" step="any" placeholder="Buy price"><button class="btn p" id="ha">Save</button></div></div>
  <div class="tw" style="margin-top:16px"><table><thead><tr><th>Symbol</th><th>Shares</th><th>Avg cost</th><th>Price</th><th>Value</th><th>P&L</th><th>Action</th><th></th></tr></thead><tbody>${H.map(h => { const ac = (A.actions || []).find(x => x.symbol === h.symbol); return `<tr onclick="location.hash='#/stock/${esc(h.symbol)}'"><td><b>${esc(h.symbol)}</b></td><td class="num">${n(h.shares, 0)}</td><td class="num">${n(h.buy_price)}</td><td class="num">${n(h.current_price)}</td><td class="num">${n(h.current_value, 0)}</td><td class="num ${cls(h.pnl)}">${n(h.pnl, 0)} (${pct(h.pnl_pct)})</td><td>${ac ? `<span class="chip am" title="${esc(ac.reason)}">${esc(ac.action)}</span>` : ""}</td><td><button class="btn d" data-rm="${esc(h.symbol)}">✕</button></td></tr>`; }).join("") || '<tr><td colspan=8 class="empty">No holdings yet</td></tr>'}</tbody></table></div>
  <div class="card" style="margin-top:16px"><h2>Advice</h2><p>${esc(A.summary)}</p><p class="sub">${esc(A.diversification_tip || "")} ${esc(A.risk_warning || "")}</p></div>`;
  const hist = ph?.data || [];
  if (hist.length) { spark($("#pf"), hist.map(x => x.date), hist.map(x => x.value), css("--ac")); charts[0].data.datasets.push({ data: hist.map(x => x.invested), borderColor: css("--t3"), borderDash: [5, 4], borderWidth: 1.5, pointRadius: 0, fill: false }); charts[0].update(); }
  else $("#pf").parentNode.innerHTML = '<div class="empty">The chart fills in as the server records a snapshot each day.</div>';
  const live = H.filter(h => h.current_value);
  if (live.length) charts.push(new Chart($("#al"), { type: "doughnut", data: { labels: live.map(h => h.symbol), datasets: [{ data: live.map(h => h.current_value), borderWidth: 0, backgroundColor: ["#4f8cff", "#19c37d", "#f5b942", "#a78bfa", "#ff5470", "#22d3ee", "#fb923c", "#94a3b8"] }] }, options: { responsive: true, maintainAspectRatio: false, cutout: "68%", plugins: { legend: { position: "right", labels: { color: css("--t2"), boxWidth: 10 } } } } }));
  $("#ha").onclick = async () => { await send("/portfolio/add", "POST", { symbol: $("#hs").value, shares: +$("#hn").value, buy_price: +$("#hp").value }); route(true); };
  v.querySelectorAll("[data-rm]").forEach(b => b.onclick = async e => { e.stopPropagation(); await send("/portfolio/" + b.dataset.rm, "DELETE"); route(true); });
}

async function Corporate(v) {
  const [d, a] = await Promise.all([api("/dividends"), api("/announcements")]); let tab = "div", q = "";
  const card = x => `<div class="card hov"><div style="display:flex;justify-content:space-between;gap:8px"><a href="#/stock/${esc(x.symbol)}"><b>${esc(x.symbol)}</b></a><span class="chip ${x.type === "dividend" ? "up" : x.type === "bonus" ? "am" : ""}">${esc((x.type_label || x.type).replace(/[^\w ]/g, "").trim())}</span></div><p style="margin:8px 0">${esc(x.title)}</p><p class="sub">${esc(x.advice)}</p><div style="display:flex;justify-content:space-between;align-items:center;margin-top:10px"><span class="fl num" style="font-size:12px">${esc(x.date)}</span>${x.link ? `<a class="btn p" style="padding:5px 12px" href="${esc(x.link)}" target="_blank" rel="noopener">📥 Download PDF</a>` : ""}</div></div>`;
  const draw = () => { const L = ((tab === "div" ? d?.data : a?.data) || []).filter(x => (x.symbol + " " + x.title + " " + x.type + " " + (x.account_type || "")).toLowerCase().includes(q)).sort((p, r) => String(r.date).localeCompare(String(p.date)));
    $("#cn").textContent = L.length + " shown"; $("#cl").innerHTML = L.length ? L.map(card).join("") : '<div class="card empty" style="grid-column:1/-1">No matches.</div>'; };
  v.innerHTML = `<div class="head"><div><h1>Corporate actions</h1><div class="sub">Last 30 days and the next 45 · <span id="cn"></span></div></div><div style="display:flex;gap:10px;flex-wrap:wrap"><input id="cq" placeholder="Search symbol or keyword…" style="min-width:230px"><div class="seg" id="ct"><button data-t="div" class="on">Payouts</button><button data-t="ann">Results & meetings</button></div></div></div><div class="grid" id="cl" style="grid-template-columns:repeat(auto-fill,minmax(320px,1fr))"></div>`;
  $("#cq").oninput = e => { q = e.target.value.toLowerCase().trim(); draw(); };
  $("#ct").onclick = e => { if (e.target.dataset.t) { tab = e.target.dataset.t; document.querySelectorAll("#ct button").forEach(b => b.classList.toggle("on", b === e.target)); draw(); } }; draw();
}

async function Compare(v, arg) {
  if (!stocks.length) stocks = (await api("/stocks?limit=600"))?.data || [];
  const cols = ["#4f8cff", "#19c37d", "#f5b942", "#ff5470", "#a78bfa"];
  let sel = (arg || "").split(",").map(x => x.trim().toUpperCase()).filter(x => stocks.some(s => s.symbol === x)).slice(0, 5), hi = 0, opts = [], tok = 0;
  v.innerHTML = `<div class="head"><div><h1>Compare</h1><div class="sub">Pick 2–5 stocks. Search by symbol or company name.</div></div></div>
  <div class="card cmp-box"><div class="cmp-field"><span id="chips"></span><input id="cs" placeholder="Type a symbol or company name…" autocomplete="off" spellcheck="false"></div><div class="cmp-dd" id="dd" hidden></div></div><div id="cr" style="margin-top:16px"></div>`;
  const cs = $("#cs"), dd = $("#dd");
  const chips = () => { $("#chips").innerHTML = sel.map((s, i) => `<span class="cchip" style="--c:${cols[i]}">${esc(s)}<button data-x="${esc(s)}" title="Remove">✕</button></span>`).join(""); };
  const sync = () => history.replaceState(null, "", "#/compare" + (sel.length ? "/" + sel.join(",") : ""));
  const menu = () => {
    const q = cs.value.trim().toLowerCase();
    opts = stocks.filter(s => !sel.includes(s.symbol) && (!q || (s.symbol + " " + (s.name || "")).toLowerCase().includes(q)))
      .sort((a, b) => q ? (b.symbol.toLowerCase().startsWith(q) - a.symbol.toLowerCase().startsWith(q)) || a.symbol.localeCompare(b.symbol) : Math.abs(b.change_pct) - Math.abs(a.change_pct)).slice(0, 8);
    hi = Math.min(hi, Math.max(0, opts.length - 1));
    dd.hidden = false;
    dd.innerHTML = opts.map((s, i) => `<div class="ci ${i === hi ? "on" : ""}" data-s="${esc(s.symbol)}"><b>${esc(s.symbol)}</b><span class="fl" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(s.name || "")}</span><small class="num">${n(s.price)} <span class="${cls(s.change_pct)}">${pct(s.change_pct)}</span></small></div>`).join("") || '<div class="empty" style="padding:16px">No matching stocks</div>';
  };
  const add = sym => { if (!sym || sel.includes(sym)) return; if (sel.length >= 5) { toast("You can compare up to 5 stocks."); return; } sel.push(sym); cs.value = ""; hi = 0; chips(); sync(); load(); menu(); cs.focus(); };
  cs.oninput = () => { hi = 0; menu(); };
  cs.onfocus = menu;
  cs.onblur = () => setTimeout(() => dd.hidden = true, 120);
  cs.onkeydown = e => {
    if (e.key === "ArrowDown") { hi = Math.min(opts.length - 1, hi + 1); menu(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { hi = Math.max(0, hi - 1); menu(); e.preventDefault(); }
    else if (e.key === "Enter") { const exact = stocks.find(s => s.symbol === cs.value.trim().toUpperCase()); add(opts[hi]?.symbol || exact?.symbol); e.preventDefault(); }
    else if (e.key === "Backspace" && !cs.value && sel.length) { sel.pop(); chips(); sync(); load(); menu(); }
    else if (e.key === "Escape") dd.hidden = true;
  };
  dd.onmousedown = e => { e.preventDefault(); const it = e.target.closest("[data-s]"); if (it) add(it.dataset.s); };
  $("#chips").onclick = e => { const b = e.target.closest("[data-x]"); if (b) { sel = sel.filter(x => x !== b.dataset.x); chips(); sync(); load(); cs.focus(); } };

  const load = async () => {
    const my = ++tok; kill();
    if (sel.length < 2) { $("#cr").innerHTML = '<div class="card empty">Add at least two stocks to compare performance, indicators and signals.</div>'; return; }
    $("#cr").innerHTML = '<div class="skel" style="height:340px"></div>';
    const parts = []; for (let i = 0; i < sel.length; i += 3) parts.push(sel.slice(i, i + 3));
    const D = (await Promise.all(parts.map(p => api("/compare?symbols=" + p.join(","))))).flatMap(r => r?.data || []).sort((a, b) => sel.indexOf(a.stock.symbol) - sel.indexOf(b.stock.symbol));
    if (my !== tok) return;
    if (D.length < 2) { $("#cr").innerHTML = '<div class="card empty">Could not load data for these stocks. Try again in a moment.</div>'; return; }
    const P = x => x.tech.perf || {}, R = (k, up) => x => P(x)[k] == null ? "—" : `<span class="${up ? cls(P(x)[k]) : ""}">${up && P(x)[k] > 0 ? "+" : ""}${P(x)[k]}%</span>`;
    const rows = [["Price", x => n(x.stock.price)], ["Today", x => pct(x.stock.change_pct)], ["Sector", x => esc(x.stock.sector)], ["Halal", x => x.stock.shariah ? "Yes" : "No"],
      ["1 month", R("ret_1m", 1)], ["3 months", R("ret_3m", 1)], ["1 year", R("ret_1y", 1)], ["Volatility (annual)", R("volatility", 0)], ["Max drawdown", R("max_drawdown", 1)],
      ["RSI", x => x.tech.rsi ?? "—"], ["Trend", x => esc(x.tech.trend || "—")], ["MACD", x => esc((x.tech.macd_cross || "—").replace(/_/g, " "))], ["Bollinger %B", x => x.tech.bb_pct ?? "—"], ["Signal", x => sigChip(x.tech.tech_signal)]];
    const withS = D.filter(x => x.series.length > 1), N = withS.length ? Math.min(...withS.map(x => x.series.length)) : 0;
    $("#cr").innerHTML = `<div class="card"><h2>Performance ${N ? `<span class="chip">rebased to 100 · last ${N} trading days</span>` : ""}</h2>${N ? '<div class="cv"><canvas id="cc"></canvas></div>' : '<div class="empty">Not enough price history to draw the chart.</div>'}</div>
    <div class="tw flow" style="margin-top:16px"><table><thead><tr><th></th>${D.map(x => `<th><a href="#/stock/${esc(x.stock.symbol)}" style="color:${cols[sel.indexOf(x.stock.symbol)]}">${esc(x.stock.symbol)}</a></th>`).join("")}</tr></thead><tbody>${rows.map(([l, f]) => `<tr style="cursor:default"><td class="fl">${l}</td>${D.map(x => `<td class="num">${f(x)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    if (N) charts.push(new Chart($("#cc"), { type: "line", data: { labels: withS[0].dates.slice(-N), datasets: withS.map(x => { const s = x.series.slice(-N); return { label: x.stock.symbol, data: s.map(c => +(c / s[0] * 100).toFixed(2)), borderColor: cols[sel.indexOf(x.stock.symbol)], borderWidth: 2, pointRadius: 0, tension: .25 }; }) },
      options: { responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: "index" }, plugins: { legend: { labels: { color: css("--t2"), usePointStyle: true } } }, scales: { x: { display: false }, y: { grid: { color: css("--bd") }, ticks: { color: css("--t3") } } } } }));
  };
  chips(); load(); if (!sel.length) cs.focus();
}

async function Alerts(v, pre) {
  const [a, t] = await Promise.all([api("/alerts"), api("/alerts/triggered")]); const A = a?.data || [], T = t?.data || [];
  v.innerHTML = `<div class="head"><div><h1>Alerts</h1><div class="sub">Checked every 30 seconds on the server</div></div></div>
  <div class="card"><h2>New alert</h2><div class="form"><input id="as" placeholder="Symbol" value="${esc(pre || "")}" style="width:110px"><select id="at"><option value="price_above">Price ≥</option><option value="price_below">Price ≤</option><option value="percent_move">Day move ±%</option><option value="signal_change">Signal turns bullish</option></select><input id="av" type="number" step="any" placeholder="Value"><button class="btn p" id="ab">Create</button></div></div>
  <div class="grid g2" style="margin-top:16px"><div class="card"><h2>Active</h2>${A.filter(x => !x.triggered).map(x => `<div class="row" style="cursor:default"><b>${esc(x.symbol)}</b><span class="fl">${esc(x.type.replace("_", " "))} ${x.target_value || ""}</span><button class="btn d r" data-d="${x.id}">✕</button></div>`).join("") || '<div class="empty">None</div>'}</div>
  <div class="card"><h2>Triggered <button class="chip" id="cl">Clear</button></h2>${T.slice().reverse().map(x => `<div class="row" style="cursor:default"><span>${esc(x.message)}</span></div>`).join("") || '<div class="empty">None yet</div>'}</div></div>`;
  $("#ab").onclick = async () => { const ty = $("#at").value; await send("/alerts", "POST", { symbol: $("#as").value, type: ty, condition: ty === "signal_change" ? "bullish" : ty.replace("price_", ""), target_value: +$("#av").value || 0 }); route(true); };
  v.querySelectorAll("[data-d]").forEach(b => b.onclick = async () => { await send("/alerts/" + b.dataset.d, "DELETE"); route(true); });
  $("#cl").onclick = async () => { await send("/alerts/triggered/clear", "DELETE"); route(true); };
}

/* ── ticker tape, command palette, alert polling ── */
async function updateTape() {
  const r = await api("/stocks?limit=600"); stocks = r?.data || stocks; if (!stocks.length) return;
  const top = [...stocks].sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct)).slice(0, 24);
  const h = top.map(s => `<a class="tk" href="#/stock/${esc(s.symbol)}"><b>${esc(s.symbol)}</b><span class="num">${n(s.price)}</span><span class="num ${cls(s.change_pct)}">${pct(s.change_pct)}</span></a>`).join("");
  $("#tape").innerHTML = h + h;
}
const cmd = $("#cmd"), cin = $("#cmd-in"); let sel = 0;
function cmdDraw() {
  const q = cin.value.toLowerCase(), pages = ROUTES.filter(r => r[1].toLowerCase().includes(q)).map(r => ({ l: r[1], s: "Page", h: "#/" + r[0] }));
  const st = q ? stocks.filter(s => (s.symbol + " " + s.name).toLowerCase().includes(q)).slice(0, 8).map(s => ({ l: s.symbol + " · " + (s.name || ""), s: n(s.price), h: "#/stock/" + s.symbol })) : [];
  const L = [...st, ...pages].slice(0, 10); sel = Math.min(sel, Math.max(0, L.length - 1));
  $("#cmd-list").innerHTML = L.map((x, i) => `<div class="ci ${i === sel ? "on" : ""}" data-h="${esc(x.h)}">${esc(x.l)}<small>${esc(x.s)}</small></div>`).join("") || '<div class="empty">No matches</div>';
}
const openCmd = () => { cmd.hidden = false; cin.value = ""; sel = 0; cmdDraw(); cin.focus(); }, closeCmd = () => cmd.hidden = true;
$("#open-cmd").onclick = openCmd; cmd.onclick = e => { if (e.target === cmd) closeCmd(); if (e.target.closest(".ci")) { location.hash = e.target.closest(".ci").dataset.h; closeCmd(); } };
cin.oninput = () => { sel = 0; cmdDraw(); };
addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && e.key === "k") { e.preventDefault(); openCmd(); } else if (e.key === "Escape") closeCmd();
  else if (!cmd.hidden && (e.key === "ArrowDown" || e.key === "ArrowUp")) { sel = Math.max(0, sel + (e.key === "ArrowDown" ? 1 : -1)); cmdDraw(); e.preventDefault(); }
  else if (!cmd.hidden && e.key === "Enter") { const x = $(".ci.on"); if (x) location.hash = x.dataset.h; else if (/^[A-Za-z0-9]{2,10}$/.test(cin.value.trim())) location.hash = "#/stock/" + cin.value.trim().toUpperCase(); closeCmd(); }
});
let seen = new Set();
async function pollAlerts() {
  const st = await api("/status");
  if (st) { $("#status").textContent = (st.market_open ? "Market open" : "Market closed") + (st.status === "loading" ? " · loading…" : ""); $("#dot").className = "dot" + (st.market_open ? " live" : ""); }
  else { $("#status").textContent = "Server offline"; $("#dot").className = "dot"; }
  const t = await api("/alerts/triggered"); const L = t?.data || [];
  L.forEach(x => { const k = x.id + x.triggered_at; if (!seen.has(k)) { if (seen.size || sessionStorage.getItem("psx-init")) toast("🔔 " + esc(x.message)); seen.add(k); } });
  sessionStorage.setItem("psx-init", "1"); $("#badge").hidden = !L.length; $("#badge").textContent = L.length;
}
route(); updateTape(); pollAlerts(); setInterval(pollAlerts, 30000); setInterval(updateTape, 60000);

let _st; addEventListener("scroll", () => { document.body.classList.add("scrolling"); clearTimeout(_st); _st = setTimeout(() => document.body.classList.remove("scrolling"), 120); }, { passive: true });