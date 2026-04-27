import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class RiskRule(ABC):
    """风控规则基类"""
    
    @abstractmethod
    def is_triggered(self, signal: dict) -> bool:
        """检查规则是否被触发"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """规则描述"""
        pass

class PriceBreakMA20Rule(RiskRule):
    """破位20日均线规则"""
    
    def is_triggered(self, signal: dict) -> bool:
        return signal.get('close', 0) < signal.get('SMA_20', float('inf'))
    
    @property
    def description(self) -> str:
        return "⚠️ 价格跌破20日均线，技术面转弱"

class RSISuperBoughtRule(RiskRule):
    """RSI 超买规则"""
    
    def __init__(self, threshold: float = 80):
        self.threshold = threshold
    
    def is_triggered(self, signal: dict) -> bool:
        rsi = signal.get('RSI_14', 0)
        return rsi > self.threshold
    
    @property
    def description(self) -> str:
        return f"⚠️ RSI 超买状态 (>80)，存在回调风险"

class UnusualDropRule(RiskRule):
    """异常下跌规则"""
    
    def __init__(self, threshold: float = -5):
        self.threshold = threshold
    
    def is_triggered(self, signal: dict) -> bool:
        pct_change = signal.get('pct_change', 0)
        return pct_change < self.threshold / 100
    
    @property
    def description(self) -> str:
        return f"🔴 当日跌幅超过 {abs(self.threshold)}%，异常下跌"

class HighLeverageRatioRule(RiskRule):
    """融资融券比例过高"""
    
    def __init__(self, threshold: float = 30):
        self.threshold = threshold
    
    def is_triggered(self, signal: dict) -> bool:
        # 这里可以集成融资融券数据
        return False
    
    @property
    def description(self) -> str:
        return f"⚠️ 融资融券比例过高，市场风险增加"

class VolumeAnomalyRule(RiskRule):
    """成交量异常规则"""
    
    def is_triggered(self, signal: dict) -> bool:
        # 这里可以集成成交量数据
        return False
    
    @property
    def description(self) -> str:
        return "⚠️ 成交量异常萎缩或剧增，市场流动性风险"

class RiskManager:
    """风控管理器"""
    
    def __init__(self):
        self.rules = [
            PriceBreakMA20Rule(),
            RSISuperBoughtRule(threshold=80),
            UnusualDropRule(threshold=-5),
            HighLeverageRatioRule(threshold=30),
            VolumeAnomalyRule(),
        ]
    
    def evaluate(self, signal: dict) -> list:
        """评估风控，返回触发的规则列表"""
        triggered_rules = []
        for rule in self.rules:
            try:
                if rule.is_triggered(signal):
                    triggered_rules.append(rule.description)
            except Exception as e:
                logger.warning(f"规则 {rule.__class__.__name__} 执行出错: {e}")
        
        return triggered_rules
    
    def get_risk_level(self, signal: dict) -> str:
        """获取风险等级"""
        warnings = self.evaluate(signal)
        
        if len(warnings) >= 3:
            return "高"
        elif len(warnings) >= 1:
            return "中"
        return "低"
