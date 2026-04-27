# A 股量化分析工具

基于 Python 的 A 股量化分析与监控系统，提供 Streamlit 交互式分析、命令行自动化执行、Walk-forward 回测评估三类能力。

该项目面向数据分析/数据科学岗位，强调可复现的数据闭环：
数据采集 -> 特征计算 -> 策略打分 -> 风险调整 -> 回测评估 -> 报告导出。

## 核心特性
- **Streamlit 网页界面**：提供交互式可视化分析，支持多只股票实时监控与技术指标展示。
- **自动化监控**：基于 `main.py` 和配置文件支持定时自动化监控。
- **数据获取**：通过 AkShare 获取 A 股日线数据，支持实时数据、基金流向、市场情绪等多维度数据。
- **技术指标计算**：集成移动平均线（SMA）、RSI、MACD 等常用量化指标。
- **策略监控**：基于技术面、筹码面、情绪面综合评分生成交易建议，含风险惩罚、置信度与建议仓位。
- **研究级回测**：支持 Walk-forward 回测，输出收益率、年化、夏普、最大回撤、命中率等关键指标，并支持基准对比（Alpha/Beta/超额收益）。
- **稳健性保障**：内置 HTTP 请求重试、异常捕获、日志记录。

## 面试亮点（适合腾讯/滴滴等数据岗）
- **数据工程能力**：有明确的数据获取、清洗、异常兜底与降级机制。
- **建模思维**：从单一打分升级为“风险调整后分数 + 置信度 + 建议仓位”。
- **实验评估意识**：使用 Walk-forward 回测避免未来函数，提供可量化评估指标。
- **可解释性**：输出多维指标解读文本，支持业务汇报。
- **产出导向**：可一键导出 CSV/JSON 报告，便于复盘与展示。

## 项目结构
```text
a_share_quant/
├── app.py                      # Streamlit 网页应用入口
├── main.py                     # CLI 自动化监控入口
├── run_backtest.py             # Walk-forward 回测脚本
├── run_grid_search.py          # 参数网格搜索脚本（Top-N）
├── requirements.txt            # 依赖管理文件
├── config.json                 # 配置文件（自选股、飞书 webhook 等）
├── Dockerfile                  # Docker 容器配置
├── README.md                   # 项目说明文档
├── analytics.db                # SQLite 数据库（建议记录）
└── src/
    ├── __init__.py             # 包初始化文件
    ├── data_fetcher.py         # 数据获取与清洗模块
    ├── strategy_monitor.py     # 策略监控核心模块
    ├── backtest_engine.py      # 回测与指标评估引擎
    ├── parameter_search.py     # 参数搜索与排序引擎
    └── analytics.py            # 数据分析与建议记录
```

## 快速开始

### 1. 安装依赖
确保环境是 Python 3.8 或以上，执行：
```bash
pip install -r requirements.txt
```

### 2. 使用 Streamlit 网页界面（推荐）
启动网页应用，提供可视化交互：
```bash
streamlit run app.py
```
或使用模块方式：
```bash
python -m streamlit run app.py
```

然后在浏览器中打开 http://localhost:8501

### 3. 命令行自动化监控（可选）
编辑 `config.json` 配置监控参数，然后执行：
```bash
python main.py --mode start    # 市场开盘时播报
python main.py --mode mid      # 市场中间播报
python main.py --mode end      # 市场收盘时播报
```

### 4. Walk-forward 回测（面试推荐演示）
运行示例：
```bash
python run_backtest.py --symbols sz000001,sh600519,sz300750 --days 260 --warmup 60 --benchmark sh000300 --out outputs/backtest
```

会产出：
- `outputs/backtest_summary.csv`
- `outputs/backtest_detail.csv`
- `outputs/backtest_summary.json`

核心指标含义：
- `cumulative_return`: 累计收益率
- `annualized_return`: 年化收益率
- `annualized_volatility`: 年化波动率
- `sharpe`: 夏普比率
- `max_drawdown`: 最大回撤
- `hit_rate`: 命中率（方向判断正确比例）
- `coverage`: 策略实际出手覆盖率
- `benchmark_cumulative_return`: 基准累计收益
- `excess_return`: 相对基准超额收益
- `alpha`: 年化 Alpha（CAPM 近似）
- `beta`: Beta（相对基准的系统性风险暴露）
- `information_ratio`: 信息比率（主动收益/主动风险）

### 5. 参数网格搜索（面试强烈推荐）
运行示例：
```bash
python run_grid_search.py --symbols sz000001,sh600519 --days 260 --warmup 60 --benchmark sh000300 --long-thresholds 0.2,0.25,0.3 --short-thresholds 0.2,0.25,0.3 --min-confidences 0.5,0.6,0.7 --min-positions 20,30,40 --top-n 10 --out outputs/grid_search
```

会产出：
- `outputs/grid_search_grid_all.csv`（全部参数组合结果）
- `outputs/grid_search_grid_top10.csv`（Top-10 组合）
- `outputs/grid_search_grid_top10.json`

排序逻辑：
- 以 `objective_score` 为主排序（融合 Sharpe、信息比率、超额收益、回撤）
- 可快速得到面试展示用的“最优参数配置”和“参数敏感性结论”

## 配置说明

### config.json 示例
```json
{
  "watchlist": ["600519", "600000", "000858"],
  "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
  "sentiment_weight": 0.2,
  "fund_flow_weight": 0.3,
  "tech_weight": 0.5
}
```

## 主要模块说明

- **data_fetcher.py**：从 AkShare 获取日线数据、实时数据、基金流向、市场情绪等。
- **strategy_monitor.py**：计算 SMA、RSI、MACD 等指标，输出风险调整后的综合评分、置信度和建议仓位。
- **backtest_engine.py**：执行 Walk-forward 回测并计算风险收益指标。
- **analytics.py**：记录交易建议到 SQLite 数据库，支持建议准确度评估。
