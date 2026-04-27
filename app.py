import os
import sys

# Ensure src imports work in Codespaces/local/CI no matter the launch cwd.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(CURRENT_DIR, "src")
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

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
from src.analysis_report import StockAnalysisReport
from src.reasoning_engine import ReasoningEngine


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


SYMBOL_PRESETS = {
    "白酒龙头": "600519,000858,000568",
    "银行权重": "600036,600000,601398",
    "新能源": "300750,002594,601012",
    "半导体": "688981,603501,300223",
}


def inject_custom_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700;800&family=Space+Grotesk:wght@600;700&display=swap');

        :root {
            --bg-soft: #f3f8f7;
            --card: #ffffff;
            --brand: #006c67;
            --brand-soft: #d6f0eb;
            --accent: #f55d3e;
            --text-main: #102a43;
            --text-sub: #486581;
        }

        html, body, [data-testid="stAppViewContainer"] {
            font-family: 'Noto Sans SC', sans-serif;
            color: var(--text-main);
            background:
                radial-gradient(circle at 10% 10%, #fef4ea 0%, rgba(254, 244, 234, 0) 36%),
                radial-gradient(circle at 90% 0%, #d9f5ef 0%, rgba(217, 245, 239, 0) 40%),
                linear-gradient(170deg, #f5fbfa 0%, #eef6f7 100%);
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #12343b 0%, #1f4a52 100%);
        }

        [data-testid="stSidebar"] * {
            color: #f5fffc;
        }

        [data-testid="stMetric"] {
            background: var(--card);
            border: 1px solid #d9e2ec;
            border-radius: 14px;
            padding: 12px 14px;
            box-shadow: 0 10px 22px rgba(16, 42, 67, 0.08);
        }

        .hero-panel {
            background: linear-gradient(110deg, #0b3c49 0%, #006c67 48%, #3aa17e 100%);
            border-radius: 18px;
            padding: 20px 22px;
            margin-bottom: 12px;
            color: #f5fffc;
            box-shadow: 0 16px 40px rgba(16, 42, 67, 0.18);
        }

        .hero-title {
            margin: 0;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 28px;
            font-weight: 700;
            letter-spacing: 0.4px;
        }

        .hero-sub {
            margin: 6px 0 0;
            color: #ddfff4;
            font-size: 14px;
        }

        .tag-chip {
            display: inline-block;
            margin-top: 8px;
            background: rgba(255, 255, 255, 0.18);
            border: 1px solid rgba(255, 255, 255, 0.25);
            border-radius: 999px;
            padding: 3px 12px;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.2px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def build_results_table(monitor_results: list[dict]) -> pd.DataFrame:
    if not monitor_results:
        return pd.DataFrame()

    results_df = pd.DataFrame(monitor_results)
    show_cols = [col for col in RESULT_COLUMNS if col in results_df.columns]
    return results_df[show_cols] if show_cols else results_df


def render_price_charts(raw_data_cache: dict[str, pd.DataFrame]) -> None:
    if not raw_data_cache:
        st.info("暂无可绘制价格数据，先执行分析后查看图表。")
        return

    chart_symbol = st.selectbox("选择图表标的", options=list(raw_data_cache.keys()), key="chart_symbol")
    raw_df = raw_data_cache.get(chart_symbol, pd.DataFrame()).copy()
    if raw_df.empty:
        st.warning("当前标的暂无原始数据。")
        return

    raw_df.columns = [str(c).strip() for c in raw_df.columns]
    possible_date_cols = ["日期", "date", "Date"]
    possible_price_cols = ["收盘", "close", "Close"]
    date_col = next((c for c in possible_date_cols if c in raw_df.columns), None)
    close_col = next((c for c in possible_price_cols if c in raw_df.columns), None)

    if not date_col or not close_col:
        st.warning("原始数据字段不完整，无法绘制趋势图。")
        return

    plot_df = raw_df[[date_col, close_col]].dropna().copy()
    plot_df[date_col] = pd.to_datetime(plot_df[date_col], errors="coerce")
    plot_df[close_col] = pd.to_numeric(plot_df[close_col], errors="coerce")
    plot_df = plot_df.dropna().sort_values(date_col)
    if plot_df.empty:
        st.warning("清洗后没有可用数据点，无法绘图。")
        return

    st.line_chart(plot_df.set_index(date_col)[close_col], height=320)
    latest_close = float(plot_df[close_col].iloc[-1])
    first_close = float(plot_df[close_col].iloc[0])
    pct_move = ((latest_close - first_close) / first_close * 100.0) if first_close else 0.0
    st.caption(f"{chart_symbol} 期间累计涨跌幅: {pct_move:+.2f}%")


def render_detailed_analysis(monitor_results: list[dict], financial_data_cache: dict = None) -> None:
    """Phase 2 新增：详细分析报告展示"""
    if not monitor_results:
        st.info("暂无分析结果")
        return
    
    financial_data_cache = financial_data_cache or {}
    
    # 创建股票选择
    selected_symbols = st.multiselect(
        "选择要查看详细分析的股票",
        options=[r.get('symbol') for r in monitor_results],
        default=[r.get('symbol') for r in monitor_results[:1]] if monitor_results else [],
        key="detail_symbol_selector"
    )
    
    if not selected_symbols:
        st.info("请选择至少一只股票查看详细分析")
        return
    
    for symbol in selected_symbols:
        # 找到对应的信号数据
        signal = next((r for r in monitor_results if r.get('symbol') == symbol), None)
        if not signal:
            continue
        
        # 生成分析报告
        fin_data = financial_data_cache.get(symbol, {})
        report = StockAnalysisReport(
            symbol=symbol,
            latest_signal=signal,
            financial_data=fin_data,
            warnings=signal.get('warnings', [])
        )
        
        # 展示报告卡片
        with st.container():
            st.markdown(f"### 📊 {symbol} - 详细分析报告")
            
            # 摘要卡片
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("综合评分", f"{report.total_score:.2f}")
            with col2:
                st.metric("市场状态", report.market_state)
            with col3:
                st.metric("风险等级", report.risk_level)
            with col4:
                st.metric("信心度", f"{report.confidence:.0%}")
            
            # 建议卡片
            st.info(f"💡 {report.summary}")
            
            # 多维评分
            score_col1, score_col2, score_col3, score_col4 = st.columns(4)
            with score_col1:
                st.markdown(f"📈 **技术面**: {report.metrics['tech_score']:+.1f}")
            with score_col2:
                st.markdown(f"💰 **筹码面**: {report.metrics['chip_score']:+.1f}")
            with score_col3:
                st.markdown(f"📋 **基本面**: {report.metrics['fundamental_score']:+.1f}")
            with score_col4:
                st.markdown(f"📰 **情绪面**: {report.metrics['sentiment_score']:+.1f}")
            
            # 详细文字解读
            with st.expander("📖 详细分析解读（点击展开）", expanded=False):
                st.markdown(report.detailed_reasoning)
            
            # 风控预警
            if report.warnings:
                with st.expander(f"⚠️ 风控预警（{len(report.warnings)} 条）", expanded=True):
                    for warning in report.warnings:
                        st.warning(warning)
            else:
                st.success("✅ 暂无风控预警")
            
            st.divider()


def infer_exchange_prefix(code: str) -> str:
    if code.startswith(("60", "68", "90")):
        return "sh"
    if code.startswith(("00", "001", "002", "003", "20", "30")):
        return "sz"
    if code.startswith(("4", "8")):
        return "bj"
    return "sz"


def parse_fund_net_amount(fund_data: dict) -> float:
    raw_val = fund_data.get("主力净流入-净额", 0)
    if isinstance(raw_val, str):
        raw_val = raw_val.replace(",", "").replace("万", "").strip()
    try:
        return float(raw_val)
    except (ValueError, TypeError):
        return 0.0


def parse_symbols_input(raw_text: str) -> tuple[list[str], list[str], list[str]]:
    if not raw_text:
        return [], [], []

    raw_tokens = re.split(r"[,，;；、\s\n]+", raw_text.strip())
    seen: set[str] = set()
    normalized: list[str] = []
    invalid_tokens: list[str] = []
    unsupported_tokens: list[str] = []

    for token in raw_tokens:
        if not token:
            continue
        cleaned = token.strip().lower()
        match = re.fullmatch(r"(?:(sh|sz|bj))?(\d{6})", cleaned)
        if not match:
            invalid_tokens.append(token)
            continue

        prefix, code = match.groups()
        if not prefix:
            prefix = infer_exchange_prefix(code)

        # Current downstream fund-flow API expects sh/sz market.
        if prefix not in {"sh", "sz"}:
            unsupported_tokens.append(token)
            continue

        symbol = f"{prefix}{code}"
        if symbol not in seen:
            seen.add(symbol)
            normalized.append(symbol)

    return normalized, invalid_tokens, unsupported_tokens


def main() -> None:
    st.set_page_config(page_title="A 股量化监控系统", page_icon="📈", layout="wide")
    inject_custom_styles()
    st.markdown(
        """
        <div class="hero-panel">
            <h1 class="hero-title">A 股量化监控操作台</h1>
            <p class="hero-sub">输入股票代码后可直接执行分析、查看评分、观察价格趋势，并一键发送飞书提醒。</p>
            <span class="tag-chip">AkShare 实时驱动</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "analysis_cache" not in st.session_state:
        st.session_state["analysis_cache"] = {
            "sectors": [],
            "monitor_results": [],
            "alerts": [],
            "avg_sentiment": 0.0,
            "total_fund_net": 0.0,
            "run_mode": "实时",
        }

    default_symbols_text = st.session_state.get("last_symbols_input", "")
    default_days = int(st.session_state.get("last_target_days", 200))
    default_webhook = st.session_state.get("last_webhook", "")

    with st.sidebar:
        st.header("配置")

        preset_name = st.selectbox("快速模板", options=["自定义"] + list(SYMBOL_PRESETS.keys()), key="symbol_preset")
        if preset_name != "自定义":
            preset_symbols = SYMBOL_PRESETS[preset_name]
            if st.button("填充模板股票", width="stretch", key="apply_preset"):
                st.session_state["target_symbols_input"] = preset_symbols
                symbols_input = preset_symbols
                st.rerun()

        symbols_input = st.text_area(
            "请输入自选股代码（逗号或换行分隔）",
            value=default_symbols_text,
            key="target_symbols_input",
            help="示例: 600519, 000001 或每行一个代码。",
        )
        target_days = st.number_input(
            "回看交易日数量",
            min_value=30,
            max_value=1000,
            value=max(30, default_days),
            key="target_days_input",
            help="用于拉取历史 K 线数据并计算指标。",
        )
        webhook = st.text_input(
            "飞书 Webhook",
            type="password",
            value=default_webhook,
            placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/...",
            help="不填写则不发送飞书提醒。",
            key="feishu_webhook_input",
        )
        run_mode = st.radio("运行模式", options=["实时", "收盘"], horizontal=True, key="run_mode")
        run_analysis = st.button("执行分析", type="primary", width="stretch", key="run_analysis")

    st.session_state["last_symbols_input"] = symbols_input
    st.session_state["last_target_days"] = int(target_days)
    st.session_state["last_webhook"] = webhook

    target_symbols, invalid_tokens, unsupported_tokens = parse_symbols_input(symbols_input)

    if invalid_tokens:
        st.warning(f"⚠️ 检测到无效代码并已忽略: {', '.join(invalid_tokens)}")
    if unsupported_tokens:
        st.warning(f"⚠️ 检测到暂不支持的非沪深代码并已忽略: {', '.join(unsupported_tokens)}")

    if not target_symbols:
        st.error("❌ 请先输入至少一个有效 6 位股票代码（如 600519 或 000001）。")
        return

    st.subheader("本次分析标的")
    selected_symbols = st.multiselect(
        "临时勾选/剔除股票",
        options=target_symbols,
        default=target_symbols,
        key="target_symbols_selector",
    )

    if not selected_symbols:
        st.error("❌ 请至少选择一只股票后再执行分析。")
        return

    if webhook and not webhook.startswith(FEISHU_WEBHOOK_PREFIX):
        st.error("❌ Webhook 地址格式不正确，请输入飞书官方机器人地址。")
        return

    if run_analysis:
        sectors = []
        monitor_results = []
        alerts = []
        sentiment_values = []
        total_fund_net = 0.0
        shown_empty_warning = False
        debug_logs = []
        raw_data_cache = {}  # 缓存原始 akshare 数据

        # 创建进度容器，展示实时日志
        progress_placeholder = st.empty()

        with st.spinner(f"⏳ 正在从 AkShare 获取数据（{run_mode}模式），请稍候..."):
            debug_logs.append(f"[START] 开始执行分析流程")
            debug_logs.append(f"  运行模式: {run_mode}")
            debug_logs.append(f"  监控股票数: {len(selected_symbols)}")
            debug_logs.append(f"  回看交易日: {int(target_days)}")
            debug_logs.append(f"  股票列表: {', '.join(selected_symbols)}")
            debug_logs.append("")

            try:
                debug_logs.append("[CALL] 调用 fetch_top_sectors(5)...")
                sectors = fetch_top_sectors(5)
                debug_logs.append(f"[OK] 成功获取 {len(sectors)} 个板块数据")
            except Exception as exc:
                debug_logs.append(f"[ERROR] fetch_top_sectors 异常: {str(exc)}")
                st.error(f"获取领涨板块失败: {exc}")

            debug_logs.append("")
            debug_logs.append("[LOOP] 开始逐只股票分析...")

            # Web 输入的 selected_symbols 直接驱动底层真实 akshare 接口调用。
            for idx, symbol in enumerate(selected_symbols, 1):
                debug_logs.append(f"\n【{idx}/{len(selected_symbols)}】 处理: {symbol}")
                try:
                    debug_logs.append(f"  [CALL] fetch_daily_data(symbol='{symbol}', days={int(target_days)})")
                    debug_logs.append(f"  🔄 正在从 AkShare api：stock_zh_a_hist 获取 {symbol} 近 {int(target_days)} 日数据...")
                    df = fetch_daily_data(symbol=symbol, days=int(target_days))
                    if df is None or df.empty:
                        debug_logs.append(f"  [WARN] ❌ akshare 返回空数据帧 - 可能是网络问题或股票代码格式错误")
                        if not shown_empty_warning:
                            st.error("❌ AkShare 接口未返回数据，请检查：\n1. 网络连接\n2. 股票代码格式（如 600519 或 sh600519）\n3. 股票代码是否有效")
                            shown_empty_warning = True
                        continue

                    debug_logs.append(f"  [OK] ✓ 从 AkShare 成功获取 {len(df)} 行日线数据（OHLCV）")
                    raw_data_cache[symbol] = df.reset_index()  # 保存原始数据用于展示
                    debug_logs.append(f"  [CALL] fetch_sentiment_score('{symbol}')")
                    sentiment = fetch_sentiment_score(symbol)
                    debug_logs.append(f"  [OK] sentiment_score={sentiment}")

                    debug_logs.append(f"  [CALL] fetch_fund_flow('{symbol}')")
                    fund_data = fetch_fund_flow(symbol)
                    debug_logs.append(f"  [OK] 获得资金流向数据 ({len(fund_data)} 字段)")

                    if isinstance(sentiment, (int, float)):
                        sentiment_values.append(float(sentiment))
                    total_fund_net += parse_fund_net_amount(fund_data)

                    debug_logs.append(f"  [CALL] StrategyMonitor(symbol='{symbol}', sentiment={sentiment})")
                    monitor = StrategyMonitor(
                        df=df,
                        symbol=symbol,
                        sentiment_score=float(sentiment) if isinstance(sentiment, (int, float)) else 0.0,
                        fund_data=fund_data,
                    )
                    debug_logs.append(f"  [CALL] monitor.get_latest_signal()")
                    latest = monitor.get_latest_signal()
                    if latest:
                        debug_logs.append(f"  [OK] market_state={latest['market_state']} | suggestion={latest['suggestion']}")
                        monitor_results.append(latest)
                        if latest.get("has_warning"):
                            debug_logs.append(f"  [ALERT] ⚠️ 预警触发")
                            alerts.append(latest)
                    else:
                        debug_logs.append(f"  [WARN] get_latest_signal 返回空")
                except Exception as exc:
                    debug_logs.append(f"  [ERROR] {symbol} 异常: {str(exc)}")
                    st.error(f"处理 {symbol} 时发生异常: {exc}")

            if not monitor_results and not shown_empty_warning:
                st.error("接口未返回数据，请检查股票代码格式（如 600519、000001）")

            debug_logs.append("")
            debug_logs.append("[COMPLETE] 分析完成")
            debug_logs.append(f"  ✓ 成功处理: {len(monitor_results)} 只")
            debug_logs.append(f"  ⚠️  预警数: {len(alerts)} 只")
            if sentiment_values:
                debug_logs.append(f"  情绪均值: {round(sum(sentiment_values) / len(sentiment_values), 2)}")
            debug_logs.append(f"  资金净流入: {total_fund_net:,.0f} 万元")

        # 在页面上显示完整执行日志
        with progress_placeholder.expander("📋 执行日志详情（点击展开查看 AkShare API 调用链路）", expanded=False):
            st.code("\n".join(debug_logs), language="text")

        # 展示原始 akshare 数据（未经处理的 K 线）
        if raw_data_cache:
            st.subheader("📊 原始 AkShare K 线数据展示")
            st.info("以下数据直接来自 akshare.stock_zh_a_hist API（前复权）")
            
            # 创建标签页展示各股票的原始数据
            tabs = st.tabs([f"{sym}" for sym in raw_data_cache.keys()])
            for tab, (symbol, raw_df) in zip(tabs, raw_data_cache.items()):
                with tab:
                    st.write(f"**{symbol}** - {len(raw_df)} 日行情")
                    st.dataframe(raw_df, width="stretch", height=300)

        avg_sentiment = round(sum(sentiment_values) / len(sentiment_values), 2) if sentiment_values else 0.0
        st.session_state["analysis_cache"] = {
            "sectors": sectors,
            "monitor_results": monitor_results,
            "alerts": alerts,
            "avg_sentiment": avg_sentiment,
            "total_fund_net": total_fund_net,
            "run_mode": run_mode,
            "raw_data_cache": raw_data_cache,  # 缓存原始数据
        }
    else:
        cache = st.session_state.get("analysis_cache", {})
        sectors = cache.get("sectors", [])
        monitor_results = cache.get("monitor_results", [])
        alerts = cache.get("alerts", [])
        avg_sentiment = float(cache.get("avg_sentiment", 0.0))
        total_fund_net = float(cache.get("total_fund_net", 0.0))
        raw_data_cache = cache.get("raw_data_cache", {})
        
        if monitor_results:
            st.info("ℹ️ 当前展示的是上一次查询结果（来自 AkShare）。修改参数后点击\"执行分析\"获取新数据。")
        else:
            st.info("👈 请点击左侧\"执行分析\"按钮开始从 AkShare 获取实时数据分析。")
        
        # 展示缓存的原始数据
        if raw_data_cache:
            st.subheader("📊 原始 AkShare K 线数据展示")
            st.info("以下数据来自缓存（上一次查询结果）")
            tabs = st.tabs([f"{sym}" for sym in raw_data_cache.keys()])
            for tab, (symbol, raw_df) in zip(tabs, raw_data_cache.items()):
                with tab:
                    st.write(f"**{symbol}** - {len(raw_df)} 日行情")
                    st.dataframe(raw_df, width="stretch", height=300)

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

    overview_tab, chart_tab, table_tab, detail_tab = st.tabs(["市场总览", "趋势图表", "策略明细", "详细分析"])

    with overview_tab:
        st.subheader("📈 领涨板块（AkShare 实时数据）")
        if sectors:
            sectors_df = pd.DataFrame(sectors)
            st.dataframe(sectors_df, width="stretch", hide_index=True)
            st.caption(f"数据来自 AkShare api：stock_board_industry_name_em（获取 {len(sectors)} 个板块）")
        else:
            st.error("❌ AkShare 未返回领涨板块数据。可能是网络问题或服务暂时不可用。")

    with chart_tab:
        st.subheader("📉 个股收盘价趋势")
        render_price_charts(raw_data_cache)

    with table_tab:
        st.subheader("🎯 策略分析结果（基于 AkShare 实时数据）")
        results_df = build_results_table(monitor_results)
        if not results_df.empty:
            st.dataframe(results_df, width="stretch", hide_index=True)
            st.caption(f"✓ 成功分析 {len(results_df)} 只股票，每只股票的数据来自 AkShare API")
        else:
            st.error("❌ 扫描结果为空 — AkShare 数据源异常或全部标的获取失败。请检查：\n1. 网络连接状态\n2. 股票代码是否有效\n3. AkShare 服务可用性")
    
    with detail_tab:
        st.subheader("🔬 Phase 2 - 详细分析报告")
        st.markdown("根据 10 维评分、加权融合、风控规则的完整分析结果")
        render_detailed_analysis(monitor_results)

    if run_analysis and webhook and monitor_results:
        try:
            notifier = FeishuNotifier(webhook_url=webhook)
            notifier.send_signal_alert(
                symbol="SYSTEM",
                trigger_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                reason=f"{run_mode}模式分析完成，共扫描{len(monitor_results)}只股票（数据源：AkShare）",
                current_price=0.0,
            )
            st.success("✅ 分析完成，已发送飞书提醒（包含 AkShare 实时数据）。")
        except Exception as exc:
            st.error(f"❌ 飞书提醒发送失败（但本地分析结果已生成）: {exc}")


if __name__ == "__main__":
    main()
