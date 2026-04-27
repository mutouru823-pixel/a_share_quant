import json
from itertools import product
from typing import Any

import numpy as np
import pandas as pd

from src.backtest_engine import fetch_benchmark_returns


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
    vol = float(excess_daily.std(ddof=0))
    if vol <= 1e-8:
        return 0.0
    return float(excess_daily.mean() / vol * np.sqrt(252))


def _max_drawdown(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    rolling_peak = equity_curve.cummax()
    drawdown = equity_curve / rolling_peak - 1.0
    return float(drawdown.min())


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


def _calc_position(row: pd.Series, long_th: float, short_th: float, min_conf: float, min_pos: float) -> float:
    score = float(row.get("score", 0.0))
    conf = float(row.get("confidence_score", 0.0))
    rec = float(row.get("recommended_position", 0.0))

    if conf < min_conf or rec < min_pos:
        return 0.0

    pos = max(0.0, min(1.0, rec / 100.0))
    if score >= long_th:
        return pos
    if score <= -short_th:
        return -pos
    return 0.0


def run_parameter_grid_search(
    detail_df: pd.DataFrame,
    benchmark_symbol: str,
    lookback_days: int,
    risk_free_rate: float,
    long_thresholds: list[float],
    short_thresholds: list[float],
    min_confidences: list[float],
    min_positions: list[float],
) -> pd.DataFrame:
    required_cols = {"date", "score", "confidence_score", "recommended_position", "next_day_return"}
    missing = required_cols - set(detail_df.columns)
    if missing:
        raise ValueError(f"detail_df 缺少必要字段: {sorted(missing)}")

    work = detail_df.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work.dropna(subset=["date"])  # nosec B101

    benchmark_returns = fetch_benchmark_returns(benchmark_symbol, days=lookback_days)

    rows: list[dict[str, Any]] = []

    for long_th, short_th, min_conf, min_pos in product(
        long_thresholds,
        short_thresholds,
        min_confidences,
        min_positions,
    ):
        tmp = work.copy()
        tmp["position_opt"] = tmp.apply(
            lambda r: _calc_position(r, long_th, short_th, min_conf, min_pos),
            axis=1,
        )
        tmp["strategy_return_opt"] = tmp["position_opt"] * pd.to_numeric(tmp["next_day_return"], errors="coerce").fillna(0.0)

        daily_portfolio = tmp.groupby("date", as_index=True)["strategy_return_opt"].mean().sort_index()
        equity = (1 + daily_portfolio).cumprod()

        cumulative_return = float(equity.iloc[-1] - 1.0) if not equity.empty else 0.0
        ann_return = _annualized_return(daily_portfolio)
        ann_vol = _annualized_volatility(daily_portfolio)
        sharpe = _sharpe_ratio(daily_portfolio, risk_free_rate)
        max_dd = _max_drawdown(equity)
        hit_rate = float((daily_portfolio > 0).mean()) if len(daily_portfolio) else 0.0
        coverage = float((tmp["position_opt"].abs() > 0).mean()) if len(tmp) else 0.0
        trades = int((tmp["position_opt"].abs() > 0).sum())

        bench = _benchmark_metrics(
            strategy_returns=daily_portfolio,
            benchmark_returns=benchmark_returns,
            risk_free_rate=risk_free_rate,
        )

        # 综合评分：偏重夏普与信息比率，同时考虑超额收益、回撤与交易有效性。
        if trades == 0:
            objective_score = -9999.0
        else:
            coverage_bonus = min(0.15, coverage)
            objective_score = (
                sharpe * 0.5
                + bench["information_ratio"] * 0.3
                + bench["excess_return"] * 2.0
                + max_dd * 0.2
                + coverage_bonus
            )

        rows.append(
            {
                "long_threshold": float(long_th),
                "short_threshold": float(short_th),
                "min_confidence": float(min_conf),
                "min_position": float(min_pos),
                "trades": trades,
                "coverage": coverage,
                "cumulative_return": cumulative_return,
                "annualized_return": ann_return,
                "annualized_volatility": ann_vol,
                "sharpe": sharpe,
                "max_drawdown": max_dd,
                "hit_rate": hit_rate,
                "benchmark_symbol": benchmark_symbol,
                "benchmark_cumulative_return": bench["benchmark_cumulative_return"],
                "excess_return": bench["excess_return"],
                "alpha": bench["alpha"],
                "beta": bench["beta"],
                "information_ratio": bench["information_ratio"],
                "objective_score": objective_score,
            }
        )

    result_df = pd.DataFrame(rows)
    if result_df.empty:
        return result_df

    return result_df.sort_values(
        by=["objective_score", "sharpe", "excess_return", "max_drawdown"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def export_grid_search_report(result_df: pd.DataFrame, output_prefix: str, top_n: int = 10) -> dict[str, str]:
    all_path = f"{output_prefix}_grid_all.csv"
    top_path = f"{output_prefix}_grid_top{top_n}.csv"
    json_path = f"{output_prefix}_grid_top{top_n}.json"

    result_df.to_csv(all_path, index=False, encoding="utf-8-sig")
    top_df = result_df.head(top_n)
    top_df.to_csv(top_path, index=False, encoding="utf-8-sig")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(top_df.to_dict(orient="records"), f, ensure_ascii=False, indent=2)

    return {
        "grid_all_csv": all_path,
        "grid_top_csv": top_path,
        "grid_top_json": json_path,
    }
