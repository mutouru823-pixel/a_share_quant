import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import akshare as ak
import numpy as np
import pandas as pd

from src.data_fetcher import fetch_daily_data
from src.strategy_monitor import StrategyMonitor

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    symbols: list[str]
    lookback_days: int = 260
    warmup_days: int = 60
    risk_free_rate: float = 0.02
    benchmark_symbol: str = "sh000300"


@dataclass
class SymbolBacktestResult:
    symbol: str
    trades: int
    coverage: float
    cumulative_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe: float
    max_drawdown: float
    hit_rate: float
    benchmark_symbol: str
    benchmark_cumulative_return: float
    excess_return: float
    alpha: float
    beta: float
    information_ratio: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "trades": self.trades,
            "coverage": self.coverage,
            "cumulative_return": self.cumulative_return,
            "annualized_return": self.annualized_return,
            "annualized_volatility": self.annualized_volatility,
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "hit_rate": self.hit_rate,
            "benchmark_symbol": self.benchmark_symbol,
            "benchmark_cumulative_return": self.benchmark_cumulative_return,
            "excess_return": self.excess_return,
            "alpha": self.alpha,
            "beta": self.beta,
            "information_ratio": self.information_ratio,
        }


def _normalize_benchmark_symbol(symbol: str) -> str:
    symbol = (symbol or "").strip().lower()
    if symbol.startswith(("sh", "sz")) and len(symbol) == 8:
        return symbol[2:]
    return symbol


def fetch_benchmark_returns(benchmark_symbol: str, days: int) -> pd.Series:
    """获取基准指数日收益率，返回以日期为索引的 series。"""
    symbol = _normalize_benchmark_symbol(benchmark_symbol)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=int(days * 1.7) + 30)
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    df = None
    # 优先使用 index_zh_a_hist
    try:
        df = ak.index_zh_a_hist(symbol=symbol, period="daily", start_date=start_str, end_date=end_str)
    except Exception as e:
        logger.warning("index_zh_a_hist 获取基准失败: %s", e)

    # 兜底1：使用 stock_zh_index_daily_em（实测可用）
    if df is None or df.empty:
        try:
            market_symbol = f"{'sh' if symbol.startswith(('0', '9')) else 'sz'}{symbol}"
            df = ak.stock_zh_index_daily_em(symbol=market_symbol)
        except Exception as e:
            logger.warning("stock_zh_index_daily_em 获取基准失败: %s", e)

    # 兜底2：如果仍失败，尝试用 index_zh_a_hist 仅传 symbol
    if df is None or df.empty:
        try:
            df = ak.index_zh_a_hist(symbol=symbol)
        except Exception as e:
            logger.warning("index_zh_a_hist(简化参数) 获取基准失败: %s", e)
            return pd.Series(dtype=float)

    if df is None or df.empty:
        return pd.Series(dtype=float)

    # 字段兼容：中文字段/英文字段
    if "日期" in df.columns and "收盘" in df.columns:
        tmp = df[["日期", "收盘"]].copy()
        tmp.columns = ["date", "close"]
    elif "date" in df.columns and "close" in df.columns:
        tmp = df[["date", "close"]].copy()
    else:
        logger.warning("基准数据字段不符合预期: %s", list(df.columns))
        return pd.Series(dtype=float)

    tmp["date"] = pd.to_datetime(tmp["date"], errors="coerce")
    tmp["close"] = pd.to_numeric(tmp["close"], errors="coerce")
    tmp = tmp.dropna().sort_values("date").tail(days + 20)
    if tmp.empty:
        return pd.Series(dtype=float)

    ret = tmp.set_index("date")["close"].pct_change().dropna()
    ret.name = "benchmark_return"
    return ret


def _max_drawdown(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    rolling_peak = equity_curve.cummax()
    drawdown = equity_curve / rolling_peak - 1.0
    return float(drawdown.min())


def _annualized_return(daily_returns: pd.Series) -> float:
    if daily_returns.empty:
        return 0.0
    cumulative = (1 + daily_returns).prod()
    years = len(daily_returns) / 252
    if years <= 0:
        return 0.0
    return float(cumulative ** (1 / years) - 1)


def _annualized_volatility(daily_returns: pd.Series) -> float:
    if daily_returns.empty:
        return 0.0
    return float(daily_returns.std(ddof=0) * np.sqrt(252))


def _sharpe_ratio(daily_returns: pd.Series, risk_free_rate: float) -> float:
    if daily_returns.empty:
        return 0.0
    excess_daily = daily_returns - (risk_free_rate / 252)
    vol = excess_daily.std(ddof=0)
    if vol == 0 or np.isnan(vol):
        return 0.0
    return float(excess_daily.mean() / vol * np.sqrt(252))


def _benchmark_metrics(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_rate: float,
) -> dict[str, float]:
    if strategy_returns.empty or benchmark_returns.empty:
        return {
            "benchmark_cumulative_return": 0.0,
            "excess_return": 0.0,
            "alpha": 0.0,
            "beta": 0.0,
            "information_ratio": 0.0,
        }

    aligned = pd.concat([strategy_returns, benchmark_returns], axis=1, join="inner").dropna()
    if aligned.empty:
        return {
            "benchmark_cumulative_return": 0.0,
            "excess_return": 0.0,
            "alpha": 0.0,
            "beta": 0.0,
            "information_ratio": 0.0,
        }

    rp = aligned.iloc[:, 0]
    rb = aligned.iloc[:, 1]

    bench_cum = float((1 + rb).prod() - 1.0)
    strat_cum = float((1 + rp).prod() - 1.0)
    excess = strat_cum - bench_cum

    var_b = float(rb.var(ddof=0))
    beta = float(rp.cov(rb) / var_b) if var_b > 0 else 0.0

    rf_daily = risk_free_rate / 252
    alpha_daily = float((rp.mean() - rf_daily) - beta * (rb.mean() - rf_daily))
    alpha = alpha_daily * 252

    active = rp - rb
    active_vol = float(active.std(ddof=0))
    information_ratio = float(active.mean() / active_vol * np.sqrt(252)) if active_vol > 0 else 0.0

    return {
        "benchmark_cumulative_return": bench_cum,
        "excess_return": excess,
        "alpha": alpha,
        "beta": beta,
        "information_ratio": information_ratio,
    }


def _signal_to_position(signal: dict[str, Any]) -> float:
    score = float(signal.get("total_score", 0.0))
    position_ratio = float(signal.get("recommended_position", 0.0)) / 100.0

    if score >= 0.25:
        return max(0.0, min(1.0, position_ratio if position_ratio > 0 else 0.5))
    if score <= -0.25:
        return -max(0.0, min(1.0, position_ratio if position_ratio > 0 else 0.5))
    return 0.0


def backtest_symbol(
    symbol: str,
    lookback_days: int = 260,
    warmup_days: int = 60,
    benchmark_symbol: str = "sh000300",
    benchmark_returns: pd.Series | None = None,
    risk_free_rate: float = 0.02,
) -> tuple[SymbolBacktestResult, pd.DataFrame]:
    df = fetch_daily_data(symbol, days=lookback_days)
    if df.empty or len(df) <= warmup_days + 5:
        raise ValueError(f"{symbol} 数据不足，无法回测")

    rows: list[dict[str, Any]] = []

    # Walk-forward backtest: at each t, only use historical data up to t to generate signal for t+1.
    for i in range(warmup_days, len(df) - 1):
        hist = df.iloc[: i + 1].copy()
        current_date = hist.index[-1]
        next_date = df.index[i + 1]
        next_ret = float(df.iloc[i + 1]["close"] / df.iloc[i]["close"] - 1.0)

        monitor = StrategyMonitor(hist, symbol, sentiment_score=0.0, fund_data={})
        signal = monitor.get_latest_signal()
        position = _signal_to_position(signal)
        strategy_ret = position * next_ret

        rows.append(
            {
                "date": current_date,
                "next_date": next_date,
                "position": position,
                "score": float(signal.get("total_score", 0.0)),
                "confidence_score": float(signal.get("confidence_score", 0.0)),
                "recommended_position": float(signal.get("recommended_position", 0.0)),
                "next_day_return": next_ret,
                "strategy_return": strategy_ret,
                "market_state": signal.get("market_state", "Neutral"),
            }
        )

    detail = pd.DataFrame(rows)
    detail["date"] = pd.to_datetime(detail["date"])
    detail = detail.sort_values("date")

    active_mask = detail["position"].abs() > 0
    active = detail[active_mask]

    equity_curve = (1 + detail["strategy_return"]).cumprod()

    cumulative_return = float(equity_curve.iloc[-1] - 1.0) if not equity_curve.empty else 0.0
    strategy_returns = detail.set_index("date")["strategy_return"]
    ann_return = _annualized_return(strategy_returns)
    ann_vol = _annualized_volatility(strategy_returns)
    sharpe = _sharpe_ratio(strategy_returns, risk_free_rate=risk_free_rate)
    max_dd = _max_drawdown(equity_curve)

    bench_metrics = _benchmark_metrics(
        strategy_returns=strategy_returns,
        benchmark_returns=benchmark_returns if benchmark_returns is not None else pd.Series(dtype=float),
        risk_free_rate=risk_free_rate,
    )

    if active.empty:
        hit_rate = 0.0
    else:
        # Directional hit rate: long needs positive next return, short needs negative next return.
        hit = (
            ((active["position"] > 0) & (active["next_day_return"] > 0))
            | ((active["position"] < 0) & (active["next_day_return"] < 0))
        ).mean()
        hit_rate = float(hit)

    result = SymbolBacktestResult(
        symbol=symbol,
        trades=int(active_mask.sum()),
        coverage=float(active_mask.mean()),
        cumulative_return=cumulative_return,
        annualized_return=ann_return,
        annualized_volatility=ann_vol,
        sharpe=sharpe,
        max_drawdown=float(max_dd),
        hit_rate=hit_rate,
        benchmark_symbol=benchmark_symbol,
        benchmark_cumulative_return=bench_metrics["benchmark_cumulative_return"],
        excess_return=bench_metrics["excess_return"],
        alpha=bench_metrics["alpha"],
        beta=bench_metrics["beta"],
        information_ratio=bench_metrics["information_ratio"],
    )

    return result, detail


def run_backtest(config: BacktestConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    detail_frames: list[pd.DataFrame] = []

    benchmark_returns = fetch_benchmark_returns(config.benchmark_symbol, days=config.lookback_days)
    if benchmark_returns.empty:
        logger.warning("未获取到基准收益序列: %s，后续 Alpha/Beta 指标将为 0", config.benchmark_symbol)
    else:
        logger.info("基准序列已加载: %s, 样本点=%d", config.benchmark_symbol, len(benchmark_returns))

    for symbol in config.symbols:
        try:
            result, detail = backtest_symbol(
                symbol=symbol,
                lookback_days=config.lookback_days,
                warmup_days=config.warmup_days,
                benchmark_symbol=config.benchmark_symbol,
                benchmark_returns=benchmark_returns,
                risk_free_rate=config.risk_free_rate,
            )
            summary_rows.append(result.to_dict())
            detail.insert(0, "symbol", symbol)
            if not benchmark_returns.empty:
                detail = detail.merge(
                    benchmark_returns.rename("benchmark_return").reset_index().rename(columns={"index": "date"}),
                    how="left",
                    on="date",
                )
            detail_frames.append(detail)
            logger.info("回测完成: %s | Sharpe=%.2f | CumRet=%.2f%%", symbol, result.sharpe, result.cumulative_return * 100)
        except Exception as e:
            logger.warning("回测失败: %s, error=%s", symbol, e)

    summary_df = pd.DataFrame(summary_rows)
    detail_df = pd.concat(detail_frames, ignore_index=True) if detail_frames else pd.DataFrame()

    if not detail_df.empty:
        portfolio = detail_df.groupby("date", as_index=True)["strategy_return"].mean().sort_index()
        equity = (1 + portfolio).cumprod()
        bench_metrics = _benchmark_metrics(
            strategy_returns=portfolio,
            benchmark_returns=benchmark_returns,
            risk_free_rate=config.risk_free_rate,
        )
        portfolio_row = {
            "symbol": "PORTFOLIO",
            "trades": int((detail_df["position"].abs() > 0).sum()),
            "coverage": float((detail_df["position"].abs() > 0).mean()),
            "cumulative_return": float(equity.iloc[-1] - 1.0),
            "annualized_return": _annualized_return(portfolio),
            "annualized_volatility": _annualized_volatility(portfolio),
            "sharpe": _sharpe_ratio(portfolio, risk_free_rate=config.risk_free_rate),
            "max_drawdown": _max_drawdown(equity),
            "hit_rate": float(((portfolio > 0).mean() if len(portfolio) else 0.0)),
            "benchmark_symbol": config.benchmark_symbol,
            "benchmark_cumulative_return": bench_metrics["benchmark_cumulative_return"],
            "excess_return": bench_metrics["excess_return"],
            "alpha": bench_metrics["alpha"],
            "beta": bench_metrics["beta"],
            "information_ratio": bench_metrics["information_ratio"],
        }
        summary_df = pd.concat([summary_df, pd.DataFrame([portfolio_row])], ignore_index=True)

    return summary_df, detail_df


def export_backtest_report(summary_df: pd.DataFrame, detail_df: pd.DataFrame, output_prefix: str) -> dict[str, str]:
    summary_path = f"{output_prefix}_summary.csv"
    detail_path = f"{output_prefix}_detail.csv"
    json_path = f"{output_prefix}_summary.json"

    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    detail_df.to_csv(detail_path, index=False, encoding="utf-8-sig")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary_df.to_dict(orient="records"), f, ensure_ascii=False, indent=2)

    return {
        "summary_csv": summary_path,
        "detail_csv": detail_path,
        "summary_json": json_path,
    }
