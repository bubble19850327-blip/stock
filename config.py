import os
from datetime import timezone, timedelta

# LINE API
CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
USER_ID = os.environ.get('LINE_USER_ID')

# 時區設定
TW_TZ = timezone(timedelta(hours=8))

# 股票清單
TW_TICKERS = ['00631L.TW', '00675L.TW', '0050.TW']
US_TICKERS = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'TSM']
US_MEMORY = ['MU', 'WDC'] # 美光、威騰
TW_MEMORY = [("8299", "群聯"), ("2337", "旺宏"), ("2408", "南亞科"), ("2344", "華邦電")]

# 記憶體備份資料
FALLBACK_DATA = {
    "DRAM": {"price": "14.70", "spec": "DDR4 16Gb eTT (Backup)", "unit": "US$", "trend": "持平"},
    "NAND": {"price": "3.85", "spec": "512Gb TLC (Backup)", "unit": "US$", "trend": "持平"},
    "NOR":  {"price": "N/A",  "spec": "Generic NOR", "unit": "", "trend": "持平"},
    "ROM":  {"price": "N/A",  "spec": "Generic ROM", "unit": "", "trend": "持平"},
    "Trend": "🔺 上漲"
}
