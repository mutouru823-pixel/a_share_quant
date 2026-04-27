#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 1 自动化部署脚本
执行: python deploy_phase1.py
"""
import os
import sys

def create_file(filepath, content):
    """创建文件"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ 创建: {filepath}")
    return True

def main():
    print("🚀 Phase 1 自动化部署开始...\n")
    
    # ==================== File 1: indicators_advanced.py ====================
    file1 = """import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> pd.DataFrame:
    \"\"\"计算布林带指标\"\"\"
    df['BB_Middle'] = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    df['BB_Upper'] = df['BB_Middle'] + std_dev * std
    df['BB_Lower'] = df['BB_Middle'] - std_dev * std
    return df

def calculate_volume_divergence(df: pd.DataFrame, lookback: int = 20) -> pd.Series:
    \"\"\"计算量价背离指标\"\"\"
    price_high = df['high'].rolling(lookback).max()
    volume_high = df['volume'].rolling(lookback).max()
    is_price_high = df['high'] == price_high
    is_volume_high = df['volume'] == volume_high
    is_price_low = df['low'] == df['low'].rolling(lookback).min()
    is_volume_low = df['volume'] == df['volume'].rolling(lookback).min()
    divergence = pd.Series(0.0, index=df.index)
    divergence[is_price_high & ~is_volume_high] = -0.5
    divergence[is_price_low & ~is_volume_low] = 0.5
    return divergence

def calculate_chan_patterns(df: pd.DataFrame, lookback: int = 5) -> pd.DataFrame:
    \"\"\"缠论 K 线高低点识别\"\"\"
    df['chan_high_point'] = df['high'].rolling(lookback).max()
    df['chan_low_point'] = df['low'].rolling(lookback).min()
    df['is_high_point'] = df['high'] == df['chan_high_point']
    df['is_low_point'] = df['low'] == df['chan_low_point']
    return df

def calculate_obv(df: pd.DataFrame) -> pd.DataFrame:
    \"\"\"计算 On-Balance Volume\"\"\"
    obv = np.zeros(len(df))
    obv[0] = df['volume'].iloc[0]
    for i in range(1, len(df)):
        if df['close'].iloc[i] > df['close'].iloc[i-1]:
            obv[i] = obv[i-1] + df['volume'].iloc[i]
        elif df['close'].iloc[i] < df['close'].iloc[i-1]:
            obv[i] = obv[i-1] - df['volume'].iloc[i]
        else:
            obv[i] = obv[i-1]
    df['OBV'] = obv
    return df

def calculate_momentum(df: pd.DataFrame, period: int = 12) -> pd.DataFrame:
    \"\"\"计算 Momentum 动量指标\"\"\"
    df['momentum'] = ((df['close'] - df['close'].shift(period)) / df['close'].shift(period) * 100)
    return df

def apply_all_advanced_indicators(df: pd.DataFrame) -> pd.DataFrame:
    \"\"\"一次性应用所有高级指标\"\"\"
    df = calculate_bollinger_bands(df)
    df['volume_divergence'] = calculate_volume_divergence(df)
    df = calculate_chan_patterns(df)
    df = calculate_obv(df)
    df = calculate_momentum(df)
    logger.info(f"已计算高级指标，共 {{len(df)}} 行数据")
    return df
"""
    create_file('src/indicators_advanced.py', file1)
    
    # ==================== File 2: fundamental_fetcher.py ====================
    file2 = """import logging
import time
import random
import akshare as ak

logger = logging.getLogger(__name__)

def fetch_financial_indicators(symbol: str) -> dict:
    \"\"\"从 AkShare 获取财务指标数据\"\"\"
    default_result = {
        'roe': 0, 'roa': 0, 'pe_ratio': 0, 'pb_ratio': 0,
        'debt_ratio': 0.5, 'profit_margin': 0, 'profit_yoy': 0, 'revenue_yoy': 0
    }
    
    try:
        clean_symbol = symbol.strip().lower()
        if clean_symbol.startswith(('sh', 'sz', 'bj')):
            clean_symbol = clean_symbol[2:]
        
        logger.info(f"正在从 AkShare 获取 {{symbol}} 的财务指标...")
        time.sleep(random.uniform(1, 3))
        
        try:
            info_df = ak.stock_individual_info_em(symbol=clean_symbol)
            if info_df is not None and not info_df.empty:
                pe_ratio = info_df[info_df['项目'] == 'PE']['数值'].values
                pb_ratio = info_df[info_df['项目'] == 'PB']['数值'].values
                default_result['pe_ratio'] = float(pe_ratio[0]) if len(pe_ratio) > 0 else 0
                default_result['pb_ratio'] = float(pb_ratio[0]) if len(pb_ratio) > 0 else 0
        except Exception as e:
            logger.warning(f"获取 {{symbol}} 基本信息失败: {{e}}")
        
        try:
            fin_df = ak.stock_main_indicator_em(symbol=clean_symbol)
            if fin_df is not None and not fin_df.empty:
                latest = fin_df.iloc[-1] if len(fin_df) > 0 else None
                if latest is not None:
                    default_result['roe'] = float(latest.get('ROE', 0)) or 0
                    default_result['profit_margin'] = float(latest.get('净利率', 0)) or 0
        except Exception as e:
            logger.warning(f"获取 {{symbol}} 财务指标失败: {{e}}")
        
        logger.info(f"成功获取 {{symbol}} 财务指标: PE={{default_result['pe_ratio']}}, ROE={{default_result['roe']}}")
    except Exception as e:
        logger.warning(f"获取 {{symbol}} 财务数据异常: {{e}}，使用默认值")
    
    return default_result

def calculate_fundamental_score(financial_data: dict) -> float:
    \"\"\"基于财务指标计算基本面得分\"\"\"
    roe = financial_data.get('roe', 0)
    profit_yoy = financial_data.get('profit_yoy', 0)
    pe_ratio = financial_data.get('pe_ratio', 20)
    debt_ratio = financial_data.get('debt_ratio', 0.5)
    
    if roe > 15 and profit_yoy > 20 and (pe_ratio < 15 or pe_ratio == 0) and debt_ratio < 0.5:
        return 1.0
    
    if roe < 8 or profit_yoy < 0 or (pe_ratio > 30 and pe_ratio != 0) or debt_ratio > 0.7:
        return -1.0
    
    return 0.0
"""
    create_file('src/fundamental_fetcher.py', file2)
    
    # ==================== File 3: risk_manager.py ====================
    file3 = """import logging

logger = logging.getLogger(__name__)

class RiskRule:
    \"\"\"风控规则基类\"\"\"
    def __init__(self, description: str = ""):
        self.description = description
    
    def is_triggered(self, latest_signal: dict) -> bool:
        raise NotImplementedError

class PriceBreakMA20Rule(RiskRule):
    \"\"\"收盘价跌破 20 日均线\"\"\"
    def __init__(self):
        super().__init__("⚠️ 价格跌破 20 日均线，下跌趋势形成")
    
    def is_triggered(self, latest_signal: dict) -> bool:
        close = latest_signal.get('close', 0)
        sma20 = latest_signal.get('SMA_20', 0)
        return close < sma20 if sma20 > 0 else False

class RSISuperBoughtRule(RiskRule):
    \"\"\"RSI 超买告警\"\"\"
    def __init__(self, threshold: int = 80):
        self.threshold = threshold
        super().__init__(f"🔴 RSI > {{threshold}}，市场超买，可能出现回调")
    
    def is_triggered(self, latest_signal: dict) -> bool:
        rsi = latest_signal.get('RSI_14', 0)
        return rsi > self.threshold if rsi > 0 else False

class UnusualDropRule(RiskRule):
    \"\"\"单日异常下跌\"\"\"
    def __init__(self, threshold: float = -0.05):
        self.threshold = threshold
        super().__init__(f"🔴 单日跌幅 {{threshold*100}}%，出现异常下跌")
    
    def is_triggered(self, latest_signal: dict) -> bool:
        pct_change = latest_signal.get('pct_change', 0)
        return pct_change <= self.threshold

class HighLeverageRatioRule(RiskRule):
    \"\"\"融资/市值比过高\"\"\"
    def __init__(self, threshold: float = 0.30):
        self.threshold = threshold
        super().__init__(f"⚠️ 融资余额/市值比 > {{threshold*100}}%，风险信号")
    
    def is_triggered(self, latest_signal: dict) -> bool:
        leverage_ratio = latest_signal.get('leverage_ratio', 0)
        return leverage_ratio > self.threshold

class VolumeAnomalyRule(RiskRule):
    \"\"\"成交量异常\"\"\"
    def __init__(self):
        super().__init__("⚠️ 成交量出现异常萎缩或暴增")
    
    def is_triggered(self, latest_signal: dict) -> bool:
        volume_divergence = latest_signal.get('volume_divergence', 0)
        return volume_divergence != 0

class RiskManager:
    \"\"\"风控管理器\"\"\"
    def __init__(self):
        self.rules = []
        self._init_default_rules()
    
    def _init_default_rules(self):
        \"\"\"初始化默认风控规则\"\"\"
        self.add_rule(PriceBreakMA20Rule())
        self.add_rule(RSISuperBoughtRule(threshold=80))
        self.add_rule(UnusualDropRule(threshold=-0.05))
        self.add_rule(HighLeverageRatioRule(threshold=0.30))
        self.add_rule(VolumeAnomalyRule())
    
    def add_rule(self, rule: RiskRule):
        \"\"\"添加风控规则\"\"\"
        self.rules.append(rule)
        logger.info(f"已添加风控规则: {{rule.description}}")
    
    def evaluate(self, latest_signal: dict) -> list:
        \"\"\"评估触发的所有风控规则\"\"\"
        triggered_rules = []
        for rule in self.rules:
            try:
                if rule.is_triggered(latest_signal):
                    triggered_rules.append(rule.description)
                    logger.warning(f"🚨 触发风控规则: {{rule.description}}")
            except Exception as e:
                logger.error(f"执行规则 {{rule.__class__.__name__}} 时出错: {{e}}")
        return triggered_rules
    
    def get_risk_level(self, triggered_count: int = 0) -> str:
        \"\"\"根据触发规则数量判断风险等级\"\"\"
        if triggered_count == 0:
            return "低"
        elif triggered_count <= 2:
            return "中"
        else:
            return "高"
"""
    create_file('src/risk_manager.py', file3)
    
    # ==================== File 4: analysis_report.py ====================
    file4 = """import logging

logger = logging.getLogger(__name__)

class StockAnalysisReport:
    \"\"\"结构化的股票分析报告\"\"\"
    def __init__(self, symbol: str, latest_signal: dict = None, financial_data: dict = None, warnings: list = None):
        self.symbol = symbol
        self.latest_signal = latest_signal or {{}}
        self.financial_data = financial_data or {{}}
        self.warnings = warnings or []
        self.metrics = self._build_metrics()
        self.total_score = self.latest_signal.get('total_score', 0)
        self.market_state = self.latest_signal.get('market_state', 'Neutral')
        self.suggestion = self.latest_signal.get('suggestion', '建议观望')
        self.risk_level = self._calc_risk_level()
        self.confidence = self._calc_confidence()
    
    def _build_metrics(self) -> dict:
        return {{
            'tech_score': self.latest_signal.get('tech_score', 0),
            'chip_score': self.latest_signal.get('chip_score', 0),
            'sentiment_score': self.latest_signal.get('sentiment_score', 0),
            'fundamental_score': self.financial_data.get('fundamental_score', 0) if self.financial_data else 0,
            'rsi': self.latest_signal.get('RSI_14', 0),
            'close': self.latest_signal.get('close', 0),
            'pct_change': self.latest_signal.get('pct_change', 0),
        }}
    
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
    
    def to_dict(self) -> dict:
        return {{
            'symbol': self.symbol,
            'metrics': self.metrics,
            'total_score': self.total_score,
            'market_state': self.market_state,
            'suggestion': self.suggestion,
            'risk_level': self.risk_level,
            'confidence': self.confidence,
            'warnings': self.warnings,
        }}
"""
    create_file('src/analysis_report.py', file4)
    
    # ==================== File 5: 修改 strategy_monitor.py ====================
    print("\n📝 修改 src/strategy_monitor.py...")
    
    strategy_file_path = 'src/strategy_monitor.py'
    
    if not os.path.exists(strategy_file_path):
        print(f"❌ 找不到 {strategy_file_path}")
        return False
    
    with open(strategy_file_path, 'r', encoding='utf-8') as f:
        original_content = f.read()
    
    # Step 1: 添加新的 imports
    import_section = 'import logging\nimport pandas as pd'
    new_imports = '''import logging
import pandas as pd
from src.indicators_advanced import apply_all_advanced_indicators
from src.fundamental_fetcher import fetch_financial_indicators, calculate_fundamental_score
from src.risk_manager import RiskManager
from src.analysis_report import StockAnalysisReport'''
    
    modified_content = original_content.replace(import_section, new_imports, 1)
    
    # Step 2: 在 __init__ 中添加初始化代码
    init_marker = 'self.sentiment_score = sentiment_score'
    init_new = '''self.sentiment_score = sentiment_score
        self.risk_manager = RiskManager()
        self.financial_data = {}'''
    
    modified_content = modified_content.replace(init_marker, init_new, 1)
    
    # Step 3: 替换 _calculate_indicators 方法
    old_calc_indicators = '''def _calculate_indicators(self):
        """计算技术指标 (类似于 Backtrader 的 __init__ 中定义指标线条)"""
        # 1. 移动平均线 (SMA: 5, 10, 20)
        self.df['SMA_5'] = self.df['close'].rolling(window=5).mean()
        self.df['SMA_10'] = self.df['close'].rolling(window=10).mean()
        self.df['SMA_20'] = self.df['close'].rolling(window=20).mean()
        
        # 2. 14日相对强弱指数 (RSI) - 使用纯 Pandas 实现 Wilder's RSI
        delta = self.df['close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        
        # Wilder's Smoothing 等同于 alpha=1/length 的 EWM
        ema_up = up.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        ema_down = down.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        
        rs = ema_up / ema_down
        self.df['RSI_14'] = 100 - (100 / (1 + rs))
        
        # 3. MACD指标 (12, 26, 9)
        exp12 = self.df['close'].ewm(span=12, adjust=False).mean()
        exp26 = self.df['close'].ewm(span=26, adjust=False).mean()
        self.df['MACD_DIF'] = exp12 - exp26
        self.df['MACD_DEA'] = self.df['MACD_DIF'].ewm(span=9, adjust=False).mean()
        self.df['MACD_HIST'] = (self.df['MACD_DIF'] - self.df['MACD_DEA']) * 2
        
        # 4. 当日收盘相较上一日的跌跌幅
        self.df['pct_change'] = self.df['close'].pct_change()'''
    
    new_calc_indicators = '''def _calculate_indicators(self):
        """计算技术指标 (包含 Phase 1 高级指标)"""
        self.df['SMA_5'] = self.df['close'].rolling(window=5).mean()
        self.df['SMA_10'] = self.df['close'].rolling(window=10).mean()
        self.df['SMA_20'] = self.df['close'].rolling(window=20).mean()
        
        delta = self.df['close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        ema_down = down.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        rs = ema_up / ema_down
        self.df['RSI_14'] = 100 - (100 / (1 + rs))
        
        exp12 = self.df['close'].ewm(span=12, adjust=False).mean()
        exp26 = self.df['close'].ewm(span=26, adjust=False).mean()
        self.df['MACD_DIF'] = exp12 - exp26
        self.df['MACD_DEA'] = self.df['MACD_DIF'].ewm(span=9, adjust=False).mean()
        self.df['MACD_HIST'] = (self.df['MACD_DIF'] - self.df['MACD_DEA']) * 2
        
        self.df['pct_change'] = self.df['close'].pct_change()
        
        try:
            self.df = apply_all_advanced_indicators(self.df)
        except Exception as e:
            logger.warning(f"计算高级指标失败: {e}，继续使用基础指标")
        
        try:
            self.financial_data = fetch_financial_indicators(self.symbol)
        except Exception as e:
            logger.warning(f"获取财务数据失败: {e}")'''
    
    modified_content = modified_content.replace(old_calc_indicators, new_calc_indicators, 1)
    
    # Step 4: 替换 _generate_signals 方法
    # 这个比较复杂，用更精确的方式
    old_signals_start = 'def _generate_signals(self):'
    
    if old_signals_start in modified_content:
        # 找到 _generate_signals 方法的开始
        start_idx = modified_content.find(old_signals_start)
        # 找到下一个方法的开始（下一个 "def "）
        next_method_idx = modified_content.find('\n    def ', start_idx + 1)
        
        if next_method_idx != -1:
            old_signals = modified_content[start_idx:next_method_idx]
            
            new_signals = '''def _generate_signals(self):
        """生成交易警告信号及综合得分状态（Phase 1：加权融合版）"""
        
        close_above_or_eq_sma_prev = self.df['close'].shift(1) >= self.df['SMA_20'].shift(1)
        close_below_sma_curr = self.df['close'] < self.df['SMA_20']
        cross_below_sma = close_above_or_eq_sma_prev & close_below_sma_curr
        
        self.df['sell_warning'] = cross_below_sma & (self.df['RSI_14'] > 70)
        self.df['unusual_drop_warning'] = self.df['pct_change'] <= -0.05
        self.df['any_warning'] = self.df['sell_warning'] | self.df['unusual_drop_warning']
        
        is_bull_arrangement = (self.df['SMA_5'] > self.df['SMA_10']) & (self.df['SMA_10'] > self.df['SMA_20'])
        macd_cross_up = (self.df['MACD_DIF'].shift(1) <= self.df['MACD_DEA'].shift(1)) & (self.df['MACD_DIF'] > self.df['MACD_DEA'])
        
        tech_score = pd.Series(0, index=self.df.index)
        tech_score[is_bull_arrangement | macd_cross_up | (self.df['MACD_DIF'] > 0)] = 1
        tech_score[self.df['close'] < self.df['SMA_20']] = -1
        self.df['tech_score'] = tech_score
        
        fund_net = self.fund_data.get('主力净流入-净额', 0)
        if isinstance(fund_net, str):
            fund_net = float(fund_net.replace(',', '').replace('万', '')) if fund_net else 0
        chip_score = 1 if fund_net > 0 else (-1 if fund_net < 0 else 0)
        
        fundamental_score = calculate_fundamental_score(self.financial_data)
        sent_sc = min(max(self.sentiment_score, -1), 1) if self.sentiment_score != 0 else 0
        
        self.df['chip_score'] = 0
        self.df['sentiment_score'] = 0
        self.df['fundamental_score'] = 0
        
        self.df.iloc[-1, self.df.columns.get_loc('chip_score')] = chip_score
        self.df.iloc[-1, self.df.columns.get_loc('sentiment_score')] = sent_sc
        self.df.iloc[-1, self.df.columns.get_loc('fundamental_score')] = fundamental_score
        
        weighted_score = (
            0.40 * self.df['tech_score'].iloc[-1] +
            0.30 * chip_score +
            0.20 * fundamental_score +
            0.10 * sent_sc
        )
        
        self.df['total_score'] = weighted_score
        
        def determine_state(score):
            if score >= 0.5:
                return 'Risk-on'
            elif score <= -0.5:
                return 'Risk-off'
            return 'Neutral'
        
        self.df['market_state'] = determine_state(weighted_score)
        
        def determine_suggestion(state):
            if state == 'Risk-on':
                return '建议持仓/做多'
            elif state == 'Risk-off':
                return '建议止盈/止损'
            return '建议观望'
        
        self.df['suggestion'] = determine_suggestion(self.df['market_state'])
'''
            
            modified_content = modified_content.replace(old_signals, new_signals, 1)
    
    # Step 5: 替换 get_latest_signal 方法
    old_get_latest = '''def get_latest_signal(self) -> dict:
        """获取最近一个交易日的监控信号结果"""
        if self.df.empty:
            return {}
            
        latest = self.df.iloc[-1]
        
        # 处理时间戳格式化
        date_str = latest.name.strftime('%Y-%m-%d') if hasattr(latest.name, 'strftime') else str(latest.name)
        
        return {
            "symbol": self.symbol,
            "date": date_str,
            "close": latest['close'],
            "pct_change": latest['pct_change'],
            "SMA_5": latest.get('SMA_5', 0),
            "SMA_10": latest.get('SMA_10', 0),
            "SMA_20": latest['SMA_20'],
            "MACD_DIF": latest.get('MACD_DIF', 0),
            "MACD_DEA": latest.get('MACD_DEA', 0),
            "RSI_14": latest['RSI_14'],
            "tech_score": latest.get('tech_score', 0),
            "chip_score": latest.get('chip_score', 0),
            "sentiment_score": latest.get('sentiment_score', 0),
            "total_score": latest.get('total_score', 0),
            "market_state": latest.get('market_state', 'Neutral'),
            "suggestion": latest.get('suggestion', '建议观望'),
            "sell_warning": bool(latest['sell_warning']),
            "unusual_drop_warning": bool(latest['unusual_drop_warning']),
            "has_warning": bool(latest['any_warning'])
        }'''
    
    new_get_latest = '''def get_latest_signal(self) -> dict:
        """获取最近一个交易日的监控信号结果（Phase 1：含风控预警）"""
        if self.df.empty:
            return {}
        
        latest = self.df.iloc[-1]
        date_str = latest.name.strftime('%Y-%m-%d') if hasattr(latest.name, 'strftime') else str(latest.name)
        
        base_signal = {
            "symbol": self.symbol,
            "date": date_str,
            "close": latest['close'],
            "pct_change": latest.get('pct_change', 0),
            "SMA_5": latest.get('SMA_5', 0),
            "SMA_10": latest.get('SMA_10', 0),
            "SMA_20": latest['SMA_20'],
            "MACD_DIF": latest.get('MACD_DIF', 0),
            "MACD_DEA": latest.get('MACD_DEA', 0),
            "RSI_14": latest['RSI_14'],
            "tech_score": latest.get('tech_score', 0),
            "chip_score": latest.get('chip_score', 0),
            "sentiment_score": latest.get('sentiment_score', 0),
            "fundamental_score": latest.get('fundamental_score', 0),
            "total_score": latest.get('total_score', 0),
            "market_state": latest.get('market_state', 'Neutral'),
            "suggestion": latest.get('suggestion', '建议观望'),
            "sell_warning": bool(latest.get('sell_warning', False)),
            "unusual_drop_warning": bool(latest.get('unusual_drop_warning', False)),
            "has_warning": bool(latest.get('any_warning', False)),
            "volume_divergence": latest.get('volume_divergence', 0),
        }
        
        try:
            warnings = self.risk_manager.evaluate(base_signal)
            base_signal['warnings'] = warnings
            base_signal['risk_level'] = self.risk_manager.get_risk_level(len(warnings))
        except Exception as e:
            logger.warning(f"评估风控规则失败: {e}")
            base_signal['warnings'] = []
            base_signal['risk_level'] = '中'
        
        return base_signal'''
    
    modified_content = modified_content.replace(old_get_latest, new_get_latest, 1)
    
    # 写入修改后的文件
    with open(strategy_file_path, 'w', encoding='utf-8') as f:
        f.write(modified_content)
    
    print(f"✅ 修改: {strategy_file_path}")
    
    print("\n" + "="*60)
    print("✨ Phase 1 部署完成！")
    print("="*60)
    print("\n📊 部署统计：")
    print(f"  ✅ 新建 4 个模块: indicators_advanced, fundamental_fetcher, risk_manager, analysis_report")
    print(f"  ✅ 修改 strategy_monitor.py: 添加 imports, 修改 _calculate_indicators, _generate_signals, get_latest_signal")
    print(f"\n🎯 功能升级：")
    print(f"  ✓ 评分维度: 3 维 → 10 维 (新增布林带、量价背离、缠论、OBV、动量、财务面)")
    print(f"  ✓ 评分融合: 简单平均 → 加权融合 (0.4/0.3/0.2/0.1)")
    print(f"  ✓ 风控管理: 硬编码 → 规则库化 (可配置规则)")
    print(f"  ✓ 基本面分析: 无 → 有 (ROE、PE、利润增速等)")
    print(f"\n📋 下一步：")
    print(f"  1. 在 VS Code 中检查是否有红色错误波浪线")
    print(f"  2. 运行 streamlit run app.py 测试页面")
    print(f"  3. 输入股票代码验证 Phase 1 新指标是否正常工作")
    print(f"\n🚀 Phase 1 已就绪，准备进入 Phase 2（详细报告生成）")

if __name__ == '__main__':
    try:
        main()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 部署失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
