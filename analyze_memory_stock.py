import os
import requests
import yfinance as yf
from bs4 import BeautifulSoup

# === 設定區 (請確保環境變數已設定) ===
CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
USER_ID = os.environ.get('LINE_USER_ID')

def send_push(msg):
    """發送 LINE 推播訊息"""
    if not CHANNEL_TOKEN or not USER_ID:
        print("⚠️ LINE Token 未設定，跳過推播")
        print(msg) # 本地測試用
        return
    headers = {'Authorization': f'Bearer {CHANNEL_TOKEN}', 'Content-Type': 'application/json'}
    body = {'to': USER_ID, 'messages': [{'type': 'text', 'text': msg}]}
    try:
        requests.post('https://api.line.me/v2/bot/message/push', headers=headers, json=body)
    except Exception as e:
        print(f"推播失敗: {e}")

def get_spot_price():
    """抓取記憶體現貨價 (來源: 鉅亨網) - 擴充 NAND, NOR, ROM"""
    url = "https://www.cnyes.com/futures/material5.aspx"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    data = {"DRAM": "N/A", "NAND": "N/A", "NOR": "N/A", "ROM": "N/A", "Trend": "持平"}
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.find_all("tr")
        
        for row in rows:
            text = row.text.strip().upper()
            cols = row.find_all("td")
            if len(cols) < 4: continue
            
            price = cols[1].text.strip()
            change_text = cols[3].text.strip()
            
            # 1. DRAM (以 DDR4 為指標)
            if ("DDR4" in text) and data["DRAM"] == "N/A":
                data["DRAM"] = price
                try:
                    change = float(change_text)
                    if change > 0: data["Trend"] = "🔺 上漲"
                    elif change < 0: data["Trend"] = "🔻 下跌"
                except: pass
            
            # 2. NAND (以 TLC/MLC 為指標)
            elif ("TLC" in text or "NAND" in text) and data["NAND"] == "N/A":
                data["NAND"] = price
            
            # 3. NOR Flash
            elif "NOR" in text and data["NOR"] == "N/A":
                data["NOR"] = price
            
            # 4. ROM
            elif "ROM" in text and data["ROM"] == "N/A":
                data["ROM"] = price
                
    except Exception as e:
        print(f"現貨價抓取失敗: {e}")
    return data

def get_contract_news():
    """抓取 Google 新聞判斷合約價氣氛"""
    url = "https://news.google.com/rss/search?q=記憶體+合約價+when:7d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, "xml")
        items = soup.find_all("item", limit=3)
        
        sentiment = "無重大消息"
        titles = []
        for item in items:
            t = item.title.text
            titles.append(t)
            if "漲" in t or "回升" in t: sentiment = "📈 預期看漲"
            elif "跌" in t or "降" in t: sentiment = "📉 預期看跌"
            
        return sentiment, titles
    except: return "N/A", []

def analyze_memory_stock(ticker, name):
    """個股分析核心邏輯"""
    # 判斷上市櫃：8299 為上櫃 (.TWO)，其餘為上市 (.TW)
    yf_ticker = f"{ticker}.TWO" if ticker == "8299" else f"{ticker}.TW"
    
    try:
        df = yf.Ticker(yf_ticker).history(period="150d")
        if df.empty or len(df) < 60: return f"⚠️ {name} 數據不足"
        
        price = df['Close'].iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        ma60 = df['Close'].rolling(60).mean().iloc[-1]
    except: return f"⚠️ {name} 抓取錯誤"

    # 取得共用基本面
    spot_data = get_spot_price()
    contract_sentiment, _ = get_contract_news()

    # 針對個股關注不同報價
    if ticker == "2408": focus_spot = f"DRAM: {spot_data['DRAM']}"
    elif ticker == "2337": focus_spot = f"NOR: {spot_data['NOR']}"
    elif ticker == "8299": focus_spot = f"NAND: {spot_data['NAND']}"
    else: focus_spot = f"Trend: {spot_data['Trend']}"

    # 交易策略
    action = "觀望 (Wait)"
    reason = "多空不明"
    
    if spot_data['Trend'] == "🔺 上漲" and price > ma20:
        action, reason = "🔥 順勢買進", "報價漲+站穩月線"
    elif spot_data['Trend'] == "🔻 下跌" and price < ma20:
        action, reason = "⚠️ 避險賣出", "報價跌+跌破月線"
    elif contract_sentiment == "📈 預期看漲" and price < ma60:
        action, reason = "💎 價值佈局", "合約漲+回測季線"

    return (
        f"💾 【{name} {ticker}】\n"
        f"現價: {price:.1f} (MA60: {ma60:.1f})\n"
        f"焦點: {focus_spot}\n"
        f"💡 {action}\n"
        f"📝 {reason}\n"
    )

if __name__ == "__main__":
    print("🚀 啟動記憶體族群掃描...")
    
    targets = [
        ("8299", "群聯"), # NAND controller
        ("2337", "旺宏"), # NOR Flash
        ("2408", "南亞科"), # DRAM
        ("2344", "華邦電") # Specialty DRAM/Flash
    ]
    
    # 產出總報告
    report_header = (
        f"⚡ 記憶體戰報 {os.environ.get('Today', '')}\n"
        f"----------------------\n"
    )
    
    stock_reports = ""
    for t, n in targets:
        stock_reports += analyze_memory_stock(t, n) + "\n"
        
    full_report = report_header + stock_reports
    send_push(full_report)
