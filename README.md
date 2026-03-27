# A 股量化分析工具

基于 Python 的 A 股量化分析与监控系统，提供 Streamlit 网页交互界面和命令行自动化监控两种使用方式。集成数据获取、技术指标计算、策略监控和飞书通知功能。

## 核心特性
- **Streamlit 网页界面**：提供交互式可视化分析，支持多只股票实时监控与技术指标展示。
- **自动化监控**：基于 `main.py` 和配置文件支持定时自动化监控和飞书机器人通知。
- **数据获取**：通过 AkShare 获取 A 股日线数据，支持实时数据、基金流向、市场情绪等多维度数据。
- **技术指标计算**：集成移动平均线（SMA）、RSI、MACD 等常用量化指标。
- **策略监控**：基于技术面、筹码面、情绪面综合评分生成交易建议。
- **稳健性保障**：内置 HTTP 请求重试、异常捕获、日志记录。

## 项目结构
```text
a_share_quant/
├── app.py                      # Streamlit 网页应用入口
├── main.py                     # CLI 自动化监控入口
├── requirements.txt            # 依赖管理文件
├── config.json                 # 配置文件（自选股、飞书 webhook 等）
├── Dockerfile                  # Docker 容器配置
├── README.md                   # 项目说明文档
├── analytics.db                # SQLite 数据库（建议记录）
└── src/
    ├── __init__.py             # 包初始化文件
    ├── data_fetcher.py         # 数据获取与清洗模块
    ├── strategy_monitor.py     # 策略监控核心模块
    ├── notifier.py             # 飞书通知器
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
- **strategy_monitor.py**：计算 SMA、RSI、MACD 等指标，综合评分生成买卖建议。
- **notifier.py**：通过飞书群机器人 Webhook 发送实时交易警告信息。
- **analytics.py**：记录交易建议到 SQLite 数据库，支持建议准确度评估。
