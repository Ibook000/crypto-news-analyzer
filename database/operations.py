import sys
import os

# 添加项目根目录到 Python 路径
# 获取当前文件的绝对路径，然后向上两级目录找到项目根目录
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from sqlalchemy import create_engine, Column, String, Text, DateTime, Float, Boolean
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import Optional, List, Dict
import datetime
import logging
# 导入配置
from config.config import DB_URL
logger = logging.getLogger(__name__)
# 创建基类
Base = declarative_base()
logger.info(f"数据库URL: {DB_URL}")
# 定义文章模型
class Article(Base):
    __tablename__ = 'articles'
    
    id = Column(String(255), primary_key=True)  # 使用文章的唯一标识作为主键
    source = Column(String(50))  # 新闻来源（如Cointelegraph, Coindesk等）
    title = Column(String(255))  # 文章标题
    link = Column(String(255))  # 文章链接
    summary = Column(Text)  # 文章摘要
    published = Column(DateTime)  # 发布时间
    content = Column(Text)  # 完整内容（可选）
    author = Column(String(100))  # 作者（可选）
    sentiment = Column(String(100))  # 情感分析结果（'positive', 'negative', 'neutral'）
    sentiment_score = Column(Float)  # 情感分数（范围-1到1，由AI分析）
    chinese_summary = Column(Text)  # 中文摘要
    keywords = Column(String(255))  # 关键词
    created_at = Column(DateTime, default=datetime.datetime.now)  # 数据库插入时间
    updated_at = Column(DateTime, default=datetime.datetime.now)  # 数据库更新时间
    ai_processed = Column(Boolean, default=False)  # 是否已由AI处理

class Database:
    """数据库操作类，封装所有数据库交互方法"""
    def __init__(self, db_url: str):
        """初始化数据库引擎和会话"""
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)  # 创建所有表
        self.Session = sessionmaker(bind=self.engine)
        
        # 检查并迁移数据库表结构
        self._migrate_database()

    def get_session(self):
        """获取数据库会话对象"""
        return self.Session()
    
    def _migrate_database(self):
        """
        检查并迁移数据库表结构，添加缺失的列
        """
        from sqlalchemy import text
        
        # 需要添加的列定义
        columns_to_add = [
            "sentiment VARCHAR(100)",
            "sentiment_score REAL",
            "chinese_summary TEXT",
            "keywords VARCHAR(255)",
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP",
            "ai_processed BOOLEAN DEFAULT 0"
        ]
        
        with self.engine.connect() as conn:
            # 检查表是否存在
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='articles'"
            )).fetchone()
            
            if not result:
                logger.info("表 'articles' 不存在，将创建新表")
                Base.metadata.create_all(self.engine)
                logger.info("表 'articles' 创建成功")
                return
            
            # 获取当前表结构
            current_columns = conn.execute(text("PRAGMA table_info(articles)")).fetchall()
            current_column_names = [col[1] for col in current_columns]
            
            logger.info(f"当前表中的列: {current_column_names}")
            
            # 添加缺失的列
            for column_def in columns_to_add:
                column_name = column_def.split()[0]
                if column_name not in current_column_names:
                    try:
                        conn.execute(text(f"ALTER TABLE articles ADD COLUMN {column_def}"))
                        conn.commit()
                        logger.info(f"成功添加列: {column_name}")
                    except Exception as e:
                        logger.error(f"添加列 {column_name} 失败: {e}")
                else:
                    logger.info(f"列 {column_name} 已存在，跳过")
        
        logger.info("数据库迁移完成")

    def add_article(self, article_data: Dict) -> bool:
        """
        添加一篇文章到数据库
        
        参数:
            article_data: 文章数据字典
        
        返回:
            bool: 是否添加成功
        """
        session = self.get_session()
        try:
            # 检查文章是否已存在
            existing_article = session.query(Article).filter_by(id=article_data['id']).first()
            if existing_article:
                return False
            
            # 创建文章对象
            article = Article(
                id=article_data['id'],
                source=article_data['source'],
                title=article_data['title'],
                link=article_data['link'],
                summary=article_data['summary'],
                published=article_data['published'],
                content=article_data.get('content'),
                author=article_data.get('author'),
                sentiment=article_data.get('sentiment'),
                sentiment_score=article_data.get('sentiment_score'),
                chinese_summary=article_data.get('chinese_summary'),
                keywords=article_data.get('keywords'),
                ai_processed=article_data.get('ai_processed', False)  # 设置AI处理状态，默认False
            )
            
            # 添加到数据库
            session.add(article)
            session.commit()
            logger.info(f"成功添加文章 {article_data['id']} 到数据库")
            return True
        
        except Exception as e:
            session.rollback()
            logger.error(f"添加文章 {article_data['id']} 失败: {e}")
            return False
        finally:
            session.close()

    def get_articles_by_source(self, source: str) -> List[Article]:
        """
        根据来源获取文章
        
        参数:
            source: 新闻来源
        
        返回:
            List[Article]: 文章列表
        """
        session = self.get_session()
        try:
            articles = session.query(Article).filter_by(source=source).order_by(Article.published.desc()).all()
            logger.info(f"成功获取来源 {source} 的 {len(articles)} 篇文章")
            return articles
        except Exception as e:
            logger.error(f"获取来源 {source} 的文章失败: {e}")
            return []
        finally:
            session.close()

    def get_articles_by_date_range(self, start_date: datetime.datetime, end_date: datetime.datetime) -> List[Article]:
        """
        根据日期范围获取文章
        
        参数:
            start_date: 开始日期
            end_date: 结束日期
        
        返回:
            List[Article]: 文章列表
        """
        session = self.get_session()
        try:
            articles = session.query(Article).filter(
                Article.published.between(start_date, end_date)
            ).order_by(Article.published.desc()).all()
            logger.info(f"成功获取日期范围 {start_date} 到 {end_date} 的 {len(articles)} 篇文章")
            return articles
        except Exception as e:
            logger.error(f"获取日期范围 {start_date} 到 {end_date} 的文章失败: {e}")
            return []
        finally:
            session.close()

    def get_all_articles(self) -> List[Article]:
        """
        获取所有文章
        
        返回:
            List[Article]: 所有文章列表
        """
        session = self.get_session()
        try:
            articles = session.query(Article).order_by(Article.published.desc()).all()
            logger.info(f"成功获取数据库中的 {len(articles)} 篇文章")
            return articles
        except Exception as e:
            logger.error(f"获取所有文章失败: {e}")
            return []
        finally:
            session.close()

    def update_article(self, article_id: str, update_data: Dict) -> bool:
        """
        更新文章的信息
        
        参数:
            article_id: 文章ID
            update_data: 要更新的数据字典
        
        返回:
            bool: 是否更新成功  
        """
        session = self.get_session()
        try:
            article = session.query(Article).filter_by(id=article_id).first()
            if not article:
                logger.warning(f"未找到ID为 {article_id} 的文章")
                return False
            
            # 更新提供的字段
            if 'title' in update_data:
                article.title = update_data['title']
            if 'link' in update_data:
                article.link = update_data['link']
            if 'source' in update_data:
                article.source = update_data['source']
            if 'summary' in update_data:
                article.summary = update_data['summary']
            if 'published' in update_data:
                article.published = update_data['published']
            if 'content' in update_data:
                article.content = update_data['content']
            if 'author' in update_data:
                article.author = update_data['author']
            if 'keywords' in update_data:
                article.keywords = update_data['keywords']
            if 'sentiment' in update_data:
                article.sentiment = update_data['sentiment']
            if 'sentiment_score' in update_data:
                article.sentiment_score = update_data['sentiment_score']
            if 'chinese_summary' in update_data:
                article.chinese_summary = update_data['chinese_summary']
            if 'ai_processed' in update_data:
                article.ai_processed = update_data['ai_processed']
            
            article.updated_at = datetime.datetime.now()  # 更新时间戳
            session.commit()
            logger.info(f"成功更新文章 {article_id}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"更新文章 {article_id} 失败: {e}")
            return False
        finally:
            session.close()

    def get_unprocessed_articles(self, limit: int = None) -> List[Article]:
        """
        获取所有未经过AI处理的文章
        
        参数:
            limit: 限制返回的文章数量
        
        返回:
            List[Article]: 未处理的文章列表
        """
        session = self.get_session()
        try:
            query = session.query(Article).filter_by(ai_processed=False).order_by(Article.published.desc())
            if limit:
                query = query.limit(limit)
            articles = query.all()
            logger.info(f"成功获取 {len(articles)} 篇未处理的文章")
            return articles
        except Exception as e:
            logger.error(f"获取未处理文章失败: {e}")
            return []
        finally:
            session.close()
    def get_sentiment_articles(self, sentiment: str) -> List[Article]:
        """
        获取所有情感为指定值的文章
        
        参数:
            sentiment: 情感值（'positive', 'negative', 'neutral'）
        
        返回:
            List[Article]: 情感为指定值的文章列表
        """
        session = self.get_session()
        try:
            articles = session.query(Article).filter_by(sentiment=sentiment).order_by(Article.published.desc()).all()
            logger.info(f"成功获取情感为 {sentiment} 的 {len(articles)} 篇文章")
            return articles
        except Exception as e:
            logger.error(f"获取情感为 {sentiment} 的文章失败: {e}")
            return []
        finally:
            session.close()
# 示例用法
if __name__ == "__main__":
    # 初始化数据库连接
    db = Database(DB_URL)
    
    print("数据库连接成功！")
    print("已创建articles表")
    re=db.get_unprocessed_articles()
    
    print(f"未处理文章数量: {len(re)}")
