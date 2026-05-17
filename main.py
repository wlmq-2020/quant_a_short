# -*- coding: utf-8 -*-
"""
A股短线量化交易系统 - 主引擎
核心功能：
1. 单策略回测 (默认运行)
2. 所有策略对比 (--compare-strategies)
3. 参数优化 (--optimize, --optimize-all)

【项目结构规则】
- strategy/       - 放策略相关代码
- backtest/       - 放回测相关代码
- data_fetcher/   - 放数据处理相关代码
- logger/         - 放日志相关代码
- config.py       - 配置文件
- main.py         - 主入口（同级只允许这一个文件）
"""
import sys
import io
# 修复Windows控制台中文乱码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from logger.logger import GlobalLogger
from data_fetcher.data_fetcher import AStockDataFetcher




class QuantMainEngine:
    """量化主引擎类 - 单策略回测"""

    def __init__(self):
        """初始化主引擎"""
        # 确保目录存在
        Config.ensure_dirs()

        # 初始化日志
        self.logger = GlobalLogger(
            log_dir=Config.LOG_DIR,
            log_level=Config.LOG_LEVEL,
            retention_days=Config.LOG_RETENTION_DAYS
        )

        # 初始化各模块
        self.data_fetcher = AStockDataFetcher(Config, self.logger)

        self.logger.info("=" * 60)
        self.logger.info("A股短线量化交易系统启动 (Backtrader版本)")
        self.logger.info("=" * 60)

    def run(self):
        """运行全流程 - 单策略回测"""
        try:
            self.logger.info("=" * 60)
            self.logger.info("开始运行Backtrader量化系统")
            self.logger.info("=" * 60)

            # 1. 加载数据
            stock_data = self._get_stock_data()
            if not stock_data:
                self.logger.error("无可用数据，系统退出")
                return

            # 2. 运行回测
            all_results = self._run_backtests(stock_data)

            # 3. 输出汇总结果
            self._print_summary(all_results)

            self.logger.info("=" * 60)
            self.logger.info("Backtrader量化系统运行完成！")
            self.logger.info("=" * 60)

        except Exception as e:
            self.logger.error(f"系统运行异常: {str(e)}", exc_info=True)
            raise

    def _get_stock_data(self):
        """获取股票数据 - 直接加载本地数据"""
        stock_data = {}
        self.logger.info("加载本地股票数据")
        for stock_code in Config.get_stock_list():
            df = self.data_fetcher.load_data(stock_code, Config.KLINE_PERIOD)
            if df is not None and not df.empty:
                stock_data[stock_code] = df
                self.logger.debug(f"加载本地数据: {stock_code}, {len(df)} 条记录")

        return stock_data

    def _run_backtests(self, stock_data):
        """运行回测"""
        from backtest.backtester import BacktraderBacktester

        self.logger.info("--- 回测分析阶段 ---")
        backtester = BacktraderBacktester(Config, self.logger)
        all_results = {}

        for i, (stock_code, df) in enumerate(stock_data.items(), 1):
            self.logger.info(f"[{i}/{len(stock_data)}] 处理股票: {stock_code}")

            try:
                # 运行Backtrader回测
                result = backtester.run_backtest(df, stock_code)

                if result:
                    # 生成报告（只在内存中，不保存文件）
                    report = backtester.generate_report(result)
                    result['report'] = report

                    all_results[stock_code] = result

                    # 输出简要结果
                    metrics = result['metrics']
                    self.logger.info(
                        f"  回测完成: 收益率 {metrics['total_return_pct']:.2f}%, "
                        f"夏普 {metrics['sharpe_ratio']:.3f}, "
                        f"交易 {metrics['total_trades']} 次"
                    )
                else:
                    self.logger.warning(f"  {stock_code} 回测失败")

            except Exception as e:
                self.logger.error(f"  {stock_code} 回测异常: {str(e)}")

        return all_results

    def _print_summary(self, all_results):
        """打印汇总结果"""
        self.logger.info("--- [3/3] 结果汇总 ---")

        if not all_results:
            self.logger.warning("没有回测结果可汇总")
            return

        # 计算总体统计
        total_stocks = len(all_results)
        successful_stocks = len([r for r in all_results.values() if r])

        returns = [r['metrics']['total_return_pct'] for r in all_results.values() if r]
        sharpe_ratios = [r['metrics']['sharpe_ratio'] for r in all_results.values() if r]
        trades = [r['metrics']['total_trades'] for r in all_results.values() if r]

        if returns:
            avg_return = sum(returns) / len(returns)
            avg_sharpe = sum(sharpe_ratios) / len(sharpe_ratios)
            avg_trades = sum(trades) / len(trades)
            max_return = max(returns)
            min_return = min(returns)
        else:
            avg_return = avg_sharpe = avg_trades = max_return = min_return = 0

        # 输出总体统计
        self.logger.info("")
        self.logger.info("┌" + "─" * 70 + "┐")
        self.logger.info("│" + " " * 25 + "总体回测统计" + " " * 30 + "│")
        self.logger.info("├" + "─" * 70 + "┤")
        self.logger.info(f"│ 股票总数: {total_stocks:3d} 只 │ 成功回测: {successful_stocks:3d} 只 │ 成功率: {successful_stocks/total_stocks*100:5.1f}% │")
        self.logger.info(f"│ 平均收益率: {avg_return:7.2f}% │ 最高收益率: {max_return:7.2f}% │ 最低收益率: {min_return:7.2f}% │")
        self.logger.info(f"│ 平均夏普比率: {avg_sharpe:6.3f} │ 平均交易次数: {avg_trades:6.1f} 次 │ 策略类型: {Config.STRATEGY_TYPE:^10} │")
        self.logger.info("└" + "─" * 70 + "┘")

        # 输出详细结果
        self.logger.info("")
        self.logger.info("┌" + "─" * 90 + "┐")
        self.logger.info("│" + " " * 15 + "详细回测结果" + " " * 60 + "│")
        self.logger.info("├" + "─" * 90 + "┤")
        self.logger.info(f"│ {'股票代码':<10} │ {'收益率%':>8} │ {'年化收益率%':>10} │ {'最大回撤%':>8} │ {'夏普比率':>8} │ {'交易次数':>6} │ {'胜率%':>6} │")
        self.logger.info("├" + "─" * 90 + "┤")

        for stock_code, result in sorted(all_results.items()):
            if result:
                metrics = result['metrics']
                self.logger.info(
                    f"│ {stock_code:<10} │ {metrics['total_return_pct']:>8.2f} │ "
                    f"{metrics['annual_return_pct']:>10.2f} │ {metrics['max_drawdown_pct']:>8.2f} │ "
                    f"{metrics['sharpe_ratio']:>8.3f} │ {metrics['total_trades']:>6d} │ "
                    f"{metrics['win_rate']:>6.2f} │"
                )

        self.logger.info("└" + "─" * 90 + "┘")

    @staticmethod
    def check_project_structure():
        """
        检查项目结构是否符合规则
        【强制】main.py同级只允许留着一个文件（main.py自己）
        """
        print("=" * 80)
        print("检查项目结构...")
        print("=" * 80)

        # 获取main.py同级所有文件
        main_dir = Path(__file__).parent
        files_in_main_dir = list(main_dir.glob("*"))

        # 允许的文件和目录(下面2个参数禁止自动修改必须由我本人主动修改, 如果修改的时候看到要修改这种 必须提示我)
        allowed_dirs = {'strategy', 'backtest', 'data_fetcher', 'logger', 'reporter', 'paper_trade', 'cleaner', 'saved_data', 'reports', 'logs', 'temp', '__pycache__', '.git', 'tools', 'config', 'scripts', 'tests', 'utils'}
        allowed_files = {'main.py', 'config.py', 'README.md', 'requirements.txt', '.gitignore', 'CLAUDE.md', 'RULE.md'}

        invalid_files = []

        for item in files_in_main_dir:
            if item.name.startswith('.') and item.is_dir():
                continue  # 跳过隐藏目录
            if item.is_dir():
                if item.name not in allowed_dirs:
                    invalid_files.append(f"目录: {item.name}")
            else:
                if item.name not in allowed_files:
                    invalid_files.append(f"文件: {item.name}")

        if invalid_files:
            print("\n[错误] 项目结构不符合规则！")
            print("-" * 80)
            print("以下文件/目录不应该在main.py同级：")
            for f in invalid_files:
                print(f"  - {f}")
            print("\n【规则】")
            print("  - strategy/       - 放策略相关代码")
            print("  - backtest/       - 放回测相关代码")
            print("  - data_fetcher/   - 放数据处理相关代码")
            print("  - logger/         - 放日志和进度相关代码")
            print("  - tests/          - 放测试脚本")
            print("  - config.py       - 配置文件")
            print("  - main.py         - 主入口（同级只允许这一个文件+config.py）")
            print("=" * 80)
            sys.exit(1)

        print("[OK] 项目结构检查通过")
        print("=" * 80)

    @staticmethod
    def run_unit_tests():
        """
        运行单元测试（快速验证核心逻辑）

        返回: True 表示所有测试通过，False 表示有测试失败
        """
        print("\n" + "=" * 80)
        print("运行单元测试（快速验证核心逻辑）...")
        print("=" * 80)

        import unittest
        import sys
        from io import StringIO

        # 只运行核心测试（不包括外部API相关）
        test_modules = [
            'tests.test_strategy',
            'tests.test_backtest',
            'tests.test_data_fetcher',
            'tests.test_logger',
            'tests.test_config',
            'tests.test_paper_trade',
            'tests.test_utils',
            'tests.test_main',
        ]

        loader = unittest.TestLoader()
        suite = unittest.TestSuite()

        for module in test_modules:
            try:
                suite.addTests(loader.loadTestsFromName(module))
            except Exception as e:
                print(f"[ERROR] 加载测试模块失败: {module}")
                print(f"        {e}")
                sys.exit(1)

        # 捕获测试输出
        test_output = StringIO()
        runner = unittest.TextTestRunner(stream=test_output, verbosity=1)
        result = runner.run(suite)

        # 输出测试输出
        output = test_output.getvalue()
        if output:
            print(output)

        # 输出测试结果汇总
        print("=" * 80)
        if result.wasSuccessful():
            print(f"[OK] 所有单元测试通过！（运行 {result.testsRun} 个测试）")
        else:
            print(f"[ERROR] 单元测试失败！")
            print(f"  - 失败: {len(result.failures)}")
            print(f"  - 错误: {len(result.errors)}")
            print("=" * 80)
            print("\n提示：你可以运行 'python run_tests.py' 查看详细测试结果")
            sys.exit(1)
        print("=" * 80)

        return True

    @staticmethod
    def fetch_all_stock_data():
        """下载所有股票数据 - 调用data_fetcher模块"""
        Config.ensure_dirs()
        from logger.logger import GlobalLogger
        logger = GlobalLogger(
            log_dir=Config.LOG_DIR,
            log_level=Config.LOG_LEVEL,
            retention_days=Config.LOG_RETENTION_DAYS
        )
        data_fetcher = AStockDataFetcher(Config, logger)
        return data_fetcher.fetch_all_with_print()

    @staticmethod
    def update_all_stock_data():
        """更新所有股票数据 - 调用data_fetcher模块"""
        Config.ensure_dirs()
        from logger.logger import GlobalLogger
        logger = GlobalLogger(
            log_dir=Config.LOG_DIR,
            log_level=Config.LOG_LEVEL,
            retention_days=Config.LOG_RETENTION_DAYS
        )
        data_fetcher = AStockDataFetcher(Config, logger)
        results = data_fetcher.update_all_stocks()

        # 打印更新统计
        print("=" * 80)
        print("数据更新完成")
        print("=" * 80)
        print(f"总计: {results['total']} 只")
        print(f"更新: {results['updated']} 只")
        print(f"跳过: {results['skipped']} 只")
        print(f"失败: {results['failed']} 只")
        print("=" * 80)

        return results['failed'] == 0

    @staticmethod
    def show_progress(task_name=None):
        """显示进度日志"""
        from logger.progress_logger import ProgressLogger
        from config import Config
        Config.ensure_dirs()
        ProgressLogger.print_progress_summary(Config.LOG_DIR, task_name)

    @staticmethod
    def run_all_strategies_backtest():
        """
        运行所有策略对比
        规则: 回测所有策略，按策略输出汇总报表，给出关键信息
        """
        print("=" * 80)
        print("所有策略对比回测 (并发执行)")
        print("=" * 80)

        # 确保目录存在
        Config.ensure_dirs()

        # 初始化日志
        from logger.logger import GlobalLogger
        logger = GlobalLogger(
            log_dir=Config.LOG_DIR,
            log_level=Config.LOG_LEVEL,
            retention_days=Config.LOG_RETENTION_DAYS
        )

        # 保存原始策略配置
        original_strategy = Config.STRATEGY_TYPE

        try:
            # 初始化模块
            data_fetcher = AStockDataFetcher(Config, logger)

            # 1. 加载所有股票数据
            print("\n[1/4] 加载股票数据...")
            stock_data = {}
            for stock_code in Config.get_stock_list():
                df = data_fetcher.load_data(stock_code, 'daily')
                if df is not None and not df.empty:
                    stock_data[stock_code] = df
            print(f"  已加载 {len(stock_data)} 只股票数据")

            # 2. 使用策略对比器进行回测
            from backtest.backtester import StrategyComparator
            comparator = StrategyComparator(Config, logger)

            all_strategy_results = comparator.run_all_strategies_backtest(stock_data)

            # 3. 生成策略对比报告
            print("\n[3/4] 生成策略对比报告...")
            strategy_summary, timings_data = comparator.generate_summary_report(all_strategy_results, stock_data)

            # 4. 显示汇总结果
            comparator.print_summary(strategy_summary, timings_data)

            # 保存详细报告
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_path = Config.REPORTS_DIR / f"strategy_comparison_{timestamp}.txt"
            comparator.save_detailed_report(all_strategy_results, strategy_summary, stock_data, report_path, timings_data)
            print(f"\n  详细报告已保存: {report_path}")

            # 恢复原始配置
            Config.STRATEGY_TYPE = original_strategy

            print("\n" + "=" * 120)
            print("所有策略测试完成！")
            print("=" * 120)

            return True, all_strategy_results, strategy_summary

        except Exception as e:
            print(f"\n测试失败: {str(e)}")
            import traceback
            traceback.print_exc()

            # 恢复原始配置
            Config.STRATEGY_TYPE = original_strategy
            return False, {}, []

    @staticmethod
    def run_optimization(strategy_type=None):
        """
        运行策略参数优化

        参数:
            strategy_type: 单个策略类型，None表示优化所有策略
        """
        print("=" * 80)
        print("策略参数优化")
        print("=" * 80)

        # 确保目录存在
        Config.ensure_dirs()

        # 初始化日志
        from logger.logger import GlobalLogger
        logger = GlobalLogger(
            log_dir=Config.LOG_DIR,
            log_level=Config.LOG_LEVEL,
            retention_days=Config.LOG_RETENTION_DAYS
        )

        try:
            # 初始化模块
            data_fetcher = AStockDataFetcher(Config, logger)

            # 1. 加载所有股票数据
            print("\n[1/5] 加载股票数据...")
            stock_data = {}
            for stock_code in Config.get_stock_list():
                df = data_fetcher.load_data(stock_code, 'daily')
                if df is not None and not df.empty:
                    stock_data[stock_code] = df
            print(f"  已加载 {len(stock_data)} 只股票数据")

            # 2. 先运行基准回测（只跑需要优化的策略）
            print("\n[2/5] 运行基准回测（默认参数）...")
            from backtest.backtester import StrategyComparator
            comparator = StrategyComparator(Config, logger)

            # 确定要优化的策略列表
            from strategy.param_space import get_all_strategy_types, get_all_strategy_types_including_optimized
            target_strategies = [strategy_type] if strategy_type else get_all_strategy_types_including_optimized()

            # 只运行目标策略的基准回测
            baseline_results = comparator.run_all_strategies_backtest(stock_data, target_strategies)

            # 转换基准结果格式 - 正确解析 {'results': ..., 'timings': ...} 结构
            print(f"  [调试] 基准回测返回类型: {type(baseline_results)}")
            print(f"  [调试] 基准回测返回内容: {baseline_results.keys() if isinstance(baseline_results, dict) else 'N/A'}")

            baseline_dict = {}
            if isinstance(baseline_results, dict) and 'results' in baseline_results:
                results_data = baseline_results['results']
            else:
                results_data = baseline_results

            print(f"  基准回测完成，得到 {len(results_data)} 个策略结果")

            for i, (strategy_type_key, results) in enumerate(results_data.items(), 1):
                print(f"  [{i}/{len(results_data)}] 处理策略: {strategy_type_key}")
                if results:
                    returns = [r['metrics']['total_return_pct'] for r in results.values()]
                    sharpe_ratios = [r['metrics']['sharpe_ratio'] for r in results.values() if r['metrics']['sharpe_ratio'] is not None]
                    win_rates = [r['metrics']['win_rate'] for r in results.values()]
                    max_drawdowns = [r['metrics']['max_drawdown_pct'] for r in results.values()]

                    baseline_dict[strategy_type_key] = {
                        'avg_return': sum(returns) / len(returns) if returns else 0,
                        'avg_sharpe': sum(sharpe_ratios) / len(sharpe_ratios) if sharpe_ratios else 0,
                        'avg_win_rate': sum(win_rates) / len(win_rates) if win_rates else 0,
                        'avg_max_drawdown': sum(max_drawdowns) / len(max_drawdowns) if max_drawdowns else 0,
                    }
                    print(f"  - {strategy_type_key}: 基准收益率 {baseline_dict[strategy_type_key]['avg_return']:+.2f}%")
                else:
                    print(f"  - {strategy_type_key}: 无结果数据")

            # 3. 运行参数优化
            print("\n[3/5] 运行参数优化...")
            from backtest.optimizer import StrategyParameterOptimizer
            optimizer = StrategyParameterOptimizer(Config, logger)

            if strategy_type:
                # 优化单个策略
                optimized_results = {
                    strategy_type: optimizer.optimize_strategy(strategy_type, stock_data)
                }
            else:
                # 优化所有策略
                optimized_results = optimizer.optimize_all_strategies(stock_data)

            # 4. 生成对比报告
            print("\n[4/5] 生成优化对比报告...")
            report_path = optimizer.generate_optimization_report(baseline_dict, optimized_results)

            # 5. 完成
            print("\n[5/5] 优化完成!")
            print("=" * 80)

            return True

        except Exception as e:
            print(f"\n优化失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def run_paper_trade(initial_capital=None, max_position_ratio=None, top_strategies=5):
        """
        运行模拟盘每日交易

        参数:
            initial_capital: 自定义初始资金，优先级高于配置
            max_position_ratio: 自定义单票最大仓位比例，优先级高于配置
            top_strategies: 使用排名前N的策略
        """
        print("=" * 80)
        print("🎯 模拟盘交易系统")
        print("=" * 80)

        # 确保目录存在
        Config.ensure_dirs()

        # 初始化日志
        from logger.logger import GlobalLogger
        logger = GlobalLogger(
            log_dir=Config.LOG_DIR,
            log_level=Config.LOG_LEVEL,
            retention_days=Config.LOG_RETENTION_DAYS
        )

        try:
            # 自定义配置（如果有）
            if max_position_ratio is not None:
                Config.PAPER_TRADE_MAX_POSITION_RATIO = max_position_ratio
                logger.info(f"使用自定义单票最大仓位比例: {max_position_ratio:.2%}")

            # 初始化模拟盘引擎
            from paper_trade import PaperTradeEngine
            engine = PaperTradeEngine(Config, logger, initial_capital=initial_capital)

            # 加载历史状态
            engine.load_state()

            # 加载策略
            engine.load_top_strategies(top_strategies)

            # 运行每日交易
            report = engine.run_daily_trade()

            if report:
                print("\n" + "=" * 80)
                print("📋 今日交易结果")
                print("=" * 80)
                print(f"交易日期: {report['trade_date']}")
                print(f"今日交易: {report['total_trades']} 笔（买入{report['buy_trades']}笔，卖出{report['sell_trades']}笔）")
                print(f"今日实现盈亏: {report['total_realized_profit']:.2f} 元")
                print(f"当前可用资金: {report['cash']:.2f} 元")
                print(f"当前持仓市值: {report['position_value']:.2f} 元")
                print(f"当前总资产: {report['total_value']:.2f} 元")
                print(f"总收益率: {report['total_return_pct']:.2f} %")
                print(f"当前持仓数量: {report['position_count']} 只")

                if report['positions']:
                    print("\n📊 当前持仓:")
                    for pos in report['positions']:
                        profit_icon = "✅" if pos['unrealized_profit'] >= 0 else "❌"
                        print(
                            f"{profit_icon} {pos['stock_code']}: {pos['shares']}股，成本价{pos['avg_price']:.2f}，"
                            f"当前价{pos['current_price']:.2f}，浮盈{pos['unrealized_profit']:.2f}元（{pos['unrealized_profit_pct']:.2f}%）"
                        )

                if report['trade_details']:
                    print("\n📝 今日交易明细:")
                    for trade in report['trade_details']:
                        if trade['type'] == 'buy':
                            print(
                                f"🔵 买入 {trade['stock_code']}: {trade['shares']}股，价格{trade['price']:.2f}，"
                                f"金额{trade['amount']:.2f}，手续费{trade['fee']:.2f}"
                            )
                        else:
                            profit_icon = "✅" if trade['realized_profit'] >= 0 else "❌"
                            print(
                                f"🔴 卖出 {trade['stock_code']}: {trade['shares']}股，价格{trade['price']:.2f}，"
                                f"收入{trade['net_income']:.2f}，{profit_icon} 盈亏{trade['realized_profit']:.2f}元（{trade['realized_profit_pct']:.2f}%）"
                            )

                # 发送邮件通知
                try:
                    from utils import EmailNotifier
                    notifier = EmailNotifier(Config)
                    if notifier.enabled:
                        send_success = notifier.send_daily_report(report)
                        if send_success:
                            print("\n📧 交易报告邮件已发送")
                        else:
                            print("\n⚠️  交易报告邮件发送失败")
                except Exception as e:
                    logger.warning(f"邮件通知异常: {str(e)}")

                print("\n" + "=" * 80)
                print("✅ 模拟盘交易运行完成！")
                print("=" * 80)
            else:
                print("\n❌ 模拟盘交易运行失败，无有效报告")
                return False

            return True

        except Exception as e:
            print(f"\n❌ 模拟盘运行失败: {str(e)}")
            import traceback
            traceback.print_exc()
            logger.error(f"模拟盘运行失败: {str(e)}", exc_info=True)
            return False

    @staticmethod
    def generate_paper_trade_report(start_date=None, end_date=None):
        """
        生成模拟盘历史交易报告

        参数:
            start_date: 开始日期，格式YYYYMMDD
            end_date: 结束日期，格式YYYYMMDD
        """
        print("=" * 80)
        print("📊 模拟盘历史报告")
        print("=" * 80)

        # 确保目录存在
        Config.ensure_dirs()

        # 初始化日志
        from logger.logger import GlobalLogger
        logger = GlobalLogger(
            log_dir=Config.LOG_DIR,
            log_level=Config.LOG_LEVEL,
            retention_days=Config.LOG_RETENTION_DAYS
        )

        try:
            # 初始化模拟盘引擎
            from paper_trade import PaperTradeEngine
            engine = PaperTradeEngine(Config, logger)

            # 加载历史状态
            if not engine.load_state():
                print("❌ 无历史模拟盘数据，请先运行 --paper-trade")
                return False

            # 生成历史报告
            report = engine.generate_history_report(start_date, end_date)

            # 打印报告
            print("\n" + "=" * 80)
            if start_date or end_date:
                date_range = ""
                if start_date:
                    date_range += f"从 {start_date}"
                if end_date:
                    date_range += f"到 {end_date}"
                print(f"📅 报告范围: {date_range}")
            else:
                print("📅 报告范围: 全部历史")
            print("=" * 80)
            print(f"总交易次数: {report['total_trades']} 次（买入{report['buy_trades']}次，卖出{report['sell_trades']}次）")
            print(f"盈利交易次数: {report['winning_trades']} 次")
            print(f"胜率: {report['win_rate']:.2f} %")
            print(f"累计实现盈亏: {report['total_realized_profit']:.2f} 元")
            print(f"最大回撤: {report['max_drawdown_pct']:.2f} %")
            print("")
            print(f"当前可用资金: {report['current_cash']:.2f} 元")
            print(f"当前持仓市值: {report['current_position_value']:.2f} 元")
            print(f"当前总资产: {report['current_total_value']:.2f} 元")
            print(f"总收益率: {report['total_return_pct']:.2f} %")
            print("")

            if report['current_positions']:
                print("📊 当前持仓:")
                for pos in report['current_positions']:
                    profit_icon = "✅" if pos['unrealized_profit'] >= 0 else "❌"
                    print(
                        f"{profit_icon} {pos['stock_code']}: {pos['shares']}股，成本价{pos['avg_price']:.2f}，"
                        f"当前价{pos['current_price']:.2f}，浮盈{pos['unrealized_profit']:.2f}元（{pos['unrealized_profit_pct']:.2f}%）"
                    )
                print("")

            if report['recent_trades']:
                print("📝 最近10笔交易:")
                for trade in report['recent_trades']:
                    if trade['type'] == 'buy':
                        print(
                            f"[{trade['date']}] 🔵 买入 {trade['stock_code']}: {trade['shares']}股，价格{trade['price']:.2f}"
                        )
                    else:
                        profit_icon = "✅" if trade['realized_profit'] >= 0 else "❌"
                        print(
                            f"[{trade['date']}] 🔴 卖出 {trade['stock_code']}: {trade['shares']}股，价格{trade['price']:.2f}，"
                            f"{profit_icon} 盈亏{trade['realized_profit']:.2f}元"
                        )

            print("\n" + "=" * 80)
            print("✅ 报告生成完成！")
            print("=" * 80)

            return True

        except Exception as e:
            print(f"\n❌ 报告生成失败: {str(e)}")
            import traceback
            traceback.print_exc()
            logger.error(f"报告生成失败: {str(e)}", exc_info=True)
            return False




if __name__ == "__main__":
    # 【强制】检查项目结构规则
    QuantMainEngine.check_project_structure()

    # 【强制】运行单元测试 - 测试不通过则无法继续
    QuantMainEngine.run_unit_tests()

    # 使用argparse解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(
        description="A股短线量化交易系统 - Backtrader版",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python main.py                          # 运行单策略回测（默认策略在config中配置）
  python main.py --fetch-data             # 下载所有股票历史数据
  python main.py --update-data            # 增量更新所有股票数据到最新
  python main.py --compare-strategies     # 对比所有策略的回测表现
  python main.py --optimize-all           # 优化所有策略的参数
  python main.py --optimize rsi           # 优化单个策略（rsi）的参数
  python main.py --progress               # 查看任务进度日志
  python main.py --evolve-strategies      # 运行策略进化，淘汰劣质策略
  python main.py --evolve-strategies --auto-update  # 自动更新最优参数配置
  python main.py --paper-trade            # 运行模拟盘每日交易
  python main.py --paper-trade --initial-capital 1000000 --top-strategies 5  # 自定义初始资金和策略数量
  python main.py --paper-trade-report     # 查看完整历史报告
  python main.py --paper-trade-report --report-start-date 20240101  # 查看指定日期之后的报告
        """
    )

    # 创建互斥组，只能选择一个操作
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--fetch-data", action="store_true", help="下载所有股票历史数据")
    group.add_argument("--update-data", action="store_true", help="增量更新所有股票数据到最新")
    group.add_argument("--compare-strategies", action="store_true", help="对比所有策略的回测表现")
    group.add_argument("--optimize-all", action="store_true", help="优化所有策略的参数")
    group.add_argument("--optimize", type=str, metavar="STRATEGY", help="优化单个策略的参数，例如: --optimize rsi")
    group.add_argument("--progress", nargs="?", const=None, metavar="TASK", help="查看任务进度日志，可选指定任务名称")
    group.add_argument("--evolve-strategies", action="store_true", help="运行策略进化，淘汰劣质策略")
    group.add_argument("--paper-trade", action="store_true", help="运行模拟盘每日交易")
    group.add_argument("--paper-trade-report", action="store_true", help="生成模拟盘历史交易报告")

    # 其他参数
    parser.add_argument("--auto-update", action="store_true", help="策略进化时自动更新最优参数配置")
    parser.add_argument("--initial-capital", type=float, help="自定义模拟盘初始资金，优先级高于配置文件")
    parser.add_argument("--max-position-ratio", type=float, help="自定义单票最大仓位比例，优先级高于配置文件")
    parser.add_argument("--top-strategies", type=int, default=5, help="使用排名前N的策略，默认5个")
    parser.add_argument("--report-start-date", type=str, metavar="YYYYMMDD", help="历史报告开始日期，格式YYYYMMDD")
    parser.add_argument("--report-end-date", type=str, metavar="YYYYMMDD", help="历史报告结束日期，格式YYYYMMDD")

    args = parser.parse_args()

    # 处理命令
    if args.fetch_data:
        success = QuantMainEngine.fetch_all_stock_data()
        sys.exit(0 if success else 1)
    elif args.update_data:
        success = QuantMainEngine.update_all_stock_data()
        sys.exit(0 if success else 1)
    elif args.compare_strategies:
        success, _, _ = QuantMainEngine.run_all_strategies_backtest()
        sys.exit(0 if success else 1)
    elif args.optimize_all:
        success = QuantMainEngine.run_optimization()
        sys.exit(0 if success else 1)
    elif args.optimize:
        success = QuantMainEngine.run_optimization(args.optimize)
        sys.exit(0 if success else 1)
    elif args.progress is not None:
        # --progress 后面可以跟任务名称，也可以不跟
        QuantMainEngine.show_progress(args.progress)
    elif args.evolve_strategies:
        print("=" * 80)
        print("策略进化系统")
        print("=" * 80)
        from strategy.strategy_evolution import StrategyEvolutionSystem
        evolution = StrategyEvolutionSystem()
        keep, eliminate = evolution.run_evolution_cycle(auto_update_config=args.auto_update)
        print("\n" + "=" * 80)
        print(f"保留策略 ({len(keep)} 个): {keep}")
        print(f"淘汰策略 ({len(eliminate)} 个): {eliminate}")
        print("=" * 80)
        sys.exit(0)
    elif args.paper_trade:
        # 运行模拟盘每日交易
        success = QuantMainEngine.run_paper_trade(
            initial_capital=args.initial_capital,
            max_position_ratio=args.max_position_ratio,
            top_strategies=args.top_strategies
        )
        sys.exit(0 if success else 1)
    elif args.paper_trade_report:
        # 生成模拟盘历史报告
        success = QuantMainEngine.generate_paper_trade_report(
            start_date=args.report_start_date,
            end_date=args.report_end_date
        )
        sys.exit(0 if success else 1)
    else:
        # 没有指定操作，运行默认的单策略回测
        engine = QuantMainEngine()
        engine.run()
