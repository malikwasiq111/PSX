import requests

API = "http://localhost:8000"

# Test status
r = requests.get(f"{API}/api/status")
print("STATUS:", r.json())

# Test stocks
r = requests.get(f"{API}/api/stocks")
d = r.json()
count = d["count"]
print(f"\nSTOCKS: {count} loaded")
for s in d["data"][:10]:
    print(f"  {s['symbol']:8s} PKR {s['price']:>8.2f}  {s['change_pct']:+.2f}%  vol={s['volume']:>10,}  src={s['source']}")

# Test market
r = requests.get(f"{API}/api/market")
m = r.json()
print(f"\nKSE-100: {m['kse100']}")
print(f"PKR/USD: {m['pkr']}")
print(f"Market:  {m['market_analysis'].get('overall_sentiment') if m['market_analysis'] else 'N/A'}")

# Test sectors
r = requests.get(f"{API}/api/sectors")
secs = r.json()["data"]
print(f"\nSECTORS: {len(secs)}")
for s in secs[:5]:
    print(f"  {s['sector']:15s} {s['avg_change']:+.2f}% ({len(s['stocks'])} stocks)")

# Test single stock detail
r = requests.get(f"{API}/api/stocks/OGDC")
det = r.json()
if "error" not in det:
    print(f"\nOGDC DETAIL:")
    print(f"  Price: {det['stock']['price']}")
    print(f"  Signal: {det.get('signal', {}).get('signal', 'N/A')}")
    print(f"  Technical: {'YES' if det.get('technical') else 'NO'}")
    print(f"  Dividends: {len(det.get('dividends', []))}")

print("\n✅ All endpoints working!")
