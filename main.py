import os
import requests
import yfinance as yf
import pandas_ta as ta
from datetime import datetime

# === 設定區 ===
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
    try:
        r = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=body)
        r.raise_for_status()
        print("✅ LINE 通知已發送")
    except Exception as e:
        print(f"❌ 發送失敗: {e}")

def analyze_strategy(ticker):
    """
    長期持有策略：
    1. 不停損：移除跌破月線賣出的邏輯。
    2. 再平衡賣出：乖離過大時分批賣出，將資金轉回現金/0050。
    3. 再平衡買進：跌破季線/半年線時動用現金買進。
    4. ADX濾網：僅作為盤整提醒，不強制出場。
    """
    try:
        # 1. 抓取數據
        df = yf.Ticker(ticker).history(period="150d")
        if len(df) < 120: return f"\n⚠️ {ticker} 數據不足"

        # 2. 計算指標
        price = df['Close'].iloc[-1]
        ma60 = df['Close'].rolling(60).mean().iloc[-1]   # 季線 (買點1)
        ma120 = df['Close'].rolling(120).mean().iloc[-1] # 半年線 (買點2)
        bias = ((price - ma60) / ma60) * 100             # 季線乖離率

        # ADX 趨勢強度
        adx_df = df.ta.adx(length=14)
        adx = adx_df['ADX_14'].iloc[-1] if adx_df is not None and not adx_df.empty else 0

        # 3. 策略邏輯 (優先檢查停利，再來檢查加碼)
        action = "信仰續抱 (Hold)"
        icon = "💎" # 鑽石手，代表長期持有
        reason = f"趨勢行進中 (ADX={adx:.1f})"

        # --- A. 網格停利 (再平衡賣出：轉為現金) ---
        if bias > 25:
            action = "🚀 網格停利 3 (Sell 10%)"
            icon = "💰💰"
            reason = f"乖離過熱 > 25% ({bias:.1f}%)，獲利入袋"
        elif bias > 20:
            action = "🚀 網格停利 2 (Sell 10%)"
            icon = "💰"
            reason = f"乖離擴大 > 20% ({bias:.1f}%)，調節水位"
        elif bias > 15:
            action = "🚀 網格停利 1 (Sell 10%)"
            icon = "🟠"
            reason = f"乖離起漲 > 15% ({bias:.1f}%)，適度減碼"

        # --- B. 金字塔買進 (再平衡買進：動用現金) ---
        elif price < ma120:
            action = "🔥 重擊加碼 (Buy 20%)"
            icon = "🟢🟢"
            reason = "跌破半年線，嚴重超跌，大膽買進"
        elif price < ma60:
            action = "✨ 試單加碼 (Buy 10%)"
            icon = "🟢"
            reason = "跌破季線，價值浮現，分批承接"
            
        # --- C. 盤整提示 (僅提示，不賣出) ---
        elif adx < 20:
            action = "⚠️ 盤整忍耐 (波動耗損)"
            icon = "🧘" # 靜坐忍耐
            reason = f"ADX僅 {adx:.1f} 無趨勢，耐心度過震盪期"

        return (
            f"\n\n📊 【{ticker} 長期戰報】"
            f"\n現價: {price:.2f} / 乖離: {bias:.1f}%"
            f"\nADX強度: {adx:.1f}"
            f"\n關鍵均線: 季{ma60:.0f} / 半{ma120:.0f}"
            f"\n------------------"
            f"\n💡 建議: {icon} {action}"
            f"\n📝 理由: {reason}"
        )

    except Exception as e:
        return f"\n⚠️ {ticker} 分析錯誤: {e}"

if __name__ == "__main__":
    print("🚀 執行收盤前策略掃描 (長期持有版)...")
    # 標題標示為 13:20 預判
    report = f"⚡ {datetime.now().strftime('%Y-%m-%d')} 尾盤戰報 (13:20)"
    for t in TICKERS:
        report += analyze_strategy(t)
    send_push(report)
