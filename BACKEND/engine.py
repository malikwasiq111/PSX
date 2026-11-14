"""Rule-based analysis engine. Replaces Gemini: free, instant, deterministic."""
BUY = ("BUY", "STRONG BUY")

def _label(total):
    return ("STRONG BUY" if total >= 5 else "BUY" if total >= 2 else
            "STRONG SELL" if total <= -5 else "SELL" if total <= -2 else "HOLD")

def analyze_single_stock(symbol, stock, news, tech=None):
    price = stock.get("price") or 0
    if not tech:
        return {"available": False, "signal": "NO DATA", "confidence": 0, "reasoning": "Not enough price history to compute indicators for this stock.",
                "technical_summary": "", "news_summary": "", "risk_level": "—", "key_risk": "", "engine": "rules"}
    ns = sum({"positive": 1, "negative": -1}.get(n.get("sentiment"), 0) for n in news[:6])
    total = tech.get("tech_score", 0) + max(-2, min(2, ns))
    sig = _label(total)
    sup, res = tech.get("supports") or [], tech.get("resistances") or []
    up = sig in BUY
    target = res[0] if (up and res) else round(price * (1.08 if up else 0.92), 2)
    stop = sup[0] if (up and sup) else round(price * (0.95 if up else 1.05), 2)
    vol = abs(stock.get("change_pct", 0))
    risk = "High" if vol > 4 else "Medium" if vol > 2 else "Low"
    bits = []
    if tech:
        bits.append(f"RSI {tech.get('rsi')} ({tech.get('rsi_signal','').replace('_',' ')})")
        bits.append(f"{tech.get('trend','')} trend, MACD {tech.get('macd_cross','').replace('_',' ')}")
    return {
        "signal": sig, "confidence": min(90, 45 + abs(total) * 6),
        "entry_price": price, "target_price": target, "stop_loss": stop,
        "holding_period": "2-4 weeks" if abs(total) >= 2 else "Wait for setup",
        "reasoning": f"Composite score {total:+d} from technicals ({tech.get('tech_score', 0):+d}) and news ({ns:+d}).",
        "technical_summary": "; ".join(bits) or "Not enough price history.",
        "news_summary": f"{sum(1 for n in news if n.get('sentiment')=='positive')} positive / "
                        f"{sum(1 for n in news if n.get('sentiment')=='negative')} negative headlines",
        "risk_level": risk, "key_risk": "Day move above 4%" if risk == "High" else "General market risk",
        "score": total, "engine": "rules", "available": True,
    }

def analyze_overall_market(news, kse, pkr, stocks=None, sectors=None):
    stocks, sectors = stocks or [], sectors or []
    up = sum(1 for s in stocks if s.get("change_pct", 0) > 0)
    dn = sum(1 for s in stocks if s.get("change_pct", 0) < 0)
    breadth = (up - dn) / max(1, up + dn)
    nsent = sum({"positive": 1, "negative": -1}.get(n.get("sentiment"), 0) for n in news[:30]) / max(1, min(30, len(news)))
    idx = (kse or {}).get("change_pct", 0) or 0
    score = round(max(-100, min(100, breadth * 50 + nsent * 25 + idx * 10)))
    label = "Bullish" if score > 15 else "Bearish" if score < -15 else "Neutral"
    ranked = sorted(sectors, key=lambda s: s.get("change_pct", 0), reverse=True)
    return {
        "overall_sentiment": label, "sentiment_score": score,
        "summary": f"{up} advancers vs {dn} decliners. KSE-100 {idx:+.2f}%. News tone is "
                   f"{'positive' if nsent > .1 else 'negative' if nsent < -.1 else 'mixed'}.",
        "key_drivers": [n["title"] for n in news[:3]],
        "hot_sectors": [s["sector"] for s in ranked[:3] if s.get("change_pct", 0) > 0],
        "weak_sectors": [s["sector"] for s in ranked[-3:][::-1] if s.get("change_pct", 0) < 0],
        "market_advice": "Momentum favours buyers; trail stops." if label == "Bullish" else
                         "Defensive tone; reduce position sizes." if label == "Bearish" else "Stay selective.",
        "watch_out": "Index and breadth disagree." if (idx > 0) != (breadth > 0) else "No divergence.",
        "advancers": up, "decliners": dn, "engine": "rules",
    }

def portfolio_advice(portfolio, news, tech_cache=None):
    hs, tech_cache = portfolio.get("holdings", []), tech_cache or {}
    if not hs:
        return {"summary": "Add holdings to get advice.", "actions": [], "health_score": 0, "overall_health": "N/A"}
    tot = sum(h.get("current_value") or h["invested"] for h in hs) or 1
    top = max(hs, key=lambda h: h.get("current_value") or h["invested"])
    topw = (top.get("current_value") or top["invested"]) / tot * 100
    secs = {h.get("sector") for h in hs if h.get("sector")}
    score = 70 - max(0, topw - 30) * .8 + min(len(secs), 5) * 4 + max(-15, min(15, portfolio["summary"]["total_pnl_pct"] / 2))
    score = round(max(5, min(98, score)))
    acts = []
    for h in hs:
        sg = (tech_cache.get(h["symbol"]) or {}).get("tech_signal", "HOLD")
        p = h.get("pnl_pct") or 0
        a = "REDUCE" if sg in ("SELL", "STRONG SELL") and p > 0 else "EXIT" if sg == "STRONG SELL" else \
            "ADD MORE" if sg in BUY and p < 15 else "HOLD"
        acts.append({"symbol": h["symbol"], "action": a, "reason": f"Technical signal {sg}, P&L {p:+.1f}%"})
    return {"overall_health": "Excellent" if score > 80 else "Good" if score > 60 else "Fair" if score > 40 else "Poor",
            "health_score": score, "summary": f"{len(hs)} holdings across {len(secs)} sectors; largest position {top['symbol']} is {topw:.0f}% of value.",
            "actions": acts, "diversification_tip": "Keep any single stock under ~25-30%." if topw > 30 else "Concentration looks reasonable.",
            "risk_warning": f"{top['symbol']} dominates the portfolio." if topw > 40 else None}
