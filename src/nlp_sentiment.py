import logging
import numpy as np
import pandas as pd
from typing import Union

logger = logging.getLogger(__name__)

class SimpleSentimentAnalyzer:
    """
    轻量级情感分析器（基于词汇库方案）
    不依赖重型模型，速度快，适合实时应用
    """
    
    def __init__(self):
        # 正面词库
        self.positive_words = {
            '增长', '利好', '突破', '大涨', '涨停', '分红', '回购', '增持', '超预期',
            '强势', '稳健', '优秀', '领先', '创新', '竞争力', '扩张', '并购', '整合',
            '看好', '建议', '买入', '增加', '上升', '好转', '改善', '高增长', '高质量',
            '龙头', '领头', '佼佼者', '翘楚', '佳绩', '亮眼', '抢眼', '闪耀', '璀璨'
        }
        
        # 负面词库
        self.negative_words = {
            '下跌', '利空', '爆雷', '减持', '跌停', '亏损', '警示', '立案', '退市',
            '弱势', '不稳', '衰落', '滑坡', '困境', '危机', '风险', '隐患', '挑战',
            '看空', '卖出', '减少', '下降', '恶化', '不利', '低增长', '低质量',
            '垫底', '掉队', '落后', '萎靡', '惨淡', '黯淡', '失利', '受挫', '折戟'
        }
    
    def analyze(self, text: str) -> float:
        """
        分析文本情感
        返回: -1.0 (负面) ~ +1.0 (正面)
        """
        if not text or not isinstance(text, str):
            return 0.0
        
        text_lower = text.lower()
        
        pos_count = sum(1 for word in self.positive_words if word in text_lower)
        neg_count = sum(1 for word in self.negative_words if word in text_lower)
        
        total = pos_count + neg_count
        if total == 0:
            return 0.0
        
        # 归一化到 -1 ~ +1
        score = (pos_count - neg_count) / total
        return max(-1.0, min(1.0, score))
    
    def analyze_batch(self, texts: list) -> list:
        """批量分析"""
        return [self.analyze(text) for text in texts]


class AdvancedSentimentAnalyzer:
    """
    高级情感分析器（尝试使用轻量级模型）
    自动降级：如果模型不可用，自动切换到词汇库方案
    """
    
    def __init__(self):
        self.simple_analyzer = SimpleSentimentAnalyzer()
        self.use_model = False
        self.model = None
        
        # 尝试加载预训练模型
        try:
            from transformers import pipeline
            # 使用极其轻量的模型
            self.model = pipeline(
                "sentiment-analysis",
                model="distilbert-base-uncased-finetuned-sst-2-english",
                device=-1  # CPU 模式
            )
            self.use_model = True
            logger.info("✅ 已加载轻量级 NLP 模型")
        except Exception as e:
            logger.warning(f"⚠️ NLP 模型加载失败: {e}，自动切换到词汇库方案")
            self.use_model = False
    
    def analyze(self, text: str) -> float:
        """
        分析文本情感
        返回: -1.0 (负面) ~ +1.0 (正面)
        """
        if not text or not isinstance(text, str):
            return 0.0
        
        try:
            if self.use_model and self.model:
                # 使用预训练模型
                result = self.model(text[:512])[0]  # 限制长度
                label = result['label'].lower()
                score = result['score']
                
                if 'positive' in label or 'positive' == label:
                    return min(1.0, score)
                else:
                    return -min(1.0, score)
            else:
                # 降级到词汇库方案
                return self.simple_analyzer.analyze(text)
        except Exception as e:
            logger.warning(f"情感分析出错: {e}，使用词汇库方案")
            return self.simple_analyzer.analyze(text)
    
    def analyze_batch(self, texts: list) -> list:
        """批量分析"""
        return [self.analyze(text) for text in texts]


class SentimentAggregator:
    """舆情聚合器 - 汇总多条新闻的情感评分"""
    
    def __init__(self):
        self.analyzer = AdvancedSentimentAnalyzer()
    
    def aggregate_sentiment(self, news_list: list) -> float:
        """
        聚合多条新闻的情感评分
        
        参数:
            news_list: 新闻标题或内容列表
        
        返回:
            -1.0 ~ +1.0 的综合情感评分
        """
        if not news_list:
            return 0.0
        
        scores = self.analyzer.analyze_batch(news_list)
        
        # 加权平均（最新的新闻权重更高）
        if len(scores) > 1:
            weights = np.linspace(0.5, 1.0, len(scores))
            weights = weights / weights.sum()
            aggregated = np.average(scores, weights=weights)
        else:
            aggregated = scores[0] if scores else 0.0
        
        return float(aggregated)
    
    def get_sentiment_category(self, score: float) -> str:
        """获取情感类别"""
        if score > 0.3:
            return "强烈看多"
        elif score > 0:
            return "看多"
        elif score > -0.3:
            return "中立偏弱"
        else:
            return "看空"
