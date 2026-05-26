# -*- coding: utf-8 -*-
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

import pandas as pd
import streamlit as st

from src.data_fetcher import (
    fetch_daily_data,
    fetch_fund_flow,
    fetch_sentiment_score,
    fetch_top_sectors,
)
from src.strategy_monitor import StrategyMonitor
from src.analysis_report import StockAnalysisReport
from src.reasoning_engine import ReasoningEngine
from src.backtest_engine import BacktestConfig, run_backtest
from src.parameter_search import run_parameter_grid_search


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
    "confidence_score",
    "recommended_position",
    "total_score",
    "market_state",
    "suggestion",
    "has_warning",
]


SYMBOL_PRESETS = {
    "【ETF核心指数基金】": "510300,159915,510500",  # 沪深300 ETF, 创业板 ETF, 中证500 ETF
    "【场外热门公募基金】": "110011,000001,003095",  # 易方达蓝筹精选, 华夏成长, 易方达安全量化
    "【科技与成长 ETF】": "588000,159949,512480",  # 科创50 ETF, 创业板50 ETF, 芯片 ETF
    "【跨境与全球 ETF】": "513100,513050,513180",  # 纳指100 ETF, 恒生科技 ETF, 恒生互联网 ETF
    "【消费与行业 ETF】": "515650,512010,512690",  # 消费 ETF, 医药 ETF, 酒 ETF
    "白酒龙头股票": "600519,000858,000568",
    "新能源龙头股票": "300750,002594,601012",
}


def inject_custom_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;700&family=Outfit:wght@300;400;500;600;700;800&family=Noto+Sans+SC:wght@300;400;500;700;800&display=swap');

        :root {
            --bg-base: #0c0d14;          /* TradingView extremely dark background */
            --bg-card: #131722;          /* TradingView primary card background */
            --bg-card-hover: #1e222d;    /* TradingView active/hover card */
            --border-color: #2a2e39;     /* Thin TradingView grid border */
            --brand-blue: #2962ff;       /* TradingView signature neon blue */
            --positive-green: #00c076;   /* TradingView premium green */
            --negative-red: #ff3b30;     /* TradingView premium red */
            --text-main: #d1d4dc;        /* High contrast text */
            --text-sub: #787b86;         /* Low contrast text */
        }

        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            font-family: 'Outfit', 'Noto Sans SC', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg-base) !important;
            color: var(--text-main) !important;
        }

        /* Sidebar styling override to look like TradingView sidebar */
        [data-testid="stSidebar"] {
            background-color: #131722 !important;
            border-right: 1px solid var(--border-color) !important;
        }

        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] {
            color: var(--text-main) !important;
        }

        /* Custom Input elements styling to look like TradingView dark inputs */
        input, select, textarea, [data-baseweb="input"] input, [data-baseweb="select"] div {
            background-color: #1c2030 !important;
            color: var(--text-main) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: 6px !important;
        }

        input:focus, select:focus, textarea:focus {
            border-color: var(--brand-blue) !important;
            box-shadow: 0 0 0 2px rgba(41, 98, 255, 0.2) !important;
        }

        /* Hero Panel TradingView Styling */
        .hero-panel {
            background: linear-gradient(135deg, #131722 0%, #1e222d 100%);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
            position: relative;
            overflow: hidden;
        }
        
        .hero-panel::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background-color: var(--brand-blue);
        }

        .hero-title {
            margin: 0;
            font-size: 32px;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: -0.5px;
        }

        .hero-sub {
            margin: 8px 0 0;
            color: var(--text-sub);
            font-size: 14px;
        }

        .tag-chip {
            display: inline-block;
            margin-top: 12px;
            background: rgba(41, 98, 255, 0.15);
            border: 1px solid rgba(41, 98, 255, 0.3);
            color: #4fc3f7;
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 600;
            font-family: 'Fira Code', monospace;
        }

        /* Premium TradingView Ticker Cards */
        .tv-ticker-card {
            background: #131722;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 16px 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            transition: all 0.25s ease-in-out;
            flex: 1;
            min-width: 220px;
        }

        .tv-ticker-card:hover {
            border-color: #363c4e;
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.25);
        }

        .tv-ticker-label {
            font-size: 11px;
            color: var(--text-sub);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 700;
            margin-bottom: 6px;
        }

        .tv-ticker-val {
            font-size: 26px;
            font-weight: 700;
            color: #ffffff;
            font-family: 'Fira Code', 'Noto Sans SC', monospace;
        }

        .tv-ticker-sub {
            font-size: 11px;
            color: var(--text-sub);
            margin-top: 6px;
        }

        /* Tabs custom override */
        .stTabs [data-baseweb="tab-list"] {
            gap: 12px;
            background-color: #131722;
            border-bottom: 1px solid var(--border-color);
            padding: 0 10px;
        }

        .stTabs [data-baseweb="tab"] {
            color: var(--text-sub) !important;
            background-color: transparent !important;
            font-weight: 600 !important;
            padding: 12px 16px !important;
            transition: all 0.2s !important;
        }

        .stTabs [data-baseweb="tab"]:hover {
            color: #ffffff !important;
        }

        .stTabs [aria-selected="true"] {
            color: var(--brand-blue) !important;
            border-bottom: 2px solid var(--brand-blue) !important;
        }

        /* Table custom styling for dark mode */
        div[data-testid="stTable"] table {
            background-color: #131722 !important;
            color: var(--text-main) !important;
            border-collapse: collapse !important;
        }

        div[data-testid="stTable"] th {
            background-color: #1c2030 !important;
            border-bottom: 1px solid var(--border-color) !important;
            color: #ffffff !important;
            font-weight: 600 !important;
        }

        div[data-testid="stTable"] td {
            border-bottom: 1px solid var(--border-color) !important;
        }

        /* Buttons custom styling to look like TradingView primary and secondary buttons */
        button[kind="primary"] {
            background-color: var(--brand-blue) !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 6px !important;
            font-weight: 700 !important;
            padding: 8px 16px !important;
            box-shadow: 0 4px 12px rgba(41, 98, 255, 0.3) !important;
            transition: all 0.2s !important;
        }

        button[kind="primary"]:hover {
            background-color: #1e52d6 !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 6px 16px rgba(41, 98, 255, 0.4) !important;
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

    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=plot_df[date_col],
        y=plot_df[close_col],
        mode="lines",
        name="收盘价",
        line=dict(color="#2962ff", width=2),
        fill="tozeroy",
        fillcolor="rgba(41, 98, 255, 0.08)"
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Outfit, Noto Sans SC, sans-serif", color="#d1d4dc"),
        margin=dict(l=10, r=10, t=10, b=10),
        height=320,
        showlegend=False
    )
    fig.update_xaxes(
        gridcolor="#2a2e39", 
        linecolor="#2a2e39",
        tickfont=dict(color="#787b86")
    )
    fig.update_yaxes(
        gridcolor="#2a2e39", 
        linecolor="#2a2e39",
        tickfont=dict(color="#787b86")
    )
    st.plotly_chart(fig, use_container_width=True)
    latest_close = float(plot_df[close_col].iloc[-1])
    first_close = float(plot_df[close_col].iloc[0])
    pct_move = ((latest_close - first_close) / first_close * 100.0) if first_close else 0.0
    st.caption(f"{chart_symbol} 期间累计涨跌幅: {pct_move:+.2f}%")


def render_beginner_advisor(summary_df: pd.DataFrame, detail_df: pd.DataFrame, selected_symbols: list[str]) -> None:
    """
    【智能投顾与新手诊断模块】对标 TradingView Advisor，将高深的回测指标翻译成小白通俗易懂的白话诊断与操盘建议，支持股票与基金定投分流诊断。
    """
    st.markdown('<div style="margin-top: 30px;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title" style="color: #2962ff; font-size: 20px; font-weight: 700; margin-bottom: 16px;">🎓 小白策略自诊断与智能投资建议 (TradingView Advisor)</div>', unsafe_allow_html=True)

    portfolio = summary_df[summary_df["symbol"] == "PORTFOLIO"]
    if portfolio.empty:
        portfolio = summary_df.head(1)
    
    if portfolio.empty:
        st.info("无法加载组合收益数据，暂无法生成智能投资建议。")
        return
        
    stats = portfolio.iloc[0]
    
    # 提取关键回测数值
    cum_ret = float(stats.get("cumulative_return", 0.0))
    sharpe = float(stats.get("sharpe", 0.0))
    mdd = abs(float(stats.get("max_drawdown", 0.0)))
    excess_ret = float(stats.get("excess_return", 0.0))
    trades = int(stats.get("trades", 0))
    hit_rate = float(stats.get("hit_rate", 0.5))
    
    # 动态检测是否为 交易所 ETF 或 场外公募基金组合
    is_fund_portfolio = any((sym.startswith(("5", "1", "0", "2", "3", "4", "7", "8", "9")) and len(sym) == 6) for sym in selected_symbols)
    
    # 1. 策略星级综合评定 (Beginner Strategy Star Rating)
    stars = 2.0
    # 依据夏普比率加星
    if sharpe >= 1.5:
        stars += 1.5
    elif sharpe >= 0.8:
        stars += 1.0
    elif sharpe >= 0.3:
        stars += 0.5
    elif sharpe < 0.0:
        stars -= 1.0
        
    # 依据最大回撤加星/减星
    if mdd < 0.10:
        stars += 1.0
    elif mdd >= 0.10 and mdd < 0.20:
        stars += 0.5
    elif mdd >= 0.30:
        stars -= 1.0
        
    # 依据胜率与超额收益加星
    if hit_rate >= 0.58:
        stars += 0.5
    if excess_ret > 0.0:
        stars += 0.5
        
    stars = max(1.0, min(5.0, stars))
    
    # 星级图标渲染
    star_str = "★" * int(stars) + ("☆" if (stars - int(stars) >= 0.5) else "")
    star_str = star_str.ljust(5, "☆")
    
    # 诊断等级与星级卡片样式
    if stars >= 4.0:
        badge_color = "#00c076"
        if is_fund_portfolio:
            badge_text = "极佳 / 极度推荐长线定投"
        else:
            badge_text = "极佳 / 强烈推荐模拟"
        border_shadow = "rgba(0, 192, 118, 0.2)"
    elif stars >= 3.0:
        badge_color = "#2962ff"
        if is_fund_portfolio:
            badge_text = "稳健 / 推荐轻仓配置定投"
        else:
            badge_text = "稳健 / 建议轻仓试水"
        border_shadow = "rgba(41, 98, 255, 0.2)"
    else:
        badge_color = "#ff3b30"
        badge_text = "高危 / 需调优后观察"
        border_shadow = "rgba(255, 59, 48, 0.2)"
 
    # 基金 vs 股票大白话定制
    if is_fund_portfolio:
        portfolio_type_desc = "指数基金/ETF/场外公募定投组合"
        mdd_beginner_desc = "定投安全垫 (历史回撤深度)"
        mdd_explanation = f"""
                        <b>新手解读</b>：这是你<b>长线定投</b>或者分批买入该基金/ETF时，需要做好的最大账面浮亏准备。
                        { "<b>极佳（极其适合定投理财）</b>：最大浮亏在10%以内。这非常稳健，是定投理投、获取复利最省心的选择，持仓心理几乎没有压力。" if mdd < 0.10 else
                          "<b>适中（宽基指数标准波动）</b>：最大浮亏在20%以内，属于沪深300等核心大盘指数的常态波动。定投可以助你在回撤底部以更便宜的价格收集更多份额，平摊持仓成本。" if mdd < 0.20 else
                          "<b>偏高（高弹性主题基金）</b>：最大浮亏在20%-30%之间。这通常是高成长的行业主题基金（如半导体、医药、芯片、新能源）。定投时需严控总仓位，分批吸纳筹码。" if mdd < 0.30 else
                          "<b>高风险（波动极度分化）</b>：最大浮亏超过30%！这代表该基金/ETF波动极其剧烈。定投风险较大，新手必须严控单笔额度，或利用下方‘参数网格搜索’优化风控线以摊薄回撤。" }
                        """
        
        advice_text = f"""
                    <b>【🔎 基金定投与公募/ETF 强弱轮动实盘指南】</b>：
                    监测到该组合以 <b>指数基金/ETF/场外公募基金</b> 为主，非常适合散户和小白长线理财。
                    - <b>智能定投扣款点指南</b>：当策略给出的<b>推荐度较高（如夏普良好、胜率高）</b>时，可作为<b>“定投多倍（150%-200%）扣款信号”</b>，在底部加速捡便宜筹码以分摊成本；当系统发出<b>风控警告</b>时，代表短期高估或技术面破位，应<b>暂停定投扣款，守住本金利润并等待回调后再扣</b>。
                    - <b>轮动配置建议</b>：
                      { "该基金组合夏普比率极好，最大回撤可控，是绝佳的长线财富增值标的。建议以 <b>60% - 80%</b> 的高仓位作为核心底仓进行长线定投持有。" if (mdd < 0.15 and sharpe >= 1.0) else
                        "该组合具有一定的行业弹性和进攻性，但最大回撤不可忽视。建议将仓位控制在 <b>30% - 40%</b> 之间，采用<b>按月/按周定投方式</b>建仓，不建议单笔重仓买入。" if (mdd < 0.25 and sharpe >= 0.5) else
                        "该基金/ETF组合历史波动极大，性价比偏低。当前参数在弱势市场下定投可能会面临漫长的浮亏熬底。强烈建议在下方运行<b>‘参数网格搜索’</b>以寻找更能降低回撤、平稳收益率的最佳量化风控参数后再行定投。" }
                    """
    else:
        portfolio_type_desc = "股票交易组合"
        mdd_beginner_desc = "最惨历史浮亏 (最大心理承受)"
        mdd_explanation = f"""
                        <b>新手解读</b>：代表如果你极其不幸买在了<b>最高点</b>，跌到最低点时账户可能会面临的最大<b>账面浮动亏损</b>。
                        { "<b>极佳（回撤极小）</b>：浮亏在10%以内，属于极低波动策略，持仓安全感十足，最适合小白。" if mdd < 0.10 else
                          "<b>适中（正常回撤）</b>：浮亏在20%以内，属于正常二级市场波动范畴，需要做好本金暂时浮亏的心理准备。" if mdd < 0.20 else
                          "<b>偏高（需要心脏大）</b>：浮亏超20%，新手容易在浮亏探底时惊慌失措进而割肉，切勿盲目满仓！" if mdd < 0.30 else
                          "<b>高风险（极易恐慌）</b>：浮亏超30%！这极考验神经。新手切勿重仓，策略急需通过参数调优降低最大回撤！" }
                        """
        
        advice_text = f"""
                    <b>【📌 资金与仓位分配动作建议】</b>：
                    监测到该组合以 <b>A股高风险股票</b> 为主，持仓体验较刺激，请严格执行风控：
                    - <b>仓位分配策略</b>：
                      { "该策略历史表现极为稳健，夏普比率优秀且回撤极低。新手可考虑用总资金的 <b>5% - 10%</b> 进行初期实盘轻仓探索，注意防范AkShare网络限流引起的信号漂移。" if (mdd < 0.15 and sharpe >= 1.0) else
                        "该策略具备一定的盈利能力，但历史浮亏（最大回撤）不容忽视。切忌一把梭哈！建议采用<b>分批定投或金字塔建仓</b>（如 3:3:4 比例分批买入）以平摊持仓成本，每只个股分配仓位不超过 10%。" if (mdd < 0.25 and sharpe >= 0.5) else
                        "该策略历史回撤极大（超过25%）或夏普性价比偏低。当前盲目实盘极易沦为韭菜。建议使用下方的<b>‘参数网格搜索’</b>功能进行多维度搜索调优，直至夏普比率拉升、最大回撤压降到可接受的水平后再作考虑。" }
                    """

    # 预计算一些在 f-string 中容易引起 # 符号注释崩溃的 CSS 颜色变量
    cum_ret_color = "#00c076" if cum_ret >= 0 else "#ff3b30"

    # 动态计算每个基金的估值安全边际 (Valuation Margin of Safety)
    safety_margin_html = ""
    if is_fund_portfolio and detail_df is not None and not detail_df.empty:
        safety_margin_html = """
            <h4 style="color: #ffffff; margin-top: 24px; margin-bottom: 12px; font-size: 16px; font-weight: 700;">📊 基金估值安全边际水位诊断 (Valuation Safety Margin)</h4>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px;">
        """
        for sym in selected_symbols:
            sym_df = detail_df[detail_df["symbol"] == sym]
            if not sym_df.empty and "next_day_return" in sym_df.columns:
                cum_returns = (1 + sym_df["next_day_return"]).cumprod()
                latest_val = cum_returns.iloc[-1]
                max_val = cum_returns.max()
                min_val = cum_returns.min()
                margin = (max_val - latest_val) / (max_val - min_val) if max_val > min_val else 0.5
                margin_pct = margin * 100
                drawdown_from_peak = (1.0 - latest_val / max_val) * 100
                
                # 判定等级
                if margin_pct >= 70:
                    status_desc = "🔥 极高安全边际 (底部黄金吸筹区)"
                    status_color = "#00c076"
                elif margin_pct >= 40:
                    status_desc = "✨ 稳健吸筹区 (中低估值水位)"
                    status_color = "#2962ff"
                else:
                    status_desc = "⚠️ 警惕追高区 (中高估值水位，建议分批止盈)"
                    status_color = "#ff3b30"
                
                safety_margin_html += f"""
                <div style="background: #1e222d; padding: 14px; border-radius: 8px; border: 1px solid var(--border-color);">
                    <div style="font-size: 12px; color: var(--text-sub); font-weight: 600;">📈 基金代号: {sym}</div>
                    <div style="font-size: 16px; font-weight: 700; margin: 4px 0; color: {status_color};">{margin_pct:.1f}% 安全边际</div>
                    <p style="font-size: 12px; color: var(--text-main); margin: 0; line-height: 1.5;">
                        <b>当前状态</b>：{status_desc}<br/>
                        相对于回测最高点已回撤了 <b>{drawdown_from_peak:.1f}%</b>。底仓可继续安心持有或继续进行定投分摊成本。
                    </p>
                </div>
                """
        safety_margin_html += "</div>"

    st.markdown(
        f"""
        <div style="background: #131722; border: 1px solid var(--border-color); border-radius: 12px; padding: 24px; box-shadow: 0 8px 32px {border_shadow}; margin-bottom: 24px; position: relative;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; border-bottom: 1px solid var(--border-color); padding-bottom: 16px;">
                <div>
                    <span style="font-size: 12px; color: var(--text-sub); text-transform: uppercase; font-weight: 700; display: block; margin-bottom: 4px;">策略诊断标的属性：{portfolio_type_desc}</span>
                    <span style="font-size: 26px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">诊断结论：{badge_text}</span>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 24px; color: {badge_color}; font-weight: 800; font-family: monospace;">{star_str}</div>
                    <div style="font-size: 11px; color: var(--text-sub); margin-top: 4px;">综合星级: {stars:.1f} / 5.0</div>
                </div>
            </div>
            
            <h4 style="color: #ffffff; margin-top: 0; margin-bottom: 12px; font-size: 16px; font-weight: 700;">🎯 白话核心指标解读 (Layman's Metrics)</h4>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px;">
                <div style="background: #1e222d; padding: 14px; border-radius: 8px; border: 1px solid var(--border-color);">
                    <div style="font-size: 12px; color: var(--text-sub); font-weight: 600;">💰 赚钱能力 (本金增值度)</div>
                    <div style="font-size: 18px; font-weight: 700; margin: 4px 0; color: {cum_ret_color};">{cum_ret:+.2%}</div>
                    <p style="font-size: 12px; color: var(--text-main); margin: 0; line-height: 1.5;">
                        <b>新手解读</b>：回测期间，如果期初投入 <b>10,000元</b> 本金，你的资产将增值到 <b>{10000 * (1 + cum_ret):,.2f}元</b>。
                        { "表现极强，收益大幅跑赢绝大多数理财产品！" if cum_ret > 0.15 else "收益较为温和，起到了一定的长线增值效果。" if cum_ret > 0 else "目前本金正处于缩水状态，指数深套容易让小白心态失衡，千万别实盘！" }
                    </p>
                </div>
                <div style="background: #1e222d; padding: 14px; border-radius: 8px; border: 1px solid var(--border-color);">
                    <div style="font-size: 12px; color: var(--text-sub); font-weight: 600;">💎 稳健性价比 (持仓焦虑度)</div>
                    <div style="font-size: 18px; font-weight: 700; margin: 4px 0; color: #2962ff;">{sharpe:.2f} (夏普比率)</div>
                    <p style="font-size: 12px; color: var(--text-main); margin: 0; line-height: 1.5;">
                        <b>新手解读</b>：这是衡量“性价比”的指标。
                        { "<b>极高（超稳健）</b>：收益远超其波动风险，持仓期间心电图极其平稳，几乎没有持仓焦虑，极其适合新手持仓。" if sharpe >= 1.5 else
                          "<b>良好（稳健）</b>：波动在正常股市范围内，收益产出性价比好，新手正常理财心态即可长期拿住。" if sharpe >= 0.8 else
                          "<b>中等（有持仓焦虑）</b>：虽然赚钱但一波三折，持仓过程可能让你经常因浮盈折损而焦虑，需要定力。" if sharpe >= 0.3 else
                          "<b>极低（极易恐慌割肉）</b>：性性比极低，收益无法弥补震荡风险，新手极易在暴跌中割肉离场。" }
                    </p>
                </div>
                <div style="background: #1e222d; padding: 14px; border-radius: 8px; border: 1px solid var(--border-color);">
                    <div style="font-size: 12px; color: var(--text-sub); font-weight: 600;">{mdd_beginner_desc}</div>
                    <div style="font-size: 18px; font-weight: 700; margin: 4px 0; color: #ff3b30;">-{mdd:.2%}</div>
                    <p style="font-size: 12px; color: var(--text-main); margin: 0; line-height: 1.5;">
                        {mdd_explanation}
                    </p>
                </div>
            </div>

            {safety_margin_html}

            <h4 style="color: #ffffff; margin-top: 0; margin-bottom: 12px; font-size: 16px; font-weight: 700;">💡 新手操盘实盘指南 (Advisor Tips)</h4>
            <div style="background: rgba(41, 98, 255, 0.08); border-left: 4px solid var(--brand-blue); padding: 16px; border-radius: 4px; margin-bottom: 20px;">
                <p style="font-size: 13px; color: #ffffff; margin: 0 0 8px 0; font-weight: 700;">📌 资金与仓位分配动作建议：</p>
                <p style="font-size: 13px; color: var(--text-main); margin: 0; line-height: 1.6;">
                    {advice_text}
                </p>
            </div>

            <h4 style="color: #ffffff; margin-top: 0; margin-bottom: 12px; font-size: 15px; font-weight: 700;">🚨 小白量化风控三大警戒线 (Hard Rules)</h4>
            <ul style="font-size: 12px; color: var(--text-main); margin: 0; padding-left: 20px; line-height: 1.8;">
                <li><b>指数/定投防死扛线</b>：即使是定投宽基指数ETF，若单只个股或行业ETF买入破位严重，单只基金累计浮亏跌破 <b>-15%</b> 且策略处于持续空头推荐，可选择<b>暂停定投扣款并等待趋势修复</b>，拒绝无脑死扛。</li>
                <li><b>严禁小白加杠杆</b>：在策略没有获得连续 3 个季度平稳盈利流水前，<b>坚决不要融券或使用借贷资金</b>，量化回测 the risk 往往隐藏在黑天鹅尾部中。</li>
                <li><b>策略信号钢铁纪律</b>：量化交易的核心是战胜人性的贪婪与恐惧。一旦系统计算出<b>仓位减仓或清仓警告信号</b>，不可抱有“明天可能会反弹”的幻想，必须严格执行。</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 2. 智能基金定投复利计算器 (DCA Compound Wealth Simulator)
    if is_fund_portfolio:
        st.markdown('<div style="margin-top: 10px;"></div>', unsafe_allow_html=True)
        with st.expander("🧮 智能基金定投复利模拟器 (DCA Compound Wealth Simulator)", expanded=True):
            st.markdown(
                '<div style="font-size: 13px; color: var(--text-sub); margin-bottom: 12px;">根据策略回测的年化收益率，模拟您在实盘中定期定额买入该组合的长线复利效果：</div>',
                unsafe_allow_html=True
            )
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                dca_amount = st.number_input("每期定投金额 (元)", min_value=100, max_value=100000, value=1000, step=100, key="dca_amount_input")
            with col2:
                dca_freq = st.selectbox("定投扣款频率", options=["按月定投", "按周定投"], index=0, key="dca_freq_input")
            with col3:
                ann_return_val = float(stats.get("annualized_return", 0.08))
                default_rate = max(1.0, min(50.0, ann_return_val * 100))
                expected_yield = st.number_input("预期年化收益率 (%)", min_value=0.1, max_value=100.0, value=float(default_rate), step=0.5, key="dca_yield_input")
            with col4:
                years = st.slider("定投投资限期 (年)", min_value=1, max_value=30, value=3, step=1, key="dca_years_input")
                
            # 计算定投收益
            # 假定在每期初进行扣款
            if dca_freq == "按月定投":
                periods = years * 12
                rate_per_period = expected_yield / 100 / 12
            else:
                periods = years * 52
                rate_per_period = expected_yield / 100 / 52
                
            total_principal = dca_amount * periods
            if rate_per_period > 0:
                future_value = dca_amount * (((1 + rate_per_period) ** periods - 1) / rate_per_period) * (1 + rate_per_period)
            else:
                future_value = total_principal
                
            total_profit = future_value - total_principal
            growth_pct = (total_profit / total_principal) * 100 if total_principal > 0 else 0.0
            
            st.markdown(
                f"""
                <div style="display: flex; gap: 16px; margin-top: 12px; flex-wrap: wrap; width: 100%;">
                    <div class="tv-ticker-card" style="flex: 1; min-width: 140px; background: #1e222d;">
                        <div class="tv-ticker-label" style="font-size: 11px;">💰 累计定投本金</div>
                        <div class="tv-ticker-val" style="color: #ffffff; font-size: 18px;">{total_principal:,.0f} 元</div>
                        <div class="tv-ticker-sub" style="font-size: 10px;">持之以恒的财富基石</div>
                    </div>
                    <div class="tv-ticker-card" style="flex: 1; min-width: 140px; background: #1e222d;">
                        <div class="tv-ticker-label" style="font-size: 11px;">💎 到期预期总资产</div>
                        <div class="tv-ticker-val" style="color: #00c076; font-size: 18px;">{future_value:,.2f} 元</div>
                        <div class="tv-ticker-sub" style="font-size: 10px;">本金 + 预期复利收益</div>
                    </div>
                    <div class="tv-ticker-card" style="flex: 1; min-width: 140px; background: #1e222d;">
                        <div class="tv-ticker-label" style="font-size: 11px;">📈 预期净收益 (利息)</div>
                        <div class="tv-ticker-val" style="color: #00c076; font-size: 18px;">+{total_profit:,.2f} 元</div>
                        <div class="tv-ticker-sub" style="font-size: 10px;">时间玫瑰绽放的果实</div>
                    </div>
                    <div class="tv-ticker-card" style="flex: 1; min-width: 140px; background: #1e222d;">
                        <div class="tv-ticker-label" style="font-size: 11px;">⚡ 净资产增值度</div>
                        <div class="tv-ticker-val" style="color: #2962ff; font-size: 18px;">+{growth_pct:+.2f}%</div>
                        <div class="tv-ticker-sub" style="font-size: 10px;">相比本金资产收益比例</div>
                    </div>
                </div>
                <div style="background: rgba(0, 192, 118, 0.08); border-left: 4px solid #00c076; padding: 12px; border-radius: 4px; margin-top: 16px;">
                    <span style="font-size: 12px; color: #ffffff; line-height: 1.5;">
                        <b>💡 定投复利感悟</b>：如果坚持定投 <b>{years}年</b>，您的本金将通过该策略在预期 <b>{expected_yield:.1f}%</b> 的年化复利滚存下成长至 <b>{future_value:,.0f}元</b>，资产净增值了 <b>{growth_pct:.1f}%</b>。时间是散户和小白量化最好的朋友，定投平摊了成本并完美避开了由于择时踏空引起的持仓焦虑！
                    </span>
                </div>
                """,
                unsafe_allow_html=True
            )
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


def render_backtest_analysis(selected_symbols: list[str], default_days: int = 260) -> None:
    st.subheader("🧪 回测分析（Walk-forward）")
    st.markdown("在网页内直接执行回测并查看收益/风险指标，适合面试演示。")

    if not selected_symbols:
        st.info("请先在上方选择至少一只股票后再执行回测。")
        return

    backtest_col1, backtest_col2, backtest_col3 = st.columns(3)
    with backtest_col1:
        backtest_days = st.number_input(
            "回测区间交易日",
            min_value=90,
            max_value=1200,
            value=max(180, int(default_days)),
            key="backtest_days_input",
        )
    with backtest_col2:
        warmup_days = st.number_input(
            "预热天数",
            min_value=20,
            max_value=200,
            value=60,
            key="backtest_warmup_input",
        )
    with backtest_col3:
        benchmark_symbol = st.text_input(
            "基准指数",
            value="sh000300",
            key="backtest_benchmark_input",
            help="默认使用沪深300。",
        )

    run_backtest_btn = st.button("执行回测", type="primary", key="run_backtest_web_btn")

    if run_backtest_btn:
        with st.spinner("正在执行回测，请稍候..."):
            cfg = BacktestConfig(
                symbols=selected_symbols,
                lookback_days=int(backtest_days),
                warmup_days=int(warmup_days),
                benchmark_symbol=benchmark_symbol.strip() or "sh000300",
            )
            summary_df, detail_df = run_backtest(cfg)
            st.session_state["backtest_cache"] = {
                "summary": summary_df,
                "detail": detail_df,
                "symbols": selected_symbols,
                "benchmark": cfg.benchmark_symbol,
                "days": int(backtest_days),
                "warmup": int(warmup_days),
            }

    cache = st.session_state.get("backtest_cache", {})
    summary_df = cache.get("summary")
    detail_df = cache.get("detail")

    if summary_df is None or not isinstance(summary_df, pd.DataFrame) or summary_df.empty:
        st.info("点击“执行回测”开始计算。")
        return

    st.markdown("### 📈 回测结果总览")
    st.dataframe(summary_df, width="stretch", hide_index=True)

    portfolio = summary_df[summary_df["symbol"] == "PORTFOLIO"]
    if portfolio.empty:
        portfolio = summary_df.head(1)
    latest = portfolio.iloc[0]
    cum_ret_val = float(latest.get('cumulative_return', 0.0))
    excess_ret_val = float(latest.get('excess_return', 0.0))
    cum_ret_color = "#00c076" if cum_ret_val >= 0 else "#ff3b30"
    excess_ret_color = "#00c076" if excess_ret_val >= 0 else "#ff3b30"

    st.markdown(
        f"""
        <div style="display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; width: 100%;">
            <div class="tv-ticker-card">
                <div class="tv-ticker-label">📈 组合累计收益</div>
                <div class="tv-ticker-val" style="color: {cum_ret_color};">{cum_ret_val:+.2%}</div>
                <div class="tv-ticker-sub">回测区间总收益率</div>
            </div>
            <div class="tv-ticker-card">
                <div class="tv-ticker-label">💎 组合夏普比率</div>
                <div class="tv-ticker-val" style="color: #2962ff;">{float(latest.get('sharpe', 0.0)):.2f}</div>
                <div class="tv-ticker-sub">风险调整后收益比率</div>
            </div>
            <div class="tv-ticker-card">
                <div class="tv-ticker-label">📉 最大回撤</div>
                <div class="tv-ticker-val" style="color: #ff3b30;">{float(latest.get('max_drawdown', 0.0)):.2%}</div>
                <div class="tv-ticker-sub">历史最大浮亏极值</div>
            </div>
            <div class="tv-ticker-card">
                <div class="tv-ticker-label">⚡ 组合超额收益</div>
                <div class="tv-ticker-val" style="color: {excess_ret_color};">{excess_ret_val:+.2%}</div>
                <div class="tv-ticker-sub">相较于基准指数的超额</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if detail_df is None or not isinstance(detail_df, pd.DataFrame) or detail_df.empty:
        return

    plot_df = detail_df.copy()
    plot_df["date"] = pd.to_datetime(plot_df["date"], errors="coerce")
    plot_df = plot_df.dropna(subset=["date"])
    if plot_df.empty:
        return

    strategy_daily = plot_df.groupby("date", as_index=True)["strategy_return"].mean().sort_index()
    equity_df = pd.DataFrame({"strategy": (1 + strategy_daily).cumprod()})

    if "benchmark_return" in plot_df.columns:
        bench_daily = plot_df.groupby("date", as_index=True)["benchmark_return"].mean().sort_index().fillna(0.0)
        equity_df["benchmark"] = (1 + bench_daily).cumprod()

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.markdown("### 📊 策略与基准权益曲线")
        st.line_chart(equity_df, height=340)
        
    with col_chart2:
        st.markdown("### 📉 策略与基准历史动态回撤 (Underwater)")
        # Calculate drawdown
        strategy_peak = equity_df["strategy"].cummax()
        equity_df["strategy_drawdown"] = (equity_df["strategy"] / strategy_peak - 1.0)
        
        import plotly.graph_objects as go
        fig_dd = go.Figure()
        fig_dd.add_trace(go.Scatter(
            x=equity_df.index,
            y=equity_df["strategy_drawdown"],
            mode="lines",
            name="策略回撤",
            line=dict(color="#f55d3e", width=2),
            fill="tozeroy",
            fillcolor="rgba(245, 93, 62, 0.15)"
        ))
        if "benchmark" in equity_df.columns:
            benchmark_peak = equity_df["benchmark"].cummax()
            equity_df["benchmark_drawdown"] = (equity_df["benchmark"] / benchmark_peak - 1.0)
            fig_dd.add_trace(go.Scatter(
                x=equity_df.index,
                y=equity_df["benchmark_drawdown"],
                mode="lines",
                name="基准回撤",
                line=dict(color="#486581", width=1.5, dash="dash"),
                fill="tozeroy",
                fillcolor="rgba(72, 101, 129, 0.05)"
            ))
            
        fig_dd.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Outfit, Noto Sans SC, sans-serif", color="#d1d4dc"),
            yaxis=dict(tickformat=".2%"),
            margin=dict(l=10, r=10, t=10, b=10),
            height=340,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#d1d4dc"))
        )
        fig_dd.update_xaxes(gridcolor="#2a2e39", linecolor="#2a2e39", tickfont=dict(color="#787b86"))
        fig_dd.update_yaxes(gridcolor="#2a2e39", linecolor="#2a2e39", tickfont=dict(color="#787b86"))
        st.plotly_chart(fig_dd, use_container_width=True)
        
        # 渲染小白量化投资建议
        render_beginner_advisor(summary_df, detail_df, selected_symbols)

    st.markdown("---")
    st.markdown("### 🔧 参数网格搜索（Top-N）")
    st.caption("基于当前回测明细进行阈值调优，输出最优参数组合。")

    gs_col1, gs_col2 = st.columns(2)
    with gs_col1:
        long_grid_text = st.text_input(
            "多头阈值网格",
            value="0.10,0.20,0.25,0.30",
            key="grid_long_thresholds",
            help="示例: 0.10,0.20,0.25",
        )
        min_conf_grid_text = st.text_input(
            "最小置信度网格",
            value="0.30,0.50,0.70",
            key="grid_min_confidences",
            help="示例: 0.30,0.50,0.70",
        )
    with gs_col2:
        short_grid_text = st.text_input(
            "空头阈值网格",
            value="0.10,0.20,0.25,0.30",
            key="grid_short_thresholds",
            help="示例: 0.10,0.20,0.25",
        )
        min_pos_grid_text = st.text_input(
            "最小建议仓位网格",
            value="10,20,30,40",
            key="grid_min_positions",
            help="示例: 10,20,30,40",
        )

    top_n = st.number_input(
        "显示前 N 个参数组合",
        min_value=3,
        max_value=50,
        value=10,
        key="grid_top_n",
    )

    run_grid_btn = st.button("执行参数搜索", key="run_grid_search_web_btn")

    def _parse_float_grid(raw_text: str) -> list[float]:
        vals = []
        for token in raw_text.replace("，", ",").split(","):
            token = token.strip()
            if token:
                vals.append(float(token))
        return vals

    if run_grid_btn:
        try:
            long_thresholds = _parse_float_grid(long_grid_text)
            short_thresholds = _parse_float_grid(short_grid_text)
            min_confidences = _parse_float_grid(min_conf_grid_text)
            min_positions = _parse_float_grid(min_pos_grid_text)

            if not long_thresholds or not short_thresholds or not min_confidences or not min_positions:
                st.error("参数网格不能为空。")
            else:
                with st.spinner("正在执行参数网格搜索，请稍候..."):
                    grid_df = run_parameter_grid_search(
                        detail_df=detail_df,
                        benchmark_symbol=str(cache.get("benchmark", "sh000300")),
                        lookback_days=int(cache.get("days", default_days)),
                        risk_free_rate=0.02,
                        long_thresholds=long_thresholds,
                        short_thresholds=short_thresholds,
                        min_confidences=min_confidences,
                        min_positions=min_positions,
                    )
                    st.session_state["grid_search_cache"] = grid_df
        except ValueError as e:
            st.error(f"参数解析失败，请检查输入格式: {e}")

    grid_df = st.session_state.get("grid_search_cache")
    if isinstance(grid_df, pd.DataFrame) and not grid_df.empty:
        st.markdown("#### Top 参数组合")
        st.dataframe(grid_df.head(int(top_n)), width="stretch", hide_index=True)

        best = grid_df.iloc[0]
        st.success(
            "最优参数: "
            f"long={best['long_threshold']:.2f}, "
            f"short={best['short_threshold']:.2f}, "
            f"min_conf={best['min_confidence']:.2f}, "
            f"min_pos={best['min_position']:.0f}"
        )

        st.markdown("#### 🚀 一键应用 Top-1 参数")
        apply_top1_btn = st.button("应用 Top-1 并重算对比", key="apply_top1_compare_btn")

        def _calc_sharpe(returns: pd.Series, rf: float = 0.02) -> float:
            if returns.empty:
                return 0.0
            excess = returns - (rf / 252)
            vol = float(excess.std(ddof=0))
            if vol <= 1e-8:
                return 0.0
            return float(excess.mean() / vol * (252 ** 0.5))

        def _calc_max_dd(equity_curve: pd.Series) -> float:
            if equity_curve.empty:
                return 0.0
            peak = equity_curve.cummax()
            drawdown = equity_curve / peak - 1.0
            return float(drawdown.min())

        def _calc_position(score: float, conf: float, rec_pos: float, long_th: float, short_th: float, min_conf: float, min_pos: float) -> float:
            if conf < min_conf or rec_pos < min_pos:
                return 0.0
            pos = max(0.0, min(1.0, rec_pos / 100.0))
            if score >= long_th:
                return pos
            if score <= -short_th:
                return -pos
            return 0.0

        if apply_top1_btn:
            try:
                if int(best.get("trades", 0)) <= 0:
                    st.warning("Top-1 参数没有有效交易，暂不建议应用。请调整网格后重试。")
                else:
                    cmp_df = detail_df.copy()
                    cmp_df["date"] = pd.to_datetime(cmp_df["date"], errors="coerce")
                    cmp_df = cmp_df.dropna(subset=["date"]).sort_values("date")

                    cmp_df["position_opt"] = cmp_df.apply(
                        lambda r: _calc_position(
                            score=float(r.get("score", 0.0)),
                            conf=float(r.get("confidence_score", 0.0)),
                            rec_pos=float(r.get("recommended_position", 0.0)),
                            long_th=float(best["long_threshold"]),
                            short_th=float(best["short_threshold"]),
                            min_conf=float(best["min_confidence"]),
                            min_pos=float(best["min_position"]),
                        ),
                        axis=1,
                    )
                    cmp_df["strategy_return_opt"] = cmp_df["position_opt"] * pd.to_numeric(cmp_df["next_day_return"], errors="coerce").fillna(0.0)

                    base_daily = cmp_df.groupby("date", as_index=True)["strategy_return"].mean().sort_index()
                    opt_daily = cmp_df.groupby("date", as_index=True)["strategy_return_opt"].mean().sort_index()

                    base_equity = (1 + base_daily).cumprod()
                    opt_equity = (1 + opt_daily).cumprod()

                    base_ret = float(base_equity.iloc[-1] - 1.0) if not base_equity.empty else 0.0
                    opt_ret = float(opt_equity.iloc[-1] - 1.0) if not opt_equity.empty else 0.0
                    base_sharpe = _calc_sharpe(base_daily)
                    opt_sharpe = _calc_sharpe(opt_daily)
                    base_mdd = _calc_max_dd(base_equity)
                    opt_mdd = _calc_max_dd(opt_equity)

                    compare_equity = pd.DataFrame({
                        "baseline": base_equity,
                        "optimized": opt_equity,
                    }).dropna(how="all")

                    st.session_state["top1_compare_cache"] = {
                        "base_ret": base_ret,
                        "opt_ret": opt_ret,
                        "base_sharpe": base_sharpe,
                        "opt_sharpe": opt_sharpe,
                        "base_mdd": base_mdd,
                        "opt_mdd": opt_mdd,
                        "compare_equity": compare_equity,
                    }
            except Exception as e:
                st.error(f"应用 Top-1 失败: {e}")

        cmp_cache = st.session_state.get("top1_compare_cache")
        if isinstance(cmp_cache, dict) and cmp_cache:
            st.markdown("#### 📊 优化前后对比")
            c1, c2, c3 = st.columns(3)
            c1.metric(
                "累计收益(优化后)",
                f"{float(cmp_cache.get('opt_ret', 0.0)):.2%}",
                delta=f"{(float(cmp_cache.get('opt_ret', 0.0)) - float(cmp_cache.get('base_ret', 0.0))):+.2%}",
            )
            c2.metric(
                "夏普(优化后)",
                f"{float(cmp_cache.get('opt_sharpe', 0.0)):.2f}",
                delta=f"{(float(cmp_cache.get('opt_sharpe', 0.0)) - float(cmp_cache.get('base_sharpe', 0.0))):+.2f}",
            )
            c3.metric(
                "最大回撤(优化后)",
                f"{float(cmp_cache.get('opt_mdd', 0.0)):.2%}",
                delta=f"{(float(cmp_cache.get('opt_mdd', 0.0)) - float(cmp_cache.get('base_mdd', 0.0))):+.2%}",
            )

            eq_df = cmp_cache.get("compare_equity")
            if isinstance(eq_df, pd.DataFrame) and not eq_df.empty:
                st.markdown("#### 📉 基线 vs 优化后 权益曲线")
                st.line_chart(eq_df, height=320)


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
            <h1 class="hero-title">A 股股票与 ETF 基金量化监控操作台</h1>
            <p class="hero-sub">已支持 A 股个股与交易所主流 ETF 指数基金（支持定投分析与轮动评级）。输入代码后可执行智能量化诊断、观察 TradingView 风格趋势图表并导出策略意见。</p>
            <span class="tag-chip">AkShare 基金/个股双路自适应引擎</span>
        </div>
        """,
        unsafe_allow_html=True
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
        run_mode = st.radio("运行模式", options=["实时", "收盘"], horizontal=True, key="run_mode")
        run_analysis = st.button("执行分析", type="primary", width="stretch", key="run_analysis")

    st.session_state["last_symbols_input"] = symbols_input
    st.session_state["last_target_days"] = int(target_days)

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

    if run_analysis:
        sectors = []
        monitor_results = []
        alerts = []
        sentiment_values = []
        total_fund_net = 0.0
        shown_empty_warning = False
        sector_fetch_failed = False
        daily_data_empty_symbols = []
        symbol_exceptions = []
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
                if sectors:
                    debug_logs.append(f"[OK] 成功获取 {len(sectors)} 个板块数据")
                else:
                    debug_logs.append("[WARN] fetch_top_sectors 返回空列表（非阻断，继续个股分析）")
            except Exception as exc:
                sector_fetch_failed = True
                debug_logs.append(f"[ERROR] fetch_top_sectors 异常: {str(exc)}")
                st.warning(f"获取领涨板块失败（不影响个股分析）: {exc}")

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
                        daily_data_empty_symbols.append(symbol)
                        debug_logs.append("  [WARN] ❌ 日线数据为空（可能是网络抖动、AkShare 限流或该区间暂无有效数据）")
                        if not shown_empty_warning:
                            st.warning("⚠️ 部分股票日线数据为空，系统将自动跳过并继续分析其他股票。")
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
                    symbol_exceptions.append((symbol, str(exc)))
                    debug_logs.append(f"  [ERROR] {symbol} 异常: {str(exc)}")
                    st.error(f"处理 {symbol} 时发生异常: {exc}")

            if not monitor_results and not shown_empty_warning:
                st.error("本次未得到可用结果：请优先检查网络与 AkShare 服务状态，再重试。")

            if daily_data_empty_symbols:
                st.info(
                    "跳过日线为空标的: " + ", ".join(daily_data_empty_symbols)
                )
            if symbol_exceptions:
                st.warning(
                    "发生处理异常标的: " + ", ".join([s for s, _ in symbol_exceptions])
                )

            debug_logs.append("")
            debug_logs.append("[COMPLETE] 分析完成")
            debug_logs.append(f"  ✓ 成功处理: {len(monitor_results)} 只")
            debug_logs.append(f"  ⚠️  预警数: {len(alerts)} 只")
            debug_logs.append(f"  跳过(空数据): {len(daily_data_empty_symbols)} 只")
            debug_logs.append(f"  异常失败: {len(symbol_exceptions)} 只")
            if sentiment_values:
                debug_logs.append(f"  情绪均值: {round(sum(sentiment_values) / len(sentiment_values), 2)}")
            debug_logs.append(f"  资金净流入: {total_fund_net:,.0f} 万元")
            if sector_fetch_failed:
                debug_logs.append("  板块数据状态: 获取失败（不影响个股分析）")

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

    sentiment_color = "#00c076" if avg_sentiment >= 0 else "#ff3b30"
    fund_color = "#00c076" if total_fund_net >= 0 else "#ff3b30"
    alert_color = "#ff3b30" if len(alerts) > 0 else "#00c076"

    st.markdown(
        f"""
        <div style="display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; width: 100%;">
            <div class="tv-ticker-card">
                <div class="tv-ticker-label">📰 市场情绪得分</div>
                <div class="tv-ticker-val" style="color: {sentiment_color};">{avg_sentiment:+.2f}</div>
                <div class="tv-ticker-sub">近期新闻舆情偏向度</div>
            </div>
            <div class="tv-ticker-card">
                <div class="tv-ticker-label">🔥 领涨板块</div>
                <div class="tv-ticker-val" style="color: #00c076; font-size: 22px;">{top_sector_name}</div>
                <div class="tv-ticker-sub">今日最强势板块 (今日涨幅: <b style="color: #00c076;">{top_sector_delta}</b>)</div>
            </div>
            <div class="tv-ticker-card">
                <div class="tv-ticker-label">💰 主力资金流入</div>
                <div class="tv-ticker-val" style="color: {fund_color};">{total_fund_net:,.0f} 万元</div>
                <div class="tv-ticker-sub">个股主力资金加总流入额</div>
            </div>
            <div class="tv-ticker-card">
                <div class="tv-ticker-label">⚠️ 风控预警数量</div>
                <div class="tv-ticker-val" style="color: {alert_color};">{len(alerts)}</div>
                <div class="tv-ticker-sub">触发风控预警规则的个股数</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    overview_tab, chart_tab, table_tab, detail_tab, backtest_tab = st.tabs(["市场总览", "趋势图表", "策略明细", "详细分析", "回测分析"])

    with overview_tab:
        st.subheader("📈 领涨板块（AkShare 实时数据）")
        if sectors:
            sectors_df = pd.DataFrame(sectors)
            st.dataframe(sectors_df, width="stretch", hide_index=True)
            st.caption(f"数据来自 AkShare api：stock_board_industry_name_em（获取 {len(sectors)} 个板块）")
        else:
            st.warning("⚠️ 当前未获取到领涨板块数据（不影响个股策略分析结果）。")

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
            st.warning("⚠️ 扫描结果为空：常见原因是网络抖动、AkShare 服务波动或当前标的数据暂不可用。")
    
    with detail_tab:
        st.subheader("🔬 Phase 2 - 详细分析报告")
        st.markdown("根据 10 维评分、加权融合、风控规则的完整分析结果")
        render_detailed_analysis(monitor_results)

    with backtest_tab:
        render_backtest_analysis(selected_symbols, default_days=int(target_days))

if __name__ == "__main__":
    main()