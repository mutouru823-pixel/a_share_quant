#!/usr/bin/env python3
import argparse
import os

from src.backtest_engine import BacktestConfig, run_backtest
from src.parameter_search import export_grid_search_report, run_parameter_grid_search


def parse_symbols(raw: str) -> list[str]:
    values = []
    for s in raw.replace("，", ",").split(","):
        s = s.strip()
        if s:
            values.append(s)
    return values


def parse_floats(raw: str) -> list[float]:
    values = []
    for x in raw.replace("，", ",").split(","):
        x = x.strip()
        if x:
            values.append(float(x))
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="参数网格搜索：寻找最优交易阈值组合")
    parser.add_argument("--symbols", type=str, required=True, help="股票代码列表，例如: sz000001,sh600519")
    parser.add_argument("--days", type=int, default=260, help="回看交易日")
    parser.add_argument("--warmup", type=int, default=60, help="指标预热天数")
    parser.add_argument("--benchmark", type=str, default="sh000300", help="基准指数代码")
    parser.add_argument("--long-thresholds", type=str, default="0.20,0.25,0.30", help="多头阈值网格")
    parser.add_argument("--short-thresholds", type=str, default="0.20,0.25,0.30", help="空头阈值网格")
    parser.add_argument("--min-confidences", type=str, default="0.50,0.60,0.70", help="最小置信度网格")
    parser.add_argument("--min-positions", type=str, default="20,30,40", help="最小建议仓位网格")
    parser.add_argument("--top-n", type=int, default=10, help="输出前 N 个参数组合")
    parser.add_argument("--out", type=str, default="outputs/grid_search", help="输出文件前缀")
    args = parser.parse_args()

    symbols = parse_symbols(args.symbols)
    if not symbols:
        print("未提供有效 symbols")
        return 1

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    base_config = BacktestConfig(
        symbols=symbols,
        lookback_days=args.days,
        warmup_days=args.warmup,
        benchmark_symbol=args.benchmark,
    )

    _, detail_df = run_backtest(base_config)
    if detail_df.empty:
        print("基础回测 detail 为空，无法进行参数搜索")
        return 1

    result_df = run_parameter_grid_search(
        detail_df=detail_df,
        benchmark_symbol=args.benchmark,
        lookback_days=args.days,
        risk_free_rate=base_config.risk_free_rate,
        long_thresholds=parse_floats(args.long_thresholds),
        short_thresholds=parse_floats(args.short_thresholds),
        min_confidences=parse_floats(args.min_confidences),
        min_positions=parse_floats(args.min_positions),
    )

    if result_df.empty:
        print("参数搜索未产生结果")
        return 1

    paths = export_grid_search_report(result_df, args.out, top_n=args.top_n)

    print("\n=== Grid Search Top Results ===")
    print(result_df.head(args.top_n).to_string(index=False))
    print("\n=== Reports Generated ===")
    for k, v in paths.items():
        print(f"{k}: {v}")

    best = result_df.iloc[0]
    print("\n=== Best Params ===")
    print(
        f"long={best['long_threshold']}, short={best['short_threshold']}, "
        f"min_conf={best['min_confidence']}, min_pos={best['min_position']}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
