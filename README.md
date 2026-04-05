# A股短线量化交易回测系统

工业级、高规范、全模块化的A股短线量化交易程序。

## 项目结构

```
quant_a_short/
├── main.py                 # 全局主入口，一键启动全流程
├── config                  # 全局配置文件
├── requirements.txt        # 依赖包列表
├── logger/                 # 全局日志模块
├── data_fetcher/           # 数据下载模块
├── strategy/               # 策略模块
├── backtest/               # 回测模块
├── paper_trade/            # 模拟交易模块
├── reporter/               # 统一量化报表模块
├── cleaner/                # 文件清理模块
├── saved_data/             # 正式数据目录
├── reports/                # 报表输出目录
├── logs/                   # 日志目录
└── temp/                   # 临时目录
```

## 快速开始

### 1. 安装依赖

```bash
cd quant_a_short
pip install -r requirements.txt
```

### 2. 配置参数

编辑 `config.py` 文件，修改股票代码、时间范围、策略类型等参数。

### 3. 运行系统

```bash
python main.py
```

## 核心功能

- **数据下载**: 支持A股日线/60分钟线数据获取
- **策略模块**: MACD+KDJ共振、RSI、布林带三种策略
- **回测分析**: 收益、回撤、胜率、夏普比率等指标
- **模拟交易**: T+1合规的模拟盘交易
- **统一报表**: Excel/CSV/图片格式输出
- **全局日志**: 全流程统一记录
- **自动清理**: 临时文件自动清理

## 交易规则

- 手续费：万分之2.5
- 印花税：千分之1（仅卖出）
- 涨跌幅：10%
- T+1规则：严格执行
