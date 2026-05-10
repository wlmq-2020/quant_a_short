# -*- coding: utf-8 -*-
"""
组合策略统一模块
提供组合管理、相关性分析、回测、优化、轮动等全套功能
"""
import sys
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from logger.logger import GlobalLogger


@dataclass
class StrategyConfig:
    """策略配置"""
    name: str
    params: dict
    weight: float = 0.0
    enabled: bool = True


class PortfolioStrategy:
    """组合策略管理类"""

    def __init__(
        self,
        strategy_configs: List[StrategyConfig],
        allocation_method: str = 'equal',
        max_single_weight: float = 0.4,
        min_single_weight: float = 0.05
    ):
        """
        初始化组合策略

        参数:
            strategy_configs: 策略配置列表
            allocation_method: 分配方式 ('equal', 'sharpe', 'risk_parity')
            max_single_weight: 单策略最大权重
            min_single_weight: 单策略最小权重
        """
        self.strategy_configs = strategy_configs
        self.allocation_method = allocation_method
        self.max_single_weight = max_single_weight
        self.min_single_weight = min_single_weight

        # 性能历史
        self.performance_history = {
            s.name: {'returns': [], 'sharpe': None, 'max_drawdown': None}
            for s in strategy_configs
        }

        # 计算初始权重
        self.weights = self._calculate_weights()

    def _calculate_weights(self) -> Dict[str, float]:
        """
        计算仓位权重

        返回:
            {strategy_name: weight}
        """
        if self.allocation_method == 'equal':
            return self._equal_weighted()
        elif self.allocation_method == 'sharpe':
            return self._sharpe_weighted()
        elif self.allocation_method == 'risk_parity':
            return self._risk_parity()
        else:
            return self._equal_weighted()

    def _equal_weighted(self) -> Dict[str, float]:
        """等权重分配"""
        enabled_strategies = [s for s in self.strategy_configs if s.enabled]
        weight = 1.0 / len(enabled_strategies) if enabled_strategies else 0

        weights = {}
        for s in self.strategy_configs:
            weights[s.name] = weight if s.enabled else 0.0

        return self._normalize_weights(weights)

    def _sharpe_weighted(self) -> Dict[str, float]:
        """夏普比率加权"""
        weights = {}
        total_sharpe = 0.0

        for s in self.strategy_configs:
            if not s.enabled:
                weights[s.name] = 0.0
                continue

            sharpe = self.performance_history[s.name]['sharpe']
            if sharpe is None or sharpe <= 0:
                weights[s.name] = 0.0
            else:
                weights[s.name] = sharpe
                total_sharpe += sharpe

        if total_sharpe > 0:
            for s in self.strategy_configs:
                if weights[s.name] > 0:
                    weights[s.name] /= total_sharpe

        return self._normalize_weights(weights)

    def _risk_parity(self) -> Dict[str, float]:
        """风险平价分配"""
        weights = {}
        total_inv_vol = 0.0

        for s in self.strategy_configs:
            if not s.enabled:
                weights[s.name] = 0.0
                continue

            returns = self.performance_history[s.name]['returns']
            if len(returns) < 20:
                # 数据不足，等权
                weights[s.name] = 1.0
            else:
                volatility = np.std(returns) * np.sqrt(252)
                if volatility <= 0:
                    weights[s.name] = 1.0
                else:
                    weights[s.name] = 1.0 / volatility

            total_inv_vol += weights[s.name]

        if total_inv_vol > 0:
            for s in self.strategy_configs:
                if weights[s.name] > 0:
                    weights[s.name] /= total_inv_vol

        return self._normalize_weights(weights)

    def _normalize_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        """
        归一化权重，限制单策略权重范围

        参数:
            weights: 原始权重

        返回:
            归一化后的权重
        """
        # 限制单策略权重范围
        for name in weights:
            if weights[name] > 0:
                weights[name] = max(self.min_single_weight,
                                    min(self.max_single_weight, weights[name]))

        # 重新归一化
        total = sum(weights.values())
        if total > 0:
            for name in weights:
                weights[name] /= total

        return weights

    def update_performance(self, strategy_name: str, returns: List[float],
                          sharpe: float = None, max_drawdown: float = None):
        """
        更新策略性能数据

        参数:
            strategy_name: 策略名称
            returns: 收益率序列
            sharpe: 夏普比率
            max_drawdown: 最大回撤
        """
        if strategy_name in self.performance_history:
            self.performance_history[strategy_name]['returns'] = returns
            self.performance_history[strategy_name]['sharpe'] = sharpe
            self.performance_history[strategy_name]['max_drawdown'] = max_drawdown

    def rebalance(self, force: bool = False):
        """
        再平衡仓位

        参数:
            force: 是否强制再平衡
        """
        self.weights = self._calculate_weights()
        return self.weights

    def get_weights(self) -> Dict[str, float]:
        """获取当前权重"""
        return self.weights

    def get_enabled_strategies(self) -> List[str]:
        """获取启用的策略列表"""
        return [s.name for s in self.strategy_configs if s.enabled]

    def disable_strategy(self, strategy_name: str):
        """禁用策略"""
        for s in self.strategy_configs:
            if s.name == strategy_name:
                s.enabled = False
                break
        self.weights = self._calculate_weights()

    def enable_strategy(self, strategy_name: str):
        """启用策略"""
        for s in self.strategy_configs:
            if s.name == strategy_name:
                s.enabled = True
                break
        self.weights = self._calculate_weights()


class StrategyCorrelationAnalyzer:
    """策略相关性分析器"""

    def __init__(self, strategy_list: List[str] = None):
        """
        初始化相关性分析器

        参数:
            strategy_list: 策略列表，默认使用所有已优化策略
        """
        if strategy_list is None:
            self.strategy_list = Config.get_all_optimized_strategies()
        else:
            self.strategy_list = strategy_list

        self.returns_data = {}
        self.correlation_matrix = None

    def analyze_strategy_returns(self, strategy_returns: Dict[str, pd.Series]) -> pd.DataFrame:
        """
        分析策略收益率相关性

        参数:
            strategy_returns: {策略名: 收益率序列}

        返回:
            相关性矩阵 DataFrame
        """
        self.returns_data = strategy_returns

        # 对齐时间索引
        returns_df = pd.DataFrame(strategy_returns)
        returns_df = returns_df.dropna()

        # 计算相关性矩阵
        self.correlation_matrix = returns_df.corr()

        return self.correlation_matrix

    def get_low_correlation_pairs(self, threshold: float = 0.3) -> List[Tuple[str, str, float]]:
        """
        获取低相关策略对

        参数:
            threshold: 相关性阈值，低于此值认为低相关

        返回:
            [(策略1, 策略2, 相关系数), ...]
        """
        if self.correlation_matrix is None:
            return []

        pairs = []
        n = len(self.correlation_matrix.columns)

        for i in range(n):
            for j in range(i+1, n):
                corr = self.correlation_matrix.iloc[i, j]
                if abs(corr) < threshold:
                    pairs.append((
                        self.correlation_matrix.index[i],
                        self.correlation_matrix.columns[j],
                        corr
                    ))

        # 按相关系数绝对值排序
        pairs.sort(key=lambda x: abs(x[2]))
        return pairs

    def recommend_portfolio(self, n_strategies: int = 4) -> List[str]:
        """
        推荐低相关组合

        参数:
            n_strategies: 组合策略数量

        返回:
            推荐的策略列表
        """
        if self.correlation_matrix is None:
            return self.strategy_list[:n_strategies]

        # 简单贪心算法：选择相关性最低的组合
        selected = []
        remaining = list(self.correlation_matrix.columns)

        # 先选表现最好的策略（这里简化处理）
        if remaining:
            selected.append(remaining[0])
            remaining.pop(0)

        # 逐步添加与已选策略相关性最低的
        while len(selected) < n_strategies and remaining:
            avg_corrs = []
            for s in remaining:
                # 计算与已选策略的平均相关系数
                corrs = [abs(self.correlation_matrix.loc[s, sel]) for sel in selected]
                avg_corr = np.mean(corrs)
                avg_corrs.append((s, avg_corr))

            # 选平均相关性最低的
            avg_corrs.sort(key=lambda x: x[1])
            best_strategy = avg_corrs[0][0]

            selected.append(best_strategy)
            remaining.remove(best_strategy)

        return selected


class PortfolioBacktester:
    """组合策略回测器"""

    def __init__(self, initial_capital: float = 100000.0):
        """
        初始化组合回测器

        参数:
            initial_capital: 初始资金
        """
        self.initial_capital = initial_capital

    def backtest_equal_weight(self, strategy_returns: Dict[str, pd.Series],
                               weights: Dict[str, float] = None) -> pd.Series:
        """
        等权重组合回测

        参数:
            strategy_returns: {策略名: 收益率序列}
            weights: 权重字典，None表示等权

        返回:
            组合净值序列
        """
        returns_df = pd.DataFrame(strategy_returns).dropna()

        if weights is None:
            # 等权重
            n = len(returns_df.columns)
            weights = {s: 1.0/n for s in returns_df.columns}

        # 计算组合收益率
        portfolio_returns = pd.Series(0.0, index=returns_df.index)

        for strategy, weight in weights.items():
            if strategy in returns_df.columns:
                portfolio_returns += returns_df[strategy] * weight

        # 计算净值
        portfolio_value = (1 + portfolio_returns).cumprod() * self.initial_capital

        return portfolio_value

    def calculate_metrics(self, portfolio_value: pd.Series) -> Dict:
        """
        计算组合表现指标

        参数:
            portfolio_value: 组合净值序列

        返回:
            指标字典
        """
        returns = portfolio_value.pct_change().dropna()

        total_return = (portfolio_value.iloc[-1] / portfolio_value.iloc[0] - 1) * 100
        annual_return = (1 + total_return/100) ** (252/len(returns)) - 1 if len(returns) > 0 else 0

        # 最大回撤
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min() * 100

        # 夏普比率（假设无风险利率3%）
        risk_free_rate = 0.03
        excess_returns = returns - risk_free_rate/252
        sharpe = np.sqrt(252) * excess_returns.mean() / excess_returns.std() if excess_returns.std() > 0 else 0

        # 卡尔马比率
        calmar = annual_return / abs(max_drawdown/100) if max_drawdown != 0 else 0

        return {
            'total_return_pct': total_return,
            'annual_return_pct': annual_return * 100,
            'max_drawdown_pct': max_drawdown,
            'sharpe_ratio': sharpe,
            'calmar_ratio': calmar,
            'final_value': portfolio_value.iloc[-1]
        }


class RealStrategyBacktester:
    """真实策略回测器 - 基于真实回测引擎"""

    def __init__(self):
        self.logger = GlobalLogger(
            log_dir=Config.LOG_DIR,
            log_level="INFO",
            retention_days=7
        )

    def run_all_strategies_real(self, stock_data: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        """
        运行所有17个策略的真实回测

        参数:
            stock_data: 股票数据字典 {stock_code: df}

        返回:
            {strategy_name: portfolio_value_series}
        """
        from backtest.backtester import StrategyComparator, BacktraderBacktester

        self.logger.info("="*80)
        self.logger.info("运行所有策略真实回测")
        self.logger.info("="*80)

        strategy_values = {}

        # 1. 运行所有策略回测
        comparator = StrategyComparator(Config, self.logger)
        all_results = comparator.run_all_strategies_backtest(stock_data)

        # 2. 计算每个策略的组合净值
        self.logger.info("\n计算各策略组合净值...")

        for strategy_name, stock_results in all_results.items():
            self.logger.info(f"  处理策略: {strategy_name}")

            # 计算该策略的组合净值
            portfolio_value = self._calculate_strategy_portfolio(stock_results)
            strategy_values[strategy_name] = portfolio_value

        self.logger.info("="*80)
        self.logger.info("✅ 所有策略真实回测完成！")
        self.logger.info("="*80)

        return strategy_values

    def _calculate_strategy_portfolio(self, stock_results: Dict) -> pd.Series:
        """
        计算单个策略的组合净值（等权配置所有股票）

        参数:
            stock_results: 单策略的各股票回测结果

        返回:
            组合净值时间序列
        """
        if not stock_results:
            return pd.Series()

        # 获取所有日期索引
        all_dates = set()
        for stock_code, result in stock_results.items():
            if result and 'value_series' in result:
                all_dates.update(result['value_series'].index)

        if not all_dates:
            self.logger.warning("  策略回测无有效日期数据，返回空序列")
            return pd.Series()

        all_dates = sorted(all_dates)

        # 等权计算组合净值
        n_stocks = len(stock_results)
        portfolio_values = []

        for date in all_dates:
            total_value = 0.0
            count = 0

            for stock_code, result in stock_results.items():
                if result and 'value_series' in result:
                    if date in result['value_series'].index:
                        total_value += result['value_series'].loc[date]
                        count += 1

            if count > 0:
                avg_value = total_value / count
                portfolio_values.append(avg_value)
            else:
                # 无数据时使用前值
                if portfolio_values:
                    portfolio_values.append(portfolio_values[-1])
                else:
                    portfolio_values.append(Config.INITIAL_CAPITAL)

        return pd.Series(portfolio_values, index=all_dates)


class PortfolioRotationTester:
    """策略轮动回测器"""

    def __init__(self):
        self.logger = GlobalLogger(
            log_dir=Config.LOG_DIR,
            log_level="INFO",
            retention_days=7
        )

    def run_monthly_rotation(self, strategy_values: Dict[str, pd.Series],
                             market_prices: pd.Series = None) -> pd.Series:
        """
        运行月度策略轮动回测

        参数:
            strategy_values: 各策略净值时间序列
            market_prices: 市场基准价格（用于市场状态识别）

        返回:
            轮动组合净值时间序列
        """
        from strategy.market_state import MarketStateDetector, StrategyRotator

        self.logger.info("="*80)
        self.logger.info("月度策略轮动回测")
        self.logger.info("="*80)

        # 对齐所有策略时间索引
        values_df = pd.DataFrame(strategy_values).dropna()

        if market_prices is None:
            # 如果没有市场价格，用第一个策略的净值作为代理
            market_prices = values_df.iloc[:, 0]

        detector = MarketStateDetector()
        rotator = StrategyRotator(detector)

        # 按月分组
        monthly_groups = values_df.groupby(pd.Grouper(freq='ME'))

        rotation_portfolio_values = []
        current_strategies = list(strategy_values.keys())[:4]  # 初始用前4个
        current_weights = {s: 1/len(current_strategies) for s in current_strategies}

        self.logger.info("\n--- 月度轮动 ---")

        for month_end, month_data in monthly_groups:
            # 用截至月底的数据判断市场状态
            state = detector.detect(market_prices.loc[:month_end])
            recommended = rotator.get_recommended_strategies(market_prices.loc[:month_end])

            # 判断是否需要轮动
            if rotator.should_rotate(current_strategies, market_prices.loc[:month_end]):
                self.logger.info(f"  {month_end.strftime('%Y-%m')}: 状态={state:12} -> 轮动到: {recommended[:4]}")
                current_strategies = recommended[:4]
                current_weights = {s: 1/len(current_strategies) for s in current_strategies}
            else:
                self.logger.info(f"  {month_end.strftime('%Y-%m')}: 状态={state:12} -> 保持")

            # 计算当月组合收益
            month_returns = month_data[current_strategies].pct_change().dropna()

            for date in month_returns.index:
                portfolio_return = 0.0
                for s in current_strategies:
                    if s in month_returns.columns:
                        portfolio_return += month_returns.loc[date, s] * current_weights[s]

                if rotation_portfolio_values:
                    new_value = rotation_portfolio_values[-1] * (1 + portfolio_return)
                else:
                    new_value = Config.INITIAL_CAPITAL * (1 + portfolio_return)

                rotation_portfolio_values.append(new_value)

        # 创建净值序列
        rotation_value_series = pd.Series(
            rotation_portfolio_values,
            index=values_df.index[-len(rotation_portfolio_values):]
        )

        # 计算指标
        total_return = (rotation_value_series.iloc[-1] / rotation_value_series.iloc[0] - 1) * 100

        self.logger.info(f"\n--- 轮动结果 ---")
        self.logger.info(f"  总收益率: {total_return:.2f}%")

        return rotation_value_series


# ========== 公共函数 ==========
def save_portfolio_results(strategy_values: Dict[str, pd.Series],
                          rotation_value: pd.Series = None):
    """保存组合回测结果"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # 保存策略净值
    values_df = pd.DataFrame(strategy_values)
    values_path = Config.REPORTS_DIR / f"phase2/real_strategy_values_{timestamp}.csv"
    values_df.to_csv(values_path)
    print(f"真实策略净值已保存: {values_path}")

    # 保存最新版本
    latest_values_path = Config.REPORTS_DIR / "phase2/real_strategy_values_latest.csv"
    values_df.to_csv(latest_values_path)

    # 保存轮动结果
    if rotation_value is not None:
        rotation_path = Config.REPORTS_DIR / f"phase2/rotation_portfolio_{timestamp}.csv"
        rotation_value.to_csv(rotation_path)
        print(f"轮动组合净值已保存: {rotation_path}")

        latest_rotation_path = Config.REPORTS_DIR / "phase2/rotation_portfolio_latest.csv"
        rotation_value.to_csv(latest_rotation_path)


def create_balanced_portfolio() -> PortfolioStrategy:
    """
    创建均衡组合

    策略: rsi, mean_reversion, bollinger, volume_spread (各25%)
    """
    strategy_configs = [
        StrategyConfig(
            name='rsi',
            params=Config.get_optimized_params('rsi')
        ),
        StrategyConfig(
            name='mean_reversion',
            params=Config.get_optimized_params('mean_reversion')
        ),
        StrategyConfig(
            name='bollinger',
            params=Config.get_optimized_params('bollinger')
        ),
        StrategyConfig(
            name='volume_spread',
            params=Config.get_optimized_params('volume_spread')
        )
    ]

    return PortfolioStrategy(
        strategy_configs=strategy_configs,
        allocation_method='equal'
    )


def create_aggressive_portfolio() -> PortfolioStrategy:
    """
    创建进取组合

    策略: ema_cross (30%), sar (20%), rsi (25%), momentum (25%)
    """
    strategy_configs = [
        StrategyConfig(
            name='ema_cross',
            params=Config.get_optimized_params('ema_cross'),
            weight=0.30
        ),
        StrategyConfig(
            name='sar',
            params=Config.get_optimized_params('sar'),
            weight=0.20
        ),
        StrategyConfig(
            name='rsi',
            params=Config.get_optimized_params('rsi'),
            weight=0.25
        ),
        StrategyConfig(
            name='momentum',
            params=Config.get_optimized_params('momentum'),
            weight=0.25
        )
    ]

    return PortfolioStrategy(
        strategy_configs=strategy_configs,
        allocation_method='equal'
    )


def create_conservative_portfolio() -> PortfolioStrategy:
    """
    创建保守组合

    策略: mean_reversion (30%), cci (25%), keltner (25%), turtle_trading (20%)
    """
    strategy_configs = [
        StrategyConfig(
            name='mean_reversion',
            params=Config.get_optimized_params('mean_reversion'),
            weight=0.30
        ),
        StrategyConfig(
            name='cci',
            params=Config.get_optimized_params('cci'),
            weight=0.25
        ),
        StrategyConfig(
            name='keltner',
            params=Config.get_optimized_params('keltner'),
            weight=0.25
        ),
        StrategyConfig(
            name='turtle_trading',
            params=Config.get_optimized_params('turtle_trading'),
            weight=0.20
        )
    ]

    return PortfolioStrategy(
        strategy_configs=strategy_configs,
        allocation_method='equal'
    )


def run_phase2_analysis():
    """
    运行 Phase 2 完整分析
    (需要真实回测数据时使用)
    """
    print("="*80)
    print("Phase 2: 组合策略分析")
    print("="*80)
    print("\n注意：此函数需要策略回测收益率数据作为输入")
    print("使用示例:")
    print("  1. 先获取各策略的净值/收益率数据")
    print("  2. 调用 StrategyCorrelationAnalyzer.analyze_strategy_returns()")
    print("  3. 调用 PortfolioBacktester.backtest_equal_weight()")
    print("\n" + "="*80)


if __name__ == '__main__':
    print("="*80)
    print("组合策略统一模块")
    print("="*80)
    print("\n主要类:")
    print("  - StrategyConfig: 策略配置")
    print("  - PortfolioStrategy: 组合策略管理")
    print("  - StrategyCorrelationAnalyzer: 策略相关性分析")
    print("  - PortfolioBacktester: 组合回测")
    print("  - RealStrategyBacktester: 真实策略回测")
    print("  - PortfolioRotationTester: 策略轮动回测")
    print("\n可用组合:")
    print("  1. create_balanced_portfolio()     - 均衡组合")
    print("  2. create_aggressive_portfolio()   - 进取组合")
    print("  3. create_conservative_portfolio() - 保守组合")
    print("\n" + "="*80)
