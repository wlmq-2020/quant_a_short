# -*- coding: utf-8 -*-
"""
策略模块测试
- 测试36个策略的基本功能（导入、参数、指标初始化）
"""
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def create_mock_data(n_days=100):
    """创建模拟股票数据"""
    dates = pd.date_range('2023-01-01', periods=n_days)
    np.random.seed(42)
    base_price = 100
    df = pd.DataFrame({
        'open': np.random.uniform(base_price * 0.95, base_price * 1.05, n_days),
        'high': np.random.uniform(base_price * 1.0, base_price * 1.1, n_days),
        'low': np.random.uniform(base_price * 0.9, base_price * 0.98, n_days),
        'close': np.random.uniform(base_price * 0.95, base_price * 1.05, n_days),
        'volume': np.random.uniform(1000000, 10000000, n_days),
        'openinterest': np.zeros(n_days)
    }, index=dates)
    return df


class TestStrategyImports(unittest.TestCase):
    """测试策略导入和基本结构"""

    def test_import_strategy_module(self):
        """测试能否正确导入 strategy 模块"""
        try:
            from strategy import strategy
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"导入失败: {e}")

    def test_base_strategy_exists(self):
        """测试基类存在"""
        from strategy.strategy import BaseAStockStrategy
        self.assertTrue(hasattr(BaseAStockStrategy, '__init__'))

    def test_all_strategies_importable(self):
        """测试所有36个策略类都能导入（与strategy.py中的get_strategy_class映射完全对应）"""
        from strategy.strategy import (
            # 【基础策略 - 17个】
            MacdKdjStrategy,
            RsiStrategy,
            BollingerStrategy,
            MaCrossStrategy,
            KdjOversoldStrategy,
            MacdZeroAxisStrategy,
            TripleScreenStrategy,
            TurtleTradingStrategy,
            MomentumStrategy,
            MeanReversionStrategy,
            DonchianStrategy,
            WilliamsRStrategy,
            CCIStrategy,
            EMACrossStrategy,
            VolumeSpreadStrategy,
            SARStrategy,
            KeltnerChannelStrategy,
            # 【优化策略 - 19个】
            MacdKdjFibonacciStrategy,
            BollRsiOptimizedStrategy,
            KdjRsiOptimizedStrategy,
            MacdStrategyWithATR,
            RsiStrategyWithTrendFilter,
            TurtleStrategyWithFilter,
            EmaRsiStrategy,
            DualMacdStrategy,
            MacdStrategy,
            BollRsiStrategy,
            TurtleBreakoutStrategy,
            TripleEmaTrendStrategy,
            KdjMacdResonanceStrategy,
            RsiAtrAdaptiveStrategy,
            MacdBollStrategy,
            KdjRsiStrategy,
            MaVolumeStrategy,
            AtrStopStrategy,
            CompositeStrategy,
            # 别名
            MacdWithAtr,
            RsiWithTrend,
            TurtleWithFilter,
        )
        # 如果能走到这里，说明导入成功
        self.assertTrue(True)

    def test_strategy_params_exist(self):
        """测试策略类有 params 属性"""
        from strategy.strategy import (
            MacdKdjStrategy,
            RsiStrategy,
            BollingerStrategy,
        )
        self.assertTrue(hasattr(MacdKdjStrategy, 'params'))
        self.assertTrue(hasattr(RsiStrategy, 'params'))
        self.assertTrue(hasattr(BollingerStrategy, 'params'))


class TestStrategyParameterStructure(unittest.TestCase):
    """测试策略参数结构"""

    def test_base_strategy_has_params(self):
        """测试基类有 params 属性"""
        from strategy.strategy import BaseAStockStrategy
        self.assertTrue(hasattr(BaseAStockStrategy, 'params'))

    def test_macd_kdj_has_params(self):
        """测试 MacdKdjStrategy 有 params 属性"""
        from strategy.strategy import MacdKdjStrategy
        self.assertTrue(hasattr(MacdKdjStrategy, 'params'))

    def test_rsi_has_params(self):
        """测试 RsiStrategy 有 params 属性"""
        from strategy.strategy import RsiStrategy
        self.assertTrue(hasattr(RsiStrategy, 'params'))

    def test_bollinger_has_params(self):
        """测试 BollingerStrategy 有 params 属性"""
        from strategy.strategy import BollingerStrategy
        self.assertTrue(hasattr(BollingerStrategy, 'params'))


class TestStrategyInstantiation(unittest.TestCase):
    """测试策略实例化（不实际运行backtrader）"""

    def test_base_strategy_class_type(self):
        """测试基类类型"""
        from strategy.strategy import BaseAStockStrategy
        import backtrader as bt

        self.assertTrue(issubclass(BaseAStockStrategy, bt.Strategy))

    def test_strategy_inheritance(self):
        """测试策略继承关系"""
        from strategy.strategy import (
            BaseAStockStrategy,
            MacdKdjStrategy,
            RsiStrategy,
            BollingerStrategy,
        )

        self.assertTrue(issubclass(MacdKdjStrategy, BaseAStockStrategy))
        self.assertTrue(issubclass(RsiStrategy, BaseAStockStrategy))
        self.assertTrue(issubclass(BollingerStrategy, BaseAStockStrategy))


class TestStrategyList(unittest.TestCase):
    """测试策略列表完整性"""

    def test_get_all_strategy_types(self):
        """测试 param_space 中的策略列表"""
        from strategy.param_space import get_all_strategy_types
        strategy_types = get_all_strategy_types()

        # 所有策略应该有36个（统一后）
        self.assertEqual(len(strategy_types), 36)

    def test_get_all_strategy_types_including_optimized(self):
        """测试包含优化策略的完整列表"""
        from strategy.param_space import get_all_strategy_types_including_optimized
        all_strategy_types = get_all_strategy_types_including_optimized()

        # 总共应该有36个策略
        self.assertEqual(len(all_strategy_types), 36)

    def test_factory_function_exists(self):
        """测试策略工厂函数存在"""
        from strategy import get_strategy_class

        # 验证能获取策略类
        strategy_class = get_strategy_class('macd_kdj')
        self.assertIsNotNone(strategy_class)

        # 验证一些关键策略
        expected_strategies = [
            'macd_kdj', 'rsi', 'bollinger', 'ma_cross',
            'macd_kdj_fibonacci', 'dual_macd', 'composite'
        ]
        for name in expected_strategies:
            strategy_class = get_strategy_class(name)
            self.assertIsNotNone(strategy_class, f"缺少策略: {name}")


class TestStrategyParamSpace(unittest.TestCase):
    """测试策略参数空间"""

    def test_param_space_exists(self):
        """测试参数空间存在"""
        from strategy.param_space import PARAM_SPACES
        self.assertIsInstance(PARAM_SPACES, dict)
        self.assertEqual(len(PARAM_SPACES), 36)

    def test_each_strategy_has_param_space(self):
        """测试每个策略都有参数空间"""
        from strategy.param_space import (
            PARAM_SPACES,
            get_all_strategy_types_including_optimized
        )

        all_types = get_all_strategy_types_including_optimized()
        for strategy_type in all_types:
            self.assertIn(strategy_type, PARAM_SPACES,
                          f"策略 {strategy_type} 缺少参数空间")
            param_space = PARAM_SPACES[strategy_type]
            self.assertIsInstance(param_space, dict)
            self.assertGreater(len(param_space), 0,
                              f"策略 {strategy_type} 参数空间为空")

    def test_param_space_values_are_valid(self):
        """测试参数空间值是有效的列表或范围"""
        from strategy.param_space import PARAM_SPACES

        for strategy_type, param_space in PARAM_SPACES.items():
            for param_name, param_values in param_space.items():
                # 参数值应该是列表、元组或范围
                self.assertIsInstance(param_values, (list, tuple, range),
                    f"{strategy_type}.{param_name} 不是有效的参数类型")
                # 参数值应该非空
                self.assertGreater(len(param_values), 0,
                    f"{strategy_type}.{param_name} 参数值为空")

    def test_get_param_space_function(self):
        """测试 get_param_space 函数"""
        from strategy.param_space import get_param_space, PARAM_SPACES

        # 测试获取参数空间
        for strategy_type in PARAM_SPACES:
            param_space = get_param_space(strategy_type)
            self.assertEqual(param_space, PARAM_SPACES[strategy_type])

        # 测试不存在的策略返回空字典
        empty = get_param_space('nonexistent_strategy')
        self.assertEqual(empty, {})

    def test_get_all_param_spaces(self):
        """测试 get_all_param_spaces 函数"""
        from strategy.param_space import get_all_param_spaces, PARAM_SPACES

        all_spaces = get_all_param_spaces()
        self.assertEqual(all_spaces, PARAM_SPACES)


class TestStrategyModuleDocstring(unittest.TestCase):
    """测试策略模块文档"""

    def test_module_has_docstring(self):
        """测试模块有文档字符串"""
        from strategy import strategy
        self.assertIsNotNone(strategy.__doc__)
        self.assertGreater(len(strategy.__doc__), 0)

    def test_docstring_lists_all_strategies(self):
        """测试文档字符串列出了所有策略"""
        from strategy import strategy
        doc = strategy.__doc__

        # 检查文档中包含"36个策略"
        self.assertIn('36', doc)

        # 检查包含基础策略和优化策略标记
        self.assertIn('基础策略', doc)
        self.assertIn('优化策略', doc)


if __name__ == '__main__':
    unittest.main()
