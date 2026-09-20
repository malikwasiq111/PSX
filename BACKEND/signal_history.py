"""
PSX AI Analyst — Signal History Tracker (Phase 5)
Records every AI signal generated with timestamp and price.
Compares against current prices to calculate historical accuracy.
Stores data in signal_history.json.
"""

import json
import os
from datetime import datetime

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "signal_history.json")


def _load() -> dict:
    if not os.path.exists(HISTORY_FILE):
        return {"signals": [], "stats": {}}
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"signals": [], "stats": {}}


def _save(data: dict):
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=2)


def record_signal(symbol: str, signal: str, confidence: int,
                  price_at_signal: float, target_price: float,
                  stop_loss: float, reasoning: str = ""):
    """Record a new AI signal for historical tracking."""
    data = _load()
    signals = data.get("signals", [])

    # Avoid recording duplicate signals within 5 minutes
    for s in signals[-20:]:
        if (s["symbol"] == symbol and s["signal"] == signal and
            abs(s["price_at_signal"] - price_at_signal) < 0.5):
            time_diff = (datetime.now() - datetime.fromisoformat(s["timestamp"])).total_seconds()
            if time_diff < 300:
                return None  # skip duplicate

    entry = {
        "id":              len(signals) + 1,
        "symbol":          symbol.upper(),
        "signal":          signal,
        "confidence":      confidence,
        "price_at_signal": round(price_at_signal, 2),
        "target_price":    round(target_price, 2),
        "stop_loss":       round(stop_loss, 2),
        "reasoning":       reasoning[:200],
        "timestamp":       datetime.now().isoformat(),
        "outcome":         None,   # filled later when we check
        "current_price":   None,
        "return_pct":      None,
        "hit_target":      None,
        "hit_stop":        None,
    }
    signals.append(entry)
    data["signals"] = signals[-500:]  # keep last 500 signals
    _save(data)
    return entry


def update_outcomes(live_stocks: list):
    """Update all historical signals with current outcomes."""
    data = _load()
    signals = data.get("signals", [])
    price_map = {s["symbol"]: s["price"] for s in live_stocks}

    for sig in signals:
        if sig.get("outcome") == "closed":
            continue

        symbol = sig["symbol"]
        current = price_map.get(symbol)
        if not current:
            continue

        entry_price = sig["price_at_signal"]
        target = sig["target_price"]
        stop = sig["stop_loss"]

        sig["current_price"] = round(current, 2)
        sig["return_pct"] = round((current - entry_price) / entry_price * 100, 2)

        # Check if target or stop hit
        if sig["signal"] in ("BUY", "STRONG BUY"):
            if current >= target:
                sig["hit_target"] = True
                sig["outcome"] = "closed"
            elif current <= stop:
                sig["hit_stop"] = True
                sig["outcome"] = "closed"
            else:
                sig["outcome"] = "open"
                sig["hit_target"] = False
                sig["hit_stop"] = False
        elif sig["signal"] in ("SELL", "STRONG SELL"):
            if current <= target:
                sig["hit_target"] = True
                sig["outcome"] = "closed"
            elif current >= stop:
                sig["hit_stop"] = True
                sig["outcome"] = "closed"
            else:
                sig["outcome"] = "open"
                sig["hit_target"] = False
                sig["hit_stop"] = False
        else:  # HOLD
            sig["outcome"] = "open"

    data["signals"] = signals
    data["stats"] = _compute_stats(signals)
    _save(data)


def _compute_stats(signals: list) -> dict:
    """Compute aggregate stats on signal accuracy."""
    total = len(signals)
    if not total:
        return {"total": 0, "win_rate": 0, "avg_return": 0}

    closed = [s for s in signals if s.get("outcome") == "closed"]
    wins = [s for s in closed if s.get("hit_target")]
    losses = [s for s in closed if s.get("hit_stop")]

    all_returns = [s["return_pct"] for s in signals if s.get("return_pct") is not None]

    by_signal = {}
    for sig_type in ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]:
        subset = [s for s in signals if s["signal"] == sig_type]
        sub_returns = [s["return_pct"] for s in subset if s.get("return_pct") is not None]
        sub_wins = [s for s in subset if s.get("hit_target")]
        by_signal[sig_type] = {
            "count":      len(subset),
            "avg_return":  round(sum(sub_returns) / len(sub_returns), 2) if sub_returns else 0,
            "win_rate":    round(len(sub_wins) / len(subset) * 100, 1) if subset else 0,
        }

    return {
        "total_signals":   total,
        "closed_signals":  len(closed),
        "open_signals":    total - len(closed),
        "wins":            len(wins),
        "losses":          len(losses),
        "win_rate":        round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "avg_return":      round(sum(all_returns) / len(all_returns), 2) if all_returns else 0,
        "by_signal_type":  by_signal,
        "last_updated":    datetime.now().isoformat(),
    }


def get_signal_history(symbol: str = None, limit: int = 50) -> dict:
    """Get signal history with stats."""
    data = _load()
    signals = data.get("signals", [])

    if symbol:
        signals = [s for s in signals if s["symbol"] == symbol.upper()]

    # Most recent first
    signals = list(reversed(signals[-limit:]))

    return {
        "signals": signals,
        "stats":   data.get("stats", {}),
        "count":   len(signals),
    }


def get_accuracy_summary() -> dict:
    """Get just the accuracy stats for display."""
    data = _load()
    return data.get("stats", {
        "total_signals":  0,
        "win_rate":       0,
        "avg_return":     0,
        "by_signal_type": {},
    })
