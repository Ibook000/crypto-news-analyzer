import sys
import os

# 添加项目根目录到 Python 路径
# 获取当前文件的绝对路径，然后向上两级目录找到项目根目录
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

import logging
from database.operations import Database
from fetchers.rss_fetcher import RSSFetcher
from fetchers.context_extractor import extract_with_trafilatura
from config.config import RSS_FEEDS, DB_URL
import schedule
import time
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fetch_and_save.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def fetch_and_save():
    """
    从所有RSS源抓取新闻并保存到数据库
    """
    logger.info("开始执行新闻抓取与保存任务...")
    
    try:
        # 初始化数据库连接
        db = Database(DB_URL)
        logger.info("数据库连接成功")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        return
    
    total_fetched = 0
    total_saved = 0
    
    for source_name, feed_config in RSS_FEEDS.items():
        logger.info(f"开始处理源: {source_name}")
        
        try:
            # 初始化RSS抓取器
            fetcher = RSSFetcher(feed_config)
            
            # 抓取文章
            articles = fetcher.fetch()
            fetched_count = len(articles)
            total_fetched += fetched_count
            logger.info(f"从 {source_name} 抓取到 {fetched_count} 篇文章")
            
            if not articles:
                continue
            
            # 保存文章到数据库
            saved_count = 0
            for article in articles:
                try:
                    # 准备文章数据，映射到数据库字段
                    
                    db_article = {
                        'id': article['original_id'],  # 使用RSS源的唯一ID作为数据库主键
                        'source': article['source'],
                        'title': article['title'],
                        'link': article['link'],
                        'summary': article.get('description', ''),
                        'published': datetime.fromisoformat(article['published_at']),
                        'content': extract_with_trafilatura(article.get('link', '')),
                        'author': article.get('author', ''),
                        'keywords': ','.join(article.get('categories', [])),
                        'ai_processed': False  # 初始化为未处理状态
                    }
                    
                    if db.add_article(db_article):
                        saved_count += 1
                        total_saved += 1
                    else:
                        logger.debug(f"文章已存在: {article['title']}")
                        
                except Exception as e:
                    logger.error(f"保存文章 {article.get('title', '未知标题')} 失败: {e}")
                    continue
            
            logger.info(f"源 {source_name}: {saved_count}/{fetched_count} 篇文章保存成功")
            
        except Exception as e:
            logger.error(f"处理源 {source_name} 失败: {e}")
            continue
    
    logger.info(f"新闻抓取与保存任务完成: 总共抓取 {total_fetched} 篇，保存 {total_saved} 篇新文章")

if __name__ == "__main__":
    logger.info("新闻定时抓取服务启动")
    
    # 立即执行一次抓取
    fetch_and_save()
    
    # 配置定时任务，每小时执行一次
    schedule.every(1).hours.do(fetch_and_save)
    logger.info("定时任务已配置: 每小时执行一次")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次任务
    except KeyboardInterrupt:
        logger.info("新闻定时抓取服务已停止")
    except Exception as e:
        logger.error(f"服务异常终止: {e}")
        raise