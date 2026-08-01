# -*- coding: utf-8 -*-
"""
A股量化分析工具 v2 - Web API 服务
为新的 HTML/CSS/JS 前端提供数据接口，Streamlit (app.py) 继续作为兜底方案。
"""
import json
import os
import sys
import logging
from typing import List

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# 确保 src 可被导入
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(CURRENT_DIR, "src")
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from src.data_sources import (
    fetch_daily_data,
    fetch_realtime_data,
    fetch_fund_flow,
    fetch_top_sectors,
    fetch_sentiment_score,
)
from src.strategy_monitor import run_monitor_for_stocks
from src.caixin_data import init_caixin_client, fetch_caixin_macro_context
from src.ai_analyst import init_ai_analyst, get_ai_analyst

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="A股量化分析 API", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DASHBOARD_DIR = os.path.join(CURRENT_DIR, "dashboard", "pages")
ASSETS_DIR = os.path.join(CURRENT_DIR, "dashboard", "assets")

# 挂载静态资源
if os.path.isdir(ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


def load_config(config_path="config.json"):
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _clean_symbols(symbols_str: str) -> List[str]:
    return [s.strip() for s in symbols_str.replace("，", ",").split(",") if s.strip()]


@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    index_path = os.path.join(DASHBOARD_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Dashboard not found</h1>", status_code=404)


@app.get("/api/analyze")
def analyze(
    symbols: str = Query(..., description="逗号分隔的股票代码，如 sh600519,sz000858"),
    days: int = Query(200, description="回看交易日数"),
    mode: str = Query("mid", description="播报模式: start/mid/end"),
):
    """
    执行多维度量化分析并返回 JSON 结果，供前端仪表盘渲染。
    """
    config = load_config()
    target_symbols = _clean_symbols(symbols)
    target_days = days

    caixin_key = config.get("caixin_api_key", "")
    if caixin_key:
        try:
            client = init_caixin_client(caixin_key)
            if not client.health_check():
                caixin_key = ""
        except Exception:
            caixin_key = ""

    # 初始化 AI 分析师
    ai_cfg = config.get("ai_analyst", {})
    if ai_cfg.get("enabled") and ai_cfg.get("api_key"):
        try:
            init_ai_analyst(
                api_key=ai_cfg["api_key"],
                base_url=ai_cfg.get("base_url", "https://apihub.agnes-ai.com/v1"),
                model=ai_cfg.get("model", "agnes-2.0-flash"),
            )
        except Exception as e:
            logger.warning(f"AI 分析师初始化失败: {e}")

    if not target_symbols:
        return {"error": "自选股列表为空", "results": [], "alerts": [], "sectors": []}

    logger.info(f"API 分析请求 | 模式: {mode} | 标的: {len(target_symbols)} 只")

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

    stock_data_dict = {}
    extra_data = {}

    for symbol in target_symbols:
        try:
            logger.info(f"  处理: {symbol}")
            df = fetch_daily_data(symbol=symbol, days=target_days)
            if df.empty:
                logger.warning(f"  {symbol} 数据为空，跳过")
                continue

            stock_data_dict[symbol] = df
            fund_data = fetch_fund_flow(symbol)
            sentiment = fetch_sentiment_score(symbol)
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
        return {"error": "所有股票数据获取失败", "results": [], "alerts": [], "sectors": sectors}

    alerts, results = run_monitor_for_stocks(stock_data_dict, extra_data)

    # 补充 sparkline 用的近期收盘价
    for r in results:
        symbol = r.get("symbol")
        df = stock_data_dict.get(symbol)
        if df is not None and "close" in df.columns:
            r["recent_prices"] = df["close"].tail(30).tolist()

    # AI 深度分析
    ai_overview = ""
    ai = get_ai_analyst()
    if ai:
        try:
            overview = ai.market_overview(sectors, results, macro_ctx)
            if overview:
                ai_overview = overview
        except Exception as e:
            logger.warning(f"AI 市场总览生成失败: {e}")

    return {
        "results": results,
        "alerts": alerts,
        "sectors": sectors,
        "macro_ctx": macro_ctx,
        "ai_overview": ai_overview,
        "mode": mode,
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
