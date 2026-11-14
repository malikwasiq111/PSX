import numpy as np
from engine import analyze_single_stock, analyze_overall_market
from technical import _compute_rsi, _compute_macd, _compute_bollinger, _analyze

def test_rsi_bounds():
    r, _ = _compute_rsi(np.linspace(100, 150, 60)); assert 90 < r <= 100
    r, _ = _compute_rsi(np.linspace(150, 100, 60)); assert r < 10

def test_macd_and_bands():
    c = np.sin(np.linspace(0, 12, 120)) * 5 + 100
    assert len(_compute_macd(c)) == 4
    up, lo, mid, pct, _ = _compute_bollinger(c); assert lo < mid < up and 0 <= pct <= 100

def test_signal_direction():
    s = {"price": 100, "change_pct": 1}
    assert analyze_single_stock("X", s, [], {"tech_score": 6})["signal"] == "STRONG BUY"
    assert analyze_single_stock("X", s, [], {"tech_score": -6})["signal"] == "STRONG SELL"
    
def test_market():
    st = [{"symbol": "A", "change_pct": 2}, {"symbol": "B", "change_pct": -1}]
    assert analyze_overall_market([], {"change_pct": 1}, None, st)["advancers"] == 1

def test_analysis_and_backtest():
    rng = np.random.default_rng(1); c = 100 + np.cumsum(rng.normal(0, 1, 300)); v = rng.integers(1000, 5000, 300)
    r = _analyze("X", [f"d{i}" for i in range(300)], c, v)
    assert r["tech_signal"] in ("STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL") and r["backtest"]["days"] > 100
    assert r["perf"]["volatility"] > 0 and r["perf"]["max_drawdown"] <= 0
    assert len(r["chart_data"]) == 300 and r["low52"] <= r["high52"]

def test_no_data_signal():
    assert analyze_single_stock("X", {"price": 1}, [], None)["available"] is False

def test_json_safe():
    import json
    from technical import _clean
    rng = np.random.default_rng(2); c = 50 + np.cumsum(rng.normal(0, 1, 200)); v = rng.integers(0, 4000, 200)
    json.dumps(_clean(_analyze("X", [f"d{i}" for i in range(200)], c, v)), allow_nan=False)
