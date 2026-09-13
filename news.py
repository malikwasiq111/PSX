import feedparser
from datetime import datetime

# RSS news sources
RSS_SOURCES = [
    {"name": "Dawn Business",    "url": "https://www.dawn.com/feeds/business-finance"},
    {"name": "Tribune Business", "url": "https://tribune.com.pk/feed/business"},
    {"name": "The News Business","url": "https://www.thenews.com.pk/rss/2/7"},
    {"name": "Geo News Business","url": "https://www.geo.tv/rss/1"},
]

# Google News queries for PSX
GOOGLE_QUERIES = [
    "Pakistan stock exchange KSE",
    "PSX shares dividend Pakistan",
    "Pakistan economy IMF",
    "Pakistan rupee dollar rate",
    "OGDC PPL Engro Meezan Pakistan",
    "Pakistan inflation interest rate SBP",
    "Pakistan budget trade balance",
    "Pakistan cement sector Lucky DGKC",
    "Pakistan banking HBL MCB UBL",
    "Pakistan fertilizer FFC EFERT",
]

# Company name → symbol mapping for news matching (100+ stocks)
COMPANY_KEYWORDS = {
    # Energy / Oil & Gas
    "OGDC":   ["OGDC", "Oil & Gas Development", "Oil Gas Dev"],
    "PPL":    ["PPL", "Pakistan Petroleum"],
    "PSO":    ["PSO", "Pakistan State Oil"],
    "MARI":   ["MARI", "Mari Petroleum", "Mari Gas"],
    "POL":    ["POL", "Pakistan Oilfields"],
    "APL":    ["APL", "Attock Petroleum"],
    "SNGP":   ["SNGP", "Sui Northern Gas", "SNGPL"],
    "SSGC":   ["SSGC", "Sui Southern Gas"],
    "HASCOL": ["HASCOL", "Hascol Petroleum"],
    # Oil Refinery
    "ATRL":   ["ATRL", "Attock Refinery"],
    "NRL":    ["NRL", "National Refinery"],
    "PRL":    ["PRL", "Pakistan Refinery"],
    # Banking
    "HBL":    ["HBL", "Habib Bank"],
    "MCB":    ["MCB", "MCB Bank", "Muslim Commercial"],
    "UBL":    ["UBL", "United Bank"],
    "MEBL":   ["MEBL", "Meezan Bank", "Meezan"],
    "BAHL":   ["BAHL", "Bank Al Habib"],
    "ABL":    ["ABL", "Allied Bank"],
    "BAFL":   ["BAFL", "Bank Alfalah"],
    "AKBL":   ["AKBL", "Askari Bank"],
    "NBP":    ["NBP", "National Bank of Pakistan"],
    "BOP":    ["BOP", "Bank of Punjab"],
    "SCBPL":  ["SCBPL", "Standard Chartered Pakistan"],
    "JSBL":   ["JSBL", "JS Bank"],
    "FABL":   ["FABL", "Faysal Bank"],
    "BOK":    ["BOK", "Bank of Khyber"],
    # Cement
    "LUCK":   ["LUCK", "Lucky Cement"],
    "DGKC":   ["DGKC", "DG Khan Cement", "D.G. Khan"],
    "MLCF":   ["MLCF", "Maple Leaf Cement"],
    "FCCL":   ["FCCL", "Fauji Cement"],
    "CHCC":   ["CHCC", "Cherat Cement"],
    "PIOC":   ["PIOC", "Pioneer Cement"],
    "ACPL":   ["ACPL", "Attock Cement"],
    "KOHC":   ["KOHC", "Kohat Cement"],
    "FLYNG":  ["FLYNG", "Flying Cement"],
    "POWER":  ["POWER", "Power Cement"],
    # Fertilizer
    "FFC":    ["FFC", "Fauji Fertilizer"],
    "EFERT":  ["EFERT", "Engro Fertilizer"],
    "FATIMA": ["FATIMA", "Fatima Fertilizer"],
    # Power
    "HUBC":   ["HUBC", "Hub Power"],
    "KAPCO":  ["KAPCO", "Kapco"],
    "KEL":    ["KEL", "K-Electric"],
    "NPL":    ["NPL", "Nishat Power"],
    # Auto
    "INDU":   ["INDU", "Indus Motor", "Toyota Indus"],
    "HCAR":   ["HCAR", "Honda Atlas"],
    "PSMC":   ["PSMC", "Pak Suzuki", "Suzuki Motor"],
    "MTL":    ["MTL", "Millat Tractors"],
    "AGTL":   ["AGTL", "Al-Ghazi Tractors"],
    # Pharma
    "SEARL":  ["SEARL", "Searle Company", "Searle Pharmaceuticals"],
    "GLAXO":  ["GLAXO", "GlaxoSmithKline Pakistan"],
    "AGP":    ["AGP", "AGP Limited"],
    "FEROZ":  ["FEROZ", "Ferozsons Labs"],
    "ABOT":   ["ABOT", "Abbott Labs Pakistan"],
    # Technology
    "SYS":    ["SYS", "Systems Limited"],
    "TRG":    ["TRG", "TRG Pakistan"],
    "NETSOL": ["NETSOL", "NetSol Technologies"],
    "AVN":    ["AVN", "AVN Technologies"],
    "AIRLINK":["AIRLINK", "Air Link Communication"],
    "WTL":    ["WTL", "WorldCall Telecom"],
    # Textile
    "NML":    ["NML", "Nishat Mills"],
    "NCL":    ["NCL", "Nishat Chunian"],
    "ILP":    ["ILP", "Interloop"],
    # Chemicals
    "EPCL":   ["EPCL", "Engro Polymer"],
    "LOTCHEM":["LOTCHEM", "Lotte Chemical PK"],
    # Food / Consumer
    "NESTLE": ["NESTLE", "Nestle Pakistan"],
    "UPFL":   ["UPFL", "Unilever Pakistan Foods"],
    "COLG":   ["COLG", "Colgate-Palmolive Pakistan"],
    "UNITY":  ["UNITY", "Unity Foods"],
    "JDWS":   ["JDWS", "JDW Sugar"],
    # Conglomerate
    "ENGRO":  ["ENGRO", "Engro Corporation", "Engro Corp"],
    "DAWH":   ["DAWH", "Dawood Hercules"],
    # Steel
    "MUGHAL": ["MUGHAL", "Mughal Iron", "Mughal Steel"],
    "ISL":    ["ISL", "International Steels"],
    "ASTL":   ["ASTL", "Amreli Steels"],
    # Other
    "PKGS":   ["PKGS", "Packages Limited"],
    "PNSC":   ["PNSC", "Pakistan National Shipping"],
    "GHGL":   ["GHGL", "Ghani Glass"],
    "TGL":    ["TGL", "Tariq Glass"],
    "DCR":    ["DCR", "Dolmen City REIT"],
    "PAEL":   ["PAEL", "Pak Elektron"],
    "HUMNL":  ["HUMNL", "Hum Network"],
    "TPL":    ["TPL", "TPL Properties"],
}

POSITIVE_WORDS = [
    "profit", "growth", "increase", "record high", "dividend", "bonus share",
    "expansion", "investment", "rally", "gain", "bullish", "recovery", "surplus",
    "strong earnings", "beat", "upgrade", "approval", "positive", "rise", "up",
    "IMF tranche", "interest rate cut", "rate cut", "rupee strengthens",
    "foreign investment", "CPEC", "tax relief", "privatization"
]

NEGATIVE_WORDS = [
    "loss", "decline", "decrease", "deficit", "crisis", "debt",
    "inflation", "devaluation", "shutdown", "penalty", "fine", "fraud",
    "bearish", "crash", "fall", "down", "weak", "flood", "default",
    "miss", "downgrade", "negative", "concern", "warning",
    "IMF delay", "rate hike", "oil price rise", "circular debt",
    "load shedding", "power outage", "rupee falls"
]

MACRO_POSITIVE = [
    "IMF tranche", "IMF payment", "interest rate cut", "rate cut",
    "oil price drop", "trade surplus", "foreign investment", "CPEC",
    "dollar falls", "rupee strengthens", "tax relief", "budget surplus",
    "privatization", "GDP growth"
]

MACRO_NEGATIVE = [
    "IMF delay", "rate hike", "interest rate increase", "oil price rise",
    "trade deficit", "rupee falls", "dollar rises", "inflation high",
    "power outage", "load shedding", "circular debt", "default risk",
    "political unrest", "terrorism"
]


def get_sentiment(text: str):
    text_lower = text.lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in text_lower)
    neg = sum(1 for w in NEGATIVE_WORDS if w in text_lower)
    if pos > neg:
        return "positive", min((pos - neg) * 20, 100)
    elif neg > pos:
        return "negative", min((neg - pos) * 20, 100)
    return "neutral", 0


def get_market_impact(text: str):
    text_lower = text.lower()
    for phrase in MACRO_POSITIVE:
        if phrase in text_lower:
            return "market_positive", phrase
    for phrase in MACRO_NEGATIVE:
        if phrase in text_lower:
            return "market_negative", phrase
    return None, None


def find_related_stocks(text: str):
    related = []
    text_upper = text.upper()
    for symbol, keywords in COMPANY_KEYWORDS.items():
        for kw in keywords:
            if kw.upper() in text_upper:
                related.append(symbol)
                break
    return list(set(related))


def fetch_google_news_psx():
    """Fetch latest PSX-related news from Google News RSS."""
    import feedparser
    
    psx_queries = [
        "Pakistan stock exchange",
        "KSE-100 index",
        "PSX market",
        "Pakistani stocks",
        "KSE news",
    ]
    
    news = []
    seen_titles = set()
    
    for query in psx_queries:
        url = f"https://news.google.com/rss/search?q={query.replace(' ','+')}&hl=en-PK&gl=PK&ceid=PK:en"
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                title = entry.get("title", "").strip()
                if title in seen_titles:
                    continue
                seen_titles.add(title)
                
                summary = entry.get("summary", "").strip()
                link = entry.get("link", "")
                published = entry.get("published", datetime.now().isoformat())
                
                # Sentiment analysis
                full_text = title + " " + summary
                sentiment, strength = get_sentiment(full_text)
                impact, reason = get_market_impact(full_text)
                related = find_related_stocks(full_text)
                
                news.append({
                    "title": title,
                    "summary": summary[:300],
                    "link": link,
                    "published": published,
                    "source": "Google News",
                    "sentiment": sentiment,
                    "strength": strength,
                    "market_impact": impact,
                    "related_stocks": related,
                    "timestamp": datetime.now().isoformat(),
                })
        except Exception as e:
            print(f"Google News error [{query}]: {e}")
    
    return news


def fetch_all_news():
    """Fetch news from all sources (local RSS + Google News)."""
    all_news = []
    seen_titles = set()

    # Existing Pakistani RSS sources
    for src in RSS_SOURCES:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:8]:
                title = entry.get("title", "").strip()
                if title in seen_titles:
                    continue
                seen_titles.add(title)

                summary = entry.get("summary", "").strip()
                sentiment, strength = get_sentiment(title + " " + summary)
                impact, reason = get_market_impact(title + " " + summary)
                related = find_related_stocks(title + " " + summary)

                all_news.append({
                    "title": title,
                    "summary": summary[:300],
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "source": src["name"],
                    "sentiment": sentiment,
                    "strength": strength,
                    "market_impact": impact,
                    "related_stocks": related,
                    "timestamp": datetime.now().isoformat(),
                })
        except Exception as e:
            print(f"RSS error [{src['name']}]: {e}")

    # Google News (PSX-specific)
    google_news = fetch_google_news_psx()
    all_news.extend(google_news)

    # Remove duplicates, sort by recency
    unique_news = {}
    for n in all_news:
        key = n["title"]
        if key not in unique_news:
            unique_news[key] = n

    return sorted(unique_news.values(), 
                  key=lambda x: datetime.fromisoformat(x.get("timestamp", datetime.now().isoformat())),
                  reverse=True)[:100]
