# -*- coding: utf-8 -*-
"""
A股量化监控管线 - Streamlit 浏览器入口
将 main.py 的监控管线（多维数据获取 → 策略分析 → 播报/记录）以交互方式暴露在浏览器中。

用法:
    streamlit run monitor_app.py
"""
import json
import logging
import os
from datetime import datetime

import pandas as pd
import streamlit as st

from src.data_sources import (
    fetch_daily_data,
    fetch_realtime_data,
    fetch_fund_flow,
    fetch_top_sectors,
    fetch_sentiment_score,
)
from src.strategy_monitor import run_monitor_for_stocks
from src.notifier import FeishuNotifier
from src import analytics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

# 监控结果表中需要展示的列（与终端报告对齐）
RESULTS_DISPLAY_COLS = [
    "symbol", "close", "pct_change", "total_score", "market_state",
    "confidence", "tech_score", "vol_score", "fund_score", "sentiment_score",
    "recommended_position", "suggestion", "risk_level",
]

RESULTS_DISPLAY_NAMES = {
    "symbol": "代码", "close": "收盘", "pct_change": "涨跌%",
    "total_score": "综合评分", "market_state": "市场状态", "confidence": "置信度",
    "tech_score": "技术面", "vol_score": "量价面", "fund_score": "资金面",
    "sentiment_score": "舆情面", "recommended_position": "建议仓位%",
    "suggestion": "建议", "risk_level": "风险等级",
}

EXAMPLE_CONFIG = {
    "target_symbols": ["sh600519", "sz000858"],
    "target_days": 200,
    "feishu_webhook": "",
    "notification": {"enable_feishu": False},
    "caixin_api_key": "",
    "ai_analyst": {"enabled": False, "api_key": "", "base_url": "https://apihub.agnes-ai.com/v1", "model": "agnes-2.0-flash"},
}

FEISHU_WEBHOOK_PREFIX = "https://open.feishu.cn/open-apis/bot/v2/hook/"

st.set_page_config(page_title="A股量化监控台", page_icon="📈", layout="wide")


def _validate_feishu_webhook(url: str) -> bool:
    """SSRF 防护：仅允许飞书官方 Bot Webhook 域名"""
    return url.startswith(FEISHU_WEBHOOK_PREFIX)


def load_config(config_path: str = "config.json"):
    """加载配置；缺失/畸形时给出内联示例而非硬崩溃"""
    if not os.path.exists(config_path):
        st.error(f"找不到配置文件 `{config_path}`，请在仓库根目录创建。示例如下：")
        st.json(EXAMPLE_CONFIG)
        return None
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        st.error(f"`{config_path}` 格式损坏（{e}），请参考以下示例修复：")
        st.json(EXAMPLE_CONFIG)
        return None


def fetch_pipeline_data(symbols: list, days: int, caixin_key: str = ""):
    """阶段1: 多维数据获取（与 main.py 管线一致）"""
    from src.caixin_data import init_caixin_client, fetch_caixin_sentiment

    stock_data_dict, extra_data = {}, {}
    progress = st.progress(0.0, text="开始获取多维数据…")

    try:
        sectors = fetch_top_sectors(5)
    except Exception as e:
        logger.warning(f"板块数据获取失败: {e}")
        sectors = []

    for i, symbol in enumerate(symbols):
        progress.progress((i + 1) / (len(symbols) + 1), text=f"处理 {symbol}…")
        try:
            df = fetch_daily_data(symbol=symbol, days=days)
            if df.empty:
                st.warning(f"{symbol} 数据为空，已跳过")
                continue

            stock_data_dict[symbol] = df
            fund_data = fetch_fund_flow(symbol)
            sentiment = fetch_sentiment_score(symbol)
            if caixin_key:
                try:
                    caixin_sent = fetch_caixin_sentiment(symbol)
                    if caixin_sent != 0:
                        sentiment = sentiment * 0.4 + caixin_sent * 0.6
                except Exception:
                    pass
            realtime = fetch_realtime_data(symbol)

            extra_data[symbol] = {"sentiment": sentiment, "fund_data": fund_data, "realtime": realtime}
        except Exception as e:
            st.warning(f"{symbol} 处理失败: {e}")
            continue

    progress.progress(1.0, text="数据获取完成")
    return stock_data_dict, extra_data, sectors


def main():
    st.title("📈 A股量化监控台")
    st.caption("与 `main.py` 同源的监控管线，浏览器交互版")

    # ---------- Sidebar ----------
    with st.sidebar:
        st.header("⚙️ 运行配置")
        webhook = st.text_input(
            "飞书 Webhook（可选）",
            value="",
            type="password",
            help="仅接受飞书官方 Bot 地址，用于运行后推送播报",
        )
        if webhook and not _validate_feishu_webhook(webhook):
            st.error(f"Webhook 不合法：必须以 `{FEISHU_WEBHOOK_PREFIX}` 开头")
            webhook = ""

        mode_label = st.radio(
            "运行模式",
            ["实时监控（盘中）", "收盘总结（收盘后）", "胜率评估（仅分析）"],
            index=0,
        )
        mode = {"实时监控（盘中）": "mid", "收盘总结（收盘后）": "end", "胜率评估（仅分析）": "analytics-only"}[mode_label]

        run_clicked = st.button("🚀 运行", type="primary", use_container_width=True)

    config = load_config()
    if config is None:
        return

    # ---------- 胜率评估模式：不跑管线 ----------
    if run_clicked and mode == "analytics-only":
        st.subheader("🎯 历史建议胜率评估")
        with st.spinner("评估 3/5/10 天历史建议准确率…"):
            analytics.init_db()
            accuracy = analytics.evaluate_accuracy(days_list=[3, 5, 10])
        if not accuracy:
            st.info("暂无历史建议记录。使用「收盘总结」模式运行后会自动记录建议。")
        else:
            cols = st.columns(len(accuracy))
            for col, (days, data) in zip(cols, accuracy.items()):
                col.metric(
                    f"{days} 天胜率",
                    f"{data['rate']:.0%}",
                    f"{data['correct']}/{data['total']} 条",
                )
            st.dataframe(
                pd.DataFrame([{"周期": f"{d}天", "样本数": v["total"], "命中": v["correct"], "胜率": f"{v['rate']:.0%}"} for d, v in accuracy.items()]),
                use_container_width=True,
            )
        return

    if not run_clicked:
        st.info("左侧选择模式后点击「运行」开始监控管线")
        return

    # ---------- 阶段1: 数据获取 ----------
    symbols = config.get("target_symbols", [])
    if not symbols:
        st.error("`config.json` 中 target_symbols 为空，请补充自选股列表")
        return
    days = config.get("target_days", 200)
    caixin_key = config.get("caixin_api_key", "")

    st.subheader(f"🛰️ 监控管线 | {len(symbols)} 只标的")
    with st.spinner("阶段1: 获取多维数据（K线/资金/舆情/实时行情）…"):
        stock_data_dict, extra_data, sectors = fetch_pipeline_data(symbols, days, caixin_key)

    if not stock_data_dict:
        st.error("所有股票数据获取失败，请检查网络或数据源")
        return

    # ---------- 阶段2: 策略分析 ----------
    with st.spinner("阶段2: 执行多维策略分析…"):
        alerts, results = run_monitor_for_stocks(stock_data_dict, extra_data)

    # ---------- 收盘总结模式: 记录建议并评估 ----------
    accuracy = None
    if mode == "end":
        with st.spinner("记录收盘建议并评估历史胜率…"):
            analytics.init_db()
            for r in results:
                try:
                    analytics.record_suggestion(
                        symbol=r["symbol"],
                        date=datetime.now().strftime("%Y-%m-%d"),
                        price=float(r.get("close", 0) or 0),
                        suggestion=r.get("suggestion", ""),
                        market_state=r.get("market_state", ""),
                    )
                except Exception as e:
                    logger.warning(f"记录 {r.get('symbol')} 建议失败: {e}")
            accuracy = analytics.evaluate_accuracy(days_list=[3, 5, 10])

    # ---------- Tab 展示 ----------
    tab_overview, tab_signals = st.tabs(["📊 市场概览", "🚨 策略警报"])

    with tab_overview:
        sentiments = [r.get("sentiment_score", 0) or 0 for r in results]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0

        top_sector = sectors[0] if sectors else None
        top_sector_text = (
            f"{top_sector.get('板块名称', 'N/A')} ({top_sector.get('涨跌幅', 0):+.2f}%)"
            if top_sector else "暂无数据"
        )

        total_inflow = 0.0
        for ed in extra_data.values():
            fd = ed.get("fund_data") or {}
            total_inflow += fd.get("main_net_inflow", 0) or 0

        c1, c2, c3 = st.columns(3)
        c1.metric("平均舆情评分", f"{avg_sentiment:+.1f}", help="所有标的 sentiment_score 均值")
        c2.metric("领涨板块", top_sector_text)
        c3.metric("主力净流入合计", f"{total_inflow / 1e8:.2f} 亿", help="自选股当日主力净流入求和")

        if sectors:
            st.markdown("#### 今日领涨板块 Top5")
            st.dataframe(pd.DataFrame(sectors), use_container_width=True, hide_index=True)
        else:
            st.caption("板块数据暂不可用")

        if mode == "end":
            st.markdown("#### 🎯 收盘建议已记录 & 胜率评估")
            if accuracy:
                cols = st.columns(len(accuracy))
                for col, (d, v) in zip(cols, accuracy.items()):
                    col.metric(f"{d} 天胜率", f"{v['rate']:.0%}", f"{v['correct']}/{v['total']} 条")
            else:
                st.caption("历史样本不足，暂无胜率数据（持续使用「收盘总结」模式会逐步积累）")

    with tab_signals:
        st.markdown(f"#### 监控结果（{len(results)} 只）")
        if results:
            df_results = pd.DataFrame(results)
            display_cols = [c for c in RESULTS_DISPLAY_COLS if c in df_results.columns]
            st.dataframe(
                df_results[display_cols].rename(columns=RESULTS_DISPLAY_NAMES),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("无监控结果")

        st.divider()
        st.markdown(f"#### 风控预警（{len(alerts)} 条）")
        if alerts:
            st.dataframe(
                pd.DataFrame([
                    {"代码": a.get("symbol", ""), "预警": "；".join(a.get("warnings", []))}
                    for a in alerts
                ]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success("✅ 全部标的通过风控检查，无预警")

    # ---------- 飞书播报 ----------
    if webhook:
        with st.spinner("推送飞书播报…"):
            try:
                market_overview = ""
                if sectors:
                    market_overview = "今日领涨: " + ", ".join(
                        [f"{s.get('板块名称', '')}({s.get('涨跌幅', 0):+.1f}%)" for s in sectors[:3]]
                    )
                notifier = FeishuNotifier(webhook_url=webhook)
                notifier.send_broadcast(mode if mode != "analytics-only" else "mid", results, alerts, market_overview=market_overview)
                st.success("📨 飞书播报已发送")
            except Exception as e:
                st.error(f"飞书播报发送失败: {e}")


if __name__ == "__main__":
    main()
