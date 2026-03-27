import json
import os
import logging
import streamlit as st
import pandas as pd
from datetime import datetime

from src.data_fetcher import fetch_top_sectors, fetch_sentiment_score, fetch_fund_flow, fetch_daily_data
from src.strategy_monitor import run_monitor_for_stocks
from src.notifier import FeishuNotifier
from src.analytics import evaluate_accuracy, record_suggestion

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

# 运行模式映射
MODE_MAP = {
    "实时监控": "mid",
    "收盘总结": "end",
    "胜率评估": "accuracy",
}

# 监控结果展示列
RESULTS_DISPLAY_COLS = ["symbol", "date", "close", "pct_change", "SMA_5", "SMA_10", "SMA_20",
                        "RSI_14", "MACD_DIF", "MACD_DEA", "tech_score", "chip_score",
                        "sentiment_score", "total_score", "market_state", "suggestion", "has_warning"]

# 预警展示列
ALERTS_DISPLAY_COLS = ["symbol", "date", "close", "pct_change", "market_state",
                       "suggestion", "sell_warning", "unusual_drop_warning"]


FEISHU_WEBHOOK_PREFIX = "https://open.feishu.cn/open-apis/bot/v2/hook/"


def _validate_feishu_webhook(url: str) -> bool:
    """只允许飞书官方 Webhook 前缀，防止 SSRF 攻击。"""
    return url.startswith(FEISHU_WEBHOOK_PREFIX)


def load_config() -> dict | None:
    """加载配置文件，失败时返回 None 并通过 st.error 提示用户。"""
    if not os.path.exists(CONFIG_PATH):
        st.error(
            f"⚠️ 找不到配置文件 `config.json`（路径: {CONFIG_PATH}）。\n\n"
            "请在项目根目录创建 `config.json`，示例格式：\n"
            "```json\n"
            '{\n  "target_symbols": ["sh600519", "sz000858"],\n'
            '  "target_days": 200,\n'
            '  "feishu_webhook": ""\n'
            "}\n```"
        )
        return None
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        st.error(f"⚠️ 配置文件 `config.json` 格式错误，无法解析：{exc}")
        return None


def main():
    st.set_page_config(
        page_title="A 股量化监控看板",
        page_icon="📈",
        layout="wide",
    )

    st.title("📈 A 股量化监控系统")

    # ── 侧边栏 ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ 参数配置")

        feishu_webhook = st.text_input(
            "飞书 Webhook 地址",
            type="password",
            placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/...",
            help="留空则不发送飞书通知",
        )

        run_mode_label = st.selectbox(
            "运行模式",
            options=list(MODE_MAP.keys()),
            index=0,
            help="实时监控：午盘状态播报；收盘总结：终盘复盘+胜率记录；胜率评估：仅展示历史胜率",
        )
        run_mode = MODE_MAP[run_mode_label]

        st.divider()
        run_button = st.button("🚀 开始执行", use_container_width=True, type="primary")

    # ── 主界面占位 ────────────────────────────────────────────────────────────
    tab_overview, tab_alerts = st.tabs(["🌐 市场概览", "🚨 策略警报"])

    if not run_button:
        with tab_overview:
            st.info("点击左侧「🚀 开始执行」按钮以获取最新市场数据。")
        with tab_alerts:
            st.info("点击左侧「🚀 开始执行」按钮以运行策略监控。")
        return

    # ── 加载配置 ──────────────────────────────────────────────────────────────
    config = load_config()
    if config is None:
        return

    target_symbols: list = config.get("target_symbols", [])
    target_days: int = config.get("target_days", 200)
    # 侧边栏输入的 Webhook 优先于配置文件中的值
    webhook_url: str = feishu_webhook or config.get("feishu_webhook", "")

    # 校验 Webhook 地址，防止 SSRF
    if webhook_url and not _validate_feishu_webhook(webhook_url):
        st.error(
            "⚠️ Webhook 地址不合法，仅允许飞书官方 Webhook（需以 "
            f"`{FEISHU_WEBHOOK_PREFIX}` 开头）。请检查后重试。"
        )
        return

    if not target_symbols:
        st.warning("⚠️ `config.json` 中的 `target_symbols` 列表为空，请添加自选股后重试。")
        return

    # ── 胜率评估专属逻辑 ──────────────────────────────────────────────────────
    if run_mode == "accuracy":
        with st.spinner("正在评估历史胜率，请稍候..."):
            try:
                accuracy_data = evaluate_accuracy(days_list=[3, 5, 10])
            except Exception as exc:
                st.error(f"胜率评估失败：{exc}")
                return

        with tab_overview:
            st.subheader("🏆 历史胜率看板")
            if accuracy_data:
                cols = st.columns(len(accuracy_data))
                for col, (days_key, stats) in zip(cols, accuracy_data.items()):
                    col.metric(
                        label=f"过去 {days_key} 天胜率",
                        value=f"{stats.get('rate', 0):.1%}",
                        delta=f"共 {stats.get('total', 0)} 次判定",
                    )
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "周期（天）": k,
                                "判定次数": v.get("total", 0),
                                "正确次数": v.get("correct", 0),
                                "胜率": f"{v.get('rate', 0):.1%}",
                            }
                            for k, v in accuracy_data.items()
                        ]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("暂无足够的历史数据可供评估，请先以「收盘总结」模式运行若干天后再查看。")

        with tab_alerts:
            st.info("胜率评估模式下不执行策略扫描。")
        return

    # ── 数据获取 & 策略运行（实时监控 / 收盘总结） ───────────────────────────
    sectors = []
    stock_data_dict: dict = {}
    extra_data: dict = {}
    alerts: list = []
    monitor_results: list = []

    with st.spinner("⏳ 正在获取市场数据，请耐心等待..."):
        # 1. 板块概览
        try:
            sectors = fetch_top_sectors(5)
        except Exception as exc:
            st.warning(f"获取领涨板块失败，已跳过：{exc}")
            sectors = []

        # 2. 各股历史数据 + 情绪与资金
        for symbol in target_symbols:
            try:
                df = fetch_daily_data(symbol=symbol, days=target_days)
                if df is None or df.empty:
                    st.warning(f"⚠️ {symbol} 历史数据为空，已跳过。")
                    continue
                stock_data_dict[symbol] = df

                sent = fetch_sentiment_score(symbol)
                fund = fetch_fund_flow(symbol)
                extra_data[symbol] = {"sentiment": sent, "fund_data": fund}
            except Exception as exc:
                st.warning(f"⚠️ 获取 {symbol} 数据失败，已跳过：{exc}")
                continue

        # 3. 策略监控
        if stock_data_dict:
            try:
                alerts, monitor_results = run_monitor_for_stocks(stock_data_dict, extra_data)
            except Exception as exc:
                st.error(f"策略监控执行失败：{exc}")
                return

    # ── 市场概览板块 ──────────────────────────────────────────────────────────
    with tab_overview:
        st.subheader("📊 市场情绪 & 资金流向")

        # 汇总所有自选股的情绪得分均值
        all_sentiments = [
            v["sentiment"]
            for v in extra_data.values()
            if isinstance(v.get("sentiment"), (int, float))
        ]
        avg_sentiment = round(sum(all_sentiments) / len(all_sentiments), 2) if all_sentiments else 0.0

        # 领涨板块（取第一名名称与涨幅）
        top_sector_name = sectors[0].get("板块名称", "N/A") if sectors else "N/A"
        top_sector_pct = f"+{sectors[0].get('涨跌幅', 0):.2f}%" if sectors else "N/A"

        # 资金净流入（汇总所有自选股主力净额）
        total_fund_net = 0.0
        for sym_data in extra_data.values():
            fund_raw = sym_data.get("fund_data", {}).get("主力净流入-净额", 0)
            try:
                if isinstance(fund_raw, str):
                    fund_raw = float(fund_raw.replace(",", "").replace("万", "")) if fund_raw else 0
                total_fund_net += float(fund_raw)
            except (ValueError, TypeError):
                pass

        col1, col2, col3 = st.columns(3)
        col1.metric(
            label="📰 市场情绪得分（均值）",
            value=avg_sentiment,
            delta="利好 > 0 / 利空 < 0",
        )
        col2.metric(
            label="🏆 今日领涨板块",
            value=top_sector_name,
            delta=top_sector_pct,
        )
        col3.metric(
            label="💰 自选股主力净流入（万元）",
            value=f"{total_fund_net:,.0f}",
            delta="正为净流入 / 负为净流出",
        )

        # 展示领涨板块列表
        if sectors:
            st.subheader("📋 今日领涨板块 Top 5")
            sectors_df = pd.DataFrame(sectors)
            display_cols = [c for c in ["板块名称", "涨跌幅", "成交额"] if c in sectors_df.columns]
            st.dataframe(sectors_df[display_cols] if display_cols else sectors_df, use_container_width=True, hide_index=True)

        # 收盘总结时展示胜率
        if run_mode == "end":
            st.divider()
            st.subheader("🏆 本次胜率评估（已自动记录今日建议）")
            try:
                today_str = datetime.now().strftime("%Y-%m-%d")
                for res in monitor_results:
                    record_suggestion(
                        res.get("symbol", ""),
                        today_str,
                        res.get("close", 0.0),
                        res.get("suggestion", "建议观望"),
                        res.get("market_state", "Neutral"),
                    )
                accuracy_data = evaluate_accuracy(days_list=[3, 5, 10])
                if accuracy_data:
                    acc_cols = st.columns(len(accuracy_data))
                    for col, (days_key, stats) in zip(acc_cols, accuracy_data.items()):
                        col.metric(
                            label=f"过去 {days_key} 天胜率",
                            value=f"{stats.get('rate', 0):.1%}",
                            delta=f"共 {stats.get('total', 0)} 次",
                        )
                else:
                    st.info("暂无足够历史数据进行胜率评估。")
            except Exception as exc:
                st.warning(f"胜率评估出错：{exc}")

    # ── 策略警报板块 ──────────────────────────────────────────────────────────
    with tab_alerts:
        st.subheader("📋 所有自选股最新监控状态")

        if monitor_results:
            results_df = pd.DataFrame(monitor_results)
            # 格式化数值列
            float_cols = ["close", "pct_change", "SMA_5", "SMA_10", "SMA_20", "RSI_14", "MACD_DIF", "MACD_DEA"]
            for col in float_cols:
                if col in results_df.columns:
                    results_df[col] = results_df[col].apply(lambda x: round(float(x), 4) if pd.notna(x) else x)
            display_cols = [c for c in RESULTS_DISPLAY_COLS if c in results_df.columns]
            st.dataframe(results_df[display_cols] if display_cols else results_df, use_container_width=True, hide_index=True)
        else:
            st.info("未获取到任何自选股的监控数据。")

        st.divider()
        st.subheader("⚠️ 风控预警信号")

        if alerts:
            st.error(f"🚨 发现 {len(alerts)} 个风控预警！")
            alerts_df = pd.DataFrame(alerts)
            display_cols = [c for c in ALERTS_DISPLAY_COLS if c in alerts_df.columns]
            st.dataframe(alerts_df[display_cols] if display_cols else alerts_df, use_container_width=True, hide_index=True)
        else:
            st.success("✅ 当前所有自选股均无风控预警。")

    # ── 飞书通知 ──────────────────────────────────────────────────────────────
    if webhook_url:
        market_overview = ""
        if sectors:
            market_overview = "今日领涨板块：\n" + "\n".join(
                [f" - {s.get('板块名称', '')} (+{s.get('涨跌幅', 0)}%)" for s in sectors]
            )

        accuracy_data_for_notify = None
        if run_mode == "end":
            try:
                accuracy_data_for_notify = evaluate_accuracy(days_list=[3, 5, 10])
            except Exception:
                pass

        notifier = FeishuNotifier(webhook_url=webhook_url)
        try:
            notify_mode = run_mode  # "mid" or "end"
            notifier.send_broadcast(
                notify_mode,
                monitor_results,
                alerts,
                market_overview=market_overview,
                accuracy_data=accuracy_data_for_notify,
            )
            st.success("✅ 已成功发送飞书通知！")
        except Exception as exc:
            st.warning(f"飞书通知发送失败：{exc}")


if __name__ == "__main__":
    main()
