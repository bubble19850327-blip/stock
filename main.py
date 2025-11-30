import os
import yfinance as yf
import requests
from datetime import datetime

# 從 GitHub Secrets 讀取 Token
LINE_TOKEN = os.environ.get("LINE_TOKEN")
tickers = ['00631L.TW', '00675L.TW']

def send_push(msg):
    headers = {"Authorization": f"Bearer {os.environ['LINE_TOKEN']}", "Content-Type": "application/json"}
    requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json={
        "to": os.environ['LINE_USER_ID'], "messages": [{"type": "text", "text": msg}]
    })

def send_line_notify(token, msg):
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    requests.post("https://notify-api.line.me/api/notify", headers=headers, data={'message': msg})

def analyze_strategy(ticker):
    # 抓取足夠資料以計算半年線 (120MA)
    df = yf.Ticker(ticker).history(period="1y")
    
    if len(df) < 120: return f"\n⚠️ {ticker} 數據不足"

    price = df['Close'].iloc[-1]
    ma20 = df['Close'].rolling(20).mean().iloc[-1]   # 月線 (防守線)
    ma60 = df['Close'].rolling(60).mean().iloc[-1]   # 季線 (價值線)
    ma120 = df['Close'].rolling(120).mean().iloc[-1] # 半年線 (重壓線)
    bias = ((price - ma60) / ma60) * 100             # 季線乖離率

    action, icon, reason = "觀望 / 續抱", "👀", "無觸發訊號"

    # === 策略邏輯核心 (優先順序：買進 > 停損 > 網格停利) ===
    if price < ma120:
        action, icon = "大舉加碼 (Buy 20%)", "🟢🟢"
        reason = "跌破半年線，進入超跌區 (金字塔底部)"
    elif price < ma60:
        action, icon = "試單加碼 (Buy 10%)", "🟢"
        reason = "跌破季線，進入價值區 (金字塔中部)"
    elif price < ma20:
        action, icon = "趨勢轉弱 (Sell 1/3)", "🛡️"
        reason = "跌破月線，獲利防守"
    elif bias > 25:
        action, icon = "網格停利 3 (Sell 10%)", "🔴🔴"
        reason = f"乖離過熱 > 25% ({bias:.1f}%)"
    elif bias > 20:
        action, icon = "網格停利 2 (Sell 10%)", "🔴"
        reason = f"乖離擴大 > 20% ({bias:.1f}%)"
    elif bias > 15:
        action, icon = "網格停利 1 (Sell 10%)", "🟠"
        reason = f"乖離起漲 > 15% ({bias:.1f}%)"

    return (
        f"\n\n📊 【{ticker} 策略日報】"
        f"\n現價: {price:.2f} / 乖離: {bias:.1f}%"
        f"\n關鍵均線: 月{ma20:.0f} / 季{ma60:.0f} / 半{ma120:.0f}"
        f"\n💡 建議: {icon} {action}"
        f"\n📝 理由: {reason}"
    )

if LINE_TOKEN:
    report = f"\n📅 {datetime.now().strftime('%Y-%m-%d')} 投資雷達"
    for t in tickers:
        try: report += analyze_strategy(t)
        except Exception as e: report += f"\n⚠️ {t} 錯誤: {e}"
    send_line_notify(LINE_TOKEN, report)
else:
    print("❌ 請設定 LINE_TOKEN 環境變數")