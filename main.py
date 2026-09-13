"""
PSX AI Analyst — FastAPI Backend v5.0
Full stack with indices, pagination, announcements, portfolio, alerts
"""

import os
import threading
import time
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# ── Imports ───────────────────────────────────────────────────────────────────
from scraper import (
    get_all_stocks, get_kse100, get_kmi30, get_pkr_usd, get_sectors_live,
    get_index_top_contributors, get_index_price_history, is_psx_market_open,
    get_index_stocks, SECTOR_MAP
)
from news import fetch_all_news
from ai_analysis import analyze_single_stock, analyze_overall_market
from announcements import (
    refresh_announcements, get_all_announcements,
    get_dividends, get_announcements_for_symbol,
    get_announcements_by_type
)
from technical import get_technical_analysis
from portfolio import (
    calculate_portfolio, get_ai_portfolio_advice,
    add_holding, remove_holding, get_holdings
)
from alerts import (
    add_alert, get_alerts, delete_alert,
    get_triggered_alerts, check_alerts, clear_triggered
)


# ════════════════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ════════════════════════════════════════════════════════════════════════════════

class HoldingInput(BaseModel):
    symbol:    str
    shares:    float
    buy_price: float
    buy_date:  Optional[str] = None


class AlertInput(BaseModel):
    symbol:        str
    type:          str
    condition:     str
    target_value:  float
    note:          Optional[str] = ""


# ════════════════════════════════════════════════════════════════════════════════
# APP SETUP
# ════════════════════════════════════════════════════════════════════════════════

app = FastAPI(title="PSX AI Analyst", version="5.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


# ════════════════════════════════════════════════════════════════════════════════
# GLOBAL CACHE
# ════════════════════════════════════════════════════════════════════════════════

cache = {
    "stocks":                [],
    "news":                  [],
    "kse100":                None,
    "kmi30":                 None,
    "pkr":                   None,
    "market_analysis":       None,
    "announcements":         [],
    "dividends":             [],
    "sectors":               [],
    "kse100_contributors":   [],
    "kmi30_contributors":    [],
    "kse100_history":        [],
    "kmi30_history":         [],
    "kse100_stocks":         [],   # symbols in KSE100
    "kmi30_stocks":          [],   # symbols in KMI30
    "newly_triggered":       [],
    "last_updated":          None,
    "is_loading":            True,
}

stock_signals     = {}
signal_last_ref   = {}
technical_cache   = {}
tech_last_ref     = {}
ann_last_scrape   = 0
watchlist         = set()
index_cache_time  = 0


# ════════════════════════════════════════════════════════════════════════════════
# BACKGROUND REFRESH LOOP
# ════════════════════════════════════════════════════════════════════════════════

def refresh_loop():
    """
    Background thread that refreshes all market data every 30 seconds.
    - Stocks (paginated — all ~496)
    - Indices (KSE100, KMI30)
    - News
    - Announcements (every 5 min)
    - Technical signals
    - Alerts
    """
    global ann_last_scrape, index_cache_time

    print("🚀 Starting refresh loop...")

    while True:
        try:
            now = time.time()
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Refresh cycle...")

            # ── Stocks (ALL ~496 via pagination) ─────────────────────────
            stocks_data = get_all_stocks()
            stocks = stocks_data.get("stocks", [])
            total_stocks = stocks_data.get("total", 0)

            # ── Indices ───────────────────────────────────────────────────
            kse100 = get_kse100()
            kmi30  = get_kmi30()
            pkr    = get_pkr_usd()

            # ── News ──────────────────────────────────────────────────────
            news = fetch_all_news()

            # ── Market Analysis ───────────────────────────────────────────
            market_analysis = analyze_overall_market(news, kse100, pkr)

            # ── Sectors ───────────────────────────────────────────────────
            sectors = get_sectors_live()

            # Attach stocks to sectors
            for sec in sectors:
                sec_name = sec.get("sector", "").lower()
                sec["stocks"] = [
                    s["symbol"] for s in stocks
                    if s.get("sector", "").lower() == sec_name
                ]

            # ── Index Stocks + Contributors & History (every 5 min) ──────
            if now - index_cache_time > 300:
                print("  📊 Fetching index stocks, contributors & history...")
                
                # Fetch KSE100 and KMI30 constituent stocks
                kse100_stock_list = get_index_stocks("KSE100")
                kmi30_stock_list  = get_index_stocks("KMI30")
                
                kse100_contrib = get_index_top_contributors("KSE100", 10)
                kmi30_contrib  = get_index_top_contributors("KMI30", 10)
                kse100_hist    = get_index_price_history("KSE100", 30)
                kmi30_hist     = get_index_price_history("KMI30", 30)
                
                cache.update({
                    "kse100_stocks":       kse100_stock_list,
                    "kmi30_stocks":        kmi30_stock_list,
                    "kse100_contributors": kse100_contrib,
                    "kmi30_contributors":  kmi30_contrib,
                    "kse100_history":      kse100_hist,
                    "kmi30_history":       kmi30_hist,
                })
                index_cache_time = now

            # ── Announcements (every 5 min) ───────────────────────────
            if now - ann_last_scrape > 300:
               print("  📰 Fetching announcements...")
               refresh_announcements()
               cache["announcements"] = get_announcements_by_type("board") + get_announcements_by_type("results")
               cache["dividends"] = get_dividends()
               ann_last_scrape = now

            # ── Technical Analysis ────────────────────────────────────
            if now - tech_last_ref.get("time", 0) > 300:
                print("  📈 Computing technical indicators...")
                # Sample top 20 stocks fsor technical analysis
                for stock in stocks[:20]:
                    try:
                        tech = get_technical_analysis(stock["symbol"])
                        if tech:
                            technical_cache[stock["symbol"]] = tech
                            stock_signals[stock["symbol"]] = tech.get("tech_signal", "HOLD")
                    except:
                        pass
                tech_last_ref["time"] = now

            # ── Alerts ────────────────────────────────────────────────
            triggered = check_alerts(stocks, stock_signals)
            if triggered:
                cache["newly_triggered"].extend(triggered)
                cache["newly_triggered"] = cache["newly_triggered"][-20:]

            # ── Update Cache ──────────────────────────────────────────
            cache.update({
                "stocks":          stocks,
                "news":            news,
                "kse100":          kse100,
                "kmi30":           kmi30,
                "pkr":             pkr,
                "market_analysis": market_analysis,
                "sectors":         sectors,
                "last_updated":    datetime.now().isoformat(),
                "is_loading":      False,
            })

            # ── Summary ───────────────────────────────────────────────
            kse_val = kse100.get('value', '?') if kse100 else '?'
            kse_pct = kse100.get('change_pct', 0) if kse100 else 0
            kmi_val = kmi30.get('value', '?') if kmi30 else '?'
            kmi_pct = kmi30.get('change_pct', 0) if kmi30 else 0
            print(f"  ✅ Refreshed: {len(stocks)} stocks (total: {total_stocks}) | "
                  f"{len(news)} news | "
                  f"KSE: {kse_val} ({kse_pct}%) | "
                  f"KMI: {kmi_val} ({kmi_pct}%) | "
                  f"{len(cache['announcements'])} announcements")

        except Exception as e:
            print(f"  ❌ Refresh error: {e}")
            import traceback
            traceback.print_exc()

        time.sleep(30)  # Refresh every 30 seconds


# Start background thread
threading.Thread(target=refresh_loop, daemon=True).start()


# ════════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS — STATUS & MARKET
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/api/status")
def status():
    """API health check."""
    return {
        "status": "online" if not cache["is_loading"] else "loading",
        "version": "5.0",
        "market_open": is_psx_market_open(),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/market")
def market():
    """Overall market data."""
    return {
        "kse100": cache.get("kse100"),
        "kmi30": cache.get("kmi30"),
        "pkr": cache.get("pkr"),
        "market_analysis": cache.get("market_analysis"),
        "last_updated": cache.get("last_updated"),
    }


# ════════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS — INDICES
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/api/indices")
def get_indices():
    """Return both KSE-100 and KMI-30 index data."""
    return {
        "kse100": cache.get("kse100"),
        "kmi30": cache.get("kmi30"),
        "last_updated": cache.get("last_updated"),
    }


@app.get("/api/indices/{index}/contributors")
def index_contributors(index: str = "KSE100", limit: int = 10):
    """Top point contributors for an index."""
    key = f"{index.lower()}_contributors"
    contributors = cache.get(key, [])
    return {
        "index": index,
        "contributors": contributors[:limit],
        "count": len(contributors),
    }


@app.get("/api/indices/{index}/history")
def index_price_history(index: str = "KSE100", days: int = 30):
    """Historical price data for charting."""
    key = f"{index.lower()}_history"
    history = cache.get(key, [])
    return {
        "index": index,
        "days": days,
        "data": history[-days:] if len(history) > days else history,
        "count": len(history),
    }


# ════════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS — STOCKS
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/api/stocks")
def stocks(page: int = 1, limit: int = 500, 
           sector: str = None, shariah_only: bool = False):
    """
    Get all stocks with pagination.
    """
    data = cache.get("stocks", [])

    # Filter by sector
    if sector:
        data = [s for s in data if s.get("sector", "").lower() == sector.lower()]

    # Filter by Shariah
    if shariah_only:
        data = [s for s in data if s.get("shariah")]

    # Pagination
    offset = (page - 1) * limit
    paginated = data[offset : offset + limit]

    return {
        "data": paginated,
        "count": len(paginated),
        "total": len(data),
        "page": page,
        "limit": limit,
        "total_pages": (len(data) + limit - 1) // limit,
        "last_updated": cache.get("last_updated"),
    }


@app.get("/api/stocks/index/{index}")
def stocks_by_index(index: str):
    """
    Get all stocks belonging to KSE100 or KMI30 index.
    Returns enriched data by merging index ticker data with main stock cache.
    """
    index = index.upper()
    key = f"{index.lower()}_stocks"
    index_stock_list = cache.get(key, [])
    
    if not index_stock_list:
        return {"data": [], "count": 0, "index": index, "error": "Index data not yet loaded"}
    
    # Get symbol set for fast lookup
    index_symbols = {s["symbol"] for s in index_stock_list}
    
    # Merge: use main stock cache for full data, enriched with volume from ticker API
    all_stocks = cache.get("stocks", [])
    ticker_map = {s["symbol"]: s for s in index_stock_list}
    
    results = []
    for stock in all_stocks:
        if stock["symbol"] in index_symbols:
            enriched = dict(stock)
            # Add volume from ticker API (listing API doesn't have it)
            ticker_data = ticker_map.get(stock["symbol"], {})
            if ticker_data.get("volume"):
                enriched["volume"] = ticker_data["volume"]
            if ticker_data.get("change_pct"):
                enriched["change_pct"] = ticker_data["change_pct"]
            if ticker_data.get("change"):
                enriched["change"] = ticker_data["change"]
            if ticker_data.get("price"):
                enriched["price"] = ticker_data["price"]
            results.append(enriched)
    
    # Add any index stocks not found in main cache (with basic data)
    found_symbols = {s["symbol"] for s in results}
    for ticker in index_stock_list:
        if ticker["symbol"] not in found_symbols:
            results.append({
                "symbol":     ticker["symbol"],
                "name":       ticker.get("name", ticker["symbol"]),
                "sector":     SECTOR_MAP.get(ticker["symbol"], "Other"),
                "price":      ticker.get("price", 0),
                "prev_close": round(ticker.get("price", 0) - ticker.get("change", 0), 2),
                "change":     ticker.get("change", 0),
                "change_pct": ticker.get("change_pct", 0),
                "volume":     ticker.get("volume", 0),
                "high":       ticker.get("price", 0),
                "low":        ticker.get("price", 0),
                "shariah":    ticker.get("shariah", False),
                "logo":       "",
                "timestamp":  datetime.now().isoformat(),
                "source":     "sarmaaya.pk",
            })
    
    return {
        "data": results,
        "count": len(results),
        "index": index,
        "last_updated": cache.get("last_updated"),
    }


@app.get("/api/stocks/search")
def search_stocks(q: str = Query(..., min_length=1)):
    """Search stocks by symbol or name."""
    q_lower = q.lower()
    stocks_list = cache.get("stocks", [])
    results = [
        s for s in stocks_list
        if q_lower in s.get("symbol", "").lower() or 
           q_lower in s.get("name", "").lower()
    ]
    return {
        "query": q,
        "results": results[:20],
        "count": len(results),
    }


@app.get("/api/stocks/{symbol}")
def stock_detail(symbol: str):
    """Get detailed stock info + technical analysis."""
    symbol = symbol.upper()
    stocks_list = cache.get("stocks", [])
    stock = next((s for s in stocks_list if s["symbol"] == symbol), None)

    if not stock:
        return {"error": f"Stock {symbol} not found", "data": None}

    # Get technical analysis
    tech = technical_cache.get(symbol, {})

    # Get news for this stock
    news_items = [n for n in cache.get("news", [])
                  if symbol in n.get("related_stocks", [])]

    # Get AI signal
    signal = analyze_single_stock(symbol, stock, news_items)

    return {
        "stock": stock,
        "technical": tech,
        "signal": signal,
        "news": news_items[:5],
        "announcements": get_announcements_for_symbol(symbol),
    }


# ════════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS — SECTORS
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/api/sectors")
def sectors():
    """Get all sectors with stock counts."""
    sectors_list = cache.get("sectors", [])
    return {
        "sectors": sectors_list,
        "data": sectors_list,  # alias for frontend compatibility
        "count": len(sectors_list),
        "last_updated": cache.get("last_updated"),
    }


# ════════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS — NEWS
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/api/news")
def news(sentiment: str = None, stock: str = None):
    """Get news with optional filtering."""
    news_list = cache.get("news", [])

    # Filter by sentiment
    if sentiment:
        news_list = [n for n in news_list if n.get("sentiment") == sentiment]

    # Filter by stock
    if stock:
        stock = stock.upper()
        news_list = [n for n in news_list if stock in n.get("related_stocks", [])]

    return {
        "data": news_list[:50],
        "count": len(news_list),
        "filtered_count": len(news_list),
    }


# ════════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS — ANNOUNCEMENTS (no dividends)
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/api/announcements")
def announcements(atype: str = None):
    """Get announcements by type (board, results, bonus, rights, or 'all'). No dividends."""
    if atype:
        anns = get_announcements_by_type(atype)
    else:
        anns = cache.get("announcements", [])

    return {
        "data": anns,
        "count": len(anns),
        "type": atype or "all",
    }


@app.get("/api/announcements/{symbol}")
def announcements_symbol(symbol: str):
    """Get announcements for a specific stock."""
    anns = get_announcements_for_symbol(symbol.upper())
    return {
        "symbol": symbol.upper(),
        "data": anns,
        "count": len(anns),
    }


@app.get("/api/dividends")
def dividends():
    """Get dividend announcements (from payouts API)."""
    return {
        "data": cache.get("dividends", []),
        "count": len(cache.get("dividends", [])),
    }


# ════════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS — WATCHLIST
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/api/watchlist")
def get_watchlist():
    """Get user's watchlist."""
    stocks_list = cache.get("stocks", [])
    watchlist_stocks = [s for s in stocks_list if s["symbol"] in watchlist]
    return {
        "stocks": watchlist_stocks,
        "count": len(watchlist_stocks),
    }


@app.post("/api/watchlist/{symbol}")
def add_to_watchlist(symbol: str):
    """Add stock to watchlist."""
    watchlist.add(symbol.upper())
    return {"status": "added", "symbol": symbol.upper(), "count": len(watchlist)}


@app.delete("/api/watchlist/{symbol}")
def remove_from_watchlist(symbol: str):
    """Remove stock from watchlist."""
    watchlist.discard(symbol.upper())
    return {"status": "removed", "symbol": symbol.upper(), "count": len(watchlist)}


# ════════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS — PORTFOLIO
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/api/portfolio")
def portfolio():
    holdings    = get_holdings()
    stocks_list = cache.get("stocks", [])
    price_map   = {s["symbol"]: s for s in stocks_list}

    enriched       = []
    total_invested = 0.0
    total_current  = 0.0

    for h in holdings:
        sym       = h["symbol"]
        shares    = h["shares"]
        buy_price = h["buy_price"]
        invested  = shares * buy_price
        total_invested += invested
        live      = price_map.get(sym)

        if live:
            cur_price  = live["price"]
            cur_val    = shares * cur_price
            pnl        = cur_val - invested
            pnl_pct    = (pnl / invested * 100) if invested else 0
            total_current += cur_val
            enriched.append({
                "symbol":        sym,
                "name":          live.get("name", sym),
                "sector":        live.get("sector", ""),
                "shares":        shares,
                "buy_price":     buy_price,
                "current_price": round(cur_price, 2),
                "invested":      round(invested, 2),
                "current_value": round(cur_val, 2),
                "pnl":           round(pnl, 2),
                "pnl_pct":       round(pnl_pct, 2),
                "today_change":  live.get("change_pct", 0),
                "shariah":       live.get("shariah", False),
                "buy_date":      h.get("buy_date", ""),
                "has_live_data": True,
            })
        else:
            enriched.append({
                "symbol":        sym,
                "name":          sym,
                "sector":        "",
                "shares":        shares,
                "buy_price":     buy_price,
                "current_price": None,
                "invested":      round(invested, 2),
                "current_value": None,
                "pnl":           None,
                "pnl_pct":       None,
                "today_change":  None,
                "shariah":       False,
                "buy_date":      h.get("buy_date", ""),
                "has_live_data": False,
            })

    total_pnl     = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0

    return {
        "holdings": enriched,
        "summary": {
            "total_invested":  round(total_invested, 2),
            "total_current":   round(total_current, 2),
            "total_pnl":       round(total_pnl, 2),
            "total_pnl_pct":   round(total_pnl_pct, 2),
            "num_holdings":    len(enriched),
            "winners":         len([h for h in enriched if h["pnl"] and h["pnl"] > 0]),
            "losers":          len([h for h in enriched if h["pnl"] and h["pnl"] < 0]),
        },
        "last_calculated": datetime.now().isoformat(),
    }


@app.get("/api/portfolio/advice")
def portfolio_advice():
    calc   = portfolio()   # reuse the endpoint above
    advice = get_ai_portfolio_advice(calc, cache.get("news", []))
    return {"advice": advice, "portfolio": calc}


@app.post("/api/portfolio/add")
def portfolio_add(h: HoldingInput):
    result = add_holding(h.symbol.upper(), h.shares, h.buy_price, h.buy_date)
    return {"success": True, "holding": result}


@app.delete("/api/portfolio/{symbol}")
def portfolio_remove(symbol: str):
    result = remove_holding(symbol.upper())
    return {"success": result, "symbol": symbol.upper()}





# ════════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS — ALERTS
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/api/alerts")
def get_all_alerts():
    """Get all active alerts."""
    alerts_list = get_alerts()
    return {
        "data": alerts_list,
        "count": len(alerts_list),
    }


@app.post("/api/alerts")
def create_alert(a: AlertInput):
    """Create a new price alert."""
    result = add_alert(a.symbol.upper(), a.type, a.condition, a.target_value, a.note)
    return result


@app.delete("/api/alerts/{alert_id}")
def delete_alert_endpoint(alert_id: str):
    """Delete an alert."""
    result = delete_alert(alert_id)
    return result


@app.get("/api/alerts/triggered")
def get_triggered_alerts_endpoint():
    """Get recently triggered alerts."""
    triggered = get_triggered_alerts()
    return {
        "data": triggered,
        "count": len(triggered),
    }


@app.delete("/api/alerts/triggered/clear")
def clear_triggered_alerts():
    """Clear all triggered alerts."""
    result = clear_triggered()
    return result


# ════════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS — CHAT ASSISTANT
# ════════════════════════════════════════════════════════════════════════════════

from chat import chat as chat_fn, get_chat_history, clear_chat_history
from signal_history import (
    record_signal, update_outcomes,
    get_signal_history, get_accuracy_summary
)


class ChatMessage(BaseModel):
    message: str


@app.post("/api/chat")
async def chat_endpoint(msg: ChatMessage):
    """Chat with the AI assistant."""
    from portfolio import calculate_portfolio, get_holdings
    portfolio_data = None
    try:
        holdings = get_holdings()
        if holdings:
            portfolio_data = calculate_portfolio(cache.get("stocks", []))
    except:
        pass

    result = await chat_fn(
        message=msg.message,
        cache=cache,
        signals=stock_signals,
        tech_cache=technical_cache,
        portfolio_data=portfolio_data
    )
    return result


@app.get("/api/chat/history")
def chat_history():
    """Get chat conversation history."""
    return {"history": get_chat_history()}


@app.delete("/api/chat/history")
def chat_clear():
    """Clear chat history."""
    clear_chat_history()
    return {"status": "cleared"}


# ════════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS — SIGNAL HISTORY
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/api/signals/history")
def signals_history(symbol: str = None, limit: int = 50):
    """Get signal history."""
    return get_signal_history(symbol, limit)


@app.get("/api/signals/accuracy")
def signals_accuracy():
    """Get signal accuracy stats."""
    return get_accuracy_summary()


# ════════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS — PORTFOLIO EXPORT
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/api/portfolio/export")
def portfolio_export():
    """Export portfolio data for PDF generation."""
    from portfolio import calculate_portfolio as calc_port, get_holdings as get_h
    holdings = get_h()
    stocks_list = cache.get("stocks", [])
    portfolio_data = calc_port(stocks_list) if holdings else {"holdings": [], "summary": {}}
    return {"portfolio": portfolio_data}


# ════════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS — SARMAAYA LIVE DATA PROXY
# ════════════════════════════════════════════════════════════════════════════════

import httpx

SARMAAYA_BASE = "https://beta-restapi.sarmaaya.pk/api"

@app.get("/api/live/stock/{symbol}")
async def live_stock_detail(symbol: str):
    """Fetch rich stock info from Sarmaaya: 52wk high/low, open, close, volume, market cap."""
    symbol = symbol.upper()
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.get(f"{SARMAAYA_BASE}/stocks/{symbol}")
            if res.status_code == 200:
                data = res.json()
                resp = data.get("response", {})
                return {"success": True, "data": resp}
            return {"success": False, "error": f"HTTP {res.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/live/price-history/{symbol}")
async def live_price_history(symbol: str, days: int = 30):
    """Fetch 30-day price history from Sarmaaya."""
    symbol = symbol.upper()
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.get(f"{SARMAAYA_BASE}/stocks/price-history/{symbol}?days={days}")
            if res.status_code == 200:
                data = res.json()
                return {"success": True, "data": data.get("response", [])}
            return {"success": False, "error": f"HTTP {res.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/live/announcements/{symbol}")
async def live_announcements(symbol: str):
    """Fetch corporate announcements for a symbol from Sarmaaya."""
    symbol = symbol.upper()
    from datetime import timedelta
    end = datetime.now()
    start = end - timedelta(days=365)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.get(
                f"{SARMAAYA_BASE}/stocks/announcements/{symbol}",
                params={"startDate": start_str, "endDate": end_str}
            )
            if res.status_code == 200:
                data = res.json()
                return {"success": True, "data": data.get("response", [])}
            return {"success": False, "error": f"HTTP {res.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/live/insiders/{symbol}")
async def live_insiders(symbol: str):
    """Fetch insider trading data for a symbol from Sarmaaya."""
    symbol = symbol.upper()
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.get(f"{SARMAAYA_BASE}/stocks/stock-insiders/{symbol}")
            if res.status_code == 200:
                data = res.json()
                return {"success": True, "data": data.get("response", [])}
            return {"success": False, "error": f"HTTP {res.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/live/reports/{symbol}")
async def live_reports(symbol: str):
    """Fetch financial reports for a symbol from Sarmaaya."""
    symbol = symbol.upper()
    current_year = datetime.now().year
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            # Fetch current and prior year reports
            tasks = [
                client.get(f"{SARMAAYA_BASE}/stocks/reports/{symbol}", params={"year": current_year}),
                client.get(f"{SARMAAYA_BASE}/stocks/reports/{symbol}", params={"year": current_year - 1}),
            ]
            import asyncio
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            all_reports = []
            for r in responses:
                if not isinstance(r, Exception) and r.status_code == 200:
                    all_reports.extend(r.json().get("response", []))
            return {"success": True, "data": all_reports}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ════════════════════════════════════════════════════════════════════════════════
# STATIC FILES
# ════════════════════════════════════════════════════════════════════════════════

# Serve frontend (handle directory naming variations)
frontend_path = os.path.join(os.path.dirname(__file__), "../frontend")
if not os.path.exists(frontend_path):
    frontend_path = os.path.join(os.path.dirname(__file__), "../FRoNTEND")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")


# ════════════════════════════════════════════════════════════════════════════════
# ROOT
# ════════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)