import os
import requests
import yfinance as yf
import pandas_ta as ta
from bs4 import BeautifulSoup
from datetime import datetime

# === 設定區 ===
CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
USER_ID = os.environ.get('LINE_USER_ID')

def send_push(msg):
    if not CHANNEL_TOKEN or not USER_ID: return
    headers = {"Authorization": f"Bearer {CHANNEL_TOKEN}", "Content-Type": "application/json"}
    body = {"to": USER_ID, "messages": [{"type": "text", "text": msg}]}
    try: requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=body)
    except: pass

def get_spot_price():
    """抓取記憶體現貨價 (來源: 鉅亨網)"""
    url = "https://www.cnyes.com/futures/material5.aspx"
    headers = {"User-Agent": "Mozilla/5.0"}
    data = {"DRAM": "N/A", "NAND": "N/A", "Trend": "持平"}
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.find_all("tr")
        
        for row in rows:
            text = row.text.strip()
            # 抓取指標性產品
            if "DDR4 8G" in text and data["DRAM"] == "N/A":
                cols = row.find_all("td")
                data["DRAM"] = cols[1].text.strip()
                change = float(cols[3].text.strip())
                if change > 0: data["Trend"] = "🔺 上漲"
                elif change < 0: data["Trend"] = "🔻 下跌"
            
            if "512Gb TLC" in text and data["NAND"] == "N/A":
                cols = row.find_all("td")
                data["NAND"] = cols[1].text.strip()
    except: pass
    return data

def get_contract_news():
    """搜尋合約價相關新聞 (模擬合約價趨勢)"""
    # 這裡使用 Google News RSS 搜尋關鍵字
    url = "https://news.google.com/rss/search?q=記憶體+合約價+when:7d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, "xml")
        items = soup.find_all("item", limit=3) # 只看最新的 3 則
        
        news_sentiment = "無重大消息"
        titles = []
        for item in items:
            title = item.title.text
            titles.append(title)
            if "漲" in title or "回升" in title: news_sentiment = "📈 預期看漲"
            elif "跌" in title or "降" in title: news_sentiment = "📉 預期看跌"
            
        return news_sentiment, titles
    except:
        return "N/A", []

def analyze_phison():
    ticker = "8299.TW"
    
    # 1. 抓取股價
    df = yf.Ticker(ticker).history(period="150d")
    if len(df) < 60: return "⚠️ 數據不足"
    
    price = df['Close'].iloc[-1]
    ma20 = df['Close'].rolling(20).mean().iloc[-1]
    ma60 = df['Close'].rolling(60).mean().iloc[-1]
    
    # 2. 抓取基本面數據
    spot_data = get_spot_price()
    contract_sentiment, news_titles = get_contract_news()
    
    # 3. 綜合分析
    action = "觀望 (Wait)"
    reason = "多空不明"
    
    # 策略邏輯：現貨漲 + 股價強 = 買進
    if spot_data["Trend"] == "🔺 上漲" and price > ma20:
        action = "🔥 順勢買進"
        reason = "現貨報價上揚且股價站穩月線"
    elif spot_data["Trend"] == "🔻 下跌" and price < ma20:
        action = "⚠️ 避險賣出"
        reason = "現貨跌勢不止且股價轉弱"
    elif contract_sentiment == "📈 預期看漲" and price < ma60:
        action = "💎 價值佈局"
        reason = "合約價看漲，股價回測季線有撐"

    # 4. 產出報告
    report = (
        f"💾 【群聯 8299 專題報告】\n"
        f"股價: {price:.1f} (MA60: {ma60:.1f})\n"
        f"----------------------\n"
        f"📊 現貨市場 (Daily):\n"
        f"• DRAM: {spot_data['DRAM']}\n"
        f"• NAND: {spot_data['NAND']}\n"
        f"• 趨勢: {spot_data['Trend']}\n"
        f"----------------------\n"
        f"📑 合約市場 (News):\n"
        f"• 氣氛: {contract_sentiment}\n"
        f"• 焦點: {news_titles[0] if news_titles else '無'}\n"
        f"----------------------\n"
        f"💡 建議: {action}\n"
        f"📝 理由: {reason}"
    )
    return report

if __name__ == "__main__":
    print("🚀 執行群聯專題分析...")
    report = analyze_phison()
    send_push(report)
