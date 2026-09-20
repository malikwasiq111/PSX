"""
PSX AI Analyst — Chat Assistant (Phase 5)
Conversational AI assistant powered by Gemini that acts as an
experienced PSX stock market analyst. Has access to live market
data, portfolio, signals, and news to provide informed answers.
"""

import json
from datetime import datetime
from google import genai

import os
from dotenv import load_dotenv
load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL  = "gemini-2.5-flash"

# Conversation history per session (in-memory)
_conversation_history = []
MAX_HISTORY = 30  # keep last 30 messages

SYSTEM_PROMPT = """You are **PSX Pro**, an elite Pakistan Stock Exchange (PSX) analyst with 15+ years of experience in Pakistani capital markets. You work as the AI assistant inside the "PSX AI Analyst" platform.

## Your Persona
- You're confident, professional yet friendly — like a trusted financial advisor
- You speak in clear, concise language with actionable insights  
- Use ₨ for PKR amounts, proper financial terminology
- You're deeply knowledgeable about Pakistani markets: KSE-100, sectors (banking, cement, energy, fertilizer, tech, pharma), macro factors (SBP rates, IMF, PKR/USD, inflation)
- You reference technical indicators (RSI, MACD, Bollinger Bands, S/R levels) when relevant
- You understand Shariah-compliant investing and can advise on halal stocks

## Your Capabilities
- Analyze specific stocks using live price data, technical indicators, and AI signals  
- Give portfolio advice based on user's actual holdings
- Explain market sentiment and sector trends
- Discuss dividend opportunities and corporate announcements
- Provide entry/exit strategies with risk management
- Compare stocks within sectors
- Explain complex financial concepts simply

## Rules
1. Always provide balanced analysis — mention both upside AND risks
2. Include specific price levels when discussing stocks (support, resistance, targets)
3. When asked about a specific stock, reference its current price, change%, signal, and sector
4. Add disclaimers when giving specific buy/sell advice: "This is AI analysis, not financial advice"
5. Use emojis sparingly for clarity: 📈📉🟢🔴⚠️💡🎯
6. Keep responses focused and under 300 words unless deep analysis is requested
7. If you don't have data on something, say so honestly
8. Reference Pakistani market specifics: PSX trading hours (9:30-3:30), T+2 settlement, circuit breakers

## Response Format
- Use **bold** for key terms and stock symbols
- Use bullet points for multi-point analysis
- End actionable responses with a clear recommendation or next step
"""


def _build_context(cache: dict, portfolio_data: dict = None) -> str:
    """Build context string from live market data for the AI."""
    parts = []

    # Market overview
    kse = cache.get("kse100")
    if kse:
        parts.append(f"📊 KSE-100 Index: {kse.get('value', 'N/A')} ({kse.get('change_pct', 0):+.2f}%)")

    pkr = cache.get("pkr")
    if pkr:
        parts.append(f"💱 USD/PKR: {pkr.get('rate', 'N/A')} ({pkr.get('change_pct', 0):+.2f}%)")

    ma = cache.get("market_analysis")
    if ma:
        parts.append(f"🎯 Market Sentiment: {ma.get('overall_sentiment', 'N/A')} (Score: {ma.get('sentiment_score', 0)})")
        if ma.get("summary"):
            parts.append(f"Market Summary: {ma['summary']}")
        if ma.get("hot_sectors"):
            parts.append(f"🔥 Hot Sectors: {', '.join(ma['hot_sectors'])}")
        if ma.get("weak_sectors"):
            parts.append(f"❄️ Weak Sectors: {', '.join(ma['weak_sectors'])}")

    # Top movers
    stocks = cache.get("stocks", [])
    if stocks:
        gainers = sorted(stocks, key=lambda s: s.get("change_pct", 0), reverse=True)[:5]
        losers = sorted(stocks, key=lambda s: s.get("change_pct", 0))[:5]
        parts.append(f"\n📈 Top Gainers: " + ", ".join(
            f"{s['symbol']} ({s.get('change_pct', 0):+.2f}%)" for s in gainers))
        parts.append(f"📉 Top Losers: " + ", ".join(
            f"{s['symbol']} ({s.get('change_pct', 0):+.2f}%)" for s in losers))
        parts.append(f"Total stocks tracked: {len(stocks)}")

    # Recent news headlines
    news = cache.get("news", [])
    if news:
        parts.append(f"\n📰 Recent News ({len(news)} articles):")
        for n in news[:5]:
            parts.append(f"  - [{n.get('sentiment', 'neutral').upper()}] {n.get('title', '')[:80]}")

    # Portfolio context
    if portfolio_data and portfolio_data.get("holdings"):
        holdings = portfolio_data["holdings"]
        summary = portfolio_data.get("summary", {})
        parts.append(f"\n💼 User Portfolio ({len(holdings)} holdings):")
        parts.append(f"  Invested: ₨{summary.get('total_invested', 0):,.0f} | Current: ₨{summary.get('total_current', 0):,.0f} | P&L: {summary.get('total_pnl_pct', 0):.2f}%")
        for h in holdings[:10]:
            parts.append(f"  - {h['symbol']}: {h['shares']} shares @ ₨{h.get('buy_price', 0):.2f} → ₨{h.get('current_price', 'N/A')} (P&L: {h.get('pnl_pct', 0):.1f}%)")

    # Announcements
    anns = cache.get("announcements", [])
    if anns:
        parts.append(f"\n📢 Recent Announcements ({len(anns)}):")
        for a in anns[:5]:
            parts.append(f"  - {a.get('symbol', '?')}: {a.get('title', '')[:60]} ({a.get('type_label', '')})")

    return "\n".join(parts)


def _get_stock_context(symbol: str, cache: dict, signals: dict, tech_cache: dict) -> str:
    """Get detailed context for a specific stock."""
    stock = next((s for s in cache.get("stocks", []) if s["symbol"] == symbol), None)
    if not stock:
        return f"No live data available for {symbol}."

    parts = [
        f"\n--- {symbol} Detail ---",
        f"Price: ₨{stock.get('price', 0):.2f} | Change: {stock.get('change_pct', 0):+.2f}%",
        f"High: ₨{stock.get('high', 'N/A')} | Low: ₨{stock.get('low', 'N/A')} | Volume: {stock.get('volume', 'N/A')}",
        f"Sector: {stock.get('sector', 'N/A')} | Shariah: {'Yes ✓' if stock.get('shariah') else 'No'}",
    ]

    sig = signals.get(symbol, {})
    if sig:
        parts.extend([
            f"AI Signal: {sig.get('signal', 'N/A')} (Confidence: {sig.get('confidence', 0)}%)",
            f"Entry: ₨{sig.get('entry_price', 'N/A')} | Target: ₨{sig.get('target_price', 'N/A')} | Stop Loss: ₨{sig.get('stop_loss', 'N/A')}",
            f"Risk: {sig.get('risk_level', 'N/A')} | Hold Period: {sig.get('holding_period', 'N/A')}",
            f"Reasoning: {sig.get('reasoning', 'N/A')[:200]}",
        ])

    tech = tech_cache.get(symbol, {})
    if tech:
        parts.extend([
            f"RSI: {tech.get('rsi', 'N/A')} ({tech.get('rsi_signal', '')}) | MACD: {tech.get('macd', 'N/A')} ({tech.get('macd_cross', '')})",
            f"Trend: {tech.get('trend', 'N/A')} | BB Position: {tech.get('bb_pct', 'N/A')}% | Tech Score: {tech.get('tech_score', 'N/A')}/8",
        ])

    return "\n".join(parts)


def _detect_stock_mentions(message: str, stocks: list) -> list:
    """Detect stock symbols mentioned in the user's message."""
    msg_upper = message.upper()
    mentioned = []
    for s in stocks:
        if s["symbol"] in msg_upper:
            mentioned.append(s["symbol"])
    # Also check common names
    name_map = {
        "lucky": "LUCK", "engro": "ENGRO", "hub power": "HUBC", "hubco": "HUBC",
        "meezan": "MEBL", "habib bank": "HBL", "habib": "HBL", "mcb": "MCB",
        "united bank": "UBL", "systems": "SYS", "nestle": "NESTLE", "ogdc": "OGDC",
        "ppl": "PPL", "pso": "PSO", "ffc": "FFC", "searle": "SEARL",
        "indus motor": "INDU", "toyota": "INDU", "honda": "HCAR", "suzuki": "PSMC",
        "fauji fertilizer": "FFC", "bank alfalah": "BAFL", "bank al habib": "BAHL",
        "mari": "MARI", "nishat": "NML", "colgate": "COLG", "unilever": "UPFL",
        "interloop": "ILP", "packages": "PKGS", "mughal": "MUGHAL",
        "cement": None, "bank": None, "oil": None,  # sector queries, not individual
    }
    for name, sym in name_map.items():
        if name in message.lower() and sym and sym not in mentioned:
            mentioned.append(sym)
    return mentioned[:5]  # cap at 5


async def chat(message: str, cache: dict, signals: dict = None,
               tech_cache: dict = None, portfolio_data: dict = None) -> dict:
    """
    Process a user chat message and return AI analyst response.
    """
    global _conversation_history
    if signals is None:
        signals = {}
    if tech_cache is None:
        tech_cache = {}

    # Build context
    market_context = _build_context(cache, portfolio_data)

    # Detect stock mentions and add specific context
    mentioned = _detect_stock_mentions(message, cache.get("stocks", []))
    stock_context = ""
    for sym in mentioned:
        stock_context += _get_stock_context(sym, cache, signals, tech_cache)

    # Build conversation for Gemini
    context_message = f"""LIVE MARKET DATA (as of {cache.get('last_updated', 'now')}):
{market_context}
{stock_context}

Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} PKT
PSX Trading Hours: 9:30 AM - 3:30 PM PKT, Mon-Fri"""

    # Build messages list
    messages = []

    # Add recent conversation history for continuity
    for h in _conversation_history[-10:]:
        messages.append(h)

    # Add current user message with context
    user_msg = f"{message}\n\n[CONTEXT FOR AI - DO NOT REPEAT THIS TO USER]\n{context_message}"
    messages.append({"role": "user", "parts": [{"text": user_msg}]})

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=messages,
            config={
                "system_instruction": SYSTEM_PROMPT,
                "temperature": 0.7,
                "max_output_tokens": 1500,
            }
        )

        reply = response.text or "I apologize, I couldn't generate a response. Please try again."

        # Store in history (clean version without context)
        _conversation_history.append({"role": "user", "parts": [{"text": message}]})
        _conversation_history.append({"role": "model", "parts": [{"text": reply}]})

        # Trim history
        if len(_conversation_history) > MAX_HISTORY * 2:
            _conversation_history = _conversation_history[-(MAX_HISTORY * 2):]

        return {
            "reply": reply,
            "mentioned_stocks": mentioned,
            "timestamp": datetime.now().isoformat(),
            "success": True,
        }

    except Exception as e:
        print(f"Chat error: {e}")
        return {
            "reply": f"I'm having trouble connecting right now. Error: {str(e)[:100]}. Please try again in a moment.",
            "mentioned_stocks": mentioned,
            "timestamp": datetime.now().isoformat(),
            "success": False,
        }


def clear_chat_history():
    """Clear conversation history."""
    global _conversation_history
    _conversation_history = []
    return True


def get_chat_history() -> list:
    """Return the chat history."""
    return [
        {"role": h["role"], "text": h["parts"][0]["text"]}
        for h in _conversation_history
    ]