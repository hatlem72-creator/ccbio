import json, datetime, urllib.parse, urllib.request, email.utils, re, html
import xml.etree.ElementTree as ET
import yfinance as yf

SECTIONS = [
 ("Silver & Precious-Metal Miners", [
  ("HL","Hecla Mining","Hecla Mining"),("HYMC","Hycroft Mining","Hycroft Mining"),
  ("ASM","Avino Silver & Gold","Avino Silver"),("CDE","Coeur Mining","Coeur Mining"),
  ("AG.TO","First Majestic Silver","First Majestic Silver"),("DEF.V","Defiance Silver","Defiance Silver"),
  ("GRSL.V","GR Silver Mining","GR Silver Mining"),("GSVR.V","Guanajuato Silver","Guanajuato Silver"),
  ("AGX.V","Silver X Mining","Silver X Mining")]),
 ("Funds & ETFs", [
  ("G2X.DE","VanEck Gold Miners UCITS ETF","VanEck Gold Miners"),
  ("0P0001IMY8.F","AuAg Silver Bullet B","AuAg Silver Bullet")]),
 ("Technology & Defence", [
  ("KOG.OL","Kongsberg Gruppen","Kongsberg Gruppen"),("KMAR.OL","Kongsberg Maritime","Kongsberg Maritime"),
  ("2B76.DE","iShares Automation & Robotics UCITS ETF","iShares Automation & Robotics")]),
]

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
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": f'"{q}" when:30d', "hl": "en-US", "gl": "US", "ceid": "US:en"})
    try:
        root = ET.fromstring(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read())
    except Exception: return []
    out = []
    for it in root.iter("item"):
        title = it.findtext("title") or ""; src = it.findtext("source") or ""
        if src and title.endswith(" - " + src): title = title[:-len(src)-3]
        try: d = email.utils.parsedate_to_datetime(it.findtext("pubDate")).isoformat()
        except Exception: d = None
        out.append({"title": html.unescape(title), "link": it.findtext("link"), "source": src, "date": d})
    out.sort(key=lambda x: x["date"] or "", reverse=True)
    return out[:n]

fx = {k: quote(v) for k, v in {"USDNOK": "USDNOK=X"}.items()}
usdnok = fx["USDNOK"]["price"]
btc = quote("BTC-USD"); ag = quote("SI=F")
data = {"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(), "usdnok": usdnok,
        "btc": btc, "silver": ag, "sections": [], "failed": []}
for title, items in SECTIONS:
    sec = {"title": title, "items": []}
    for sym, name, q in items:
        try: qu = quote(sym)
        except Exception: qu = None
        if not qu: data["failed"].append(sym)
        sec["items"].append({"symbol": sym, "name": name, "quote": qu, "news": news(q)})
    data["sections"].append(sec)
json.dump(data, open("markets/data.json", "w"), indent=1)
print("failed:", data["failed"])
