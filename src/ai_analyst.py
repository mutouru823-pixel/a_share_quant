# -*- coding: utf-8 -*-
"""
AI 智能分析师模块
基于 Agnes AI 大模型，将量化信号转化为专业自然语言分析报告。
兼容 OpenAI API 格式。
"""
import logging
import json
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# 默认配置（从 config.json 覆盖）
DEFAULT_BASE_URL = "https://apihub.agnes-ai.com/v1"
DEFAULT_MODEL = "agnes-2.0-flash"
DEFAULT_TIMEOUT = 60


class AIAnalyst:
    """
    AI 智能分析师
    将多维量化信号转化为专业、易懂的自然语言分析报告。
    """

    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL,
                 model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def _chat(self, messages: list, temperature: float = 0.7,
              max_tokens: int = 2000) -> Optional[str]:
        """调用 Chat Completion API"""
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            resp = self.session.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            elif resp.status_code == 401:
                logger.error("AI API 认证失败，请检查密钥")
                return None
            elif resp.status_code == 429:
                logger.warning("AI API 限流")
                return None
            else:
                logger.warning(f"AI API 返回 {resp.status_code}: {resp.text[:300]}")
                return None
        except requests.exceptions.Timeout:
            logger.warning("AI API 请求超时")
            return None
        except Exception as e:
            logger.warning(f"AI API 异常: {e}")
            return None

    # ============ 核心功能 ============

    def analyze_stock(self, signal: dict, fund_data: dict = None) -> str:
        """
        生成单只股票的 AI 深度分析报告
        """
        prompt = f"""你是一位资深A股量化分析师。请根据以下量化系统输出的多维数据，撰写一段专业但易懂的个股分析（200-400字）。

【股票】{signal.get('symbol', 'N/A')}
【日期】{signal.get('date', 'N/A')}
【收盘价】{signal.get('close', 0)} 元，当日涨跌 {signal.get('pct_change', 0):+.2f}%

【四维评分】（范围 -100 ~ +100）
- 技术面: {signal.get('tech_score', 0):+.1f}
- 量价面: {signal.get('vol_score', 0):+.1f}
- 资金面: {signal.get('fund_score', 0):+.1f}
- 舆情面: {signal.get('sentiment_score', 0):+.1f}
- 综合评分: {signal.get('total_score', 0):+.1f}

【技术指标】
- 均线: MA5={signal.get('SMA_5')}, MA10={signal.get('SMA_10')}, MA20={signal.get('SMA_20')}, MA60={signal.get('SMA_60')}
- RSI(14): {signal.get('RSI_14', 50):.1f}
- MACD: DIF={signal.get('MACD_DIF', 0)}, DEA={signal.get('MACD_DEA', 0)}, 柱={signal.get('MACD_HIST', 0)}
- 布林带%B: {signal.get('BB_PctB', 0.5):.3f}
- KDJ_J: {signal.get('KDJ_J', 50):.1f}
- ATR(14): {signal.get('ATR_14', 0)}
- 量比: {signal.get('VOL_Ratio', 1):.2f}
- 5日动量: {signal.get('Momentum_5', 0):+.2f}%

【系统判定】
- 市场状态: {signal.get('market_state', 'N/A')}
- 置信度: {signal.get('confidence', 0):.0%}
- 建议仓位: {signal.get('recommended_position', 0):.0f}%
- 操作建议: {signal.get('suggestion', 'N/A')}
- 风险等级: {signal.get('risk_level', 'N/A')}
- 风控预警: {', '.join(signal.get('warnings', [])) or '无'}

请从以下角度分析：
1. 当前趋势判断（多/空/震荡）及核心依据
2. 量价配合情况与资金动向
3. 短期关键支撑/压力位参考
4. 操作建议与风险提示

语言风格：专业简洁，避免废话，像给基金经理写的晨报。不要用markdown格式，直接写段落。"""

        messages = [
            {"role": "system", "content": "你是一位顶级A股量化分析师，擅长将量化数据转化为精准的投资研判。语言简练专业，观点明确，不含糊。"},
            {"role": "user", "content": prompt},
        ]

        result = self._chat(messages, temperature=0.6)
        return result or "AI 分析暂不可用"

    def market_overview(self, sectors: list, results: list, macro_ctx: dict = None) -> str:
        """
        生成市场总览 AI 点评
        """
        sector_text = ""
        if sectors:
            sector_text = "领涨板块: " + ", ".join(
                [f"{s.get('板块名称', '')}({s.get('涨跌幅', 0):+.1f}%)" for s in sectors[:5]]
            )

        stocks_text = ""
        if results:
            stocks_text = "\n".join([
                f"- {r['symbol']}: 评分{r['total_score']:+.1f}, {r['market_state']}, {r['suggestion']}"
                for r in results
            ])

        macro_text = ""
        if macro_ctx:
            if "market_sentiment_index" in macro_ctx:
                macro_text += f"市场情绪指数: {macro_ctx['market_sentiment_index']}\n"

        prompt = f"""请根据以下市场数据，写一段100-200字的市场总览点评。

{sector_text}
{macro_text}

持仓个股状态:
{stocks_text}

要求：概括今日市场特征，点评持仓组合整体状态，给出简短的下一步关注要点。像晨报开头的大盘综述。"""

        messages = [
            {"role": "system", "content": "你是A股市场策略分析师，擅长用精炼语言概括市场全貌。"},
            {"role": "user", "content": prompt},
        ]

        result = self._chat(messages, temperature=0.7, max_tokens=800)
        return result or ""

    def risk_alert(self, alerts: list) -> str:
        """
        生成风控预警的 AI 解读
        """
        if not alerts:
            return ""

        alerts_text = "\n".join([
            f"- {a['symbol']}(评分{a['total_score']:+.1f}): {', '.join(a.get('warnings', []))}"
            for a in alerts
        ])

        prompt = f"""以下股票触发了量化风控预警，请给出简短的风险研判和应对建议（100字以内每只）：

{alerts_text}

要求：判断预警严重程度，给出具体应对动作（持有观察/减仓/清仓），不要泛泛而谈。"""

        messages = [
            {"role": "system", "content": "你是风控专家，语言直接果断，不模棱两可。"},
            {"role": "user", "content": prompt},
        ]

        result = self._chat(messages, temperature=0.5, max_tokens=1000)
        return result or ""

    def health_check(self) -> bool:
        """检查 API 连通性"""
        messages = [{"role": "user", "content": "回复OK"}]
        result = self._chat(messages, max_tokens=10)
        if result:
            logger.info(f"AI 分析师已连接 (模型: {self.model})")
            return True
        logger.warning("AI 分析师连接失败")
        return False


# ============ 全局实例 ============

_ai_instance: Optional[AIAnalyst] = None


def init_ai_analyst(api_key: str, base_url: str = DEFAULT_BASE_URL,
                    model: str = DEFAULT_MODEL) -> AIAnalyst:
    """初始化全局 AI 分析师"""
    global _ai_instance
    _ai_instance = AIAnalyst(api_key, base_url, model)
    return _ai_instance


def get_ai_analyst() -> Optional[AIAnalyst]:
    """获取全局 AI 分析师实例"""
    return _ai_instance
