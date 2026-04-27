import logging
from src.reasoning_engine import ReasoningEngine

logger = logging.getLogger(__name__)

class StockAnalysisReport:
    """结构化的股票分析报告（Phase 2：含文字解读）"""
    
    def __init__(self, symbol: str, latest_signal: dict = None, financial_data: dict = None, warnings: list = None):
        self.symbol = symbol
        self.latest_signal = latest_signal or {}
        self.financial_data = financial_data or {}
        self.warnings = warnings or []
        
        self.metrics = self._build_metrics()
        self.total_score = self.latest_signal.get('total_score', 0)
        self.market_state = self.latest_signal.get('market_state', 'Neutral')
        self.suggestion = self.latest_signal.get('suggestion', '建议观望')
        self.risk_level = self._calc_risk_level()
        self.confidence = self._calc_confidence()
        
        # Phase 2 新增：文字解读
        self.reasoning_engine = ReasoningEngine()
        self.detailed_reasoning = self._generate_reasoning()
        self.summary = self._generate_summary()
    
    def _build_metrics(self) -> dict:
        return {
            'tech_score': self.latest_signal.get('tech_score', 0),
            'chip_score': self.latest_signal.get('chip_score', 0),
            'sentiment_score': self.latest_signal.get('sentiment_score', 0),
            'fundamental_score': self.financial_data.get('fundamental_score', 0) if self.financial_data else 0,
            'rsi': self.latest_signal.get('RSI_14', 0),
            'close': self.latest_signal.get('close', 0),
            'pct_change': self.latest_signal.get('pct_change', 0),
        }
    
    def _calc_risk_level(self) -> str:
        score = self.total_score
        if score >= 1:
            return "低"
        elif score <= -1:
            return "高"
        return "中"
    
    def _calc_confidence(self) -> float:
        scores = [self.metrics['tech_score'], self.metrics['chip_score'], self.metrics['sentiment_score']]
        positive_count = sum(1 for s in scores if s > 0)
        negative_count = sum(1 for s in scores if s < 0)
        if positive_count >= 2:
            return min(0.95, 0.6 + positive_count * 0.15)
        elif negative_count >= 2:
            return min(0.95, 0.6 + negative_count * 0.15)
        return 0.5
    
    def _generate_reasoning(self) -> str:
        """Phase 2 新增：生成详细文字解读"""
        return self.reasoning_engine.generate_full_reasoning(self.latest_signal, self.financial_data)
    
    def _generate_summary(self) -> str:
        """生成简短总结"""
        msg_map = {
            'Risk-on': '📈 看多：多个维度信号积极，建议持仓或做多。',
            'Risk-off': '📉 看空：多个维度信号消极，建议减仓或止损。',
            'Neutral': '⚖️ 中立：信号混合，建议观望或等待更清晰信号。'
        }
        
        base_msg = msg_map.get(self.market_state, '中立')
        risk_info = f"风险等级：{self.risk_level}，信心度：{self.confidence:.0%}"
        
        if self.warnings:
            warning_info = f"⚠️ 风控预警：{len(self.warnings)} 条规则触发"
            return f"{base_msg} {risk_info} {warning_info}"
        else:
            return f"{base_msg} {risk_info}"
    
    def to_dict(self) -> dict:
        return {
            'symbol': self.symbol,
            'metrics': self.metrics,
            'total_score': self.total_score,
            'market_state': self.market_state,
            'suggestion': self.suggestion,
            'risk_level': self.risk_level,
            'confidence': self.confidence,
            'warnings': self.warnings,
            'detailed_reasoning': self.detailed_reasoning,
            'summary': self.summary,
        }
    
    def __repr__(self) -> str:
        return f"<StockAnalysisReport {self.symbol} score={self.total_score:.2f} state={self.market_state}>"
