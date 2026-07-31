# -*- coding: utf-8 -*-
"""
策略监控引擎 v2
- 集成全部技术指标（SMA/EMA/RSI/MACD/布林线/OBV/动量/量价背离）
- 连续评分系统（-100 ~ +100）替代离散 -1/0/+1
- 内嵌风控规则引擎
- 置信度评估
- 仓位建议
"""
import logging
import numpy as np
import pandas as pd
from typing import Optional

logger = logging.getLogger(__name__)


class StrategyMonitorV2:
    """
    多维量化策略监控器 v2
    评分体系：技术面(50%) + 量价面(25%) + 资金面(15%) + 舆情面(10%)
    输出：连续综合评分(-100~+100)、置信度(0~1)、建议仓位(0~100%)
    """

    # 各维度权重
    WEIGHTS = {
        "technical": 0.50,
        "volume_price": 0.25,
        "fund_flow": 0.15,
        "sentiment": 0.10,
    }

    def __init__(self, df: pd.DataFrame, symbol: str,
                 sentiment_score: float = 0.0,
                 fund_data: dict = None,
                 realtime_data: dict = None):
        self.symbol = symbol
        self.df = df.copy()
        self.sentiment_score = sentiment_score
        self.fund_data = fund_data or {}
        self.realtime_data = realtime_data or {}

        self._calculate_all_indicators()
        self._calculate_scores()
        self._apply_risk_rules()

    # ==================== 指标计算 ====================

    def _calculate_all_indicators(self):
        """计算全部技术指标"""
        df = self.df

        # --- 均线系统 ---
        df["SMA_5"] = df["close"].rolling(5).mean()
        df["SMA_10"] = df["close"].rolling(10).mean()
        df["SMA_20"] = df["close"].rolling(20).mean()
        df["SMA_60"] = df["close"].rolling(60).mean()
        df["EMA_12"] = df["close"].ewm(span=12, adjust=False).mean()
        df["EMA_26"] = df["close"].ewm(span=26, adjust=False).mean()

        # --- RSI (Wilder's) ---
        delta = df["close"].diff()
        up = delta.clip(lower=0)
        down = -delta.clip(upper=0)
        ema_up = up.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        ema_down = down.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        rs = ema_up / ema_down.replace(0, np.nan)
        df["RSI_14"] = 100 - (100 / (1 + rs))
        df["RSI_14"] = df["RSI_14"].fillna(50)

        # --- MACD ---
        df["MACD_DIF"] = df["EMA_12"] - df["EMA_26"]
        df["MACD_DEA"] = df["MACD_DIF"].ewm(span=9, adjust=False).mean()
        df["MACD_HIST"] = (df["MACD_DIF"] - df["MACD_DEA"]) * 2

        # --- 布林线 (20, 2) ---
        bb_mid = df["close"].rolling(20).mean()
        bb_std = df["close"].rolling(20).std()
        df["BB_Upper"] = bb_mid + 2 * bb_std
        df["BB_Middle"] = bb_mid
        df["BB_Lower"] = bb_mid - 2 * bb_std
        df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / df["BB_Middle"]
        # %B 指标：价格在布林带中的位置 (0=下轨, 1=上轨)
        df["BB_PctB"] = (df["close"] - df["BB_Lower"]) / (df["BB_Upper"] - df["BB_Lower"]).replace(0, np.nan)
        df["BB_PctB"] = df["BB_PctB"].fillna(0.5)

        # --- OBV (能量潮) ---
        obv = [0.0]
        for i in range(1, len(df)):
            if df["close"].iloc[i] > df["close"].iloc[i - 1]:
                obv.append(obv[-1] + df["volume"].iloc[i])
            elif df["close"].iloc[i] < df["close"].iloc[i - 1]:
                obv.append(obv[-1] - df["volume"].iloc[i])
            else:
                obv.append(obv[-1])
        df["OBV"] = obv
        df["OBV_MA20"] = df["OBV"].rolling(20).mean()

        # --- 动量 (ROC) ---
        df["Momentum_12"] = df["close"].pct_change(12) * 100
        df["Momentum_5"] = df["close"].pct_change(5) * 100

        # --- 成交量分析 ---
        df["VOL_MA5"] = df["volume"].rolling(5).mean()
        df["VOL_MA20"] = df["volume"].rolling(20).mean()
        df["VOL_Ratio"] = df["volume"] / df["VOL_MA20"].replace(0, np.nan)
        df["VOL_Ratio"] = df["VOL_Ratio"].fillna(1.0)

        # --- ATR (平均真实波幅) ---
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift(1)).abs()
        low_close = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["ATR_14"] = tr.rolling(14).mean()

        # --- 涨跌幅 ---
        df["pct_change"] = df["close"].pct_change()

        # --- KDJ ---
        low_9 = df["low"].rolling(9).min()
        high_9 = df["high"].rolling(9).max()
        rsv = (df["close"] - low_9) / (high_9 - low_9).replace(0, np.nan) * 100
        rsv = rsv.fillna(50)
        df["KDJ_K"] = rsv.ewm(com=2, adjust=False).mean()
        df["KDJ_D"] = df["KDJ_K"].ewm(com=2, adjust=False).mean()
        df["KDJ_J"] = 3 * df["KDJ_K"] - 2 * df["KDJ_D"]

    # ==================== 评分系统 ====================

    def _calculate_scores(self):
        """计算多维度连续评分"""
        df = self.df
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        # === 1. 技术面评分 (-100 ~ +100) ===
        tech_score = 0.0

        # 均线排列 (权重 25)
        if latest["SMA_5"] > latest["SMA_10"] > latest["SMA_20"]:
            tech_score += 25  # 多头排列
            if len(df) > 60 and latest["SMA_20"] > latest["SMA_60"]:
                tech_score += 5  # 长期多头加分
        elif latest["SMA_5"] < latest["SMA_10"] < latest["SMA_20"]:
            tech_score -= 25  # 空头排列
            if len(df) > 60 and latest["SMA_20"] < latest["SMA_60"]:
                tech_score -= 5

        # 价格与均线关系 (权重 15)
        if latest["close"] > latest["SMA_20"]:
            dist = (latest["close"] - latest["SMA_20"]) / latest["SMA_20"]
            tech_score += min(15, dist * 100)
        else:
            dist = (latest["SMA_20"] - latest["close"]) / latest["SMA_20"]
            tech_score -= min(15, dist * 100)

        # MACD (权重 20)
        if latest["MACD_DIF"] > latest["MACD_DEA"]:
            tech_score += 10
            # 金叉刚发生加分
            if prev["MACD_DIF"] <= prev["MACD_DEA"]:
                tech_score += 10
        else:
            tech_score -= 10
            if prev["MACD_DIF"] >= prev["MACD_DEA"]:
                tech_score -= 10  # 死叉刚发生

        # MACD 柱状图趋势
        if latest["MACD_HIST"] > 0 and latest["MACD_HIST"] > prev["MACD_HIST"]:
            tech_score += 5  # 红柱放大
        elif latest["MACD_HIST"] < 0 and latest["MACD_HIST"] < prev["MACD_HIST"]:
            tech_score -= 5  # 绿柱放大

        # RSI (权重 15)
        rsi = latest["RSI_14"]
        if rsi > 80:
            tech_score -= 10  # 极度超买
        elif rsi > 70:
            tech_score -= 5
        elif rsi < 20:
            tech_score += 10  # 极度超卖（反弹机会）
        elif rsi < 30:
            tech_score += 5
        elif 40 <= rsi <= 60:
            tech_score += 2  # 中性偏稳

        # KDJ (权重 10)
        if latest["KDJ_J"] > 100:
            tech_score -= 5  # 超买
        elif latest["KDJ_J"] < 0:
            tech_score += 5  # 超卖
        if latest["KDJ_K"] > latest["KDJ_D"] and prev["KDJ_K"] <= prev["KDJ_D"]:
            tech_score += 5  # KDJ金叉

        # 布林带位置 (权重 10)
        pctb = latest["BB_PctB"]
        if pctb > 0.95:
            tech_score -= 5  # 触及上轨，回调风险
        elif pctb < 0.05:
            tech_score += 5  # 触及下轨，反弹机会
        elif 0.4 <= pctb <= 0.6:
            tech_score += 2

        # 动量 (权重 5)
        if latest["Momentum_5"] > 3:
            tech_score += 5
        elif latest["Momentum_5"] < -3:
            tech_score -= 5

        self._tech_score = max(-100, min(100, tech_score))

        # === 2. 量价面评分 (-100 ~ +100) ===
        vol_score = 0.0

        # 量比分析
        vol_ratio = latest["VOL_Ratio"]
        pct = latest.get("pct_change", 0)
        if pd.isna(pct):
            pct = 0

        if pct > 0 and vol_ratio > 1.5:
            vol_score += 30  # 放量上涨，强势
        elif pct > 0 and vol_ratio > 1.0:
            vol_score += 15  # 温和放量上涨
        elif pct < 0 and vol_ratio > 2.0:
            vol_score -= 30  # 放量下跌，恐慌
        elif pct < 0 and vol_ratio > 1.5:
            vol_score -= 20
        elif pct < 0 and vol_ratio < 0.7:
            vol_score += 10  # 缩量下跌，抛压减轻

        # OBV 趋势
        if not pd.isna(latest["OBV_MA20"]):
            if latest["OBV"] > latest["OBV_MA20"]:
                vol_score += 20  # OBV在均线上方，资金流入
            else:
                vol_score -= 20

        # 量价背离检测
        if len(df) >= 10:
            recent_5 = df.tail(5)
            price_up = recent_5["close"].iloc[-1] > recent_5["close"].iloc[0]
            vol_down = recent_5["volume"].mean() < df["volume"].iloc[-10:-5].mean() * 0.7
            if price_up and vol_down:
                vol_score -= 15  # 顶背离：价涨量缩
            elif not price_up and not vol_down:
                vol_score += 10  # 底背离：价跌量增（可能见底）

        # ATR 波动率评估
        if not pd.isna(latest["ATR_14"]) and latest["ATR_14"] > 0:
            atr_pct = latest["ATR_14"] / latest["close"] * 100
            if atr_pct > 5:
                vol_score -= 10  # 波动过大，风险高
            elif atr_pct < 1.5:
                vol_score += 5   # 波动小，走势平稳

        self._vol_score = max(-100, min(100, vol_score))

        # === 3. 资金面评分 (-100 ~ +100) ===
        fund_score = 0.0

        main_net = self.fund_data.get("main_net_inflow", 0)
        if isinstance(main_net, str):
            main_net = float(main_net.replace(",", "")) if main_net else 0

        if main_net > 0:
            # 按净流入金额分级
            if main_net > 5e8:      # >5亿
                fund_score += 50
            elif main_net > 1e8:    # >1亿
                fund_score += 30
            elif main_net > 3e7:    # >3000万
                fund_score += 15
            else:
                fund_score += 5
        elif main_net < 0:
            if main_net < -5e8:
                fund_score -= 50
            elif main_net < -1e8:
                fund_score -= 30
            elif main_net < -3e7:
                fund_score -= 15
            else:
                fund_score -= 5

        # 超大单占比
        super_large = self.fund_data.get("super_large_net_inflow", 0)
        if isinstance(super_large, (int, float)) and super_large > 0:
            fund_score += 10  # 机构在买

        self._fund_score = max(-100, min(100, fund_score))

        # === 4. 舆情面评分 (-100 ~ +100) ===
        # sentiment_score 输入范围 [-3, 3]，映射到 [-100, 100]
        sent_normalized = max(-3, min(3, self.sentiment_score))
        self._sent_score = sent_normalized / 3.0 * 100

        # === 综合加权评分 ===
        self._total_score = (
            self._tech_score * self.WEIGHTS["technical"] +
            self._vol_score * self.WEIGHTS["volume_price"] +
            self._fund_score * self.WEIGHTS["fund_flow"] +
            self._sent_score * self.WEIGHTS["sentiment"]
        )

        # === 置信度评估 ===
        self._confidence = self._calculate_confidence()

        # === 仓位建议 ===
        self._position = self._calculate_position()

        # === 市场状态判定 ===
        if self._total_score >= 30:
            self._market_state = "强势看多"
            self._suggestion = "建议持仓/加仓"
        elif self._total_score >= 10:
            self._market_state = "偏多震荡"
            self._suggestion = "建议轻仓持有"
        elif self._total_score > -10:
            self._market_state = "中性观望"
            self._suggestion = "建议观望等待"
        elif self._total_score > -30:
            self._market_state = "偏空震荡"
            self._suggestion = "建议减仓防守"
        else:
            self._market_state = "强势看空"
            self._suggestion = "建议清仓/止损"

    def _calculate_confidence(self) -> float:
        """
        置信度评估 (0~1)
        基于：信号一致性、数据完整度、波动率
        """
        confidence = 0.5  # 基础置信度

        # 1. 多维度信号一致性（各维度同向加分）
        scores = [self._tech_score, self._vol_score, self._fund_score, self._sent_score]
        positive_count = sum(1 for s in scores if s > 10)
        negative_count = sum(1 for s in scores if s < -10)

        if positive_count >= 3 or negative_count >= 3:
            confidence += 0.25  # 高度一致
        elif positive_count >= 2 or negative_count >= 2:
            confidence += 0.1
        elif positive_count >= 1 and negative_count >= 1:
            confidence -= 0.1  # 信号矛盾

        # 2. 数据长度充足
        if len(self.df) >= 120:
            confidence += 0.1
        elif len(self.df) < 60:
            confidence -= 0.1

        # 3. 波动率适中（ATR%在2-4%最可信）
        latest = self.df.iloc[-1]
        if not pd.isna(latest.get("ATR_14", np.nan)) and latest["ATR_14"] > 0:
            atr_pct = latest["ATR_14"] / latest["close"] * 100
            if 1.5 <= atr_pct <= 4:
                confidence += 0.05
            elif atr_pct > 6:
                confidence -= 0.1  # 极端波动降低置信

        return max(0.1, min(0.95, confidence))

    def _calculate_position(self) -> float:
        """
        建议仓位 (0~100%)
        基于评分+置信度+波动率
        """
        if self._total_score <= 0:
            return 0.0

        # 基础仓位 = 评分映射
        base_position = (self._total_score / 100) * 80  # 最高80%

        # 置信度调整
        adjusted = base_position * self._confidence

        # 波动率惩罚
        latest = self.df.iloc[-1]
        if not pd.isna(latest.get("ATR_14", np.nan)) and latest["ATR_14"] > 0:
            atr_pct = latest["ATR_14"] / latest["close"] * 100
            if atr_pct > 4:
                adjusted *= 0.7  # 高波动降低仓位
            elif atr_pct > 6:
                adjusted *= 0.5

        return max(0, min(100, adjusted))

    # ==================== 风控规则 ====================

    def _apply_risk_rules(self):
        """执行风控规则检查"""
        self._warnings = []
        latest = self.df.iloc[-1]
        prev = self.df.iloc[-2] if len(self.df) > 1 else latest

        # 1. 跌破20日均线
        if latest["close"] < latest["SMA_20"] and prev["close"] >= prev["SMA_20"]:
            self._warnings.append("价格跌破20日均线，技术面转弱")

        # 2. 跌破60日均线（中期趋势破坏）
        if not pd.isna(latest["SMA_60"]):
            if latest["close"] < latest["SMA_60"] and prev["close"] >= prev["SMA_60"]:
                self._warnings.append("价格跌破60日均线，中期趋势可能反转")

        # 3. RSI 超买
        if latest["RSI_14"] > 80:
            self._warnings.append(f"RSI={latest['RSI_14']:.1f}，极度超买，回调风险大")
        elif latest["RSI_14"] > 70:
            self._warnings.append(f"RSI={latest['RSI_14']:.1f}，进入超买区间")

        # 4. 异常跌幅
        pct = latest.get("pct_change", 0)
        if pd.isna(pct):
            pct = 0
        if pct <= -0.07:
            self._warnings.append(f"当日暴跌 {pct*100:.1f}%，疑似重大利空")
        elif pct <= -0.05:
            self._warnings.append(f"当日大跌 {pct*100:.1f}%，注意风险")

        # 5. 布林带突破
        if latest["close"] > latest["BB_Upper"]:
            self._warnings.append("价格突破布林线上轨，短期过热")
        elif latest["close"] < latest["BB_Lower"]:
            self._warnings.append("价格跌破布林线下轨，可能超跌")

        # 6. 放量滞涨（顶部信号）
        if latest["VOL_Ratio"] > 2.0 and abs(pct) < 0.01:
            self._warnings.append("成交量异常放大但价格滞涨，警惕主力出货")

        # 7. 连续下跌
        if len(self.df) >= 5:
            recent_5_pct = self.df["pct_change"].tail(5)
            if (recent_5_pct < 0).sum() >= 4:
                self._warnings.append("近5日中4日以上下跌，空头趋势明确")

        # 8. MACD 顶背离
        if len(self.df) >= 20:
            recent_high = self.df["close"].tail(10).max()
            prev_high = self.df["close"].iloc[-20:-10].max()
            recent_dif = self.df["MACD_DIF"].tail(10).max()
            prev_dif = self.df["MACD_DIF"].iloc[-20:-10].max()
            if recent_high > prev_high and recent_dif < prev_dif:
                self._warnings.append("MACD顶背离：价格新高但DIF未新高，上涨动能衰竭")

        # 风险等级
        if len(self._warnings) >= 4:
            self._risk_level = "极高"
        elif len(self._warnings) >= 2:
            self._risk_level = "高"
        elif len(self._warnings) >= 1:
            self._risk_level = "中"
        else:
            self._risk_level = "低"

    # ==================== 输出接口 ====================

    def get_latest_signal(self) -> dict:
        """获取最新交易日的完整分析结果"""
        if self.df.empty:
            return {}

        latest = self.df.iloc[-1]
        date_str = latest.name.strftime("%Y-%m-%d") if hasattr(latest.name, "strftime") else str(latest.name)

        return {
            "symbol": self.symbol,
            "date": date_str,
            "close": round(float(latest["close"]), 2),
            "pct_change": round(float(latest.get("pct_change", 0) or 0) * 100, 2),

            # 技术指标
            "SMA_5": round(float(latest["SMA_5"]), 2) if not pd.isna(latest["SMA_5"]) else None,
            "SMA_10": round(float(latest["SMA_10"]), 2) if not pd.isna(latest["SMA_10"]) else None,
            "SMA_20": round(float(latest["SMA_20"]), 2) if not pd.isna(latest["SMA_20"]) else None,
            "SMA_60": round(float(latest["SMA_60"]), 2) if not pd.isna(latest.get("SMA_60", np.nan)) else None,
            "RSI_14": round(float(latest["RSI_14"]), 1),
            "MACD_DIF": round(float(latest["MACD_DIF"]), 3),
            "MACD_DEA": round(float(latest["MACD_DEA"]), 3),
            "MACD_HIST": round(float(latest["MACD_HIST"]), 3),
            "BB_PctB": round(float(latest["BB_PctB"]), 3),
            "KDJ_J": round(float(latest["KDJ_J"]), 1),
            "ATR_14": round(float(latest["ATR_14"]), 2) if not pd.isna(latest["ATR_14"]) else None,
            "VOL_Ratio": round(float(latest["VOL_Ratio"]), 2),
            "Momentum_5": round(float(latest["Momentum_5"]), 2) if not pd.isna(latest["Momentum_5"]) else None,

            # 多维评分
            "tech_score": round(self._tech_score, 1),
            "vol_score": round(self._vol_score, 1),
            "fund_score": round(self._fund_score, 1),
            "sentiment_score": round(self._sent_score, 1),
            "total_score": round(self._total_score, 1),

            # 决策输出
            "confidence": round(self._confidence, 2),
            "recommended_position": round(self._position, 1),
            "market_state": self._market_state,
            "suggestion": self._suggestion,

            # 风控
            "risk_level": self._risk_level,
            "warnings": self._warnings,
            "has_warning": len(self._warnings) > 0,
        }

    def get_signals_df(self) -> pd.DataFrame:
        """返回带指标的完整DataFrame"""
        return self.df


def run_monitor_for_stocks(stock_data_dict: dict, extra_data: dict = None) -> tuple:
    """
    批量执行策略监控
    参数:
        stock_data_dict: {symbol: DataFrame}
        extra_data: {symbol: {"sentiment": float, "fund_data": dict, "realtime": dict}}
    返回:
        (alerts, results)
    """
    alerts = []
    results = []
    extra_data = extra_data or {}

    for symbol, df in stock_data_dict.items():
        if df is None or df.empty:
            continue

        ext = extra_data.get(symbol, {})
        try:
            monitor = StrategyMonitorV2(
                df=df,
                symbol=symbol,
                sentiment_score=ext.get("sentiment", 0.0),
                fund_data=ext.get("fund_data", {}),
                realtime_data=ext.get("realtime", {}),
            )
            latest_status = monitor.get_latest_signal()

            if latest_status:
                results.append(latest_status)
                if latest_status.get("has_warning"):
                    alerts.append(latest_status)
        except Exception as e:
            logger.error(f"策略监控 {symbol} 执行失败: {e}")
            continue

    return alerts, results


# 向后兼容别名
StrategyMonitor = StrategyMonitorV2
