# -*- coding: utf-8 -*-
"""
通用工具类
提供项目中多处使用的公共函数，减少重复代码
"""
import os
import json
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import numpy as np
import pandas as pd

from utils.atomic_writer import AtomicWriter
from config import Config


class CommonUtils:
    """
    通用工具类，所有方法都是静态方法
    """

    @staticmethod
    def ensure_dir_exists(dir_path: str | Path) -> Path:
        """
        确保目录存在，如果不存在则创建
        参数:
            dir_path: 目录路径
        返回:
            Path对象
        """
        path = Path(dir_path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def get_timestamp(format_str: str = "%Y%m%d_%H%M%S") -> str:
        """
        获取当前时间戳字符串
        参数:
            format_str: 时间格式，默认是%Y%m%d_%H%M%S
        返回:
            时间戳字符串
        """
        return datetime.datetime.now().strftime(format_str)

    @staticmethod
    def get_current_date_str(format_str: str = "%Y-%m-%d") -> str:
        """
        获取当前日期字符串
        参数:
            format_str: 日期格式，默认是%Y-%m-%d
        返回:
            日期字符串
        """
        return datetime.date.today().strftime(format_str)

    @staticmethod
    def calculate_metrics_stats(metrics_list: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        批量计算指标的统计值（平均值、最大值、最小值、标准差等）
        参数:
            metrics_list: 指标字典列表，每个字典包含相同的key
        返回:
            统计结果字典，每个key对应的值是该指标的统计值
            例如: {'avg_return': 0.1, 'max_return': 0.5, 'min_return': -0.2, 'std_return': 0.3}
        """
        if not metrics_list:
            return {}

        # 收集所有指标的数值
        metrics_data: Dict[str, List[float]] = {}
        for metrics in metrics_list:
            for key, value in metrics.items():
                if isinstance(value, (int, float)) and value is not None:
                    if key not in metrics_data:
                        metrics_data[key] = []
                    metrics_data[key].append(value)

        # 计算统计值
        stats: Dict[str, float] = {}
        for key, values in metrics_data.items():
            if not values:
                continue
            values_np = np.array(values)
            stats[f'avg_{key}'] = float(np.mean(values_np))
            stats[f'max_{key}'] = float(np.max(values_np))
            stats[f'min_{key}'] = float(np.min(values_np))
            stats[f'std_{key}'] = float(np.std(values_np))
            stats[f'count_{key}'] = len(values_np)

        return stats

    @staticmethod
    def calculate_trade_fees(
        amount: float,
        is_sell: bool = False,
        stock_code: Optional[str] = None
    ) -> float:
        """
        计算交易费用（佣金、印花税、过户费），完全符合A股实盘规则
        参数:
            amount: 交易金额（元）
            is_sell: 是否是卖出，默认是False（买入）
            stock_code: 股票代码，用于判断是否收取过户费（沪市股票收取）
        返回:
            总交易费用（元）
        """
        if amount <= 0:
            return 0.0

        # 佣金：万分之2.5，最低5元
        commission = max(amount * Config.COMMISSION_RATE, Config.MIN_COMMISSION)

        # 过户费：万分之0.1，双向收取，仅沪市股票
        transfer_fee = 0.0
        if stock_code and stock_code.startswith(Config.STOCK_PREFIX_SH):
            transfer_fee = amount * Config.TRANSFER_FEE_RATE

        # 印花税：千分之1，仅卖出时收取
        stamp_duty = amount * Config.STAMP_DUTY_RATE if is_sell else 0.0

        return commission + transfer_fee + stamp_duty

    @staticmethod
    def check_t1_rule(
        buy_date: datetime.date | str,
        sell_date: datetime.date | str,
        date_format: str = "%Y-%m-%d"
    ) -> bool:
        """
        检查是否符合T+1交易规则（买入后第二个交易日才能卖出）
        参数:
            buy_date: 买入日期，可以是date对象或者字符串
            sell_date: 卖出日期，可以是date对象或者字符串
            date_format: 日期字符串的格式，默认是%Y-%m-%d
        返回:
            True表示可以卖出，False表示不符合T+1规则
        """
        # 转换为date对象
        if isinstance(buy_date, str):
            buy_date = datetime.datetime.strptime(buy_date, date_format).date()
        if isinstance(sell_date, str):
            sell_date = datetime.datetime.strptime(sell_date, date_format).date()

        # 计算持有天数
        days_held = (sell_date - buy_date).days
        return days_held >= 1

    @staticmethod
    def safe_float(value: Any, default: float = 0.0) -> float:
        """
        安全的转换为float，避免异常
        参数:
            value: 要转换的值
            default: 转换失败时的默认值
        返回:
            转换后的float值
        """
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def safe_int(value: Any, default: int = 0) -> int:
        """
        安全的转换为int，避免异常
        参数:
            value: 要转换的值
            default: 转换失败时的默认值
        返回:
            转换后的int值
        """
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def load_json_file(file_path: str | Path, default: Any = None) -> Any:
        """
        安全的加载JSON文件
        参数:
            file_path: JSON文件路径
            default: 加载失败时的默认值
        返回:
            加载后的JSON数据
        """
        path = Path(file_path)
        if not path.exists():
            return default

        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return default

    @staticmethod
    def save_json_file(file_path: str | Path, data: Any, indent: int = 2) -> bool:
        """
        安全的保存JSON文件，使用原子写入避免文件损坏
        参数:
            file_path: JSON文件路径
            data: 要保存的数据
            indent: 缩进空格数，默认2
        返回:
            True表示保存成功，False表示失败
        """
        try:
            AtomicWriter.write_json(Path(file_path), data, ensure_ascii=False, indent=indent)
            return True
        except Exception:
            return False

    @staticmethod
    def format_percent(value: float, decimal_places: int = 2) -> str:
        """
        格式化为百分比字符串
        参数:
            value: 数值，例如0.1表示10%
            decimal_places: 小数位数，默认2
        返回:
            格式化后的百分比字符串，例如"10.00%"
        """
        return f"{value * 100:.{decimal_places}f}%"

    @staticmethod
    def format_currency(value: float, decimal_places: int = 2) -> str:
        """
        格式化为货币字符串
        参数:
            value: 金额
            decimal_places: 小数位数，默认2
        返回:
            格式化后的货币字符串，例如"¥1,234.56"
        """
        return f"¥{value:,.{decimal_places}f}"

    @staticmethod
    def get_stock_code_prefix(stock_code: str) -> str:
        """
        获取股票代码的前缀（sh或sz）
        参数:
            stock_code: 股票代码，例如"sh600000"或"600000"
        返回:
            前缀"sh"或"sz"，如果没有前缀则返回空字符串
        """
        if stock_code.startswith((Config.STOCK_PREFIX_SH, Config.STOCK_PREFIX_SZ)):
            return stock_code[:2]
        return ""

    @staticmethod
    def remove_stock_code_prefix(stock_code: str) -> str:
        """
        移除股票代码的前缀
        参数:
            stock_code: 股票代码，例如"sh600000"
        返回:
            移除前缀后的代码，例如"600000"
        """
        if stock_code.startswith((Config.STOCK_PREFIX_SH, Config.STOCK_PREFIX_SZ)):
            return stock_code[2:]
        return stock_code
