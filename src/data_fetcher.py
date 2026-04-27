import logging
import time
import random
import requests
from datetime import datetime, timedelta
import pandas as pd
import akshare as ak
from tenacity import retry, wait_fixed, stop_after_attempt, retry_if_exception_type

# 随机User-Agent列表，防止被封锁
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/122.0.0.0"
]

# 全局替换 requests.Session.request 以注入 random User-Agent 彻底解决 RemoteDisconnected 错误
_original_request = requests.Session.request
def _mocked_request(self, method, url, **kwargs):
    headers = kwargs.get('headers')
    if headers is None:
        headers = {}
        kwargs['headers'] = headers
    if 'User-Agent' not in headers:
        headers['User-Agent'] = random.choice(USER_AGENTS)
    return _original_request(self, method, url, **kwargs)
requests.Session.request = _mocked_request

logger = logging.getLogger(__name__)

def setup_logger():
    """配置日志记录器"""
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

setup_logger()

def _clean_symbol(symbol: str) -> str:
    """
    清洗股票代码（移除 sh, sz 等前缀）
    AkShare 的 stock_zh_a_hist 接口通常需要 6 位数字代码
    """
    symbol = symbol.strip().lower()
    for prefix in ['sh', 'sz', 'bj']:
        if symbol.startswith(prefix):
            return symbol[2:]
    return symbol

@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(20),
    retry=retry_if_exception_type(Exception),
    before_sleep=lambda retry_state: logger.warning(f"获取日线数据失败，等待20s后第 {retry_state.attempt_number} 次重试...")
)
def fetch_daily_data(symbol: str, days: int = 200) -> pd.DataFrame:
    """
    使用 AkShare 获取指定股票最近交易日的日线数据
    
    参数:
        symbol (str): 股票代码（支持带前缀如 'sh600519' 或纯数字 '600519'）
        days (int): 需要获取最近多少个交易日的数据，默认 200 天
        
    返回:
        pd.DataFrame: 数据格式清洗为开盘、最高、最低、收盘、成交量，且索引为日期
    """
    clean_symbol = _clean_symbol(symbol)
    
    # 由于存在周末和节假日，为了确保能取到充足的交易日数据，
    # 我们往前推算的自然日需要大于交易日数量。一般一年约 250 个交易日。
    # 这里我们放宽时间窗口获取更多数据，最后再做截断。
    calendar_days_to_fetch = int(days * 1.5) + 30 
    end_date = datetime.now()
    start_date = end_date - timedelta(days=calendar_days_to_fetch)
    
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")
    
    logger.info(f"正在获取 {symbol} ({clean_symbol}) 从 {start_str} 到 {end_str} 的数据")
    
    sleep_time = random.uniform(3, 7)
    logger.info(f"防封锁机制：随机休眠 {sleep_time:.2f} 秒...")
    time.sleep(sleep_time)
    
    try:
        # 获取 A 股日线数据（qfq：前复权）
        df = ak.stock_zh_a_hist(
            symbol=clean_symbol, 
            period="daily", 
            start_date=start_str, 
            end_date=end_str, 
            adjust="qfq"
        )
    except Exception as e:
        logger.warning(f"获取 {symbol} 日线数据失败: {e}")
        return pd.DataFrame()
    
    if df is None or df.empty:
        logger.warning(f"未获取到 {symbol} 的数据，请检查代码是否正确或是否在交易区间内")
        return pd.DataFrame()
        
    # AkShare 默认返回的中文列名：日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
    column_mapping = {
        '日期': 'date',
        '开盘': 'open',
        '最高': 'high',
        '最低': 'low',
        '收盘': 'close',
        '成交量': 'volume'
    }
    
    # 检查期望的列是否存在
    missing_cols = [col for col in column_mapping.keys() if col not in df.columns]
    if missing_cols:
        logger.error(f"AkShare 响应的格式不符合预期，缺少列：{missing_cols}")
        return pd.DataFrame()
        
    # 重命名列
    df = df.rename(columns=column_mapping)
    
    # 仅保留需要的列
    required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
    df = df[required_cols]
    
    # 类型转换
    df['date'] = pd.to_datetime(df['date'])
    # 将 OHLCV 转为 float / int
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        
    # 剔除包含空值的行
    df = df.dropna()
    
    # 设日期为索引，并按时间升序排序
    df.set_index('date', inplace=True)
    df.sort_index(ascending=True, inplace=True)
    
    logger.info(f"成功清洗数据，共获取到 {len(df)} 条记录")
    
    # 截取最近的 N 个交易日数据
    result_df = df.tail(days)
    logger.info(f"已截取最近 {len(result_df)} 个交易日的数据")
    
    return result_df

@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(20),
    retry=retry_if_exception_type(Exception),
    before_sleep=lambda retry_state: logger.warning(f"获取实时数据失败，等待20s后第 {retry_state.attempt_number} 次重试...")
)
def fetch_realtime_data(symbol: str) -> pd.DataFrame:
    """获取单只股票的基本/实时信息 (单股狙击)"""
    clean_sym = _clean_symbol(symbol)
    logger.info(f"获取 {symbol} 单只股票最新行情...")
    df = ak.stock_individual_info_em(symbol=clean_sym)
    return df

def fetch_top_sectors(n: int = 5) -> list:
    """获取今日涨幅前几名的板块（非关键数据，失败不影响主流程）"""
    logger.info(f"获取今日涨幅前 {n} 的板块...")
    try:
        df = ak.stock_board_industry_name_em()
        if df is not None and not df.empty:
            # 按涨跌幅排序降序
            df = df.sort_values(by="涨跌幅", ascending=False)
            top_n = df.head(n)
            return top_n.to_dict('records')
    except Exception as e:
        logger.warning(f"获取板块数据失败（非关键步骤，跳过）: {e}")
    return []

def fetch_sentiment_score(symbol: str) -> float:
    """
    Phase 3 升级：使用 NLP 分析舆情
    抓取个股最新新闻标题，使用 NLP 模型/词汇库判断情感倾向
    返回: -1.0 (负面) ~ +1.0 (正面)
    """
    clean_symbol = _clean_symbol(symbol)
    logger.info(f"[Phase 3] 获取 {symbol} 近期舆情并进行 NLP 分析...")
    
    # 延迟导入 SentimentAggregator（避免 SyntaxError 导致 RetryError）
    try:
        from nlp_sentiment import SentimentAggregator
    except Exception as e:
        logger.warning(f"导入 SentimentAggregator 失败: {e}")
        return 0.0
    
    try:
        df = ak.stock_news_em(symbol=clean_symbol)
    except Exception as e:
        logger.warning(f"获取 {symbol} 舆情失败: {e}")
        return 0.0
        
    if df is None or df.empty:
        logger.warning(f"{symbol} 暂无最新新闻数据")
        return 0.0
    
    # 收集所有新闻文本
    news_texts = []
    for col in df.columns:
        if '标题' in col or '内容' in col or 'title' in col.lower() or 'content' in col.lower():
            for text in df[col].astype(str).head(20):
                if text and text != 'nan':
                    news_texts.append(text)
    
    if not news_texts:
        logger.warning(f"{symbol} 无有效新闻文本")
        return 0.0
    
    # 使用 NLP 分析器聚合舆情
    try:
        aggregator = SentimentAggregator()
        sentiment_score = aggregator.aggregate_sentiment(news_texts)
        category = aggregator.get_sentiment_category(sentiment_score)
        logger.info(f"✅ {symbol} NLP 舆情分析完成: {category} (评分: {sentiment_score:+.2f})")
        return sentiment_score
    except Exception as e:
        logger.warning(f"NLP 分析出错，降级到关键词方案: {e}")
        # 降级方案：使用关键词统计
        text_content = " ".join(news_texts)
        score = 0
        positive_words = ['增长', '利好', '突破', '大涨', '涨停', '分红', '回购', '增持', '超预期']
        negative_words = ['下跌', '利空', '爆雷', '减持', '跌停', '亏损', '警示', '立案', '退市']
        
        for word in positive_words:
            score += text_content.count(word)
        for word in negative_words:
            score -= text_content.count(word)
        
        # 归一化到 -1 ~ +1
        total_count = len(positive_words) + len(negative_words)
        if total_count > 0:
            score = score / total_count
        
        return max(-1.0, min(1.0, score))

def fetch_fund_flow(symbol: str) -> dict:
    """
    获取个股主力净流入数据
    注意：如果遇到接口变更报错，返回空字典。
    """
    clean_symbol = _clean_symbol(symbol)
    logger.info(f"获取 {symbol} 资金流向...")
    
    # 获取市场后缀，如果用户提供了 sh/sz，直接提取，否则依靠 clean_symbol 猜测大概率
    market = "sh" if symbol.lower().startswith("sh") else "sz"
    
    try:
        # stock_individual_fund_flow 接口接受 stock="600519", market="sh"
        df = ak.stock_individual_fund_flow(stock=clean_symbol, market=market)
    except Exception as e:
        logger.warning(f"获取 {symbol} 资金流向失败: {e}")
        return {}
        
    if df is None or df.empty:
        return {}
    
    # 确保按日期升序排列，取最新一行
    if '日期' in df.columns:
        df = df.sort_values(by='日期', ascending=True)
    latest = df.iloc[-1]
    
    # 将 Series 转为标量 dict（处理可能存在的 NaN 值）
    result = {}
    for key, value in latest.items():
        if isinstance(value, (pd.Timestamp, pd.Period)):
            result[key] = str(value)
        elif pd.isna(value):
            result[key] = 0.0
        else:
            result[key] = value
    return result

