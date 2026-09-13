# PSX AI Analyst 🇵🇰📈

AI-powered Pakistan Stock Exchange intelligence platform.
Real-time prices, news sentiment, buy/sell signals, Shariah screening.

---

## Setup (5 minutes)

### 1. Install Python dependencies
```
cd psx-ai-analyst
pip install -r requirements.txt
```

### 2. Set your API key
```
# Copy the example file
copy .env.example .env        (Windows)
cp .env.example .env          (Mac/Linux)

```

### 3. Run the server
```
cd backend
uvicorn main:app --reload --port 8000
```

### 4. Open the dashboard
Open your browser and go to:
```
http://localhost:8000
```

That's it! Data refreshes every 30 seconds automatically.

---

## Features

| Feature | Status |
|---|---|
| Live PSX stock prices  | ✅ |
| KSE-100 Index live | ✅ |
| USD/PKR live rate | ✅ |
| Real-time news (Dawn, Tribune, Google News) | ✅ |
| AI buy/sell/hold signals with reasoning | ✅ |
| News sentiment analysis | ✅ |
| News linked to specific stocks | ✅ |
| Market macro impact detection | ✅ |
| Shariah compliance filter | ✅ |
| Sector performance heatmap | ✅ |
| Price targets + stop loss | ✅ |
| 30-second auto-refresh | ✅ |

---

## Project Structure

```
psx-ai-analyst/
├── backend/
│   ├── main.py          ← FastAPI server + all API endpoints
│   ├── scraper.py       ← PSX stock prices via yfinance
│   ├── news.py          ← News from RSS feeds + Google News
│   └── ai_analysis.py  ← Claude AI buy/sell signals
├── frontend/
│   ├── index.html       ← Dashboard UI
│   ├── style.css        ← Styling
│   └── app.js           ← Frontend logic
├── requirements.txt
└── .env                 ← Your API keys (never commit this)
```

---

## API Endpoints

| Endpoint | Description |
|---|---|
| GET /api/market | KSE-100, USD/PKR, AI market overview |
| GET /api/stocks | All 20 stocks with live prices |
| GET /api/stocks/{SYMBOL} | Single stock + AI signal + related news |
| GET /api/news | All news with sentiment tags |
| GET /api/sectors | Sector performance summary |
| GET /api/status | Server status |

---

## Notes

- Stock prices update every 30 seconds via Yahoo Finance
- AI signals refresh every 5 minutes per stock (to save API costs)
- News is fetched from Dawn, Tribune, The News, and Google News
- Shariah status is pre-screened based on SECP + Meezan criteria
