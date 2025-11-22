# 添加项目根目录到Python路径，使模块可以正确导入
import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

import logging
from typing import List, Dict, Any
from database.operations import Database
from ai.SentimentAnalyzer import SentimentAnalyzer
try:
    # 优先使用抓取器抽取正文
    from fetchers.context_extractor import extract_with_trafilatura
except Exception:
    # 当依赖未安装或导入失败时，提供降级函数，返回None
    def extract_with_trafilatura(url: str):
        return None
from config.config import DB_URL
import time
# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ai_processor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def process_unprocessed_articles(batch_size, delay: float = 1.0) -> Dict[str, Any]:
    """
    处理数据库中未经过AI处理的新闻文章
    
    Args:
        batch_size: 每批处理的文章数量
        delay: 每篇文章处理之间的延迟（秒），避免API调用过于频繁
        
    Returns:
        包含处理结果的字典
    """
    logger.info("开始处理未处理的新闻文章...")
    
    # 初始化数据库和AI分析器
    db = Database(DB_URL)
    analyzer = SentimentAnalyzer()
    
    # 获取未处理的文章
    unprocessed_articles = db.get_unprocessed_articles(limit=batch_size)
    
    if not unprocessed_articles:
        logger.info("没有需要处理的文章")
        return {"processed": 0, "success": 0, "failed": 0, "articles": []}
    
    logger.info(f"找到 {len(unprocessed_articles)} 篇未处理的文章")
    
    processed_count = 0
    success_count = 0
    failed_count = 0
    processed_articles = []
    
    for article in unprocessed_articles:
        try:
            article_id = article.id
            title = article.title or ''
            content = extract_with_trafilatura(article.link)
            keywords = article.keywords
            if content == None:
                content = article.content
            if keywords == None:
                keywords = extract_keywords(title, content)
            # 检查标题和内容是否为空
            if not title or not content:
                logger.warning(f"文章 ID {article_id} 缺少标题或内容")
                #continue
            
            logger.info(f"正在处理文章 ID {article_id}: {title[:50]}...")
            
            # 进行AI分析
            sentiment, sentiment_score, chinese_summary = analyzer.analyze(title, content)


            
            # 更新数据库中的文章
            update_data = {
                'sentiment': sentiment,
                'sentiment_score': sentiment_score,
                'chinese_summary': chinese_summary,
                'keywords': keywords,
                'ai_processed': True
            }
            
            if db.update_article(article_id, update_data):
                logger.info(f"文章 ID {article_id} 处理成功")
                success_count += 1
                processed_articles.append({
                    'id': article_id,
                    'title': title,
                    'sentiment': sentiment,
                    'sentiment_score': sentiment_score
                })
            else:
                logger.error(f"文章 ID {article_id} 更新失败")
                failed_count += 1
            
            processed_count += 1
            
            # 添加延迟，避免API调用过于频繁
            if delay > 0:
                time.sleep(delay)
                
        except Exception as e:
            logger.error(f"处理文章 ID {article.id if hasattr(article, 'id') else 'unknown'} 时出错: {e}")
            failed_count += 1
    
    result = {
        "processed": processed_count,
        "success": success_count,
        "failed": failed_count,
        "articles": processed_articles
    }
    
    logger.info(f"处理完成: 总计 {processed_count} 篇，成功 {success_count} 篇，失败 {failed_count} 篇")
    return result

def extract_keywords(title: str, content: str, max_keywords: int = 5) -> str:
    """
    从标题和内容中提取关键词
    
    Args:
        title: 文章标题
        content: 文章内容
        max_keywords: 最大关键词数量
        
    Returns:
        逗号分隔的关键词字符串
    """
    # 简单的关键词提取实现，可以根据需要改进
    # 这里使用常见的加密货币相关词汇
    crypto_keywords = [
        '比特币', 'BTC', '以太坊', 'ETH', '莱特币', 'LTC',
        '瑞波币', 'XRP', '狗狗币', 'DOGE', '币安币', 'BNB',
        '卡尔达诺', 'ADA', '索拉纳', 'SOL', '波卡', 'DOT',
        '链上', 'DeFi', 'NFT', 'Web3', '挖矿', '区块链',
        '交易所', '监管', '牛市', '熊市', '价格', '涨跌',
        '投资', '交易', '钱包', '智能合约', '减半', '分叉'
    ]
    
    text = (title + " " + content).lower()
    found_keywords = []
    
    for keyword in crypto_keywords:
        if keyword.lower() in text:
            found_keywords.append(keyword)
            if len(found_keywords) >= max_keywords:
                break
    
    return ", ".join(found_keywords) if found_keywords else "加密货币"

def run_continuous_processing(interval_minutes: int = 60, batch_size: int = 10):
    """
    持续运行AI处理，定期检查并处理未处理的文章
    
    Args:
        interval_minutes: 检查间隔（分钟）
        batch_size: 每批处理的文章数量
    """
    logger.info(f"启动持续AI处理，每 {interval_minutes} 分钟检查一次，每批处理 {batch_size} 篇文章")
    
    while True:
        try:
            result = process_unprocessed_articles(batch_size=batch_size)
            
            # 如果没有文章需要处理，可以适当延长等待时间
            if result["processed"] == 0:
                logger.info("没有需要处理的文章，延长等待时间")
                time.sleep(interval_minutes * 60 * 2)  # 双倍等待时间
            else:
                time.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            logger.info("接收到中断信号，停止AI处理")
            break
        except Exception as e:
            logger.error(f"持续处理过程中出错: {e}")
            time.sleep(interval_minutes * 60)  # 出错后等待一段时间再重试

if __name__ == "__main__":
    # 直接运行时，执行一次处理
    logger.info("执行单次AI处理任务")
    result = process_unprocessed_articles(batch_size=5)
    print(f"处理结果: {result}")
    
    # 如果需要持续运行，可以取消下面的注释
    # logger.info("启动持续AI处理服务")
    # run_continuous_processing(interval_minutes=30, batch_size=5)