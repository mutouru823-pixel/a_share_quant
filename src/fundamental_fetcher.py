import logging
import akshare as ak
from typing import Dict

logger = logging.getLogger(__name__)

def fetch_financial_indicators(symbol: str) -> Dict:
    """获取财务指标数据"""
    try:
        clean_symbol = symbol.replace('sh', '').replace('sz', '')
        
        # 获取个股信息
        stock_info = ak.stock_individual_info_em(symbol=clean_symbol)
        if stock_info is None or stock_info.empty:
            logger.warning(f"无法获取 {symbol} 的个股信息")
            return {}
        
        # 获取主要指标
        main_indicator = ak.stock_main_indicator_em(symbol=clean_symbol)
        if main_indicator is None or main_indicator.empty:
            logger.warning(f"无法获取 {symbol} 的主要指标")
            return {}
        
        # 提取关键指标
        result = {
            'symbol': symbol,
            'ROE': 0.0,
            'PE': 0.0,
            'profit_yoy': 0.0,
            'debt_ratio': 0.0,
        }
        
        try:
            roe_val = stock_info[stock_info['item'] == '净资产收益率'].iloc[0]['value'] if len(stock_info) > 0 else 0
            result['ROE'] = float(str(roe_val).strip('%')) if roe_val else 0.0
        except:
            pass
        
        try:
            pe_val = stock_info[stock_info['item'] == '市盈率'].iloc[0]['value'] if len(stock_info) > 0 else 0
            result['PE'] = float(pe_val) if pe_val else 0.0
        except:
            pass
        
        logger.info(f"✅ 获取 {symbol} 财务指标成功")
        return result
    
    except Exception as e:
        logger.warning(f"获取 {symbol} 财务指标失败: {e}")
        return {}

def calculate_fundamental_score(financial_data: Dict) -> float:
    """计算基本面评分"""
    if not financial_data:
        return 0.0
    
    score = 0.0
    
    # ROE > 15% 加分
    if financial_data.get('ROE', 0) > 15:
        score += 0.3
    
    # PE < 15 加分
    pe = financial_data.get('PE', 0)
    if 0 < pe < 15:
        score += 0.3
    
    # 利润同比增长 > 20% 加分
    if financial_data.get('profit_yoy', 0) > 20:
        score += 0.2
    
    # 债务比 < 0.5 加分
    if financial_data.get('debt_ratio', 0) < 0.5:
        score += 0.2
    
    return min(1.0, score) - 0.5  # 归一化到 -1 ~ 1
