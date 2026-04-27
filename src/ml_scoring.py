import logging
import numpy as np
import pandas as pd
from sklearn.linear_model import Lasso
from sklearn.ensemble import GradientBoostingClassifier
from typing import Tuple

logger = logging.getLogger(__name__)

class MLScorer:
    """
    机器学习多因子融合评分器
    基于历史交易数据自动优化各维度权重
    """
    
    def __init__(self):
        self.model = None
        self.weights = {
            'tech_score': 0.40,
            'chip_score': 0.30,
            'fundamental_score': 0.20,
            'sentiment_score': 0.10,
        }
        self.is_trained = False
    
    def prepare_features(self, signals_list: list) -> Tuple[np.ndarray, np.ndarray]:
        """
        准备特征和标签
        
        参数:
            signals_list: 包含历史信号和实际结果的列表
            [
                {
                    'tech_score': 0.5,
                    'chip_score': -0.2,
                    'fundamental_score': 0.3,
                    'sentiment_score': 0.1,
                    'actual_return': 0.05,  # 实际收益率
                },
                ...
            ]
        
        返回:
            (X, y) 特征矩阵和标签向量
        """
        if not signals_list or len(signals_list) < 10:
            logger.warning("历史数据不足 10 条，无法训练模型")
            return None, None
        
        features = []
        labels = []
        
        for signal in signals_list:
            feature = [
                signal.get('tech_score', 0),
                signal.get('chip_score', 0),
                signal.get('fundamental_score', 0),
                signal.get('sentiment_score', 0),
            ]
            features.append(feature)
            
            # 标签：实际收益率是否为正
            actual_return = signal.get('actual_return', 0)
            label = 1 if actual_return > 0 else 0
            labels.append(label)
        
        return np.array(features), np.array(labels)
    
    def train(self, signals_list: list) -> bool:
        """
        训练模型
        
        参数:
            signals_list: 历史信号列表
        
        返回:
            训练是否成功
        """
        try:
            X, y = self.prepare_features(signals_list)
            
            if X is None or y is None:
                logger.warning("无法准备训练数据")
                return False
            
            # 使用 GradientBoostingClassifier
            self.model = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )
            self.model.fit(X, y)
            
            # 提取特征重要性作为权重
            importances = self.model.feature_importances_
            total_importance = importances.sum()
            
            if total_importance > 0:
                self.weights['tech_score'] = importances[0] / total_importance
                self.weights['chip_score'] = importances[1] / total_importance
                self.weights['fundamental_score'] = importances[2] / total_importance
                self.weights['sentiment_score'] = importances[3] / total_importance
            
            self.is_trained = True
            logger.info(f"✅ 模型训练成功，更新权重: {self.weights}")
            return True
        
        except Exception as e:
            logger.warning(f"模型训练失败: {e}，使用默认权重")
            return False
    
    def predict_proba(self, features: list) -> float:
        """
        预测上涨概率
        
        参数:
            features: [tech_score, chip_score, fundamental_score, sentiment_score]
        
        返回:
            0 ~ 1 之间的上涨概率
        """
        if not self.is_trained or self.model is None:
            # 未训练时使用加权平均
            weighted_sum = (
                features[0] * self.weights['tech_score'] +
                features[1] * self.weights['chip_score'] +
                features[2] * self.weights['fundamental_score'] +
                features[3] * self.weights['sentiment_score']
            )
            # 转换到 0 ~ 1
            proba = (weighted_sum + 1.0) / 2.0
            return max(0.0, min(1.0, proba))
        
        try:
            X = np.array([features])
            proba = self.model.predict_proba(X)[0, 1]
            return proba
        except Exception as e:
            logger.warning(f"预测概率失败: {e}")
            return 0.5
    
    def get_optimized_weights(self) -> dict:
        """获取优化后的权重"""
        return self.weights.copy()
    
    def update_weights_manually(self, new_weights: dict) -> None:
        """手动更新权重"""
        for key, value in new_weights.items():
            if key in self.weights:
                self.weights[key] = value
        
        # 归一化
        total = sum(self.weights.values())
        if total > 0:
            for key in self.weights:
                self.weights[key] /= total
        
        logger.info(f"权重已更新: {self.weights}")


class EnsembleScorer:
    """
    集成评分器 - 结合多个评分方法
    """
    
    def __init__(self):
        self.ml_scorer = MLScorer()
        self.use_ml = False
    
    def train_with_history(self, signals_list: list) -> bool:
        """用历史数据训练 ML 模型"""
        if len(signals_list) >= 10:
            self.use_ml = self.ml_scorer.train(signals_list)
            return self.use_ml
        return False
    
    def calculate_ensemble_score(self, signal: dict) -> float:
        """
        计算集成评分
        
        参数:
            signal: {tech_score, chip_score, fundamental_score, sentiment_score}
        
        返回:
            最终综合评分 (-1 ~ +1)
        """
        features = [
            signal.get('tech_score', 0),
            signal.get('chip_score', 0),
            signal.get('fundamental_score', 0),
            signal.get('sentiment_score', 0),
        ]
        
        if self.use_ml:
            # 使用 ML 预测概率
            proba = self.ml_scorer.predict_proba(features)
            # 转换到 -1 ~ +1
            score = (proba - 0.5) * 2.0
        else:
            # 使用加权平均
            weights = self.ml_scorer.get_optimized_weights()
            score = (
                features[0] * weights['tech_score'] +
                features[1] * weights['chip_score'] +
                features[2] * weights['fundamental_score'] +
                features[3] * weights['sentiment_score']
            )
        
        return max(-1.0, min(1.0, score))
    
    def get_weights(self) -> dict:
        """获取当前权重"""
        return self.ml_scorer.get_optimized_weights()
