# -*- coding: utf-8 -*-
"""
回测模块测试
- StrategyComparator.run_all_strategies_backtest()
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
