import os
from pathlib import Path
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# RSS源配置
RSS_FEEDS = {
    'cointelegraph': {
        'url': 'https://cointelegraph.com/rss',
        'name': 'Cointelegraph',
    },
    'coindesk': {
        'url': 'https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml',
        'name': 'CoinDesk', 
    },
    'cryptoslate': {
        'url': 'https://cryptoslate.com/feed/',
        'name': 'CryptoSlate',
    }
}
BASE_URL = os.getenv("BASE_URL", "openai")  
API_KEY = os.getenv("API_KEY")
MODEL = os.getenv("MODEL")

# 抓取配置
FETCH_INTERVAL = 300
MAX_RETRIES = 3
TIMEOUT = 30
# 调度参数
FETCH_INTERVAL_MINUTES = 10
PROCESS_INTERVAL_MINUTES = 10
PROCESS_BATCH_SIZE = int(os.getenv("PROCESS_BATCH_SIZE", "20"))
PROCESS_DELAY_SEC = float(os.getenv("PROCESS_DELAY_SEC", "0.5"))
#数据库配置
DB_URL='sqlite:///f:/PyCode/crypto-news-analyzer/database/crypto_news.db'
if __name__ == "__main__":
    print(BASE_URL, API_KEY, MODEL)
