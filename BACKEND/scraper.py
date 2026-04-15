import yfinance as yf
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup
import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── 100+ PSX Stocks — All major KSE-100 constituents ───────────────────────
PSX_STOCKS = {
    # ── Energy / Oil & Gas ──
    "OGDC":   {"ticker": "OGDC.KA",   "name": "Oil & Gas Dev Co",          "sector": "Energy"},
    "PPL":    {"ticker": "PPL.KA",    "name": "Pakistan Petroleum",         "sector": "Energy"},
    "PSO":    {"ticker": "PSO.KA",    "name": "Pakistan State Oil",         "sector": "Energy"},
    "MARI":   {"ticker": "MARI.KA",   "name": "Mari Petroleum",             "sector": "Energy"},
    "POL":    {"ticker": "POL.KA",    "name": "Pakistan Oilfields",         "sector": "Energy"},
    "APL":    {"ticker": "APL.KA",    "name": "Attock Petroleum",           "sector": "Energy"},
    "SNGP":   {"ticker": "SNGP.KA",   "name": "Sui Northern Gas",          "sector": "Energy"},
    "SSGC":   {"ticker": "SSGC.KA",   "name": "Sui Southern Gas",          "sector": "Energy"},
    # ── Oil Refinery ──
    "ATRL":   {"ticker": "ATRL.KA",   "name": "Attock Refinery",           "sector": "Oil Refinery"},
    "NRL":    {"ticker": "NRL.KA",    "name": "National Refinery",          "sector": "Oil Refinery"},
    "PRL":    {"ticker": "PRL.KA",    "name": "Pakistan Refinery",          "sector": "Oil Refinery"},
    # ── Banking ──
    "HBL":    {"ticker": "HBL.KA",    "name": "Habib Bank Ltd",            "sector": "Banking"},
    "MCB":    {"ticker": "MCB.KA",    "name": "MCB Bank",                  "sector": "Banking"},
    "UBL":    {"ticker": "UBL.KA",    "name": "United Bank Ltd",           "sector": "Banking"},
    "MEBL":   {"ticker": "MEBL.KA",   "name": "Meezan Bank",               "sector": "Banking"},
    "BAHL":   {"ticker": "BAHL.KA",   "name": "Bank Al Habib",             "sector": "Banking"},
    "ABL":    {"ticker": "ABL.KA",    "name": "Allied Bank Ltd",           "sector": "Banking"},
    "BAFL":   {"ticker": "BAFL.KA",   "name": "Bank Alfalah",             "sector": "Banking"},
    "AKBL":   {"ticker": "AKBL.KA",   "name": "Askari Bank",               "sector": "Banking"},
    "NBP":    {"ticker": "NBP.KA",    "name": "National Bank",             "sector": "Banking"},
    "BOP":    {"ticker": "BOP.KA",    "name": "Bank of Punjab",            "sector": "Banking"},
    "SCBPL":  {"ticker": "SCBPL.KA",  "name": "Standard Chartered PK",    "sector": "Banking"},
    "JSBL":   {"ticker": "JSBL.KA",   "name": "JS Bank",                   "sector": "Banking"},
    "FABL":   {"ticker": "FABL.KA",   "name": "Faysal Bank",               "sector": "Banking"},
    "BOK":    {"ticker": "BOK.KA",    "name": "Bank of Khyber",            "sector": "Banking"},
    # ── Cement ──
    "LUCK":   {"ticker": "LUCK.KA",   "name": "Lucky Cement",              "sector": "Cement"},
    "DGKC":   {"ticker": "DGKC.KA",   "name": "DG Khan Cement",           "sector": "Cement"},
    "MLCF":   {"ticker": "MLCF.KA",   "name": "Maple Leaf Cement",        "sector": "Cement"},
    "FCCL":   {"ticker": "FCCL.KA",   "name": "Fauji Cement",              "sector": "Cement"},
    "CHCC":   {"ticker": "CHCC.KA",   "name": "Cherat Cement",             "sector": "Cement"},
    "PIOC":   {"ticker": "PIOC.KA",   "name": "Pioneer Cement",            "sector": "Cement"},
    "ACPL":   {"ticker": "ACPL.KA",   "name": "Attock Cement",             "sector": "Cement"},
    "KOHC":   {"ticker": "KOHC.KA",   "name": "Kohat Cement",              "sector": "Cement"},
    "THCCL":  {"ticker": "THCCL.KA",  "name": "Thatta Cement",             "sector": "Cement"},
    # ── Fertilizer ──
    "FFC":    {"ticker": "FFC.KA",    "name": "Fauji Fertilizer",          "sector": "Fertilizer"},
    "EFERT":  {"ticker": "EFERT.KA",  "name": "Engro Fertilizer",          "sector": "Fertilizer"},
    "FATIMA": {"ticker": "FATIMA.KA", "name": "Fatima Fertilizer",         "sector": "Fertilizer"},
    # ── Power / Energy ──
    "HUBC":   {"ticker": "HUBC.KA",   "name": "Hub Power Company",         "sector": "Power"},
    "KAPCO":  {"ticker": "KAPCO.KA",  "name": "K-Electric/Kapco",          "sector": "Power"},
    "KEL":    {"ticker": "KEL.KA",    "name": "K-Electric",                "sector": "Power"},
    "NPL":    {"ticker": "NPL.KA",    "name": "Nishat Power",              "sector": "Power"},
    # ── Auto ──
    "INDU":   {"ticker": "INDU.KA",   "name": "Indus Motor",               "sector": "Auto"},
    "HCAR":   {"ticker": "HCAR.KA",   "name": "Honda Atlas Cars",          "sector": "Auto"},
    "PSMC":   {"ticker": "PSMC.KA",   "name": "Pak Suzuki Motor",          "sector": "Auto"},
    "MTL":    {"ticker": "MTL.KA",    "name": "Millat Tractors",           "sector": "Auto"},
    "AGTL":   {"ticker": "AGTL.KA",   "name": "Al-Ghazi Tractors",         "sector": "Auto"},
    # ── Pharma ──
    "SEARL":  {"ticker": "SEARL.KA",  "name": "Searle Company",            "sector": "Pharma"},
    "GLAXO":  {"ticker": "GLAXO.KA",  "name": "GlaxoSmithKline PK",       "sector": "Pharma"},
    "AGP":    {"ticker": "AGP.KA",    "name": "AGP Ltd",                   "sector": "Pharma"},
    "FEROZ":  {"ticker": "FEROZ.KA",  "name": "Ferozsons Labs",            "sector": "Pharma"},
    "ABOT":   {"ticker": "ABOT.KA",   "name": "Abbott Labs PK",            "sector": "Pharma"},
    # ── Technology / Telecom ──
    "SYS":    {"ticker": "SYS.KA",    "name": "Systems Ltd",               "sector": "Technology"},
    "TRG":    {"ticker": "TRG.KA",    "name": "TRG Pakistan",              "sector": "Technology"},
    "NETSOL":  {"ticker": "NETSOL.KA", "name": "NetSol Technologies",      "sector": "Technology"},
    "AVN":    {"ticker": "AVN.KA",    "name": "AVN Technologies",          "sector": "Technology"},
    "TELE":   {"ticker": "TELE.KA",   "name": "Telecard Limited",          "sector": "Technology"},
    # ── Textile ──
    "NML":    {"ticker": "NML.KA",    "name": "Nishat Mills",              "sector": "Textile"},
    "NCL":    {"ticker": "NCL.KA",    "name": "Nishat Chunian",            "sector": "Textile"},
    "ILP":    {"ticker": "ILP.KA",    "name": "Interloop Ltd",             "sector": "Textile"},
    # ── Chemicals ──
    "EPCL":   {"ticker": "EPCL.KA",   "name": "Engro Polymer",            "sector": "Chemicals"},
    "LOTCHEM": {"ticker": "LOTCHEM.KA","name": "Lotte Chemical PK",        "sector": "Chemicals"},
    "ICI":    {"ticker": "ICI.KA",    "name": "ICI Pakistan",              "sector": "Chemicals"},
    # ── Food / Consumer ──
    "NESTLE": {"ticker": "NESTLE.KA", "name": "Nestle Pakistan",           "sector": "Food"},
    "UPFL":   {"ticker": "UPFL.KA",   "name": "Unilever PK Foods",        "sector": "Food"},
    "COLG":   {"ticker": "COLG.KA",   "name": "Colgate-Palmolive PK",     "sector": "Food"},
    "FFL":    {"ticker": "FFL.KA",    "name": "Friesland Foods",           "sector": "Food"},
    "BATA":   {"ticker": "BATA.KA",   "name": "Bata Pakistan",             "sector": "Food"},
    # ── Insurance ──
    "JLICL":  {"ticker": "JLICL.KA",  "name": "Jubilee Life Ins",         "sector": "Insurance"},
    # ── Conglomerate / Holding ──
    "ENGRO":  {"ticker": "ENGRO.KA",  "name": "Engro Corporation",         "sector": "Conglomerate"},
    "DAWH":   {"ticker": "DAWH.KA",   "name": "Dawood Hercules",           "sector": "Conglomerate"},
    "ISL":    {"ticker": "ISL.KA",    "name": "Islamabad Stock Exchange",  "sector": "Conglomerate"},
    # ── Steel ──
    "MUGHAL": {"ticker": "MUGHAL.KA", "name": "Mughal Steel",              "sector": "Steel"},
    "ISL":    {"ticker": "ISL.KA",    "name": "International Steels",      "sector": "Steel"},
    "ASTL":   {"ticker": "ASTL.KA",   "name": "Amreli Steels",             "sector": "Steel"},
    # ── Paper / Packaging ──
    "PKGS":   {"ticker": "PKGS.KA",   "name": "Packages Ltd",              "sector": "Packaging"},
    "PAKT":   {"ticker": "PAKT.KA",   "name": "Pakages Ltd T",             "sector": "Packaging"},
    # ── Transport ──
    "PNSC":   {"ticker": "PNSC.KA",   "name": "Pakistan National Ship",   "sector": "Transport"},
    "AIRLINK": {"ticker": "AIRLINK.KA","name": "Air Link Comm",            "sector": "Technology"},
    # ── Glass / Ceramics ──
    "GHGL":   {"ticker": "GHGL.KA",   "name": "Ghani Glass",               "sector": "Glass"},
    "TGL":    {"ticker": "TGL.KA",    "name": "Tariq Glass",               "sector": "Glass"},
    # ── Real Estate ──
    "DCR":    {"ticker": "DCR.KA",    "name": "Dolmen City REIT",          "sector": "Real Estate"},
    # ── Misc Blue Chips ──
    "PAEL":   {"ticker": "PAEL.KA",   "name": "Pak Elektron",              "sector": "Engineering"},
    "HASCOL": {"ticker": "HASCOL.KA", "name": "Hascol Petroleum",          "sector": "Energy"},
    "CNERGY": {"ticker": "CNERGY.KA", "name": "Cnergy Coal",               "sector": "Mining"},
    "FLYNG":  {"ticker": "FLYNG.KA",  "name": "Flying Cement",             "sector": "Cement"},
    "GGL":    {"ticker": "GGL.KA",    "name": "Ghani Global",              "sector": "Glass"},
    "MUGHAL": {"ticker": "MUGHAL.KA", "name": "Mughal Iron & Steel",       "sector": "Steel"},
    "PIAHCLA": {"ticker": "PIAHCLA.KA","name": "PIA Holding",              "sector": "Transport"},
    "HUMNL":  {"ticker": "HUMNL.KA",  "name": "Hum Network",               "sector": "Media"},
    "WTL":    {"ticker": "WTL.KA",    "name": "WorldCall Telecom",         "sector": "Technology"},
    "TPL":    {"ticker": "TPL.KA",    "name": "TPL Properties",            "sector": "Real Estate"},
    "JDWS":   {"ticker": "JDWS.KA",   "name": "JDW Sugar",                 "sector": "Sugar"},
    "PIBTL":  {"ticker": "PIBTL.KA",  "name": "Pakistan Int Bulk",        "sector": "Transport"},
    "POWER":  {"ticker": "POWER.KA",  "name": "Power Cement",              "sector": "Cement"},
    "UNITY":  {"ticker": "UNITY.KA",  "name": "Unity Foods",               "sector": "Food"},
    "WAVES":  {"ticker": "WAVES.KA",  "name": "Waves Singer",              "sector": "Engineering"},
    "SPEL":   {"ticker": "SPEL.KA",   "name": "Saif Power",                "sector": "Power"},
    "FCL":    {"ticker": "FCL.KA",    "name": "Fauji Foods",               "sector": "Food"},
    "JUBS":   {"ticker": "JUBS.KA",   "name": "Jubilee Spinning",          "sector": "Textile"},
    "STL":    {"ticker": "STL.KA",    "name": "Service Textile",           "sector": "Textile"},
}

# Shariah compliant status (based on SECP/Meezan criteria — June 2024 list)
SHARIAH_STATUS = {
    # Energy
    "OGDC": True, "PPL": True, "PSO": False, "MARI": True, "POL": True,
    "APL": True, "SNGP": False, "SSGC": False,
    # Oil Refinery
    "ATRL": False, "NRL": False, "PRL": False,
    # Banking (conventional = not shariah)
    "HBL": False, "MCB": False, "UBL": False, "MEBL": True, "BAHL": False,
    "ABL": False, "BAFL": False, "AKBL": False, "NBP": False, "BOP": False,
    "SCBPL": False, "JSBL": False, "FABL": False, "BOK": False,
    # Cement
    "LUCK": True, "DGKC": True, "MLCF": True, "FCCL": True, "CHCC": True,
    "PIOC": True, "ACPL": True, "KOHC": True, "THCCL": True, "FLYNG": True,
    "POWER": True,
    # Fertilizer
    "FFC": True, "EFERT": True, "FATIMA": True,
    # Power
    "HUBC": True, "KAPCO": True, "KEL": False, "NPL": True, "SPEL": True,
    # Auto
    "INDU": True, "HCAR": True, "PSMC": True, "MTL": True, "AGTL": True,
    # Pharma
    "SEARL": True, "GLAXO": True, "AGP": True, "FEROZ": True, "ABOT": True,
    # Technology
    "SYS": True, "TRG": True, "NETSOL": True, "AVN": True, "TELE": True,
    "AIRLINK": True, "WTL": True,
    # Textile
    "NML": True, "NCL": True, "ILP": True, "JUBS": True, "STL": True,
    # Chemicals
    "EPCL": True, "LOTCHEM": True, "ICI": True,
    # Food
    "NESTLE": True, "UPFL": True, "COLG": True, "FFL": True, "BATA": True,
    "UNITY": True, "FCL": True, "JDWS": True,
    # Conglomerate
    "ENGRO": True, "DAWH": True,
    # Steel
    "MUGHAL": True, "ISL": True, "ASTL": True,
    # Other
    "PKGS": True, "PAKT": True, "PNSC": True, "GHGL": True, "TGL": True,
    "DCR": True, "PAEL": True, "HASCOL": False, "CNERGY": True,
    "GGL": True, "PIAHCLA": False, "HUMNL": True, "TPL": True,
    "PIBTL": True, "WAVES": True, "JLICL": False,
}

# ── PSX Market hours (PKT = UTC+5) ─────────────────────────────────────────
PKT = timezone(timedelta(hours=5))

def is_psx_market_open():
    """Check if PSX market is currently open (Mon-Fri 9:30 AM – 3:30 PM PKT)."""
    now = datetime.now(PKT)
    if now.weekday() >= 5:          # Saturday / Sunday
        return False
    market_open  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


# ── Real-time data from PSX Data Portal ─────────────────────────────────────

PSX_TIMESERIES_URL = "https://dps.psx.com.pk/timeseries/int/{symbol}"
PSX_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://dps.psx.com.pk/",
}


def _fetch_psx_realtime(symbol: str):
    """
    Fetch real-time intraday trade data from PSX Data Portal.
    Returns list of [timestamp, price, volume] trades, newest first.
    """
    url = PSX_TIMESERIES_URL.format(symbol=symbol)
    try:
        resp = requests.get(url, headers=PSX_HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("status") == 1 and data.get("data"):
            return data["data"]      # [[ts, price, vol], ...]
    except Exception as e:
        pass  # silent for 100+ stocks
    return None


def _parse_psx_trades(symbol: str, trades: list):
    """
    Parse PSX trade data into a stock dict.
    trades = [[timestamp, price, volume], ...] sorted newest-first.
    """
    info = PSX_STOCKS[symbol]

    # Latest trade = current price
    current_price = float(trades[0][1])

    # Aggregate intraday stats
    prices  = [float(t[1]) for t in trades]
    volumes = [int(t[2])   for t in trades]
    total_volume = sum(volumes)
    day_high = max(prices)
    day_low  = min(prices)

    # Opening price = last trade of the day (oldest in list)
    open_price = float(trades[-1][1])

    # Change from day open (intraday change)
    change     = current_price - open_price
    change_pct = (change / open_price * 100) if open_price else 0

    # Trade timestamp (most recent)
    last_trade_ts = trades[0][0]
    try:
        trade_time = datetime.fromtimestamp(last_trade_ts, tz=PKT).isoformat()
    except Exception:
        trade_time = datetime.now(PKT).isoformat()

    return {
        "symbol":       symbol,
        "name":         info["name"],
        "sector":       info["sector"],
        "price":        round(current_price, 2),
        "open":         round(open_price, 2),
        "prev_close":   round(open_price, 2),   # best proxy without separate EOD call
        "change":       round(change, 2),
        "change_pct":   round(change_pct, 2),
        "volume":       total_volume,
        "high":         round(day_high, 2),
        "low":          round(day_low, 2),
        "shariah":      SHARIAH_STATUS.get(symbol, False),
        "timestamp":    trade_time,
        "source":       "PSX Live",
        "market_open":  is_psx_market_open(),
    }


# ── Previous close from yfinance (for accurate daily change) ────────────────

_prev_close_cache = {}       # symbol → {"price": float, "fetched_at": float}
_PREV_CLOSE_TTL   = 3600     # refresh once per hour

def _get_prev_close(symbol: str):
    """Get yesterday's close price via yfinance (cached for 1 hour)."""
    cached = _prev_close_cache.get(symbol)
    if cached and (_time.time() - cached["fetched_at"]) < _PREV_CLOSE_TTL:
        return cached["price"]

    info = PSX_STOCKS.get(symbol)
    if not info:
        return None
    try:
        ticker = yf.Ticker(info["ticker"])
        hist = ticker.history(period="5d", interval="1d")
        if hist.empty or len(hist) < 2:
            return None
        prev = float(hist['Close'].iloc[-2])
        _prev_close_cache[symbol] = {"price": prev, "fetched_at": _time.time()}
        return prev
    except Exception:
        return None


# ── Public API: single stock ────────────────────────────────────────────────

def get_stock_data(symbol: str):
    """Fetch real-time data for a single stock."""
    try:
        info = PSX_STOCKS.get(symbol)
        if not info:
            return None

        # Primary: PSX real-time trades
        trades = _fetch_psx_realtime(symbol)
        if trades:
            stock = _parse_psx_trades(symbol, trades)

            # Try to get accurate prev close from yfinance
            prev = _get_prev_close(symbol)
            if prev:
                stock["prev_close"] = round(prev, 2)
                stock["change"]     = round(stock["price"] - prev, 2)
                stock["change_pct"] = round((stock["price"] - prev) / prev * 100, 2)

            return stock

        # Fallback: yfinance
        return _yfinance_single(symbol, info)

    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None


def _yfinance_single(symbol: str, info: dict):
    """Fallback: get stock data from yfinance."""
    try:
        ticker = yf.Ticker(info["ticker"])
        hist = ticker.history(period="5d", interval="1m")
        if hist.empty:
            return None

        current_price = float(hist['Close'].iloc[-1])
        daily = ticker.history(period="2d", interval="1d")
        if len(daily) >= 2:
            prev_close = float(daily['Close'].iloc[-2])
        else:
            prev_close = float(hist['Close'].iloc[0])

        change = current_price - prev_close
        change_pct = (change / prev_close) * 100
        volume = int(hist['Volume'].iloc[-1])

        return {
            "symbol":       symbol,
            "name":         info["name"],
            "sector":       info["sector"],
            "price":        round(current_price, 2),
            "prev_close":   round(prev_close, 2),
            "change":       round(change, 2),
            "change_pct":   round(change_pct, 2),
            "volume":       volume,
            "high":         round(float(hist['High'].max()), 2),
            "low":          round(float(hist['Low'].min()), 2),
            "shariah":      SHARIAH_STATUS.get(symbol, False),
            "timestamp":    datetime.now(PKT).isoformat(),
            "source":       "yfinance (delayed)",
            "market_open":  is_psx_market_open(),
        }
    except Exception:
        return None


# ── Public API: all stocks ──────────────────────────────────────────────────

def get_all_stocks():
    """
    Fetch real-time data for all tracked stocks.
    Uses PSX Data Portal as primary source (parallel requests).
    Falls back to yfinance if PSX fails.
    """
    results = []
    failed_symbols = []

    def fetch_one(symbol):
        trades = _fetch_psx_realtime(symbol)
        if trades:
            return _parse_psx_trades(symbol, trades), None
        return None, symbol

    # Fetch all stocks from PSX in parallel (10 threads for 100+ stocks)
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(fetch_one, sym): sym for sym in PSX_STOCKS}
        for future in as_completed(futures):
            try:
                stock, failed = future.result()
                if stock:
                    results.append(stock)
                elif failed:
                    failed_symbols.append(failed)
            except Exception:
                pass

    # For stocks that got PSX data, try to enrich with accurate prev_close
    # (only do a batch of first 20 to avoid slowdown — rest use open price)
    for stock in results[:20]:
        prev = _get_prev_close(stock["symbol"])
        if prev:
            stock["prev_close"] = round(prev, 2)
            stock["change"]     = round(stock["price"] - prev, 2)
            stock["change_pct"] = round((stock["price"] - prev) / prev * 100, 2)

    source_count = sum(1 for s in results if s.get("source") == "PSX Live")
    print(f"PSX scraper: {len(results)} stocks ({source_count} live, "
          f"{len(failed_symbols)} failed)")

    return results if results else _yfinance_fallback()


def _yfinance_fallback():
    """Use yfinance if PSX scraping fails entirely."""
    results = []
    for symbol, info in list(PSX_STOCKS.items())[:20]:  # limit to 20 for speed
        try:
            ticker = yf.Ticker(info["ticker"])
            hist = ticker.history(period="2d", interval="1d")
            if hist.empty:
                continue
            price = float(hist['Close'].iloc[-1])
            prev  = float(hist['Close'].iloc[-2]) if len(hist) > 1 else price
            change = price - prev
            pct    = (change / prev * 100) if prev else 0
            results.append({
                "symbol":     symbol,
                "name":       info["name"],
                "sector":     info["sector"],
                "price":      round(price, 2),
                "prev_close": round(prev, 2),
                "change":     round(change, 2),
                "change_pct": round(pct, 2),
                "volume":     int(hist['Volume'].iloc[-1]),
                "high":       round(price, 2),
                "low":        round(price, 2),
                "shariah":    SHARIAH_STATUS.get(symbol, False),
                "timestamp":  datetime.now(PKT).isoformat(),
                "source":     "yfinance (delayed)",
                "market_open": is_psx_market_open(),
            })
        except:
            continue
    return results


# ── KSE-100 Index ───────────────────────────────────────────────────────────

def get_kse100():
    """Fetch KSE-100 index data from PSX timeseries API."""
    try:
        # Try the PSX timeseries API for the index
        url = "https://dps.psx.com.pk/timeseries/int/KSE100"
        resp = requests.get(url, headers=PSX_HEADERS, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == 1 and data.get("data"):
                trades = data["data"]
                current = float(trades[0][1])
                opening = float(trades[-1][1])
                change = current - opening
                change_pct = (change / opening * 100) if opening else 0
                return {
                    "value":      round(current, 2),
                    "change":     round(change, 2),
                    "change_pct": round(change_pct, 2),
                    "timestamp":  datetime.now(PKT).isoformat(),
                    "source":     "PSX Live",
                }
    except Exception as e:
        print(f"KSE-100 timeseries error: {e}")

    # Fallback: try scraping PSX homepage
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get("https://dps.psx.com.pk/", headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        el = soup.select_one(".kse100-value") or soup.select_one("[class*='index']")
        if el:
            text = el.get_text(strip=True).replace(",", "")
            val = float(''.join(c for c in text if c.isdigit() or c == '.'))
            return {"value": val, "change": 0, "change_pct": 0,
                    "timestamp": datetime.now(PKT).isoformat(), "source": "PSX Web"}
    except Exception as e:
        print(f"KSE-100 scrape error: {e}")

    # Fallback: yfinance
    try:
        ticker = yf.Ticker("^KSE100")
        hist = ticker.history(period="2d", interval="1d")
        if not hist.empty:
            val = float(hist['Close'].iloc[-1])
            prev = float(hist['Close'].iloc[-2]) if len(hist) > 1 else val
            return {
                "value": round(val, 2),
                "change": round(val - prev, 2),
                "change_pct": round((val - prev) / prev * 100, 2) if prev else 0,
                "timestamp": datetime.now(PKT).isoformat(),
                "source": "yfinance",
            }
    except:
        pass

    return {"value": None, "change": 0, "change_pct": 0,
            "timestamp": datetime.now(PKT).isoformat(), "source": "unavailable"}


# ── PKR / USD Rate ──────────────────────────────────────────────────────────

def get_pkr_usd():
    try:
        ticker = yf.Ticker("PKR=X")
        hist = ticker.history(period="2d", interval="5m")
        if not hist.empty:
            rate    = float(hist['Close'].iloc[-1])
            prev    = float(hist['Close'].iloc[0])
            change  = rate - prev
            pct     = (change / prev) * 100
            return {
                "rate":       round(rate, 2),
                "change":     round(change, 4),
                "change_pct": round(pct, 2),
                "timestamp":  datetime.now(PKT).isoformat()
            }
    except Exception as e:
        print(f"PKR rate error: {e}")
    return None
