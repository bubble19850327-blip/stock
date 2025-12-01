import os
import requests
import yfinance as yf
import pandas_ta as ta
from datetime import datetime

# === 設定區 ===
CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
USER_ID = os.environ.get('LINE_USER_ID')
TICKERS = ['00631L.TW', '00675L.TW', '0050.TW']

def send_push(msg):
    """發送 LINE 推播"""
    if not CHANNEL_TOKEN or not USER_ID:
        print("❌ 錯誤：未讀取到 Token 或 User ID")
        return
    headers = {
        "Authorization": f"Bearer {CHANNEL_TOKEN}",
        "Content-Type": "application/json"
    }
    body = {"to": USER_ID, "messages": [{"type": "text", "text": msg}]}
    try:
        requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=body)
        print("✅ LINE 通知已發送")
    except Exception as e:
        print(f"❌ 發送失敗: {e}")

def get_vix():
    """抓取美股恐慌指數 VIX"""
    try:
        vix = yf.Ticker("^VIX").history(period="5d")
        return vix['Close'].iloc[-1]
    except:
        return 0

def analyze_strategy(ticker, current_vix):
    try:
        # 1. 抓取數據
        df = yf.Ticker(ticker).history(period="150d")
        if len(df) < 120: return f"\n⚠️ {ticker} 數據不足"

        price = df['Close'].iloc[-1]
        open_price = df['Open'].iloc[-1]

        # === 策略分流 ===

        # 【策略 A：0050 存股 (買綠不買紅 + KD + VIX輔助)】
        if ticker == '0050.TW':
            stoch = df.ta.stoch(k=9, d=3, smooth_k=3)
            k_val = stoch['STOCHk_9_3_3'].iloc[-1]
            is_green = price < open_price
            
            action = "觀望 / 續抱"
            icon = "👀"
            reason = "收紅暫不動作"

            # VIX > 30 代表市場大跌，0050 閉眼買
            if current_vix > 30:
                action = "💎 恐慌貪婪買 (VIX爆表)"
                icon = "🔥🔥"
                reason = f"VIX達 {current_vix:.1f} 市場極度恐慌，長線絕佳買點"
            elif k_val < 20:
                action = "💰 KD超賣買進"
                icon = "📉"
                reason = f"KD={k_val:.1f} 進入低檔區"
            elif is_green:
                action = "✅ 定期買進 (收綠)"
                icon = "🌱"
                reason = "買綠不買紅，累積股數"

            return (
                f"\n\n📊 【{ticker} 存股戰報】"
                f"\n現價: {price:.2f} ({(price-open_price):.2f})"
                f"\nKD: {k_val:.1f} / VIX: {current_vix:.1f}"
                f"\n------------------"
                f"\n💡 建議: {icon} {action}"
                f"\n📝 理由: {reason}"
            )

        # 【策略 B：槓桿 ETF (再平衡 + ADX + VIX)】
        else:
            ma60 = df['Close'].rolling(60).mean().iloc[-1]
            ma120 = df['Close'].rolling(120).mean().iloc[-1]
            bias = ((price - ma60) / ma60) * 100
            
            adx_df = df.ta.adx(length=14)
            adx = adx_df['ADX_14'].iloc[-1] if adx_df is not None and not adx_df.empty else 0

            action = "信仰續抱 (Hold)"
            icon = "💎"
            reason = f"趨勢行進中 (ADX={adx:.1f})"

            # --- 優先級判斷 ---
            
            # 1. 停利 (VIX太低代表市場安逸，停利要更果斷)
            if bias > 25:
                action = "🚀 網格停利 3 (Sell 10%)"
                icon = "💰💰"
                reason = f"乖離過熱 > 25% ({bias:.1f}%)"
            elif bias > 20:
                action = "🚀 網格停利 2 (Sell 10%)"
                icon = "💰"
                reason = f"乖離擴大 > 20%"
            elif bias > 15 and current_vix < 13: # 市場太安逸時，乖離15%就先跑一點
                action = "⚠️ 安逸警示 (Sell 5%)"
                icon = "🟠"
                reason = f"VIX偏低({current_vix:.1f})且乖離>15%，居高思危"

            # 2. 買進 (配合 VIX 恐慌指數)
            elif price < ma120:
                if current_vix > 30:
                    action = "💎 恐慌鑽石買 (All In)"
                    icon = "🔥🔥🔥"
                    reason = f"跌破半年線 + VIX飆高({current_vix:.1f})，歷史級買點"
                else:
                    action = "🔥 重擊加碼 (Buy 20%)"
                    icon = "🟢🟢"
                    reason = "跌破半年線，嚴重超跌"
            elif price < ma60:
                action = "✨ 試單加碼 (Buy 10%)"
                icon = "🟢"
                reason = "跌破季線，價值浮現"
            
            # 3. 盤整濾網
            elif adx < 20:
                action = "⚠️ 盤整忍耐"
                icon = "🧘"
                reason = f"無趨勢 (ADX={adx:.1f})，耐心避開耗損"

            return (
                f"\n\n📊 【{ticker} 槓桿戰報】"
                f"\n現價: {price:.2f} / 乖離: {bias:.1f}%"
                f"\nADX: {adx:.1f} / VIX: {current_vix:.1f}"
                f"\n------------------"
                f"\n💡 建議: {icon} {action}"
                f"\n📝 理由: {reason}"
            )

    except Exception as e:
        return f"\n⚠️ {ticker} 分析錯誤: {e}"

if __name__ == "__main__":
    print("🚀 執行策略掃描 (含VIX恐慌指數)...")
    
    # 先抓一次 VIX，傳入所有策略共用
    vix_val = get_vix()
    print(f"目前美股恐慌指數: {vix_val:.2f}")

    report = f"⚡ {datetime.now().strftime('%Y-%m-%d')} 尾盤戰報 (13:20)"
    report += f"\n🌎 VIX恐慌指數: {vix_val:.2f}"
    
    for t in TICKERS:
        report += analyze_strategy(t, vix_val)
    
    send_push(report)
