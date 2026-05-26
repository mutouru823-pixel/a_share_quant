# A 股量化分析工具

这是一个基于 Python 的 A 股量化分析工具的基础项目结构，旨在提供健壮、自动化的股票数据获取与清洗服务。

## 核心特性
- **数据源获取**：以 AkShare 为底层数据源，稳定抓取 A 股日线数据。
- **稳健性保障**：内置 HTTP 请求重试机制（借助 `tenacity` 库）和健全的异常捕获与日志。
- **自动清洗**：自动剔除股票代码前缀（如 sh/sz/bj），自动转换列名为标准的 open、high、low、close、volume。
- **标准化数据格式**：最终产出清洗为以日期为索引的 Pandas DataFrame 对象，时间序列升序排列，直接可用作量化测试。

## 项目结构
```text
a_share_quant/
├── requirements.txt      # 依赖管理文件
├── README.md             # 项目说明文档
├── main.py               # 项目入口及示例演示
└── src/
    ├── __init__.py       # 包初始化文件
    └── data_fetcher.py   # 数据拉取与清洗模块
```

## 快速开始

### 1. 安装依赖
请确保你的环境是 Python 3.8 或以上，执行以下命令安装依赖：
```bash
pip install -r requirements.txt
```

### 2. 运行示例
执行 `main.py` 将演示如何拉取贵州茅台（sh600519）近 200 个交易日的数据。
```bash
python main.py
```

## 未来可扩展功能建议
- 添加 `src/strategy/`：用于存放量化交易策略（例如双均线策略，RSI 等）。
- 添加 `src/backtest/`：用于集成回测引擎（如 Backtrader 或者自定义回测框架）。
- 添加数据库支持：定期抓取全市场每天数据写入 MySQL 或 MongoDB 持久化。
