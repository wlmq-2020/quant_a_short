# -*- coding: utf-8 -*-
"""
回测分析模块 - Backtrader版本
负责策略回测、指标计算和可视化

【并发架构】
- 策略级别: ProcessPoolExecutor (多进程)
- 股票级别: ThreadPoolExecutor (多线程)
"""
import pandas as pd
import numpy as np
from pathlib import Path
import backtrader as bt
from datetime import datetime
import copy
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed


def run_single_strategy_process(strategy_type, stock_data_dict, config_dict):
    """
    运行单个策略的回测（进程入口函数）
    【策略级】在独立进程中运行

    参数:
        strategy_type: 策略类型
        stock_data_dict: 股票数据字典 {stock_code: df} (已pickle化)
        config_dict: 配置字典

    返回:
        dict: {
            'strategy_type': 策略类型,
            'results': 股票回测结果,
            'start_time': 开始时间,
            'end_time': 结束时间,
            'duration': 耗时
        }
    """
    from datetime import datetime
    import sys
    from pathlib import Path

    # 重建项目路径
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    from config import Config
    from logger.logger import GlobalLogger

    # 重建配置对象
    config = Config()
    for key, value in config_dict.items():
        setattr(config, key, value)

    # 初始化日志
    logger = GlobalLogger(
        log_dir=config.LOG_DIR,
        log_level=config.LOG_LEVEL,
        retention_days=config.LOG_RETENTION_DAYS
    )

    start_time = datetime.now()
    logger.info(f"[进程] 策略 {strategy_type} 开始回测")

    # 创建回测器，在线程池中运行所有股票
    backtester = BacktraderBacktester(config, logger)
    results = backtester.run_backtest_batch(stock_data_dict, strategy_type)

    end_time = datetime.now()
    duration = end_time - start_time

    logger.info(f"[进程] 策略 {strategy_type} 完成，耗时: {duration}")

    return {
        'strategy_type': strategy_type,
        'results': results,
        'start_time': start_time,
        'end_time': end_time,
        'duration': duration
    }


class BacktraderBacktester:
    """A股回测类 - 使用Backtrader框架"""

    def __init__(self, config, logger):
        """
        初始化回测器

        参数:
            config: 配置对象
            logger: 日志对象
        """
        self.config = config
        self.logger = logger
        self.initial_capital = config.INITIAL_CAPITAL
        self.temp_dir = Path(config.TEMP_DIR)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # 导入策略
        from strategy.strategy import get_strategy_class
        self.get_strategy_class = get_strategy_class

    def _build_strategy_params(self, strategy_type, config, override_params=None):
        """
        构建策略参数字典

        参数:
            strategy_type: 策略类型
            config: 配置对象
            override_params: 覆盖参数字典

        返回:
            dict: 策略参数字典
        """
        # 基础参数
        params = {
            'initial_capital': config.INITIAL_CAPITAL,
            'position_ratio': config.POSITION_RATIO,
            'stop_loss_ratio': config.STOP_LOSS_RATIO,
            'take_profit_ratio': config.TAKE_PROFIT_RATIO,
            'commission_rate': config.COMMISSION_RATE,
            'stamp_duty_rate': config.STAMP_DUTY_RATE,
            'transfer_fee_rate': config.TRANSFER_FEE_RATE,
            'min_commission': config.MIN_COMMISSION,
            't1_rule': config.T1_RULE,
            'volume_filter': config.VOLUME_FILTER,
            'volume_ratio': config.VOLUME_RATIO,
        }

        # 从最优参数文件加载策略特定参数
        import json
        best_params_file = config.CONFIG_DIR / "best_strategy_params.json"

        found_in_json = False
        if best_params_file.exists():
            try:
                with open(best_params_file, 'r', encoding='utf-8') as f:
                    all_best_params = json.load(f)

                if strategy_type in all_best_params:
                    strategy_data = all_best_params[strategy_type]
                    if 'best_params' in strategy_data:
                        best_params = strategy_data['best_params']
                        params.update(best_params)
                        found_in_json = True
            except Exception:
                pass

        # 如果JSON里没有，从参数空间取第一个值作为默认值
        if not found_in_json:
            from strategy.param_space import get_all_param_spaces
            param_spaces = get_all_param_spaces()
            if strategy_type in param_spaces:
                param_space = param_spaces[strategy_type]
                default_params = {k: v[0] for k, v in param_space.items()}
                params.update(default_params)

        # 应用覆盖参数（优先级最高）
        if override_params:
            params.update(override_params)

        return params

    def run_backtest(self, df, stock_code=None):
        """
        运行回测 - 使用Backtrader框架

        参数:
            df: 股票数据DataFrame
            stock_code: 股票代码

        返回:
            dict: 回测结果
        """
        if df is None or df.empty:
            if self.logger:
                self.logger.error("数据为空，无法回测")
            return None

        try:
            # 1. 创建Cerebro引擎
            cerebro = bt.Cerebro()

            # 2. 添加数据
            data_feed = self._create_data_feed(df)
            cerebro.adddata(data_feed)

            # 3. 添加策略
            from strategy.strategy import get_strategy_class
            strategy_class = get_strategy_class(self.config.STRATEGY_TYPE)
            params = self._build_strategy_params(self.config.STRATEGY_TYPE, self.config)
            cerebro.addstrategy(strategy_class, **params)

            # 4. 设置初始资金
            cerebro.broker.setcash(self.initial_capital)

            # 5. 设置手续费
            cerebro.broker.setcommission(
                commission=self.config.COMMISSION_RATE,
                margin=None,
                mult=1.0,
                commtype=bt.CommInfoBase.COMM_PERC,
                stocklike=True
            )

            # 6. 添加分析器
            cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
            cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
            cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
            cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
            cerebro.addanalyzer(bt.analyzers.VWR, _name='vwr')
            cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn', timeframe=bt.TimeFrame.Days)

            # 7. 运行回测
            results = cerebro.run()
            strat = results[0]

            # 8. 提取和分析结果
            result = self._analyze_results(strat, df, stock_code)

            return result

        except Exception as e:
            if self.logger:
                self.logger.error(f"回测异常: {str(e)}", exc_info=True)
            return None

    def _create_data_feed(self, df):
        """创建Backtrader数据feed"""
        # 确保数据格式正确
        df_bt = df.copy()

        # 重命名列
        column_mapping = {
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume',
            'date': 'datetime'
        }

        for old_col, new_col in column_mapping.items():
            if old_col in df_bt.columns:
                df_bt[new_col] = df_bt[old_col]

        # 设置datetime索引
        if 'datetime' in df_bt.columns:
            df_bt['datetime'] = pd.to_datetime(df_bt['datetime'])
            df_bt.set_index('datetime', inplace=True)

        # 创建数据feed
        data = bt.feeds.PandasData(
            dataname=df_bt,
            datetime=None,  # 使用索引
            open='open',
            high='high',
            low='low',
            close='close',
            volume='volume',
            openinterest=-1
        )

        return data

    def _analyze_results(self, strat, df, stock_code):
        """分析回测结果"""
        # 获取分析器结果
        returns_analyzer = strat.analyzers.returns.get_analysis()
        sharpe_analyzer = strat.analyzers.sharpe.get_analysis()
        drawdown_analyzer = strat.analyzers.drawdown.get_analysis()
        trades_analyzer = strat.analyzers.trades.get_analysis()

        # 计算基本指标
        initial_capital = self.initial_capital
        final_capital = strat.broker.getvalue()
        total_return = final_capital - initial_capital
        total_return_pct = (total_return / initial_capital) * 100

        # 年化收益率
        trading_days = len(df)
        if trading_days > 0:
            annual_return_pct = ((final_capital / initial_capital) ** (252 / trading_days) - 1) * 100
        else:
            annual_return_pct = 0

        # 最大回撤
        max_drawdown_pct = drawdown_analyzer.get('max', {}).get('drawdown', 0)

        # 夏普比率
        sharpe_ratio = sharpe_analyzer.get('sharperatio', 0)
        if sharpe_ratio is None:
            sharpe_ratio = 0.0

        # 交易统计
        total_trades = trades_analyzer.get('total', {}).get('total', 0)
        won_trades = trades_analyzer.get('won', {}).get('total', 0)
        lost_trades = trades_analyzer.get('lost', {}).get('total', 0)

        # 胜率
        if total_trades > 0:
            win_rate = (won_trades / total_trades) * 100
        else:
            win_rate = 0

        # 盈亏比
        if lost_trades > 0:
            avg_win = trades_analyzer.get('won', {}).get('pnl', {}).get('average', 0)
            avg_loss = abs(trades_analyzer.get('lost', {}).get('pnl', {}).get('average', 0))
            profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float('inf')
        else:
            profit_loss_ratio = 0

        # 收集指标
        metrics = {
            'initial_capital': initial_capital,
            'final_capital': final_capital,
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'annual_return_pct': annual_return_pct,
            'max_drawdown_pct': max_drawdown_pct,
            'sharpe_ratio': sharpe_ratio,
            'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
            'total_trades': total_trades,
            'won_trades': won_trades,
            'lost_trades': lost_trades,
            'trading_days': trading_days
        }

        # 创建投资组合数据
        portfolio_df = self._create_portfolio_data(strat, df)

        # 创建交易记录
        trades_list = self._extract_trades(strat, stock_code)

        result = {
            'portfolio': portfolio_df,
            'trades': pd.DataFrame(trades_list) if trades_list else pd.DataFrame(),
            'metrics': metrics,
            'stock_code': stock_code,
            '_strat': None  # 不返回strat对象，避免pickle问题
        }

        return result

    def _create_portfolio_data(self, strat, df):
        """创建投资组合数据 - 从TimeReturn分析器提取资金曲线"""
        portfolio_df = pd.DataFrame({
            'date': df.index if hasattr(df, 'index') else range(len(df)),
            'equity': [self.initial_capital] * len(df)
        })

        # 尝试从TimeReturn分析器提取资金曲线
        try:
            if hasattr(strat.analyzers, 'timereturn'):
                timereturn_analyzer = strat.analyzers.timereturn.get_analysis()
                if timereturn_analyzer:
                    # 重建资金曲线
                    equity_values = []
                    current_equity = self.initial_capital
                    for i, ret in enumerate(timereturn_analyzer.values()):
                        if i == 0:
                            equity_values.append(current_equity)
                        current_equity = current_equity * (1 + ret)
                        equity_values.append(current_equity)

                    # 对齐数据长度
                    if len(equity_values) > 0:
                        min_len = min(len(portfolio_df), len(equity_values))
                        portfolio_df = portfolio_df.iloc[:min_len].copy()
                        portfolio_df['equity'] = equity_values[:min_len]
        except Exception:
            # 如果提取失败，返回默认值
            pass

        return portfolio_df

    def _extract_trades(self, strat, stock_code):
        """提取交易记录 - 从TradeAnalyzer分析器提取详细交易"""
        trades_list = []

        # 从分析器中提取交易
        trades_analyzer = strat.analyzers.trades.get_analysis()

        if 'total' in trades_analyzer and trades_analyzer['total']['total'] > 0:
            # 尝试提取每笔交易
            if 'trades' in trades_analyzer:
                for trade_id, trade_data in trades_analyzer['trades'].items():
                    if isinstance(trade_data, dict):
                        trade_info = {
                            'stock_code': stock_code,
                            'trade_id': trade_id,
                            'pnl': trade_data.get('pnl', {}).get('net', 0),
                            'pnl_pct': trade_data.get('pnl', {}).get('pct', 0),
                            'is_win': trade_data.get('pnl', {}).get('net', 0) > 0,
                            'bars_in_trade': trade_data.get('barlen', 0)
                        }
                        trades_list.append(trade_info)

        return trades_list

    def plot_results(self, backtest_result, save_path=None):
        """
        绘制回测结果图 - 已禁用，不再生成temp文件

        参数:
            backtest_result: 回测结果字典
            save_path: 保存路径

        返回:
            None
        """
        # 禁用temp文件生成，减少磁盘IO
        return None

    def generate_report(self, backtest_result):
        """
        生成回测报告

        参数:
            backtest_result: 回测结果

        返回:
            str: 报告文本
        """
        if backtest_result is None:
            return "无回测结果"

        metrics = backtest_result['metrics']
        stock_code = backtest_result.get('stock_code', '未知股票')

        report = f"""
        ========================================
        A股短线策略回测报告
        ========================================
        股票代码: {stock_code}
        策略类型: {self.config.STRATEGY_TYPE}
        回测期间: {self.config.get_start_date()} 至 {self.config.get_end_date()}

        绩效指标:
        ----------------------------------------
        初始资金: ¥{metrics['initial_capital']:,.2f}
        最终资金: ¥{metrics['final_capital']:,.2f}
        总收益率: {metrics['total_return_pct']:.2f}%
        年化收益率: {metrics['annual_return_pct']:.2f}%
        最大回撤: {metrics['max_drawdown_pct']:.2f}%
        夏普比率: {metrics['sharpe_ratio']:.3f}

        交易统计:
        ----------------------------------------
        总交易次数: {metrics['total_trades']}
        盈利交易: {metrics['won_trades']}
        亏损交易: {metrics['lost_trades']}
        胜率: {metrics['win_rate']:.2f}%
        盈亏比: {metrics['profit_loss_ratio']:.2f}

        风险指标:
        ----------------------------------------
        交易天数: {metrics['trading_days']}
        日均收益率: {metrics['total_return_pct']/metrics['trading_days']:.4f}%
        ========================================
        """

        return report

    def run_backtest_with_params(self, df, stock_code, strategy_type, override_params=None):
        """
        使用指定参数运行回测

        参数:
            df: 股票数据DataFrame
            stock_code: 股票代码
            strategy_type: 策略类型
            override_params: 覆盖参数字典

        返回:
            dict: 回测结果
        """
        if df is None or df.empty:
            if self.logger:
                self.logger.error("数据为空，无法回测")
            return None

        try:
            # 1. 创建Cerebro引擎
            cerebro = bt.Cerebro()

            # 2. 添加数据
            data_feed = self._create_data_feed(df)
            cerebro.adddata(data_feed)

            # 3. 添加策略（使用覆盖参数）
            from strategy.strategy import get_strategy_class
            strategy_class = get_strategy_class(strategy_type)
            params = self._build_strategy_params(strategy_type, self.config, override_params)
            cerebro.addstrategy(strategy_class, **params)

            # 4. 设置初始资金
            cerebro.broker.setcash(self.initial_capital)

            # 5. 设置手续费
            cerebro.broker.setcommission(
                commission=self.config.COMMISSION_RATE,
                margin=None,
                mult=1.0,
                commtype=bt.CommInfoBase.COMM_PERC,
                stocklike=True
            )

            # 6. 添加分析器
            cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
            cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
            cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
            cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
            cerebro.addanalyzer(bt.analyzers.VWR, _name='vwr')
            cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn', timeframe=bt.TimeFrame.Days)

            # 7. 运行回测
            results = cerebro.run()
            strat = results[0]

            # 8. 提取和分析结果
            result = self._analyze_results(strat, df, stock_code)

            return result

        except Exception as e:
            if self.logger:
                self.logger.error(f"回测异常: {str(e)}")
            return None

    def run_backtest_batch(self, stock_data, strategy_type, override_params=None, max_workers=None):
        """
        并发运行多只股票的回测（使用线程池）
        【股票级】在线程池中执行

        参数:
            stock_data: 股票数据字典 {stock_code: df}
            strategy_type: 策略类型
            override_params: 覆盖参数字典
            max_workers: 最大并发数，默认使用CPU核心数

        返回:
            dict: 回测结果字典 {stock_code: result}
        """
        if max_workers is None:
            max_workers = min(multiprocessing.cpu_count(), 4)

        results = {}
        total = len(stock_data)
        completed = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            futures = {}
            for stock_code, df in stock_data.items():
                future = executor.submit(
                    self.run_backtest_with_params,
                    df, stock_code, strategy_type, override_params
                )
                futures[future] = stock_code

            # 收集结果
            for future in as_completed(futures):
                stock_code = futures[future]
                completed += 1
                try:
                    result = future.result()
                    if result:
                        results[stock_code] = result
                    if completed % 10 == 0 or completed == total:
                        if self.logger:
                            self.logger.info(f"  进度: {completed}/{total}")
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"  {stock_code} 回测失败: {str(e)}")

        return results


# 兼容原有类名
AStockBacktester = BacktraderBacktester


class StrategyComparator:
    """策略对比分析器"""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    def run_all_strategies_backtest(self, stock_data, strategy_types=None):
        """
        运行所有策略的回测并生成对比报告
        【策略级】使用进程池并发执行

        参数:
            stock_data: 股票数据字典 {stock_code: df}
            strategy_types: 策略类型列表，None表示使用所有策略

        返回:
            dict: 所有策略的回测结果
        """
        from datetime import datetime

        if strategy_types is None:
            # 默认使用所有36个策略（基础策略 + 优化策略）
            from strategy.strategy import get_all_strategy_types
            strategy_types = get_all_strategy_types()

        print("\n[2/4] 开始测试策略...")

        # 记录整体开始时间
        overall_start_time = datetime.now()

        # 将配置转换为字典（用于进程间传递）
        config_dict = {}
        for key in dir(self.config):
            if not key.startswith('_') and not callable(getattr(self.config, key)):
                config_dict[key] = getattr(self.config, key)

        # 使用进程池运行所有策略
        all_strategy_results = {}
        strategy_timings = {}

        max_processes = min(multiprocessing.cpu_count(), 2)
        print(f"  使用 {max_processes} 个进程并发执行策略...")

        with ProcessPoolExecutor(max_workers=max_processes) as executor:
            # 提交所有策略任务
            futures = {}
            for strategy_type in strategy_types:
                future = executor.submit(
                    run_single_strategy_process,
                    strategy_type,
                    stock_data,
                    config_dict
                )
                futures[future] = strategy_type

            # 收集结果
            completed = 0
            total = len(strategy_types)

            for future in as_completed(futures):
                strategy_type = futures[future]
                completed += 1

                try:
                    result = future.result()
                    all_strategy_results[result['strategy_type']] = result['results']

                    # 保存时间信息
                    strategy_timings[result['strategy_type']] = {
                        'start_time': result['start_time'],
                        'end_time': result['end_time'],
                        'duration': result['duration']
                    }

                    print(f"  [{completed}/{total}] 策略 {strategy_type} 完成，"
                          f"测试 {len(result['results'])} 只股票，"
                          f"耗时: {result['duration']}")
                    self.logger.info(f"策略 {strategy_type} 完成，"
                                    f"测试 {len(result['results'])} 只股票，"
                                    f"耗时: {result['duration']}")

                except Exception as e:
                    print(f"  [{completed}/{total}] 策略 {strategy_type} 失败: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    self.logger.warning(f"策略 {strategy_type} 失败: {str(e)}")

        # 记录整体结束时间
        overall_end_time = datetime.now()
        overall_duration = overall_end_time - overall_start_time

        # 返回结果和时间信息
        return {
            'results': all_strategy_results,
            'timings': {
                'strategy_timings': strategy_timings,
                'overall_start_time': overall_start_time,
                'overall_end_time': overall_end_time,
                'overall_duration': overall_duration
            }
        }

    def generate_summary_report(self, all_strategy_results, stock_data):
        """
        生成策略对比汇总报告

        参数:
            all_strategy_results: 所有策略的回测结果（包含results和timings）
            stock_data: 股票数据字典

        返回:
            tuple: (strategy_summary, timings_data)
        """
        from datetime import datetime

        # 解析数据结构
        if isinstance(all_strategy_results, dict) and 'results' in all_strategy_results:
            results_data = all_strategy_results['results']
            timings_data = all_strategy_results.get('timings', {})
        else:
            results_data = all_strategy_results
            timings_data = {}

        # 计算每个策略的统计数据
        strategy_summary = []
        for strategy_type, results in results_data.items():
            if not results:
                continue

            returns = [r['metrics']['total_return_pct'] for r in results.values()]
            sharpe_ratios = [r['metrics']['sharpe_ratio'] for r in results.values() if r['metrics']['sharpe_ratio'] is not None]
            win_rates = [r['metrics']['win_rate'] for r in results.values()]
            max_drawdowns = [r['metrics']['max_drawdown_pct'] for r in results.values()]
            total_trades_list = [r['metrics']['total_trades'] for r in results.values()]

            avg_return = sum(returns) / len(returns) if returns else 0
            avg_sharpe = sum(sharpe_ratios) / len(sharpe_ratios) if sharpe_ratios else 0
            avg_win_rate = sum(win_rates) / len(win_rates) if win_rates else 0
            avg_max_drawdown = sum(max_drawdowns) / len(max_drawdowns) if max_drawdowns else 0
            avg_total_trades = sum(total_trades_list) / len(total_trades_list) if total_trades_list else 0
            max_return = max(returns) if returns else 0
            min_return = min(returns) if returns else 0
            positive_count = sum(1 for r in returns if r > 0)
            positive_ratio = (positive_count / len(returns) * 100) if returns else 0

            strategy_summary.append({
                'type': strategy_type,
                'avg_return': avg_return,
                'avg_sharpe': avg_sharpe,
                'avg_win_rate': avg_win_rate,
                'avg_max_drawdown': avg_max_drawdown,
                'avg_total_trades': avg_total_trades,
                'max_return': max_return,
                'min_return': min_return,
                'positive_ratio': positive_ratio,
                'count': len(results)
            })

        # 按收益排序
        strategy_summary.sort(key=lambda x: x['avg_return'], reverse=True)

        return strategy_summary, timings_data

    def save_detailed_report(self, all_strategy_results, strategy_summary, stock_data, report_path, timings_data=None):
        """
        保存详细报告到文件

        参数:
            all_strategy_results: 所有策略的回测结果
            strategy_summary: 策略汇总数据
            stock_data: 股票数据字典
            report_path: 报告保存路径
            timings_data: 时间统计数据
        """
        from datetime import datetime

        # 解析数据结构
        if isinstance(all_strategy_results, dict) and 'results' in all_strategy_results:
            results_data = all_strategy_results['results']
            if timings_data is None:
                timings_data = all_strategy_results.get('timings', {})
        else:
            results_data = all_strategy_results

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("=" * 150 + "\n")
            f.write("策略对比汇总报告\n")
            f.write("=" * 150 + "\n\n")

            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

            # 写入整体时间统计
            if timings_data:
                overall_start = timings_data.get('overall_start_time')
                overall_end = timings_data.get('overall_end_time')
                overall_duration = timings_data.get('overall_duration')
                if overall_start:
                    f.write(f"回测开始时间: {overall_start.strftime('%Y-%m-%d %H:%M:%S')}\n")
                if overall_end:
                    f.write(f"回测结束时间: {overall_end.strftime('%Y-%m-%d %H:%M:%S')}\n")
                if overall_duration:
                    f.write(f"回测总耗时: {overall_duration}\n")

            f.write(f"回测时间范围: {self.config.START_DATE} 至 {self.config.END_DATE}\n")
            f.write(f"回测股票数量: {len(stock_data)} 只\n")
            f.write(f"策略数量: {len(strategy_summary)} 个\n")
            f.write(f"初始资金: ¥{self.config.INITIAL_CAPITAL:,.2f}\n")
            f.write(f"手续费率: {self.config.COMMISSION_RATE*10000:.1f}‱\n")
            f.write(f"印花税率: {self.config.STAMP_DUTY_RATE*1000:.1f}‰\n")
            f.write(f"仓位比例: {self.config.POSITION_RATIO*100:.0f}%\n")
            f.write(f"止损比例: {self.config.STOP_LOSS_RATIO*100:.0f}%\n")
            f.write(f"止盈比例: {self.config.TAKE_PROFIT_RATIO*100:.0f}%\n\n")

            # 写入每个策略的时间统计
            if timings_data and 'strategy_timings' in timings_data:
                f.write("=" * 150 + "\n")
                f.write("各策略执行时间统计:\n")
                f.write("=" * 150 + "\n")
                f.write(f"{'策略类型':<20} {'开始时间':<20} {'结束时间':<20} {'耗时':<15}\n")
                f.write("-" * 150 + "\n")
                for strategy_type, timing in timings_data['strategy_timings'].items():
                    start_time = timing.get('start_time')
                    end_time = timing.get('end_time')
                    duration = timing.get('duration')
                    f.write(f"{strategy_type:<20} ")
                    f.write(f"{start_time.strftime('%H:%M:%S') if start_time else '-':<20} ")
                    f.write(f"{end_time.strftime('%H:%M:%S') if end_time else '-':<20} ")
                    f.write(f"{str(duration) if duration else '-':<15}\n")
                f.write("\n")

            f.write("=" * 150 + "\n")
            f.write("策略排名 (按平均收益率):\n")
            f.write("=" * 150 + "\n")
            f.write(f"{'排名':<5} {'策略类型':<20} {'平均收益率':<12} {'年化收益':<12} {'夏普比率':<10} {'胜率':<10} {'最大回撤':<10} {'最高收益':<12} {'最低收益':<12} {'交易次数':<10} {'正收益占比':<12}\n")
            f.write("-" * 150 + "\n")
            for idx, s in enumerate(strategy_summary, 1):
                # 计算年化收益（假设3年 = 756个交易日）
                total_days = 756
                annual_return = ((1 + s['avg_return']/100) ** (252 / (total_days/3)) - 1) * 100 if s.get('count', 50) > 0 else 0
                f.write(f"{idx:<5} {s['type']:<20} {s['avg_return']:>+10.2f}%  {annual_return:>+10.2f}%  {s['avg_sharpe']:>8.3f}  {s['avg_win_rate']:>8.2f}%  {s['avg_max_drawdown']:>8.2f}%  {s.get('max_return', 0):>+10.2f}%  {s.get('min_return', 0):>+10.2f}%  {s['avg_total_trades']:>8.1f}  {s['positive_ratio']:>9.2f}%\n")

            # 每个策略的详细数据 - TOP 5和BOTTOM 5
            f.write("\n" + "=" * 150 + "\n")
            f.write("各策略详细数据 (TOP 5 和 BOTTOM 5):\n")
            f.write("=" * 150 + "\n")

            # 解析数据结构
            if isinstance(all_strategy_results, dict) and 'results' in all_strategy_results:
                results_data = all_strategy_results['results']
            else:
                results_data = all_strategy_results

            for strategy_type, results in results_data.items():
                if not results:
                    continue

                f.write(f"\n【策略: {strategy_type}】\n")
                f.write("-" * 150 + "\n")

                # 计算该策略的统计
                stock_returns = []
                for stock_code, result in results.items():
                    metrics = result['metrics']
                    stock_returns.append({
                        'code': stock_code,
                        'return': metrics['total_return_pct'],
                        'sharpe': metrics['sharpe_ratio'],
                        'trades': metrics['total_trades'],
                        'win_rate': metrics['win_rate'],
                        'max_drawdown': metrics['max_drawdown_pct'],
                        'annual_return': metrics['annual_return_pct']
                    })

                # 按收益率排序
                stock_returns.sort(key=lambda x: x['return'], reverse=True)

                # TOP 5
                f.write(f"\n  TOP 5 (收益率最高):\n")
                f.write(f"  {'排名':<5} {'股票代码':<12} {'收益率':>12} {'年化收益':>12} {'夏普比率':>10} {'交易次数':>10} {'胜率':>10} {'最大回撤':>12}\n")
                f.write(f"  {'-' * 5} {'-' * 12} {'-' * 12} {'-' * 12} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 12}\n")
                for idx, sr in enumerate(stock_returns[:5], 1):
                    f.write(f"  {idx:<5} {sr['code']:<12} {sr['return']:>+10.2f}%  {sr['annual_return']:>+10.2f}%  {sr['sharpe']:>8.3f}  {sr['trades']:>10d}  {sr['win_rate']:>8.2f}%  {sr['max_drawdown']:>10.2f}%\n")

                # BOTTOM 5
                f.write(f"\n  BOTTOM 5 (收益率最低):\n")
                f.write(f"  {'排名':<5} {'股票代码':<12} {'收益率':>12} {'年化收益':>12} {'夏普比率':>10} {'交易次数':>10} {'胜率':>10} {'最大回撤':>12}\n")
                f.write(f"  {'-' * 5} {'-' * 12} {'-' * 12} {'-' * 12} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 12}\n")
                for idx, sr in enumerate(reversed(stock_returns[-5:]), 1):
                    f.write(f"  {idx:<5} {sr['code']:<12} {sr['return']:>+10.2f}%  {sr['annual_return']:>+10.2f}%  {sr['sharpe']:>8.3f}  {sr['trades']:>10d}  {sr['win_rate']:>8.2f}%  {sr['max_drawdown']:>10.2f}%\n")

                # 该策略的汇总统计
                f.write(f"\n  策略汇总统计:\n")
                returns_list = [sr['return'] for sr in stock_returns]
                sharpe_list = [sr['sharpe'] for sr in stock_returns if sr['sharpe'] is not None]
                trades_list = [sr['trades'] for sr in stock_returns]
                win_rate_list = [sr['win_rate'] for sr in stock_returns]
                max_drawdown_list = [sr['max_drawdown'] for sr in stock_returns]

                avg_return = sum(returns_list) / len(returns_list)
                avg_sharpe = sum(sharpe_list) / len(sharpe_list) if sharpe_list else 0
                avg_trades = sum(trades_list) / len(trades_list)
                avg_win_rate = sum(win_rate_list) / len(win_rate_list)
                avg_max_drawdown = sum(max_drawdown_list) / len(max_drawdown_list)
                max_return = max(returns_list)
                min_return = min(returns_list)
                positive_count = sum(1 for r in returns_list if r > 0)
                positive_ratio = positive_count / len(returns_list) * 100

                f.write(f"    平均收益率: {avg_return:+.2f}%\n")
                f.write(f"    最高收益率: {max_return:+.2f}%\n")
                f.write(f"    最低收益率: {min_return:+.2f}%\n")
                f.write(f"    平均夏普比率: {avg_sharpe:.3f}\n")
                f.write(f"    平均胜率: {avg_win_rate:.2f}%\n")
                f.write(f"    平均最大回撤: {avg_max_drawdown:.2f}%\n")
                f.write(f"    平均交易次数: {avg_trades:.1f}\n")
                f.write(f"    正收益股票数: {positive_count}/{len(returns_list)}\n")
                f.write(f"    正收益占比: {positive_ratio:.2f}%\n")

            f.write("\n" + "=" * 150 + "\n")
            f.write("报告结束\n")
            f.write("=" * 150 + "\n")

    def print_summary(self, strategy_summary, timings_data=None):
        """
        打印策略对比汇总结果

        参数:
            strategy_summary: 策略汇总数据
            timings_data: 时间统计数据
        """
        print("\n[4/4] 汇总结果:")
        print("=" * 120)

        # 输出时间统计
        if timings_data:
            overall_start = timings_data.get('overall_start_time')
            overall_end = timings_data.get('overall_end_time')
            overall_duration = timings_data.get('overall_duration')
            if overall_start and overall_end and overall_duration:
                print(f"\n回测时间统计:")
                print(f"  开始时间: {overall_start.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  结束时间: {overall_end.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  总耗时: {overall_duration}")
                print("-" * 120)

        # 详细策略对比表
        print(f"\n{'排名':<5} {'策略类型':<18} {'平均收益率':<12} {'夏普比率':<10} {'胜率':<10} {'最大回撤':<10} {'交易次数':<10} {'正收益占比':<12}")
        print("-" * 120)
        for idx, s in enumerate(strategy_summary, 1):
            print(f"{idx:<5} {s['type']:<18} {s['avg_return']:>+10.2f}%  {s['avg_sharpe']:>8.3f}  {s['avg_win_rate']:>8.2f}%  {s['avg_max_drawdown']:>8.2f}%  {s['avg_total_trades']:>8.1f}  {s['positive_ratio']:>9.2f}%")

        # 关键信息总结
        print("\n" + "=" * 120)
        print("关键信息总结:")
        print("-" * 120)

        if strategy_summary:
            best = strategy_summary[0]
            worst = strategy_summary[-1]

            print(f"  最优策略: {best['type']}")
            print(f"    - 平均收益率: {best['avg_return']:+.2f}%")
            print(f"    - 夏普比率: {best['avg_sharpe']:.3f}")
            print(f"    - 平均胜率: {best['avg_win_rate']:.2f}%")
            print(f"    - 正收益股票占比: {best['positive_ratio']:.2f}%")

            print(f"\n  最差策略: {worst['type']}")
            print(f"    - 平均收益率: {worst['avg_return']:+.2f}%")
            print(f"    - 夏普比率: {worst['avg_sharpe']:.3f}")

            # 按夏普比率排序
            sorted_by_sharpe = sorted(strategy_summary, key=lambda x: x['avg_sharpe'], reverse=True)
            print(f"\n  风险调整后最优策略 (按夏普比率): {sorted_by_sharpe[0]['type']}")
            print(f"    - 夏普比率: {sorted_by_sharpe[0]['avg_sharpe']:.3f}")
            print(f"    - 平均收益率: {sorted_by_sharpe[0]['avg_return']:+.2f}%")

            # 按胜率排序
            sorted_by_winrate = sorted(strategy_summary, key=lambda x: x['avg_win_rate'], reverse=True)
            print(f"\n  胜率最高策略: {sorted_by_winrate[0]['type']}")
            print(f"    - 平均胜率: {sorted_by_winrate[0]['avg_win_rate']:.2f}%")
            print(f"    - 平均收益率: {sorted_by_winrate[0]['avg_return']:+.2f}%")

        print("\n" + "=" * 120)
