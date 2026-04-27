import logging
import pandas as pd

logger = logging.getLogger(__name__)


def _to_scalar_float(value, default: float = 0.0) -> float:
    """将任意输入尽量转换为标量 float，避免 Series/DataFrame 真值歧义。"""
    try:
        if isinstance(value, pd.DataFrame):
            if value.empty:
                return default
            value = value.iloc[-1, -1]
        elif isinstance(value, pd.Series):
            if value.empty:
                return default
            value = value.iloc[-1]

        if isinstance(value, str):
            value = value.replace(',', '').replace('万', '').strip()
            if not value:
                return default

        return float(value)
    except (ValueError, TypeError):
        return default

# Phase 3: 延迟导入 ML 评分器（避免导入循环）
_ensemble_scorer = None

def _get_ensemble_scorer():
    """延迟导入 EnsembleScorer"""
    global _ensemble_scorer
    if _ensemble_scorer is None:
        try:
            from .ml_scoring import EnsembleScorer
            _ensemble_scorer = EnsembleScorer()
        except ImportError:
            # 如果相对导入失败，尝试直接导入
            try:
                from ml_scoring import EnsembleScorer
                _ensemble_scorer = EnsembleScorer()
            except ImportError:
                logger.warning("无法加载 ml_scoring 模块，将使用基础加权方案")
                _ensemble_scorer = False
    return _ensemble_scorer

class StrategyMonitor:
    """
    量化盯盘策略基础监控类
    参考 Backtrader 风格剥离策略逻辑与数据流，使得易于扩展多只股票。
    
    Phase 3 升级：集成 AI 多因子融合评分器
    """
    
    def __init__(self, df: pd.DataFrame, symbol: str, sentiment_score: float = 0.0, fund_data: dict = None):
        self.symbol = symbol
        # 拷贝数据防止篡改原始传入对象
        self.df = df.copy() 
        self.sentiment_score = sentiment_score
        self.fund_data = fund_data or {}
        
        # 检查数据量是否足够计算指标（至少需要20行数据才能计算20日均线等指标）
        if len(self.df) < 20:
            logger.warning(f"{symbol} 数据量只有 {len(self.df)} 行，不足以计算完整技术指标，将使用简化模式")
            # 填充足够行数的 NaN 占位，让后续指标计算不报错
            pass
        
        # Phase 3：延迟初始化 AI 多因子融合器
        self.ensemble_scorer = _get_ensemble_scorer()
        
        self._calculate_indicators()
        self._generate_signals()

    def _calculate_indicators(self):
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
        self.df['pct_change'] = self.df['close'].pct_change()

    def _generate_signals(self):
        """生成交易警告信号及综合得分状态"""
        
        # 将所有含 NaN 的布尔 Series 用 fillna(False) 清洗，避免 pandas 歧义错误
        # （指标的前 N 行由于 rolling 窗口会有 NaN）
        
        # === 基础风控告警 ===
        # 跌破20日均线
        close_above_or_eq_sma_prev = (self.df['close'].shift(1) >= self.df['SMA_20'].shift(1)).fillna(False)
        close_below_sma_curr = (self.df['close'] < self.df['SMA_20']).fillna(False)
        cross_below_sma = close_above_or_eq_sma_prev & close_below_sma_curr
        
        rsi_gt_70 = (self.df['RSI_14'] > 70).fillna(False)
        self.df['sell_warning'] = cross_below_sma & rsi_gt_70
        self.df['unusual_drop_warning'] = (self.df['pct_change'] <= -0.05).fillna(False)
        self.df['any_warning'] = self.df['sell_warning'] | self.df['unusual_drop_warning']
        
        # === Pro版：多维综合评分 ===
        # 1. 技术面得分 (多头排列 + MACD金叉)
        # 多头排列：MA5 > MA10 > MA20
        is_bull_arrangement = ((self.df['SMA_5'] > self.df['SMA_10']) & (self.df['SMA_10'] > self.df['SMA_20'])).fillna(False)
        
        # MACD 金叉：前一日 DIF <= DEA，今日 DIF > DEA 
        macd_cross_up = ((self.df['MACD_DIF'].shift(1) <= self.df['MACD_DEA'].shift(1)) & (self.df['MACD_DIF'] > self.df['MACD_DEA'])).fillna(False)
        
        # 技术面如果多头排列 + MACD大于0，算作看多。如果破位均线则看空。
        # 用一列 tech_score 记录（+1 表示好，-1 表示坏）
        macd_pos = (self.df['MACD_DIF'] > 0).fillna(False)
        close_lt_sma20 = (self.df['close'] < self.df['SMA_20']).fillna(False)
        
        tech_score = pd.Series(0, index=self.df.index)
        tech_score[is_bull_arrangement | macd_cross_up | macd_pos] = 1
        tech_score[close_lt_sma20] = -1
        self.df['tech_score'] = tech_score

        # 结合实时传入的 sentiment_score 和 fund_data 算出最后一天的最终得分
        # (因为舆情和盘中筹码是标量，此处将其作用于最后一天的状态)
        fund_net = _to_scalar_float(self.fund_data.get('主力净流入-净额', 0), default=0.0)

        chip_score = 1.0 if fund_net > 0 else (-1.0 if fund_net < 0 else 0.0)
        sent_sc_raw = _to_scalar_float(self.sentiment_score, default=0.0)
        sent_sc = min(max(sent_sc_raw, -1.0), 1.0)
        
        # 将最新一日的筹码和舆情得分记录下来（初始化为 float 避免类型错误）
        self.df['chip_score'] = 0.0
        self.df['sentiment_score'] = 0.0
        self.df['fundamental_score'] = 0.0
        self.df.iloc[-1, self.df.columns.get_loc('chip_score')] = chip_score
        self.df.iloc[-1, self.df.columns.get_loc('sentiment_score')] = sent_sc
        
        # total_score = tech + chip + sentiment
        self.df['total_score'] = self.df['tech_score'] + self.df['chip_score'] + self.df['sentiment_score']
        
        # 划分状态 (Risk-on 进攻: score >= 1, Neutral 均衡: score == 0, Risk-off 防守: score <= -1)
        def determine_state(score):
            if score >= 1:
                return 'Risk-on'
            elif score <= -1:
                return 'Risk-off'
            return 'Neutral'
            
        self.df['market_state'] = self.df['total_score'].apply(determine_state)
        
        def determine_suggestion(state):
            if state == 'Risk-on':
                return '建议持仓/做多'
            elif state == 'Risk-off':
                return '建议止盈/止损'
            return '建议观望'
            
        self.df['suggestion'] = self.df['market_state'].apply(determine_suggestion)

    def get_signals_df(self) -> pd.DataFrame:
        """返回包含指标和信号的数据表"""
        return self.df

    def get_latest_signal(self) -> dict:
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
        }

def run_monitor_for_stocks(stock_data_dict: dict, extra_data: dict = None) -> (list, list):
    """
    针对多只股票统一执行策略并返回最新警告结果和指标结果。
    参数: 
        stock_data_dict: 键为股票代码, 值为对应股票日线 pd.DataFrame 的字典
        extra_data: {"symbol": {"sentiment": 0.0, "fund_data": {}}, ...}
    返回:
        alerts (list): 仅包含有警告的信号列表
        results (list): 所有股票的最新状态列表
    """
    alerts = []
    results = []
    extra_data = extra_data or {}
    
    for symbol, df in stock_data_dict.items():
        if df is None or df.empty:
            continue
            
        ext = extra_data.get(symbol, {})
        try:
            monitor = StrategyMonitor(df, symbol, 
                                      sentiment_score=ext.get('sentiment', 0.0),
                                      fund_data=ext.get('fund_data', {}))
        except Exception as e:
            logger.error(f"创建 StrategyMonitor ({symbol}) 失败: {e}，跳过此股票")
            continue
        latest_status = monitor.get_latest_signal()
        
        if latest_status:
            results.append(latest_status)
            if latest_status.get("has_warning"):
                alerts.append(latest_status)
                
    return alerts, results
