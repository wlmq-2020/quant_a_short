# -*- coding: utf-8 -*-
"""
策略参数优化模块
提供网格搜索、参数优化、对比报告等功能
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import copy
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing


class StrategyParameterOptimizer:
    """策略参数优化器"""

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

        # 导入参数空间
        from strategy.param_space import PARAM_SPACES, generate_param_combinations
        self.param_spaces = PARAM_SPACES
        self.generate_param_combinations = generate_param_combinations

    def calculate_calmar_ratio(self, annual_return_pct, max_drawdown_pct):
        """
        计算卡尔马比率 (Calmar Ratio)

        参数:
            annual_return_pct: 年化收益率 (%)
            max_drawdown_pct: 最大回撤 (%)

        返回:
            float: 卡尔马比率
        """
        if max_drawdown_pct <= 0:
            return float('inf') if annual_return_pct > 0 else 0
        return annual_return_pct / max_drawdown_pct

    def calculate_composite_score(self, metrics, weights=None):
        """
        计算综合得分（超激进版本 - 以收益率为核心目标）

        参数:
            metrics: 指标字典
            weights: 权重字典，默认为收益率优先

        返回:
            float: 综合得分
        """
        if weights is None:
            weights = {
                'total_return_pct': 0.60,  # 收益率权重大幅提高
                'sharpe_ratio': 0.15,
                'win_rate': 0.10,
                'calmar_ratio': 0.15,
            }

        score = 0
        for key, weight in weights.items():
            if key in metrics and metrics[key] is not None:
                value = metrics[key]
                # 标准化处理
                if key == 'total_return_pct':
                    # 收益率：更高的归一化上限，鼓励更高收益
                    value = max(-100, min(200, value)) / 100  # 归一化到[-1, 2]
                elif key == 'sharpe_ratio':
                    value = max(-5, min(10, value)) / 5  # 归一化到[-1, 2]
                elif key == 'win_rate':
                    value = value / 100  # 归一化到[0, 1]
                elif key == 'calmar_ratio':
                    value = min(20, value) / 10  # 归一化到[0, 2]
                score += value * weight

        return score

    def _evaluate_param_set(self, strategy_type, param_set, stock_data, config):
        """
        评估一组参数（用于多进程）

        参数:
            strategy_type: 策略类型
            param_set: 参数组合
            stock_data: 股票数据字典
            config: 配置对象副本

        返回:
            dict: 参数评估结果
        """
        from backtest.backtester import BacktraderBacktester

        backtester = BacktraderBacktester(config, None)

        all_returns = []
        all_sharpe = []
        all_win_rates = []
        all_max_drawdowns = []
        all_trades = []

        for stock_code, df in stock_data.items():
            try:
                result = backtester.run_backtest_with_params(df, stock_code, strategy_type, param_set)
                if result:
                    metrics = result['metrics']
                    all_returns.append(metrics['total_return_pct'])
                    if metrics['sharpe_ratio'] is not None:
                        all_sharpe.append(metrics['sharpe_ratio'])
                    all_win_rates.append(metrics['win_rate'])
                    all_max_drawdowns.append(metrics['max_drawdown_pct'])
                    all_trades.append(metrics['total_trades'])
            except Exception:
                continue

        if not all_returns:
            return None

        # 计算平均指标
        avg_return = sum(all_returns) / len(all_returns) if all_returns else 0
        avg_sharpe = sum(all_sharpe) / len(all_sharpe) if all_sharpe else 0
        avg_win_rate = sum(all_win_rates) / len(all_win_rates) if all_win_rates else 0
        avg_max_drawdown = sum(all_max_drawdowns) / len(all_max_drawdowns) if all_max_drawdowns else 0
        avg_trades = sum(all_trades) / len(all_trades) if all_trades else 0

        # 计算卡尔马比率
        calmar_ratio = self.calculate_calmar_ratio(avg_return, avg_max_drawdown)

        # 计算综合得分
        composite_metrics = {
            'total_return_pct': avg_return,
            'sharpe_ratio': avg_sharpe,
            'win_rate': avg_win_rate,
            'calmar_ratio': calmar_ratio,
        }
        composite_score = self.calculate_composite_score(composite_metrics)

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

    def grid_search(self, strategy_type, stock_data, optimization_metric='composite_score', max_workers=None):
        """
        网格搜索优化

        参数:
            strategy_type: 策略类型
            stock_data: 股票数据字典
            optimization_metric: 优化目标指标
            max_workers: 最大并发进程数

        返回:
            dict: 最优参数和结果
        """
        print(f"\n开始网格搜索优化策略: {strategy_type}")

        param_space = self.param_spaces.get(strategy_type, {})
        if not param_space:
            print(f"  警告: 策略 {strategy_type} 没有定义参数空间")
            return None

        param_combinations = self.generate_param_combinations(param_space)
        print(f"  参数组合数量: {len(param_combinations)}")

        if max_workers is None:
            max_workers = min(multiprocessing.cpu_count(), 4)
        print(f"  使用 {max_workers} 个并发进程")

        all_results = []

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for param_set in param_combinations:
                config_copy = copy.deepcopy(self.config)
                future = executor.submit(
                    self._evaluate_param_set,
                    strategy_type, param_set, stock_data, config_copy
                )
                futures[future] = param_set

            completed = 0
            for future in as_completed(futures):
                completed += 1
                try:
                    result = future.result()
                    if result:
                        all_results.append(result)
                    if completed % 10 == 0:
                        print(f"  进度: {completed}/{len(param_combinations)}")
                except Exception as e:
                    print(f"  参数组合评估失败: {str(e)}")

        if not all_results:
            print(f"  警告: 没有有效的参数组合结果")
            return None

        # 按优化指标排序
        all_results.sort(key=lambda x: x[optimization_metric], reverse=True)
        best_result = all_results[0]

        print(f"  优化完成!")
        print(f"  最优参数: {best_result['params']}")
        print(f"  {optimization_metric}: {best_result[optimization_metric]:.4f}")
        print(f"  平均收益率: {best_result['avg_return']:+.2f}%")
        print(f"  平均夏普比率: {best_result['avg_sharpe']:.3f}")
        print(f"  平均胜率: {best_result['avg_win_rate']:.2f}%")
        print(f"  平均最大回撤: {best_result['avg_max_drawdown']:.2f}%")

        return {
            'best_params': best_result['params'],
            'best_result': best_result,
            'all_results': all_results,
        }

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

        # 网格搜索
        optimization_result = self.grid_search(
            strategy_type, stock_data, optimization_metric
        )

        if optimization_result:
            self.optimization_results[strategy_type] = optimization_result

        return optimization_result

    def optimize_all_strategies(self, stock_data, strategy_types=None, optimization_metric='composite_score'):
        """
        优化所有策略

        参数:
            stock_data: 股票数据字典
            strategy_types: 策略类型列表，None表示优化所有
            optimization_metric: 优化目标指标

        返回:
            dict: 所有策略的优化结果
        """
        from strategy.param_space import get_all_strategy_types

        if strategy_types is None:
            strategy_types = get_all_strategy_types()

        print("=" * 80)
        print(f"开始优化所有策略 ({len(strategy_types)} 个)")
        print("=" * 80)

        all_results = {}
        for i, strategy_type in enumerate(strategy_types, 1):
            print(f"\n[{i}/{len(strategy_types)}]")
            result = self.optimize_strategy(strategy_type, stock_data, optimization_metric)
            if result:
                all_results[strategy_type] = result

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
        return str(report_path)
