import json
import os
import sys
import logging
import argparse
from datetime import datetime
import pandas as pd
from src.data_fetcher import fetch_daily_data, fetch_realtime_data, fetch_top_sectors, fetch_sentiment_score, fetch_fund_flow, _clean_symbol
from src.strategy_monitor import run_monitor_for_stocks, StrategyMonitor
from src.notifier import FeishuNotifier
from src.analytics import record_suggestion, evaluate_accuracy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config(config_path="config.json"):
    if not os.path.exists(config_path):
        logger.error(f"找不到配置文件: {config_path}")
        sys.exit(1)
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    parser = argparse.ArgumentParser(description="A 股量化监控自动化程序")
    parser.add_argument("--mode", type=str, choices=['start', 'mid', 'end'], required=True, help="播报模式: start, mid, end")
    args = parser.parse_args()
    
    logger.info(f"=== A 股量化监控自动化程序启动 (模式: {args.mode}) ===")
    
    # 动态加载自选股配置
    config = load_config()
    target_symbols = config.get("target_symbols", [])
    target_days = config.get("target_days", 200)
    feishu_webhook = config.get("feishu_webhook", "")
    
    if not target_symbols:
        logger.warning("自选股列表为空，请检查 config.json。")
        sys.exit(0)
    
    stock_data_dict = {}
    
    logger.info("=== 阶段 1：获取多维数据 ===")
    
    # 获取板块概览 (允许非必要化报错跳过)
    try:
        sectors = fetch_top_sectors(5)
    except Exception as e:
        logger.warning(f"获取板块概览失败，跳过: {e}")
        sectors = []
        
    market_overview = ""
    if sectors:
        market_overview = "今日领涨板块：\n" + "\n".join([f" - {s.get('板块名称', '')} (+{s.get('涨跌幅', 0)}%)" for s in sectors])
    
    extra_data = {}
    
    for symbol in target_symbols:
        try:
            logger.info(f"--- 此刻正在处理: {symbol} ---")
            df = fetch_daily_data(symbol=symbol, days=target_days)
            if df.empty:
                logger.warning(f"获取 {symbol} 的历史数据为空！跳过。")
                continue
                
            clean_sym = _clean_symbol(symbol)
            # 获取单只股票基本面 (单股狙击)
            try:
                realtime_df = fetch_realtime_data(clean_sym)
                logger.info(f"{symbol} 实时基本信息获取成功，包含 {len(realtime_df) if realtime_df is not None else 0} 条属性")
                # 注：由于 stock_individual_info_em 多为静态基础信息，如果没有实时的 "最新价" 则继续使用日线最后一天数据
            except Exception as e:
                logger.warning(f"获取 {symbol} 单股实时信息失败: {e}")
            
            stock_data_dict[symbol] = df
            
            # 抓取情绪与资金（防封锁机制已在底层或此处加上延时）
            sent = fetch_sentiment_score(symbol)
            fund = fetch_fund_flow(symbol)
            extra_data[symbol] = {"sentiment": sent, "fund_data": fund}
            
        except Exception as e:
            logger.warning(f"获取 {symbol} 数据执行失败: {e}，将 continue 继续抓取下一只")
            continue
            
    if not stock_data_dict:
        logger.warning("所有自选股均历史数据获取失败！将发送空播报。")
        
    logger.info("=== 阶段 2：执行策略监控分析 === ")
    
    # 扫描触发报警及所有标的结果
    alerts, monitor_results = run_monitor_for_stocks(stock_data_dict, extra_data)
    
    if alerts:
        logger.warning(f"【报警发现】在最新交易日发现 {len(alerts)} 个风控警告实例！")
    else:
        logger.info("最新交易日所有股票平稳，无风控报警。")
        
    # === 阶段 3：Analytics 与通知 ===
    
    accuracy_data = None
    if args.mode == 'end':
        logger.info("终盘模式：正在记录建议并评估胜率...")
        # 记录每只股票今天的建议
        today_str = datetime.now().strftime('%Y-%m-%d')
        for res in monitor_results:
            sym = res.get('symbol')
            price = res.get('close', 0.0)
            sugg = res.get('suggestion', '建议观望')
            state = res.get('market_state', 'Neutral')
            record_suggestion(sym, today_str, price, sugg, state)
            
        # 评估胜率
        accuracy_data = evaluate_accuracy(days_list=[3, 5, 10])

    # 初始化通知器并发起对应模式的播报
    notifier = FeishuNotifier(webhook_url=feishu_webhook)
    notifier.send_broadcast(args.mode, monitor_results, alerts, market_overview=market_overview, accuracy_data=accuracy_data)

if __name__ == "__main__":
    main()
