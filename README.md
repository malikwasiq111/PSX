# PSX Pro

A personal Pakistan Stock Exchange terminal: live prices, KSE-100 / KMI-30, sector heatmap, per-stock technical
analysis with an honest historical backtest, portfolio tracking, alerts, and corporate actions with PDF downloads.
Free to run: no paid APIs, no AI services. Everything is computed locally.

## Features
| Area | What you get |
|---|---|
| Overview | Index charts, breadth, KSE-100 heatmap, sector performance, what moved the index, gainers / losers / most active |
| Markets | Sortable, filterable table of all listed stocks (Halal filter, infinite scroll, CSV export) and a full heatmap |
| Stock page | Price + volume (1M-1Y) with MA20/50, RSI / MACD / Bollinger / trend, support and resistance, performance and risk stats, sector peers, signal with a backtest on that stock, payouts and board meetings, announcements, reports and insider trades (PDF links), news |
| Compare | Up to 3 stocks rebased to 100, plus indicators side by side |
| Watchlist | Live prices for the stocks you follow |
| Portfolio | P&L, allocation, daily performance chart, rule-based health score and per-holding actions |
| Corporate | Searchable payouts and results / meetings (last 30 days and next 45) with PDF downloads |
| Alerts | Price, percent-move and signal alerts, checked every 30 s, with in-app notifications |
| Extras | Ctrl/Cmd+K command palette, light and dark themes, mobile layout |

## Run it
Windows: double-click `run.bat`. Others: `./run.sh`. Or manually:
```
pip install -r requirements.txt
cd BACKEND
uvicorn main:app --port 8000      # open http://127.0.0.1:8000
```
Tests: `pip install pytest && python -m pytest BACKEND/test_api.py`. Docker: `docker build -t psxpro . && docker run -p 8000:8000 psxpro`.
API docs: `/docs`.

## How the signal works
A score from RSI, MACD, trend (MA20/MA50), Bollinger position, volume spikes and MA crosses, plus the tone of recent
headlines. It is **not** a prediction model. Each stock page backtests the same rule on that stock's own history and
shows what happened 10 days after each BUY / SELL / HOLD day, so you can see whether it has had any edge there.

## Data sources
Prices, indices, announcements, insiders and reports: Sarmaaya's REST API. Price history for indicators: PSX's public
end-of-day feed, with Sarmaaya and yfinance as fallbacks. Sarmaaya's endpoint is undocumented, so it may change.

## Limitations
Personal-use project. Check the data providers' terms before hosting it publicly. Data may be delayed or incomplete.
Nothing here is financial advice.

## Layout
`BACKEND/` FastAPI app (`main.py`, `technical.py`, `engine.py`, `portfolio.py`, `alerts.py`, `announcements.py`, `news.py`,
`scraper.py`) · `FRoNTEND/` vanilla JS single-page app (Chart.js).
