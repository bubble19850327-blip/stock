import requests
import yfinance as yf
import calendar
from datetime import datetime, date
from bs4 import BeautifulSoup
from config import TW_TZ, FALLBACK_DATA, CHANNEL_TOKEN, USER_ID

def send_push(msg):
    if not CHANNEL_TOKEN or not USER_ID: return
    headers = {'Authorization': f'Bearer {CHANNEL_TOKEN}', 'Content-Type': 'application/json'}
    body = {'to': USER_ID, 'messages': [{'type': 'text', 'text': msg}]}
    try: requests.post('https://api.line.me/v2/bot/message/push', headers=headers, json=body)
    except: pass

def get_vix():
    try: return yf.Ticker('^VIX').history(period='5d')['Close'].iloc[-1]
    except: return 0

def get_realtime_nav(ticker):
    try:
        stock_id = ticker.split('.')[0]
        url = f"https://tw.stock.yahoo.com/quote/{stock_id}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        elements = soup.find_all('li', class_='price-detail-item')
        for el in elements:
            if '淨值' in el.text:
                return float(el.find_all('span')[1].text.replace(',', ''))
    except: pass
    return None

def get_settlement_status():
    today = datetime.now(TW_TZ).date()
    cal = calendar.monthcalendar(today.year, today.month)
    wednesdays = [week[2] for week in cal if week[2] != 0]
    settlement_day = wednesdays[2]
    settlement_date = date(today.year, today.month, settlement_day)
    days_diff = (settlement_date - today).days

    if days_diff == 0: return "🔥 本日結算 (慎防波動)", 0
    elif days_diff == 1: return "⚠️ 明日結算 (提防壓盤)", 1
    elif days_diff == 2: return "⚠️ 本週結算 (震盪)", 2
    return "", days_diff

def get_futures_basis():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res_spot = requests.get('https://tw.stock.yahoo.com/quote/^TWII', headers=headers)
        soup_spot = BeautifulSoup(res_spot.text, 'html.parser')
        spot_price = float(soup_spot.find('span', class_='Fz(32px)').text.replace(',', ''))
        
        res_fut = requests.get('https://tw.stock.yahoo.com/quote/WTX-1.F', headers=headers)
        soup_fut = BeautifulSoup(res_fut.text, 'html.parser')
        fut_price = float(soup_fut.find('span', class_='Fz(32px)').text.replace(',', ''))
        return spot_price, fut_price, (fut_price - spot_price)
    except: return 0, 0, 0

def get_tx_night():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get('https://tw.stock.yahoo.com/quote/WTX-1.F', headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        price = float(soup.find('span', class_='Fz(32px)').text.replace(',', ''))
        pct = 0.0
        for span in soup.find_all('span'):
            if '%' in span.text and ('+' in span.text or '-' in span.text):
                try:
                    pct_str = span.text.replace('(', '').replace(')', '').replace('%', '').replace('+', '')
                    pct = float(pct_str)
                    break
                except: pass
        return price, pct
    except: return 0, 0

def get_trendforce_spot_price():
    url = "https://www.trendforce.com.tw/price/dram/dram_spot"
    headers = {"User-Agent": "Mozilla/5.0"}
    data = FALLBACK_DATA.copy()
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200: return data
        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.find_all("tr")
        found_dram = found_nand = False
        
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 5: continue
            spec_name = cols[0].text.strip()
            price = cols[2].text.strip()
            change_text = cols[4].text.strip()
            
            if "DDR4" in spec_name.upper() and not found_dram:
                data["DRAM"] = {"price": price, "spec": spec_name, "unit": "US$"}
                try:
                    change = float(change_text.replace('%', ''))
                    data["Trend"] = "🔺 上漲" if change > 0 else "🔻 下跌" if change < 0 else "持平"
                    found_dram = True
                except: pass
            elif "TLC" in spec_name.upper() and not found_nand:
                data["NAND"] = {"price": price, "spec": spec_name, "unit": "US$"}
                found_nand = True
            elif "NOR" in spec_name.upper():
                data["NOR"] = {"price": price, "spec": spec_name, "unit": "US$"}
    except: pass
    return data

def get_contract_news():
    url = "https://news.google.com/rss/search?q=記憶體+合約價+when:7d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, "xml")
        titles = [item.title.text for item in soup.find_all("item", limit=3)]
        sentiment = "無重大消息"
        for t in titles:
            if "漲" in t or "回升" in t: sentiment = "📈 預期看漲"
            elif "跌" in t or "降" in t: sentiment = "📉 預期看跌"
        return sentiment
    except: return "N/A"
