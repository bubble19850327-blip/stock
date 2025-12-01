import os
import requests
import yfinance as yf
import pandas_ta as ta
from datetime import datetime

# === 設定區 ===
CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
USER_ID = os.environ.get('LINE_USER_ID')
# 新增 0050 至監控清單
TICKERS = ['00631L.TW', '00675L.TW', '0050.TW']

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
        print(f"✅ LINE 通知已發送")
    except Exception as e:
        print(f"❌ 發送失敗: {e}")

def analyze_strategy(ticker):
    try:
        # 1. 抓取數據 (取 150 天)
        df = yf.Ticker(ticker).history(period="150d")
        if len(df) < 120: return f"\n⚠️ {ticker} 數據不足"

        price = df['Close'].iloc[-1]
        open_price = df['Open'].iloc[-1]
        
        # === 策略分流 ===
        
        # 【策略 A：0050 長期存股 (買綠不買紅 + KD)】
        if ticker == '0050.TW':
            # 計算 KD 指標 (參數 9,3,3)
            stoch = df.ta.stoch(k=9, d=3, smooth_k=3)
            # pandas_ta 欄位名稱可能為 STOCHk_9_3_3, STOCHd_9_3_3
            k_val = stoch['STOCHk_9_3_3'].iloc[-1]
            
            # 判斷收黑 (綠棒：收盤 < 開盤)
            is_green = price < open_price
            
            # 邏輯判斷
            action = "觀望 / 續抱"
            icon = "👀"
            reason = "今日收紅，暫不追高"
            
            if k_val < 20:
                action = "💎 強力買進 (KD低檔)"
                icon = "🔥"
                reason = f"KD值 {k_val:.1f} < 20，超賣區撿便宜"
            elif is_green:
                action = "✅ 定期買進 (收綠)"
                icon = "🌱"
                reason = "遵循買綠不買紅原則，累積股數"
                
            return (
                f"\n\n📊 【{ticker} 存股戰報】"
                f"\n現價: {price:.2f} ({(price-open_price):.2f})"
                f"\nKD值: {k_val:.1f}"
                f"\n狀態: {'🟩 收綠 (跌)' if is_green else '🟥 收紅 (漲)'}"
                f"\n------------------"
                f"\n💡 建議: {icon} {action}"
                f"\n📝 理由: {reason}"
            )

        # 【策略 B：槓桿 ETF 長期持有 (再平衡 + ADX)】
        else:
            ma60 = df['Close'].rolling(60).mean().iloc[-1]
            ma120 = df['Close'].rolling(120).mean().iloc[-1]
            bias = ((price - ma60) / ma60) * 100
            
            adx_df = df.ta.adx(length=14)
            adx = adx_df['ADX_14'].iloc[-1] if adx_df is not None and not adx_df.empty else 0

            action = "信仰續抱 (Hold)"
            icon = "💎"
            reason = f"趨勢行進中 (ADX={adx:.1f})"

            if bias > 25:
                action = "🚀 網格停利 3 (Sell 10%)"
                icon = "💰💰"
                reason = f"乖離過熱 > 25% ({bias:.1f}%)"
            elif bias > 20:
                action = "🚀 網格停利 2 (Sell 10%)"
                icon = "💰"
                reason = f"乖離擴大 > 20% ({bias:.1f}%)"
            elif price < ma120:
                action = "🔥 重擊加碼 (Buy 20%)"
                icon = "🟢🟢"
                reason = "跌破半年線，嚴重超跌"
            elif price < ma60:
                action = "✨ 試單加碼 (Buy 10%)"
                icon = "🟢"
                reason = "跌破季線，價值浮現"
            elif adx < 20:
                action = "⚠️ 盤整忍耐"
                icon = "🧘"
                reason = f"無趨勢 (ADX={adx:.1f})，耐心度過耗損"

            return (
                f"\n\n📊 【{ticker} 槓桿戰報】"
                f"\n現價: {price:.2f} / 乖離: {bias:.1f}%"
                f"\nADX強度: {adx:.1f}"
                f"\n------------------"
                f"\n💡 建議: {icon} {action}"
                f"\n📝 理由: {reason}"
            )

    except Exception as e:
        return f"\n⚠️ {ticker} 分析錯誤: {e}"

if __name__ == "__main__":
    print("🚀 執行全方位策略掃描...")
    report = f"⚡ {datetime.now().strftime('%Y-%m-%d')} 尾盤戰報 (13:20)"
    for t in TICKERS:
        report += analyze_strategy(t)
    send_push(report)
