import sqlite3
import logging
import os
from datetime import datetime, timedelta
import pandas as pd
from src.data_fetcher import fetch_daily_data

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "analytics.db")

def init_db():
    """初始化数据库表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            date TEXT,
            price REAL,
            suggestion TEXT,
            market_state TEXT
        )
    ''')
    conn.commit()
    conn.close()

def record_suggestion(symbol: str, date: str, price: float, suggestion: str, market_state: str):
    """记录一条操作建议"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 避免同一张票同一天重复记录
    cursor.execute('SELECT id FROM suggestions WHERE symbol=? AND date=?', (symbol, date))
    if cursor.fetchone():
        cursor.execute('''
            UPDATE suggestions 
            SET price=?, suggestion=?, market_state=?
            WHERE symbol=? AND date=?
        ''', (price, suggestion, market_state, symbol, date))
    else:
        cursor.execute('''
            INSERT INTO suggestions (symbol, date, price, suggestion, market_state)
            VALUES (?, ?, ?, ?, ?)
        ''', (symbol, date, price, suggestion, market_state))
        
    conn.commit()
    conn.close()
    logger.info(f"成功保存 {symbol} 的操作建议到本地库: {suggestion}")

def evaluate_accuracy(days_list=[3, 5, 10]) -> dict:
    """
    自动评估过去 3/5/10 天的分析准确率。
    简单逻辑：如果当时建议是 "Risk-on/做多"，当前价格大于当时价格算作准了；
    如果是 "Risk-off/看空"，当前价格小于当时价格算作准了。
    返回的字典结构: {"3": {"total": 10, "correct": 6, "rate": 0.6}, ...}
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM suggestions", conn)
    conn.close()
    
    if df.empty:
        return {}
        
    df['date'] = pd.to_datetime(df['date'])
    today = datetime.now()
    
    results = {}
    
    # 为了避免频繁请求，做个简单的当前价缓存
    current_prices = {}
    
    for days in days_list:
        target_date = today - timedelta(days=days)
        # 宽泛地匹配：由于有节假日，我们看建议日期距离今天是不是大致 days 天之前（比如前后1天内）
        # 更严谨的做法是对每个 symbol 取前 days 个交易日的记录，这里简化为自然日的区间匹配
        start_date = target_date - timedelta(days=2)
        end_date = target_date + timedelta(days=2)
        
        mask = (df['date'] >= pd.to_datetime(start_date)) & (df['date'] <= pd.to_datetime(end_date))
        target_records = df[mask]
        
        if target_records.empty:
            results[str(days)] = {"total": 0, "correct": 0, "rate": 0.0}
            continue
            
        correct_count = 0
        total_count = 0
        
        for _, row in target_records.iterrows():
            sym = row['symbol']
            old_price = row['price']
            state = row['market_state']
            
            # 去除 Neutral 状态的，因为观望不计入胜率评估
            if state == 'Neutral':
                continue
                
            if sym not in current_prices:
                # 获取最新价
                try:
                    df_latest = fetch_daily_data(sym, days=2)
                    if not df_latest.empty:
                        current_prices[sym] = df_latest.iloc[-1]['close']
                except:
                    pass
            
            curr_price = current_prices.get(sym)
            if not curr_price:
                continue
                
            total_count += 1
            if state == 'Risk-on' and curr_price >= old_price:
                correct_count += 1
            elif state == 'Risk-off' and curr_price <= old_price:
                correct_count += 1
                
        rate = correct_count / total_count if total_count > 0 else 0.0
        results[str(days)] = {"total": total_count, "correct": correct_count, "rate": rate}
        
    return results

if __name__ == "__main__":
    init_db()
    print("Analytics DB Initialized!")
