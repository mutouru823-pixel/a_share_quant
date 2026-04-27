#!/usr/bin/env python3
import argparse
import os

from src.backtest_engine import BacktestConfig, export_backtest_report, run_backtest


def parse_symbols(raw: str) -> list[str]:
    symbols = []
    for s in raw.replace("，", ",").split(","):
        cleaned = s.strip()
        if cleaned:
            symbols.append(cleaned)
    return symbols


def main() -> int:
    parser = argparse.ArgumentParser(description="A股策略 Walk-forward 回测脚本")
    parser.add_argument("--symbols", type=str, required=True, help="股票代码列表，逗号分隔，例如: sz000001,sh600519")
    parser.add_argument("--days", type=int, default=260, help="回看交易日数量")
    parser.add_argument("--warmup", type=int, default=60, help="指标预热天数")
    parser.add_argument("--benchmark", type=str, default="sh000300", help="基准指数代码，默认沪深300: sh000300")
    parser.add_argument("--out", type=str, default="outputs/backtest", help="输出文件前缀")
    args = parser.parse_args()

    symbols = parse_symbols(args.symbols)
    if not symbols:
        print("未提供有效 symbols")
        return 1

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    config = BacktestConfig(
        symbols=symbols,
        lookback_days=args.days,
        warmup_days=args.warmup,
        benchmark_symbol=args.benchmark,
    )
    summary_df, detail_df = run_backtest(config)

    if summary_df.empty:
        print("回测未产出结果，请检查数据可用性")
        return 1

    paths = export_backtest_report(summary_df, detail_df, args.out)

    print("\n=== Backtest Summary ===")
    print(summary_df.to_string(index=False))
    print("\n=== Reports Generated ===")
    for k, v in paths.items():
        print(f"{k}: {v}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
