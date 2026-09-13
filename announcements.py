"""
PSX Corporate Announcements — sarmaaya.pk REST API
Endpoints used:
  /api/announcements/board-meetings?from=DATE&to=DATE
  /api/announcements/payouts?from=DATE&to=DATE
  /api/announcements/result-announcements?from=DATE&to=DATE
All return clean JSON — no scraping needed.
"""

import requests
from datetime import datetime, timedelta, timezone

PKT     = timezone(timedelta(hours=5))
BASE    = "https://beta-restapi.sarmaaya.pk/api"
HEADERS = {"User-Agent":"Mozilla/5.0","Accept":"application/json"}

# Cache
_ann_cache    = []
_div_cache    = []
_last_fetched = None


def _date_range(days_back: int = 30):
    """Return (from_str, to_str) for the last N days."""
    today = datetime.now(PKT).date()
    start = today - timedelta(days=days_back)
    return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


# ── Fetch: Board Meetings ─────────────────────────────────────────────────────

def fetch_board_meetings(days_back: int = 30) -> list:
    results = []
    from_dt, to_dt = _date_range(days_back)
    try:
        r    = requests.get(
            f"{BASE}/announcements/board-meetings",
            params={"from": from_dt, "to": to_dt},
            headers=HEADERS, timeout=12
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("success"):
            return []

        for item in data.get("response", []):
            symbol        = item.get("symbol","").upper()
            held_date     = item.get("heldDate","")
            period_ended  = item.get("periodEnded","")
            account_type  = item.get("accountType","").strip()
            title         = item.get("announcementTitle","").strip()
            posting_date  = item.get("postingDate","")
            attachments   = item.get("attachments",[])
            pdf_link      = next((a for a in attachments if a.endswith(".pdf")), "")
            img_link      = next((a for a in attachments if a.endswith(".gif")), "")

            # Generate investor advice
            advice = _board_advice(symbol, title, held_date, period_ended, account_type)

            results.append({
                "symbol":       symbol,
                "type":         "board",
                "type_label":   "📌 Board Meeting",
                "title":        title,
                "date":         posting_date,
                "held_date":    held_date,
                "period_ended": period_ended,
                "account_type": account_type,
                "amount":       None,
                "closure_date": None,
                "advice":       advice,
                "source":       "PSX AI Analyst",
                "link":         pdf_link or img_link,
                "logo":         item.get("logo",""),
                "scraped_at":   datetime.now(PKT).isoformat(),
            })

        print(f"Board meetings: {len(results)} fetched")
    except Exception as e:
        print(f"Board meetings API error: {e}")
    return results


# ── Fetch: Payouts (Dividends + Bonus) ───────────────────────────────────────

def fetch_payouts(days_back: int = 30) -> list:
    results = []
    from_dt, to_dt = _date_range(days_back)
    try:
        r    = requests.get(
            f"{BASE}/announcements/payouts",
            params={"from": from_dt, "to": to_dt},
            headers=HEADERS, timeout=12
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("success"):
            return []

        for item in data.get("response", []):
            symbol      = item.get("symbol","").upper()
            payout_type = item.get("payoutType","dividend").lower()  # "dividend" or "bonus"
            payout_pct  = float(item.get("payoutPercentage",0) or 0)
            face_value  = float(item.get("faceValue",10) or 10)
            ex_date     = item.get("exDate","")
            name        = item.get("name","")

            # Calculate PKR per share from percentage × face value / 100
            pkr_per_share = round(payout_pct * face_value / 100, 2) if payout_pct else None

            if payout_type == "bonus":
                atype       = "bonus"
                type_label  = "🎁 Bonus Shares"
                title       = f"{name or symbol}: {payout_pct}% Bonus Shares"
                advice      = (
                    f"{symbol} issuing {payout_pct}% bonus shares — "
                    f"you receive {payout_pct} free shares per 100 held. "
                    f"Must hold before ex-date {ex_date}. "
                    "Bonus shares dilute price proportionally but increase your holding count."
                )
            else:
                atype       = "dividend"
                type_label  = "💰 Cash Dividend"
                title       = f"{name or symbol}: {payout_pct}% Dividend (₨{pkr_per_share}/share)"
                advice      = (
                    f"{symbol} paying ₨{pkr_per_share}/share dividend "
                    f"({payout_pct}% of face value ₨{face_value}). "
                    f"Ex-date: {ex_date} — must hold BEFORE this date to qualify. "
                    "Expect stock price to drop ~₨" + str(pkr_per_share) + " on ex-date."
                )

            results.append({
                "symbol":       symbol,
                "type":         atype,
                "type_label":   type_label,
                "title":        title,
                "date":         ex_date,
                "held_date":    ex_date,
                "period_ended": "",
                "account_type": payout_type,
                "amount":       pkr_per_share if atype=="dividend" else payout_pct,
                "payout_pct":   payout_pct,
                "face_value":   face_value,
                "closure_date": ex_date,
                "advice":       advice,
                "source":       "PSX AI Analyst",
                "link":         "",
                "logo":         item.get("logo",""),
                "scraped_at":   datetime.now(PKT).isoformat(),
            })

        print(f"Payouts: {len(results)} fetched")
    except Exception as e:
        print(f"Payouts API error: {e}")
    return results


# ── Fetch: Financial Results ──────────────────────────────────────────────────

def fetch_results(days_back: int = 30) -> list:
    results = []
    from_dt, to_dt = _date_range(days_back)
    try:
        r    = requests.get(
            f"{BASE}/announcements/result-announcements",
            params={"from": from_dt, "to": to_dt},
            headers=HEADERS, timeout=12
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("success"):
            return []

        for item in data.get("response", []):
            symbol       = item.get("symbol","").upper()
            title        = item.get("announcementTitle","").strip()
            posting_date = item.get("postingDate","")
            period_ended = item.get("periodEnded","")
            div_pct      = item.get("dividendPercent","-")
            close_from   = item.get("closeFrom","")
            close_to     = item.get("closeTo","")
            attachments  = item.get("attachments",[])
            pdf_link     = next((a for a in attachments if a.endswith(".pdf")), "")

            # If result includes dividend info
            div_advice = ""
            if div_pct and div_pct not in ("-","","0"):
                div_advice = f" Dividend declared: {div_pct}%."

            closure_str = f"{close_from} to {close_to}" if close_from and close_to and close_from!="-" else ""
            advice = (
                f"{symbol} released financial results for {period_ended or 'recent period'}."
                + div_advice
                + (f" Book closure: {closure_str}." if closure_str else "")
                + " Review EPS, revenue growth, and margins before making investment decisions."
            )

            results.append({
                "symbol":       symbol,
                "type":         "results",
                "type_label":   "📊 Financial Results",
                "title":        title or f"{symbol} Financial Results",
                "date":         posting_date,
                "held_date":    posting_date,
                "period_ended": period_ended,
                "account_type": "",
                "amount":       None,
                "closure_date": closure_str,
                "advice":       advice,
                "source":       "PSX AI Analyst",
                "link":         pdf_link,
                "logo":         item.get("logo",""),
                "scraped_at":   datetime.now(PKT).isoformat(),
            })

        print(f"Results: {len(results)} fetched")
    except Exception as e:
        print(f"Results API error: {e}")
    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _board_advice(symbol, title, held_date, period_ended, account_type) -> str:
    parts = []
    if "other than financial" in title.lower():
        parts.append(f"{symbol} board meeting called for non-financial matter.")
        parts.append("Watch for strategic decisions, dividend announcements, or corporate actions.")
    else:
        period = account_type.strip() if account_type and account_type!="-" else "quarterly"
        parts.append(f"{symbol} board meeting on {held_date} to announce {period} results for {period_ended or 'recent period'}.")
        parts.append("Watch for dividend declaration, EPS figures, and management guidance post-meeting.")
    return " ".join(parts)


# ── Main refresh ──────────────────────────────────────────────────────────────

def refresh_announcements(days_back: int = 30) -> list:
    global _ann_cache, _div_cache, _last_fetched

    board    = fetch_board_meetings(days_back)
    payouts  = fetch_payouts(days_back)
    results  = fetch_results(days_back)

    # Combine all — payouts first (most actionable), then results, then board meetings
    all_ann = payouts + results + board

    # Deduplicate by symbol + type + date
    seen, final = set(), []
    for a in all_ann:
        key = f"{a['symbol']}_{a['type']}_{a['date']}"
        if key not in seen:
            seen.add(key)
            final.append(a)

    _ann_cache    = final
    _div_cache    = [a for a in final if a["type"] in ("dividend","bonus")]
    _last_fetched = datetime.now(PKT).isoformat()

    print(f"Announcements: {len(final)} total | "
          f"{len(_div_cache)} dividends/bonus | "
          f"{len(results)} results | "
          f"{len(board)} board meetings")
    return final


# ── Getters ───────────────────────────────────────────────────────────────────

def get_all_announcements() -> list:
    return _ann_cache

def get_dividends() -> list:
    return _div_cache

def get_announcements_for_symbol(symbol: str) -> list:
    return [a for a in _ann_cache if a.get("symbol") == symbol.upper()]

def get_announcements_by_type(atype: str) -> list:
    if atype == "all":
        return _ann_cache
    return [a for a in _ann_cache if a.get("type") == atype]