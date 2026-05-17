# -*- coding: utf-8 -*-
"""
原子写入工具类，避免写入过程中程序崩溃导致文件损坏
"""
import json
import csv
import time
import logging
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

class AtomicWriter:
    """原子写入工具类，支持JSON、CSV、普通文本文件（性能优化版）
    【优化点】
    - 提取公共写入逻辑，减少重复代码
    - 支持批量写入，减少临时文件创建次数
    """
    from typing import Callable

    @staticmethod
    def _atomic_write_internal(file_path: Union[str, Path], write_func: Callable[[Path], None]) -> None:
        """内部公共原子写入逻辑，减少重复代码
        Args:
            file_path: 目标文件路径
            write_func: 写入函数，接收临时文件路径作为参数，负责写入内容到临时文件
        """
        file_path = Path(file_path)
        temp_path = file_path.with_suffix(f'{file_path.suffix}.tmp')

        try:
            # 先写入临时文件，设置权限为0o600
            write_func(temp_path)
            # 设置临时文件权限
            try:
                temp_path.chmod(0o600)
            except Exception as e:
                logger.debug(f"设置临时文件{temp_path}权限失败：{e}")

            # 计算SHA256哈希
            hash_sha256 = hashlib.sha256()
            with open(temp_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    hash_sha256.update(chunk)
            file_hash = hash_sha256.hexdigest()

            # 原子替换原文件
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    temp_path.replace(file_path)
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"写入文件{file_path}失败，已重试{max_retries}次：{e}")
                        raise
                    time.sleep(0.1)  # 等待100ms后重试
                    logger.debug(f"写入文件{file_path}第{attempt+1}次失败，重试中：{e}")

            # 写入哈希文件
            hash_path = file_path.with_suffix(f'{file_path.suffix}.hash')
            with open(hash_path, 'w', encoding='utf-8') as f:
                f.write(file_hash)
            try:
                hash_path.chmod(0o600)
            except Exception as e:
                logger.debug(f"设置哈希文件{hash_path}权限失败：{e}")

        finally:
            # 清理临时文件
            if temp_path.exists():
                try:
                    temp_path.unlink(missing_ok=True)
                except Exception as e:
                    logger.warning(f"清理临时文件{temp_path}失败：{e}")

    @staticmethod
    def write_json(file_path: Union[str, Path], data: Any, ensure_ascii: bool = False, indent: int = 2, **kwargs) -> None:
        """原子写入JSON文件"""
        def write_impl(temp_path: Path):
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent, **kwargs)
        AtomicWriter._atomic_write_internal(file_path, write_impl)

    @staticmethod
    def write_csv(file_path: Union[str, Path], df: pd.DataFrame, index: bool = False, encoding: str = 'utf-8-sig', **kwargs) -> None:
        """原子写入CSV文件"""
        def write_impl(temp_path: Path):
            df.to_csv(temp_path, index=index, encoding=encoding, **kwargs)
        AtomicWriter._atomic_write_internal(file_path, write_impl)

    @staticmethod
    def write_text(file_path: Union[str, Path], content: str, encoding: str = 'utf-8', **kwargs) -> None:
        """原子写入普通文本文件"""
        def write_impl(temp_path: Path):
            with open(temp_path, 'w', encoding=encoding, **kwargs) as f:
                f.write(content)
        AtomicWriter._atomic_write_internal(file_path, write_impl)

    @staticmethod
    def batch_write_json(batch_data: Dict[Union[str, Path], Any], **kwargs) -> None:
        """批量写入多个JSON文件，减少重复逻辑开销
        Args:
            batch_data: 字典，key是目标文件路径，value是要写入的JSON数据
        """
        for file_path, data in batch_data.items():
            AtomicWriter.write_json(file_path, data, **kwargs)

    @staticmethod
    def batch_write_text(batch_data: Dict[Union[str, Path], str], **kwargs) -> None:
        """批量写入多个文本文件，减少重复逻辑开销
        Args:
            batch_data: 字典，key是目标文件路径，value是要写入的文本内容
        """
        for file_path, content in batch_data.items():
            AtomicWriter.write_text(file_path, content, **kwargs)

    @staticmethod
    def _verify_file_hash(file_path: Path) -> bool:
        """验证文件哈希是否匹配
        Args:
            file_path: 目标文件路径
        Returns:
            是否匹配
        """
        hash_path = file_path.with_suffix(f'{file_path.suffix}.hash')
        if not hash_path.exists():
            logger.warning(f"哈希文件{hash_path}不存在，跳过校验")
            return True

        try:
            # 读取保存的哈希
            with open(hash_path, 'r', encoding='utf-8') as f:
                saved_hash = f.read().strip()

            # 计算当前文件哈希
            hash_sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    hash_sha256.update(chunk)
            current_hash = hash_sha256.hexdigest()

            return saved_hash == current_hash
        except Exception as e:
            logger.warning(f"校验文件{file_path}哈希失败：{e}")
            return False

    @staticmethod
    def read_json(file_path: Union[str, Path], backup_suffix: str = '.bak', **kwargs) -> Any:
        """读取JSON文件，校验哈希，失败则使用备份
        Args:
            file_path: 目标文件路径
            backup_suffix: 备份文件后缀，或者备份文件路径模式
        Returns:
            读取的数据
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件{file_path}不存在")

        # 校验哈希
        if AtomicWriter._verify_file_hash(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f, **kwargs)
            except Exception as e:
                logger.warning(f"读取文件{file_path}失败：{e}，尝试使用备份")

        # 尝试从备份恢复
        backup_path = file_path.with_suffix(backup_suffix)
        if backup_path.exists():
            logger.info(f"尝试从备份文件{backup_path}恢复")
            if AtomicWriter._verify_file_hash(backup_path):
                try:
                    with open(backup_path, 'r', encoding='utf-8') as f:
                        data = json.load(f, **kwargs)
                    # 恢复主文件
                    AtomicWriter.write_json(file_path, data, **kwargs)
                    return data
                except Exception as e:
                    logger.error(f"读取备份文件{backup_path}失败：{e}")

        raise RuntimeError(f"无法读取文件{file_path}，所有备份均无效")

    @staticmethod
    def read_text(file_path: Union[str, Path], backup_suffix: str = '.bak', **kwargs) -> str:
        """读取文本文件，校验哈希，失败则使用备份
        Args:
            file_path: 目标文件路径
            backup_suffix: 备份文件后缀，或者备份文件路径模式
        Returns:
            读取的文本内容
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件{file_path}不存在")

        # 校验哈希
        if AtomicWriter._verify_file_hash(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8', **kwargs) as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"读取文件{file_path}失败：{e}，尝试使用备份")

        # 尝试从备份恢复
        backup_path = file_path.with_suffix(backup_suffix)
        if backup_path.exists():
            logger.info(f"尝试从备份文件{backup_path}恢复")
            if AtomicWriter._verify_file_hash(backup_path):
                try:
                    with open(backup_path, 'r', encoding='utf-8', **kwargs) as f:
                        content = f.read()
                    # 恢复主文件
                    AtomicWriter.write_text(file_path, content, **kwargs)
                    return content
                except Exception as e:
                    logger.error(f"读取备份文件{backup_path}失败：{e}")

        raise RuntimeError(f"无法读取文件{file_path}，所有备份均无效")

    @staticmethod
    def read_csv(file_path: Union[str, Path], backup_suffix: str = '.bak', **kwargs) -> pd.DataFrame:
        """读取CSV文件，校验哈希，失败则使用备份
        Args:
            file_path: 目标文件路径
            backup_suffix: 备份文件后缀，或者备份文件路径模式
        Returns:
            读取的DataFrame
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件{file_path}不存在")

        # 校验哈希
        if AtomicWriter._verify_file_hash(file_path):
            try:
                return pd.read_csv(file_path, **kwargs)
            except Exception as e:
                logger.warning(f"读取文件{file_path}失败：{e}，尝试使用备份")

        # 尝试从备份恢复
        backup_path = file_path.with_suffix(backup_suffix)
        if backup_path.exists():
            logger.info(f"尝试从备份文件{backup_path}恢复")
            if AtomicWriter._verify_file_hash(backup_path):
                try:
                    df = pd.read_csv(backup_path, **kwargs)
                    # 恢复主文件
                    AtomicWriter.write_csv(file_path, df, **kwargs)
                    return df
                except Exception as e:
                    logger.error(f"读取备份文件{backup_path}失败：{e}")

        raise RuntimeError(f"无法读取文件{file_path}，所有备份均无效")

    @staticmethod
    def clean_old_backups(directory: Union[str, Path], file_pattern: str, days: int = 30) -> None:
        """清理指定目录下超过指定天数的备份文件
        Args:
            directory: 目标目录
            file_pattern: 文件名匹配模式，例如"state_backup_*.json"、"daily_report_*.json"
            days: 保留天数，默认30天
        """
        directory = Path(directory)
        if not directory.exists():
            return

        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0

        try:
            for file_path in directory.glob(file_pattern):
                if not file_path.is_file():
                    continue

                try:
                    # 获取文件修改时间
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff_date:
                        # 删除文件和对应的哈希文件
                        file_path.unlink(missing_ok=True)
                        hash_path = file_path.with_suffix(f'{file_path.suffix}.hash')
                        hash_path.unlink(missing_ok=True)
                        deleted_count += 1
                except Exception as e:
                    logger.warning(f"删除旧备份文件{file_path}失败：{e}")

            if deleted_count > 0:
                logger.info(f"清理了{deleted_count}个超过{days}天的旧备份文件")
        except Exception as e:
            logger.error(f"清理旧备份文件失败：{e}")
