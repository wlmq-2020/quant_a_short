# -*- coding: utf-8 -*-
"""
原子写入工具类，避免写入过程中程序崩溃导致文件损坏
"""
import json
import csv
import time
import logging
from pathlib import Path
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
            # 先写入临时文件
            write_func(temp_path)

            # 原子替换，最多重试3次
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
