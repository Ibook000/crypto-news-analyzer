import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.fetch_and_save import fetch_and_save, logger
import schedule
import time

def main():
    """主函数：启动加密货币新闻抓取服务"""
    logger.info("🚀 加密货币新闻分析器启动")
    
    # 立即执行一次抓取
    logger.info("📰 执行首次新闻抓取...")
    fetch_and_save()
    
    # 配置定时任务，每小时执行一次
    schedule.every(1).hours.do(fetch_and_save)
    logger.info("⏰ 定时任务已配置: 每小时执行一次")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次任务
    except KeyboardInterrupt:
        logger.info("👋 新闻定时抓取服务已停止")
    except Exception as e:
        logger.error(f"❌ 服务异常终止: {e}")
        raise

if __name__ == "__main__":
    main()
