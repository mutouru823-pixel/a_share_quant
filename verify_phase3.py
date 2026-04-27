#!/usr/bin/env python3
"""快速验证 Phase 3 部署"""
import sys
sys.path.insert(0, 'src')

print("🧪 Phase 3 快速验证...\n")

# 测试 1: NLP
try:
    from nlp_sentiment import SimpleSentimentAnalyzer
    analyzer = SimpleSentimentAnalyzer()
    score = analyzer.analyze("利好消息，非常看好这支股票")
    print(f"✅ NLP 舆情分析: {score:.2f}")
except Exception as e:
    print(f"❌ NLP 舆情分析失败: {e}")

# 测试 2: ML
try:
    from ml_scoring import EnsembleScorer
    scorer = EnsembleScorer()
    signal = {'tech_score': 0.5, 'chip_score': 0.2, 'fundamental_score': 0.3, 'sentiment_score': 0.1}
    score = scorer.calculate_ensemble_score(signal)
    print(f"✅ ML 多因子融合: {score:.2f}")
except Exception as e:
    print(f"❌ ML 多因子融合失败: {e}")

# 测试 3: strategy_monitor
try:
    from strategy_monitor import StrategyMonitor
    import pandas as pd
    dates = pd.date_range('2024-01-01', periods=50, freq='D')
    df = pd.DataFrame({
        'open': [100 + i*0.5 for i in range(50)],
        'high': [101 + i*0.5 for i in range(50)],
        'low': [99 + i*0.5 for i in range(50)],
        'close': [100.5 + i*0.5 for i in range(50)],
        'volume': [1000000] * 50,
    }, index=dates)
    
    monitor = StrategyMonitor(df, '600519', sentiment_score=0.2)
    signal = monitor.get_latest_signal()
    print(f"✅ Strategy Monitor: 市场状态={signal.get('market_state')}, 评分={signal.get('total_score'):.2f}")
except Exception as e:
    print(f"❌ Strategy Monitor 失败: {e}")
    import traceback
    traceback.print_exc()

print("\n🎉 Phase 3 快速验证完成！")
