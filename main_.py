import os
import sys
import requests
import yfinance as yf
import pandas_ta as ta
import calendar
from datetime import datetime, date, timezone, timedelta
from bs4 import BeautifulSoup

# === 設定區 ===
CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
USER_ID = os.environ.get('LINE_USER_ID')

TW_TICKERS = ['00631L.TW', '00675L.TW', '0050.TW']
US_TICKERS = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'TSM']

def send_push(msg):
    # 發送 LINE 推播
    if not CHANNEL_TOKEN or not USER_ID: return
    headers = {'Authorization': f'Bearer {CHANNEL_TOKEN}', 'Content-Type': 'application/json'}
    body = {'to': USER_ID, 'messages': [{'type': 'text', 'text': msg}]}
    try: requests.post('https://api.line.me/v2/bot/message/push', headers=headers, json=body)
    except: pass

# === 基礎數據獲取 ===
def get_vix():
    # 抓取美股恐慌指數
    try: return yf.Ticker('^VIX').history(period='5d')['Close'].iloc[-1]
    except: return 0

def get_realtime_nav(ticker):
    # 爬取 Yahoo 股市抓取即時淨值 (計算溢價用)
    try:
        stock_id = ticker.split('.')[0]
        url = f"https://tw.stock.yahoo.com/quote/{stock_id}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        elements = soup.find_all('li', class_='price-detail-item')
        for el in elements:
            if '淨值' in el.text:
                return float(el.find_all('span')[1].text.replace(',', ''))
    except: pass
    return None

def get_settlement_status():
    # 計算台指期結算日 (每月第3個週三)
    tw_tz = timezone(timedelta(hours=8))
    today = datetime.now(tw_tz).date()
    cal = calendar.monthcalendar(today.year, today.month)
    wednesdays = [week[2] for week in cal if week[2] != 0]
    settlement_day = wednesdays[2]
    settlement_date = date(today.year, today.month, settlement_day)
    days_diff = (settlement_date - today).days

    if days_diff == 0: return "🔥 本日結算 (慎防波動)", 0
    elif days_diff == 1: return "⚠️ 明日結算 (提防壓盤)", 1
    elif days_diff == 2: return "⚠️ 本週結算 (震盪)", 2
    return "", days_diff

def get_futures_basis():
    # 抓取台指期與大盤，計算價差 (Basis)
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res_spot = requests.get('https://tw.stock.yahoo.com/quote/^TWII', headers=headers)
        soup_spot = BeautifulSoup(res_spot.text, 'html.parser')
        spot_price = float(soup_spot.find('span', class_='Fz(32px)').text.replace(',', ''))
        
        res_fut = requests.get('https://tw.stock.yahoo.com/quote/WTX-1.F', headers=headers)
        soup_fut = BeautifulSoup(res_fut.text, 'html.parser')
        fut_price = float(soup_fut.find('span', class_='Fz(32px)').text.replace(',', ''))
        
        return spot_price, fut_price, (fut_price - spot_price)
    except:
        return 0, 0, 0

def get_tx_night():
    # 🌟 新增：抓取台指期夜盤 (08:00 執行時即為夜盤收盤價)
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get('https://tw.stock.yahoo.com/quote/WTX-1.F', headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        price = float(soup.find('span', class_='Fz(32px)').text.replace(',', ''))
        
        pct = 0.0
        for span in soup.find_all('span'):
            if '%' in span.text and ('+' in span.text or '-' in span.text):
                try:
                    pct_str = span.text.replace('(', '').replace(')', '').replace('%', '').replace('+', '')
                    pct = float(pct_str)
                    break
                except: pass
        return price, pct
    except:
        return 0, 0

# === 策略模組 ===
def analyze_pre_open(data):
    # 08:00 盤前分析 (加入台指夜盤與四大指數)
    tsm = data['tsm_pct']
    vix = data['vix']
    
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

def analyze_strategy(ticker, current_vix):
    # 13:20 盤中/收盤分析
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
        
        is_us = ticker in US_TICKERS
        title_icon = "🇺🇸" if is_us else "🇹🇼"
        
        settlement_msg, days_to_settle = get_settlement_status()
        spot, fut, basis = get_futures_basis()
        
        basis_msg = f" \n 台指期結算日價差: {basis:.0f}" if "TW" in ticker and days_to_settle == 0 else ""
        
        premium_msg = ""
        is_premium_high = False
        if not is_us and "0050" not in ticker:
            nav = get_realtime_nav(ticker)
            if nav:
                premium = ((price - nav) / nav) * 100
                premium_msg = f"/ 溢價: {premium:+.2f}%"
                if premium > 3.0: is_premium_high = True; premium_msg += " 🔥太貴"
                elif premium < -1.0: premium_msg += " 💧折價"

        action = "信仰續抱"
        icon = "💎"
        reason = f"趨勢行進 (ADX={adx:.1f})"

        if "00631L" in ticker or "00675L" in ticker:
            if days_to_settle == 0:
                settlement_msg += f" (🔥本日結算)"
                if basis > 40: action, icon, reason = "⚠️ 提防殺尾盤", "📉", "順價差過大，期貨恐補跌"
                elif basis < -60: action, icon, reason = "✨ 期待拉尾盤", "📈", "逆價差過大，易拉高收斂"
                else: action, icon, reason = "觀望 (避結算)", "👀", "結算日震盪風險"
            elif days_to_settle == 1 and bias > 20:
                action, icon, reason = "🚀 提前停利", "💰", "明日結算+乖離大，落袋為安"

        if is_premium_high:
            action, icon, reason = "💎 溢價套利 (賣)", "💸", "溢價>3% 價格虛高"

        elif ticker == '0050.TW':
            k_val = df.ta.stoch(k=9, d=3)['STOCHk_9_3_3'].iloc[-1]
            if current_vix > 30: action, icon, reason = "💎 恐慌貪婪買", "🔥🔥", f"VIX飆高 {current_vix:.1f}"
            elif k_val < 20: action, icon, reason = "💰 KD超賣買", "📉", "KD低檔鈍化"
            elif price < df['Open'].iloc[-1]: action, icon, reason = "✅ 收綠買進", "🌱", "日常累積股數"
            else: action, icon, reason = "觀望", "👀", "暫不追高"

        elif "TW" in ticker or is_us:
            if bias > (30 if is_us else 25): 
                action, icon, reason = "🚀 網格停利", "💰", f"乖離過熱 {bias:.1f}%"
            elif price < ma120 and current_vix > 30: 
                action, icon, reason = "💎 恐慌鑽石買", "🔥🔥🔥", "半年線+VIX爆表"
            elif price < ma60: 
                action, icon, reason = "✨ 試單加碼", "🟢", "季線價值浮現"
            elif price < ma20 and adx > 25 and ma20 > ma20_prev: 
                action, icon, reason = "🎯 強勢回檔買", "🟡", "破月線但趨勢強(ADX>25)且月線上揚"
            elif adx < 20: 
                action, icon, reason = "⚠️ 盤整忍耐", "🧘", "無趨勢避耗損"

        settle_info = f"\n🗓️ {settlement_msg}" if settlement_msg else ""
        return f"\n\n📊 【{title_icon} {ticker}】{settle_info}{basis_msg}\n現價: {price:.2f} (乖離 {bias:.1f}%)\n{premium_msg}💡 {icon} {action}\n📝 {reason}"

    except Exception as e: return f"\n⚠️ {ticker} 錯誤: {e}"

# === 主程式入口 ===
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    print(f"🚀 啟動模式: {mode}")

    tw_tz = timezone(timedelta(hours=8))
    tw_now = datetime.now(tw_tz)

    if mode == "pre_open":
        tickers = ['TSM', '^SOX', '^IXIC', '^DJI', '^GSPC', '^VIX']
        data = yf.download(tickers, period='5d', progress=False)['Close']
        changes = data.pct_change().iloc[-1] * 100
        last_close = data.iloc[-1]
        
        # 抓取台指期夜盤
        tx_night_price, tx_night_pct = get_tx_night()
        
        info = {
            'tsm_pct': changes['TSM'],
            'vix': last_close['^VIX'],
            'dji_price': last_close['^DJI'], 'dji_pct': changes['^DJI'],
            'spx_price': last_close['^GSPC'], 'spx_pct': changes['^GSPC'],
            'ndx_price': last_close['^IXIC'], 'ndx_pct': changes['^IXIC'],
            'sox_price': last_close['^SOX'], 'sox_pct': changes['^SOX'],
            'tx_night_price': tx_night_price, 'tx_night_pct': tx_night_pct
        }
        
        report = f"📅 {tw_now.strftime('%Y-%m-%d %H:%M')}\n" + analyze_pre_open(info)
        send_push(report)
    else:
        target_list = US_TICKERS if mode == "us" else TW_TICKERS if mode == "tw" else TW_TICKERS + US_TICKERS
        vix = get_vix()
        
        report = f"⚡ 投資戰報 {tw_now.strftime('%m-%d %H:%M')}\n🌎 VIX: {vix:.2f}"
        for t in target_list: report += analyze_strategy(t, vix)
        send_push(report)

