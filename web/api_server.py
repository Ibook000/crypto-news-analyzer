import sys
import os

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json
from sqlalchemy import func

# 导入数据库操作
from database.operations import Database, Article
from utils.ai_processor import process_unprocessed_articles
from utils.fetch_and_save import fetch_and_save
import uuid
import threading
from datetime import datetime
from config.config import DB_URL

# 配置日志
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api_server.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="加密货币新闻分析API",
    description="提供加密货币新闻数据的RESTful API",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该指定具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="web/static"), name="static")

# 初始化数据库连接
try:
    db = Database(DB_URL)
    logger.info("数据库连接成功")
except Exception as e:
    logger.error(f"数据库初始化失败: {e}")
    raise

# 定义响应模型
class ArticleResponse(BaseModel):
    id: str
    source: Optional[str] = None
    title: Optional[str] = None
    link: Optional[str] = None
    summary: Optional[str] = None
    published: Optional[datetime] = None
    content: Optional[str] = None
    author: Optional[str] = None
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    chinese_summary: Optional[str] = None
    keywords: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    ai_processed: bool = False

    class Config:
        from_attributes = True

class ArticleListResponse(BaseModel):
    articles: List[ArticleResponse]
    total: int
    page: int
    page_size: int

class ProcessRequest(BaseModel):
    batch_size: int = 10
    delay: float = 0.5

# 简易任务状态存储
TASKS = {}
TASKS_LOCK = threading.Lock()

def _set_task(task_id: str, data: dict):
    with TASKS_LOCK:
        TASKS[task_id] = data

def _get_task(task_id: str):
    with TASKS_LOCK:
        return TASKS.get(task_id)

# 辅助函数：将Article对象转换为响应模型
def article_to_response(article: Article) -> ArticleResponse:
    return ArticleResponse(
        id=article.id,
        source=article.source,
        title=article.title,
        link=article.link,
        summary=article.summary,
        published=article.published,
        content=article.content,
        author=article.author,
        sentiment=article.sentiment,
        sentiment_score=article.sentiment_score,
        chinese_summary=article.chinese_summary,
        keywords=article.keywords,
        created_at=article.created_at,
        updated_at=article.updated_at,
        ai_processed=article.ai_processed
    )

# API端点
@app.get("/", response_class=HTMLResponse)
async def root():
    """返回主页HTML"""
    try:
        with open("web/templates/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="主页模板文件不存在")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取主页模板失败: {str(e)}")

@app.get("/api/articles", response_model=ArticleListResponse)
async def get_articles(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    source: Optional[str] = Query(None, description="新闻来源筛选"),
    sentiment: Optional[str] = Query(None, description="情感筛选 (positive/negative/neutral)"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    ai_processed: Optional[bool] = Query(None, description="是否已AI处理")
):
    try:
        session = db.get_session()
        try:
            query = session.query(Article)
            if source:
                query = query.filter(Article.source == source)
            if sentiment:
                query = query.filter(Article.sentiment == sentiment)
            if ai_processed is not None:
                query = query.filter(Article.ai_processed == ai_processed)
            if start_date and end_date:
                try:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                except ValueError:
                    raise HTTPException(status_code=400, detail="日期格式错误，请使用YYYY-MM-DD格式")
                query = query.filter(Article.published.between(start_dt, end_dt))
            total = query.count()
            paginated_articles = (
                query.order_by(Article.published.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            article_responses = [article_to_response(a) for a in paginated_articles]
            return ArticleListResponse(
                articles=article_responses,
                total=total,
                page=page,
                page_size=page_size
            )
        finally:
            session.close()
    except HTTPException:
        raise
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"获取文章失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取文章失败: {str(e)}")

@app.get("/api/articles/by-id", response_model=ArticleResponse)
async def get_article_by_id(article_id: str = Query(..., description="文章ID")):
    """
    获取单篇文章详情（使用查询参数）
    """
    try:
        session = db.get_session()
        try:
            article = session.query(Article).filter_by(id=article_id).first()
            if not article:
                raise HTTPException(status_code=404, detail="文章不存在")
            return article_to_response(article)
        finally:
            session.close()
    except HTTPException:
        raise
    except Exception as e:
        # 记录详细错误信息到日志
        logger = logging.getLogger(__name__)
        logger.error(f"获取文章详情失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取文章失败: {str(e)}")

@app.get("/api/articles/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: str):
    """
    获取单篇文章详情
    """
    try:
        session = db.get_session()
        try:
            article = session.query(Article).filter_by(id=article_id).first()
            if not article:
                raise HTTPException(status_code=404, detail="文章不存在")
            return article_to_response(article)
        finally:
            session.close()
    except HTTPException:
        raise
    except Exception as e:
        # 记录详细错误信息到日志
        logger = logging.getLogger(__name__)
        logger.error(f"获取文章详情失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取文章失败: {str(e)}")

@app.get("/api/sources")
async def get_sources():
    """
    获取所有新闻来源
    """
    try:
        session = db.get_session()
        try:
            # 获取所有不重复的新闻来源
            sources = session.query(Article.source).distinct().all()
            return [source[0] for source in sources if source[0]]
        finally:
            session.close()
    except Exception as e:
        # 记录详细错误信息到日志
        logger = logging.getLogger(__name__)
        logger.error(f"获取新闻来源失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取新闻来源失败: {str(e)}")

@app.get("/api/sentiments")
async def get_sentiments():
    """
    获取所有情感类型
    """
    try:
        session = db.get_session()
        try:
            # 获取所有不重复的情感类型
            sentiments = session.query(Article.sentiment).distinct().all()
            return [sentiment[0] for sentiment in sentiments if sentiment[0]]
        finally:
            session.close()
    except Exception as e:
        # 记录详细错误信息到日志
        logger = logging.getLogger(__name__)
        logger.error(f"获取情感类型失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取情感类型失败: {str(e)}")

@app.get("/api/stats")
async def get_stats():
    """
    获取统计信息
    """
    try:
        session = db.get_session()
        try:
            total_articles = session.query(Article).count()
            processed_articles = session.query(Article).filter_by(ai_processed=True).count()
            unprocessed_articles = total_articles - processed_articles
            
            # 按来源统计
            source_stats = {}
            sources = session.query(Article.source, func.count(Article.id)).group_by(Article.source).all()
            for source, count in sources:
                if source:
                    source_stats[source] = count
            
            # 按情感统计
            sentiment_stats = {}
            sentiments = session.query(Article.sentiment, func.count(Article.id)).group_by(Article.sentiment).all()
            for sentiment, count in sentiments:
                if sentiment:
                    sentiment_stats[sentiment] = count
            
            return {
                "total_articles": total_articles,
                "processed_articles": processed_articles,
                "unprocessed_articles": unprocessed_articles,
                "source_stats": source_stats,
                "sentiment_stats": sentiment_stats
            }
        finally:
            session.close()
    except Exception as e:
        # 记录详细错误信息到日志
        logger = logging.getLogger(__name__)
        logger.error(f"获取统计信息失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")

@app.post("/api/process-unprocessed")
async def process_unprocessed(req: ProcessRequest, background_tasks: BackgroundTasks):
    """后台触发处理未AI文章，立即返回任务ID"""
    try:
        task_id = str(uuid.uuid4())
        _set_task(task_id, {
            "type": "process",
            "status": "running",
            "started_at": datetime.utcnow().isoformat()
        })

        def _run():
            try:
                result = process_unprocessed_articles(batch_size=req.batch_size, delay=req.delay)
                _set_task(task_id, {
                    "type": "process",
                    "status": "completed",
                    "started_at": _get_task(task_id)["started_at"],
                    "finished_at": datetime.utcnow().isoformat(),
                    "detail": result
                })
            except Exception as e:
                _set_task(task_id, {
                    "type": "process",
                    "status": "failed",
                    "started_at": _get_task(task_id)["started_at"],
                    "finished_at": datetime.utcnow().isoformat(),
                    "detail": {"error": str(e)}
                })

        background_tasks.add_task(_run)
        return {"task_id": task_id, "message": "处理任务已触发"}
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"触发处理任务失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"触发失败: {str(e)}")

@app.post("/api/fetch-latest")
async def fetch_latest(background_tasks: BackgroundTasks):
    """后台触发抓取任务，立即返回任务ID"""
    try:
        task_id = str(uuid.uuid4())
        _set_task(task_id, {
            "type": "fetch",
            "status": "running",
            "started_at": datetime.utcnow().isoformat()
        })

        def _run():
            try:
                fetch_and_save()
                _set_task(task_id, {
                    "type": "fetch",
                    "status": "completed",
                    "started_at": _get_task(task_id)["started_at"],
                    "finished_at": datetime.utcnow().isoformat()
                })
            except Exception as e:
                _set_task(task_id, {
                    "type": "fetch",
                    "status": "failed",
                    "started_at": _get_task(task_id)["started_at"],
                    "finished_at": datetime.utcnow().isoformat(),
                    "detail": {"error": str(e)}
                })

        background_tasks.add_task(_run)
        return {"task_id": task_id, "message": "抓取任务已触发"}
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"触发抓取任务失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"触发失败: {str(e)}")

@app.get("/api/task-status")
async def task_status(task_id: str = Query(..., description="任务ID")):
    """查询后台任务状态"""
    task = _get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task

# 启动服务器时的提示
if __name__ == "__main__":
    import uvicorn
    print("启动加密货币新闻分析API服务器...")
    print("API文档地址: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)