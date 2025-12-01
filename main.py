import os
import requests
import yfinance as yf
import pandas_ta as ta
from datetime import datetime

# === 設定區 ===
# 從 GitHub Secrets 讀取 Token
CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
USER_ID = os.environ.get('LINE_USER_ID')
TICKERS = ['00631L.TW', '00675L.TW']

def send_push(msg):
    """發送 LINE Push Message"""
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
    try:
        r = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=body)
        r.raise_for_status()
        print("✅ LINE 通知已發送")
    except Exception as e:
        print(f"❌ 發送失敗: {e}")

def analyze_strategy(ticker):
    """分析個股策略：ADX濾網 + 金字塔買進 + 網格停利"""
    try:
        # 1. 抓取數據 (取 150 天以確保 ADX 計算穩定)
        df = yf.Ticker(ticker).history(period="150d")
        if len(df) < 120: return f"\n⚠️ {ticker} 數據不足"

        # 2. 計算基礎指標
        price = df['Close'].iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]   # 月線 (防守)
        ma60 = df['Close'].rolling(60).mean().iloc[-1]   # 季線 (價值)
        ma120 = df['Close'].rolling(120).mean().iloc[-1] # 半年線 (重壓)
        bias = ((price - ma60) / ma60) * 100             # 季線乖離率

        # 3. 計算 ADX 趨勢指標 (長度 14)
        # ADX < 20 代表盤整(耗損風險高); ADX > 25 代表有趨勢
        adx_df = df.ta.adx(length=14)
        if adx_df is None or adx_df.empty:
            adx = 0
        else:
            adx = adx_df['ADX_14'].iloc[-1]

        # 4. 策略邏輯判斷 (優先級：賣出保本 > 大跌抄底 > 盤整警告)
        action = "觀望 / 續抱 (Hold)"
        icon = "👀"
        reason = f"趨勢延續 (ADX={adx:.1f})"

        # --- A. 賣出訊號 (停利/停損) ---
        if price < ma20:
            action = "🛡️ 獲利防守 (Sell 1/3)"
            icon = "🔴"
            reason = "跌破月線，短線轉弱"
        elif bias > 25:
            action = "🚀 網格停利 3 (Sell 10%)"
            icon = "💰💰"
            reason = f"乖離過熱 > 25% ({bias:.1f}%)"
        elif bias > 20:
            action = "🚀 網格停利 2 (Sell 10%)"
            icon = "💰"
            reason = f"乖離擴大 > 20% ({bias:.1f}%)"
        elif bias > 15:
            action = "🚀 網格停利 1 (Sell 10%)"
            icon = "🟠"
            reason = f"乖離起漲 > 15% ({bias:.1f}%)"

        # --- B. 買進訊號 (金字塔加碼) ---
        # 只有在沒有賣出訊號時，才檢查買進
        elif price < ma120:
            action = "🔥 重擊加碼 (Buy 20%)"
            icon = "🟢🟢"
            reason = "跌破半年線，超跌進場"
        elif price < ma60:
            action = "✨ 試單加碼 (Buy 10%)"
            icon = "🟢"
            reason = "跌破季線，價值進場"
            
        # --- C. 盤整濾網 (若無買賣訊號，檢查是否盤整) ---
        elif adx < 20:
            action = "⚠️ 盤整預警 (避開耗損)"
            icon = "🌫️"
            reason = f"ADX僅 {adx:.1f} 無趨勢，槓桿ETF易內扣耗損"

        return (
            f"\n\n📊 【{ticker} 策略報告】"
            f"\n現價: {price:.2f} / 乖離: {bias:.1f}%"
            f"\n趨勢強度 (ADX): {adx:.1f}"
            f"\n關鍵均線: 季{ma60:.0f} / 半{ma120:.0f}"
            f"\n------------------"
            f"\n💡 建議: {icon} {action}"
            f"\n📝 理由: {reason}"
        )

    except Exception as e:
        return f"\n⚠️ {ticker} 分析錯誤: {e}"

# === 主程式執行 ===
if __name__ == "__main__":
    print("🚀 開始執行 ADX 策略分析...")
    report = f"📅 {datetime.now().strftime('%Y-%m-%d')} 投資雷達"
    
    for t in TICKERS:
        report += analyze_strategy(t)
    
    send_push(report)
