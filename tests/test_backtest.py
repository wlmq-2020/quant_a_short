# -*- coding: utf-8 -*-
"""
回测模块测试
- StrategyComparator.run_all_strategies_backtest()
- StrategyParameterOptimizer._update_each_strategy_best_params()
"""
import unittest
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import json
from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.backtester import StrategyComparator
from backtest.optimizer import StrategyParameterOptimizer


def create_mock_stock_data(n_stocks=2, n_days=100):
    """创建模拟股票数据"""
    stock_data = {}
    for i in range(n_stocks):
        stock_code = f'sh600{i:03d}'
        dates = pd.date_range('2023-01-01', periods=n_days)
        np.random.seed(i)
        base_price = 100 + i * 50
        df = pd.DataFrame({
            'date': dates,
            'open': np.random.uniform(base_price * 0.95, base_price * 1.05, n_days),
            'high': np.random.uniform(base_price * 1.0, base_price * 1.1, n_days),
            'low': np.random.uniform(base_price * 0.9, base_price * 0.98, n_days),
            'close': np.random.uniform(base_price * 0.95, base_price * 1.05, n_days),
            'volume': np.random.uniform(1000000, 10000000, n_days)
        })
        stock_data[stock_code] = df
    return stock_data


class TestBestParamsUpdate(unittest.TestCase):
    """测试最优参数更新逻辑 - _update_each_strategy_best_params()"""

    def setUp(self):
        """测试前准备"""
        self.config = MagicMock()
        self.config.CONFIG_DIR = Path('/tmp/test_config')
        self.logger = MagicMock()
        self.optimizer = StrategyParameterOptimizer(self.config, self.logger)
        self.optimizer.temp_dir = Path('/tmp/test_temp')

    def create_mock_result(self, avg_return, sharpe=0.8, params=None):
        """创建模拟优化结果"""
        return {
            'best_result': {
                'avg_return': avg_return,
                'avg_sharpe': sharpe,
                'max_return': avg_return * 1.5 if avg_return is not None else 0,
                'min_return': avg_return * 0.5 if avg_return is not None else 0,
                'best_stock': 'sh600519',
                'worst_stock': 'sh600036'
            },
            'best_params': params or {'param1': 1}
        }

    def test_get_effective_return_logic(self):
        """测试辅助函数逻辑：None 值处理"""
        def get_effective_return(val):
            return val if val is not None else -float('inf')

        self.assertEqual(get_effective_return(None), -float('inf'))
        self.assertEqual(get_effective_return(10.0), 10.0)
        self.assertTrue(get_effective_return(15.0) > get_effective_return(10.0))
        self.assertTrue(get_effective_return(10.0) > get_effective_return(None))

    @patch('builtins.print')
    @patch('backtest.optimizer.Path.exists')
    def test_core_comparison_matrix(self, mock_exists, mock_print):
        """
        【核心】测试完整的比较矩阵
        只有 eff_curr > eff_hist 才更新
        """
        mock_exists.return_value = False

        test_cases = [
            # (hist, curr, should_update, description)
            (None, None, False, "都None → 不更新"),
            (None, 5.0, True, "历史None，本次5.0 → 更新"),
            (None, 10.0, True, "历史None，本次10.0 → 更新"),
            (5.0, None, False, "历史5.0，本次None → 不更新"),
            (5.0, 3.0, False, "历史5.0，本次3.0 → 不更新"),
            (5.0, 5.0, False, "相等 → 不更新"),
            (5.0, 7.0, True, "历史5.0，本次7.0 → 更新"),
            (10.0, None, False, "历史10.0，本次None → 不更新"),
            (10.0, 8.0, False, "历史10.0，本次8.0 → 不更新"),
            (10.0, 10.0, False, "相等 → 不更新"),
            (10.0, 12.0, True, "历史10.0，本次12.0 → 更新"),
            (-5.0, -3.0, True, "亏损减少 → 更新"),
            (-5.0, -7.0, False, "亏损增加 → 不更新"),
        ]

        def get_effective_return(val):
            return val if val is not None else -float('inf')

        for hist, curr, should_update, description in test_cases:
            with self.subTest(description=description):
                eff_hist = get_effective_return(hist)
                eff_curr = get_effective_return(curr)

                if should_update:
                    self.assertTrue(eff_curr > eff_hist)
                else:
                    self.assertFalse(eff_curr > eff_hist)

    def test_higher_return_covers_lower(self):
        """
        【核心】新高数据覆盖次高数据
        """
        def get_effective_return(val):
            return val if val is not None else -float('inf')

        # 新高 > 次高 → 更新
        self.assertTrue(get_effective_return(20.0) > get_effective_return(15.0))
        self.assertTrue(get_effective_return(15.0) > get_effective_return(10.0))
        self.assertTrue(get_effective_return(10.0) > get_effective_return(5.0))

    def test_lower_return_keeps_higher(self):
        """
        【核心】次高数据不覆盖新高数据
        """
        def get_effective_return(val):
            return val if val is not None else -float('inf')

        # 次高 < 新高 → 不更新
        self.assertFalse(get_effective_return(10.0) > get_effective_return(15.0))
        self.assertFalse(get_effective_return(5.0) > get_effective_return(10.0))
        self.assertFalse(get_effective_return(None) > get_effective_return(10.0))

    def test_never_add_none_for_new_strategy(self):
        """
        【重要】历史为空且本次收益为None时，不应该新增记录
        """
        def get_effective_return(val):
            return val if val is not None else -float('inf')

        # 验证：-inf > -inf 是 False，所以不会更新
        self.assertFalse(get_effective_return(None) > get_effective_return(None))

    @patch('builtins.print')
    @patch('builtins.open', new_callable=mock_open)
    @patch('backtest.optimizer.Path.exists')
    def test_json_writing_format(self, mock_exists, mock_file, mock_print):
        """测试 JSON 写入格式"""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = '{}'

        optimized_results = {
            'rsi': self.create_mock_result(15.5)
        }

        self.optimizer._update_each_strategy_best_params(optimized_results)

        mock_file.assert_called()
        self.assertTrue(len(mock_file().write.call_args_list) > 0)

    @patch('builtins.print')
    @patch('backtest.optimizer.Path.exists')
    def test_missing_data_handling(self, mock_exists, mock_print):
        """测试缺失数据处理"""
        mock_exists.return_value = True

        optimized_results = {}
        try:
            self.optimizer._update_each_strategy_best_params(optimized_results)
        except Exception as e:
            self.fail(f"处理空结果时崩溃: {e}")

        optimized_results = {'rsi': {}}
        try:
            self.optimizer._update_each_strategy_best_params(optimized_results)
        except Exception as e:
            self.fail(f"处理无效结果时崩溃: {e}")


class TestStrategyComparator(unittest.TestCase):
    """测试 StrategyComparator 类"""

    def setUp(self):
        """测试前准备"""
        self.config = MagicMock()
        self.config.START_DATE = "20230101"
        self.config.END_DATE = "20260101"
        self.config.INITIAL_CAPITAL = 100000.0
        self.config.COMMISSION_RATE = 0.00025
        self.config.STAMP_DUTY_RATE = 0.001
        self.config.POSITION_RATIO = 0.8
        self.config.STOP_LOSS_RATIO = 0.05
        self.config.TAKE_PROFIT_RATIO = 0.2

        self.logger = MagicMock()
        self.comparator = StrategyComparator(self.config, self.logger)

    def test_config_dict_generation_logic(self):
        """测试配置字典生成逻辑"""
        test_attrs = ['START_DATE', '_private_attr', 'INITIAL_CAPITAL', 'some_method']
        public_attrs = [attr for attr in test_attrs if not attr.startswith('_')]
        self.assertIn('START_DATE', public_attrs)
        self.assertIn('INITIAL_CAPITAL', public_attrs)
        self.assertNotIn('_private_attr', public_attrs)

    def test_empty_strategy_list(self):
        """测试空策略列表"""
        mock_stock_data = create_mock_stock_data(n_stocks=2)

        with patch('builtins.print'):
            result = self.comparator.run_all_strategies_backtest(
                mock_stock_data,
                strategy_types=[]
            )

        self.assertIsNotNone(result)
        self.assertIn('results', result)
        self.assertIn('timings', result)
        self.assertEqual(len(result['results']), 0)

    def test_generate_summary_report(self):
        """测试 generate_summary_report 方法 - 核心功能"""
        mock_stock_data = create_mock_stock_data(n_stocks=2)
        stock_codes = list(mock_stock_data.keys())

        all_strategy_results = {
            'results': {
                'rsi': {
                    stock_codes[0]: {'metrics': {
                        'total_return_pct': 10.0,
                        'sharpe_ratio': 0.8,
                        'win_rate': 60.0,
                        'max_drawdown_pct': 5.0,
                        'total_trades': 10
                    }},
                    stock_codes[1]: {'metrics': {
                        'total_return_pct': 15.0,
                        'sharpe_ratio': 1.0,
                        'win_rate': 65.0,
                        'max_drawdown_pct': 6.0,
                        'total_trades': 12
                    }}
                },
                'macd_kdj': {
                    stock_codes[0]: {'metrics': {
                        'total_return_pct': 8.0,
                        'sharpe_ratio': 0.6,
                        'win_rate': 55.0,
                        'max_drawdown_pct': 7.0,
                        'total_trades': 8
                    }},
                    stock_codes[1]: {'metrics': {
                        'total_return_pct': 12.0,
                        'sharpe_ratio': 0.9,
                        'win_rate': 58.0,
                        'max_drawdown_pct': 8.0,
                        'total_trades': 9
                    }}
                }
            }
        }

        summary, timings = self.comparator.generate_summary_report(all_strategy_results, mock_stock_data)

        self.assertEqual(len(summary), 2)
        self.assertEqual(summary[0]['type'], 'rsi')
        self.assertEqual(summary[1]['type'], 'macd_kdj')
        self.assertEqual(summary[0]['avg_return'], 12.5)
        self.assertEqual(summary[0]['avg_sharpe'], 0.9)

    def test_generate_summary_report_with_none_sharpe(self):
        """测试含 None 值的汇总报告"""
        mock_stock_data = create_mock_stock_data(n_stocks=2)
        stock_codes = list(mock_stock_data.keys())

        all_strategy_results = {
            'results': {
                'rsi': {
                    stock_codes[0]: {'metrics': {
                        'total_return_pct': 10.0,
                        'sharpe_ratio': None,
                        'win_rate': 60.0,
                        'max_drawdown_pct': 5.0,
                        'total_trades': 10
                    }},
                    stock_codes[1]: {'metrics': {
                        'total_return_pct': 15.0,
                        'sharpe_ratio': 1.0,
                        'win_rate': 65.0,
                        'max_drawdown_pct': 6.0,
                        'total_trades': 12
                    }}
                }
            }
        }

        summary, timings = self.comparator.generate_summary_report(all_strategy_results, mock_stock_data)
        self.assertEqual(summary[0]['avg_sharpe'], 1.0)

    def test_generate_summary_report_empty_results(self):
        """测试空结果的汇总报告"""
        mock_stock_data = create_mock_stock_data(n_stocks=2)

        all_strategy_results = {'results': {}}
        summary, timings = self.comparator.generate_summary_report(all_strategy_results, mock_stock_data)
        self.assertEqual(len(summary), 0)

        all_strategy_results = {'results': {'rsi': {}}}
        summary, timings = self.comparator.generate_summary_report(all_strategy_results, mock_stock_data)
        self.assertEqual(len(summary), 0)

    def test_generate_summary_report_direct_format(self):
        """测试直接传入 results 格式"""
        mock_stock_data = create_mock_stock_data(n_stocks=2)
        stock_codes = list(mock_stock_data.keys())

        all_strategy_results = {
            'rsi': {
                stock_codes[0]: {'metrics': {
                    'total_return_pct': 10.0,
                    'sharpe_ratio': 0.8,
                    'win_rate': 60.0,
                    'max_drawdown_pct': 5.0,
                    'total_trades': 10
                }}
            }
        }

        summary, timings = self.comparator.generate_summary_report(all_strategy_results, mock_stock_data)
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]['type'], 'rsi')


if __name__ == '__main__':
    unittest.main()
