import os
import requests
import yfinance as yf
from datetime import datetime

# 1. 讀取 GitHub Secrets (必須與 Repo 設定一致)
CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
USER_ID = os.environ.get('LINE_USER_ID')
TICKERS = ['00631L.TW', '00675L.TW']

def send_push(msg):
    """透過 LINE Messaging API 發送推播訊息"""
    if not CHANNEL_TOKEN or not USER_ID:
        print("❌ 錯誤：未讀取到 Token 或 User ID")
        return

    headers = {
        "Authorization": f"Bearer {CHANNEL_TOKEN}",
        "Content-Type": "application/json"
    }
    body = {
        "to": USER_ID,
        "messages": [{"type": "text", "text": msg}]
    }
    
    # 呼叫 LINE Push API
    try:
        r = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=body)
        r.raise_for_status()
        print("✅ LINE 通知已發送")
    except Exception as e:
        print(f"❌ 發送失敗: {e}")

def analyze_strategy(ticker):
    """分析個股策略邏輯"""
    try:
        # 抓取 1 年數據以計算半年線
        df = yf.Ticker(ticker).history(period="1y")
        if len(df) < 120: return f"\n⚠️ {ticker} 數據不足 (需 > 120 天)"

        price = df['Close'].iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]   # 月線 (防守)
        ma60 = df['Close'].rolling(60).mean().iloc[-1]   # 季線 (買點1)
        ma120 = df['Close'].rolling(120).mean().iloc[-1] # 半年線 (買點2)
        bias = ((price - ma60) / ma60) * 100             # 季線乖離率

        # 初始化訊號
        action = "觀望 / 續抱 (Hold)"
        icon = "👀"
        reason = "未觸發特定訊號"

        # === 核心策略邏輯 (優先順序：大跌買進 > 跌破防守 > 過熱停利) ===
        if price < ma120:
            action = "🔥 重擊加碼 (Buy 20%)"
            icon = "🟢🟢"
            reason = f"跌破半年線 {ma120:.1f}，進入超跌區"
        elif price < ma60:
            action = "✨ 試單加碼 (Buy 10%)"
            icon = "🟢"
            reason = f"跌破季線 {ma60:.1f}，進入價值區"
        elif price < ma20:
            action = "🛡️ 獲利了結 (Sell 1/3)"
            icon = "🔴"
            reason = f"跌破月線 {ma20:.1f}，短線轉弱"
        elif bias > 25:
            action = "🚀 網格停利 3 (Sell 10%)"
            icon = "💰💰"
            reason = f"乖離過熱 > 25% (目前 {bias:.1f}%)"
        elif bias > 20:
            action = "🚀 網格停利 2 (Sell 10%)"
            icon = "💰"
            reason = f"乖離擴大 > 20% (目前 {bias:.1f}%)"
        elif bias > 15:
            action = "🚀 網格停利 1 (Sell 10%)"
            icon = "🟠"
            reason = f"乖離起漲 > 15% (目前 {bias:.1f}%)"

        return (
            f"\n\n📊 【{ticker} 策略報告】"
            f"\n現價: {price:.2f}"
            f"\n乖離: {bias:.2f}%"
            f"\n均線: 月 {ma20:.0f} / 季 {ma60:.0f} / 半 {ma120:.0f}"
            f"\n------------------"
            f"\n💡 建議: {icon} {action}"
            f"\n📝 理由: {reason}"
        )
    except Exception as e:
        return f"\n⚠️ {ticker} 分析錯誤: {e}"

# === 主程式執行區 ===
if __name__ == "__main__":
    print("🚀 開始執行策略分析...")
    full_report = f"📅 {datetime.now().strftime('%Y-%m-%d')} 投資雷達"
    
    for t in TICKERS:
        full_report += analyze_strategy(t)
    
    # 發送結果
    send_push(full_report)

