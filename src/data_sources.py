# -*- coding: utf-8 -*-
"""
多源数据获取引擎 v2
优先级：腾讯财经 > 东方财富 > AkShare（兜底）
所有接口均为免费公开HTTP接口，无需API Key，稳定性远超AkShare爬虫。
"""
import logging
import time
import random
import requests
import json
import re
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from tenacity import retry, wait_fixed, stop_after_attempt

logger = logging.getLogger(__name__)

# ============ 全局 Session 配置 ============
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Connection": "keep-alive",
})


def _clean_symbol(symbol: str) -> str:
    """移除 sh/sz/bj 前缀，返回纯6位数字代码"""
    symbol = symbol.strip().lower()
    for prefix in ("sh", "sz", "bj"):
        if symbol.startswith(prefix):
            return symbol[2:]
    return symbol


def _infer_market(symbol: str) -> str:
    """根据代码推断市场前缀"""
    code = _clean_symbol(symbol)
    if code.startswith(("6", "9")):
        return "sh"
    elif code.startswith(("0", "2", "3")):
        return "sz"
    elif code.startswith(("4", "8")):
        return "bj"
    elif code.startswith(("5", "1")):
        return "sh"  # ETF
    return "sz"


def _full_symbol(symbol: str) -> str:
    """返回带市场前缀的完整代码，如 sh600519"""
    code = _clean_symbol(symbol)
    market = _infer_market(symbol)
    return f"{market}{code}"


# ============ 腾讯财经接口 ============

def fetch_realtime_tencent(symbols: list) -> dict:
    """
    腾讯财经实时行情（支持批量，一次最多60只）
    返回: {symbol: {name, price, open, high, low, close, volume, amount, pe, pb, ...}}
    """
    full_symbols = [_full_symbol(s) for s in symbols]
    results = {}

    # 分批，每批最多60只
    for i in range(0, len(full_symbols), 60):
        batch = full_symbols[i:i + 60]
        codes_str = ",".join(batch)
        url = f"https://qt.gtimg.cn/q={codes_str}"

        try:
            resp = _SESSION.get(url, timeout=10)
            resp.encoding = "gbk"
            text = resp.text

            # 解析 v_sh600519="1~贵州茅台~600519~1800.00~..."
            pattern = r'v_(\w+)="(.+?)"'
            for match in re.finditer(pattern, text):
                code = match.group(1)
                fields = match.group(2).split("~")
                if len(fields) < 50:
                    continue

                results[code] = {
                    "name": fields[1],
                    "code": fields[2],
                    "price": _safe_float(fields[3]),
                    "prev_close": _safe_float(fields[4]),
                    "open": _safe_float(fields[5]),
                    "volume": _safe_float(fields[6]),  # 手
                    "outer_vol": _safe_float(fields[7]),
                    "inner_vol": _safe_float(fields[8]),
                    "bid1_price": _safe_float(fields[9]),
                    "bid1_vol": _safe_float(fields[10]),
                    "high": _safe_float(fields[33]) if len(fields) > 33 else _safe_float(fields[3]),
                    "low": _safe_float(fields[34]) if len(fields) > 34 else _safe_float(fields[3]),
                    "amount": _safe_float(fields[37]),  # 万元
                    "turnover": _safe_float(fields[38]),  # 换手率%
                    "pe": _safe_float(fields[39]),
                    "pb": _safe_float(fields[46]) if len(fields) > 46 else 0,
                    "market_cap": _safe_float(fields[45]) if len(fields) > 45 else 0,  # 亿
                    "pct_change": _safe_float(fields[32]),
                    "amplitude": _safe_float(fields[43]) if len(fields) > 43 else 0,
                }
        except Exception as e:
            logger.warning(f"腾讯实时行情获取失败: {e}")

        time.sleep(0.3)

    return results


def fetch_kline_tencent(symbol: str, days: int = 200) -> pd.DataFrame:
    """
    腾讯财经日K线数据（前复权）
    接口: https://web.ifzq.gtimg.cn/appstock/app/fqkline/get
    """
    full_sym = _full_symbol(symbol)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=int(days * 1.6) + 30)).strftime("%Y-%m-%d")

    url = (
        f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?param={full_sym},day,{start_date},{end_date},{days + 50},qfq"
    )

    try:
        resp = _SESSION.get(url, timeout=15)
        data = resp.json()

        # 解析嵌套JSON
        stock_data = data.get("data", {}).get(full_sym, {})
        # 优先取前复权数据 qfqday，否则取 day
        klines = stock_data.get("qfqday") or stock_data.get("day", [])

        if not klines:
            logger.warning(f"腾讯K线接口返回空数据: {symbol}")
            return pd.DataFrame()

        rows = []
        for k in klines:
            # 格式: [date, open, close, high, low, volume, ...]
            if len(k) >= 6:
                rows.append({
                    "date": k[0],
                    "open": float(k[1]),
                    "close": float(k[2]),
                    "high": float(k[3]),
                    "low": float(k[4]),
                    "volume": float(k[5]),
                })

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        df.sort_index(inplace=True)
        return df.tail(days)

    except Exception as e:
        logger.warning(f"腾讯K线获取失败 {symbol}: {e}")
        return pd.DataFrame()


# ============ 东方财富接口 ============

def fetch_kline_eastmoney(symbol: str, days: int = 200) -> pd.DataFrame:
    """
    东方财富日K线（前复权）
    接口: https://push2his.eastmoney.com/api/qt/stock/kline/get
    """
    code = _clean_symbol(symbol)
    market = _infer_market(symbol)
    secid = f"{'1' if market == 'sh' else '0'}.{code}"

    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=int(days * 1.6) + 30)).strftime("%Y%m%d")

    url = (
        f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
        f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
        f"&klt=101&fqt=1&beg={start_date}&end={end_date}&lmt={days + 50}"
    )

    try:
        resp = _SESSION.get(url, timeout=15)
        data = resp.json()

        klines = data.get("data", {}).get("klines", [])
        if not klines:
            logger.warning(f"东方财富K线返回空: {symbol}")
            return pd.DataFrame()

        rows = []
        for line in klines:
            # 格式: date,open,close,high,low,volume,amount,amplitude,pct_change,change,turnover
            parts = line.split(",")
            if len(parts) >= 7:
                rows.append({
                    "date": parts[0],
                    "open": float(parts[1]),
                    "close": float(parts[2]),
                    "high": float(parts[3]),
                    "low": float(parts[4]),
                    "volume": float(parts[5]),
                    "amount": float(parts[6]),
                })

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        df.sort_index(inplace=True)
        return df.tail(days)

    except Exception as e:
        logger.warning(f"东方财富K线获取失败 {symbol}: {e}")
        return pd.DataFrame()


def fetch_fund_flow_eastmoney(symbol: str) -> dict:
    """
    东方财富个股资金流向（主力/超大/大/中/小单）
    """
    code = _clean_symbol(symbol)
    market = _infer_market(symbol)
    secid = f"{'1' if market == 'sh' else '0'}.{code}"

    url = (
        f"https://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
        f"?secid={secid}&fields1=f1,f2,f3,f7"
        f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"
        f"&klt=101&lmt=5"
    )

    try:
        resp = _SESSION.get(url, timeout=10)
        data = resp.json()
        klines = data.get("data", {}).get("klines", [])
        if not klines:
            return {}

        # 取最新一天
        latest = klines[-1].split(",")
        if len(latest) >= 7:
            return {
                "date": latest[0],
                "main_net_inflow": float(latest[1]),      # 主力净流入
                "small_net_inflow": float(latest[2]),     # 小单净流入
                "mid_net_inflow": float(latest[3]),       # 中单净流入
                "large_net_inflow": float(latest[4]),     # 大单净流入
                "super_large_net_inflow": float(latest[5]),  # 超大单净流入
            }
    except Exception as e:
        logger.warning(f"东方财富资金流向获取失败 {symbol}: {e}")

    return {}


def fetch_sector_eastmoney(n: int = 5) -> list:
    """东方财富行业板块涨幅排行"""
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get"
        "?pn=1&pz=50&po=1&np=1&fltt=2&invt=2"
        "&fid=f3&fs=m:90+t:2+f:!50"
        "&fields=f2,f3,f4,f12,f14"
    )
    try:
        resp = _SESSION.get(url, timeout=10)
        data = resp.json()
        items = data.get("data", {}).get("diff", [])
        results = []
        for item in items[:n]:
            results.append({
                "板块名称": item.get("f14", ""),
                "涨跌幅": item.get("f3", 0),
                "板块代码": item.get("f12", ""),
            })
        return results
    except Exception as e:
        logger.warning(f"东方财富板块数据获取失败: {e}")
        return []


def fetch_news_eastmoney(symbol: str, limit: int = 20) -> list:
    """东方财富个股新闻"""
    code = _clean_symbol(symbol)
    url = (
        f"https://search-api-web.eastmoney.com/search/jsonp"
        f"?cb=jQuery&param=%7B%22uid%22%3A%22%22%2C%22keyword%22%3A%22{code}%22"
        f"%2C%22type%22%3A%5B%22cmsArticleWebOld%22%5D%2C%22client%22%3A%22web%22"
        f"%2C%22clientType%22%3A%22web%22%2C%22clientVersion%22%3A%22curr%22"
        f"%2C%22param%22%3A%7B%22cmsArticleWebOld%22%3A%7B%22searchScope%22%3A%22default%22"
        f"%2C%22sort%22%3A%22default%22%2C%22pageIndex%22%3A1%2C%22pageSize%22%3A{limit}"
        f"%2C%22preTag%22%3A%22%22%2C%22postTag%22%3A%22%22%7D%7D%7D"
    )
    try:
        resp = _SESSION.get(url, timeout=10)
        text = resp.text
        # 去掉 JSONP 包装
        json_str = re.search(r'jQuery\((.*)\)', text, re.DOTALL)
        if json_str:
            data = json.loads(json_str.group(1))
            articles = data.get("result", {}).get("cmsArticleWebOld", {}).get("list", [])
            return [{"title": a.get("title", ""), "date": a.get("date", ""),
                     "content": a.get("content", "")[:200]} for a in articles]
    except Exception as e:
        logger.warning(f"东方财富新闻获取失败 {symbol}: {e}")
    return []


# ============ 统一入口（多源降级） ============

def fetch_daily_data(symbol: str, days: int = 200) -> pd.DataFrame:
    """
    多源日K线获取（自动降级）
    优先级: 腾讯财经 > 东方财富 > AkShare
    """
    # 第一源：腾讯
    df = fetch_kline_tencent(symbol, days)
    if not df.empty and len(df) >= 20:
        logger.info(f"[腾讯] {symbol} 获取成功: {len(df)} 条")
        return df

    time.sleep(0.5)

    # 第二源：东方财富
    df = fetch_kline_eastmoney(symbol, days)
    if not df.empty and len(df) >= 20:
        logger.info(f"[东财] {symbol} 获取成功: {len(df)} 条")
        return df

    time.sleep(0.5)

    # 第三源：AkShare 兜底
    try:
        import akshare as ak
        code = _clean_symbol(symbol)
        end_str = datetime.now().strftime("%Y%m%d")
        start_str = (datetime.now() - timedelta(days=int(days * 1.6) + 30)).strftime("%Y%m%d")
        df_ak = ak.stock_zh_a_hist(symbol=code, period="daily",
                                    start_date=start_str, end_date=end_str, adjust="qfq")
        if df_ak is not None and not df_ak.empty:
            col_map = {"日期": "date", "开盘": "open", "收盘": "close",
                       "最高": "high", "最低": "low", "成交量": "volume"}
            df_ak = df_ak.rename(columns=col_map)
            required = ["date", "open", "high", "low", "close", "volume"]
            df_ak = df_ak[[c for c in required if c in df_ak.columns]]
            df_ak["date"] = pd.to_datetime(df_ak["date"])
            df_ak.set_index("date", inplace=True)
            df_ak.sort_index(inplace=True)
            logger.info(f"[AkShare兜底] {symbol} 获取成功: {len(df_ak)} 条")
            return df_ak.tail(days)
    except Exception as e:
        logger.warning(f"[AkShare兜底] {symbol} 也失败了: {e}")

    logger.error(f"所有数据源均无法获取 {symbol} 的数据")
    return pd.DataFrame()


def fetch_realtime_data(symbol: str) -> dict:
    """获取单只股票实时行情（腾讯源）"""
    results = fetch_realtime_tencent([symbol])
    full_sym = _full_symbol(symbol)
    return results.get(full_sym, {})


def fetch_fund_flow(symbol: str) -> dict:
    """获取个股资金流向（东方财富源）"""
    return fetch_fund_flow_eastmoney(symbol)


def fetch_top_sectors(n: int = 5) -> list:
    """获取领涨板块（东方财富源）"""
    return fetch_sector_eastmoney(n)


def fetch_sentiment_score(symbol: str) -> float:
    """
    基于东方财富新闻的舆情评分
    使用加权关键词匹配，比简单计数更精确
    """
    news_list = fetch_news_eastmoney(symbol, limit=15)
    if not news_list:
        return 0.0

    # 强利好/利空词（权重2）
    strong_positive = ["涨停", "大涨", "超预期", "重大利好", "突破新高", "业绩预增", "回购"]
    strong_negative = ["跌停", "爆雷", "立案", "退市", "重大利空", "业绩预亏", "暴雷"]
    # 一般利好/利空词（权重1）
    mild_positive = ["增长", "利好", "突破", "分红", "增持", "上涨", "反弹", "创新高"]
    mild_negative = ["下跌", "利空", "减持", "亏损", "警示", "下滑", "回调", "承压"]

    score = 0.0
    for news in news_list:
        text = news.get("title", "") + news.get("content", "")
        for w in strong_positive:
            if w in text:
                score += 2.0
        for w in strong_negative:
            if w in text:
                score -= 2.0
        for w in mild_positive:
            if w in text:
                score += 1.0
        for w in mild_negative:
            if w in text:
                score -= 1.0

    # 归一化到 [-3, 3] 区间
    return max(-3.0, min(3.0, score / max(len(news_list), 1) * 3))


def _safe_float(val) -> float:
    """安全转换为浮点数"""
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0
