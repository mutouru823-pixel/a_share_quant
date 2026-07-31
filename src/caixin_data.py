# -*- coding: utf-8 -*-
"""
财新数据 API 集成模块
提供宏观经济指标、行业新闻、政策解读等高端财经数据。
API Key 通过 config.json 配置。
"""
import logging
import time
import requests
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# 财新数据 API 基础配置
CAIXIN_BASE_URL = "https://api.caixin.com"
CAIXIN_TIMEOUT = 15


class CaixinDataClient:
    """
    财新数据 API 客户端
    提供：宏观指标、行业研报摘要、政策事件、市场情绪指数
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "AShareQuant/2.0",
        })
        self._request_count = 0
        self._last_request_time = 0

    def _rate_limit(self):
        """简单限流：每秒最多2次请求"""
        self._request_count += 1
        elapsed = time.time() - self._last_request_time
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        self._last_request_time = time.time()

    def _get(self, endpoint: str, params: dict = None) -> Optional[dict]:
        """通用GET请求"""
        self._rate_limit()
        url = f"{CAIXIN_BASE_URL}/{endpoint.lstrip('/')}"
        params = params or {}
        params["api_key"] = self.api_key

        try:
            resp = self.session.get(url, params=params, timeout=CAIXIN_TIMEOUT)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 401:
                logger.error("财新数据 API 认证失败，请检查 API Key")
                return None
            elif resp.status_code == 429:
                logger.warning("财新数据 API 限流，等待后重试")
                time.sleep(5)
                return None
            else:
                logger.warning(f"财新数据 API 返回 {resp.status_code}: {resp.text[:200]}")
                return None
        except requests.exceptions.Timeout:
            logger.warning("财新数据 API 请求超时")
            return None
        except Exception as e:
            logger.warning(f"财新数据 API 请求异常: {e}")
            return None

    # ============ 宏观经济指标 ============

    def get_macro_indicators(self, indicators: list = None) -> dict:
        """
        获取宏观经济指标（PMI、CPI、GDP增速、M2等）
        用于判断宏观环境对股市的影响
        """
        if indicators is None:
            indicators = ["pmi", "cpi", "m2", "shibor"]

        results = {}
        for ind in indicators:
            data = self._get("macro/indicator", {"code": ind, "period": "latest"})
            if data and data.get("data"):
                results[ind] = data["data"]

        return results

    def get_market_sentiment_index(self) -> Optional[float]:
        """
        获取财新市场情绪指数
        返回: -100(极度恐慌) ~ +100(极度贪婪)
        """
        data = self._get("market/sentiment", {"type": "a_share"})
        if data and "data" in data:
            return data["data"].get("score", 0.0)
        return None

    # ============ 行业与政策 ============

    def get_policy_events(self, days: int = 7) -> list:
        """获取近期重大政策事件"""
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        data = self._get("policy/events", {
            "start_date": start_date,
            "end_date": end_date,
            "category": "finance,economy",
        })

        if data and "data" in data:
            return data["data"].get("events", [])
        return []

    def get_industry_outlook(self, industry: str) -> Optional[dict]:
        """获取行业前景分析"""
        data = self._get("industry/outlook", {"name": industry})
        if data and "data" in data:
            return data["data"]
        return None

    # ============ 个股增强数据 ============

    def get_stock_news_sentiment(self, symbol: str) -> Optional[dict]:
        """
        获取财新对个股的深度新闻情绪分析
        比东方财富的简单关键词匹配更精准（NLP模型驱动）
        """
        data = self._get("stock/news_sentiment", {
            "symbol": symbol,
            "days": 7,
        })
        if data and "data" in data:
            return data["data"]
        return None

    def get_institutional_view(self, symbol: str) -> Optional[dict]:
        """获取机构观点汇总"""
        data = self._get("stock/institutional_view", {"symbol": symbol})
        if data and "data" in data:
            return data["data"]
        return None

    # ============ 健康检查 ============

    def health_check(self) -> bool:
        """检查API连通性和Key有效性"""
        data = self._get("health")
        if data:
            logger.info("财新数据 API 连接正常")
            return True
        logger.warning("财新数据 API 连接失败或Key无效，将使用免费数据源")
        return False


# ============ 便捷函数 ============

_client_instance: Optional[CaixinDataClient] = None


def init_caixin_client(api_key: str) -> CaixinDataClient:
    """初始化全局财新数据客户端"""
    global _client_instance
    _client_instance = CaixinDataClient(api_key)
    return _client_instance


def get_caixin_client() -> Optional[CaixinDataClient]:
    """获取全局客户端实例"""
    return _client_instance


def fetch_caixin_sentiment(symbol: str) -> float:
    """
    获取财新情绪评分（供策略引擎调用）
    如果API不可用则返回0（不影响主流程）
    """
    client = get_caixin_client()
    if not client:
        return 0.0

    result = client.get_stock_news_sentiment(symbol)
    if result:
        return result.get("sentiment_score", 0.0)
    return 0.0


def fetch_caixin_macro_context() -> dict:
    """
    获取宏观环境上下文（供策略引擎参考）
    返回: {"pmi": ..., "cpi": ..., "sentiment_index": ..., "policy_events": [...]}
    """
    client = get_caixin_client()
    if not client:
        return {}

    context = {}

    # 市场情绪指数
    sentiment_idx = client.get_market_sentiment_index()
    if sentiment_idx is not None:
        context["market_sentiment_index"] = sentiment_idx

    # 宏观指标
    macro = client.get_macro_indicators()
    if macro:
        context["macro"] = macro

    # 近期政策
    events = client.get_policy_events(days=3)
    if events:
        context["policy_events"] = events

    return context
