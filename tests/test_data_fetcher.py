# -*- coding: utf-8 -*-
"""
数据获取模块测试
- AStockDataFetcher 的数据清洗、标准化、本地加载等功能
"""
import unittest
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDataFetcher(unittest.TestCase):
    """测试数据获取器"""

    def setUp(self):
        """测试前准备"""
        self.config = MagicMock()
        self.config.SAVED_DATA_DIR = Path('/tmp/test_data')
        self.config.START_DATE = "20230101"
        self.config.END_DATE = "20260101"
        self.config.KLINE_PERIOD = "daily"

        def get_stock_list():
            return ['sh600519', 'sz000001']

        def get_start_date():
            return "20230101"

        def get_end_date():
            return "20260101"

        self.config.get_stock_list = get_stock_list
        self.config.get_start_date = get_start_date
        self.config.get_end_date = get_end_date

        self.logger = MagicMock()

    def create_mock_dataframe(self, n_days=100, seed=42):
        """创建模拟股票 DataFrame"""
        np.random.seed(seed)
        dates = pd.date_range('2023-01-01', periods=n_days)
        base_price = 100
        df = pd.DataFrame({
            'date': dates,
            'open': np.random.uniform(base_price * 0.95, base_price * 1.05, n_days),
            'high': np.random.uniform(base_price * 1.0, base_price * 1.1, n_days),
            'low': np.random.uniform(base_price * 0.9, base_price * 0.98, n_days),
            'close': np.random.uniform(base_price * 0.95, base_price * 1.05, n_days),
            'volume': np.random.uniform(1000000, 10000000, n_days)
        })
        return df

    def test_import_data_fetcher(self):
        """测试能否正确导入 data_fetcher 模块"""
        try:
            from data_fetcher.data_fetcher import AStockDataFetcher
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"导入失败: {e}")

    @patch('data_fetcher.data_fetcher.AK_AVAILABLE', False)
    @patch('data_fetcher.data_fetcher.BAOSTOCK_AVAILABLE', False)
    def test_init_no_data_sources(self):
        """测试无数据源时的初始化"""
        from data_fetcher.data_fetcher import AStockDataFetcher
        with self.assertRaises(ImportError):
            AStockDataFetcher(self.config, self.logger)

    def test_clean_data_basic(self):
        """测试数据清洗基本功能"""
        from data_fetcher.data_fetcher import AStockDataFetcher

        # 不实际调用 API，只测试内部方法
        with patch('data_fetcher.data_fetcher.AK_AVAILABLE', True):
            with patch('data_fetcher.data_fetcher.BAOSTOCK_AVAILABLE', True):
                fetcher = AStockDataFetcher(self.config, self.logger)

        # 创建有问题的数据
        df = self.create_mock_dataframe(n_days=10)
        # 添加重复行
        df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
        # 添加负数价格（单独测试，避免整行删除互相影响）
        df_neg_price = df.copy()
        df_neg_price.loc[0, 'open'] = -10
        # 添加负数成交量（单独测试）
        df_neg_vol = df.copy()
        df_neg_vol.loc[5, 'volume'] = -100  # 选第5行，不与负价格行重叠

        # 测试1：去重
        cleaned_df = fetcher._clean_data(df)
        self.assertEqual(len(cleaned_df['date'].unique()), len(cleaned_df))

        # 测试2：负价格被过滤
        cleaned_df2 = fetcher._clean_data(df_neg_price)
        self.assertTrue((cleaned_df2['open'] > 0).all())
        self.assertTrue((cleaned_df2['close'] > 0).all())

        # 测试3：负成交量被过滤
        cleaned_df3 = fetcher._clean_data(df_neg_vol)
        self.assertTrue((cleaned_df3['volume'] >= 0).all())

    def test_clean_data_empty(self):
        """测试清洗空数据"""
        from data_fetcher.data_fetcher import AStockDataFetcher

        with patch('data_fetcher.data_fetcher.AK_AVAILABLE', True):
            with patch('data_fetcher.data_fetcher.BAOSTOCK_AVAILABLE', True):
                fetcher = AStockDataFetcher(self.config, self.logger)

        # 测试 None
        result = fetcher._clean_data(None)
        self.assertIsNone(result)

        # 测试空 DataFrame
        empty_df = pd.DataFrame()
        result = fetcher._clean_data(empty_df)
        self.assertTrue(result.empty)

    def test_standardize_data(self):
        """测试数据标准化"""
        from data_fetcher.data_fetcher import AStockDataFetcher

        with patch('data_fetcher.data_fetcher.AK_AVAILABLE', True):
            with patch('data_fetcher.data_fetcher.BAOSTOCK_AVAILABLE', True):
                fetcher = AStockDataFetcher(self.config, self.logger)

        df = self.create_mock_dataframe(n_days=5)

        # 确保日期是 datetime 格式
        df['date'] = pd.to_datetime(df['date'])

        # 标准化
        standardized_df = fetcher._standardize_data(df)

        # 验证日期格式
        self.assertEqual(standardized_df['date'].iloc[0], '2023-01-01')

        # 验证数值列是数值类型
        for col in ['open', 'high', 'low', 'close', 'volume']:
            self.assertTrue(pd.api.types.is_numeric_dtype(standardized_df[col]))

    def test_standardize_data_empty(self):
        """测试标准化空数据"""
        from data_fetcher.data_fetcher import AStockDataFetcher

        with patch('data_fetcher.data_fetcher.AK_AVAILABLE', True):
            with patch('data_fetcher.data_fetcher.BAOSTOCK_AVAILABLE', True):
                fetcher = AStockDataFetcher(self.config, self.logger)

        # 测试 None
        result = fetcher._standardize_data(None)
        self.assertIsNone(result)

        # 测试空 DataFrame
        empty_df = pd.DataFrame()
        result = fetcher._standardize_data(empty_df)
        self.assertTrue(result.empty)

    @patch('pathlib.Path.exists')
    @patch('pandas.read_csv')
    def test_load_data(self, mock_read_csv, mock_exists):
        """测试从本地加载数据"""
        from data_fetcher.data_fetcher import AStockDataFetcher

        with patch('data_fetcher.data_fetcher.AK_AVAILABLE', True):
            with patch('data_fetcher.data_fetcher.BAOSTOCK_AVAILABLE', True):
                fetcher = AStockDataFetcher(self.config, self.logger)

        # Mock 文件存在
        mock_exists.return_value = True
        expected_df = self.create_mock_dataframe(n_days=10)
        mock_read_csv.return_value = expected_df

        # 加载数据
        result = fetcher.load_data('sh600519', 'daily')

        # 验证
        mock_read_csv.assert_called_once()
        pd.testing.assert_frame_equal(result, expected_df)

    @patch('pathlib.Path.exists')
    def test_load_data_not_exists(self, mock_exists):
        """测试加载不存在的数据"""
        from data_fetcher.data_fetcher import AStockDataFetcher

        with patch('data_fetcher.data_fetcher.AK_AVAILABLE', True):
            with patch('data_fetcher.data_fetcher.BAOSTOCK_AVAILABLE', True):
                fetcher = AStockDataFetcher(self.config, self.logger)

        # Mock 文件不存在
        mock_exists.return_value = False

        # 加载数据
        result = fetcher.load_data('sh600519', 'daily')

        # 验证
        self.assertIsNone(result)

    @patch('data_fetcher.data_fetcher.AStockDataFetcher.load_data')
    @patch('pathlib.Path.exists')
    def test_fetch_stock_data_local_exists(self, mock_exists, mock_load_data):
        """测试本地数据存在时跳过下载"""
        from data_fetcher.data_fetcher import AStockDataFetcher

        with patch('data_fetcher.data_fetcher.AK_AVAILABLE', True):
            with patch('data_fetcher.data_fetcher.BAOSTOCK_AVAILABLE', True):
                fetcher = AStockDataFetcher(self.config, self.logger)

        # Mock 本地文件存在
        mock_exists.return_value = True
        expected_df = self.create_mock_dataframe(n_days=10)
        mock_load_data.return_value = expected_df

        # 调用 fetch_stock_data
        result = fetcher.fetch_stock_data('sh600519', '20230101', '20260101', 'daily')

        # 验证直接加载本地数据，不调用 API
        mock_load_data.assert_called_once_with('sh600519', 'daily')
        pd.testing.assert_frame_equal(result, expected_df)

    def test_clean_data_remove_duplicates(self):
        """测试清洗重复日期"""
        from data_fetcher.data_fetcher import AStockDataFetcher

        with patch('data_fetcher.data_fetcher.AK_AVAILABLE', True):
            with patch('data_fetcher.data_fetcher.BAOSTOCK_AVAILABLE', True):
                fetcher = AStockDataFetcher(self.config, self.logger)

        # 创建有重复日期的数据
        df = self.create_mock_dataframe(n_days=5)
        df = pd.concat([df, df], ignore_index=True)  # 重复所有行

        self.assertEqual(len(df), 10)

        # 清洗
        cleaned_df = fetcher._clean_data(df)

        # 验证重复被移除
        self.assertEqual(len(cleaned_df), 5)

    def test_clean_data_positive_prices(self):
        """测试清洗确保价格为正"""
        from data_fetcher.data_fetcher import AStockDataFetcher

        with patch('data_fetcher.data_fetcher.AK_AVAILABLE', True):
            with patch('data_fetcher.data_fetcher.BAOSTOCK_AVAILABLE', True):
                fetcher = AStockDataFetcher(self.config, self.logger)

        df = self.create_mock_dataframe(n_days=5)
        df.loc[0, 'open'] = -10  # 负价格
        df.loc[1, 'high'] = -5
        df.loc[2, 'low'] = -3
        df.loc[3, 'close'] = -1

        cleaned_df = fetcher._clean_data(df)

        # 验证负价格行被移除
        for col in ['open', 'high', 'low', 'close']:
            self.assertTrue((cleaned_df[col] > 0).all())

    def test_clean_data_non_negative_volume(self):
        """测试清洗确保成交量非负"""
        from data_fetcher.data_fetcher import AStockDataFetcher

        with patch('data_fetcher.data_fetcher.AK_AVAILABLE', True):
            with patch('data_fetcher.data_fetcher.BAOSTOCK_AVAILABLE', True):
                fetcher = AStockDataFetcher(self.config, self.logger)

        df = self.create_mock_dataframe(n_days=5)
        df.loc[0, 'volume'] = -100  # 负成交量

        cleaned_df = fetcher._clean_data(df)

        # 验证负成交量行被移除
        self.assertTrue((cleaned_df['volume'] >= 0).all())

    def test_standardize_data_date_format(self):
        """测试日期格式标准化"""
        from data_fetcher.data_fetcher import AStockDataFetcher

        with patch('data_fetcher.data_fetcher.AK_AVAILABLE', True):
            with patch('data_fetcher.data_fetcher.BAOSTOCK_AVAILABLE', True):
                fetcher = AStockDataFetcher(self.config, self.logger)

        # 测试能被 pd.to_datetime 解析的日期格式
        # 注意：真实代码有 try-except，解析失败会保持原样
        test_cases = [
            ('2023-01-01', '2023-01-01'),
            (pd.Timestamp('2023-01-01'), '2023-01-01'),
        ]

        for date_val, expected in test_cases:
            with self.subTest(date_val=date_val):
                df = pd.DataFrame({
                    'date': [date_val],
                    'open': [100],
                    'high': [110],
                    'low': [90],
                    'close': [105],
                    'volume': [1000000]
                })

                standardized_df = fetcher._standardize_data(df)
                self.assertEqual(standardized_df['date'].iloc[0], expected)

    def test_standardize_data_numeric_columns(self):
        """测试数值列标准化"""
        from data_fetcher.data_fetcher import AStockDataFetcher

        with patch('data_fetcher.data_fetcher.AK_AVAILABLE', True):
            with patch('data_fetcher.data_fetcher.BAOSTOCK_AVAILABLE', True):
                fetcher = AStockDataFetcher(self.config, self.logger)

        # 创建字符串类型的数值列
        df = pd.DataFrame({
            'date': ['2023-01-01'],
            'open': ['100.5'],
            'high': ['110.0'],
            'low': ['90.5'],
            'close': ['105.0'],
            'volume': ['1000000']
        })

        standardized_df = fetcher._standardize_data(df)

        # 验证都转换为数值类型
        for col in ['open', 'high', 'low', 'close', 'volume']:
            self.assertTrue(pd.api.types.is_numeric_dtype(standardized_df[col]))

    @patch('pathlib.Path.exists')
    @patch('pandas.read_csv')
    def test_update_stock_data_local_not_exists(self, mock_read_csv, mock_exists):
        """测试 update_stock_data - 本地不存在时调用 fetch_stock_data"""
        from data_fetcher.data_fetcher import AStockDataFetcher

        with patch('data_fetcher.data_fetcher.AK_AVAILABLE', True):
            with patch('data_fetcher.data_fetcher.BAOSTOCK_AVAILABLE', True):
                fetcher = AStockDataFetcher(self.config, self.logger)

        # Mock 本地文件不存在
        mock_exists.return_value = False

        # Mock fetch_stock_data
        expected_df = self.create_mock_dataframe(n_days=10)
        with patch.object(fetcher, 'fetch_stock_data') as mock_fetch:
            mock_fetch.return_value = expected_df

            # 调用 update_stock_data
            result = fetcher.update_stock_data('sh600519', 'daily')

            # 验证 fetch_stock_data 被调用
            mock_fetch.assert_called_once()
            pd.testing.assert_frame_equal(result, expected_df)

    @patch('pathlib.Path.exists')
    @patch('pandas.read_csv')
    def test_update_stock_data_already_latest(self, mock_read_csv, mock_exists):
        """测试 update_stock_data - 数据已是最新"""
        from data_fetcher.data_fetcher import AStockDataFetcher
        from datetime import datetime, timedelta

        with patch('data_fetcher.data_fetcher.AK_AVAILABLE', True):
            with patch('data_fetcher.data_fetcher.BAOSTOCK_AVAILABLE', True):
                fetcher = AStockDataFetcher(self.config, self.logger)

        # Mock 本地文件存在
        mock_exists.return_value = True

        # 创建包含今天日期的数据
        today = datetime.now()
        df = self.create_mock_dataframe(n_days=5)
        df['date'] = pd.date_range(end=today, periods=5)
        mock_read_csv.return_value = df

        # 调用 update_stock_data
        result = fetcher.update_stock_data('sh600519', 'daily')

        # 验证返回本地数据（不调用API）
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 5)

    @patch('data_fetcher.data_fetcher.AStockDataFetcher.fetch_stock_data')
    def test_fetch_all_stocks(self, mock_fetch):
        """测试 fetch_all_stocks - 循环调用 fetch_stock_data"""
        from data_fetcher.data_fetcher import AStockDataFetcher

        with patch('data_fetcher.data_fetcher.AK_AVAILABLE', True):
            with patch('data_fetcher.data_fetcher.BAOSTOCK_AVAILABLE', True):
                fetcher = AStockDataFetcher(self.config, self.logger)

        # Mock fetch_stock_data 返回值
        expected_df = self.create_mock_dataframe(n_days=10)
        mock_fetch.return_value = expected_df

        # Mock time.sleep
        with patch('time.sleep'):
            # 调用 fetch_all_stocks
            results = fetcher.fetch_all_stocks()

        # 验证 fetch_stock_data 被调用了2次（配置里有2只股票）
        self.assertEqual(mock_fetch.call_count, 2)
        # 验证返回结果
        self.assertIn('sh600519', results)
        self.assertIn('sz000001', results)

    @patch('data_fetcher.data_fetcher.AStockDataFetcher.update_stock_data')
    def test_update_all_stocks(self, mock_update):
        """测试 update_all_stocks - 循环调用 update_stock_data"""
        from data_fetcher.data_fetcher import AStockDataFetcher

        with patch('data_fetcher.data_fetcher.AK_AVAILABLE', True):
            with patch('data_fetcher.data_fetcher.BAOSTOCK_AVAILABLE', True):
                fetcher = AStockDataFetcher(self.config, self.logger)

        # Mock update_stock_data 返回值
        expected_df = self.create_mock_dataframe(n_days=10)
        mock_update.return_value = expected_df

        # Mock time.sleep
        with patch('time.sleep'):
            # 调用 update_all_stocks
            results = fetcher.update_all_stocks()

        # 验证 update_stock_data 被调用了2次
        self.assertEqual(mock_update.call_count, 2)
        # 验证返回统计信息
        self.assertEqual(results['total'], 2)
        self.assertEqual(results['updated'], 2)
        self.assertEqual(results['skipped'], 0)
        self.assertEqual(results['failed'], 0)

    @patch('builtins.print')
    @patch('data_fetcher.data_fetcher.AStockDataFetcher.fetch_all_stocks')
    def test_fetch_all_with_print(self, mock_fetch_all, mock_print):
        """测试 fetch_all_with_print - 调用 fetch_all_stocks"""
        from data_fetcher.data_fetcher import AStockDataFetcher

        with patch('data_fetcher.data_fetcher.AK_AVAILABLE', True):
            with patch('data_fetcher.data_fetcher.BAOSTOCK_AVAILABLE', True):
                fetcher = AStockDataFetcher(self.config, self.logger)

        # Mock fetch_all_stocks 返回 True
        mock_fetch_all.return_value = True

        # 调用 fetch_all_with_print
        result = fetcher.fetch_all_with_print()

        # 验证返回值
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
