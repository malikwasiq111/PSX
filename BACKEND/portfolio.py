import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "portfolio.json")


# ── File I/O ─────────────────────────────────────────────────────────────────

def _load() -> dict:
    if not os.path.exists(PORTFOLIO_FILE):
        return {"holdings": [], "created_at": datetime.now().isoformat()}
    with open(PORTFOLIO_FILE, "r") as f:
        return json.load(f)


def _save(data: dict):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── CRUD ─────────────────────────────────────────────────────────────────────

def get_holdings() -> list:
    return _load().get("holdings", [])


def add_holding(symbol: str, shares: float, buy_price: float, buy_date: str = None) -> dict:
    """Add or update a holding."""
    symbol = symbol.upper()
    data   = _load()
    holdings = data.get("holdings", [])

    # Check if symbol already exists → update
    for h in holdings:
        if h["symbol"] == symbol:
            h["shares"]    = shares
            h["buy_price"] = buy_price
            h["buy_date"]  = buy_date or h.get("buy_date", datetime.now().strftime("%Y-%m-%d"))
            h["updated_at"] = datetime.now().isoformat()
            _save(data)
            return h

    # New holding
    holding = {
        "symbol":     symbol,
        "shares":     shares,
        "buy_price":  buy_price,
        "buy_date":   buy_date or datetime.now().strftime("%Y-%m-%d"),
        "added_at":   datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    holdings.append(holding)
    data["holdings"] = holdings
    _save(data)
    return holding


def remove_holding(symbol: str) -> bool:
    symbol = symbol.upper()
    data   = _load()
    before = len(data.get("holdings", []))
    data["holdings"] = [h for h in data.get("holdings", []) if h["symbol"] != symbol]
    _save(data)
    return len(data["holdings"]) < before


# ── Calculations ─────────────────────────────────────────────────────────────

def calculate_portfolio(live_stocks: list) -> dict:
    """
    Merge holdings with live prices and compute P&L.
    live_stocks = list from cache["stocks"]
    """
    holdings  = get_holdings()
    price_map = {s["symbol"]: s for s in live_stocks}

    enriched        = []
    total_invested  = 0.0
    total_current   = 0.0

    for h in holdings:
        sym        = h["symbol"]
        shares     = h["shares"]
        buy_price  = h["buy_price"]
        live       = price_map.get(sym)

        invested   = shares * buy_price
        total_invested += invested

        if live:
            current_price = live["price"]
            current_val   = shares * current_price
            pnl           = current_val - invested
            pnl_pct       = (pnl / invested * 100) if invested else 0
            total_current += current_val

            enriched.append({
                "symbol":        sym,
                "name":          live.get("name", sym),
                "sector":        live.get("sector", ""),
                "shares":        shares,
                "buy_price":     buy_price,
                "current_price": current_price,
                "invested":      round(invested, 2),
                "current_value": round(current_val, 2),
                "pnl":           round(pnl, 2),
                "pnl_pct":       round(pnl_pct, 2),
                "today_change":  live.get("change_pct", 0),
                "shariah":       live.get("shariah", False),
                "buy_date":      h.get("buy_date", ""),
                "has_live_data": True,
            })
        else:
            # No live data — show invested only
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
        "holdings":       enriched,
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




# ── Daily value snapshots (powers the performance chart) ─────────────────────
HIST_FILE = os.path.join(os.path.dirname(__file__), "portfolio_history.json")

def snapshot(summary: dict):
    if not summary.get("total_current"):
        return
    try:
        h = json.load(open(HIST_FILE))
    except Exception:
        h = []
    rec = {"date": datetime.now().strftime("%Y-%m-%d"), "value": summary["total_current"], "invested": summary["total_invested"]}
    if h and h[-1]["date"] == rec["date"]:
        h[-1] = rec
    else:
        h.append(rec)
    json.dump(h[-730:], open(HIST_FILE, "w"))

def get_history() -> list:
    try:
        return json.load(open(HIST_FILE))
    except Exception:
        return []
