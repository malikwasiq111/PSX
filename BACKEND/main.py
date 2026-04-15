from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import threading
import time
from datetime import datetime

from scraper import get_all_stocks, get_kse100, get_pkr_usd, PSX_STOCKS
from news import fetch_all_news
from ai_analysis import analyze_single_stock, analyze_overall_market
from dividends import scrape_psx_announcements, get_parsed_dividends, get_stock_fundamentals, get_stock_dividends
from technical import get_technical_analysis
from portfolio import (
    calculate_portfolio, get_ai_portfolio_advice,
    add_holding, remove_holding, get_holdings
)

class HoldingInput(BaseModel):
    symbol:    str
    shares:    float
    buy_price: float
    buy_date:  Optional[str] = None

app = FastAPI(title="PSX AI Analyst", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory cache (refreshed every 30s) ──────────────────────────────────
cache = {
    "stocks":          [],
    "news":            [],
    "kse100":          None,
    "pkr":             None,
    "market_analysis": None,
    "dividends":       [],
    "last_updated":    None,
    "is_loading":      True,
}

stock_signals        = {}   # symbol -> AI signal (refreshed every 5 min)
signal_last_refresh  = {}
technical_cache      = {}   # symbol -> technical data (refreshed every 10 min)
tech_last_refresh    = {}
dividend_last_scrape = 0    # timestamp


def refresh_loop():
    """Background thread: refresh market data every 30 seconds."""
    global dividend_last_scrape
    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Refreshing data...")

            stocks = get_all_stocks()
            news   = fetch_all_news()
            kse    = get_kse100()
            pkr    = get_pkr_usd()
            market = analyze_overall_market(news, kse, pkr)

            cache["stocks"]          = stocks
            cache["news"]            = news
            cache["kse100"]          = kse
            cache["pkr"]             = pkr
            cache["market_analysis"] = market
            cache["last_updated"]    = datetime.now().isoformat()
            cache["is_loading"]      = False

            # Scrape dividends every 5 minutes
            now = time.time()
            if now - dividend_last_scrape > 300:
                scrape_psx_announcements()
                cache["dividends"] = get_parsed_dividends()
                dividend_last_scrape = now
                print(f"  -> Dividends refreshed: {len(cache['dividends'])} found")

            print(f"  -> {len(stocks)} stocks | {len(news)} news | "
                  f"KSE: {kse.get('value') if kse else 'N/A'} | "
                  f"Market: {market.get('overall_sentiment') if market else 'N/A'}")

        except Exception as e:
            print(f"Refresh error: {e}")
            import traceback
            traceback.print_exc()

        time.sleep(30)


# Start background thread immediately
t = threading.Thread(target=refresh_loop, daemon=True)
t.start()


# ── API Endpoints ───────────────────────────────────────────────────────────

@app.get("/api/status")
def status():
    return {
        "status":        "running",
        "stocks_loaded": len(cache["stocks"]),
        "news_loaded":   len(cache["news"]),
        "is_loading":    cache["is_loading"],
        "last_updated":  cache["last_updated"],
        "total_tracked": len(PSX_STOCKS),
    }


@app.get("/api/market")
def market():
    """Overall market data: KSE-100, USD/PKR, AI market analysis."""
    return {
        "kse100":          cache["kse100"],
        "pkr":             cache["pkr"],
        "market_analysis": cache["market_analysis"],
        "last_updated":    cache["last_updated"],
    }


@app.get("/api/stocks")
def stocks(sector: str = None, shariah_only: bool = False):
    """All stocks. Optional filters: sector, shariah_only."""
    data = cache["stocks"]
    if sector:
        data = [s for s in data if s.get("sector", "").lower() == sector.lower()]
    if shariah_only:
        data = [s for s in data if s.get("shariah")]
    return {"data": data, "count": len(data), "last_updated": cache["last_updated"]}


@app.get("/api/stocks/{symbol}")
def stock_detail(symbol: str):
    """Single stock detail + AI signal + technical analysis + dividends."""
    symbol = symbol.upper()
    stock = next((s for s in cache["stocks"] if s["symbol"] == symbol), None)
    if not stock:
        return {"error": f"Stock {symbol} not found"}

    # ── Technical Analysis (cached 10 min) ──
    now = time.time()
    tech_data = None
    last_tech = tech_last_refresh.get(symbol, 0)
    if now - last_tech > 600 or symbol not in technical_cache:
        info = PSX_STOCKS.get(symbol)
        if info:
            print(f"Computing technicals for {symbol}...")
            tech_data = get_technical_analysis(symbol, info["ticker"])
            if tech_data:
                technical_cache[symbol] = tech_data
                tech_last_refresh[symbol] = now
    else:
        tech_data = technical_cache.get(symbol)

    # ── Fundamentals from sarmaaya.pk ──
    fundamentals = get_stock_fundamentals(symbol)

    # ── AI Signal (cached 5 min) ──
    last_refresh = signal_last_refresh.get(symbol, 0)
    if now - last_refresh > 300 or symbol not in stock_signals:
        print(f"Generating AI signal for {symbol}...")
        stock_signals[symbol] = analyze_single_stock(
            symbol, stock, cache["news"],
            technical=tech_data,
            fundamentals=fundamentals
        )
        signal_last_refresh[symbol] = now

    # ── Related News ──
    related_news = [n for n in cache["news"] if symbol in n.get("related_stocks", [])]

    # ── Dividends for this stock ──
    stock_divs = get_stock_dividends(symbol)

    return {
        "stock":        stock,
        "signal":       stock_signals.get(symbol),
        "technical":    tech_data,
        "fundamentals": fundamentals if fundamentals else None,
        "dividends":    stock_divs[:5],
        "related_news": related_news[:8],
        "last_updated": cache["last_updated"],
    }


@app.get("/api/technical/{symbol}")
def technical_endpoint(symbol: str):
    """Get technical analysis for a specific stock."""
    symbol = symbol.upper()
    info = PSX_STOCKS.get(symbol)
    if not info:
        return {"error": f"Stock {symbol} not found"}

    now = time.time()
    if symbol in technical_cache and (now - tech_last_refresh.get(symbol, 0)) < 600:
        return {"data": technical_cache[symbol], "cached": True}

    tech = get_technical_analysis(symbol, info["ticker"])
    if tech:
        technical_cache[symbol] = tech
        tech_last_refresh[symbol] = now
        return {"data": tech, "cached": False}

    return {"error": "Could not compute technical analysis", "data": None}


@app.get("/api/news")
def news(sentiment: str = None, stock: str = None):
    """All news. Optional filters: sentiment, stock symbol."""
    data = cache["news"]
    if sentiment:
        data = [n for n in data if n.get("sentiment") == sentiment.lower()]
    if stock:
        data = [n for n in data if stock.upper() in n.get("related_stocks", [])]
    return {"data": data, "count": len(data), "last_updated": cache["last_updated"]}


@app.get("/api/sectors")
def sectors():
    """Sector summary with average change."""
    sector_map = {}
    for s in cache["stocks"]:
        sec = s.get("sector", "Other")
        if sec not in sector_map:
            sector_map[sec] = {"stocks": [], "changes": []}
        sector_map[sec]["stocks"].append(s["symbol"])
        sector_map[sec]["changes"].append(s.get("change_pct", 0))

    result = []
    for sec, data in sector_map.items():
        avg_change = sum(data["changes"]) / len(data["changes"]) if data["changes"] else 0
        result.append({
            "sector":      sec,
            "stocks":      data["stocks"],
            "stock_count": len(data["stocks"]),
            "avg_change":  round(avg_change, 2),
            "trend":       "up" if avg_change > 0 else "down" if avg_change < 0 else "flat",
        })

    result.sort(key=lambda x: x["avg_change"], reverse=True)
    return {"data": result}


@app.get("/api/dividends")
def dividends():
    """All recent PSX dividend announcements."""
    return {
        "data":         cache["dividends"],
        "count":        len(cache["dividends"]),
        "last_updated": cache["last_updated"],
    }


@app.get("/api/dividends/{symbol}")
def dividends_for_symbol(symbol: str):
    """Dividend history for a specific stock."""
    symbol = symbol.upper()
    data = get_stock_dividends(symbol)
    return {"symbol": symbol, "data": data}


# ── Portfolio Endpoints ───────────────────────────────────────────────────────

@app.get("/api/portfolio")
def portfolio():
    """Get full portfolio with live P&L calculation."""
    calc = calculate_portfolio(cache["stocks"])
    return calc


@app.get("/api/portfolio/advice")
def portfolio_advice():
    """Get AI advice for current portfolio."""
    calc   = calculate_portfolio(cache["stocks"])
    advice = get_ai_portfolio_advice(calc, cache["news"])
    return {"advice": advice, "portfolio": calc}


@app.post("/api/portfolio/add")
def portfolio_add(holding: HoldingInput):
    """Add or update a holding."""
    result = add_holding(
        symbol    = holding.symbol,
        shares    = holding.shares,
        buy_price = holding.buy_price,
        buy_date  = holding.buy_date,
    )
    return {"success": True, "holding": result}


@app.delete("/api/portfolio/{symbol}")
def portfolio_remove(symbol: str):
    """Remove a holding by symbol."""
    success = remove_holding(symbol.upper())
    return {"success": success, "symbol": symbol.upper()}


# ── Serve frontend ────────────────────────────────────────────────────────
app.mount("/", StaticFiles(directory="../FRoNTEND", html=True), name="static")