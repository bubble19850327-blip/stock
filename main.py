import os
import sys
import requests
import yfinance as yf
import pandas_ta as ta
import pandas as pd
from datetime import datetime

# === 設定區 ===
CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
USER_ID = os.environ.get('LINE_USER_ID')

TW_TICKERS = ['00631L.TW', '00675L.TW', '0050.TW']
# 美股七巨頭 + 台積電ADR (台股領先指標)
US_TICKERS = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'TSM']

def send_push(msg):
    """發送 LINE 推播"""
    if not CHANNEL_TOKEN or not USER_ID: return
    headers = {"Authorization": f"Bearer {CHANNEL_TOKEN}", "Content-Type": "application/json"}
    body = {"to": USER_ID, "messages": [{"type": "text", "text": msg}]}
    try: requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=body)
    except: pass

def get_market_sentiment():
    """計算美股七巨頭昨晚平均漲跌幅 & VIX"""
    try:
        # 1. 抓取 VIX
        vix = yf.Ticker("^VIX").history(period="5d")['Close'].iloc[-1]
        
        # 2. 計算美股巨頭平均漲跌 (US Trend)
        us_data = yf.download(US_TICKERS, period="5d", progress=False)['Close']
        pct_change = us_data.pct_change().iloc[-1] # 取最新一天漲跌幅
        avg_change = pct_change.mean() * 100 # 轉為百分比
        
        return vix, avg_change
    except Exception as e:
        print(f"數據抓取失敗: {e}")
        return 0, 0

def analyze_tw_strategy(ticker, vix, us_trend):
    """台股策略：納入美股趨勢因子"""
    try:
        df = yf.Ticker(ticker).history(period="150d")
        if len(df) < 120: return ""
        
        price = df['Close'].iloc[-1]
        open_price = df['Open'].iloc[-1]
        ma60 = df['Close'].rolling(60).mean().iloc[-1]
        ma120 = df['Close'].rolling(120).mean().iloc[-1]
        bias = ((price - ma60) / ma60) * 100
        
        adx_df = df.ta.adx(length=14)
        adx = adx_df['ADX_14'].iloc[-1] if adx_df is not None and not adx_df.empty else 0

        # === 策略核心 ===
        action = "信仰續抱"
        icon = "💎"
        reason = f"趨勢穩健 (ADX={adx:.1f})"
        
        # 判斷美股影響力
        us_msg = ""
        if us_trend > 1.5: us_msg = " (🇺🇸美股大漲助攻)"
        elif us_trend < -1.5: us_msg = " (🇺🇸美股大跌拖累)"

        # 【A. 0050 存股邏輯 (越跌越買)】
        if ticker == '0050.TW':
            stoch = df.ta.stoch(k=9, d=3, smooth_k=3)
            k_val = stoch['STOCHk_9_3_3'].iloc[-1]
            is_green = price < open_price

            if vix > 30 or (us_trend < -2 and price < ma60):
                action = "💎 恐慌貪婪買"
                icon = "🔥🔥"
                reason = f"美股重挫/VIX高，0050撿便宜良機{us_msg}"
            elif k_val < 20:
                action = "💰 KD超賣買進"
                icon = "📉"
                reason = "KD低檔鈍化"
            elif is_green:
                action = "✅ 定期買進"
                icon = "🌱"
                reason = "逢綠買進累積部位"

        # 【B. 槓桿 ETF (00631L/00675L) 風控邏輯】
        else:
            # 1. 停利 (若美股大漲導致乖離過大，加速停利)
            if bias > 25:
                action = "🚀 網格停利 3 (Sell 10%)"
                icon = "💰💰"
                reason = f"乖離過熱{us_msg}，落袋為安"
            elif bias > 15 and us_trend > 1: # 美股大漲助推，容易開高走低
                action = "⚠️ 趁勢調節 (Sell 5%)"
                icon = "🟠"
                reason = f"乖離偏大且美股大漲{us_msg}，慎防回檔"

            # 2. 買進 (若美股大跌，需更嚴格的買點)
            elif price < ma120:
                if vix > 30:
                    action = "💎 恐慌鑽石買"
                    icon = "🔥🔥🔥"
                    reason = f"跌破半年線+恐慌極致{us_msg}"
                elif us_trend < -1.5:
                    action = "✋ 暫停接刀 (觀察)"
                    icon = "🛑"
                    reason = f"跌破半年線但美股重挫{us_msg}，多看一天"
                else:
                    action = "🔥 重擊加碼"
                    icon = "🟢🟢"
                    reason = "跌破半年線，超跌買進"
            
            # 3. 盤整濾網
            elif adx < 20:
                action = "⚠️ 盤整忍耐"
                icon = "🧘"
                reason = f"無趨勢 (ADX={adx:.1f})，避開耗損"

        return (
            f"\n\n📊 【{ticker}】"
            f"\n現價: {price:.2f} (乖離 {bias:.1f}%)"
            f"\nADX: {adx:.1f} / 🇺🇸動能: {us_trend:+.1f}%"
            f"\n💡 建議: {icon} {action}"
            f"\n📝 理由: {reason}"
        )

    except Exception as e:
        return f"\n⚠️ {ticker} 錯誤: {e}"

if __name__ == "__main__":
    # 僅處理台股模式 (此策略針對台股收盤前)
    mode = sys.argv[1] if len(sys.argv) > 1 else "tw"
    
    if mode == "tw" or mode == "all":
        print("🚀 執行台股策略掃描 (含美股連動)...")
        vix, us_trend = get_market_sentiment()
        
        report = f"🇹🇼 台股尾盤戰報 {datetime.now().strftime('%Y-%m-%d')}"
        report += f"\n🌎 VIX: {vix:.1f} / 🇺🇸昨夜勢頭: {us_trend:+.2f}%"
        
        for t in TW_TICKERS:
            report += analyze_tw_strategy(t, vix, us_trend)
        
        send_push(report)
