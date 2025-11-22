import sys
import os
import threading
import time
import schedule
import uvicorn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.fetch_and_save import fetch_and_save, logger
from utils.ai_processor import process_unprocessed_articles
from config.config import (
    FETCH_INTERVAL_MINUTES,
    PROCESS_INTERVAL_MINUTES,
    PROCESS_BATCH_SIZE,
    PROCESS_DELAY_SEC,
)

_lock = threading.Lock()

def drain_unprocessed():
    if not _lock.acquire(blocking=False):
        return
    try:
        loops = 0
        while loops < 10:
            result = process_unprocessed_articles(
                batch_size=PROCESS_BATCH_SIZE,
                delay=PROCESS_DELAY_SEC,
            )
            if not result or result.get("processed", 0) == 0:
                break
            loops += 1
    finally:
        _lock.release()

def run_api():
    p = int(os.getenv("PORT", "8002"))
    uvicorn.run("web.api_server:app", host="0.0.0.0", port=p, log_level="info")

def main():
    logger.info("启动主入口")
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    fetch_and_save()
    schedule.every(FETCH_INTERVAL_MINUTES).minutes.do(fetch_and_save)
    schedule.every(PROCESS_INTERVAL_MINUTES).minutes.do(drain_unprocessed)
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
