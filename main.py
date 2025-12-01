import os
import requests
import yfinance as yf
import pandas_ta as ta
from datetime import datetime

# === 設定區 ===
CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
USER_ID = os.environ.get('LINE_USER_ID')

# 定義股票清單
TW_TICKERS = ['00631L.TW', '00675L.TW', '0050.TW']
# 美股科技巨頭 (Mag 7 + TSM)
US_TICKERS = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'TSM']

def send_push(msg):
    """發送 LINE 推播"""
    if not CHANNEL_TOKEN or not USER_ID: return
    headers = {"Authorization": f"Bearer {CHANNEL_TOKEN}", "Content-Type": "application/json"}
    body = {"to": USER_ID, "messages": [{"type": "text", "text": msg}]}
    try: requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=body)
    except: pass

def get_vix():
    """抓取恐慌指數 (美股盤後數據)"""
    try: return yf.Ticker("^VIX").history(period="5d")['Close'].iloc[-1]
    except: return 0

def analyze_strategy(ticker, current_vix):
    try:
        # 1. 抓取數據 (美股收盤後，台灣下午抓得到最新日K)
        df = yf.Ticker(ticker).history(period="200d") # 美股看長一點，抓200天
        if len(df) < 120: return ""

        price = df['Close'].iloc[-1]
        
        # 2. 技術指標
        ma60 = df['Close'].rolling(60).mean().iloc[-1]   # 季線
        ma120 = df['Close'].rolling(120).mean().iloc[-1] # 半年線
        bias = ((price - ma60) / ma60) * 100             # 乖離率
        
        adx_df = df.ta.adx(length=14)
        adx = adx_df['ADX_14'].iloc[-1] if adx_df is not None and not adx_df.empty else 0

        # 3. 判斷邏輯 (美股與槓桿ETF共用邏輯：波動大、趨勢強)
        is_us_stock = ticker in US_TICKERS
        title_icon = "🇺🇸" if is_us_stock else "🇹🇼"
        
        action = "信仰續抱 (Hold)"
        icon = "💎"
        reason = f"趨勢行進 (ADX={adx:.1f})"

        # A. 停利機制 (美股波動大，乖離標準稍微放寬)
        profit_gate = 30 if is_us_stock else 25
        if bias > profit_gate:
            action = f"🚀 網格停利 ({profit_gate}%+)"
            icon = "💰💰"
            reason = f"乖離過熱 > {profit_gate}% ({bias:.1f}%)"
        
        # B. 恐慌買進 (VIX 濾網)
        elif current_vix > 30 and price < ma120:
            action = "💎 恐慌鑽石買 (All In)"
            icon = "🔥🔥🔥"
            reason = f"VIX飆高({current_vix:.1f}) + 跌破半年線"
            
        # C. 價值買進
        elif price < ma120:
            action = "🔥 重擊加碼 (Buy 20%)"
            icon = "🟢🟢"
            reason = "跌破半年線，嚴重超跌"
        elif price < ma60:
            action = "✨ 試單加碼 (Buy 10%)"
            icon = "🟢"
            reason = "跌破季線，價值浮現"

        return (
            f"\n\n📊 【{title_icon} {ticker}】"
            f"\n現價: {price:.2f} (乖離 {bias:.1f}%)"
            f"\n關鍵均線: 季{ma60:.0f} / 半{ma120:.0f}"
            f"\n💡 建議: {icon} {action}"
            f"\n📝 理由: {reason}"
        )

    except Exception as e:
        return f"\n⚠️ {ticker} 錯誤: {e}"

if __name__ == "__main__":
    print("🚀 執行台美股全域掃描...")
    vix = get_vix()
    report = f"⚡ {datetime.now().strftime('%Y-%m-%d')} 投資戰報\n🌎 VIX: {vix:.2f}"
    
    # 合併掃描
    all_tickers = TW_TICKERS + US_TICKERS
    for t in all_tickers:
        report += analyze_strategy(t, vix)
    
    send_push(report)
