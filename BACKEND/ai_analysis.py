from google import genai
import os
import json
from dotenv import load_dotenv

load_dotenv()

# New google-genai SDK — single client instance
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Best model for fast, structured analysis tasks
MODEL = "gemini-2.5-flash"


def analyze_single_stock(symbol: str, stock: dict, news_items: list,
                         technical: dict = None, fundamentals: dict = None) -> dict:
    """Generate AI buy/sell/hold signal for a specific stock using price + news + technicals + fundamentals."""
    # Filter news relevant to this stock
    relevant = [n for n in news_items if symbol in n.get("related_stocks", [])]
    news_lines = "\n".join(
        f"- [{n['sentiment'].upper()}] {n['title']}" for n in relevant[:6]
    ) or "No specific recent news for this stock."

    # Technical indicators block
    tech_block = "Not available."
    if technical:
        tech_block = f"""RSI(14): {technical.get('rsi', 'N/A')} — {technical.get('rsi_signal', 'N/A')}
MACD: {technical.get('macd', 'N/A')} | Signal: {technical.get('macd_signal', 'N/A')} | Histogram: {technical.get('macd_hist', 'N/A')}
MACD Cross: {technical.get('macd_cross', 'N/A')}
Trend: {technical.get('trend', 'N/A')} | MA20: {technical.get('ma20', 'N/A')} | MA50: {technical.get('ma50', 'N/A')}
Bollinger: {technical.get('bb_signal', 'N/A')} | Position: {technical.get('bb_pct', 'N/A')}%
Support Levels: {technical.get('supports', [])}
Resistance Levels: {technical.get('resistances', [])}
Volume Ratio: {technical.get('volume_ratio', 'N/A')}x avg | Surge: {technical.get('volume_surge', False)}
Tech Signal: {technical.get('tech_signal', 'N/A')} | Score: {technical.get('tech_score', 'N/A')}/8
{f"⚡ {technical['cross_signal'].upper().replace('_', ' ')}" if technical.get('cross_signal') else ""}"""

    # Fundamentals block
    fund_block = "Not available."
    if fundamentals and any(fundamentals.get(k) for k in ['eps', 'pe_ratio', 'dividend_yield']):
        fund_block = f"""EPS: {fundamentals.get('eps', 'N/A')}
P/E Ratio: {fundamentals.get('pe_ratio', 'N/A')}
Dividend Yield: {fundamentals.get('dividend_yield', 'N/A')}%
Payout Ratio: {fundamentals.get('payout_ratio', 'N/A')}%
Book Value: {fundamentals.get('book_value', 'N/A')}"""

    price      = stock.get("price", 0)
    change_pct = stock.get("change_pct", 0)
    prev_close = stock.get("prev_close", price)
    volume     = stock.get("volume", 0)

    prompt = f"""You are a senior Pakistan Stock Exchange (PSX) analyst. Analyze this stock and give a precise trading signal.

STOCK DATA:
Symbol: {symbol}
Name: {stock.get('name')}
Sector: {stock.get('sector')}
Current Price: PKR {price}
Previous Close: PKR {prev_close}
Today's Change: {change_pct:+.2f}%
Volume: {volume:,}
Day High/Low: {stock.get('high', 'N/A')} / {stock.get('low', 'N/A')}
Shariah Compliant: {"YES" if stock.get('shariah') else "NO"}

TECHNICAL ANALYSIS:
{tech_block}

FUNDAMENTAL DATA:
{fund_block}

RECENT RELEVANT NEWS:
{news_lines}

Based on ALL this data (technicals + fundamentals + news + price action), provide a comprehensive trading signal. Weight technicals heavily.

Respond ONLY with valid JSON, no markdown, no extra text:
{{
  "signal": "STRONG BUY",
  "confidence": 82,
  "entry_price": {price},
  "target_price": {round(price * 1.12, 2)},
  "stop_loss": {round(price * 0.94, 2)},
  "holding_period": "2-4 weeks",
  "reasoning": "Brief 2-sentence analysis combining technicals, fundamentals, and news.",
  "technical_summary": "One line summarizing the technical picture.",
  "news_summary": "One line summarizing the news sentiment.",
  "risk_level": "Medium",
  "key_risk": "Main risk factor here."
}}

signal must be one of: STRONG BUY, BUY, HOLD, SELL, STRONG SELL
risk_level must be one of: Low, Medium, High"""

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
        )
        raw = response.text.strip()
        # Strip markdown if present
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"AI analysis error for {symbol}: {e}")
        # Use tech signal as fallback if available
        fallback_signal = "HOLD"
        if technical and technical.get("tech_signal"):
            fallback_signal = technical["tech_signal"]
        return {
            "signal": fallback_signal,
            "confidence": 50,
            "entry_price": price,
            "target_price": round(price * 1.08, 2),
            "stop_loss": round(price * 0.95, 2),
            "holding_period": "N/A",
            "reasoning": "AI analysis temporarily unavailable. Using technical signal as fallback.",
            "technical_summary": technical.get("tech_signal", "N/A") if technical else "N/A",
            "news_summary": "N/A",
            "risk_level": "Medium",
            "key_risk": "Insufficient data."
        }


def analyze_overall_market(news_items: list, kse100: dict, pkr: dict) -> dict:
    """Generate overall market outlook based on news + macro data."""
    if not news_items:
        return None

    news_lines = "\n".join(
        f"- [{n['sentiment'].upper()}] {n['title']}" for n in news_items[:15]
    )

    kse_info = f"KSE-100: {kse100.get('value', 'N/A')} ({kse100.get('change_pct', 0):+.2f}%)" if kse100 else "KSE-100: N/A"
    pkr_info = f"USD/PKR: {pkr.get('rate', 'N/A')} ({pkr.get('change_pct', 0):+.2f}%)" if pkr else "USD/PKR: N/A"

    prompt = f"""You are a Pakistan market strategist. Analyze today's market based on latest news and data.

MARKET DATA:
{kse_info}
{pkr_info}

TODAY'S TOP NEWS:
{news_lines}

Provide a market overview. Respond ONLY with valid JSON, no markdown:
{{
  "overall_sentiment": "Bullish",
  "sentiment_score": 65,
  "summary": "2-3 sentence market overview here.",
  "key_drivers": ["Driver 1", "Driver 2", "Driver 3"],
  "hot_sectors": ["Cement", "Energy"],
  "weak_sectors": ["Banking"],
  "market_advice": "One line advice for investors today.",
  "watch_out": "Main risk to watch today."
}}

overall_sentiment must be: Bullish, Bearish, or Neutral
sentiment_score: -100 (very bearish) to +100 (very bullish)"""

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
        )
        raw = response.text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"Market analysis error: {e}")
        return {
            "overall_sentiment": "Neutral",
            "sentiment_score": 0,
            "summary": "Market analysis temporarily unavailable.",
            "key_drivers": [],
            "hot_sectors": [],
            "weak_sectors": [],
            "market_advice": "Monitor news and price action carefully.",
            "watch_out": "N/A"
        }


def analyze_dividend(announcement_text: str) -> dict:
    """Extract structured dividend info from announcement text."""
    prompt = f"""Extract dividend details from this PSX announcement. Respond ONLY with JSON, no markdown:

ANNOUNCEMENT:
{announcement_text}

{{
  "company": "Company name",
  "symbol": "TICKER",
  "dividend_type": "Final Cash Dividend",
  "amount_per_share": 5.0,
  "book_closure_date": "YYYY-MM-DD",
  "payment_date": "YYYY-MM-DD",
  "ex_dividend_date": "YYYY-MM-DD",
  "advice": "Buy before [date] to receive this dividend. Expect price to drop ~PKR X after ex-date."
}}

If any field is not mentioned, use null."""
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
        )
        raw = (response.text or "").strip().replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except:
        return None
