import os
import sys
import requests
import yfinance as yf
import pandas_ta as ta
from datetime import datetime

# === 設定區 ===
CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
USER_ID = os.environ.get('LINE_USER_ID')

# 股票清單
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
    """抓取恐慌指數"""
    try: return yf.Ticker("^VIX").history(period="5d")['Close'].iloc[-1]
    except: return 0

# === 模組 A: 盤前分析 (08:00) ===
def get_overnight_data():
    """抓取美股收盤數據 (TSM, SOX, NDX, VIX)"""
    tickers = ['TSM', '^SOX', '^NDX', '^VIX']
    data = yf.download(tickers, period="5d", progress=False)['Close']
    
    changes = data.pct_change().iloc[-1] * 100
    last_close = data.iloc[-1]
    
    return {
        'tsm': changes['TSM'],
        'sox': changes['^SOX'],
        'ndx': changes['^NDX'],
        'vix': last_close['^VIX']
    }

def analyze_pre_open(data):
    """盤前策略建議"""
    tsm = data['tsm']
    ndx = data['ndx']
    vix = data['vix']
    
    sentiment = "😐 中性震盪"
    if tsm > 2.5 or ndx > 1.5: sentiment = "🔥 極度樂觀 (美股帶動)"
    elif tsm < -2.5 or ndx < -1.5: sentiment = "❄️ 極度悲觀 (美股重挫)"
    elif tsm > 1: sentiment = "📈 偏多看待"
    elif tsm < -1: sentiment = "📉 偏空看待"

    advice_0050 = "觀望 (Wait)"
    advice_lev = "續抱 (Hold)"

    if tsm < -2: advice_0050 = "✅ 掛低買進 (撿便宜)"
    elif vix > 30: advice_0050 = "💎 恐慌貪婪買 (All In)"
    
    if tsm > 3: advice_lev = "⚠️ 勿追高 / 考慮調節"
    elif tsm < -3 and vix < 25: advice_lev = "✋ 暫緩加碼"
    elif tsm < -3 and vix > 30: advice_lev = "💎 鑽石買點"

    return (
        f"🌅 【08:00 盤前戰報】\n"
        f"昨夜氣氛: {sentiment}\n"
        f"------------------\n"
        f"🇺🇸 TSM ADR: {tsm:+.2f}%\n"
        f"🇺🇸 納斯達克: {ndx:+.2f}%\n"
        f"🌎 VIX 指數: {vix:.2f}\n"
        f"------------------\n"
        f"💡 0050: {advice_0050}\n"
        f"💡 正二: {advice_lev}\n"
        f"📝 預判台積開盤: {tsm:+.1f}%"
    )

# === 模組 B: 盤中策略 (12:30/13:20) ===
def analyze_strategy(ticker, current_vix):
    try:
        df = yf.Ticker(ticker).history(period="200d")
        if len(df) < 120: return ""

        price = df['Close'].iloc[-1]
        open_price = df['Open'].iloc[-1]
        is_us = ticker in US_TICKERS
        title_icon = "🇺🇸" if is_us else "🇹🇼"

        # 【策略 A：0050 存股】
        if ticker == '0050.TW':
            stoch = df.ta.stoch(k=9, d=3, smooth_k=3)
            k_val = stoch['STOCHk_9_3_3'].iloc[-1]
            is_green = price < open_price
            
            action = "觀望 / 續抱"
            icon = "👀"
            reason = "暫不追高"

            if current_vix > 30:
                action, icon = "💎 恐慌貪婪買", "🔥🔥"
                reason = f"VIX飆高 {current_vix:.1f}"
            elif k_val < 20:
                action, icon = "💰 KD超賣買進", "📉"
                reason = f"KD={k_val:.1f} 低檔鈍化"
            elif is_green:
                action, icon = "✅ 定期買進 (收綠)", "🌱"
                reason = "買綠不買紅"

            return f"\n\n📊 【{title_icon} {ticker}】\n現價: {price:.2f}\nKD: {k_val:.1f} / VIX: {current_vix:.1f}\n💡 {icon} {action}\n📝 {reason}"

        # 【策略 B：槓桿/科技股】
        else:
            ma60 = df['Close'].rolling(60).mean().iloc[-1]
            ma120 = df['Close'].rolling(120).mean().iloc[-1]
            bias = ((price - ma60) / ma60) * 100
            adx_df = df.ta.adx(length=14)
            adx = adx_df['ADX_14'].iloc[-1] if adx_df is not None and not adx_df.empty else 0

            action, icon = "信仰續抱", "💎"
            reason = f"趨勢行進 (ADX={adx:.1f})"
            
            profit_gate = 30 if is_us else 25 # 停利門檻

            if bias > profit_gate:
                action, icon = f"🚀 網格停利 ({profit_gate}%)", "💰💰"
                reason = f"乖離過熱 {bias:.1f}%"
            elif bias > (profit_gate-5) and current_vix < 13:
                action, icon = "⚠️ 安逸警示 (Sell)", "🟠"
                reason = "市場過度樂觀"
            elif price < ma120:
                if current_vix > 30:
                    action, icon = "💎 恐慌鑽石買", "🔥🔥🔥"
                    reason = "半年線+VIX爆表"
                else:
                    action, icon = "🔥 重擊加碼", "🟢🟢"
                    reason = "嚴重超跌"
            elif price < ma60:
                action, icon = "✨ 試單加碼", "🟢"
                reason = "季線價值浮現"
            elif adx < 20:
                action, icon = "⚠️ 盤整忍耐", "🧘"
                reason = "無趨勢避開耗損"

            return f"\n\n📊 【{title_icon} {ticker}】\n現價: {price:.2f} (乖離 {bias:.1f}%)\nADX: {adx:.1f}\n💡 {icon} {action}\n📝 {reason}"

    except Exception as e:
        return f"\n⚠️ {ticker} 錯誤: {e}"

# === 主程式入口 ===
if __name__ == "__main__":
    # 讀取參數: pre_open / tw / us
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    print(f"🚀 啟動模式: {mode}")

    # 1. 盤前戰報 (08:00)
    if mode == "pre_open":
        data = get_overnight_data()
        report = analyze_pre_open(data)
        send_push(report)

    # 2. 盤中策略 (12:30 / 13:20)
    else:
        if mode == "us":
            tickers = US_TICKERS
            title = "🇺🇸 美股早安戰報"
        elif mode == "tw":
            tickers = TW_TICKERS
            title = "🇹🇼 台股尾盤戰報"
        else:
            tickers = TW_TICKERS + US_TICKERS
            title = "⚡ 全球投資戰報"

        vix = get_vix()
        report = f"{title} {datetime.now().strftime('%Y-%m-%d')}\n🌎 VIX: {vix:.2f}"
        
        for t in tickers:
            report += analyze_strategy(t, vix)
        
        send_push(report)
