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

def analyze_strategy(ticker, current_vix):
    try:
        # 1. 抓取數據 (取200天以計算半年線)
        df = yf.Ticker(ticker).history(period="200d")
        if len(df) < 120: return ""

        price = df['Close'].iloc[-1]
        open_price = df['Open'].iloc[-1]
        
        # 判斷是否為美股
        is_us = ticker in US_TICKERS
        title_icon = "🇺🇸" if is_us else "🇹🇼"

        # === 策略分流 ===

        # 【策略 A：0050 存股 (買綠不買紅 + KD)】
        if ticker == '0050.TW':
            stoch = df.ta.stoch(k=9, d=3, smooth_k=3)
            k_val = stoch['STOCHk_9_3_3'].iloc[-1]
            is_green = price < open_price # 台股綠是跌
            
            action = "觀望 / 續抱"
            icon = "👀"
            reason = "收紅暫不追高"

            if current_vix > 30:
                action = "💎 恐慌貪婪買"
                icon = "🔥🔥"
                reason = f"VIX飆高 {current_vix:.1f}，絕佳買點"
            elif k_val < 20:
                action = "💰 KD超賣買進"
                icon = "📉"
                reason = f"KD={k_val:.1f} 低檔鈍化"
            elif is_green:
                action = "✅ 定期買進 (收綠)"
                icon = "🌱"
                reason = "買綠不買紅，累積股數"

            return (
                f"\n\n📊 【{title_icon} {ticker} 存股】"
                f"\n現價: {price:.2f} ({(price-open_price):.2f})"
                f"\nKD: {k_val:.1f} / VIX: {current_vix:.1f}"
                f"\n💡 建議: {icon} {action}"
                f"\n📝 理由: {reason}"
            )

        # 【策略 B：槓桿/科技股 (趨勢 + 網格 + ADX)】
        else:
            ma60 = df['Close'].rolling(60).mean().iloc[-1]
            ma120 = df['Close'].rolling(120).mean().iloc[-1]
            bias = ((price - ma60) / ma60) * 100
            
            adx_df = df.ta.adx(length=14)
            adx = adx_df['ADX_14'].iloc[-1] if adx_df is not None and not adx_df.empty else 0

            action = "信仰續抱 (Hold)"
            icon = "💎"
            reason = f"趨勢行進 (ADX={adx:.1f})"

            # 停利門檻 (美股波動大，放寬至30%)
            profit_gate_high = 30 if is_us else 25
            profit_gate_mid = 25 if is_us else 20
            profit_gate_low = 20 if is_us else 15

            # 1. 網格停利
            if bias > profit_gate_high:
                action = f"🚀 網格停利 3 (Sell 10%)"
                icon = "💰💰"
                reason = f"乖離過熱 > {profit_gate_high}% ({bias:.1f}%)"
            elif bias > profit_gate_mid:
                action = f"🚀 網格停利 2 (Sell 10%)"
                icon = "💰"
                reason = f"乖離擴大 > {profit_gate_mid}%"
            elif bias > profit_gate_low and current_vix < 13:
                action = "⚠️ 安逸警示 (Sell 5%)"
                icon = "🟠"
                reason = "市場過度樂觀且乖離偏大"

            # 2. 買進邏輯
            elif price < ma120:
                if current_vix > 30:
                    action = "💎 恐慌鑽石買 (All In)"
                    icon = "🔥🔥🔥"
                    reason = "跌破半年線 + VIX爆表"
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
                reason = f"無趨勢 (ADX={adx:.1f})，避開耗損"

            return (
                f"\n\n📊 【{title_icon} {ticker} 趨勢】"
                f"\n現價: {price:.2f} (乖離 {bias:.1f}%)"
                f"\nADX: {adx:.1f} / VIX: {current_vix:.1f}"
                f"\n💡 建議: {icon} {action}"
                f"\n📝 理由: {reason}"
            )

    except Exception as e:
        return f"\n⚠️ {ticker} 錯誤: {e}"

if __name__ == "__main__":
    # 讀取外部參數決定跑哪種模式 (us / tw / all)
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    print(f"🚀 啟動策略掃描: {mode} 模式")

    if mode == "us":
        target_tickers = US_TICKERS
        title = "🇺🇸 美股早安戰報"
    elif mode == "tw":
        target_tickers = TW_TICKERS
        title = "🇹🇼 台股尾盤戰報"
    else:
        target_tickers = TW_TICKERS + US_TICKERS
        title = "⚡ 全球投資戰報"

    vix = get_vix()
    report = f"{title} {datetime.now().strftime('%Y-%m-%d')}\n🌎 VIX恐慌指數: {vix:.2f}"
    
    for t in target_tickers:
        report += analyze_strategy(t, vix)
    
    send_push(report)
