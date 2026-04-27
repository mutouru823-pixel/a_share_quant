import logging

logger = logging.getLogger(__name__)

class StockAnalysisReport:
    """股票分析报告"""
    
    def __init__(self, symbol: str, latest_signal: dict, financial_data: dict = None, warnings: list = None):
        self.symbol = symbol
        self.latest_signal = latest_signal or {}
        self.financial_data = financial_data or {}
        self.warnings = warnings or []
        
        self.metrics = self._build_metrics()
        self.total_score = self.latest_signal.get('total_score', 0)
        self.market_state = self.latest_signal.get('market_state', 'Neutral')
        self.risk_level = self._calc_risk_level()
        self.confidence = self._calc_confidence()
        self.summary = self._generate_summary()
        self.detailed_reasoning = self._generate_reasoning()
    
    def _build_metrics(self) -> dict:
        """构建评分指标"""
        return {
            'tech_score': self.latest_signal.get('tech_score', 0),
            'chip_score': self.latest_signal.get('chip_score', 0),
            'fundamental_score': self.latest_signal.get('fundamental_score', 0),
            'sentiment_score': self.latest_signal.get('sentiment_score', 0),
            'RSI': self.latest_signal.get('RSI_14', 50),
            'close': self.latest_signal.get('close', 0),
            'pct_change': self.latest_signal.get('pct_change', 0),
        }
    
    def _calc_risk_level(self) -> str:
        """计算风险等级"""
        if len(self.warnings) >= 3:
            return "高"
        elif len(self.warnings) >= 1:
            return "中"
        return "低"
    
    def _calc_confidence(self) -> float:
        """计算信心度"""
        # 基于评分和风险的综合计算
        base_conf = (self.total_score + 1.0) / 2.0  # 归一化到 0-1
        risk_penalty = len(self.warnings) * 0.1
        confidence = max(0.0, min(1.0, base_conf - risk_penalty))
        return confidence
    
    def _generate_summary(self) -> str:
        """生成摘要"""
        if self.total_score > 0.5:
            return f"看多信号。综合评分 {self.total_score:.2f}，建议关注"
        elif self.total_score < -0.5:
            return f"看空信号。综合评分 {self.total_score:.2f}，建议规避"
        else:
            return f"中立信号。综合评分 {self.total_score:.2f}，建议观望"
    
    def _generate_reasoning(self) -> str:
        """生成详细分析文字"""
        text = f"### 📊 {self.symbol} 分析报告\n\n"
        
        text += f"**综合评分**: {self.total_score:+.2f}\n"
        text += f"**市场状态**: {self.market_state}\n"
        text += f"**风险等级**: {self.risk_level}\n\n"
        
        text += "**多维评分分析**:\n"
        text += f"- 📈 技术面: {self.metrics['tech_score']:+.1f} - "
        if self.metrics['tech_score'] > 0:
            text += "技术面向好，均线排列看多\n"
        else:
            text += "技术面走弱，需要谨慎\n"
        
        text += f"- 💰 筹码面: {self.metrics['chip_score']:+.1f} - "
        if self.metrics['chip_score'] > 0:
            text += "主力净流入，机构看好\n"
        else:
            text += "主力净流出，需要关注\n"
        
        text += f"- 📋 基本面: {self.metrics['fundamental_score']:+.1f} - "
        if self.metrics['fundamental_score'] > 0:
            text += "基本面良好，业绩稳定\n"
        else:
            text += "基本面一般，需要改善\n"
        
        text += f"- 📰 情绪面: {self.metrics['sentiment_score']:+.1f} - "
        if self.metrics['sentiment_score'] > 0:
            text += "舆情积极，市场看多\n"
        else:
            text += "舆情消极，需要观察\n"
        
        return text
    
    def to_dict(self) -> dict:
        """导出为字典"""
        return {
            'symbol': self.symbol,
            'metrics': self.metrics,
            'total_score': self.total_score,
            'market_state': self.market_state,
            'risk_level': self.risk_level,
            'confidence': self.confidence,
            'summary': self.summary,
            'detailed_reasoning': self.detailed_reasoning,
            'warnings': self.warnings,
        }
