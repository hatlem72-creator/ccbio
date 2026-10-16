import json, datetime, urllib.parse, urllib.request, email.utils, re, html
import xml.etree.ElementTree as ET
import yfinance as yf

SECTIONS = [
 ("ETFs & Index Funds", [
  ("G2X.DE","VanEck Gold Miners UCITS ETF","VanEck Gold Miners"),
  ("2B76.DE","iShares Automation & Robotics UCITS ETF","iShares Automation & Robotics"),
  ("0P0001IMY8.F","AuAg Silver Bullet B","AuAg Silver Bullet")]),
 ("Silver Mining", [
  ("HL","Hecla Mining","Hecla Mining"),("HYMC","Hycroft Mining","Hycroft Mining"),
  ("ASM","Avino Silver & Gold","Avino Silver"),("CDE","Coeur Mining","Coeur Mining"),
  ("AG.TO","First Majestic Silver","First Majestic Silver"),("DEF.V","Defiance Silver","Defiance Silver Corp"),
  ("GRSL.V","GR Silver Mining","GR Silver Mining"),("GSVR.V","Guanajuato Silver","Guanajuato Silver"),
  ("AGX.V","Silver X Mining","Silver X Mining")]),
 ("General Markets", [
  ("^GSPC","S&P 500",None),("^IXIC","Nasdaq Composite",None),("^DJI","Dow Jones",None),
  ("OSEBX.OL","Oslo Børs (OSEBX)",None),("^GDAXI","DAX",None),("^VIX","VIX volatility",None),
  ("GC=F","Gold (USD/oz)",None),("^TNX","US 10-year yield (%)",None),("USDNOK=X","USD/NOK",None)]),
 ("Stocks", [
  ("KOG.OL","Kongsberg Gruppen","Kongsberg Gruppen"),("KMAR.OL","Kongsberg Maritime","Kongsberg Maritime")]),
 ("Tech Stocks", [
  ("AAPL","Apple","Apple stock"),("MSFT","Microsoft","Microsoft stock"),("NVDA","Nvidia","Nvidia stock"),
  ("GOOGL","Alphabet","Alphabet stock"),("AMZN","Amazon","Amazon stock"),("META","Meta Platforms","Meta stock"),
  ("TSLA","Tesla","Tesla stock")]),
]

ORDER=["Stocks","ETFs & Index Funds","Silver Mining","General Markets","Tech Stocks"]
SECTIONS.sort(key=lambda x: ORDER.index(x[0]))

def quote(sym):
    t = yf.Ticker(sym)
    h = t.history(period="7d")
    if h.empty: return None
    last = float(h.Close.iloc[-1]); prev = float(h.Close.iloc[-2]) if len(h) > 1 else None
    try: cur = t.fast_info.get("currency")
    except Exception: cur = None
    return {"price": last, "prev": prev, "chg": (last/prev-1)*100 if prev else None,
            "currency": cur, "asof": h.index[-1].isoformat()}

def news(q, n=4):
    exact = q.endswith(" Corp")
    if q.startswith("RAW:"):
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q[4:] + " when:7d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
    else:
     url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": f'"{q.replace(" Corp","")}" when:' + ("365d" if exact else "30d"), "hl": "en-US", "gl": "US", "ceid": "US:en"})
    try:
        root = ET.fromstring(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read())
    except Exception: return []
    out = []
    for it in root.iter("item"):
        title = it.findtext("title") or ""; src = it.findtext("source") or ""
        if src and title.endswith(" - " + src): title = title[:-len(src)-3]
        try: d = email.utils.parsedate_to_datetime(it.findtext("pubDate")).isoformat()
        except Exception: d = None
        if exact and q.lower() not in title.lower() and "defiance silver" not in title.lower(): continue
        out.append({"title": html.unescape(title), "link": it.findtext("link"), "source": src, "date": d})
    out.sort(key=lambda x: x["date"] or "", reverse=True)
    return out[:n+8]

fx = {k: quote(v) for k, v in {"USDNOK": "USDNOK=X"}.items()}
usdnok = fx["USDNOK"]["price"]
btc = quote("BTC-USD"); ag = quote("SI=F")
data = {"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(), "usdnok": usdnok,
        "btc": btc, "silver": ag, "sections": [], "failed": []}
for title, items in SECTIONS:
    sec = {"title": title, "part": 2 if title in ("General Markets","Tech Stocks") else 1, "items": []}
    for sym, name, q in items:
        try: qu = quote(sym)
        except Exception: qu = None
        if not qu: data["failed"].append(sym)
        sec["items"].append({"symbol": sym, "name": name, "quote": qu, "want": 2 if title in ("Silver Mining","Tech Stocks") else 4, "news": news(q) if q else None})
    data["sections"].append(sec)
gn = []
for q in ["stock market outlook", "stock market crash warning OR bubble", "recession risk economy", "Oslo Børs"]:
    gn += news("RAW:" + q, 5)
data["general_news"] = gn
import difflib
REP = ["reuters","bloomberg","financial times","wall street journal","cnbc","associated press","barron","marketwatch","e24","dn.no","yahoo finance","the globe and mail","kitco","investing.com","seeking alpha","motley fool"]
def rep(n):
    src = (n.get("source") or "").lower()
    return next((i for i, r in enumerate(REP) if r in src), len(REP))
def norm(t, src=""):
    t = t.lower()
    if src and t.endswith(" - " + src.lower()): t = t[:-len(src)-3]
    t = re.sub(r"\s[-|–—]\s[^-|–—]{2,40}$", "", t)
    return " ".join(re.sub(r"[^\w\s]", " ", t).split())
kept = []  # (url, normtitle, tokens)
def dup(n):
    nt = norm(n["title"], n.get("source", "")); tk = set(nt.split())
    for u, t, k in kept:
        if n.get("link") == u or nt == t: return True
        if difflib.SequenceMatcher(None, nt, t).ratio() > 0.85: return True
        if tk and k and len(tk & k) / min(len(tk), len(k)) > 0.85: return True
    return False
def pick(cands, want):
    # group near-duplicates within the candidate list: keep most reputable, then earliest
    cands = sorted(cands, key=lambda x: (rep(x), x["date"] or ""))
    out = []
    for n in cands:
        if len(out) >= want: break
        if dup(n): continue
        out.append(n); nt = norm(n["title"], n.get("source", ""))
        kept.append((n.get("link"), nt, set(nt.split())))
    return sorted(out, key=lambda x: x["date"] or "", reverse=True)
# most specific first: holdings (portfolio, then tech), general market feed last
for sec in sorted(data["sections"], key=lambda x: x["part"]):
    for it in sec["items"]:
        if it["news"] is not None: it["news"] = pick(it["news"], it.pop("want"))
        else: it.pop("want", None)
data["general_news"] = pick(data["general_news"], 12)
json.dump(data, open("markets/data.json", "w"), indent=1)
print("failed:", data["failed"])
