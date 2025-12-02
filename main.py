import os
import sys
import requests
import yfinance as yf
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

def get_overnight_data():
    """抓取美股收盤數據 (TSM, SOX, NDX, VIX)"""
    tickers = ['TSM', '^SOX', '^NDX', '^VIX']
    data = yf.download(tickers, period="5d", progress=False)['Close']
    
    # 計算漲跌幅
    changes = data.pct_change().iloc[-1] * 100
    last_close = data.iloc[-1]
    
    return {
        'tsm': changes['TSM'],
        'sox': changes['^SOX'],
        'ndx': changes['^NDX'],
        'vix': last_close['^VIX']
    }

def analyze_pre_open(data):
    """盤前策略分析"""
    tsm = data['tsm']
    ndx = data['ndx']
    vix = data['vix']
    
    # 預判開盤氣氛
    sentiment = "😐 中性震盪"
    if tsm > 2.5 or ndx > 1.5: sentiment = "🔥 極度樂觀 (由美股帶動)"
    elif tsm < -2.5 or ndx < -1.5: sentiment = "❄️ 極度悲觀 (美股重挫)"
    elif tsm > 1: sentiment = "📈 偏多看待"
    elif tsm < -1: sentiment = "📉 偏空看待"

    # 給出建議
    advice_0050 = "觀望 (Wait)"
    advice_lev = "續抱 (Hold)" # 槓桿ETF建議

    # 1. 0050 建議
    if tsm < -2: 
        advice_0050 = "✅ 掛低買進 (撿便宜)"
    elif vix > 30:
        advice_0050 = "💎 恐慌貪婪買 (All In)"
    
    # 2. 00631L/675L 建議
    if tsm > 3:
        advice_lev = "⚠️ 勿追高 / 考慮調節 (乖離恐過大)"
    elif tsm < -3 and vix < 25:
        advice_lev = "✋ 暫緩加碼 (接刀小心)"
    elif tsm < -3 and vix > 30:
        advice_lev = "💎 鑽石買點 (歷史級機會)"

    return (
        f"🌅 【08:00 盤前戰報】\n"
        f"昨夜美股氣氛: {sentiment}\n"
        f"------------------\n"
        f"🇺🇸 TSM ADR: {tsm:+.2f}%\n"
        f"🇺🇸 納斯達克: {ndx:+.2f}%\n"
        f"🌎 VIX 指數: {vix:.2f}\n"
        f"------------------\n"
        f"💡 0050 策略: {advice_0050}\n"
        f"💡 正二 策略: {advice_lev}\n"
        f"📝 備註: 預判台積電今日開盤約 {(tsm):+.1f}%"
    )

# ... (保留原有的 analyze_strategy 函式) ...

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    if mode == "pre_open":
        print("🚀 執行 08:00 盤前分析...")
        market_data = get_overnight_data()
        report = analyze_pre_open(market_data)
        send_push(report)
        
    # ... (保留原有的 tw/us 模式邏輯) ...
