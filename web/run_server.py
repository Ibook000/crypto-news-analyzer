#!/usr/bin/env python3
"""
Web服务器启动脚本
用于启动FastAPI后端服务和静态文件服务
"""

import os
import sys
import uvicorn
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入API服务器
from web.api_server import app

def main():
    """启动Web服务器"""
    # 获取项目根目录
    web_dir = Path(__file__).parent
    
    # 配置静态文件目录
    static_dir = web_dir / "static"
    templates_dir = web_dir / "templates"
    
    # 确保目录存在
    static_dir.mkdir(exist_ok=True)
    templates_dir.mkdir(exist_ok=True)
    
    print("🚀 启动加密货币新闻分析器Web服务...")
    print(f"📁 静态文件目录: {static_dir}")
    print(f"📁 模板目录: {templates_dir}")
    print(f"🌐 访问地址: http://localhost:8000")
    print(f"📚 API文档: http://localhost:8000/docs")
    print("\n按 Ctrl+C 停止服务")
    
    # 启动服务器
    uvicorn.run(
        "web.api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(web_dir)],
        log_level="info"
    )

if __name__ == "__main__":
    main()