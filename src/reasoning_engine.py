import logging

logger = logging.getLogger(__name__)

class ReasoningEngine:
    """多维指标 → 文字解读转换引擎"""
    
    def __init__(self):
        pass
    
    def generate_tech_reasoning(self, signal: dict) -> str:
        """生成技术面解读"""
        tech_score = signal.get('tech_score', 0)
        sma5 = signal.get('SMA_5', 0)
        sma10 = signal.get('SMA_10', 0)
        sma20 = signal.get('SMA_20', 0)
        rsi = signal.get('RSI_14', 50)
        macd_dif = signal.get('MACD_DIF', 0)
        macd_dea = signal.get('MACD_DEA', 0)
        close = signal.get('close', 0)
        
        reasons = []
        
        if sma5 > sma10 > sma20:
            reasons.append("均线呈多头排列 (MA5 > MA10 > MA20)")
        elif sma5 < sma10 < sma20:
            reasons.append("均线呈空头排列 (MA5 < MA10 < MA20)")
        
        if close > sma20:
            reasons.append(f"价格在 20 日均线上方 ({close:.2f} > {sma20:.2f})")
        else:
            reasons.append(f"价格在 20 日均线下方 ({close:.2f} < {sma20:.2f})")
        
        if macd_dif > macd_dea:
            reasons.append("MACD 金叉状态（DIF > DEA）")
        elif macd_dif < macd_dea:
            reasons.append("MACD 死叉状态（DIF < DEA）")
        
        if rsi > 70:
            reasons.append(f"RSI 值 {rsi:.1f}，市场超买")
        elif rsi < 30:
            reasons.append(f"RSI 值 {rsi:.1f}，市场超卖")
        else:
            reasons.append(f"RSI 值 {rsi:.1f}，处于中性区间")
        
        if tech_score > 0:
            return f"技术面积极向好。{', '.join(reasons)}"
        elif tech_score < 0:
            return f"技术面风险信号。{', '.join(reasons)}"
        else:
            return f"技术面中立。{', '.join(reasons)}"
    
    def generate_chip_reasoning(self, signal: dict) -> str:
        """生成筹码面解读"""
        chip_score = signal.get('chip_score', 0)
        
        if chip_score > 0:
            return "筹码面：主力资金净流入，机构持仓积极，多头氛围浓厚。"
        elif chip_score < 0:
            return "筹码面：主力资金净流出，机构持仓谨慎，空头力量显现。"
        else:
            return "筹码面：主力资金进出平衡，市场参与者观望态度中立。"
    
    def generate_fundamental_reasoning(self, financial_data: dict) -> str:
        """生成基本面解读"""
        roe = financial_data.get('roe', 0)
        profit_yoy = financial_data.get('profit_yoy', 0)
        pe_ratio = financial_data.get('pe_ratio', 0)
        debt_ratio = financial_data.get('debt_ratio', 0)
        
        reasons = []
        
        if roe > 15:
            reasons.append(f"ROE {roe:.1f}% 较高，盈利能力强")
        elif roe < 8:
            reasons.append(f"ROE {roe:.1f}% 较低，盈利能力弱")
        else:
            reasons.append(f"ROE {roe:.1f}% 均衡")
        
        if profit_yoy > 20:
            reasons.append(f"利润同比增长 {profit_yoy:.1f}% 强劲")
        elif profit_yoy < 0:
            reasons.append(f"利润同比下滑 {profit_yoy:.1f}%，需警惕")
        else:
            reasons.append(f"利润同比增长 {profit_yoy:.1f}%")
        
        if pe_ratio > 0:
            if pe_ratio < 15:
                reasons.append(f"PE {pe_ratio:.1f}x 处于低位，估值便宜")
            elif pe_ratio > 30:
                reasons.append(f"PE {pe_ratio:.1f}x 处于高位，估值昂贵")
            else:
                reasons.append(f"PE {pe_ratio:.1f}x 估值合理")
        
        if debt_ratio < 0.5:
            reasons.append("负债率低，财务安全可靠")
        elif debt_ratio > 0.7:
            reasons.append("负债率高，财务风险较大")
        
        return f"基本面分析：{', '.join(reasons)}"
    
    def generate_sentiment_reasoning(self, signal: dict) -> str:
        """生成情绪面解读"""
        sentiment_score = signal.get('sentiment_score', 0)
        
        if sentiment_score > 0:
            return "舆情面：市场情绪积极向上，新闻面偏利好，散户情绪高涨。"
        elif sentiment_score < 0:
            return "舆情面：市场情绪悲观失望，新闻面偏利空，风险情绪蔓延。"
        else:
            return "舆情面：市场情绪中立平静，新闻面无明显方向，参与者理性。"
    
    def generate_full_reasoning(self, signal: dict, financial_data: dict = None) -> str:
        """生成完整分析解读"""
        financial_data = financial_data or {}
        
        tech_text = self.generate_tech_reasoning(signal)
        chip_text = self.generate_chip_reasoning(signal)
        fundamental_text = self.generate_fundamental_reasoning(financial_data)
        sentiment_text = self.generate_sentiment_reasoning(signal)
        
        full_text = f"""
📊 多维分析解读
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 技术面分析
{tech_text}

💰 筹码面分析
{chip_text}

📋 基本面分析
{fundamental_text}

📰 舆情面分析
{sentiment_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """
        return full_text.strip()
