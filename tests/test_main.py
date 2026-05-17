# -*- coding: utf-8 -*-
"""
主程序入口测试
测试命令行参数解析和主要功能入口
"""
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys
import argparse

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from main import QuantMainEngine


class TestMainCommandLineArgs(unittest.TestCase):
    """测试命令行参数解析"""

    @patch('sys.argv', ['main.py'])
    def test_default_args_parse(self):
        """测试默认参数解析"""
        from main import parser
        args = parser.parse_args([])
        self.assertFalse(args.fetch_data)
        self.assertFalse(args.update_data)
        self.assertFalse(args.compare_strategies)
        self.assertFalse(args.optimize_all)
        self.assertIsNone(args.optimize)
        self.assertIsNone(args.progress)
        self.assertFalse(args.evolve_strategies)
        self.assertFalse(args.paper_trade)
        self.assertFalse(args.paper_trade_report)

    @patch('sys.argv', ['main.py', '--fetch-data'])
    def test_fetch_data_arg_parse(self):
        """测试--fetch-data参数解析"""
        from main import parser
        args = parser.parse_args(['--fetch-data'])
        self.assertTrue(args.fetch_data)

    @patch('sys.argv', ['main.py', '--update-data'])
    def test_update_data_arg_parse(self):
        """测试--update-data参数解析"""
        from main import parser
        args = parser.parse_args(['--update-data'])
        self.assertTrue(args.update_data)

    @patch('sys.argv', ['main.py', '--compare-strategies'])
    def test_compare_strategies_arg_parse(self):
        """测试--compare-strategies参数解析"""
        from main import parser
        args = parser.parse_args(['--compare-strategies'])
        self.assertTrue(args.compare_strategies)

    @patch('sys.argv', ['main.py', '--optimize-all'])
    def test_optimize_all_arg_parse(self):
        """测试--optimize-all参数解析"""
        from main import parser
        args = parser.parse_args(['--optimize-all'])
        self.assertTrue(args.optimize_all)

    @patch('sys.argv', ['main.py', '--optimize', 'rsi'])
    def test_optimize_single_arg_parse(self):
        """测试--optimize参数带策略名解析"""
        from main import parser
        args = parser.parse_args(['--optimize', 'rsi'])
        self.assertEqual(args.optimize, 'rsi')

    @patch('sys.argv', ['main.py', '--progress', 'optimize'])
    def test_progress_arg_parse(self):
        """测试--progress参数解析"""
        from main import parser
        args = parser.parse_args(['--progress', 'optimize'])
        self.assertEqual(args.progress, 'optimize')

    @patch('sys.argv', ['main.py', '--paper-trade', '--initial-capital', '2000000', '--max-position-ratio', '0.2', '--top-strategies', '10'])
    def test_paper_trade_args_parse(self):
        """测试模拟盘相关参数解析"""
        from main import parser
        args = parser.parse_args([
            '--paper-trade',
            '--initial-capital', '2000000',
            '--max-position-ratio', '0.2',
            '--top-strategies', '10'
        ])
        self.assertTrue(args.paper_trade)
        self.assertEqual(args.initial_capital, 2000000.0)
        self.assertEqual(args.max_position_ratio, 0.2)
        self.assertEqual(args.top_strategies, 10)

    @patch('sys.argv', ['main.py', '--paper-trade-report', '--report-start-date', '20240101', '--report-end-date', '20240131'])
    def test_paper_trade_report_args_parse(self):
        """测试模拟盘报告参数解析"""
        from main import parser
        args = parser.parse_args([
            '--paper-trade-report',
            '--report-start-date', '20240101',
            '--report-end-date', '20240131'
        ])
        self.assertTrue(args.paper_trade_report)
        self.assertEqual(args.report_start_date, '20240101')
        self.assertEqual(args.report_end_date, '20240131')


class TestMainEngineStaticMethods(unittest.TestCase):
    """测试主引擎的静态方法"""

    def test_check_project_structure(self):
        """测试项目结构检查方法"""
        # 应该不会抛出异常，因为当前项目结构是正确的
        try:
            QuantMainEngine.check_project_structure()
            self.assertTrue(True)
        except SystemExit:
            self.fail("项目结构检查失败，当前结构应该是正确的")

    @patch('unittest.TextTestRunner.run')
    def test_run_unit_tests(self, mock_run):
        """测试运行单元测试"""
        mock_result = MagicMock()
        mock_result.wasSuccessful.return_value = True
        mock_result.testsRun = 10
        mock_run.return_value = mock_result

        result = QuantMainEngine.run_unit_tests()
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
