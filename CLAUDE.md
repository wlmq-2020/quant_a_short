# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an industrial-grade A-shares (China stock market) short-term quantitative trading backtest system. Built on [Backtrader](https://github.com/mementum/backtrader), it supports 36 trading strategies across 50 SSE 50 constituent stocks.

**Key Contraints**:
- Market: China A-shares with T+1 trading, 10% price limits, real commission/stamp duty rules
- No real trading — only backtesting and paper trading
- Data must come from real A-share sources (akshare primary, baostock fallback)
- All code in classes, no standalone scripts
- One feature = one folder

## Quick Start

```bash
cd quant_a_short
pip install -r requirements.txt
python main.py                    # Single strategy backtest (default: RSI)
python main.py --compare-strategies  # Compare all 36 strategies
python main.py --optimize rsi        # Optimize a single strategy's parameters
python main.py --optimize-all        # Optimize all 36 strategies
python main.py --fetch-data          # Download stock data for all configured stocks
python main.py --update-data         # Incremental data update
python main.py --progress            # View optimization progress logs
python main.py --evolve-strategies   # Strategy evolution (rank/eliminate by metrics)
```

## Running Tests

```bash
python tests/run_tests.py              # All tests
python tests/run_tests.py backtest     # Backtest tests only
python tests/run_tests.py data         # Data fetcher tests only
```

Tests are run automatically before every main.py execution (tests must pass to proceed).

## Architecture

### Data Flow
```
Config → AStockDataFetcher (akshare/baostock) → CSV cache in saved_data/
  → BacktraderBacktester (Cerebro engine) → Strategy class with params
    → Metrics (returns, sharpe, drawdown, etc.) → Report
```

### Concurrency Architecture
- **Strategy level**: `ProcessPoolExecutor` (max 2) for strategy comparison
- **Stock level**: `ThreadPoolExecutor` (max 4) for multi-stock backtests within a strategy
- **Optimization level**: `ThreadPoolExecutor` (max 4) for parameter grid search — no nested pools to avoid deadlock on Windows
- File-level locking via `FileRWLock` for safe concurrent writes to `best_strategy_params.json`

### Config (config/__init__.py)
- Single `Config` class with all parameters (stock list, trading rules, strategy type, etc.)
- 50 predetermined SSE 50 stocks with sh/sz prefixes
- Trading rules: 0.025% commission (min ¥5), 0.1% stamp duty (sell only), 0.001% transfer fee, 10% price limits
- Optimized parameters cached in `config/best_strategy_params.json`

### Strategies (strategy/)
- 36 strategy types defined in `param_space.py` with search ranges for optimization
- Each strategy extends `BaseAStockStrategy` which inherits from `bt.Strategy`
- All strategies implement the same pattern: `_add_indicators()` + `next()` with buy/sell logic
- Strategy factory in `strategy.py`: `get_strategy_class(strategy_type)` → backtrader class

### Backtesting (backtest/)
- `BacktraderBacktester`: Main engine wrapping `bt.Cerebro` — creates data feeds, configures broker with A-share commission/slippage, runs backtests, analyzes results
- `StrategyComparator`: Runs all strategies across all stocks (multi-process), generates comparison reports
- `StrategyParameterOptimizer`: Grid search with time-series cross-validation, composite scoring (return 30% + sharpe 20% + win rate 15% + calmar 20% + drawdown penalty 10% + trade frequency 5%)
- `AStockCommission`: Custom Backtrader commission model matching real A-share rules
- `MarketCapSlippage`: Slippage model with 0.1% for large-caps, 0.3% for small-mid caps

### Data Fetcher (data_fetcher/)
- `AStockDataFetcher`: Dual-source data fetching (akshare → baostock fallback)
- Supports daily and 60-min K-line periods
- Full fetch and incremental update modes
- Data saved as CSV in `saved_data/`

### Paper Trading (paper_trade/)
- `PaperTrader`: Simulates T+1-compliant trading with position management, fee calculation, and daily portfolio tracking

### Utilities (utils/)
- `AtomicWriter`: Atomic JSON/CSV/text file writes via temp-file + replace pattern
- `FileRWLock`: Cross-process file lock using platform APIs (LockFileEx on Windows, flock on Linux)

## Important Rules

1. **Project structure enforcement**: `main.py` validates allowed files/dirs at root level — no rogue files
2. **No fake data**: Must use real A-share data via akshare or baostock
3. **T+1 enforced**: All strategies must respect same-day sell restriction
4. **Comments in Chinese**: Code comments should be in Chinese
5. **Optimization discipline**: Must always read historical best from `config/best_strategy_params.json`; only update when new composite score exceeds historical best; auto-backup before overwriting
6. **No nested thread pools**: Stock-level backtests within optimizer run serially to avoid Windows deadlocks

## Key Configuration

Configure everything in `config/__init__.py`:
- `Config.STOCK_CODES`: Stock list to backtest
- `Config.STRATEGY_TYPE`: Active strategy (set via `main.py --optimize` too)
- `Config.KLINE_PERIOD`: "daily" or "60min"
- `Config.INITIAL_CAPITAL`, `Config.POSITION_RATIO`, `Config.STOP_LOSS_RATIO`, etc.
- `Config.COMMISSION_RATE`, `Config.STAMP_DUTY_RATE`, `Config.TRANSFER_FEE_RATE`

## Key Files to Modify

- `config/__init__.py`: Stock list, trading parameters, strategy selection
- `strategy/param_space.py`: Add/modify strategy parameter search spaces
- `strategy/strategy.py`: Add new strategy implementations
- `backtest/backtester.py`: Modify backtesting logic
- `backtest/optimizer.py`: Modify optimization logic
