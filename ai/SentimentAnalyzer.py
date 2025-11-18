import openai
from typing import Tuple, Optional
import json
import logging
from config.config import BASE_URL, API_KEY, MODEL
logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """市场情绪分析器"""
    
    def __init__(self, base_url: str = BASE_URL, api_key: str = API_KEY, model: str = MODEL):
        self.client = openai.OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
    
    def analyze_with_tools(self, title: str, content: str) -> Tuple[str, float, str]:
        """
        使用工具函数模式分析新闻情感（备用方案）
        返回: (情感类型, 情感分数, 中文摘要)
        """
        try:
            # 定义工具函数
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "analyze_sentiment",
                        "description": "分析加密货币新闻的情感倾向",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "sentiment": {
                                    "type": "string",
                                    "enum": ["positive", "negative", "neutral"],
                                    "description": "新闻的情感倾向"
                                },
                                "score": {
                                    "type": "number",
                                    "description": "情感分数，范围从-1.0到1.0"
                                },
                                "chinese_summary": {
                                    "type": "string",
                                    "description": "新闻的中文摘要"
                                }
                            },
                            "required": ["sentiment", "score", "chinese_summary"]
                        }
                    }
                }
            ]
            
            # 构建提示词
            prompt = f"""
            请分析以下加密货币新闻的情感倾向：
            
            标题: {title}
            内容: {content}
            
            请使用analyze_sentiment工具返回分析结果。
            """
            
            # 调用API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是专业的加密货币市场分析师，擅长分析新闻对市场情绪的影响。"},
                    {"role": "user", "content": prompt}
                ],
                tools=tools,
                tool_choice={"type": "function", "function": {"name": "analyze_sentiment"}}
            )
            
            # 解析工具调用响应
            tool_call = response.choices[0].message.tool_calls[0]
            function_args = json.loads(tool_call.function.arguments)
            
            sentiment = function_args.get('sentiment', 'neutral')
            score = float(function_args.get('score', 0))
            chinese_summary = function_args.get('chinese_summary', '')
            
            # 验证情感类型
            if sentiment not in ['positive', 'negative', 'neutral']:
                sentiment = 'neutral'
            
            logger.info(f"工具函数模式分析完成: {sentiment} ({score}) - {chinese_summary}")
            return sentiment, score, chinese_summary
            
        except Exception as e:
            logger.error(f"工具函数模式分析失败: {e} - 标题: {title}", exc_info=True)
            return "neutral", 0.0, "工具函数分析失败"

    def analyze(self, title: str, content: str) -> Tuple[str, float, str]:
        """
        分析新闻情感
        返回: (情感类型, 情感分数)
        """
        try:
            # 优化后的提示词，更加结构化和明确
            prompt = f"""
            你是专业的加密货币市场分析师，擅长分析新闻对市场情绪的影响。请严格按照以下要求执行分析：
            
            ## 分析对象
            标题: {title}
            内容: {content}
            
            ## 分析要求
            1. 识别新闻中提到的具体加密货币（如比特币、以太坊等）
            2. 分析新闻对整体加密货币市场或特定币种的影响
            3. 考虑市场当前可能的反应和投资者情
            4. 忽略不相关的背景信息，聚焦核心内容
            
            ## 评分标准
            - 情感类型：必须是positive（积极）、negative（消极）或neutral（中性）之一
            - 情感分数：-1.0（极度负面）到1.0（极度正面）的浮点数
            
            ## 输出格式（必须严格遵守）
            {{
                "sentiment": "positive/negative/neutral",
                "score": 0.0,
                "chinese_summary": "新闻的中文摘要"
            }}
            
            ## 示例
            {{
                "sentiment": "positive",
                "score": 0.75,
                "chinese_summary": "比特币减半事件预期将减少供应，历史上常引发价格上涨。"
            }}
            
            请只返回JSON格式的结果，不要包含任何其他文本。
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是深耕加密货币领域的市场情绪分析师，精通链上数据、宏观政策与热点事件对行情的即时影响，尤其擅长从话题热度与资金流向中提炼可操作的情绪信号。"},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            # 获取响应内容
            response_content = response.choices[0].message.content
            logger.debug(f"API原始响应: {response_content}")
            
            # 尝试解析JSON
            try:
                result = json.loads(response_content)
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析错误: {e} - 原始内容: {response_content}")
                # 尝试修复常见的JSON格式问题
                try:
                    # 移除可能的前后缀非JSON内容
                    json_start = response_content.find('{')
                    json_end = response_content.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        cleaned_json = response_content[json_start:json_end]
                        result = json.loads(cleaned_json)
                    else:
                        raise ValueError("无法找到有效的JSON内容")
                except Exception as fix_error:
                    logger.error(f"JSON修复尝试失败: {fix_error}")
                    logger.warning("JSON模式完全失败，切换到工具函数模式")
                    # 切换到工具函数模式作为备用
                    return self.analyze_with_tools(title, content)
            
            chinese_summary = result.get('chinese_summary', '')
            sentiment = result.get('sentiment', 'neutral')
            score = float(result.get('score', 0))
            
            # 验证情感类型
            if sentiment not in ['positive', 'negative', 'neutral']:
                sentiment = 'neutral'
            
            logger.info(f"情感分析完成: {sentiment} ({score}) - {chinese_summary}")
            return sentiment, score, chinese_summary
            
        except Exception as e:
            logger.error(f"情感分析失败: {e} - 标题: {title}", exc_info=True)
            return "neutral", 0.0, "分析失败"
