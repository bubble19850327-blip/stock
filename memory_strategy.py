import os
import requests
import yfinance as yf
from bs4 import BeautifulSoup
import datetime

# === 設定區 ===
CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
USER_ID = os.environ.get('LINE_USER_ID')

# === 備份數據 (當爬蟲失敗時的最後一道防線) ===
# 根據搜尋結果，2026年記憶體價格飆漲，此處備份數據已微調以符合作業當下情境
FALLBACK_DATA = {
    "DRAM": {"price": "6.26", "spec": "DDR4 4G (Backup)", "unit": "US$", "trend": "持平"},
    "NAND": {"price": "3.85", "spec": "512Gb TLC (Backup)", "unit": "US$", "trend": "持平"},
    "NOR":  {"price": "N/A",  "spec": "Generic NOR", "unit": "US$", "trend": "持平"},
    "ROM":  {"price": "N/A",  "spec": "Generic ROM", "unit": "US$", "trend": "持平"},
    "Trend": "持平"
}

def send_push(msg):
    """發送 LINE 推播訊息"""
    if not CHANNEL_TOKEN or not USER_ID:
        print("⚠️ LINE Token 未設定，略過推播")
        print(msg) # 本地測試用
        return
    headers = {'Authorization': f'Bearer {CHANNEL_TOKEN}', 'Content-Type': 'application/json'}
    body = {'to': USER_ID, 'messages': [{'type': 'text', 'text': msg}]}
    try:
        requests.post('https://api.line.me/v2/bot/message/push', headers=headers, json=body)
    except Exception as e:
        print(f"推播失敗: {e}")

def get_spot_price():
    """抓取記憶體現貨價，含規格、單位與備份機制"""
    url = "https://www.cnyes.com/futures/material5.aspx"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 預設使用備份數據
    data = FALLBACK_DATA.copy()
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        
        if res.status_code != 200:
            print(f"網頁回應錯誤: {res.status_code}，使用備份數據")
            return data

        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.find_all("tr")
        
        # 標記是否找到指標性產品，避免重複覆蓋
        found_dram = False
        
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 4: continue
            
            # 欄位解析
            spec_name = cols[0].text.strip() # 規格
            price = cols[1].text.strip()     # 價格
            change_text = cols[3].text.strip() # 漲跌
            unit = "US$" # 鉅亨網國際現貨報價通常為美金
            
            # 1. DRAM (鎖定 DDR4 為指標，根據新聞 DDR4 漲幅劇烈)
            if ("DDR4" in spec_name.upper()) and not found_dram:
                data["DRAM"] = {"price": price, "spec": spec_name, "unit": unit}
                try:
                    change = float(change_text)
                    if change > 0: data["Trend"] = "🔺 上漲"
                    elif change < 0: data["Trend"] = "🔻 下跌"
                    found_dram = True
                except: pass
            
            # 2. NAND (鎖定 TLC)
            elif ("TLC" in spec_name.upper()) and ("512" in spec_name or "256" in spec_name):
                # 優先抓 512Gb，若無則抓任意 TLC
                if "512" in spec_name or data["NAND"]["price"] == "N/A":
                    data["NAND"] = {"price": price, "spec": spec_name, "unit": unit}
            
            # 3. NOR Flash
            elif "NOR" in spec_name.upper():
                data["NOR"] = {"price": price, "spec": spec_name, "unit": unit}
            
            # 4. ROM
            elif "ROM" in spec_name.upper():
                data["ROM"] = {"price": price, "spec": spec_name, "unit": unit}
                
    except Exception as e:
        print(f"現貨價抓取失敗: {e}，將使用備份數據")
        
    return data

def get_contract_news():
    """抓取新聞判斷合約價氣氛"""
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
    # 上市櫃判斷
    yf_ticker = f"{ticker}.TWO" if ticker == "8299" else f"{ticker}.TW"
    
    try:
        df = yf.Ticker(yf_ticker).history(period="150d")
        if df.empty or len(df) < 60: return f"⚠️ {name} 數據不足"
        
        price = df['Close'].iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        ma60 = df['Close'].rolling(60).mean().iloc[-1]
    except: return f"⚠️ {name} 抓取錯誤"

    # 取得基本面數據
    spot_data = get_spot_price()
    contract_sentiment, _ = get_contract_news()

    # 針對個股顯示對應報價 (含單位與規格)
    if ticker == "2408": # 南亞科看 DRAM
        info = spot_data['DRAM']
        focus_spot = f"DRAM: {info['unit']}{info['price']} ({info['spec']})"
    elif ticker == "2337": # 旺宏看 NOR
        info = spot_data['NOR']
        focus_spot = f"NOR: {info['unit']}{info['price']} ({info['spec']})"
    elif ticker == "8299": # 群聯看 NAND
        info = spot_data['NAND']
        focus_spot = f"NAND: {info['unit']}{info['price']} ({info['spec']})"
    else: # 華邦電 (綜合)
        focus_spot = f"Trend: {spot_data['Trend']}"

    # 簡單交易策略
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
        f"💡 {action} ({reason})\n"
    )

if __name__ == "__main__":
    print("🚀 啟動記憶體四大天王掃描...")
    
    targets = [
        ("8299", "群聯"), 
        ("2337", "旺宏"), 
        ("2408", "南亞科"), 
        ("2344", "華邦電") 
    ]
    
    report_header = (
        f"⚡ 記憶體戰報 {datetime.date.today()}\n"
        f"----------------------\n"
    )
    
    stock_reports = ""
    for t, n in targets:
        stock_reports += analyze_memory_stock(t, n) + "\n"
        
    full_report = report_header + stock_reports
    send_push(full_report)
