"""
PSX AI Analyst — Alerts Engine (Phase 4)
Price alerts, signal change alerts, volume surge alerts, news alerts.
Stored in alerts.json, checked every 30 seconds.
Browser notifications sent via frontend polling.
"""

import json
import os
from datetime import datetime

ALERTS_FILE = os.path.join(os.path.dirname(__file__), "alerts.json")

# ── File I/O ──────────────────────────────────────────────────────────────────

def _load() -> dict:
    if not os.path.exists(ALERTS_FILE):
        return {"alerts": [], "triggered": []}
    try:
        with open(ALERTS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"alerts": [], "triggered": []}

def _save(data: dict):
    with open(ALERTS_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── CRUD ──────────────────────────────────────────────────────────────────────

def add_alert(symbol: str, alert_type: str, condition: str,
              target_value: float, note: str = "") -> dict:
    """
    Add a new alert.

    alert_type: 'price_above' | 'price_below' | 'signal_change' | 'volume_surge' |
                'percent_move' | 'news_alert'
    condition:  'above' | 'below' | 'any' | 'bullish' | 'bearish' | 'positive' | 'negative'
    target_value: price level or 0 for signal/volume/news alerts
    """
    data   = _load()
    alerts = data.get("alerts", [])

    alert = {
        "id":           len(alerts) + 1,
        "symbol":       symbol.upper(),
        "type":         alert_type,
        "condition":    condition,
        "target_value": target_value,
        "note":         note,
        "active":       True,
        "triggered":    False,
        "created_at":   datetime.now().isoformat(),
        "triggered_at": None,
    }
    alerts.append(alert)
    data["alerts"] = alerts
    _save(data)
    return alert


def get_alerts(active_only: bool = False) -> list:
    data = _load()
    alerts = data.get("alerts", [])
    if active_only:
        return [a for a in alerts if a.get("active") and not a.get("triggered")]
    return alerts


def delete_alert(alert_id: int) -> bool:
    data   = _load()
    before = len(data.get("alerts", []))
    data["alerts"] = [a for a in data.get("alerts", []) if a["id"] != alert_id]
    _save(data)
    return len(data["alerts"]) < before


def get_triggered_alerts() -> list:
    data = _load()
    return data.get("triggered", [])[-20:]  # last 20


def clear_triggered() -> bool:
    data = _load()
    data["triggered"] = []
    _save(data)
    return True


# ── Alert Checking Engine ─────────────────────────────────────────────────────

def check_alerts(live_stocks: list, stock_signals: dict, news_items: list = None) -> list:
    """
    Check all active alerts against live data.
    Returns list of newly triggered alerts.
    Now supports news_alert type that fires when major news breaks.
    """
    data       = _load()
    alerts     = data.get("alerts", [])
    triggered  = data.get("triggered", [])
    newly_triggered = []

    price_map  = {s["symbol"]: s for s in live_stocks}
    if news_items is None:
        news_items = []

    for alert in alerts:
        if not alert.get("active") or alert.get("triggered"):
            continue

        symbol = alert["symbol"]
        stock  = price_map.get(symbol)
        if not stock and alert["type"] != "news_alert":
            continue

        fired      = False
        fire_msg   = ""
        atype      = alert["type"]
        target     = alert.get("target_value", 0)
        price      = stock.get("price", 0) if stock else 0
        change_pct = stock.get("change_pct", 0) if stock else 0

        # ── Price Alerts ──────────────────────────────────────────────
        if atype == "price_above" and price >= target:
            fired    = True
            fire_msg = f"🎯 {symbol} hit ₨{price:.2f} — above your target of ₨{target:.2f}"

        elif atype == "price_below" and price <= target:
            fired    = True
            fire_msg = f"⚠️ {symbol} dropped to ₨{price:.2f} — below your target of ₨{target:.2f}"

        # ── Volume Surge Alert ────────────────────────────────────────
        elif atype == "volume_surge" and stock:
            vol = stock.get("volume", 0)
            avg = stock.get("avg_volume", 0)
            if avg and vol > avg * 2:
                fired    = True
                fire_msg = f"🔥 {symbol} volume surge — {vol:,} vs avg {avg:,} (2x+ average)"

        # ── Percent Move Alert ────────────────────────────────────────
        elif atype == "percent_move":
            if abs(change_pct) >= target:
                direction = "📈 UP" if change_pct > 0 else "📉 DOWN"
                fired    = True
                fire_msg = f"{direction} {symbol} moved {change_pct:+.2f}% today — your threshold was {target:.1f}%"

        # ── Signal Change Alert ───────────────────────────────────────
        elif atype == "signal_change":
            sig = stock_signals.get(symbol, "")
            if isinstance(sig, dict):
             sig = sig.get("signal", "")
            if sig in ("BUY", "STRONG BUY") and alert.get("condition") in ("bullish", "any"):
                fired    = True
                fire_msg = f"🟢 {symbol} AI signal: {sig} — Bullish signal detected!"
            elif sig in ("SELL", "STRONG SELL") and alert.get("condition") in ("bearish", "any"):
                fired    = True
                fire_msg = f"🔴 {symbol} AI signal: {sig} — Bearish signal, consider action!"

        # ── News Alert ────────────────────────────────────────────────
        elif atype == "news_alert":
            condition = alert.get("condition", "any")
            related = [n for n in news_items if symbol in n.get("related_stocks", [])]
            for n in related[:3]:
                sentiment = n.get("sentiment", "neutral")
                if condition == "any" and sentiment != "neutral":
                    fired = True
                    fire_msg = f"📰 {symbol} NEWS: {n['title'][:80]}"
                    break
                elif condition == "positive" and sentiment == "positive":
                    fired = True
                    fire_msg = f"📈 {symbol} POSITIVE NEWS: {n['title'][:80]}"
                    break
                elif condition == "negative" and sentiment == "negative":
                    fired = True
                    fire_msg = f"📉 {symbol} NEGATIVE NEWS: {n['title'][:80]}"
                    break

        if fired:
            alert["triggered"]    = True
            alert["triggered_at"] = datetime.now().isoformat()
            triggered_entry = {
                "id":           alert["id"],
                "symbol":       symbol,
                "type":         atype,
                "message":      fire_msg,
                "price_at_trigger": price,
                "triggered_at": datetime.now().isoformat(),
            }
            triggered.append(triggered_entry)
            newly_triggered.append(triggered_entry)

    data["alerts"]    = alerts
    data["triggered"] = triggered[-50:]  # keep last 50
    _save(data)
    return newly_triggered