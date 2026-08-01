# A股量化分析工具 v2

多源数据驱动、多维评分、风控一体化的 A 股量化分析系统。

## 核心升级（v2）

- **多源数据引擎**：腾讯财经 > 东方财富 > AkShare 三级自动降级，告别单源被封困境
- **连续评分系统**：-100 ~ +100 精细评分，替代旧版 -1/0/+1 粗糙判定
- **四维分析框架**：技术面(50%) + 量价面(25%) + 资金面(15%) + 舆情面(10%) 加权融合
- **完整指标体系**：SMA/EMA/RSI/MACD/布林线/OBV/KDJ/ATR/动量/量价背离
- **内嵌风控引擎**：8条风控规则（均线破位、RSI超买、MACD顶背离、放量滞涨等）
- **置信度评估**：基于信号一致性、数据充足度、波动率的综合置信度
- **仓位建议**：评分 × 置信度 × 波动率惩罚 → 量化仓位百分比
- **财新数据增强**：接入财新数据API，NLP驱动的精准舆情 + 宏观环境研判

## 项目结构

```
a_share_quant/
├── config.json              # 配置文件（自选股、API Key、风控参数）
├── main.py                  # 命令行入口
├── app.py                   # Streamlit Web 界面
├── requirements.txt         # 依赖
├── src/
│   ├── data_sources.py      # [新] 多源数据引擎（腾讯/东财/AkShare）
│   ├── caixin_data.py       # [新] 财新数据 API 客户端
│   ├── strategy_monitor.py  # [重写] 多维策略监控引擎 v2
│   ├── indicators_advanced.py  # 高级技术指标库
│   ├── ml_scoring.py        # ML多因子融合评分器
│   ├── risk_manager.py      # 风控规则引擎
│   ├── reasoning_engine.py  # 文字解读生成
│   ├── analysis_report.py   # 分析报告生成
│   ├── backtest_engine.py   # 回测引擎
│   ├── parameter_search.py  # 参数网格搜索
│   ├── fundamental_fetcher.py  # 基本面数据
│   ├── nlp_sentiment.py     # NLP情绪分析
│   ├── notifier.py          # 飞书通知
│   └── analytics.py         # 胜率追踪
└── outputs/                 # 回测输出
```

## 快速开始

```bash
pip install -r requirements.txt

# 命令行分析
python main.py --symbols sh600519,sz000858 --days 200

# 新版 Web 仪表盘（推荐）
python api_server.py
# 打开 http://localhost:8000

# Streamlit 保底界面
streamlit run app.py
# 打开 http://localhost:8501
```

## 配置说明

编辑 `config.json`：

```json
{
    "target_symbols": ["sh600519", "sz000858"],
    "target_days": 200,
    "caixin_api_key": "你的财新数据API Key",
    "feishu_webhook": "飞书机器人Webhook地址"
}
```

## 数据源说明

| 优先级 | 数据源 | 用途 | 稳定性 |
|--------|--------|------|--------|
| 1 | 腾讯财经 | 实时行情、日K线 | 极高 |
| 2 | 东方财富 | K线、资金流、板块、新闻 | 高 |
| 3 | AkShare | 兜底（场外基金等） | 中 |
| 增强 | 财新数据 | 宏观、NLP舆情、机构观点 | 高（付费） |

## 评分体系

综合评分 = 技术面×50% + 量价面×25% + 资金面×15% + 舆情面×10%

- 技术面：均线排列、MACD状态、RSI、KDJ、布林带位置、动量
- 量价面：量比、OBV趋势、量价背离、ATR波动率
- 资金面：主力净流入分级、超大单方向
- 舆情面：加权关键词匹配 + 财新NLP增强
