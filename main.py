import os
import sys
import requests
import yfinance as yf
import pandas_ta as ta
from datetime import datetime
from bs4 import BeautifulSoup

# === 設定區 ===
CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
USER_ID = os.environ.get('LINE_USER_ID')

TW_TICKERS = ['00631L.TW', '00675L.TW', '0050.TW']
US_TICKERS = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'TSM']

def send_push(msg):
    """發送 LINE 推播"""
    if not CHANNEL_TOKEN or not USER_ID:
        print("❌ 錯誤：未讀取到 Token 或 User ID")
        return
    headers = {"Authorization": f"Bearer {CHANNEL_TOKEN}", "Content-Type": "application/json"}
    body = {"to": USER_ID, "messages": [{"type": "text", "text": msg}]}
    try:
        requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=body)
        print("✅ LINE 通知已發送")
    except Exception as e:
        print(f"❌ 發送失敗: {e}")

def get_vix():
    """抓取美股恐慌指數"""
    try: return yf.Ticker("^VIX").history(period="5d")['Close'].iloc[-1]
    except: return 0

# === 新增功能：抓取即時淨值 ===
def get_realtime_nav(ticker):
    """
    爬取 Yahoo 奇摩股市的 '淨值'
    注意：這通常是 '昨日淨值' 或 '即時預估淨值' (視網站更新而定)
    """
    try:
        # 轉換代號 (yfinance 是 0050.TW -> Yahoo 是 0050)
        stock_id = ticker.split('.')[0] 
        url = f"https://tw.stock.yahoo.com/quote/{stock_id}"
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")
        
        # 尋找含有 "淨值" 字眼的區塊 (Yahoo 網頁結構可能會變，這是通用抓法)
        # 通常在詳細報價欄位中
        elements = soup.find_all("li", class_="price-detail-item")
        
        for el in elements:
            if "淨值" in el.text:
                # 抓取數值部分
                val_text = el.find_all("span")[1].text
                return float(val_text.replace(",", ""))
                
    except Exception as e:
        print(f"⚠️ 淨值抓取失敗 {ticker}: {e}")
        
    return None

# === 模組 A: 盤前分析 (08:00) ===
def get_overnight_data():
    tickers = ['TSM', '^SOX', '^NDX', '^VIX']
    data = yf.download(tickers, period="5d", progress=False)['Close']
    changes = data.pct_change().iloc[-1] * 100
    last_close = data.iloc[-1]
    return {'tsm': changes['TSM'], 'sox': changes['^SOX'], 'ndx': changes['^NDX'], 'vix': last_close['^VIX']}

def analyze_pre_open(data):
    tsm, ndx, vix = data['tsm'], data['ndx'], data['vix']
    sentiment = "😐 中性"
    if tsm > 2.5: sentiment = "🔥 極度樂觀"
    elif tsm < -2.5: sentiment = "❄️ 極度悲觀"
    
    advice_0050 = "觀望"
    if tsm < -2: advice_0050 = "✅ 掛低買進"
    elif vix > 30: advice_0050 = "💎 恐慌貪婪買"
    
    advice_lev = "續抱"
    if tsm > 3: advice_lev = "⚠️ 勿追高/調節"
    elif tsm < -3 and vix > 30: advice_lev = "💎 鑽石買點"

    return f"🌅 08:00 盤前戰報\n氣氛: {sentiment}\nTSM: {tsm:+.2f}%\n0050: {advice_0050}\n正二: {advice_lev}"

# === 模組 B: 盤中策略 (12:30/13:20) ===
def analyze_strategy(ticker, current_vix):
    try:
        # 1. 抓取技術面數據
        df = yf.Ticker(ticker).history(period="200d")
        if len(df) < 120: return ""
        price = df['Close'].iloc[-1]
        ma60 = df['Close'].rolling(60).mean().iloc[-1]
        ma120 = df['Close'].rolling(120).mean().iloc[-1]
        bias = ((price - ma60) / ma60) * 100
        adx = df.ta.adx(length=14)['ADX_14'].iloc[-1] if df.ta.adx(length=14) is not None else 0
        
        is_us = ticker in US_TICKERS
        title_icon = "🇺🇸" if is_us else "🇹🇼"

        # 2. 抓取淨值與計算溢價 (僅針對台股 ETF)
        premium_msg = ""
        is_premium_high = False
        
        if not is_us and "0050" not in ticker: # 0050溢價通常不大，主要看正二
            nav = get_realtime_nav(ticker)
            if nav:
                premium = ((price - nav) / nav) * 100
                premium_msg = f"/ 溢價: {premium:+.2f}%"
                
                # 溢價判斷邏輯
                if premium > 3.0:
                    is_premium_high = True
                    premium_msg += " 🔥太貴"
                elif premium < -1.0:
                    premium_msg += " 💧折價"

        # 3. 策略邏輯
        action = "信仰續抱"
        icon = "💎"
        reason = f"ADX={adx:.1f}"

        # 【策略 A：0050 存股】
        if ticker == '0050.TW':
            k_val = df.ta.stoch(k=9, d=3)['STOCHk_9_3_3'].iloc[-1]
            if current_vix > 30: action, icon, reason = "💎 恐慌貪婪買", "🔥🔥", f"VIX飆高 {current_vix:.1f}"
            elif k_val < 20: action, icon, reason = "💰 KD超賣買", "📉", "KD低檔"
            elif price < df['Open'].iloc[-1]: action, icon, reason = "✅ 收綠買進", "🌱", "日常累積"
            else: action, icon, reason = "觀望", "👀", "暫不追高"

        # 【策略 B：槓桿/科技股】
        else:
            profit_gate = 30 if is_us else 25
            
            # 優先檢查：是否溢價過大 (送分題)
            if is_premium_high:
                action = "💎 溢價套利 (強力賣出)"
                icon = "💸"
                reason = f"溢價過大(>3%)，價格虛高"
            # 其次檢查：技術面乖離
            elif bias > profit_gate:
                action = f"🚀 網格停利", "💰"
                reason = f"乖離過熱 {bias:.1f}%"
            # 再來檢查：買點
            elif price < ma120 and current_vix > 30:
                action, icon, reason = "💎 恐慌鑽石買", "🔥🔥🔥", "半年線+VIX爆表"
            elif price < ma60:
                action, icon, reason = "✨ 試單加碼", "🟢", "季線價值浮現"
            elif adx < 20:
                action, icon, reason = "⚠️ 盤整忍耐", "🧘", "無趨勢避耗損"

        return f"\n\n📊 【{title_icon} {ticker}】\n現價: {price:.2f} (乖離 {bias:.1f}%)\n{premium_msg}\n💡 {icon} {action}\n📝 {reason}"

    except Exception as e:
        return f"\n⚠️ {ticker} 錯誤: {e}"

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    print(f"🚀 啟動模式: {mode}")

    if mode == "pre_open":
        data = get_overnight_data()
        report = analyze_pre_open(data)
        send_push(report)
    else:
        # 決定跑哪些股票
        target_list = []
        if mode == "us": target_list = US_TICKERS
        elif mode == "tw": target_list = TW_TICKERS
        else: target_list = TW_TICKERS + US_TICKERS
        
        vix = get_vix()
        report = f"⚡ 投資戰報 {datetime.now().strftime('%m-%d %H:%M')}\n🌎 VIX: {vix:.2f}"
        
        for t in target_list:
            report += analyze_strategy(t, vix)
        
        send_push(report)
