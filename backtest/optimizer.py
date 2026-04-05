# -*- coding: utf-8 -*-
"""
策略参数优化模块 - 三层并发架构
【并发架构】
- 策略级: ThreadPoolExecutor (8线程) - Windows下避免多进程死锁
- 参数组合级: ThreadPoolExecutor (16线程)
- 股票级: ThreadPoolExecutor (16线程) - 已在backtester.py中实现
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import copy
import json
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed
from logger.progress_logger import ProgressLogger


def _evaluate_strategy_with_params(config, strategy_type, stock_data_dict, param_set):
    """
    评估单个参数组合的内部函数

    参数:
        config: 配置对象
        strategy_type: 策略类型
        stock_data_dict: 股票数据字典
        param_set: 参数组合

    返回:
        dict: 评估结果
    """
    from backtest.backtester import BacktraderBacktester
    backtester = BacktraderBacktester(config, None)

    # 股票级: 16线程并发回测 (已在backtester.py中实现)
    results = backtester.run_backtest_batch(
        stock_data_dict, strategy_type, param_set, max_workers=16
    )

    if not results:
        return None

    # 计算指标
    all_returns = []
    all_sharpe = []
    all_win_rates = []
    all_max_drawdowns = []
    all_trades = []

    for result in results.values():
        if result:
            metrics = result['metrics']
            all_returns.append(metrics['total_return_pct'])
            if metrics['sharpe_ratio'] is not None:
                all_sharpe.append(metrics['sharpe_ratio'])
            all_win_rates.append(metrics['win_rate'])
            all_max_drawdowns.append(metrics['max_drawdown_pct'])
            all_trades.append(metrics['total_trades'])

    if not all_returns:
        return None

    avg_return = sum(all_returns) / len(all_returns)
    avg_sharpe = sum(all_sharpe) / len(all_sharpe) if all_sharpe else 0
    avg_win_rate = sum(all_win_rates) / len(all_win_rates)
    avg_max_drawdown = sum(all_max_drawdowns) / len(all_max_drawdowns)
    avg_trades = sum(all_trades) / len(all_trades)

    # 计算卡尔马比率
    calmar_ratio = float('inf') if avg_max_drawdown <= 0 else avg_return / avg_max_drawdown

    # 计算综合得分
    composite_score = (
        (max(-100, min(200, avg_return)) / 100) * 0.60 +
        (max(-5, min(10, avg_sharpe)) / 5) * 0.15 +
        (avg_win_rate / 100) * 0.10 +
        (min(20, calmar_ratio) / 10) * 0.15
    )

    return {
        'params': param_set,
        'avg_return': avg_return,
        'avg_sharpe': avg_sharpe,
        'avg_win_rate': avg_win_rate,
        'avg_max_drawdown': avg_max_drawdown,
        'avg_trades': avg_trades,
        'calmar_ratio': calmar_ratio,
        'composite_score': composite_score,
        'stock_count': len(all_returns),
    }


def _optimize_strategy_core(config, logger, strategy_type, stock_data_dict, param_space_dict):
    """
    优化单个策略的核心逻辑（可重用）

    参数:
        config: 配置对象
        logger: 日志对象
        strategy_type: 策略类型
        stock_data_dict: 股票数据字典
        param_space_dict: 该策略的参数字典空间

    返回:
        dict: 策略优化结果
    """
    from itertools import product

    print(f"\n[优化] 开始优化策略: {strategy_type}")

    # 生成参数组合
    def generate_param_combinations(param_space):
        if not param_space:
            return []
        keys = list(param_space.keys())
        values = list(param_space.values())
        combinations = []
        for combo in product(*values):
            param_dict = dict(zip(keys, combo))
            combinations.append(param_dict)
        return combinations

    param_combinations = generate_param_combinations(param_space_dict)
    print(f"  参数组合数量: {len(param_combinations)}")

    # 参数组合级: 16线程并发评估
    max_threads = min(multiprocessing.cpu_count() * 2, 16)
    print(f"  使用 {max_threads} 个线程评估参数组合")

    # 线程池评估所有参数组合
    all_results = []
    completed = 0

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = {executor.submit(_evaluate_strategy_with_params, config, strategy_type, stock_data_dict, param_set): param_set
                   for param_set in param_combinations}

        for future in as_completed(futures):
            completed += 1
            try:
                result = future.result()
                if result:
                    all_results.append(result)
                if completed % 10 == 0 or completed == len(param_combinations):
                    print(f"  进度: {completed}/{len(param_combinations)}")
            except Exception as e:
                print(f"  参数组合评估失败: {str(e)}")

    if not all_results:
        print(f"  警告: 策略 {strategy_type} 没有有效的参数组合结果")
        return None

    # 按综合得分排序
    all_results.sort(key=lambda x: x['composite_score'], reverse=True)
    best_result = all_results[0]

    print(f"  策略 {strategy_type} 优化完成!")
    print(f"  最优参数: {best_result['params']}")
    print(f"  综合得分: {best_result['composite_score']:.4f}")
    print(f"  平均收益率: {best_result['avg_return']:+.2f}%")
    print(f"  平均夏普比率: {best_result['avg_sharpe']:.3f}")
    print(f"  平均胜率: {best_result['avg_win_rate']:.2f}%")
    print(f"  平均最大回撤: {best_result['avg_max_drawdown']:.2f}%")

    return {
        'strategy_type': strategy_type,
        'best_params': best_result['params'],
        'best_result': best_result,
        'all_results': all_results,
    }


# 策略级进程入口函数（保留用于兼容，但不再推荐使用）
def optimize_strategy_process(strategy_type, stock_data_dict, config_dict, param_space_dict):
    """
    优化单个策略的进程入口（保留兼容，Windows下建议使用线程方式）

    参数:
        strategy_type: 策略类型
        stock_data_dict: 股票数据字典 {stock_code: df}
        config_dict: 配置字典
        param_space_dict: 该策略的参数字典空间

    返回:
        dict: 策略优化结果
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

    return _optimize_strategy_core(config, logger, strategy_type, stock_data_dict, param_space_dict)


class StrategyParameterOptimizer:
    """策略参数优化器 - 三层并发架构"""

    def __init__(self, config, logger):
        """
        初始化优化器

        参数:
            config: 配置对象
            logger: 日志对象
        """
        self.config = config
        self.logger = logger
        self.reports_dir = Path(config.REPORTS_DIR)
        self.temp_dir = Path(config.TEMP_DIR)

        # 确保目录存在
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # 优化结果缓存
        self.optimization_results = {}

        # 导入参数空间（包括优化策略）
        from strategy.param_space import get_all_param_spaces
        self.param_spaces = get_all_param_spaces()

    def optimize_strategy(self, strategy_type, stock_data, optimization_metric='composite_score'):
        """
        优化单个策略

        参数:
            strategy_type: 策略类型
            stock_data: 股票数据字典
            optimization_metric: 优化目标指标

        返回:
            dict: 优化结果
        """
        print(f"=" * 80)
        print(f"优化策略: {strategy_type}")
        print(f"=" * 80)

        param_space = self.param_spaces.get(strategy_type, {})
        if not param_space:
            print(f"  警告: 策略 {strategy_type} 没有定义参数空间")
            return None

        # 直接调用核心优化函数（避免多进程问题）
        result = _optimize_strategy_core(self.config, self.logger, strategy_type, stock_data, param_space)

        if result:
            self.optimization_results[strategy_type] = result
            # 更新最优参数、记录日志、更新config
            self._update_each_strategy_best_params({strategy_type: result})

        return result

    def optimize_all_strategies(self, stock_data, strategy_types=None, optimization_metric='composite_score'):
        """
        优化所有策略 - 策略级多线程并发（Windows下避免多进程死锁）

        参数:
            stock_data: 股票数据字典
            strategy_types: 策略类型列表，None表示优化所有
            optimization_metric: 优化目标指标

        返回:
            dict: 所有策略的优化结果
        """
        from strategy.param_space import get_all_strategy_types_including_optimized

        if strategy_types is None:
            # 默认只优化普通策略，不包含优化策略
            from strategy.param_space import get_all_strategy_types
            strategy_types = get_all_strategy_types()

        print("=" * 80)
        print(f"开始优化所有策略 ({len(strategy_types)} 个) - 8线程并发")
        print("=" * 80)

        # 策略级: 8线程并发
        max_threads = min(multiprocessing.cpu_count() * 2, 8)
        print(f"使用 {max_threads} 个线程并发优化策略")

        # 初始化进度日志
        progress_logger = ProgressLogger(self.config.LOG_DIR, "optimize_all")
        progress_logger.info(f"开始优化 {len(strategy_types)} 个策略", {"max_threads": max_threads})

        all_results = {}

        # 直接在线程中调用 optimize_strategy 方法
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = {}
            for strategy_type in strategy_types:
                param_space = self.param_spaces.get(strategy_type, {})
                if param_space:
                    future = executor.submit(
                        self.optimize_strategy,
                        strategy_type, stock_data, optimization_metric
                    )
                    futures[future] = strategy_type

            completed = 0
            for future in as_completed(futures):
                strategy_type = futures[future]
                completed += 1
                try:
                    result = future.result()
                    if result:
                        all_results[strategy_type] = result
                        self.optimization_results[strategy_type] = result
                        avg_return = result.get('best_result', {}).get('avg_return', 0)
                        progress_logger.update(
                            completed, len(strategy_types),
                            f"策略 {strategy_type} 完成",
                            {"strategy": strategy_type, "return": avg_return}
                        )
                    else:
                        progress_logger.update(
                            completed, len(strategy_types),
                            f"策略 {strategy_type} 无结果",
                            {"strategy": strategy_type}
                        )
                    print(f"\n[{completed}/{len(strategy_types)}] 策略 {strategy_type} 完成")
                except Exception as e:
                    progress_logger.error(
                        f"策略 {strategy_type} 失败",
                        {"strategy": strategy_type, "error": str(e)}
                    )
                    print(f"\n[{completed}/{len(strategy_types)}] 策略 {strategy_type} 失败: {str(e)}")
                    import traceback
                    traceback.print_exc()

        progress_logger.finish(True, f"优化完成，成功 {len(all_results)}/{len(strategy_types)} 个策略", {"total": len(strategy_types), "success": len(all_results)})
        print(f"\n进度日志已保存到: {progress_logger.get_log_file()}")

        return all_results

    def generate_optimization_report(self, baseline_results, optimized_results, report_path=None):
        """
        生成优化对比报告

        参数:
            baseline_results: 基准结果（默认参数）
            optimized_results: 优化结果
            report_path: 报告保存路径

        返回:
            str: 报告路径
        """
        if report_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_path = self.reports_dir / f"optimization_comparison_{timestamp}.txt"

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("=" * 150 + "\n")
            f.write("策略参数优化对比报告\n")
            f.write("=" * 150 + "\n\n")

            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # 策略排名对比
            f.write("=" * 150 + "\n")
            f.write("策略优化前后对比\n")
            f.write("=" * 150 + "\n")
            f.write(f"{'策略类型':<20} {'基准收益率':<15} {'优化收益率':<15} {'提升幅度':<15} {'基准夏普':<12} {'优化夏普':<12}\n")
            f.write("-" * 150 + "\n")

            for strategy_type in optimized_results.keys():
                baseline = baseline_results.get(strategy_type, {})
                optimized = optimized_results.get(strategy_type, {})

                baseline_return = baseline.get('avg_return', 0) if baseline else 0
                optimized_return = optimized.get('best_result', {}).get('avg_return', 0) if optimized else 0
                improvement = optimized_return - baseline_return if baseline else optimized_return

                baseline_sharpe = baseline.get('avg_sharpe', 0) if baseline else 0
                optimized_sharpe = optimized.get('best_result', {}).get('avg_sharpe', 0) if optimized else 0

                f.write(f"{strategy_type:<20} {baseline_return:>+12.2f}%  {optimized_return:>+12.2f}%  {improvement:>+12.2f}%  {baseline_sharpe:>10.3f}  {optimized_sharpe:>10.3f}\n")

            f.write("\n" + "=" * 150 + "\n")
            f.write("最优参数详情\n")
            f.write("=" * 150 + "\n")

            for strategy_type, result in optimized_results.items():
                if not result:
                    continue
                f.write(f"\n【策略: {strategy_type}】\n")
                f.write(f"  最优参数: {json.dumps(result['best_params'], ensure_ascii=False, indent=6)}\n")
                f.write(f"  平均收益率: {result['best_result']['avg_return']:+.2f}%\n")
                f.write(f"  平均夏普比率: {result['best_result']['avg_sharpe']:.3f}\n")
                f.write(f"  平均胜率: {result['best_result']['avg_win_rate']:.2f}%\n")
                f.write(f"  平均最大回撤: {result['best_result']['avg_max_drawdown']:.2f}%\n")
                f.write(f"  卡尔马比率: {result['best_result']['calmar_ratio']:.3f}\n")
                f.write(f"  综合得分: {result['best_result']['composite_score']:.4f}\n")

            f.write("\n" + "=" * 150 + "\n")
            f.write("报告结束\n")
            f.write("=" * 150 + "\n")

        print(f"\n优化对比报告已保存: {report_path}")

        # 每个策略更新自己的最优参数（滚动更新）
        self._update_each_strategy_best_params(optimized_results)

        return str(report_path)

    def _update_each_strategy_best_params(self, optimized_results):
        """
        每个策略独立跟踪和更新自己的最优参数（滚动更新）

        参数:
            optimized_results: 优化结果字典
        """
        best_params_file = self.config.CONFIG_DIR / "best_strategy_params.json"

        # 兼容旧路径：如果temp目录有旧文件，迁移到config目录
        old_params_file = self.temp_dir / "best_strategy_params.json"
        if old_params_file.exists() and not best_params_file.exists():
            try:
                import shutil
                shutil.move(str(old_params_file), str(best_params_file))
                print(f"\n  已迁移旧参数文件到: {best_params_file}")
            except Exception as e:
                print(f"  迁移旧参数文件失败: {e}")

        # 1. 加载历史最优参数
        historical_best = {}
        if best_params_file.exists():
            try:
                with open(best_params_file, 'r', encoding='utf-8') as f:
                    historical_best = json.load(f)
                print(f"\n  已加载历史最优参数记录: {len(historical_best)} 个策略")
            except Exception as e:
                print(f"  读取历史最优参数失败: {e}")

        # 2. 对比并更新每个策略的最优参数
        updated_count = 0
        print("\n  各策略优化结果对比:")
        print("  " + "-" * 80)
        print(f"  {'策略类型':<20} {'本次收益':<12} {'历史最优':<12} {'状态':<10}")
        print("  " + "-" * 80)

        for strategy_type, result in optimized_results.items():
            if not result or 'best_result' not in result:
                continue

            current_return = result['best_result'].get('avg_return', -float('inf'))
            current_params = result.get('best_params', {})
            current_sharpe = result['best_result'].get('avg_sharpe', 0)

            # 获取历史最优
            hist_data = historical_best.get(strategy_type, {})
            hist_return = hist_data.get('avg_return', -float('inf'))
            status = "---"

            # 如果本次收益更高，更新历史最优
            if current_return > hist_return:
                improvement = current_return - hist_return if hist_return != -float('inf') else current_return
                historical_best[strategy_type] = {
                    'avg_return': current_return,
                    'avg_sharpe': current_sharpe,
                    'best_params': current_params,
                    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                }
                status = "↑ 更新!"
                updated_count += 1

                # 记录日志
                if hist_return == -float('inf'):
                    self.logger.info(f"[策略优化] 新增策略 {strategy_type}: 收益率 {current_return:+.2f}%, 夏普 {current_sharpe:.3f}, 参数: {current_params}")
                else:
                    self.logger.info(f"[策略优化] 策略 {strategy_type} 提升: 历史 {hist_return:+.2f}% → 本次 {current_return:+.2f}% (提升 {improvement:+.2f}%), 夏普 {current_sharpe:.3f}, 新参数: {current_params}")

            elif strategy_type not in historical_best:
                historical_best[strategy_type] = {
                    'avg_return': current_return,
                    'avg_sharpe': current_sharpe,
                    'best_params': current_params,
                    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                }
                status = "✓ 新增"
                updated_count += 1

                # 记录日志
                self.logger.info(f"[策略优化] 新增策略 {strategy_type}: 收益率 {current_return:+.2f}%, 夏普 {current_sharpe:.3f}, 参数: {current_params}")
            else:
                status = "保持历史"

            print(f"  {strategy_type:<20} {current_return:>+10.2f}%  {hist_return:>+10.2f}%  {status}")

        print("  " + "-" * 80)

        # 3. 显示历史最优策略排名 (Top 5)
        if historical_best:
            print("\n  历史最优策略排名 (Top 5):")
            print("  " + "-" * 60)

            sorted_strategies = sorted(
                historical_best.items(),
                key=lambda x: x[1].get('avg_return', -float('inf')),
                reverse=True
            )

            for i, (strategy_type, data) in enumerate(sorted_strategies[:5], 1):
                ret = data.get('avg_return', 0)
                sharpe = data.get('avg_sharpe', 0)
                print(f"  {i}. {strategy_type:<20} 收益率: {ret:>+8.2f}%  夏普: {sharpe:+.3f}")

            print("  " + "-" * 60)

            if sorted_strategies:
                top_strategy, top_data = sorted_strategies[0]
                top_return = top_data.get('avg_return', 0)
                top_params = top_data.get('best_params', {})
                print(f"\n  全局最优策略: {top_strategy} (收益率: {top_return:+.2f}%)")
                print(f"  最优参数: {top_params}")

        # 4. 保存更新后的历史最优参数
        try:
            with open(best_params_file, 'w', encoding='utf-8') as f:
                json.dump(historical_best, f, ensure_ascii=False, indent=2)
            print(f"\n  历史最优参数已保存: {best_params_file}")
            print(f"  共记录 {len(historical_best)} 个策略的最优参数")
            if updated_count > 0:
                print(f"  本次更新了 {updated_count} 个策略")
        except Exception as e:
            print(f"  保存历史最优参数失败: {e}")
