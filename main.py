import sys
import yfinance as yf
from datetime import datetime
from config import TW_TZ, US_TICKERS, TW_TICKERS, US_MEMORY, TW_MEMORY
from fetcher import send_push, get_vix, get_tx_night, get_trendforce_spot_price, get_contract_news
from strategy import analyze_pre_open, analyze_general_stock, analyze_memory_stock

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "tw_close"
    tw_now = datetime.now(TW_TZ)
    timestamp = tw_now.strftime('%m-%d %H:%M')
    print(f"🚀 啟動模式: {mode} ({timestamp})")

    # 1. 08:00 盤前模式 (美股結算 + 盤後 + 夜盤)
    if mode == "pre_market":
        tickers = ['TSM', '^SOX', '^IXIC', '^DJI', '^GSPC', '^VIX']
        data = yf.download(tickers, period='5d', progress=False)['Close']
        changes = data.pct_change().iloc[-1] * 100
        last_close = data.iloc[-1]
        
        tx_night_price, tx_night_pct = get_tx_night()
        info = {
            'tsm_pct': changes['TSM'], 'vix': last_close['^VIX'],
            'dji_price': last_close['^DJI'], 'dji_pct': changes['^DJI'],
            'spx_price': last_close['^GSPC'], 'spx_pct': changes['^GSPC'],
            'ndx_price': last_close['^IXIC'], 'ndx_pct': changes['^IXIC'],
            'sox_price': last_close['^SOX'], 'sox_pct': changes['^SOX'],
            'tx_night_price': tx_night_price, 'tx_night_pct': tx_night_pct
        }
        report = f"📅 {tw_now.strftime('%Y-%m-%d %H:%M')}\n" + analyze_pre_open(info)
        send_push(report)

    # 2. 13:20 台股尾盤模式 (大盤、槓桿、台股個股)
    elif mode == "tw_close":
        vix = get_vix()
        report = f"⚡ 投資戰報 {timestamp}\n🌎 VIX: {vix:.2f}"
        for t in TW_TICKERS: 
            report += analyze_general_stock(t, vix)
        send_push(report)

    # 3. 21:00 美股與記憶體戰報 (美股、美記憶體、台記憶體基本面)
    elif mode == "us_pre_market":
        vix = get_vix()
        global_spot = get_trendforce_spot_price()
        global_sentiment = get_contract_news()
        
        report = f"⚡ 記憶體與美股戰報 \n {timestamp}\n━━━━━━━━━━━━━\n"
        # 分析美股主要科技與記憶體
        for t in US_TICKERS + US_MEMORY:
            report += analyze_general_stock(t, vix)
            
        report += "\n-- 台股記憶體指標 --\n"
        # 分析台股記憶體與現貨報價
        for t, n in TW_MEMORY:
            report += analyze_memory_stock(t, n, global_spot, global_sentiment) + "\n"
            
        send_push(report.strip())
