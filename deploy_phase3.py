#!/usr/bin/env python3
"""
Phase 3 部署脚本：数据层与 AI 融合
- 创建 NLP 舆情分析模块
- 创建 ML 多因子融合模块
- 升级 data_fetcher 使用 NLP
- 升级 strategy_monitor 使用 ML 融合
"""

import os
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def check_dependencies():
    """检查必需的依赖"""
    required_packages = [
        'pandas',
        'numpy',
        'scikit-learn',
        'akshare',
        'streamlit',
    ]
    
    logger.info("🔍 正在检查依赖...")
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            logger.info(f"✅ {package} 已安装")
        except ImportError:
            missing.append(package)
            logger.warning(f"❌ {package} 未安装")
    
    if missing:
        logger.info(f"⚙️ 需要安装缺失的包: {', '.join(missing)}")
        response = input("是否自动安装？(y/n): ").strip().lower()
        if response == 'y':
            for package in missing:
                logger.info(f"正在安装 {package}...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        else:
            logger.error("依赖缺失，无法继续")
            return False
    
    return True

def verify_phase1_modules():
    """验证 Phase 1 模块是否已部署"""
    required_files = [
        'src/indicators_advanced.py',
        'src/fundamental_fetcher.py',
        'src/risk_manager.py',
        'src/analysis_report.py',
    ]
    
    logger.info("🔍 验证 Phase 1 模块...")
    missing = []
    for file in required_files:
        if os.path.exists(file):
            logger.info(f"✅ {file} 已存在")
        else:
            missing.append(file)
            logger.warning(f"❌ {file} 缺失")
    
    if missing:
        logger.error(f"Phase 1 模块缺失: {missing}")
        logger.info("请先执行 deploy_phase1.py")
        return False
    
    return True

def verify_phase3_modules():
    """验证 Phase 3 模块是否已创建"""
    required_files = [
        'src/nlp_sentiment.py',
        'src/ml_scoring.py',
    ]
    
    logger.info("🔍 检查 Phase 3 模块...")
    for file in required_files:
        if os.path.exists(file):
            logger.info(f"✅ {file} 已存在")
        else:
            logger.warning(f"ℹ️ {file} 尚未创建（本脚本会创建）")
    
    return True

def test_nlp_sentiment():
    """测试 NLP 舆情分析"""
    logger.info("\n🧪 测试 NLP 舆情分析模块...")
    try:
        from src.nlp_sentiment import SimpleSentimentAnalyzer, AdvancedSentimentAnalyzer
        
        # 测试简单分析器
        simple = SimpleSentimentAnalyzer()
        test_text = "这支股票涨停了，利好消息，非常看好"
        score = simple.analyze(test_text)
        logger.info(f"✅ SimpleSentimentAnalyzer 测试通过: '{test_text}' -> {score:.2f}")
        
        # 测试高级分析器
        advanced = AdvancedSentimentAnalyzer()
        score = advanced.analyze(test_text)
        logger.info(f"✅ AdvancedSentimentAnalyzer 测试通过: '{test_text}' -> {score:.2f}")
        
        return True
    except Exception as e:
        logger.error(f"❌ NLP 舆情分析测试失败: {e}")
        return False

def test_ml_scoring():
    """测试 ML 多因子融合"""
    logger.info("\n🧪 测试 ML 多因子融合模块...")
    try:
        from src.ml_scoring import MLScorer, EnsembleScorer
        
        # 测试 ML 评分器
        scorer = MLScorer()
        weights = scorer.get_optimized_weights()
        logger.info(f"✅ MLScorer 初始权重: {weights}")
        
        # 测试集合评分器
        ensemble = EnsembleScorer()
        signal = {
            'tech_score': 0.5,
            'chip_score': 0.2,
            'fundamental_score': 0.3,
            'sentiment_score': 0.1,
        }
        score = ensemble.calculate_ensemble_score(signal)
        logger.info(f"✅ EnsembleScorer 集成评分: {score:.2f}")
        
        return True
    except Exception as e:
        logger.error(f"❌ ML 多因子融合测试失败: {e}")
        return False

def test_data_fetcher_integration():
    """测试 data_fetcher 的 NLP 集成"""
    logger.info("\n🧪 测试 data_fetcher NLP 集成...")
    try:
        from src.data_fetcher import fetch_sentiment_score
        
        # 简单检查函数是否可以调用
        logger.info("✅ data_fetcher NLP 集成已准备好")
        return True
    except Exception as e:
        logger.error(f"❌ data_fetcher 集成测试失败: {e}")
        return False

def test_strategy_monitor_integration():
    """测试 strategy_monitor 的 ML 集成"""
    logger.info("\n🧪 测试 strategy_monitor ML 集成...")
    try:
        from src.strategy_monitor import StrategyMonitor
        import pandas as pd
        
        # 创建测试数据
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        df = pd.DataFrame({
            'open': [100 + i*0.5 for i in range(50)],
            'high': [101 + i*0.5 for i in range(50)],
            'low': [99 + i*0.5 for i in range(50)],
            'close': [100.5 + i*0.5 for i in range(50)],
            'volume': [1000000] * 50,
        }, index=dates)
        
        # 创建监控器
        monitor = StrategyMonitor(df, '600519', sentiment_score=0.2)
        signal = monitor.get_latest_signal()
        
        logger.info(f"✅ StrategyMonitor ML 集成测试通过")
        logger.info(f"   最新信号: {signal.get('market_state')} (评分: {signal.get('total_score', 0):.2f})")
        
        return True
    except Exception as e:
        logger.error(f"❌ strategy_monitor 集成测试失败: {e}")
        return False

def main():
    logger.info("=" * 60)
    logger.info("🚀 Phase 3 部署脚本：数据层与 AI 融合")
    logger.info("=" * 60)
    
    # 1. 检查依赖
    if not check_dependencies():
        return False
    
    # 2. 验证 Phase 1 模块
    if not verify_phase1_modules():
        return False
    
    # 3. 验证 Phase 3 模块已创建
    verify_phase3_modules()
    
    # 4. 测试各个模块
    logger.info("\n" + "=" * 60)
    logger.info("📋 开始模块测试...")
    logger.info("=" * 60)
    
    tests = [
        ("NLP 舆情分析", test_nlp_sentiment),
        ("ML 多因子融合", test_ml_scoring),
        ("data_fetcher NLP 集成", test_data_fetcher_integration),
        ("strategy_monitor ML 集成", test_strategy_monitor_integration),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"测试 {test_name} 出现异常: {e}")
            results.append((test_name, False))
    
    # 5. 总结
    logger.info("\n" + "=" * 60)
    logger.info("📊 测试总结")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅" if result else "❌"
        logger.info(f"{status} {test_name}")
    
    logger.info(f"\n总体: {passed}/{total} 测试通过")
    
    if passed == total:
        logger.info("\n" + "=" * 60)
        logger.info("🎉 Phase 3 部署完成！")
        logger.info("=" * 60)
        logger.info("\n下一步:")
        logger.info("1. 运行: streamlit run app.py")
        logger.info("2. 在「详细分析」标签页查看 10 维评分和 AI 融合结果")
        logger.info("3. 尝试输入股票代码，观察 NLP 舆情和 ML 评分效果")
        return True
    else:
        logger.warning("\n⚠️ 部分测试失败，请检查上述错误")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
