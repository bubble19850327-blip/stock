import os
import sys
import requests
import yfinance as yf
import pandas_ta as ta
import calendar
from datetime import datetime, date
from bs4 import BeautifulSoup

# === 設定區 ===
CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
USER_ID = os.environ.get('LINE_USER_ID')

TW_TICKERS = ['00631L.TW', '00675L.TW', '0050.TW']
US_TICKERS = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'TSM']

def send_push(msg):
    """發送 LINE 推播"""
    if not CHANNEL_TOKEN or not USER_ID: return
    headers = {"Authorization": f"Bearer {CHANNEL_TOKEN}", "Content-Type": "application/json"}
    body = {"to": USER_ID, "messages": [{"type": "text", "text": msg}]}
    try: requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=body)
    except: pass

# === 基礎數據獲取 ===
def get_vix():
    """抓取美股恐慌指數"""
    try: return yf.Ticker("^VIX").history(period="5d")['Close'].iloc[-1]
    except: return 0

def get_realtime_nav(ticker):
    """爬取 Yahoo 股市抓取即時淨值 (計算溢價用)"""
    try:
        stock_id = ticker.split('.')[0]
        url = f"https://tw.stock.yahoo.com/quote/{stock_id}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        elements = soup.find_all("li", class_="price-detail-item")
        for el in elements:
            if "淨值" in el.text:
                return float(el.find_all("span")[1].text.replace(",", ""))
    except: pass
    return None

def get_settlement_status():
    """計算台指期結算日 (每月第3個週三)"""
    today = datetime.now().date()
    cal = calendar.monthcalendar(today.year, today.month)
    # week[2] 是星期三，若為0代表該週沒這天
    wednesdays = [week[2] for week in cal if week[2] != 0]
    settlement_day = wednesdays[2]
    settlement_date = date(today.year, today.month, settlement_day)
    days_diff = (settlement_date - today).days

    if days_diff == 0: return "🔥 本日結算 (慎防波動)", 0
    elif days_diff == 1: return "⚠️ 明日結算 (提防壓盤)", 1
    elif days_diff == 2: return "⚠️ 本週結算 (震盪)", 2
    return "", days_diff

def get_futures_basis():
    """抓取台指期與大盤，計算價差 (Basis)"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        # 抓大盤
        res_spot = requests.get("https://tw.stock.yahoo.com/quote/^TWII", headers=headers)
        soup_spot = BeautifulSoup(res_spot.text, "html.parser")
        spot_price = float(soup_spot.find("span", class_="Fz(32px)").text.replace(",", ""))
        
        # 抓期貨
        res_fut = requests.get("https://tw.stock.yahoo.com/quote/WTX-1.F", headers=headers)
        soup_fut = BeautifulSoup(res_fut.text, "html.parser")
        fut_price = float(soup_fut.find("span", class_="Fz(32px)").text.replace(",", ""))
        
        return spot_price, fut_price, (fut_price - spot_price)
    except:
        return 0, 0, 0

# === 策略模組 ===
def analyze_pre_open(data):
    """08:00 盤前分析"""
    tsm, ndx, vix = data['tsm'], data['ndx'], data['vix']
    sentiment = "😐 中性"
    if tsm > 2.5: sentiment = "🔥 極度樂觀"
    elif tsm < -2.5: sentiment = "❄️ 極度悲觀"
    
    advice_0050 = "觀望"
    if tsm < -2: advice_0050 = "✅ 掛低買進"
    elif vix > 30: advice_0050 = "💎 恐慌貪婪買"
    
    return f"🌅 08:00 盤前戰報\n氣氛: {sentiment}\nTSM: {tsm:+.2f}%\nVIX: {vix:.1f}\n💡 0050: {advice_0050}"

def analyze_strategy(ticker, current_vix):
    """13:20 盤中/收盤分析"""
    try:
        df = yf.Ticker(ticker).history(period="200d")
        if len(df) < 120: return ""
        price = df['Close'].iloc[-1]
        ma60 = df['Close'].rolling(60).mean().iloc[-1]
        ma120 = df['Close'].rolling(120).mean().iloc[-1]
        bias = ((price - ma60) / ma60) * 100
        adx = df.
