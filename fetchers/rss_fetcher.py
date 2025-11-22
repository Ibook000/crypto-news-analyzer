import sys
import os
import json
# 将项目根目录添加到Python路径以解决config模块导入问题
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import feedparser
import time
import requests
from datetime import datetime
from typing import List, Dict, Optional
import logging
# 导入配置
from config.config import RSS_FEEDS

# 获取当前模块的日志记录器，用于输出本模块的日志信息
logger = logging.getLogger(__name__)
class RSSFetcher:
    """RSS抓取器"""
    
    def __init__(self, feed_config: Dict):
        self.config = feed_config
    
    def fetch(self) -> List[Dict]:
        """获取RSS内容"""
        try:
            logger.info(f"正在抓取: {self.config['name']} - {self.config['url']}")
            
            # 添加请求头避免被阻止
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/xml, text/xml, application/rss+xml'
            }
            
            # feedparser会自动处理重定向和编码
            feed = feedparser.parse(
                self.config['url'],
                request_headers=headers,
                agent=headers['User-Agent']
            )
            
            if feed.bozo and feed.bozo_exception:
                logger.warning(f"RSS解析警告: {feed.bozo_exception}")
            
            if not feed.entries:
                logger.warning(f"RSS源 {self.config['name']} 没有获取到条目")
                return []
            
            articles = []
            for entry in feed.entries:  # 限制每次抓取数量
                try:
                    article = self._parse_entry(entry)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.error(f"解析条目失败: {e}")
                    continue
            
            logger.info(f"成功抓取 {len(articles)} 篇文章从 {self.config['name']}")
            return articles
            
        except Exception as e:
            logger.error(f"抓取RSS失败 {self.config['name']}: {e}")
            return []
    
    def _parse_entry(self, entry) -> Optional[Dict]:
        """解析单个RSS条目"""
        try:
            # 获取唯一ID
            original_id = entry.get('id') or entry.get('link')
            if not original_id:
                return None
            
            # 获取发布时间
            pub_date = None
            if hasattr(entry, 'published_parsed'):
                pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
            elif hasattr(entry, 'updated_parsed'):
                pub_date = datetime.fromtimestamp(time.mktime(entry.updated_parsed))
            else:
                pub_date = datetime.utcnow()
            
            # 获取内容（优先获取全文）
            content = ''
            if hasattr(entry, 'content'):
                content = entry.content[0].value
            elif hasattr(entry, 'summary'):
                content = entry.summary
            
            # 获取作者
            author = ''
            if hasattr(entry, 'author'):
                author = entry.author
            elif hasattr(entry, 'dc_creator'):
                author = entry.dc_creator
            
            # 获取分类
            categories = []
            if hasattr(entry, 'tags'):
                categories = [tag.term for tag in entry.tags if hasattr(tag, 'term')]
            
            return {
                'source': self.config['name'],
                'original_id': original_id,
                'title': entry.get('title', ''),
                'link': entry.get('link', ''),
                'description': entry.get('summary', ''),
                'content': content,
                'author': author,
                'published_at': pub_date.isoformat(),  # 将datetime转换为ISO字符串支持JSON序列化
                'categories': categories
            }
            
        except Exception as e:
            logger.error(f"解析RSS条目失败: {e}")
            return None


if __name__ == "__main__":
    fetcher = RSSFetcher(RSS_FEEDS['cryptoslate'])
    content = fetcher.fetch()
    print(f"成功抓取 {len(content)} 篇文章")
    os.makedirs('data', exist_ok=True)
    with open('data/cryptoslate.json', 'w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False, indent=2)

    if content:
        article = content[0]  # 直接获取已解析的文章，无需重新调用_parse_entry
        print(f"\n第一篇文章示例:")
        print(f"标题: {article['title']}")
        print(f"来源: {article['source']}")
        print(f"发布时间: {article['published_at']}")
        print(f"链接: {article['link']}")
        print(f"作者: {article['author']}")
        print(f"分类: {article['categories']}")
        print(f"摘要: {article['description'][:100]}...")
        from fetchers.context_extractor import extract_with_trafilatura
        full_content = extract_with_trafilatura(article['link'])
        if full_content:
            print(f"完整内容: {full_content}")
        else:
            print("无法提取完整内容")
