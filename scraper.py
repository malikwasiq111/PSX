"""
PSX Scraper — Phase 5 rewrite
Uses sarmaaya.pk REST API exclusively:
  - /api/stocks/listing              → all ~496 stocks with pagination
  - /api/stocks/ticker?index=        → stocks in KSE100 / KMI30
  - /api/indices                     → KSE-100 & KMI-30 index values
  - /api/indices/top-point-contributors → top contributors per index
  - /api/indices/price-history       → 30-day chart data
  - /api/sectors/list                → all sectors live data
  - yfinance PKR=X                   → USD/PKR rate (no API alternative)
"""

import requests
import yfinance as yf
import time
from datetime import datetime, timezone, timedelta, time as dt_time

PKT     = timezone(timedelta(hours=5))
BASE    = "https://beta-restapi.sarmaaya.pk/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept":     "application/json",
}

# ── Shariah overrides (only used as fallback if API doesn't provide) ──────
SHARIAH_OVERRIDE = {
    "PSO": True, "OGDC": True, "PPL": True, "MARI": True,
    "MEBL": True, "FFC": True, "LUCK": True, "DGKC": True,
    "HUBC": True, "ENGRO": True, "FATIMA": True,
}

# ── Sector mapping (fallback — API stocks don't include sector) ───────────
SECTOR_MAP = {
    "OGDC":"Energy","PPL":"Energy","PSO":"Energy","MARI":"Energy",
    "POL":"Energy","APL":"Energy","SNGP":"Energy","SSGC":"Energy",
    "ATRL":"Oil Refinery","NRL":"Oil Refinery","PRL":"Oil Refinery",
    "HBL":"Banking","MCB":"Banking","UBL":"Banking","MEBL":"Banking",
    "BAHL":"Banking","ABL":"Banking","BAFL":"Banking","AKBL":"Banking",
    "NBP":"Banking","BOP":"Banking","SCBPL":"Banking","FABL":"Banking",
    "LUCK":"Cement","DGKC":"Cement","MLCF":"Cement","FCCL":"Cement",
    "CHCC":"Cement","PIOC":"Cement","ACPL":"Cement","KOHC":"Cement",
    "POWER":"Cement","FLYNG":"Cement",
    "FFC":"Fertilizer","EFERT":"Fertilizer","FATIMA":"Fertilizer",
    "HUBC":"Power","KAPCO":"Power","KEL":"Power","NPL":"Power",
    "INDU":"Auto","HCAR":"Auto","PSMC":"Auto","MTL":"Auto",
    "SEARL":"Pharma","GLAXO":"Pharma","AGP":"Pharma","ABOT":"Pharma",
    "SYS":"Technology","TRG":"Technology","NETSOL":"Technology",
    "NML":"Textile","NCL":"Textile","ILP":"Textile",
    "EPCL":"Chemicals","LOTCHEM":"Chemicals","ICI":"Chemicals",
    "NESTLE":"Food","UPFL":"Food","COLG":"Food",
    "ENGRO":"Conglomerate","DAWH":"Conglomerate",
    "MUGHAL":"Steel","ISL":"Steel","ASTL":"Steel",
    "PKGS":"Packaging","PNSC":"Transport","AIRLINK":"Technology",
    "GHGL":"Glass","TGL":"Glass","DCR":"Real Estate",
    "PAEL":"Engineering","HUMNL":"Media","SAZEW":"Auto",
}


# ════════════════════════════════════════════════════════════════════════════════
# STOCKS — PAGINATED (ALL ~496)
# ════════════════════════════════════════════════════════════════════════════════

def get_all_stocks(page: int = None, limit: int = 50) -> dict:
    """
    Fetch ALL stocks by paginating through the Sarmaaya listing API.
    
    Sarmaaya API caps at 50 per page, total ~496 stocks across 10 pages.
    
    API response format:
      { "success": true, "response": { "data": [...], "totalItems": 496, "totalPages": 10 } }
    
    Each stock object:
      { "symbol", "name", "close", "change", "changePercent", "isShariah", "logo", "date" }
    
    Returns: {"stocks": [...], "count": X, "total": Y}
    """
    all_results = []
    total_items = 0
    
    try:
        # First request to get total pages
        r = requests.get(
            f"{BASE}/stocks/listing?page=1&limit={limit}",
            headers=HEADERS, timeout=15
        )
        r.raise_for_status()
        data = r.json()
        
        if not data.get("success") or not data.get("response"):
            print(f"⚠️  Sarmaaya listing API: empty response")
            return {"stocks": _yfinance_fallback(), "count": 0, "total": 0}
        
        resp = data["response"]
        total_pages = resp.get("totalPages", 1)
        total_items = resp.get("totalItems", 0)
        
        # Parse page 1
        page1_stocks = _parse_stock_page(resp.get("data", []))
        all_results.extend(page1_stocks)
        
        # Fetch remaining pages (2 through total_pages)
        for pg in range(2, total_pages + 1):
            try:
                r2 = requests.get(
                    f"{BASE}/stocks/listing?page={pg}&limit={limit}",
                    headers=HEADERS, timeout=15
                )
                r2.raise_for_status()
                d2 = r2.json()
                if d2.get("success") and d2.get("response"):
                    page_stocks = _parse_stock_page(d2["response"].get("data", []))
                    all_results.extend(page_stocks)
            except Exception as e:
                print(f"  ⚠️ Page {pg} error: {e}")
                continue
        
        print(f"✅ Sarmaaya listing: {len(all_results)} stocks loaded (total: {total_items})")
        
        return {
            "stocks": all_results,
            "count": len(all_results),
            "total": total_items,
        }
        
    except Exception as e:
        print(f"❌ Stocks listing API error: {e}")
        return {"stocks": _yfinance_fallback(), "count": 0, "total": 0}


def _parse_stock_page(items: list) -> list:
    """Parse a page of stock items from Sarmaaya listing API."""
    results = []
    for s in items:
        symbol = (s.get("symbol") or "").upper().strip()
        if not symbol:
            continue
        
        # Sarmaaya uses "close" for current price, NOT "price"
        price      = float(s.get("close", 0) or 0)
        change     = float(s.get("change", 0) or 0)
        change_pct = float(s.get("changePercent", 0) or 0)
        prev_close = round(price - change, 2) if price else 0
        
        # Use API-provided name and shariah status
        name    = s.get("name", symbol)
        shariah = bool(s.get("isShariah", SHARIAH_OVERRIDE.get(symbol, False)))
        sector  = SECTOR_MAP.get(symbol, "Other")
        logo    = s.get("logo", "")
        
        results.append({
            "symbol":     symbol,
            "name":       name,
            "sector":     sector,
            "price":      round(price, 2),
            "prev_close": prev_close,
            "change":     round(change, 2),
            "change_pct": round(change_pct, 2),
            "volume":     0,  # listing API doesn't provide volume
            "high":       round(price, 2),
            "low":        round(price, 2),
            "shariah":    shariah,
            "logo":       logo,
            "timestamp":  datetime.now(PKT).isoformat(),
            "source":     "sarmaaya.pk",
        })
    
    return results


# ════════════════════════════════════════════════════════════════════════════════
# INDEX STOCKS — KSE100 / KMI30 constituent list with live prices
# ════════════════════════════════════════════════════════════════════════════════

def get_index_stocks(index: str = "KSE100") -> list:
    """
    Fetch all stocks in a given index (KSE100 or KMI30) with live prices.
    
    API: /api/stocks/ticker?index=KSE100
    Response: { "success": true, "response": [ { "symbol", "price", "change", "changePercentage", "volume", "isShariah" } ] }
    """
    try:
        r = requests.get(
            f"{BASE}/stocks/ticker?index={index}",
            headers=HEADERS, timeout=15
        )
        r.raise_for_status()
        data = r.json()
        
        if not data.get("success"):
            print(f"⚠️  Index stocks API empty for {index}")
            return []
        
        results = []
        for s in data.get("response", []):
            symbol = (s.get("symbol") or "").upper().strip()
            if not symbol:
                continue
            
            price      = float(s.get("price", 0) or 0)
            change     = float(s.get("change", 0) or 0)
            change_pct = float(s.get("changePercentage", 0) or 0)
            volume     = int(s.get("volume", 0) or 0)
            
            results.append({
                "symbol":     symbol,
                "name":       symbol,  # ticker API doesn't return name
                "price":      round(price, 2),
                "change":     round(change, 2),
                "change_pct": round(change_pct, 2),
                "volume":     volume,
                "shariah":    bool(s.get("isShariah", False)),
                "source":     "sarmaaya.pk",
            })
        
        print(f"✅ Index stocks for {index}: {len(results)} stocks")
        return results
        
    except Exception as e:
        print(f"❌ Index stocks API error for {index}: {e}")
        return []


# ════════════════════════════════════════════════════════════════════════════════
# INDICES
# ════════════════════════════════════════════════════════════════════════════════

def get_kse100() -> dict:
    """Fetch KSE-100 index from sarmaaya indices API."""
    try:
        r = requests.get(f"{BASE}/indices?limit=16", headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("success"):
            indices = data.get("response", {}).get("data", [])
            kse = next((i for i in indices if i.get("symbol") == "KSE100"), None)
            if kse:
                return {
                    "value":      round(float(kse.get("curr", 0)), 2),
                    "change":     round(float(kse.get("change", 0)), 2),
                    "change_pct": round(float(kse.get("changePercent", 0)), 2),
                    "high52":     round(float(kse.get("high52", 0)), 2),
                    "low52":      round(float(kse.get("low52", 0)), 2),
                    "volume":     int(kse.get("volume", 0)),
                    "market_cap": float(kse.get("marketCap", 0)),
                    "timestamp":  datetime.now(PKT).isoformat(),
                    "source":     "sarmaaya.pk",
                }
    except Exception as e:
        print(f"❌ KSE-100 API error: {e}")

    # yfinance fallback
    try:
        t = yf.Ticker("^KSE100")
        h = t.history(period="2d", interval="1d")
        if not h.empty:
            v = float(h['Close'].iloc[-1])
            p = float(h['Close'].iloc[-2]) if len(h) > 1 else v
            return {
                "value": round(v, 2),
                "change": round(v - p, 2),
                "change_pct": round((v - p) / p * 100, 2) if p else 0,
                "timestamp": datetime.now(PKT).isoformat(),
                "source": "yfinance"
            }
    except:
        pass

    return {
        "value": None, "change": 0, "change_pct": 0,
        "timestamp": datetime.now(PKT).isoformat(), "source": "unavailable"
    }


def get_kmi30() -> dict:
    """Fetch KMI-30 index from sarmaaya indices API."""
    try:
        r = requests.get(f"{BASE}/indices?limit=16", headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("success"):
            indices = data.get("response", {}).get("data", [])
            kmi = next((i for i in indices if i.get("symbol") == "KMI30"), None)
            if kmi:
                return {
                    "value":      round(float(kmi.get("curr", 0)), 2),
                    "change":     round(float(kmi.get("change", 0)), 2),
                    "change_pct": round(float(kmi.get("changePercent", 0)), 2),
                    "high52":     round(float(kmi.get("high52", 0)), 2),
                    "low52":      round(float(kmi.get("low52", 0)), 2),
                    "volume":     int(kmi.get("volume", 0)),
                    "market_cap": float(kmi.get("marketCap", 0)),
                    "timestamp":  datetime.now(PKT).isoformat(),
                    "source":     "sarmaaya.pk",
                }
    except Exception as e:
        print(f"❌ KMI-30 API error: {e}")

    return {
        "value": None, "change": 0, "change_pct": 0,
        "timestamp": datetime.now(PKT).isoformat(), "source": "unavailable"
    }


def get_index_top_contributors(index: str = "KSE100", limit: int = 15) -> list:
    """
    Fetch top point contributors for an index.
    index: "KSE100" or "KMI30"
    """
    try:
        r = requests.get(
            f"{BASE}/indices/top-point-contributors/{index}?filter=stocks&limit={limit}",
            headers=HEADERS, timeout=10
        )
        r.raise_for_status()
        data = r.json()
        if data.get("success"):
            results = []
            for item in data.get("response", []):
                results.append({
                    "symbol":       item.get("symbol", "").upper(),
                    "contribution": round(float(item.get("pointContribution", 0)), 2),
                    "change_pct":   round(float(item.get("changePercent", 0)), 2),
                    "price":        round(float(item.get("price", 0)), 2),
                    "volume":       int(item.get("volume", 0)),
                })
            print(f"✅ Top contributors for {index}: {len(results)} stocks")
            return results
    except Exception as e:
        print(f"❌ Top contributors error for {index}: {e}")
    return []


def get_index_price_history(index: str = "KSE100", days: int = 30) -> list:
    """
    Fetch historical price data for index (30-day chart data).
    Returns daily OHLC data for charting.
    """
    try:
        r = requests.get(
            f"{BASE}/indices/price-history/{index}?days={days}",
            headers=HEADERS, timeout=10
        )
        r.raise_for_status()
        data = r.json()
        if data.get("success"):
            history = []
            for item in data.get("response", []):
                history.append({
                    "date":   item.get("date", ""),
                    "open":   round(float(item.get("open", 0)), 2),
                    "high":   round(float(item.get("high", 0)), 2),
                    "low":    round(float(item.get("low", 0)), 2),
                    "close":  round(float(item.get("close", 0)), 2),
                    "volume": int(item.get("volume", 0)),
                })
            print(f"✅ Price history for {index}: {len(history)} days")
            return history
    except Exception as e:
        print(f"❌ Index history error for {index}: {e}")
    return []


# ════════════════════════════════════════════════════════════════════════════════
# SECTORS
# ════════════════════════════════════════════════════════════════════════════════

def get_sectors_live() -> list:
    """Fetch live sector data from sarmaaya API."""
    try:
        r = requests.get(f"{BASE}/sectors/list", headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()

        if data.get("success"):
            sectors = []
            response_data = data.get("response", {})
            sectors_list = response_data.get("sectorsList", []) if isinstance(response_data, dict) else []
            for sec in sectors_list:
                change_pct = round(float(sec.get("changePercent", 0) or 0), 2)
                sectors.append({
                    "sector":     sec.get("name", "Other"),
                    "change":     round(float(sec.get("change", 0) or 0), 2),
                    "change_pct": change_pct,
                    "avg_change": change_pct,  # alias for frontend compatibility
                    "trend":      "up" if change_pct > 0 else "down" if change_pct < 0 else "flat",
                    "volume":     int(sec.get("volume", 0) or 0),
                    "stocks":     [],  # Will be filled in main.py
                })
            print(f"✅ Sectors: {len(sectors)} loaded")
            return sectors
    except Exception as e:
        print(f"❌ Sectors API error: {e}")

    # Fallback
    return [
        {"sector": "Banking", "change": 0, "change_pct": 0, "avg_change": 0, "trend": "flat", "volume": 0, "stocks": []},
        {"sector": "Energy", "change": 0, "change_pct": 0, "avg_change": 0, "trend": "flat", "volume": 0, "stocks": []},
        {"sector": "Cement", "change": 0, "change_pct": 0, "avg_change": 0, "trend": "flat", "volume": 0, "stocks": []},
        {"sector": "Fertilizer", "change": 0, "change_pct": 0, "avg_change": 0, "trend": "flat", "volume": 0, "stocks": []},
    ]


# ════════════════════════════════════════════════════════════════════════════════
# FOREX
# ════════════════════════════════════════════════════════════════════════════════

def get_pkr_usd() -> dict:
    """Fetch USD/PKR exchange rate."""
    try:
        h = yf.Ticker("PKR=X").history(period="2d", interval="5m")
        if not h.empty:
            rate = float(h['Close'].iloc[-1])
            prev = float(h['Close'].iloc[0])
            chg  = rate - prev
            return {
                "rate":       round(rate, 2),
                "change":     round(chg, 4),
                "change_pct": round(chg / prev * 100, 2) if prev else 0,
                "timestamp":  datetime.now(PKT).isoformat()
            }
    except Exception as e:
        print(f"❌ PKR rate error: {e}")
    return None


# ════════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════════

def is_psx_market_open() -> bool:
    """Check if PSX market is currently open."""
    now = datetime.now(PKT)
    if now.weekday() >= 5:  # Saturday/Sunday
        return False
    return dt_time(9, 30) <= now.time() <= dt_time(15, 30)


def _yfinance_fallback() -> list:
    """Fallback: pull major stocks from yfinance if API fails."""
    FALLBACK = {
        "OGDC":"OGDC.KA","PPL":"PPL.KA","PSO":"PSO.KA","HBL":"HBL.KA",
        "MCB":"MCB.KA","UBL":"UBL.KA","MEBL":"MEBL.KA","LUCK":"LUCK.KA",
        "DGKC":"DGKC.KA","FFC":"FFC.KA","HUBC":"HUBC.KA","MARI":"MARI.KA",
        "ENGRO":"ENGROB.KA","FATIMA":"FATIMA.KA","ABL":"ABL.KA",
        "BAFL":"BAFL.KA","BAHL":"BAHL.KA","NBP":"NBP.KA",
    }
    results = []
    for sym, ticker in FALLBACK.items():
        try:
            h = yf.Ticker(ticker).history(period="2d", interval="1d")
            if h.empty:
                continue
            price = float(h['Close'].iloc[-1])
            prev  = float(h['Close'].iloc[-2]) if len(h) > 1 else price
            chg   = price - prev
            pct   = (chg / prev * 100) if prev else 0
            results.append({
                "symbol": sym, "name": sym,
                "sector": SECTOR_MAP.get(sym, "Other"),
                "price": round(price, 2), "prev_close": round(prev, 2),
                "change": round(chg, 2), "change_pct": round(pct, 2),
                "volume": int(h['Volume'].iloc[-1]),
                "high": round(price, 2), "low": round(price, 2),
                "shariah": SHARIAH_OVERRIDE.get(sym, False),
                "logo": "",
                "timestamp": datetime.now(PKT).isoformat(),
                "source": "yfinance (fallback)",
            })
        except:
            continue
    print(f"⚠️  yfinance fallback: {len(results)} stocks")
    return results