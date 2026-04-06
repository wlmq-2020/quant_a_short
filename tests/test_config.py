# -*- coding: utf-8 -*-
"""
配置模块测试
- config.py 全局配置
"""
import unittest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import sys
import json
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestConfig(unittest.TestCase):
    """测试 Config 类"""

    def test_import_config_module(self):
        """测试能否正确导入 config 模块"""
        try:
            from config import Config
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"导入失败: {e}")

    def test_config_paths_exist(self):
        """测试配置路径存在"""
        from config import Config

        self.assertTrue(hasattr(Config, 'PROJECT_ROOT'))
        self.assertTrue(hasattr(Config, 'LOG_DIR'))
        self.assertTrue(hasattr(Config, 'SAVED_DATA_DIR'))
        self.assertTrue(hasattr(Config, 'REPORTS_DIR'))
        self.assertTrue(hasattr(Config, 'TEMP_DIR'))
        self.assertTrue(hasattr(Config, 'CONFIG_DIR'))

    def test_config_dates(self):
        """测试日期配置"""
        from config import Config

        self.assertTrue(hasattr(Config, 'START_DATE'))
        self.assertTrue(hasattr(Config, 'END_DATE'))
        self.assertTrue(callable(Config.get_start_date))
        self.assertTrue(callable(Config.get_end_date))

    def test_get_start_date_format(self):
        """测试 get_start_date 返回格式"""
        from config import Config

        start_date = Config.get_start_date()
        self.assertIsInstance(start_date, str)
        self.assertEqual(len(start_date), 8)  # YYYYMMDD 格式

    def test_get_end_date_format(self):
        """测试 get_end_date 返回格式"""
        from config import Config

        end_date = Config.get_end_date()
        self.assertIsInstance(end_date, str)
        self.assertEqual(len(end_date), 8)  # YYYYMMDD 格式

    def test_stock_list_exists(self):
        """测试股票列表配置"""
        from config import Config

        self.assertTrue(hasattr(Config, 'STOCK_CODES'))
        self.assertIsInstance(Config.STOCK_CODES, list)
        self.assertEqual(len(Config.STOCK_CODES), 50)  # 上证50

    def test_get_stock_list(self):
        """测试 get_stock_list 方法"""
        from config import Config

        stock_list = Config.get_stock_list()
        self.assertEqual(stock_list, Config.STOCK_CODES)
        self.assertEqual(len(stock_list), 50)

    def test_trading_configs(self):
        """测试交易配置"""
        from config import Config

        self.assertTrue(hasattr(Config, 'COMMISSION_RATE'))
        self.assertTrue(hasattr(Config, 'STAMP_DUTY_RATE'))
        self.assertTrue(hasattr(Config, 'TRANSFER_FEE_RATE'))
        self.assertTrue(hasattr(Config, 'MIN_COMMISSION'))
        self.assertTrue(hasattr(Config, 'T1_RULE'))

    def test_strategy_configs(self):
        """测试策略配置"""
        from config import Config

        self.assertTrue(hasattr(Config, 'STRATEGY_TYPE'))
        self.assertTrue(hasattr(Config, 'VOLUME_FILTER'))
        self.assertTrue(hasattr(Config, 'VOLUME_RATIO'))

    def test_backtest_configs(self):
        """测试回测配置"""
        from config import Config

        self.assertTrue(hasattr(Config, 'INITIAL_CAPITAL'))
        self.assertTrue(hasattr(Config, 'POSITION_RATIO'))
        self.assertTrue(hasattr(Config, 'STOP_LOSS_RATIO'))
        self.assertTrue(hasattr(Config, 'TAKE_PROFIT_RATIO'))

    def test_logging_configs(self):
        """测试日志配置"""
        from config import Config

        self.assertTrue(hasattr(Config, 'LOG_LEVEL'))
        self.assertTrue(hasattr(Config, 'LOG_RETENTION_DAYS'))

    @patch('config.Path.mkdir')
    def test_ensure_dirs(self, mock_mkdir):
        """测试 ensure_dirs 方法"""
        from config import Config

        Config.ensure_dirs()
        self.assertTrue(mock_mkdir.called)

    def test_get_best_params_path(self):
        """测试 get_best_params_path 方法"""
        from config import Config

        path = Config.get_best_params_path()
        self.assertIsInstance(path, Path)
        self.assertEqual(path.name, 'best_strategy_params.json')

    def test_is_stock_data_exists(self):
        """测试 is_stock_data_exists 方法"""
        from config import Config

        # 方法应该存在且可调用
        self.assertTrue(callable(Config.is_stock_data_exists))

    @patch('config.Path.exists')
    def test_is_stock_data_exists_mock(self, mock_exists):
        """测试 is_stock_data_exists 方法逻辑"""
        from config import Config

        mock_exists.return_value = True
        result = Config.is_stock_data_exists('sh600519', 'daily')
        self.assertTrue(result)

        mock_exists.return_value = False
        result = Config.is_stock_data_exists('sh600519', 'daily')
        self.assertFalse(result)

    def test_calculate_fees(self):
        """测试 calculate_fees 方法"""
        from config import Config

        # 测试买入费用
        buy_fees = Config.calculate_fees(100000, is_sell=False)
        self.assertIsInstance(buy_fees, float)
        self.assertGreater(buy_fees, 0)

        # 测试卖出费用（应该比买入高，因为有印花税）
        sell_fees = Config.calculate_fees(100000, is_sell=True)
        self.assertGreater(sell_fees, buy_fees)

    def test_calculate_fees_min_commission(self):
        """测试最低手续费"""
        from config import Config

        # 小金额交易应该收取最低手续费
        small_fees = Config.calculate_fees(100, is_sell=False)
        self.assertGreaterEqual(small_fees, Config.MIN_COMMISSION)

    @patch('config.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_best_params(self, mock_file, mock_exists):
        """测试 _load_best_params 方法"""
        from config import Config

        # Mock 文件存在
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = '{}'

        # 调用 get_optimized_params 间接调用 _load_best_params
        params = Config.get_optimized_params('rsi')
        self.assertIsInstance(params, dict)

    @patch('config.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_optimized_params(self, mock_file, mock_exists):
        """测试 get_optimized_params 方法"""
        from config import Config

        # Mock 文件存在且有数据
        mock_exists.return_value = True
        test_data = {
            'rsi': {
                'best_params': {'rsi_period': 14}
            }
        }
        mock_file.return_value.read.return_value = json.dumps(test_data)

        # 清除缓存
        Config._best_params_cache = None
        Config._best_params_mtime = None

        params = Config.get_optimized_params('rsi')
        self.assertEqual(params, {'rsi_period': 14})

    @patch('config.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_all_optimized_strategies(self, mock_file, mock_exists):
        """测试 get_all_optimized_strategies 方法"""
        from config import Config

        # Mock 文件存在且有数据
        mock_exists.return_value = True
        test_data = {
            'rsi': {'best_params': {}},
            'macd': {'best_params': {}}
        }
        mock_file.return_value.read.return_value = json.dumps(test_data)

        # 清除缓存
        Config._best_params_cache = None
        Config._best_params_mtime = None

        strategies = Config.get_all_optimized_strategies()
        self.assertEqual(set(strategies), {'rsi', 'macd'})


if __name__ == '__main__':
    unittest.main()
