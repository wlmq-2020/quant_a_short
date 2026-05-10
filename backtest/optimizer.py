# -*- coding: utf-8 -*-
"""
策略参数优化模块 - 两层并发架构（修复嵌套死锁+性能优化）
【并发架构】
- 策略级: ThreadPoolExecutor (4线程) - Windows下避免多进程死锁
- 参数组合级: ThreadPoolExecutor (4线程)
- 股票级: 串行执行 - 移除嵌套线程池，避免死锁
【总并发控制】总并发数16，严格控制在CPU核心数*2以内，避免资源耗尽
【性能优化】
- 缓存股票日期过滤结果，避免重复计算
- 向量化计算指标，替代循环累加
- 缓存参数空间，避免重复导入
- 缓存历史最优参数，避免重复读文件

【强制规则】
每次执行优化时，必须先读取 config/best_strategy_params.json 历史最优记录
只记录和更新历史最高收益的参数，只有当次批跑收益 > 历史最高收益时才更新
永远保留历史最高收益的参数，不允许随便替换，否则所有批跑都是无意义的
所有日志必须使用公共组件logger模块，严禁使用print语句
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed
from logger.progress_logger import ProgressLogger
from utils.atomic_writer import AtomicWriter
from utils.file_rw_lock import FileRWLock

# 全局缓存
_param_spaces_cache = None
_filtered_stock_data_cache = {}
_best_params_cache = {}
_best_params_cache_mtime = {}


def split_data_by_time_window(df, window_size=756, step_size=180, train_ratio=0.8):
    """
    按时间划分滚动窗口（时间序列交叉验证窗口
    参数:
        df: 股票K线数据
        window_size: 每个窗口的总天数（默认252天=1年）
        step_size: 窗口滚动步长（默认60天=2个月）
        train_ratio: 训练集比例
    返回:
        list: [(df_train1, df_test1), (df_train2, df_test2), ...]
    """
    if df is None or df.empty:
        return []

    # 确保数据按日期排序
    df = df.sort_values('date').reset_index(drop=True)
    df['date'] = pd.to_datetime(df['date'])
    total_days = len(df)

    windows = []
    start_idx = 0

    while start_idx + window_size <= total_days:
        # 窗口结束索引
        window_end_idx = start_idx + window_size
        # 训练集结束索引
        train_end_idx = start_idx + int(window_size * train_ratio)

        df_train = df.iloc[start_idx:train_end_idx].copy()
        df_test = df.iloc[train_end_idx:window_end_idx].copy()

        windows.append((df_train, df_test))

        # 滚动到下一个窗口
        start_idx += step_size

    # 如果剩余数据不足一个完整窗口时，用最后一个窗口覆盖
    if start_idx < total_days and len(windows) == 0:
        train_end_idx = int(total_days * train_ratio)
        df_train = df.iloc[:train_end_idx].copy()
        df_test = df.iloc[train_end_idx:].copy()
        windows.append((df_train, df_test))

    return windows


def _evaluate_strategy_with_params(config, strategy_type, stock_data_dict, param_set, start_date=None, end_date=None):
    """
    评估单个参数组合的内部函数（性能优化版）
    - 缓存日期过滤结果，避免重复计算
    - 向量化计算指标，提升计算速度

    参数:
        config: 配置对象
        strategy_type: 策略类型
        stock_data_dict: 股票数据字典
        param_set: 参数组合
        start_date: 回测开始日期(YYYY-MM-DD)，可选
        end_date: 回测结束日期(YYYY-MM-DD)，可选

    返回:
        dict: 评估结果
    """
    from backtest.backtester import BacktraderBacktester
    backtester = BacktraderBacktester(config, None)

    # 按时间范围筛选数据（使用缓存，避免重复过滤）
    cache_key = f"{start_date or 'all'}_{end_date or 'all'}"
    if cache_key not in _filtered_stock_data_cache:
        filtered_stock_data = {}
        for stock_code, df in stock_data_dict.items():
            if df is None or df.empty:
                continue
            df['date'] = pd.to_datetime(df['date'])
            # 应用时间范围筛选
            if start_date:
                start_dt = pd.to_datetime(start_date)
                df = df[df['date'] >= start_dt]
            if end_date:
                end_dt = pd.to_datetime(end_date)
                df = df[df['date'] <= end_dt]
            if len(df) < 30:  # 数据不足30天跳过
                continue
            filtered_stock_data[stock_code] = df
        _filtered_stock_data_cache[cache_key] = filtered_stock_data
    else:
        filtered_stock_data = _filtered_stock_data_cache[cache_key]

    # 股票级: 串行执行（移除嵌套线程池，避免死锁）
    results = backtester.run_backtest_batch(
        filtered_stock_data, strategy_type, param_set, max_workers=1
    )

    if not results:
        return None

    # 计算指标（向量化计算，替代循环累加）
    metrics_list = [r['metrics'] for r in results.values() if r]

    all_returns = np.array([m['total_return_pct'] for m in metrics_list])
    all_sharpe = np.array([m['sharpe_ratio'] for m in metrics_list if m['sharpe_ratio'] is not None])
    all_win_rates = np.array([m['win_rate'] for m in metrics_list])
    all_max_drawdowns = np.array([m['max_drawdown_pct'] for m in metrics_list])
    all_trades = np.array([m['total_trades'] for m in metrics_list])

    if len(all_returns) == 0:
        return None

    avg_return = all_returns.mean()
    avg_sharpe = all_sharpe.mean() if len(all_sharpe) > 0 else 0
    avg_win_rate = all_win_rates.mean()
    avg_max_drawdown = all_max_drawdowns.mean()
    avg_trades = all_trades.mean()

    # 计算卡尔马比率
    calmar_ratio = float('inf') if avg_max_drawdown <= 0 else avg_return / avg_max_drawdown

    # 计算综合得分（新权重：更注重风险调整后收益）
    composite_score = (
        (max(-100, min(100, avg_return)) / 100) * 0.30 +  # 收益率权重从60%降为30%
        (max(-5, min(5, avg_sharpe)) / 5) * 0.20 +         # 夏普比率权重从15%升为20%
        (avg_win_rate / 100) * 0.15 +                      # 胜率权重从10%升为15%
        (min(10, calmar_ratio) / 10) * 0.20 +              # 卡玛比率权重从15%升为20%
        (1 - min(0.5, avg_max_drawdown / 0.5)) * 0.10 +    # 新增最大回撤惩罚10%（回撤越大得分越低）
        (1 - min(1, abs(avg_trades - 12) / 24)) * 0.05     # 新增交易合理性惩罚5%（最优年交易12次左右）
    )

    # ========== 新增正则化惩罚 ==========
    # 1. 参数极端值惩罚：如果参数取到搜索空间的边界值，每个边界参数扣0.05分，最多扣0.2分
    from strategy.param_space import get_all_param_spaces
    param_spaces = get_all_param_spaces()
    param_space = param_spaces.get(strategy_type, {})
    boundary_penalty = 0
    for param_name, param_values in param_space.items():
        if param_name in param_set and len(param_values) > 1:
            # 判断是否是边界值（最小值或最大值）
            min_val = min(param_values)
            max_val = max(param_values)
            if param_set[param_name] == min_val or param_set[param_name] == max_val:
                boundary_penalty += 0.05
    boundary_penalty = min(boundary_penalty, 0.2)  # 最多扣0.2分
    composite_score -= boundary_penalty

    # 2. 过度交易惩罚：平均年交易次数超过24次，每多6次扣0.05分，最多扣0.2分
    # 假设回测时间为1年，如果是其他时间按比例换算
    # 这里已经在基础得分里有交易合理性惩罚了，再加额外惩罚避免过度拟合
    excess_trades = max(0, avg_trades - 24)
    trade_penalty = min(excess_trades // 6 * 0.05, 0.2)
    composite_score -= trade_penalty

    # 确保得分不低于0
    composite_score = max(composite_score, 0)

    # 收集股票级别信息
    stock_returns = {}
    for stock_code, result in results.items():
        if result:
            stock_returns[stock_code] = result['metrics']['total_return_pct']

    # 计算最高/最低收益
    if stock_returns:
        max_return = max(stock_returns.values())
        min_return = min(stock_returns.values())
        best_stock = max(stock_returns.items(), key=lambda x: x[1])[0]
        worst_stock = min(stock_returns.items(), key=lambda x: x[1])[0]
    else:
        max_return = min_return = 0
        best_stock = worst_stock = ''

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
        'max_return': max_return,
        'min_return': min_return,
        'best_stock': best_stock,
        'worst_stock': worst_stock,
        'stock_returns': stock_returns,
    }


def _optimize_strategy_core(config, logger, strategy_type, stock_data_dict, param_space_dict):
    """
    优化单个策略的核心逻辑（可重用+性能优化版）
    - 缓存参数组合生成结果
    - 向量化计算窗口平均指标

    参数:
        config: 配置对象
        logger: 日志对象
        strategy_type: 策略类型
        stock_data_dict: 股票数据字典
        param_space_dict: 该策略的参数字典空间

    返回:
        dict: 策略优化结果
    """
    logger.info(f"[优化] 开始优化策略: {strategy_type}")

    # 从 param_space.py 导入统一的参数组合生成函数（缓存导入结果）
    global _param_spaces_cache
    if _param_spaces_cache is None:
        from strategy.param_space import generate_param_combinations, get_all_param_spaces
        _param_spaces_cache = {
            'generate_param_combinations': generate_param_combinations,
            'get_all_param_spaces': get_all_param_spaces
        }
    generate_param_combinations = _param_spaces_cache['generate_param_combinations']

    param_combinations = generate_param_combinations(param_space_dict)
    logger.info(f"  参数组合数量: {len(param_combinations)}")

    # 步骤1: 生成时间序列滚动窗口（取第一只股票的时间划分作为基准）
    windows = []
    for stock_code, df in stock_data_dict.items():
        if df is not None and not df.empty:
            windows = split_data_by_time_window(df)
            break
    if not windows:
        logger.error(f"  无法生成时间窗口，数据不足")
        return None
    logger.info(f"  生成{len(windows)}个滚动交叉验证窗口")

    # 参数组合级: 4线程并发评估，总并发数控制在CPU核心数*2以内
    max_threads = min(multiprocessing.cpu_count(), 4)
    logger.info(f"  使用 {max_threads} 个线程评估参数组合")

    # 步骤2: 对每个参数组合在所有窗口上评估
    all_param_results = []
    completed = 0
    total_tasks = len(param_combinations) * len(windows)

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = {}
        for param_set in param_combinations:
            for window_idx, (df_train, df_test) in enumerate(windows):
                # 评估训练集
                future_train = executor.submit(
                    _evaluate_strategy_with_params,
                    config, strategy_type, stock_data_dict, param_set,
                    start_date=df_train['date'].min().strftime('%Y-%m-%d'),
                    end_date=df_train['date'].max().strftime('%Y-%m-%d')
                )
                futures[future_train] = (param_set, window_idx, 'train')

                # 评估测试集
                future_test = executor.submit(
                    _evaluate_strategy_with_params,
                    config, strategy_type, stock_data_dict, param_set,
                    start_date=df_test['date'].min().strftime('%Y-%m-%d'),
                    end_date=df_test['date'].max().strftime('%Y-%m-%d')
                )
                futures[future_test] = (param_set, window_idx, 'test')

        # 收集结果（param_set是字典，需要转成可哈希的frozenset当key）
        param_window_results = {}  # {frozenset(params.items()): {'params': param_set, 'windows': {window_idx: {'train': result, 'test': result}}}}
        for future in as_completed(futures):
            param_set, window_idx, set_type = futures[future]
            completed += 1
            try:
                result = future.result()
                if result:
                    # 将参数组合转成可哈希的key
                    param_key = frozenset(param_set.items())
                    if param_key not in param_window_results:
                        param_window_results[param_key] = {
                            'params': param_set,
                            'windows': {}
                        }
                    if window_idx not in param_window_results[param_key]['windows']:
                        param_window_results[param_key]['windows'][window_idx] = {}
                    param_window_results[param_key]['windows'][window_idx][set_type] = result
                else:
                    logger.warning(f"  参数组合{param_set}在窗口{window_idx}的{set_type}集评估无有效结果，跳过")

                if completed % 10 == 0 or completed == total_tasks:
                    logger.info(f"  进度: {completed}/{total_tasks}")
            except Exception as e:
                logger.error(f"  参数组合评估失败: {str(e)}")

    if not param_window_results:
        logger.warning(f"  策略 {strategy_type} 没有有效的参数组合结果")
        return None

    # 步骤3: 综合所有窗口结果，筛选符合条件的参数
    valid_param_results = []
    for data in param_window_results.values():
        param_set = data['params']
        window_results = data['windows']
        # 确保参数在所有窗口都有训练和测试结果
        if len(window_results) != len(windows):
            continue
        if not all('train' in w and 'test' in w for w in window_results.values()):
            continue

        # 计算该参数在所有窗口的平均表现（向量化计算）
        train_returns = []
        test_returns = []
        composite_scores = []
        max_drawdowns = []
        sharpes = []
        win_rates = []
        trades_list = []

        for res in window_results.values():
            train_returns.append(res['train']['avg_return'])
            test_returns.append(res['test']['avg_return'])
            composite_scores.append(res['test']['composite_score'])
            max_drawdowns.append(res['test']['avg_max_drawdown'])
            sharpes.append(res['test']['avg_sharpe'])
            win_rates.append(res['test']['avg_win_rate'])
            trades_list.append(res['test']['avg_trades'])

        # 转换为numpy数组进行向量化计算
        train_returns_np = np.array(train_returns)
        test_returns_np = np.array(test_returns)
        composite_scores_np = np.array(composite_scores)
        max_drawdowns_np = np.array(max_drawdowns)
        sharpes_np = np.array(sharpes)
        win_rates_np = np.array(win_rates)
        trades_np = np.array(trades_list)

        avg_train_return = train_returns_np.mean()
        avg_test_return = test_returns_np.mean()
        avg_composite_score = composite_scores_np.mean()
        avg_max_drawdown = max_drawdowns_np.mean()
        avg_sharpe = sharpes_np.mean()
        avg_win_rate = win_rates_np.mean()
        avg_trades = trades_np.mean()
        return_std = test_returns_np.std() if len(test_returns_np) > 1 else 0

        # 过拟合校验：训练集收益超过测试集30%直接淘汰
        overfitting_degree = (avg_train_return - avg_test_return) / abs(avg_test_return) if avg_test_return != 0 else 1
        if overfitting_degree > 0.3:
            logger.debug(f"  参数过拟合被淘汰：训练收益{avg_train_return:.2f}%，测试收益{avg_test_return:.2f}%，过拟合度{overfitting_degree:.2%}")
            continue

        # 计算卡尔马比率
        calmar_ratio = float('inf') if avg_max_drawdown <= 0 else avg_test_return / avg_max_drawdown

        # 参数准入门槛校验
        if avg_composite_score < 0.3 or avg_max_drawdown > 30 or avg_sharpe < 0.5:
            logger.debug(f"  参数未通过准入门槛：得分{avg_composite_score:.2f}，回撤{avg_max_drawdown:.2f}%，夏普{avg_sharpe:.2f}")
            continue

        # 保存综合结果
        valid_param_results.append({
            'params': param_set,
            'avg_return': avg_test_return,
            'avg_train_return': avg_train_return,
            'avg_sharpe': avg_sharpe,
            'avg_win_rate': avg_win_rate,
            'avg_max_drawdown': avg_max_drawdown,
            'avg_trades': avg_trades,
            'calmar_ratio': calmar_ratio,
            'composite_score': avg_composite_score,
            'return_std': return_std,
            'window_results': window_results,
            'stock_count': min([w['test']['stock_count'] for w in window_results.values()]),
            'max_return': max([w['test']['max_return'] for w in window_results.values()]),
            'min_return': min([w['test']['min_return'] for w in window_results.values()]),
            'best_stock': '',  # 多窗口下不统计
            'worst_stock': '',
            'stock_returns': {}
        })

    if not valid_param_results:
        logger.warning(f"  策略 {strategy_type} 没有通过过拟合校验的参数组合")
        return None

    # 按综合得分排序
    valid_param_results.sort(key=lambda x: x['composite_score'], reverse=True)
    best_result = valid_param_results[0]

    logger.info(f"  策略 {strategy_type} 优化完成!")
    logger.info(f"  最优参数: {best_result['params']}")
    logger.info(f"  综合得分: {best_result['composite_score']:.4f}")
    logger.info(f"  平均收益率: {best_result['avg_return']:+.2f}%")
    logger.info(f"  平均夏普比率: {best_result['avg_sharpe']:.3f}")
    logger.info(f"  平均胜率: {best_result['avg_win_rate']:.2f}%")
    logger.info(f"  平均最大回撤: {best_result['avg_max_drawdown']:.2f}%")

    return {
        'strategy_type': strategy_type,
        'best_params': best_result['params'],
        'best_result': best_result,
        'all_results': valid_param_results,
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
    """策略参数优化器 - 两层并发架构（修复嵌套死锁+资源控制）"""

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
        from strategy.param_space import get_all_param_spaces
        self.param_spaces = get_all_param_spaces()

        # 跨进程读写锁，防止多进程/多线程并发读写best_strategy_params.json
        self._params_file = self.config.CONFIG_DIR / "best_strategy_params.json"
        self._file_lock = FileRWLock(self._params_file)

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
        # ========== 优化前强制读取并校验规范 ==========
        spec_file = self.config.CONFIG_DIR / "parameter_optimization_spec.md"
        SPEC_VERSION = "v1.0"  # 代码适配的规范版本

        self.logger.info(f"=" * 80)
        self.logger.info(f"优化策略: {strategy_type}")
        self.logger.info(f"=" * 80)

        # 读取规范文件并校验
        if spec_file.exists():
            try:
                with open(spec_file, 'r', encoding='utf-8') as f:
                    spec_content = f.read()
                # 校验版本
                if SPEC_VERSION in spec_content:
                    self.logger.info(f"✅ 已加载参数优化规范，版本: {SPEC_VERSION}，符合要求")
                    self.logger.info(f"📋 规范核心规则：时间序列交叉验证 + 多目标评估 + 稳健性检验")
                else:
                    self.logger.warning(f"⚠️  规范版本不匹配！预期版本: {SPEC_VERSION}，请更新规范文件")
            except Exception as e:
                self.logger.warning(f"⚠️  读取优化规范失败: {str(e)}")
        else:
            self.logger.error(f"❌ 缺失优化规范文件: {spec_file}，请确保规范文件存在后再执行优化")
            return None

        param_space = self.param_spaces.get(strategy_type, {})
        if not param_space:
            self.logger.warning(f"  策略 {strategy_type} 没有定义参数空间")
            return None

        # 直接调用核心优化函数（避免多进程问题）
        result = _optimize_strategy_core(self.config, self.logger, strategy_type, stock_data, param_space)

        if result:
            self.optimization_results[strategy_type] = result
            # 每优化完一个策略立即更新最优参数
            self._update_single_strategy_best_params(strategy_type, result, stock_data)

        return result

    def _update_single_strategy_best_params(self, strategy_type, result, stock_data=None):
        """
        更新单个策略的最优参数（立即更新）

        参数:
            strategy_type: 策略类型
            result: 优化结果
                self.logger.info(f"[策略优化] 策略 {strategy_type}: 本次收益未超越历史最优，不更新")

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
            # 默认优化所有策略
            strategy_types = get_all_strategy_types_including_optimized()

        self.logger.info("=" * 80)
        self.logger.info(f"开始优化所有策略 ({len(strategy_types)} 个) - 8线程并发")
        self.logger.info("=" * 80)

        # 策略级: 4线程并发，总并发数控制在CPU核心数*2以内
        max_threads = min(multiprocessing.cpu_count(), 4)
        self.logger.info(f"使用 {max_threads} 个线程并发优化策略")

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
                    self.logger.info(f"[{completed}/{len(strategy_types)}] 策略 {strategy_type} 完成")
                except Exception as e:
                    progress_logger.error(
                        f"策略 {strategy_type} 失败",
                        {"strategy": strategy_type, "error": str(e)}
                    )
                    self.logger.error(f"[{completed}/{len(strategy_types)}] 策略 {strategy_type} 失败: {str(e)}")
                    import traceback
                    traceback.print_exc()

        progress_logger.finish(True, f"优化完成，成功 {len(all_results)}/{len(strategy_types)} 个策略", {"total": len(strategy_types), "success": len(all_results)})
        self.logger.info(f"进度日志已保存到: {progress_logger.get_log_file()}")

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

        report_content = []
        report_content.append("=" * 150 + "\n")
        report_content.append("策略参数优化对比报告\n")
        report_content.append("=" * 150 + "\n\n")

        report_content.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # 策略排名对比
        report_content.append("=" * 150 + "\n")
        report_content.append("策略优化前后对比\n")
        report_content.append("=" * 150 + "\n")
        report_content.append(f"{'策略类型':<20} {'基准收益率':<15} {'优化收益率':<15} {'提升幅度':<15} {'基准夏普':<12} {'优化夏普':<12}\n")
        report_content.append("-" * 150 + "\n")

        for strategy_type in optimized_results.keys():
            baseline = baseline_results.get(strategy_type, {})
            optimized = optimized_results.get(strategy_type, {})

            baseline_return = baseline.get('avg_return', 0) if baseline else 0
            optimized_return = optimized.get('best_result', {}).get('avg_return', 0) if optimized else 0
            improvement = optimized_return - baseline_return if baseline else optimized_return

            baseline_sharpe = baseline.get('avg_sharpe', 0) if baseline else 0
            optimized_sharpe = optimized.get('best_result', {}).get('avg_sharpe', 0) if optimized else 0

            report_content.append(f"{strategy_type:<20} {baseline_return:>+12.2f}%  {optimized_return:>+12.2f}%  {improvement:>+12.2f}%  {baseline_sharpe:>10.3f}  {optimized_sharpe:>10.3f}\n")

        report_content.append("\n" + "=" * 150 + "\n")
        report_content.append("最优参数详情\n")
        report_content.append("=" * 150 + "\n")

        for strategy_type, result in optimized_results.items():
            if not result:
                continue
            report_content.append(f"\n【策略: {strategy_type}】\n")
            report_content.append(f"  最优参数: {json.dumps(result['best_params'], ensure_ascii=False, indent=6)}\n")
            report_content.append(f"  平均收益率: {result['best_result']['avg_return']:+.2f}%\n")
            report_content.append(f"  平均夏普比率: {result['best_result']['avg_sharpe']:.3f}\n")
            report_content.append(f"  平均胜率: {result['best_result']['avg_win_rate']:.2f}%\n")
            report_content.append(f"  平均最大回撤: {result['best_result']['avg_max_drawdown']:.2f}%\n")
            report_content.append(f"  卡尔马比率: {result['best_result']['calmar_ratio']:.3f}\n")
            report_content.append(f"  综合得分: {result['best_result']['composite_score']:.4f}\n")

        report_content.append("\n" + "=" * 150 + "\n")
        report_content.append("报告结束\n")
        report_content.append("=" * 150 + "\n")

        # 原子写入报告
        AtomicWriter.write_text(report_path, ''.join(report_content))

        self.logger.info(f"优化对比报告已保存: {report_path}")

        # 注意：最优参数已在每个策略优化完成时即时更新
        # 这里不再需要统一调用 _update_each_strategy_best_params()

        return str(report_path)
