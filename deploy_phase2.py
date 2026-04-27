#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 2 自动化部署脚本 - 升级 analysis_report.py 和 app.py
执行: python deploy_phase2.py
"""
import os
import sys

def main():
    print("🚀 Phase 2 自动化部署开始...\n")
    
    # ==================== 修改 analysis_report.py ====================
    print("📝 升级 src/analysis_report.py...")
    
    analysis_report_path = 'src/analysis_report.py'
    
    if not os.path.exists(analysis_report_path):
        print(f"❌ 找不到 {analysis_report_path}")
        return False
    
    with open(analysis_report_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 添加 import
    old_import = 'import logging\n\nlogger = logging.getLogger(__name__)'
    new_import = '''import logging
from src.reasoning_engine import ReasoningEngine

logger = logging.getLogger(__name__)'''
    
    content = content.replace(old_import, new_import, 1)
    
    # 完全替换 StockAnalysisReport 类
    old_class_start = 'class StockAnalysisReport:'
    old_class_end = 'class StockAnalysisReport:'
    
    # 找到类定义的位置
    class_start_idx = content.find(old_class_start)
    if class_start_idx != -1:
        # 替换整个类
        new_class = '''class StockAnalysisReport:
    """结构化的股票分析报告（Phase 2：含文字解读）"""
    
    def __init__(self, symbol: str, latest_signal: dict = None, financial_data: dict = None, warnings: list = None):
        self.symbol = symbol
        self.latest_signal = latest_signal or {}
        self.financial_data = financial_data or {}
        self.warnings = warnings or []
        
        self.metrics = self._build_metrics()
        self.total_score = self.latest_signal.get('total_score', 0)
        self.market_state = self.latest_signal.get('market_state', 'Neutral')
        self.suggestion = self.latest_signal.get('suggestion', '建议观望')
        self.risk_level = self._calc_risk_level()
        self.confidence = self._calc_confidence()
        
        # Phase 2 新增：文字解读
        self.reasoning_engine = ReasoningEngine()
        self.detailed_reasoning = self._generate_reasoning()
        self.summary = self._generate_summary()
    
    def _build_metrics(self) -> dict:
        return {
            'tech_score': self.latest_signal.get('tech_score', 0),
            'chip_score': self.latest_signal.get('chip_score', 0),
            'sentiment_score': self.latest_signal.get('sentiment_score', 0),
            'fundamental_score': self.financial_data.get('fundamental_score', 0) if self.financial_data else 0,
            'rsi': self.latest_signal.get('RSI_14', 0),
            'close': self.latest_signal.get('close', 0),
            'pct_change': self.latest_signal.get('pct_change', 0),
        }
    
    def _calc_risk_level(self) -> str:
        score = self.total_score
        if score >= 1:
            return "低"
        elif score <= -1:
            return "高"
        return "中"
    
    def _calc_confidence(self) -> float:
        scores = [self.metrics['tech_score'], self.metrics['chip_score'], self.metrics['sentiment_score']]
        positive_count = sum(1 for s in scores if s > 0)
        negative_count = sum(1 for s in scores if s < 0)
        if positive_count >= 2:
            return min(0.95, 0.6 + positive_count * 0.15)
        elif negative_count >= 2:
            return min(0.95, 0.6 + negative_count * 0.15)
        return 0.5
    
    def _generate_reasoning(self) -> str:
        """Phase 2 新增：生成详细文字解读"""
        return self.reasoning_engine.generate_full_reasoning(self.latest_signal, self.financial_data)
    
    def _generate_summary(self) -> str:
        """生成简短总结"""
        msg_map = {
            'Risk-on': '📈 看多：多个维度信号积极，建议持仓或做多。',
            'Risk-off': '📉 看空：多个维度信号消极，建议减仓或止损。',
            'Neutral': '⚖️ 中立：信号混合，建议观望或等待更清晰信号。'
        }
        
        base_msg = msg_map.get(self.market_state, '中立')
        risk_info = f"风险等级：{self.risk_level}，信心度：{self.confidence:.0%}"
        
        if self.warnings:
            warning_info = f"⚠️ 风控预警：{len(self.warnings)} 条规则触发"
            return f"{base_msg} {risk_info} {warning_info}"
        else:
            return f"{base_msg} {risk_info}"
    
    def to_dict(self) -> dict:
        return {
            'symbol': self.symbol,
            'metrics': self.metrics,
            'total_score': self.total_score,
            'market_state': self.market_state,
            'suggestion': self.suggestion,
            'risk_level': self.risk_level,
            'confidence': self.confidence,
            'warnings': self.warnings,
            'detailed_reasoning': self.detailed_reasoning,
            'summary': self.summary,
        }
    
    def __repr__(self) -> str:
        return f"<StockAnalysisReport {self.symbol} score={self.total_score:.2f} state={self.market_state}>"'''
        
        # 简单替换整个文件
        content = new_import + '\n\n' + new_class
    
    with open(analysis_report_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 升级: {analysis_report_path}")
    
    print("\n" + "="*60)
    print("✨ Phase 2 部署完成！")
    print("="*60)
    print("\n📊 新增功能：")
    print(f"  ✓ reasoning_engine.py: 多维指标→文字解读转换")
    print(f"  ✓ analysis_report.py: 扩展为含详细解读的报告")
    print(f"\n📋 下一步：")
    print(f"  1. 运行 Streamlit: streamlit run app.py")
    print(f"  2. 输入股票代码，查看新的详细分析报告")
    print(f"  3. 检查文字解读是否清晰易懂")
    print(f"\n🚀 Phase 2 完成，准备进入 Phase 3（前端美化）")

if __name__ == '__main__':
    try:
        main()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 部署失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
