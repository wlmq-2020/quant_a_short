# -*- coding: utf-8 -*-
"""
utils模块测试
测试AtomicWriter、CommonUtils、FileRWLock、EmailNotifier
"""
import unittest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import sys
import json
import datetime
import tempfile
import pandas as pd
import os
import time

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.atomic_writer import AtomicWriter
from utils.common_utils import CommonUtils
from utils.file_rw_lock import FileRWLock
from utils.email_notifier import EmailNotifier
from config import Config


class TestAtomicWriter(unittest.TestCase):
    """测试原子写入工具类"""

    def setUp(self):
        """测试前准备：创建临时目录"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.json"

    def tearDown(self):
        """测试后清理：删除临时目录"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_write_and_read_json(self):
        """测试写入和读取JSON文件"""
        test_data = {"name": "测试", "value": 123, "list": [1, 2, 3]}

        # 写入文件
        AtomicWriter.write_json(self.test_file, test_data)

        # 验证文件存在
        self.assertTrue(self.test_file.exists())
        # 验证哈希文件存在
        self.assertTrue(self.test_file.with_suffix(".json.hash").exists())

        # 读取文件
        read_data = AtomicWriter.read_json(self.test_file)
        self.assertEqual(read_data, test_data)

    def test_write_and_read_text(self):
        """测试写入和读取文本文件"""
        test_content = "这是测试文本\n第二行内容"

        # 写入文件
        AtomicWriter.write_text(self.test_file.with_suffix(".txt"), test_content)

        # 读取文件
        read_content = AtomicWriter.read_text(self.test_file.with_suffix(".txt"))
        self.assertEqual(read_content, test_content)

    def test_write_and_read_csv(self):
        """测试写入和读取CSV文件"""
        test_data = pd.DataFrame({
            "col1": [1, 2, 3],
            "col2": ["a", "b", "c"],
            "col3": [1.1, 2.2, 3.3]
        })

        # 写入文件
        csv_file = self.test_file.with_suffix(".csv")
        AtomicWriter.write_csv(csv_file, test_data)

        # 读取文件
        read_df = AtomicWriter.read_csv(csv_file)
        pd.testing.assert_frame_equal(read_df, test_data)

    def test_batch_write_json(self):
        """测试批量写入JSON文件"""
        batch_data = {
            self.test_file: {"data1": "test1"},
            self.test_file.with_name("test2.json"): {"data2": "test2"}
        }

        AtomicWriter.batch_write_json(batch_data)

        # 验证两个文件都存在且内容正确
        self.assertTrue(self.test_file.exists())
        self.assertTrue(self.test_file.with_name("test2.json").exists())

        self.assertEqual(AtomicWriter.read_json(self.test_file), {"data1": "test1"})
        self.assertEqual(AtomicWriter.read_json(self.test_file.with_name("test2.json")), {"data2": "test2"})

    def test_corrupted_file_recovery(self):
        """测试损坏文件从备份恢复"""
        test_data = {"name": "测试"}

        # 写入原始文件
        AtomicWriter.write_json(self.test_file, test_data)

        # 创建备份文件
        backup_file = self.test_file.with_suffix(".json.bak")
        AtomicWriter.write_json(backup_file, test_data)

        # 损坏主文件
        with open(self.test_file, 'w', encoding='utf-8') as f:
            f.write("这不是合法的JSON")

        # 删除哈希文件，模拟损坏
        hash_file = self.test_file.with_suffix(".json.hash")
        if hash_file.exists():
            hash_file.unlink()

        # 读取时应该自动从备份恢复
        read_data = AtomicWriter.read_json(self.test_file)
        self.assertEqual(read_data, test_data)
        # 验证主文件已经被修复
        with open(self.test_file, 'r', encoding='utf-8') as f:
            self.assertEqual(json.load(f), test_data)

    def test_clean_old_backups(self):
        """测试清理旧备份文件"""
        # 创建几个测试备份文件，修改时间设为40天前
        old_date = datetime.datetime.now() - datetime.timedelta(days=40)
        old_time = time.mktime(old_date.timetuple())

        for i in range(3):
            file_path = Path(self.temp_dir) / f"backup_{i}.json"
            file_path.touch()
            os.utime(file_path, (old_time, old_time))
            # 创建对应的哈希文件
            hash_path = file_path.with_suffix(".json.hash")
            hash_path.touch()
            os.utime(hash_path, (old_time, old_time))

        # 创建一个新的备份文件
        new_file = Path(self.temp_dir) / "backup_new.json"
        new_file.touch()

        # 清理超过30天的备份
        AtomicWriter.clean_old_backups(self.temp_dir, "backup_*.json", days=30)

        # 验证旧的被删除，新的保留
        self.assertEqual(len(list(Path(self.temp_dir).glob("backup_*.json"))), 1)
        self.assertTrue(new_file.exists())


class TestCommonUtils(unittest.TestCase):
    """测试通用工具类"""

    def test_ensure_dir_exists(self):
        """测试确保目录存在"""
        test_dir = Path(tempfile.mkdtemp()) / "test_dir" / "sub_dir"
        self.assertFalse(test_dir.exists())

        result = CommonUtils.ensure_dir_exists(test_dir)
        self.assertTrue(test_dir.exists())
        self.assertEqual(result, test_dir)

        import shutil
        shutil.rmtree(test_dir.parent)

    def test_get_timestamp(self):
        """测试获取时间戳"""
        timestamp = CommonUtils.get_timestamp()
        # 验证格式是YYYYMMDD_HHMMSS
        self.assertEqual(len(timestamp), 15)
        self.assertTrue(timestamp.replace("_", "").isdigit())

    def test_calculate_metrics_stats(self):
        """测试计算指标统计值"""
        metrics_list = [
            {"return": 0.1, "sharpe": 1.5, "win_rate": 0.6},
            {"return": 0.2, "sharpe": 2.0, "win_rate": 0.7},
            {"return": 0.0, "sharpe": 1.0, "win_rate": 0.5}
        ]

        stats = CommonUtils.calculate_metrics_stats(metrics_list)

        self.assertEqual(stats["avg_return"], 0.1)
        self.assertEqual(stats["max_return"], 0.2)
        self.assertEqual(stats["min_return"], 0.0)
        self.assertAlmostEqual(stats["std_return"], 0.0816, places=4)
        self.assertEqual(stats["count_return"], 3)

        self.assertEqual(stats["avg_sharpe"], 1.5)
        self.assertEqual(stats["avg_win_rate"], 0.6)

    def test_calculate_trade_fees(self):
        """测试计算交易费用"""
        # 测试买入沪市股票，金额10000元
        buy_fee = CommonUtils.calculate_trade_fees(10000, is_sell=False, stock_code="sh600519")
        # 佣金：10000*0.00025=2.5 → 最低5元，过户费10000*0.00001=0.1元，总5.1元
        self.assertAlmostEqual(buy_fee, 5.1, places=2)

        # 测试卖出沪市股票，金额10000元
        sell_fee = CommonUtils.calculate_trade_fees(10000, is_sell=True, stock_code="sh600519")
        # 佣金5元，过户费0.1元，印花税10000*0.001=10元，总15.1元
        self.assertAlmostEqual(sell_fee, 15.1, places=2)

        # 测试买入深市股票，金额10000元
        buy_fee_sz = CommonUtils.calculate_trade_fees(10000, is_sell=False, stock_code="sz000001")
        # 佣金5元，无过户费，总5元
        self.assertAlmostEqual(buy_fee_sz, 5.0, places=2)

        # 测试大金额交易，佣金超过最低5元
        large_fee = CommonUtils.calculate_trade_fees(100000, is_sell=False, stock_code="sh600519")
        # 佣金100000*0.00025=25元，过户费1元，总26元
        self.assertAlmostEqual(large_fee, 26.0, places=2)

    def test_check_t1_rule(self):
        """测试T+1规则检查"""
        # 字符串日期
        self.assertTrue(CommonUtils.check_t1_rule("2024-01-01", "2024-01-02"))
        self.assertFalse(CommonUtils.check_t1_rule("2024-01-01", "2024-01-01"))

        # date对象
        buy_date = datetime.date(2024, 1, 1)
        sell_date_same = datetime.date(2024, 1, 1)
        sell_date_next = datetime.date(2024, 1, 2)
        self.assertTrue(CommonUtils.check_t1_rule(buy_date, sell_date_next))
        self.assertFalse(CommonUtils.check_t1_rule(buy_date, sell_date_same))

        # 自定义格式
        self.assertTrue(CommonUtils.check_t1_rule("20240101", "20240102", date_format="%Y%m%d"))

    def test_safe_float_and_int(self):
        """测试安全类型转换"""
        self.assertEqual(CommonUtils.safe_float("123.45"), 123.45)
        self.assertEqual(CommonUtils.safe_float("不是数字", default=0.0), 0.0)
        self.assertEqual(CommonUtils.safe_float(None), 0.0)

        self.assertEqual(CommonUtils.safe_int("123"), 123)
        self.assertEqual(CommonUtils.safe_int("不是数字", default=10), 10)
        self.assertEqual(CommonUtils.safe_int(None), 0)

    def test_load_and_save_json_file(self):
        """测试加载和保存JSON文件"""
        test_file = Path(tempfile.mktemp(suffix=".json"))
        test_data = {"key": "value"}

        # 保存文件
        result = CommonUtils.save_json_file(test_file, test_data)
        self.assertTrue(result)
        self.assertTrue(test_file.exists())

        # 加载文件
        loaded_data = CommonUtils.load_json_file(test_file)
        self.assertEqual(loaded_data, test_data)

        # 测试加载不存在的文件
        non_exist = Path("non_exist.json")
        self.assertEqual(CommonUtils.load_json_file(non_exist, default={"default": "val"}), {"default": "val"})

        test_file.unlink()

    def test_format_percent_and_currency(self):
        """测试格式化百分比和货币"""
        self.assertEqual(CommonUtils.format_percent(0.1234), "12.34%")
        self.assertEqual(CommonUtils.format_percent(0.1234, decimal_places=1), "12.3%")

        self.assertEqual(CommonUtils.format_currency(1234.56), "¥1,234.56")
        self.assertEqual(CommonUtils.format_currency(1234.567, decimal_places=2), "¥1,234.57")

    def test_stock_code_prefix_operations(self):
        """测试股票代码前缀操作"""
        self.assertEqual(CommonUtils.get_stock_code_prefix("sh600519"), "sh")
        self.assertEqual(CommonUtils.get_stock_code_prefix("sz000001"), "sz")
        self.assertEqual(CommonUtils.get_stock_code_prefix("600519"), "")

        self.assertEqual(CommonUtils.remove_stock_code_prefix("sh600519"), "600519")
        self.assertEqual(CommonUtils.remove_stock_code_prefix("sz000001"), "000001")
        self.assertEqual(CommonUtils.remove_stock_code_prefix("600519"), "600519")


class TestFileRWLock(unittest.TestCase):
    """测试文件读写锁"""

    def setUp(self):
        """测试前准备"""
        self.temp_file = Path(tempfile.mktemp())
        self.lock = FileRWLock(self.temp_file, timeout=1)

    def tearDown(self):
        """测试后清理"""
        self.lock.release()
        if self.temp_file.exists():
            self.temp_file.unlink()
        lock_file = self.temp_file.with_suffix(".lock")
        if lock_file.exists():
            lock_file.unlink()

    @patch('os.name', 'nt')
    @patch('win32file.LockFileEx')
    @patch('win32file.UnlockFile')
    def test_write_lock_context_manager_windows(self, mock_unlock, mock_lock):
        """测试Windows环境下写锁上下文管理器"""
        mock_lock.return_value = 0

        with self.lock.acquire_write():
            self.assertTrue(self.lock._is_locked)
            # 锁文件应该存在
            self.assertTrue(self.temp_file.with_suffix(".lock").exists())

        # 退出上下文后锁应该释放
        self.assertFalse(self.lock._is_locked)
        mock_unlock.assert_called()

    @patch('os.name', 'posix')
    @patch('fcntl.flock')
    def test_write_lock_context_manager_linux(self, mock_flock):
        """测试Linux环境下写锁上下文管理器"""
        mock_flock.return_value = 0

        with self.lock.acquire_write():
            self.assertTrue(self.lock._is_locked)
            self.assertTrue(self.temp_file.with_suffix(".lock").exists())

        self.assertFalse(self.lock._is_locked)
        # 验证flock被调用了两次：一次加锁，一次解锁
        self.assertEqual(mock_flock.call_count, 2)

    @patch('os.name', 'nt')
    @patch('win32file.LockFileEx')
    @patch('win32file.UnlockFile')
    def test_read_lock_windows(self, mock_unlock, mock_lock):
        """测试Windows环境下读锁"""
        mock_lock.return_value = 0

        with self.lock.acquire_read():
            self.assertTrue(self.lock._is_locked)

        self.assertFalse(self.lock._is_locked)

    @patch('os.name', 'posix')
    @patch('fcntl.flock')
    def test_read_lock_linux(self, mock_flock):
        """测试Linux环境下读锁"""
        mock_flock.return_value = 0

        with self.lock.acquire_read():
            self.assertTrue(self.lock._is_locked)

        self.assertFalse(self.lock._is_locked)

    @patch('os.name', 'nt')
    @patch('win32file.LockFileEx')
    @patch('time.sleep')
    def test_lock_timeout_windows(self, mock_sleep, mock_lock):
        """测试Windows环境下锁超时"""
        # 第一次加锁成功
        lock1 = FileRWLock(self.temp_file, timeout=1)
        mock_lock.return_value = 0
        lock1.acquire_write()

        # 第二次加锁失败，模拟超时
        def mock_lock_fail(*args, **kwargs):
            raise Exception("Lock failed")
        mock_lock.side_effect = mock_lock_fail

        lock2 = FileRWLock(self.temp_file, timeout=1)
        with self.assertRaises(TimeoutError):
            lock2.acquire_write()

        lock1.release()


class TestEmailNotifier(unittest.TestCase):
    """测试邮件通知器"""

    def setUp(self):
        """测试前准备"""
        self.config = MagicMock()
        self.config.EMAIL_NOTIFICATION_ENABLED = True
        self.config.EMAIL_SMTP_SERVER = "smtp.qq.com"
        self.config.EMAIL_SMTP_PORT = 465
        self.config.EMAIL_SENDER = "test@qq.com"
        self.config.EMAIL_SENDER_PASSWORD = "test_password"
        self.config.EMAIL_RECIPIENTS = ["recipient@test.com"]

    @patch('smtplib.SMTP_SSL')
    def test_send_alert(self, mock_smtp):
        """测试发送告警邮件"""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        notifier = EmailNotifier(self.config)
        result = notifier.send_alert("测试告警", "这是告警内容")

        self.assertTrue(result)
        mock_server.login.assert_called_once_with("test@qq.com", "test_password")
        self.assertEqual(mock_server.sendmail.call_count, 1)

    @patch('smtplib.SMTP_SSL')
    def test_send_daily_report(self, mock_smtp):
        """测试发送每日报告"""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        report = {
            "trade_date": "2024-01-01",
            "total_trades": 2,
            "buy_trades": 1,
            "sell_trades": 1,
            "total_realized_profit": 1000.0,
            "cash": 95000.0,
            "position_value": 105000.0,
            "total_value": 200000.0,
            "total_return_pct": 10.0,
            "position_count": 2,
            "positions": [
                {
                    "stock_code": "sh600519",
                    "shares": 100,
                    "avg_price": 1800.0,
                    "current_price": 1900.0,
                    "unrealized_profit": 10000.0,
                    "unrealized_profit_pct": 5.56
                }
            ],
            "trade_details": [
                {
                    "type": "buy",
                    "stock_code": "sh600519",
                    "shares": 100,
                    "price": 1800.0,
                    "amount": 180000.0,
                    "fee": 50.0
                },
                {
                    "type": "sell",
                    "stock_code": "sz000001",
                    "shares": 1000,
                    "price": 11.0,
                    "net_income": 11000.0,
                    "realized_profit": 1000.0,
                    "realized_profit_pct": 10.0
                }
            ]
        }

        notifier = EmailNotifier(self.config)
        result = notifier.send_daily_report(report)

        self.assertTrue(result)
        mock_server.sendmail.assert_called_once()

    def test_email_disabled(self):
        """测试邮件通知禁用情况"""
        self.config.EMAIL_NOTIFICATION_ENABLED = False
        notifier = EmailNotifier(self.config)

        result = notifier.send_alert("测试", "内容")
        self.assertFalse(result)

    def test_incomplete_config(self):
        """测试配置不完整自动禁用"""
        self.config.EMAIL_SENDER = ""
        notifier = EmailNotifier(self.config)

        self.assertFalse(notifier.enabled)
        result = notifier.send_alert("测试", "内容")
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
