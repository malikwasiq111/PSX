"""
PSX Technical Analysis Module
Computes RSI, MACD, Bollinger Bands, Moving Averages, Support/Resistance,
Volume Analysis, and composite tech signals using yfinance historical data
+ PSX real-time intraday data.
"""

import yfinance as yf
import numpy as np
from datetime import datetime, timezone, timedelta

PKT = timezone(timedelta(hours=5))


def _safe_round(val, dec=2):
    try:
        return round(float(val), dec)
    except:
        return 0


def get_technical_analysis(symbol: str, ticker_suffix: str = None) -> dict:
    """
    Full technical analysis for a stock.
    Returns dict with RSI, MACD, Bollinger Bands, MAs, S/R levels,
    volume analysis, composite score, chart data, and overall signal.
    """
    try:
        yf_symbol = ticker_suffix or f"{symbol}.KA"
        ticker = yf.Ticker(yf_symbol)

        # Get 90 days of daily data for indicators
        hist = ticker.history(period="90d", interval="1d")
        if hist.empty or len(hist) < 20:
            return None

        closes = hist['Close'].values.astype(float)
        highs  = hist['High'].values.astype(float)
        lows   = hist['Low'].values.astype(float)
        volumes = hist['Volume'].values.astype(float)
        dates  = [d.strftime("%Y-%m-%d") for d in hist.index]

        current_price = closes[-1]

        # ── RSI (14-period) ─────────────────────────────────────────────
        rsi_val, rsi_signal = _compute_rsi(closes, period=14)

        # ── MACD ────────────────────────────────────────────────────────
        macd_line, signal_line, histogram, macd_cross = _compute_macd(closes)

        # ── Moving Averages ─────────────────────────────────────────────
        ma20 = _safe_round(np.mean(closes[-20:])) if len(closes) >= 20 else _safe_round(current_price)
        ma50 = _safe_round(np.mean(closes[-50:])) if len(closes) >= 50 else None

        # MA20/MA50 chart arrays
        ma20_chart = []
        for i in range(len(closes)):
            if i >= 19:
                ma20_chart.append(_safe_round(np.mean(closes[i-19:i+1])))
            else:
                ma20_chart.append(None)

        ma50_chart = []
        if len(closes) >= 50:
            for i in range(len(closes)):
                if i >= 49:
                    ma50_chart.append(_safe_round(np.mean(closes[i-49:i+1])))
                else:
                    ma50_chart.append(None)

        # Trend detection
        if ma50 is not None:
            if current_price > ma20 and ma20 > ma50:
                trend = "uptrend"
            elif current_price < ma20 and ma20 < ma50:
                trend = "downtrend"
            else:
                trend = "sideways"
        else:
            trend = "uptrend" if current_price > ma20 else "downtrend"

        # Golden Cross / Death Cross detection
        cross_signal = _detect_cross(closes) if len(closes) >= 50 else None

        # ── Bollinger Bands ─────────────────────────────────────────────
        bb_upper, bb_lower, bb_mid, bb_pct, bb_signal = _compute_bollinger(closes)

        # ── Support & Resistance ────────────────────────────────────────
        supports, resistances = _compute_support_resistance(closes, highs, lows, current_price)

        # ── Volume Analysis ─────────────────────────────────────────────
        avg_vol = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)
        last_vol = volumes[-1]
        volume_ratio = _safe_round(last_vol / avg_vol, 1) if avg_vol > 0 else 1.0
        volume_surge = volume_ratio >= 1.5

        # ── Composite Score (-8 to +8) ──────────────────────────────────
        tech_score = 0
        # RSI
        if rsi_val < 30: tech_score += 2      # Oversold = bullish
        elif rsi_val < 40: tech_score += 1
        elif rsi_val > 70: tech_score -= 2    # Overbought = bearish
        elif rsi_val > 60: tech_score -= 1

        # MACD
        if macd_cross == "bullish_cross": tech_score += 2
        elif macd_cross == "bearish_cross": tech_score -= 2
        elif histogram > 0: tech_score += 1
        else: tech_score -= 1

        # Trend
        if trend == "uptrend": tech_score += 1
        elif trend == "downtrend": tech_score -= 1

        # Bollinger
        if bb_pct < 20: tech_score += 1       # Near lower band = bullish
        elif bb_pct > 80: tech_score -= 1     # Near upper band = bearish

        # Volume
        if volume_surge and closes[-1] > closes[-2]: tech_score += 1
        elif volume_surge and closes[-1] < closes[-2]: tech_score -= 1

        # Cross
        if cross_signal == "golden_cross": tech_score += 2
        elif cross_signal == "death_cross": tech_score -= 2

        # Overall signal
        if tech_score >= 4:
            tech_signal = "STRONG BUY"
        elif tech_score >= 2:
            tech_signal = "BUY"
        elif tech_score <= -4:
            tech_signal = "STRONG SELL"
        elif tech_score <= -2:
            tech_signal = "SELL"
        else:
            tech_signal = "HOLD"

        # Confidence
        tech_confidence = min(95, 50 + abs(tech_score) * 6)

        # ── Chart Data ──────────────────────────────────────────────────
        chart_data = []
        for i in range(len(closes)):
            chart_data.append({
                "date":   dates[i],
                "close":  _safe_round(closes[i]),
                "high":   _safe_round(highs[i]),
                "low":    _safe_round(lows[i]),
                "volume": int(volumes[i]),
            })

        return {
            "symbol":          symbol,
            # RSI
            "rsi":             _safe_round(rsi_val, 1),
            "rsi_signal":      rsi_signal,
            # MACD
            "macd":            _safe_round(macd_line),
            "macd_signal":     _safe_round(signal_line),
            "macd_hist":       _safe_round(histogram),
            "macd_cross":      macd_cross,
            # Moving Averages
            "ma20":            ma20,
            "ma50":            ma50,
            "trend":           trend,
            "cross_signal":    cross_signal,
            # Bollinger Bands
            "bb_upper":        _safe_round(bb_upper),
            "bb_lower":        _safe_round(bb_lower),
            "bb_mid":          _safe_round(bb_mid),
            "bb_pct":          _safe_round(bb_pct, 1),
            "bb_signal":       bb_signal,
            # Support & Resistance
            "supports":        supports,
            "resistances":     resistances,
            # Volume
            "volume_ratio":    volume_ratio,
            "volume_surge":    volume_surge,
            # Composite
            "tech_score":      tech_score,
            "tech_signal":     tech_signal,
            "tech_confidence": tech_confidence,
            # Chart
            "chart_data":      chart_data,
            "ma20_chart":      ma20_chart,
            "ma50_chart":      ma50_chart,
            "timestamp":       datetime.now(PKT).isoformat(),
        }

    except Exception as e:
        print(f"Technical analysis error for {symbol}: {e}")
        return None


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
