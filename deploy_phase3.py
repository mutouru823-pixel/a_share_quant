#!/usr/bin/env python3
"""
Phase 3 deployment verification script.
"""

import os
import sys
import logging
import subprocess

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def check_dependencies() -> bool:
    required_packages = [
        'pandas',
        'numpy',
        'sklearn',
        'akshare',
        'streamlit',
    ]

    logger.info('Checking dependencies...')
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            logger.info('OK dependency: %s', package)
        except ImportError:
            missing.append(package)
            logger.warning('Missing dependency: %s', package)

    if not missing:
        return True

    logger.info('Installing missing packages: %s', ', '.join(missing))
    try:
        for package in missing:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
    except subprocess.CalledProcessError as exc:
        logger.error('Install failed: %s', exc)
        return False

    return True


def verify_required_modules() -> bool:
    required_files = [
        'src/indicators_advanced.py',
        'src/fundamental_fetcher.py',
        'src/risk_manager.py',
        'src/analysis_report.py',
        'src/nlp_sentiment.py',
        'src/ml_scoring.py',
    ]

    logger.info('Verifying required modules...')
    missing = [f for f in required_files if not os.path.exists(f)]
    for f in required_files:
        if f in missing:
            logger.error('Missing file: %s', f)
        else:
            logger.info('OK file: %s', f)

    return len(missing) == 0


def test_nlp() -> bool:
    logger.info('Testing NLP sentiment module...')
    try:
        from src.nlp_sentiment import SimpleSentimentAnalyzer

        analyzer = SimpleSentimentAnalyzer()
        score = analyzer.analyze('这支股票涨停了，利好消息，非常看好')
        logger.info('NLP test score: %.2f', score)
        return True
    except Exception as exc:
        logger.exception('NLP test failed: %s', exc)
        return False


def test_ml() -> bool:
    logger.info('Testing ML scoring module...')
    try:
        from src.ml_scoring import EnsembleScorer

        scorer = EnsembleScorer()
        signal = {
            'tech_score': 0.5,
            'chip_score': 0.2,
            'fundamental_score': 0.3,
            'sentiment_score': 0.1,
        }
        score = scorer.calculate_ensemble_score(signal)
        logger.info('ML test score: %.2f', score)
        return True
    except Exception as exc:
        logger.exception('ML test failed: %s', exc)
        return False


def test_strategy_monitor() -> bool:
    logger.info('Testing StrategyMonitor integration...')
    try:
        import pandas as pd
        from src.strategy_monitor import StrategyMonitor

        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        df = pd.DataFrame(
            {
                'open': [100 + i * 0.5 for i in range(50)],
                'high': [101 + i * 0.5 for i in range(50)],
                'low': [99 + i * 0.5 for i in range(50)],
                'close': [100.5 + i * 0.5 for i in range(50)],
                'volume': [1000000] * 50,
            },
            index=dates,
        )

        monitor = StrategyMonitor(df, '600519', sentiment_score=0.2)
        signal = monitor.get_latest_signal()
        logger.info('StrategyMonitor state: %s, total_score: %.2f', signal.get('market_state'), float(signal.get('total_score', 0)))
        return True
    except Exception as exc:
        logger.exception('StrategyMonitor test failed: %s', exc)
        return False


def main() -> int:
    logger.info('=' * 60)
    logger.info('Phase 3 deployment verification')
    logger.info('=' * 60)

    checks = [
        ('Dependencies', check_dependencies()),
        ('Required modules', verify_required_modules()),
    ]

    if not all(ok for _, ok in checks):
        for name, ok in checks:
            logger.info('%s: %s', name, 'PASS' if ok else 'FAIL')
        return 1

    tests = [
        ('NLP sentiment', test_nlp()),
        ('ML scoring', test_ml()),
        ('StrategyMonitor integration', test_strategy_monitor()),
    ]

    logger.info('-' * 60)
    passed = sum(1 for _, ok in tests if ok)
    total = len(tests)
    for name, ok in tests:
        logger.info('%s %s', 'PASS' if ok else 'FAIL', name)
    logger.info('Summary: %d/%d tests passed', passed, total)

    return 0 if passed == total else 1


if __name__ == '__main__':
    raise SystemExit(main())
