"""
PSX Dividends & Fundamentals Module
Scrapes dividend data from: sarmaaya.pk, PSX announcements, Google News
Provides dividend history, payout ratios, EPS, and fundamental data.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import json

# ── Configuration ───────────────────────────────────────────────────────────

SARMAAYA_URL = "https://sarmaaya.pk/stocks/{symbol}"
PSX_ANNOUNCEMENTS_URL = "https://dps.psx.com.pk/announcements/companies"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

DIVIDEND_KEYWORDS = [
    "dividend", "cash dividend", "final dividend", "interim dividend",
    "bonus share", "right share", "book closure", "payout"
]

# ── In-memory caches ────────────────────────────────────────────────────────

_dividend_cache = []
_fundamental_cache = {}  # symbol → {data, fetched_at}
_FUNDAMENTAL_TTL = 1800  # 30 minutes


# ── Sarmaaya.pk Scraper ────────────────────────────────────────────────────

def scrape_sarmaaya_stock(symbol: str) -> dict:
    """
    Scrape sarmaaya.pk for stock fundamentals:
    - Dividend history
    - EPS, P/E ratio, payout ratio
    - Book value, market cap
    - Shariah status
    """
    import time
    cached = _fundamental_cache.get(symbol)
    if cached and (time.time() - cached["fetched_at"]) < _FUNDAMENTAL_TTL:
        return cached["data"]

    url = SARMAAYA_URL.format(symbol=symbol)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        result = {"symbol": symbol, "source": "sarmaaya.pk"}

        # Extract key metrics from the page
        # Price
        price_el = soup.select_one(".stock-price, [class*='price']")
        if price_el:
            price_text = price_el.get_text(strip=True).replace("Rs", "").replace(",", "").strip()
            try:
                result["price"] = float(price_text)
            except:
                pass

        # Look for financial ratios in tables or key-value pairs
        all_text = soup.get_text(" ", strip=True)

        # EPS
        eps_match = re.search(r'EPS[:\s]*([-\d.]+)', all_text, re.IGNORECASE)
        if eps_match:
            try: result["eps"] = float(eps_match.group(1))
            except: pass

        # P/E Ratio
        pe_match = re.search(r'P/E[:\s]*([\d.]+)', all_text, re.IGNORECASE)
        if pe_match:
            try: result["pe_ratio"] = float(pe_match.group(1))
            except: pass

        # Payout Ratio
        payout_match = re.search(r'Payout[:\s]*([\d.]+)%?', all_text, re.IGNORECASE)
        if payout_match:
            try: result["payout_ratio"] = float(payout_match.group(1))
            except: pass

        # Book Value
        bv_match = re.search(r'Book\s*Value[:\s]*([\d.]+)', all_text, re.IGNORECASE)
        if bv_match:
            try: result["book_value"] = float(bv_match.group(1))
            except: pass

        # Market Cap
        mc_match = re.search(r'Market\s*Cap[:\s]*([\d,.]+)\s*(B|M|Bn|Mn)?', all_text, re.IGNORECASE)
        if mc_match:
            try:
                mc_val = float(mc_match.group(1).replace(",", ""))
                unit = (mc_match.group(2) or "").upper()
                if unit.startswith("B"):
                    mc_val *= 1e9
                elif unit.startswith("M"):
                    mc_val *= 1e6
                result["market_cap"] = mc_val
            except: pass

        # Dividend yield
        dy_match = re.search(r'Dividend\s*Yield[:\s]*([\d.]+)%?', all_text, re.IGNORECASE)
        if dy_match:
            try: result["dividend_yield"] = float(dy_match.group(1))
            except: pass

        # Shariah compliance
        if "shariah compliant" in all_text.lower() or "shairah compliant" in all_text.lower():
            result["shariah_compliant"] = True
        elif "non.shariah" in all_text.lower().replace(" ", "."):
            result["shariah_compliant"] = False

        # Extract dividend history from tables
        dividends = _extract_sarmaaya_dividends(soup, symbol)
        if dividends:
            result["dividend_history"] = dividends

        # Cache it
        _fundamental_cache[symbol] = {"data": result, "fetched_at": time.time()}
        return result

    except Exception as e:
        print(f"Sarmaaya scrape error for {symbol}: {e}")
        return None


def _extract_sarmaaya_dividends(soup, symbol: str) -> list:
    """Extract dividend history from sarmaaya.pk tables."""
    dividends = []
    tables = soup.select("table")
    for table in tables:
        header_text = ""
        prev = table.find_previous(["h2", "h3", "h4", "div"])
        if prev:
            header_text = prev.get_text(strip=True).lower()

        rows = table.select("tr")
        for row in rows[1:]:  # skip header
            cols = row.find_all("td")
            if len(cols) < 2:
                continue

            row_text = " ".join(c.get_text(strip=True) for c in cols).lower()
            if not any(kw in row_text or kw in header_text for kw in ["dividend", "payout", "bonus", "cash"]):
                continue

            try:
                div_entry = {
                    "symbol": symbol,
                    "source": "sarmaaya.pk",
                }
                for i, col in enumerate(cols):
                    text = col.get_text(strip=True)
                    # Try to identify date, amount, type columns
                    if re.match(r'\d{4}', text) or re.match(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', text):
                        div_entry["date"] = text
                    elif re.match(r'^[\d.]+$', text.replace(",", "")):
                        val = float(text.replace(",", ""))
                        if val < 200:  # likely per-share amount
                            div_entry["amount_per_share"] = val
                        else:
                            div_entry["total_amount"] = val
                    elif any(kw in text.lower() for kw in ["cash", "interim", "final", "bonus", "right"]):
                        div_entry["type"] = text

                if div_entry.get("amount_per_share") or div_entry.get("type"):
                    if "type" not in div_entry:
                        div_entry["type"] = "Cash Dividend"
                    dividends.append(div_entry)
            except:
                continue

    return dividends[:10]  # Last 10 dividends


# ── PSX Announcements Scraper ──────────────────────────────────────────────

def scrape_psx_announcements():
    """Scrape PSX announcements page for dividend-related items."""
    global _dividend_cache

    try:
        res = requests.get(PSX_ANNOUNCEMENTS_URL, headers=HEADERS, timeout=10)
        res.raise_for_status()

        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.select("table tbody tr")
        announcements = []

        for row in rows[:80]:  # top 80 announcements
            cols = row.find_all("td")
            if len(cols) < 3:
                continue

            date_text    = cols[0].get_text(strip=True)
            symbol_text  = cols[1].get_text(strip=True).upper()
            subject_text = cols[2].get_text(strip=True)

            # Only process dividend-related
            if not any(kw in subject_text.lower() for kw in DIVIDEND_KEYWORDS):
                continue

            # Try to get detail link
            link = ""
            a_tag = row.find("a")
            if a_tag and a_tag.get("href"):
                href = a_tag["href"]
                link = href if href.startswith("http") else f"https://dps.psx.com.pk{href}"

            announcements.append({
                "date":       date_text,
                "symbol":     symbol_text,
                "subject":    subject_text,
                "link":       link,
                "source":     "PSX Announcements",
                "raw_text":   f"{symbol_text}: {subject_text} ({date_text})",
                "scraped_at": datetime.now().isoformat(),
            })

        _dividend_cache = announcements
        print(f"Dividends: found {len(announcements)} PSX announcements")
        return announcements

    except Exception as e:
        print(f"PSX announcements scrape error: {e}")
        return _dividend_cache  # return cached if error


# ── Parsing & Enrichment ──────────────────────────────────────────────────

def get_dividends():
    """Return latest dividend announcements (cached)."""
    return _dividend_cache


def parse_dividend_details(announcement: dict) -> dict:
    """
    Parse key dividend details from announcement text using regex.
    Falls back gracefully if info not found.
    """
    text = announcement.get("subject", "") + " " + announcement.get("raw_text", "")

    # Try to extract PKR amount
    amount = None
    amount_match = re.search(r'(?:PKR|Rs\.?|rupees?)\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if amount_match:
        amount = float(amount_match.group(1))

    # Try to extract percentage (for bonus shares)
    pct = None
    pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
    if pct_match:
        pct = float(pct_match.group(1))

    # Try to extract book closure date
    book_closure = None
    bc_match = re.search(r'book\s*closure[:\s]*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', text, re.IGNORECASE)
    if bc_match:
        book_closure = bc_match.group(1)

    # Dividend type detection
    dtype = "Cash Dividend"
    text_lower = text.lower()
    if "bonus" in text_lower:
        dtype = "Bonus Shares"
    elif "right" in text_lower:
        dtype = "Right Shares"
    elif "interim" in text_lower:
        dtype = "Interim Dividend"
    elif "final" in text_lower:
        dtype = "Final Dividend"

    return {
        "symbol":             announcement["symbol"],
        "date":               announcement.get("date", ""),
        "announcement_date":  announcement.get("date", ""),
        "type":               dtype,
        "amount_per_share":   amount,
        "percentage":         pct,
        "book_closure_date":  book_closure,
        "subject":            announcement.get("subject", ""),
        "link":               announcement.get("link", ""),
        "source":             announcement.get("source", "PSX"),
        "advice":             _build_advice(dtype, amount, pct, announcement["symbol"]),
        "scraped_at":         announcement.get("scraped_at", ""),
    }


def _build_advice(dtype: str, amount, pct, symbol: str) -> str:
    """Build a plain-English investor tip about this dividend."""
    tips = []

    if dtype in ("Cash Dividend", "Final Dividend", "Interim Dividend"):
        if amount:
            tips.append(f"{symbol} is paying PKR {amount}/share.")
        tips.append("Buy before the book closure date to qualify.")
        tips.append("Expect the stock price to drop roughly by the dividend amount after ex-date.")

    elif dtype == "Bonus Shares":
        if pct:
            tips.append(f"{symbol} is issuing {pct}% bonus shares.")
            tips.append(f"For every 100 shares you hold, you receive {pct} extra shares free.")
        tips.append("Bonus shares dilute price but increase your share count — usually positive signal.")

    elif dtype == "Right Shares":
        if pct:
            tips.append(f"{symbol} is offering {pct}% right shares.")
        tips.append("Right shares let existing holders buy new shares at a discounted price.")
        tips.append("Check the offer price vs market price before deciding to subscribe.")

    return " ".join(tips) if tips else "Monitor the PSX announcement for full details."


def get_parsed_dividends():
    """Return all dividends with parsed details."""
    raw = get_dividends()
    return [parse_dividend_details(a) for a in raw]


# ── Stock Fundamentals (for modal enrichment) ─────────────────────────────

def get_stock_fundamentals(symbol: str) -> dict:
    """
    Get fundamental data for a stock from sarmaaya.pk.
    Returns dict with eps, pe_ratio, payout_ratio, book_value, dividend_yield, etc.
    """
    data = scrape_sarmaaya_stock(symbol)
    if not data:
        return {}

    return {
        "eps":              data.get("eps"),
        "pe_ratio":         data.get("pe_ratio"),
        "payout_ratio":     data.get("payout_ratio"),
        "book_value":       data.get("book_value"),
        "market_cap":       data.get("market_cap"),
        "dividend_yield":   data.get("dividend_yield"),
        "shariah_compliant": data.get("shariah_compliant"),
        "dividend_history": data.get("dividend_history", []),
        "source":           "sarmaaya.pk",
    }


def get_stock_dividends(symbol: str) -> list:
    """Get dividend history for a specific stock from all sources."""
    results = []

    # From PSX announcements cache
    for d in _dividend_cache:
        if d.get("symbol") == symbol.upper():
            results.append(parse_dividend_details(d))

    # From sarmaaya.pk
    fundamentals = scrape_sarmaaya_stock(symbol)
    if fundamentals and fundamentals.get("dividend_history"):
        for div in fundamentals["dividend_history"]:
            # Avoid duplicates
            exists = any(
                r.get("date") == div.get("date") and r.get("amount_per_share") == div.get("amount_per_share")
                for r in results
            )
            if not exists:
                results.append({
                    "symbol":           symbol,
                    "date":             div.get("date", ""),
                    "type":             div.get("type", "Cash Dividend"),
                    "amount_per_share": div.get("amount_per_share"),
                    "percentage":       div.get("percentage"),
                    "source":           "sarmaaya.pk",
                    "advice":           _build_advice(
                        div.get("type", "Cash Dividend"),
                        div.get("amount_per_share"),
                        div.get("percentage"),
                        symbol
                    ),
                })

    return results