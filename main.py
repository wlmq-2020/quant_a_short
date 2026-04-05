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
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from logger.logger import GlobalLogger
from data_fetcher.data_fetcher import AStockDataFetcher


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

    # 允许的文件和目录
    allowed_dirs = {'strategy', 'backtest', 'data_fetcher', 'logger', 'reporter', 'paper_trade', 'cleaner', 'saved_data', 'reports', 'logs', 'temp', '__pycache__', '.git', 'tools', 'config'}
    allowed_files = {'main.py', 'config.py', 'README.md', 'requirements.txt', '.gitignore'}

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
        print("  - config.py       - 配置文件")
        print("  - main.py         - 主入口（同级只允许这一个文件+config.py）")
        print("=" * 80)
        sys.exit(1)

    print("[OK] 项目结构检查通过")
    print("=" * 80)


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


def show_progress(task_name=None):
    """显示进度日志"""
    from logger.progress_logger import ProgressLogger
    from config import Config
    Config.ensure_dirs()
    ProgressLogger.print_progress_summary(Config.LOG_DIR, task_name)


if __name__ == "__main__":
    # 【强制】检查项目结构规则
    check_project_structure()

    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "--fetch-data":
            # 下载所有股票数据
            success = fetch_all_stock_data()
            sys.exit(0 if success else 1)
        elif sys.argv[1] == "--update-data":
            # 更新所有股票数据（增量更新）
            success = update_all_stock_data()
            sys.exit(0 if success else 1)
        elif sys.argv[1] == "--compare-strategies":
            # 循环测试所有策略并生成对比报告
            success, _, _ = run_all_strategies_backtest()
            sys.exit(0 if success else 1)
        elif sys.argv[1] == "--optimize-all":
            # 优化所有策略
            success = run_optimization()
            sys.exit(0 if success else 1)
        elif sys.argv[1] == "--optimize" and len(sys.argv) > 2:
            # 优化单个策略
            success = run_optimization(sys.argv[2])
            sys.exit(0 if success else 1)
        elif sys.argv[1] == "--progress":
            # 查看进度
            task_name = sys.argv[2] if len(sys.argv) > 2 else None
            show_progress(task_name)
        elif sys.argv[1] == "--evolve-strategies":
            # 策略进化：淘汰劣质策略，更新策略池
            print("=" * 80)
            print("策略进化系统")
            print("=" * 80)
            from strategy.strategy_evolution import StrategyEvolutionSystem
            evolution = StrategyEvolutionSystem()
            auto_update = len(sys.argv) > 2 and sys.argv[2] == "--auto-update"
            keep, eliminate = evolution.run_evolution_cycle(auto_update_config=auto_update)
            print("\n" + "=" * 80)
            print(f"保留策略 ({len(keep)} 个): {keep}")
            print(f"淘汰策略 ({len(eliminate)} 个): {eliminate}")
            print("=" * 80)
            sys.exit(0)

    # 运行完整系统（单策略回测）
    engine = QuantMainEngine()
    engine.run()
