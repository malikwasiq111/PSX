"""
PSX Technical Analysis Module
Computes RSI, MACD, Bollinger Bands, Moving Averages, Support/Resistance,
Volume Analysis, and composite tech signals using yfinance historical data
+ PSX real-time intraday data.
"""

import time, math, threading, logging, requests
import numpy as np
from datetime import datetime, timezone, timedelta

PKT = timezone(timedelta(hours=5))


def _safe_round(val, dec=2):
    try:
        return round(float(val), dec)
    except (TypeError, ValueError):
        return 0


log = logging.getLogger("psx.tech")
BASE = "https://beta-restapi.sarmaaya.pk/api"
_cache, _lock, TTL = {}, threading.Lock(), 600


UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def _fetch_dps(symbol):
    """PSX's own public end-of-day feed: years of history for every listed symbol."""
    r = requests.get(f"https://dps.psx.com.pk/timeseries/eod/{symbol}", headers=UA, timeout=12)
    r.raise_for_status()
    j = r.json()
    rows = j.get("data", []) if isinstance(j, dict) else j
    out = []
    for x in rows:
        try:
            ts = int(x[0]); ts = ts // 1000 if ts > 1e11 else ts
            out.append((ts, float(x[1]), float(x[2] or 0)))
        except Exception:
            continue
    out = sorted(set(out))[-400:]
    return [datetime.fromtimestamp(ts, PKT).strftime("%Y-%m-%d") for ts, _, _ in out], [c for _, c, _ in out], [v for _, _, v in out]


def _fetch_sarmaaya(symbol):
    r = requests.get(f"{BASE}/stocks/price-history/{symbol}", params={"days": 365}, headers=UA, timeout=12)
    r.raise_for_status()
    rows = [x for x in (r.json().get("response") or []) if x.get("price") and x.get("date")]
    rows.sort(key=lambda x: str(x["date"]))
    return [str(x["date"])[:10] for x in rows], [float(x["price"]) for x in rows], [float(x.get("volume") or 0) for x in rows]


def _clean(o):
    """Make the result JSON-safe: numpy -> python, NaN/inf -> None."""
    if isinstance(o, dict): return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_clean(x) for x in o]
    if isinstance(o, np.bool_): return bool(o)
    if isinstance(o, np.integer): return int(o)
    if isinstance(o, (np.floating, float)):
        f = float(o); return f if math.isfinite(f) else None
    return o


def _yf_series(symbol):
    try:
        import yfinance as yf
        h = yf.Ticker(f"{symbol}.KA").history(period="1y", interval="1d")
        return [d.strftime("%Y-%m-%d") for d in h.index], h["Close"].astype(float).tolist(), h["Volume"].astype(float).tolist()
    except Exception:
        return [], [], []


def _label(s):
    return "STRONG BUY" if s >= 4 else "BUY" if s >= 2 else "STRONG SELL" if s <= -4 else "SELL" if s <= -2 else "HOLD"


def _score(c, v):
    """Composite score using ONLY data up to the last bar (no look-ahead)."""
    price = c[-1]
    rsi, rsi_sig = _compute_rsi(c)
    macd, sigl, hist, mcross = _compute_macd(c)
    ma20 = float(np.mean(c[-20:])); ma50 = float(np.mean(c[-50:])) if len(c) >= 50 else None
    if ma50 is not None:
        trend = "uptrend" if price > ma20 > ma50 else "downtrend" if price < ma20 < ma50 else "sideways"
    else:
        trend = "uptrend" if price > ma20 else "downtrend"
    xs = _detect_cross(c)
    bu, bl, bm, bp, bsig = _compute_bollinger(c)
    avg = float(np.mean(v[-20:])) if len(v) >= 20 else float(np.mean(v))
    vr = v[-1] / avg if avg > 0 else 1.0
    s = 2 if rsi < 30 else 1 if rsi < 40 else -2 if rsi > 70 else -1 if rsi > 60 else 0
    s += 2 if mcross == "bullish_cross" else -2 if mcross == "bearish_cross" else (1 if hist > 0 else -1)
    s += 1 if trend == "uptrend" else -1 if trend == "downtrend" else 0
    s += 1 if bp < 20 else -1 if bp > 80 else 0
    if vr >= 1.5 and len(c) > 1:
        s += 1 if c[-1] > c[-2] else -1 if c[-1] < c[-2] else 0
    s += 2 if xs == "golden_cross" else -2 if xs == "death_cross" else 0
    return dict(score=s, rsi=rsi, rsi_sig=rsi_sig, macd=macd, sigl=sigl, hist=hist, mcross=mcross, ma20=ma20, ma50=ma50,
                trend=trend, xs=xs, bu=bu, bl=bl, bm=bm, bp=bp, bsig=bsig, vr=vr)


def _backtest(c, v, horizon=10, warm=60):
    """What did this exact scoring rule do on THIS stock? Forward return after each signal day."""
    base, b = [], {"BUY": [], "SELL": [], "HOLD": []}
    for i in range(warm, len(c) - horizon):
        s = _score(c[:i + 1], v[:i + 1])["score"]
        r = (c[i + horizon] / c[i] - 1) * 100
        base.append(r); b["BUY" if s >= 2 else "SELL" if s <= -2 else "HOLD"].append(r)
    if len(base) < 30:
        return None
    def st(x, up):
        return {"n": len(x), "avg": round(float(np.mean(x)), 2) if x else None,
                "hit": round(100 * sum(1 for y in x if (y > 0 if up else y < 0)) / len(x), 1) if x else None}
    return {"horizon": horizon, "days": len(base), "baseline": round(float(np.mean(base)), 2),
            "BUY": st(b["BUY"], True), "SELL": st(b["SELL"], False), "HOLD": st(b["HOLD"], True)}


def _ma(c, k):
    return [None] * (k - 1) + [_safe_round(x) for x in np.convolve(c, np.ones(k) / k, "valid")] if len(c) >= k else [None] * len(c)


def _risk(c):
    """Return/volatility/drawdown stats from the price series."""
    r = np.diff(c) / c[:-1]
    ret = lambda k: round(float((c[-1] / c[-k - 1] - 1) * 100), 2) if len(c) > k else None
    dd = float((c / np.maximum.accumulate(c) - 1).min() * 100)
    return {"ret_1m": ret(21), "ret_3m": ret(63), "ret_6m": ret(126), "ret_1y": ret(250),
            "volatility": round(float(r.std() * np.sqrt(250) * 100), 1), "max_drawdown": round(dd, 1)}


def _analyze(symbol, dates, c, v):
    c, v = np.array(c, float), np.array(v, float)
    m = _score(c, v)
    sup, res = _compute_support_resistance(c, c, c, c[-1])
    return {
        "symbol": symbol, "bars": len(c), "last_date": dates[-1],
        "rsi": _safe_round(m["rsi"], 1), "rsi_signal": m["rsi_sig"],
        "macd": _safe_round(m["macd"]), "macd_signal": _safe_round(m["sigl"]), "macd_hist": _safe_round(m["hist"]), "macd_cross": m["mcross"],
        "ma20": _safe_round(m["ma20"]), "ma50": _safe_round(m["ma50"]) if m["ma50"] else None, "trend": m["trend"], "cross_signal": m["xs"],
        "bb_upper": _safe_round(m["bu"]), "bb_lower": _safe_round(m["bl"]), "bb_mid": _safe_round(m["bm"]), "bb_pct": _safe_round(m["bp"], 1), "bb_signal": m["bsig"],
        "supports": sup, "resistances": res,
        "volume_ratio": _safe_round(m["vr"], 1), "volume_surge": m["vr"] >= 1.5,
        "tech_score": m["score"], "tech_signal": _label(m["score"]), "tech_confidence": min(95, 50 + abs(m["score"]) * 6),
        "perf": _risk(c), "high52": _safe_round(c.max()), "low52": _safe_round(c.min()),
        "chart_data": [{"date": dates[i], "close": _safe_round(c[i]), "volume": int(v[i])} for i in range(len(c))],
        "ma20_chart": _ma(c, 20), "ma50_chart": _ma(c, 50),
        "backtest": _backtest(c, v) if len(c) >= 100 else None,
        "timestamp": datetime.now(PKT).isoformat(),
    }


def get_technical_analysis(symbol: str, force: bool = False):
    """Indicators for any stock. Cached 10 min. Returns None if there isn't enough history."""
    symbol, now = symbol.upper(), time.time()
    with _lock:
        hit = _cache.get(symbol)
    if hit and now - hit[0] < TTL and not force:
        return hit[1]
    best = ([], [], [])
    for name, fn in (("psx", _fetch_dps), ("sarmaaya", _fetch_sarmaaya), ("yfinance", _yf_series)):
        try:
            got = fn(symbol)
        except Exception as e:
            log.warning("history %s via %s: %s", symbol, name, e); continue
        if len(got[1]) > len(best[1]):
            best = got; log.info("history %s via %s: %d bars", symbol, name, len(got[1]))
        if len(best[1]) >= 120:
            break
    d, c, v = best
    res = _clean(_analyze(symbol, d, c, v)) if len(c) >= 35 else None
    with _lock:
        _cache[symbol] = (now, res)
    return res


# ── RSI Calculation ─────────────────────────────────────────────────────────

def _compute_rsi(closes, period=14):
    """Compute RSI using exponential moving average method."""
    if len(closes) < period + 1:
        return 50, "neutral"

    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    # Initial average
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    # Smoothed RSI
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        rsi = 100
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

    # Signal
    if rsi < 30:
        signal = "oversold"
    elif rsi < 40:
        signal = "approaching_oversold"
    elif rsi > 70:
        signal = "overbought"
    elif rsi > 60:
        signal = "approaching_overbought"
    else:
        signal = "neutral"

    return rsi, signal


# ── MACD Calculation ────────────────────────────────────────────────────────

def _compute_macd(closes, fast=12, slow=26, signal_period=9):
    """Compute MACD line, signal line, histogram, and cross detection."""
    if len(closes) < slow + signal_period:
        return 0, 0, 0, "neutral"

    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)

    macd_line_arr = ema_fast - ema_slow
    signal_arr = _ema(macd_line_arr, signal_period)

    macd_val   = macd_line_arr[-1]
    signal_val = signal_arr[-1]
    hist_val   = macd_val - signal_val

    # Cross detection (last 3 bars)
    if len(macd_line_arr) >= 3 and len(signal_arr) >= 3:
        prev_diff = macd_line_arr[-2] - signal_arr[-2]
        curr_diff = macd_line_arr[-1] - signal_arr[-1]
        if prev_diff <= 0 and curr_diff > 0:
            cross = "bullish_cross"
        elif prev_diff >= 0 and curr_diff < 0:
            cross = "bearish_cross"
        elif curr_diff > 0:
            cross = "bullish_momentum"
        else:
            cross = "bearish_momentum"
    else:
        cross = "neutral"

    return macd_val, signal_val, hist_val, cross


def _ema(data, period):
    """Exponential Moving Average."""
    arr = np.array(data, dtype=float)
    ema = np.zeros_like(arr)
    ema[0] = arr[0]
    multiplier = 2 / (period + 1)
    for i in range(1, len(arr)):
        ema[i] = (arr[i] - ema[i-1]) * multiplier + ema[i-1]
    return ema


# ── Bollinger Bands ─────────────────────────────────────────────────────────

def _compute_bollinger(closes, period=20, std_dev=2):
    """Compute Bollinger Bands and price position."""
    if len(closes) < period:
        mid = closes[-1]
        return mid * 1.02, mid * 0.98, mid, 50, "neutral"

    window = closes[-period:]
    mid = np.mean(window)
    std = np.std(window)
    upper = mid + std_dev * std
    lower = mid - std_dev * std

    current = closes[-1]
    band_width = upper - lower
    if band_width > 0:
        pct = ((current - lower) / band_width) * 100
    else:
        pct = 50

    pct = max(0, min(100, pct))

    if pct < 10:
        signal = "strongly_oversold"
    elif pct < 25:
        signal = "near_lower_band"
    elif pct > 90:
        signal = "strongly_overbought"
    elif pct > 75:
        signal = "near_upper_band"
    else:
        signal = "mid_band"

    return upper, lower, mid, pct, signal


# ── Golden Cross / Death Cross ──────────────────────────────────────────────

def _detect_cross(closes):
    """Detect Golden Cross (MA20 crosses above MA50) or Death Cross."""
    if len(closes) < 51:
        return None

    # Current MAs
    ma20_now = np.mean(closes[-20:])
    ma50_now = np.mean(closes[-50:])
    # Previous day MAs
    ma20_prev = np.mean(closes[-21:-1])
    ma50_prev = np.mean(closes[-51:-1])

    if ma20_prev <= ma50_prev and ma20_now > ma50_now:
        return "golden_cross"
    elif ma20_prev >= ma50_prev and ma20_now < ma50_now:
        return "death_cross"

    return None


# ── Support & Resistance ────────────────────────────────────────────────────

def _compute_support_resistance(closes, highs, lows, current_price):
    """Find support and resistance levels from recent price pivots."""
    supports = []
    resistances = []

    if len(closes) < 10:
        return supports, resistances

    # Look at recent 60 days of lows for support, highs for resistance
    window = min(60, len(closes))
    recent_lows = lows[-window:]
    recent_highs = highs[-window:]

    # Find local minima (supports)
    for i in range(2, len(recent_lows) - 2):
        if (recent_lows[i] < recent_lows[i-1] and
            recent_lows[i] < recent_lows[i-2] and
            recent_lows[i] < recent_lows[i+1] and
            recent_lows[i] < recent_lows[i+2] and
            recent_lows[i] < current_price):
            supports.append(_safe_round(recent_lows[i]))

    # Find local maxima (resistances)
    for i in range(2, len(recent_highs) - 2):
        if (recent_highs[i] > recent_highs[i-1] and
            recent_highs[i] > recent_highs[i-2] and
            recent_highs[i] > recent_highs[i+1] and
            recent_highs[i] > recent_highs[i+2] and
            recent_highs[i] > current_price):
            resistances.append(_safe_round(recent_highs[i]))

    # Deduplicate (within 1% of each other)
    supports = _deduplicate_levels(sorted(supports, reverse=True)[:5])
    resistances = _deduplicate_levels(sorted(resistances)[:5])

    return supports[:3], resistances[:3]


def _deduplicate_levels(levels):
    """Remove levels that are too close together (within 1%)."""
    if not levels:
        return []
    result = [levels[0]]
    for level in levels[1:]:
        if abs(level - result[-1]) / result[-1] > 0.01:
            result.append(level)
    return result