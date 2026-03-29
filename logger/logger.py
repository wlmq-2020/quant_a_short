# -*- coding: utf-8 -*-
"""
全局日志组件
提供统一的日志记录功能
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
import threading


class GlobalLogger:
    """全局日志类（单例模式）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, log_dir=None, log_level="INFO", retention_days=30):
        """
        初始化日志组件

        参数:
            log_dir: 日志文件目录
            log_level: 日志级别
            retention_days: 日志保留天数
        """
        # 避免重复初始化
        if hasattr(self, '_initialized') and self._initialized:
            return

        from config import Config

        self.log_dir = Path(log_dir) if log_dir else Config.LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days

        # 创建logger
        self.logger = logging.getLogger("QuantLogger")
        self.logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        self.logger.handlers.clear()  # 清除已有handler
        self.logger.propagate = False  # 不传播到父logger

        # 日志格式
        self.formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 添加控制台handler
        self._add_console_handler()

        # 添加文件handler
        self._add_file_handler()

        self._initialized = True
        self.info("全局日志组件初始化完成")

    def _add_console_handler(self):
        """添加控制台输出handler"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.logger.level)
        console_handler.setFormatter(self.formatter)
        self.logger.addHandler(console_handler)

    def _add_file_handler(self):
        """添加文件输出handler（按天分割）"""
        log_file = self.log_dir / "quant_system.log"
        file_handler = TimedRotatingFileHandler(
            log_file,
            when='midnight',
            interval=1,
            backupCount=self.retention_days,
            encoding='utf-8'
        )
        file_handler.setLevel(self.logger.level)
        file_handler.setFormatter(self.formatter)
        file_handler.suffix = "%Y-%m-%d"
        self.logger.addHandler(file_handler)

    def debug(self, message):
        """记录DEBUG级别日志"""
        self.logger.debug(message)

    def info(self, message):
        """记录INFO级别日志"""
        self.logger.info(message)

    def warning(self, message):
        """记录WARNING级别日志"""
        self.logger.warning(message)

    def error(self, message, exc_info=False):
        """记录ERROR级别日志"""
        self.logger.error(message, exc_info=exc_info)

    def critical(self, message, exc_info=False):
        """记录CRITICAL级别日志"""
        self.logger.critical(message, exc_info=exc_info)

    def get_logger(self):
        """获取原始logger对象"""
        return self.logger


# 全局日志实例
_global_logger = None


def get_logger():
    """获取全局日志单例"""
    global _global_logger
    if _global_logger is None:
        _global_logger = GlobalLogger()
    return _global_logger
