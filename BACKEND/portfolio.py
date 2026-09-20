import json
import os
from datetime import datetime
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL  = "gemini-2.5-flash"
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


# ── AI Portfolio Advice ───────────────────────────────────────────────────────

def get_ai_portfolio_advice(portfolio: dict, news_items: list) -> dict:
    """Ask Claude to review the whole portfolio and give advice."""
    holdings = portfolio.get("holdings", [])
    summary  = portfolio.get("summary", {})

    if not holdings:
        return {"advice": "Add holdings to your portfolio to receive AI advice.", "actions": []}

    holdings_text = "\n".join([
        f"- {h['symbol']} ({h.get('name','')}): "
        f"{h['shares']} shares @ PKR {h['buy_price']} buy, "
        f"now PKR {h.get('current_price','?')} | "
        f"P&L: {h.get('pnl_pct','?')}% | Today: {h.get('today_change','?')}%"
        for h in holdings
    ])

    # Recent negative news about portfolio stocks
    portfolio_syms = [h["symbol"] for h in holdings]
    relevant_news  = [n for n in news_items if any(s in n.get("related_stocks",[]) for s in portfolio_syms)]
    news_text = "\n".join(f"- [{n['sentiment'].upper()}] {n['title']}" for n in relevant_news[:6]) \
                or "No specific news about your holdings."

    prompt = f"""You are a PSX portfolio advisor. Review this investor's portfolio and give practical advice.

PORTFOLIO SUMMARY:
Total Invested: PKR {summary.get('total_invested', 0):,.0f}
Current Value:  PKR {summary.get('total_current', 0):,.0f}
Total P&L:      PKR {summary.get('total_pnl', 0):,.0f} ({summary.get('total_pnl_pct', 0):.2f}%)
Winners: {summary.get('winners', 0)} | Losers: {summary.get('losers', 0)}

HOLDINGS:
{holdings_text}

RECENT NEWS ABOUT HOLDINGS:
{news_text}

Give practical advice. Respond ONLY in valid JSON, no markdown:
{{
  "overall_health": "Good",
  "health_score": 72,
  "summary": "2 sentence portfolio assessment.",
  "actions": [
    {{"symbol": "OGDC", "action": "HOLD", "reason": "Short reason"}},
    {{"symbol": "LUCK", "action": "ADD MORE", "reason": "Short reason"}}
  ],
  "diversification_tip": "One tip about portfolio balance.",
  "risk_warning": "Main risk to watch or null if none."
}}

overall_health: Excellent / Good / Fair / Poor
health_score: 0-100
action per holding: HOLD / ADD MORE / REDUCE / EXIT / WATCH"""

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
        )
        raw = response.text.strip().replace("```json","").replace("```","").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"Portfolio AI error: {e}")
        return {
            "overall_health":     "Fair",
            "health_score":       50,
            "summary":            "Portfolio analysis temporarily unavailable.",
            "actions":            [],
            "diversification_tip": "Diversify across sectors for lower risk.",
            "risk_warning":       None
        }