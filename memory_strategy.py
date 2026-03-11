import os
import requests
import yfinance as yf
from bs4 import BeautifulSoup
import datetime

# === 設定區 ===
CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
USER_ID = os.environ.get('LINE_USER_ID')

FALLBACK_DATA = {
    "DRAM": {"price": "14.70", "spec": "DDR4 16Gb eTT (Backup)", "unit": "US$", "trend": "持平"},
    "NAND": {"price": "3.85", "spec": "512Gb TLC (Backup)", "unit": "US$", "trend": "持平"},
    "NOR":  {"price": "N/A",  "spec": "Generic NOR", "unit": "", "trend": "持平"},
    "ROM":  {"price": "N/A",  "spec": "Generic ROM", "unit": "", "trend": "持平"},
    "Trend": "🔺 上漲"
}

def send_push(msg):
    if not CHANNEL_TOKEN or not USER_ID:
        print("⚠️ LINE Token 未設定，略過推播\n", msg)
        return
    headers = {'Authorization': f'Bearer {CHANNEL_TOKEN}', 'Content-Type': 'application/json'}
    body = {'to': USER_ID, 'messages': [{'type': 'text', 'text': msg}]}
    requests.post('https://api.line.me/v2/bot/message/push', headers=headers, json=body)

def get_trendforce_spot_price():
    """從 TrendForce 抓取記憶體現貨價"""
    url = "https://www.trendforce.com.tw/price/dram/dram_spot"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    data = FALLBACK_DATA.copy()
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200: return data

        soup = BeautifulSoup(res.text, "html.parser")
        # TrendForce 報價通常在 class="table" 內的 tbody 中
        rows = soup.find_all("tr")
        found_dram = found_nand = False
        
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 5: continue
            
            spec_name = cols[0].text.strip()
            # TrendForce 通常 Average/Session 價格在索引 2 或 3，漲跌幅在 4 或 5
            # 這裡我們取 Session Price 作為參考 (假設為 index 2)
            price = cols[2].text.strip()
            change_text = cols[4].text.strip()
            
            # DRAM (以 DDR4 為主)
            if "DDR4" in spec_name.upper() and not found_dram:
                data["DRAM"] = {"price": price, "spec": spec_name, "unit": "US$"}
                try:
                    change = float(change_text.replace('%', ''))
                    data["Trend"] = "🔺 上漲" if change > 0 else "🔻 下跌" if change < 0 else "持平"
                    found_dram = True
                except: pass
                
            # NAND (TLC)
            elif "TLC" in spec_name.upper() and not found_nand:
                data["NAND"] = {"price": price, "spec": spec_name, "unit": "US$"}
                found_nand = True
                
            # NOR (若 TrendForce 有提供)
            elif "NOR" in spec_name.upper():
                data["NOR"] = {"price": price, "spec": spec_name, "unit": "US$"}
                
    except Exception as e:
        print(f"TrendForce 爬蟲失敗: {e}，使用備份數據")
        
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

def format_price_display(info):
    """處理 N/A 時不顯示單位的問題"""
    if info['price'] == "N/A":
        return f"N/A ({info['spec']})"
    return f"{info['unit']}{info['price']} ({info['spec']})"

def analyze_memory_stock(ticker, name, spot_data, contract_sentiment):
    yf_ticker = f"{ticker}.TWO" if ticker == "8299" else f"{ticker}.TW"
    try:
        df = yf.Ticker(yf_ticker).history(period="150d")
        if df.empty or len(df) < 60: return f"⚠️ {name} 數據不足"
        price = df['Close'].iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        ma60 = df['Close'].rolling(60).mean().iloc[-1]
    except: return f"⚠️ {name} 抓取錯誤"

    # 顯示對應焦點
    if ticker == "2408": focus_spot = f"DRAM: {format_price_display(spot_data['DRAM'])}"
    elif ticker == "2337": focus_spot = f"NOR: {format_price_display(spot_data['NOR'])}"
    elif ticker == "8299": focus_spot = f"NAND: {format_price_display(spot_data['NAND'])}"
    else: focus_spot = f"整體趨勢: {spot_data['Trend']}"

    # 策略判斷
    action, reason = "👀 觀望 (Wait)", "多空不明"
    if spot_data['Trend'] == "🔺 上漲" and price > ma20:
        action, reason = "🔥 順勢買進", "報價漲 + 站穩月線"
    elif spot_data['Trend'] == "🔻 下跌" and price < ma20:
        action, reason = "⚠️ 避險賣出", "報價跌 + 破月線"
    elif contract_sentiment == "📈 預期看漲" and price < ma60:
        action, reason = "💎 價值佈局", "合約漲 + 回測季線"

    # 優化排版：同行顯示現價與均線，縮減行數
    return (
        f"💾 【{name} {ticker}】\n"
        f"現價: {price:.1f} | 季線: {ma60:.1f}\n"
        # f"焦點: {focus_spot}\n"
        f"💡 {action} \n ({reason})\n"
    )

if __name__ == "__main__":
    global_spot = get_trendforce_spot_price()
    global_sentiment = get_contract_news()
    
    targets = [("8299", "群聯"), ("2337", "旺宏"), ("2408", "南亞科"), ("2344", "華邦電")]
    
    # 使用更明顯的分隔線
    full_report = f"⚡ 記憶體戰報 {datetime.date.today()}\n━━━━━━━━━━━━━\n"
    
    for t, n in targets:
        full_report += analyze_memory_stock(t, n, global_spot, global_sentiment) + "\n"
        
    send_push(full_report.strip())
