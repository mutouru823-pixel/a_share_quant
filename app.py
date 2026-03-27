import json
import os
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from src.data_fetcher import (
    fetch_daily_data,
    fetch_fund_flow,
    fetch_sentiment_score,
    fetch_top_sectors,
)
from src.notifier import FeishuNotifier
from src.strategy_monitor import StrategyMonitor


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
FEISHU_WEBHOOK_PREFIX = "https://open.feishu.cn/open-apis/bot/v2/hook/"
RESULT_COLUMNS = [
    "symbol",
    "date",
    "close",
    "pct_change",
    "SMA_5",
    "SMA_10",
    "SMA_20",
    "RSI_14",
    "MACD_DIF",
    "MACD_DEA",
    "tech_score",
    "chip_score",
    "sentiment_score",
    "total_score",
    "market_state",
    "suggestion",
    "has_warning",
]


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def parse_fund_net_amount(fund_data: dict) -> float:
    raw_val = fund_data.get("主力净流入-净额", 0)
    if isinstance(raw_val, str):
        raw_val = raw_val.replace(",", "").replace("万", "").strip()
    try:
        return float(raw_val)
    except (ValueError, TypeError):
        return 0.0


def parse_symbols_input(raw_text: str) -> list[str]:
    if not raw_text:
        return []
    parts = re.split(r"[,\n]+", raw_text)
    return [item.strip() for item in parts if item and item.strip()]


def main() -> None:
    st.set_page_config(page_title="A 股量化监控系统", page_icon="📈", layout="wide")
    st.title("📈 A 股量化监控系统")

    config = load_config()
    config_symbols = config.get("target_symbols", [])
    default_symbols_text = ", ".join(config_symbols) if config_symbols else "sh600519, sz000001"
    target_days = int(config.get("target_days", 200))

    with st.sidebar:
        st.header("配置")
        symbols_input = st.text_area(
            "请输入自选股代码（逗号或换行分隔）",
            value=default_symbols_text,
            key="target_symbols_input",
            help="示例: sh600519, sz000001 或每行一个代码。",
        )
        webhook = st.text_input(
            "飞书 Webhook",
            type="password",
            placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/...",
            help="不填写则不发送飞书提醒。",
            key="feishu_webhook_input",
        )
        run_mode = st.radio("运行模式", options=["实时", "收盘"], horizontal=True, key="run_mode")
        run_analysis = st.button("执行分析", type="primary", use_container_width=True, key="run_analysis")

    input_symbols = parse_symbols_input(symbols_input)
    if input_symbols:
        target_symbols = input_symbols
    elif config_symbols:
        target_symbols = config_symbols
    else:
        target_symbols = []

    if not target_symbols:
        st.warning("请先输入股票代码")
        return

    st.subheader("本次分析标的")
    selected_symbols = st.multiselect(
        "临时勾选/剔除股票",
        options=target_symbols,
        default=target_symbols,
        key="target_symbols_selector",
    )

    if not selected_symbols:
        st.warning("请至少选择一只股票后再执行分析。")
        return

    if webhook and not webhook.startswith(FEISHU_WEBHOOK_PREFIX):
        st.warning("Webhook 地址格式不正确，请输入飞书官方机器人地址。")
        return

    if not run_analysis:
        st.info("请点击左侧“执行分析”按钮开始扫描。")
        return

    sectors = []
    monitor_results = []
    alerts = []
    sentiment_values = []
    total_fund_net = 0.0

    with st.spinner(f"正在执行{run_mode}模式分析，请稍候..."):
        try:
            sectors = fetch_top_sectors(5)
        except Exception as exc:
            st.warning(f"获取领涨板块失败: {exc}")

        for symbol in selected_symbols:
            try:
                df = fetch_daily_data(symbol=symbol, days=target_days)
                if df is None or df.empty:
                    st.warning(f"{symbol} 日线数据为空，已跳过。")
                    continue

                sentiment = fetch_sentiment_score(symbol)
                fund_data = fetch_fund_flow(symbol)

                if isinstance(sentiment, (int, float)):
                    sentiment_values.append(float(sentiment))
                total_fund_net += parse_fund_net_amount(fund_data)

                monitor = StrategyMonitor(
                    df=df,
                    symbol=symbol,
                    sentiment_score=float(sentiment) if isinstance(sentiment, (int, float)) else 0.0,
                    fund_data=fund_data,
                )
                latest = monitor.get_latest_signal()
                if latest:
                    monitor_results.append(latest)
                    if latest.get("has_warning"):
                        alerts.append(latest)
            except Exception as exc:
                st.warning(f"处理 {symbol} 时发生错误: {exc}")

    avg_sentiment = round(sum(sentiment_values) / len(sentiment_values), 2) if sentiment_values else 0.0
    top_sector_name = sectors[0].get("板块名称", "N/A") if sectors else "N/A"
    if sectors:
        try:
            top_sector_delta = f"{float(sectors[0].get('涨跌幅', 0)):+.2f}%"
        except (ValueError, TypeError):
            top_sector_delta = "N/A"
    else:
        top_sector_delta = "N/A"

    metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)
    metric_col_1.metric("市场情绪得分", avg_sentiment)
    metric_col_2.metric("领涨板块", top_sector_name, delta=top_sector_delta)
    metric_col_3.metric("主力净流入(万元)", f"{total_fund_net:,.0f}")
    metric_col_4.metric("预警数量", len(alerts))

    st.subheader("领涨板块")
    if sectors:
        sectors_df = pd.DataFrame(sectors)
        st.dataframe(sectors_df, use_container_width=True, hide_index=True)
    else:
        st.warning("未获取到领涨板块数据。")

    st.subheader("策略扫描结果")
    if monitor_results:
        results_df = pd.DataFrame(monitor_results)
        show_cols = [col for col in RESULT_COLUMNS if col in results_df.columns]
        st.dataframe(results_df[show_cols] if show_cols else results_df, use_container_width=True, hide_index=True)
    else:
        st.warning("扫描结果为空，可能是数据源异常或全部标的获取失败。")

    if webhook and monitor_results:
        try:
            notifier = FeishuNotifier(webhook_url=webhook)
            notifier.send_signal_alert(
                symbol="SYSTEM",
                trigger_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                reason=f"{run_mode}模式分析完成，共扫描{len(monitor_results)}只股票",
                current_price=0.0,
            )
            st.success("分析完成，已发送飞书提醒。")
        except Exception as exc:
            st.warning(f"分析已完成，但飞书提醒发送失败: {exc}")


if __name__ == "__main__":
    main()
