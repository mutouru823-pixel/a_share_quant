import logging
import pandas as pd

logger = logging.getLogger(__name__)

# Phase 3: 延迟导入 ML 评分器（避免导入路径问题）
_ensemble_scorer = None

def _get_ensemble_scorer():
    """延迟导入并缓存 EnsembleScorer 实例"""
    global _ensemble_scorer
    if _ensemble_scorer is None:
        try:
            from ml_scoring import EnsembleScorer
            _ensemble_scorer = EnsembleScorer()
        except ImportError:
            try:
                from src.ml_scoring import EnsembleScorer
                _ensemble_scorer = EnsembleScorer()
            except ImportError:
                logger.warning("无法加载 ml_scoring 模块，将使用基础加权方案")
                _ensemble_scorer = False
    return _ensemble_scorer


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


class StrategyMonitor:
    """
    量化盯盘策略基础监控类
    参考 Backtrader 风格剥离策略逻辑与数据流，使得易于扩展多只股票。

    Phase 3 升级：集成 AI 多因子融合评分器
    使用标量评分避免 Series 真值歧义问题
    """

    def __init__(self, df: pd.DataFrame, symbol: str, sentiment_score: float = 0.0, fund_data: dict = None):
        self.symbol = symbol
        # 拷贝数据防止篡改原始传入对象
        self.df = df.copy()
        self.sentiment_score = sentiment_score
        self.fund_data = fund_data or {}

        if len(self.df) < 20:
            logger.warning(f"{symbol} 数据量只有 {len(self.df)} 行，无法完整计算技术指标")

        # Phase 3：延迟加载 AI 多因子融合器（避免导入路径问题）
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

        # 4. 当日收盘相较上一日的涨跌幅
        self.df['pct_change'] = self.df['close'].pct_change()

    def _generate_signals(self):
        """
        生成交易警告信号及综合得分状态。

        风控告警使用向量化计算（全 DataFrame），
        多维评分使用标量（仅最新一天），避免 Series 真值歧义。
        """

        # ============================
        # 基础风控告警（向量化计算，fillna 防 NaN）
        # ============================
        # 跌破20日均线
        close_above_or_eq_sma_prev = (self.df['close'].shift(1) >= self.df['SMA_20'].shift(1)).fillna(False)
        close_below_sma_curr = (self.df['close'] < self.df['SMA_20']).fillna(False)
        cross_below_sma = close_above_or_eq_sma_prev & close_below_sma_curr

        rsi_gt_70 = (self.df['RSI_14'] > 70).fillna(False)
        self.df['sell_warning'] = (cross_below_sma & rsi_gt_70).fillna(False)
        self.df['unusual_drop_warning'] = (self.df['pct_change'] <= -0.05).fillna(False)
        self.df['any_warning'] = (self.df['sell_warning'] | self.df['unusual_drop_warning']).fillna(False)

        # ============================
        # 多维评分（标量计算，仅取最新行）
        # ============================
        latest = self.df.iloc[-1]

        # --- 技术面评分 ---
        is_bull = (latest.get('SMA_5', 0) > latest.get('SMA_10', 0) > latest.get('SMA_20', 0))
        macd_positive = latest.get('MACD_DIF', 0) > latest.get('MACD_DEA', 0)
        rsi = latest.get('RSI_14', 50)
        close_price = latest['close']
        sma20 = latest.get('SMA_20', close_price)

        tech_score = 0.0
        if is_bull:
            tech_score += 0.5
        if macd_positive:
            tech_score += 0.3
        if 30 < rsi < 70:
            tech_score += 0.2
        elif rsi < 30:
            tech_score += 0.1
        if close_price < sma20:
            tech_score -= 0.5
        tech_score = max(-1.0, min(1.0, tech_score))

        # --- 筹码面评分 ---
        fund_net = _to_scalar_float(self.fund_data.get('主力净流入-净额', 0), default=0.0)
        if fund_net > 0:
            chip_score = min(1.0, fund_net / 1000.0)
        elif fund_net < 0:
            chip_score = max(-1.0, fund_net / 1000.0)
        else:
            chip_score = 0.0

        # --- 基本面评分（当前为占位） ---
        fundamental_score = 0.0

        # --- 情绪面评分 ---
        sentiment_score = min(max(self.sentiment_score, -1.0), 1.0) if self.sentiment_score != 0 else 0.0

        # --- AI 多因子融合评分 ---
        signal = {
            'tech_score': tech_score,
            'chip_score': chip_score,
            'fundamental_score': fundamental_score,
            'sentiment_score': sentiment_score,
        }
        if self.ensemble_scorer:
            try:
                ensemble_score = self.ensemble_scorer.calculate_ensemble_score(signal)
                logger.info(f"[Phase 3] {self.symbol} AI 多因子评分: {ensemble_score:.2f}")
            except Exception as e:
                logger.warning(f"AI 融合评分失败: {e}，使用加权平均")
                ensemble_score = None
        else:
            ensemble_score = None

        if ensemble_score is None:
            ensemble_score = (
                tech_score * 0.4 +
                chip_score * 0.3 +
                fundamental_score * 0.2 +
                sentiment_score * 0.1
            )

        # 保存评分（标量广播到整个 DataFrame 列）
        self.df['tech_score'] = tech_score
        self.df['chip_score'] = chip_score
        self.df['fundamental_score'] = fundamental_score
        self.df['sentiment_score'] = sentiment_score
        self.df['total_score'] = ensemble_score

        # 判断市场状态
        if ensemble_score >= 0.5:
            state = 'Risk-on'
            suggestion = '建议持仓/做多'
        elif ensemble_score <= -0.5:
            state = 'Risk-off'
            suggestion = '建议止盈/止损'
        else:
            state = 'Neutral'
            suggestion = '建议观望'

        self.df['market_state'] = state
        self.df['suggestion'] = suggestion

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
            "fundamental_score": latest.get('fundamental_score', 0),
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
