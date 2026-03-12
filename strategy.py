import yfinance as yf
import pandas_ta as ta
from fetcher import get_settlement_status, get_futures_basis, get_realtime_nav
from config import US_TICKERS

def analyze_pre_open(data):
    tsm, vix = data['tsm_pct'], data['vix']
    sentiment = "😐 中性"
    if tsm > 2.5: sentiment = "🔥 極度樂觀"
    elif tsm < -2.5: sentiment = "❄️ 極度悲觀"
    
    advice_0050 = "觀望"
    if tsm < -2: advice_0050 = "✅ 掛低買進"
    elif vix > 30: advice_0050 = "💎 恐慌貪婪買"
    
    def format_idx(name, price, pct):
        icon = "🔴" if pct < 0 else "🟢" if pct > 0 else "⚪"
        return f"{icon} {name}: {price:.1f} ({pct:+.2f}%)"
    
    return (
        f"🌅 08:00 盤前戰報\n"
        f"氣氛: {sentiment}\n"
        f"TSM: {tsm:+.2f}%\n"
        f"VIX: {vix:.1f}\n"
        f"--- 夜盤與美股 ---\n"
        f"{format_idx('台指夜', data['tx_night_price'], data['tx_night_pct'])}\n"
        f"{format_idx('道瓊', data['dji_price'], data['dji_pct'])}\n"
        f"{format_idx('標普', data['spx_price'], data['spx_pct'])}\n"
        f"{format_idx('那指', data['ndx_price'], data['ndx_pct'])}\n"
        f"{format_idx('費半', data['sox_price'], data['sox_pct'])}\n"
        f"------------------\n"
        f"💡 0050: {advice_0050}"
    )

def analyze_general_stock(ticker, current_vix):
    try:
        df = yf.Ticker(ticker).history(period='200d')
        if len(df) < 120: return ""
        price = df['Close'].iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        ma20_prev = df['Close'].rolling(20).mean().iloc[-2]
        ma60 = df['Close'].rolling(60).mean().iloc[-1]
        ma120 = df['Close'].rolling(120).mean().iloc[-1]
        bias = ((price - ma60) / ma60) * 100
        
        adx_data = df.ta.adx(length=14)
        adx = adx_data['ADX_14'].iloc[-1] if adx_data is not None else 0
        
        is_us = ticker in US_TICKERS or ticker in ['MU', 'WDC']
        title_icon = "🇺🇸" if is_us else "🇹🇼"
        
        settlement_msg, days_to_settle = get_settlement_status()
        spot, fut, basis = get_futures_basis()
        basis_msg = f" \n 台指期結算日價差: {basis:.0f}" if "TW" in ticker and days_to_settle == 0 else ""
        
        premium_msg = ""
        is_premium_high = False
        if not is_us and "0050" not in ticker and ".TW" in ticker:
            nav = get_realtime_nav(ticker)
            if nav:
                premium = ((price - nav) / nav) * 100
                premium_msg = f"/ 溢價: {premium:+.2f}%"
                if premium > 3.0: is_premium_high = True; premium_msg += " 🔥太貴"
                elif premium < -1.0: premium_msg += " 💧折價"

        action, icon, reason = "信仰續抱", "💎", f"趨勢行進 (ADX={adx:.1f})"

        if "00631L" in ticker or "00675L" in ticker:
            if days_to_settle == 0:
                settlement_msg += f" (🔥本日結算)"
                if basis > 40: action, icon, reason = "⚠️ 提防殺尾盤", "📉", "順價差過大，期貨恐補跌"
                elif basis < -60: action, icon, reason = "✨ 期待拉尾盤", "📈", "逆價差過大，易拉高收斂"
                else: action, icon, reason = "觀望 (避結算)", "👀", "結算日震盪風險"
            elif days_to_settle == 1 and bias > 20:
                action, icon, reason = "🚀 提前停利", "💰", "明日結算+乖離大，落袋為安"

        elif is_premium_high:
            action, icon, reason = "💎 溢價套利 (賣)", "💸", "溢價>3% 價格虛高"

        elif ticker == '0050.TW':
            k_val = df.ta.stoch(k=9, d=3)['STOCHk_9_3_3'].iloc[-1]
            if current_vix > 30: action, icon, reason = "💎 恐慌貪婪買", "🔥🔥", f"VIX飆高 {current_vix:.1f}"
            elif k_val < 20: action, icon, reason = "💰 KD超賣買", "📉", "KD低檔鈍化"
            elif price < df['Open'].iloc[-1]: action, icon, reason = "✅ 收綠買進", "🌱", "日常累積股數"
            else: action, icon, reason = "觀望", "👀", "暫不追高"

        elif "TW" in ticker or is_us:
            if bias > (30 if is_us else 25): action, icon, reason = "🚀 網格停利", "💰", f"乖離過熱 {bias:.1f}%"
            elif price < ma120 and current_vix > 30: action, icon, reason = "💎 恐慌鑽石買", "🔥🔥🔥", "半年線+VIX爆表"
            elif price < ma60: action, icon, reason = "✨ 試單加碼", "🟢", "季線價值浮現"
            elif price < ma20 and adx > 25 and ma20 > ma20_prev: action, icon, reason = "🎯 強勢回檔買", "🟡", "破月線但趨勢強且月線上揚"
            elif adx < 20: action, icon, reason = "⚠️ 盤整忍耐", "🧘", "無趨勢避耗損"

        settle_info = f"\n🗓️ {settlement_msg}" if settlement_msg else ""
        return f"\n\n📊 【{title_icon} {ticker}】{settle_info}{basis_msg}\n現價: {price:.2f} (乖離 {bias:.1f}%)\n{premium_msg}💡 {icon} {action}\n📝 {reason}"
    except Exception as e: return f"\n⚠️ {ticker} 錯誤: {e}"

def analyze_memory_stock(ticker, name, spot_data, contract_sentiment):
    yf_ticker = f"{ticker}.TWO" if ticker == "8299" else f"{ticker}.TW"
    try:
        df = yf.Ticker(yf_ticker).history(period="150d")
        if df.empty or len(df) < 60: return f"⚠️ {name} 數據不足\n"
        price = df['Close'].iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        ma60 = df['Close'].rolling(60).mean().iloc[-1]
    except: return f"⚠️ {name} 抓取錯誤\n"

    def format_price(info):
        return f"N/A ({info['spec']})" if info['price'] == "N/A" else f"{info['unit']}{info['price']} ({info['spec']})"

    if ticker == "2408": focus_spot = f"DRAM: {format_price(spot_data['DRAM'])}"
    elif ticker == "2337": focus_spot = f"NOR: {format_price(spot_data['NOR'])}"
    elif ticker == "8299": focus_spot = f"NAND: {format_price(spot_data['NAND'])}"
    else: focus_spot = f"整體趨勢: {spot_data['Trend']}"

    action, reason = "👀 觀望 (Wait)", "多空不明"
    if spot_data['Trend'] == "🔺 上漲" and price > ma20: action, reason = "🔥 順勢買進", "報價漲 + 站穩月線"
    elif spot_data['Trend'] == "🔻 下跌" and price < ma20: action, reason = "⚠️ 避險賣出", "報價跌 + 破月線"
    elif contract_sentiment == "📈 預期看漲" and price < ma60: action, reason = "💎 價值佈局", "合約漲 + 回測季線"

    return f"💾 【{name} {ticker}】\n現價: {price:.1f} | 季線: {ma60:.1f}\n💡 {action} \n ({reason})\n"
