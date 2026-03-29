# -*- coding: utf-8 -*-
"""
文件清理模块
负责自动清理临时文件、缓存等
"""
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta


class FileCleaner:
    """文件清理类"""

    def __init__(self, config, logger):
        """
        初始化清理器

        参数:
            config: 配置对象
            logger: 日志对象
        """
        self.config = config
        self.logger = logger
        self.temp_dir = Path(config.TEMP_DIR)

        # 保留的目录（不删除）
        self.protected_dirs = [
            Path(config.SAVED_DATA_DIR),
            Path(config.REPORTS_DIR),
            Path(config.LOG_DIR)
        ]

    def clean_temp_dir(self):
        """清理临时目录"""
        if not self.temp_dir.exists():
            self.logger.debug("临时目录不存在，无需清理")
            return

        deleted_count = 0
        deleted_size = 0

        for item in self.temp_dir.iterdir():
            try:
                if item.is_file():
                    size = item.stat().st_size
                    item.unlink()
                    deleted_count += 1
                    deleted_size += size
                    self.logger.debug(f"删除临时文件: {item}")
                elif item.is_dir():
                    size = self._get_dir_size(item)
                    shutil.rmtree(item)
                    deleted_count += 1
                    deleted_size += size
                    self.logger.debug(f"删除临时目录: {item}")
            except Exception as e:
                self.logger.warning(f"删除 {item} 失败: {str(e)}")

        self.logger.info(f"临时目录清理完成，删除 {deleted_count} 项，释放 {self._format_size(deleted_size)}")

    def _get_dir_size(self, dir_path):
        """获取目录大小"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(dir_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
        return total_size

    def _format_size(self, size_bytes):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"

    def clean_old_logs(self, days=30):
        """清理旧日志文件"""
        log_dir = Path(self.config.LOG_DIR)
        if not log_dir.exists():
            return

        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0

        for item in log_dir.iterdir():
            try:
                if item.is_file():
                    mtime = datetime.fromtimestamp(item.stat().st_mtime)
                    if mtime < cutoff_date:
                        item.unlink()
                        deleted_count += 1
                        self.logger.debug(f"删除旧日志: {item}")
            except Exception as e:
                self.logger.warning(f"删除 {item} 失败: {str(e)}")

        if deleted_count > 0:
            self.logger.info(f"清理了 {deleted_count} 个旧日志文件（{days}天前）")

    def clean_all(self):
        """执行所有清理任务"""
        self.logger.info("开始执行清理任务...")
        self.clean_temp_dir()
        self.clean_old_logs(self.config.LOG_RETENTION_DAYS)
        self.logger.info("清理任务完成")
