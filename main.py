# -*- coding: utf-8 -*-
"""
A股量化分析工具 v2 - 主入口
多源数据 + 多维评分 + 风控引擎 + 财新数据增强
"""
import json
import os
import sys
import logging
import argparse
from datetime import datetime

import pandas as pd

from src.data_sources import (
    fetch_daily_data,
    fetch_realtime_data,
    fetch_fund_flow,
    fetch_top_sectors,
    fetch_sentiment_score,
    _clean_symbol,
)
from src.strategy_monitor import run_monitor_for_stocks, StrategyMonitorV2
from src.caixin_data import init_caixin_client, fetch_caixin_sentiment, fetch_caixin_macro_context

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_config(config_path="config.json"):
    if not os.path.exists(config_path):
        logger.error(f"找不到配置文件: {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def print_analysis_report(results: list, alerts: list, sectors: list, macro_ctx: dict):
    """终端格式化输出分析报告"""
    print("\n" + "=" * 70)
    print(f"  A股量化分析报告  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    # 宏观环境
    if macro_ctx:
        print("\n【宏观环境】")
        if "market_sentiment_index" in macro_ctx:
            idx = macro_ctx["market_sentiment_index"]
            mood = "贪婪" if idx > 20 else "恐慌" if idx < -20 else "中性"
            print(f"  市场情绪指数: {idx:.1f} ({mood})")
        if macro_ctx.get("macro", {}).get("pmi"):
            pmi = macro_ctx["macro"]["pmi"]
            print(f"  最新PMI: {pmi}")

    # 板块概览
    if sectors:
        print("\n【今日领涨板块】")
        for s in sectors[:5]:
            print(f"  {s.get('板块名称', 'N/A'): <6} {s.get('涨跌幅', 0):+.2f}%")

    # 个股分析
    print("\n【个股分析】")
    print("-" * 70)
    for r in results:
        score = r["total_score"]
        color_hint = "▲" if score > 0 else "▼" if score < 0 else "◆"
        print(f"\n  {color_hint} {r['symbol']}  |  收盘: {r['close']}  |  涨跌: {r['pct_change']:+.2f}%")
        print(f"    综合评分: {score:+.1f}/100  |  状态: {r['market_state']}  |  置信度: {r['confidence']:.0%}")
        print(f"    技术: {r['tech_score']:+.1f}  量价: {r['vol_score']:+.1f}  "
              f"资金: {r['fund_score']:+.1f}  舆情: {r['sentiment_score']:+.1f}")
        print(f"    建议仓位: {r['recommended_position']:.0f}%  |  建议: {r['suggestion']}")
        print(f"    风险等级: {r['risk_level']}")

        if r.get("warnings"):
            for w in r["warnings"]:
                print(f"    ⚠ {w}")

    # 风控汇总
    if alerts:
        print("\n" + "!" * 70)
        print(f"  【风控预警】共 {len(alerts)} 只股票触发预警")
        for a in alerts:
            print(f"  ⚠ {a['symbol']}: {', '.join(a['warnings'][:3])}")
        print("!" * 70)

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description="A股量化分析工具 v2")
    parser.add_argument("--mode", type=str, choices=["start", "mid", "end"],
                        default="mid", help="播报模式")
    parser.add_argument("--symbols", type=str, default=None,
                        help="逗号分隔的股票代码，覆盖config")
    parser.add_argument("--days", type=int, default=None,
                        help="回看交易日数，覆盖config")
    args = parser.parse_args()

    config = load_config()

    # 参数优先级: 命令行 > 配置文件
    target_symbols = args.symbols.split(",") if args.symbols else config.get("target_symbols", [])
    target_days = args.days or config.get("target_days", 200)

    # 初始化财新数据客户端
    caixin_key = config.get("caixin_api_key", "")
    if caixin_key:
        client = init_caixin_client(caixin_key)
        if client.health_check():
            logger.info("财新数据 API 已连接")
        else:
            logger.info("财新数据 API 不可用，使用免费数据源")
    else:
        logger.info("未配置财新数据 API Key，使用免费数据源")

    if not target_symbols:
        logger.error("自选股列表为空，请检查 config.json")
        sys.exit(1)

    logger.info(f"=== A股量化分析 v2 启动 | 模式: {args.mode} | 标的: {len(target_symbols)} 只 ===")

    # === 阶段1: 多维数据获取 ===
    logger.info("阶段1: 获取多维数据...")

    stock_data_dict = {}
    extra_data = {}

    # 板块概览
    try:
        sectors = fetch_top_sectors(5)
    except Exception as e:
        logger.warning(f"板块数据获取失败: {e}")
        sectors = []

    # 宏观上下文（财新数据）
    macro_ctx = {}
    if caixin_key:
        try:
            macro_ctx = fetch_caixin_macro_context()
        except Exception:
            pass

    for symbol in target_symbols:
        try:
            logger.info(f"  处理: {symbol}")

            # K线数据（多源自动降级）
            df = fetch_daily_data(symbol=symbol, days=target_days)
            if df.empty:
                logger.warning(f"  {symbol} 数据为空，跳过")
                continue

            stock_data_dict[symbol] = df

            # 资金流向（东方财富）
            fund_data = fetch_fund_flow(symbol)

            # 舆情评分（东方财富新闻 + 财新增强）
            sentiment = fetch_sentiment_score(symbol)
            if caixin_key:
                caixin_sent = fetch_caixin_sentiment(symbol)
                if caixin_sent != 0:
                    # 财新权重更高（NLP模型驱动）
                    sentiment = sentiment * 0.4 + caixin_sent * 0.6

            # 实时行情（腾讯）
            realtime = fetch_realtime_data(symbol)

            extra_data[symbol] = {
                "sentiment": sentiment,
                "fund_data": fund_data,
                "realtime": realtime,
            }

        except Exception as e:
            logger.warning(f"  {symbol} 处理失败: {e}")
            continue

    if not stock_data_dict:
        logger.error("所有股票数据获取失败")
        sys.exit(1)

    # === 阶段2: 策略分析 ===
    logger.info("阶段2: 执行多维策略分析...")
    alerts, results = run_monitor_for_stocks(stock_data_dict, extra_data)

    # === 阶段3: 输出报告 ===
    print_analysis_report(results, alerts, sectors, macro_ctx)

    # 飞书通知（如果配置了）
    feishu_webhook = config.get("feishu_webhook", "")
    if feishu_webhook and config.get("notification", {}).get("enable_feishu"):
        try:
            from src.notifier import FeishuNotifier
            notifier = FeishuNotifier(webhook_url=feishu_webhook)
            market_overview = ""
            if sectors:
                market_overview = "今日领涨: " + ", ".join(
                    [f"{s.get('板块名称', '')}({s.get('涨跌幅', 0):+.1f}%)" for s in sectors[:3]]
                )
            notifier.send_broadcast(args.mode, results, alerts, market_overview=market_overview)
            logger.info("飞书通知已发送")
        except Exception as e:
            logger.warning(f"飞书通知发送失败: {e}")

    logger.info("=== 分析完成 ===")


if __name__ == "__main__":
    main()
