# -*- coding: utf-8 -*-
"""
原子写入工具类，避免写入过程中程序崩溃导致文件损坏
"""
import json
import csv
from pathlib import Path
import pandas as pd
from typing import Any, Dict, List, Optional, Union

class AtomicWriter:
    """原子写入工具类，支持JSON、CSV、普通文本文件"""

    @staticmethod
    def write_json(file_path: Union[str, Path], data: Any, ensure_ascii: bool = False, indent: int = 2, **kwargs) -> None:
        """原子写入JSON文件"""
        file_path = Path(file_path)
        temp_path = file_path.with_suffix(f'{file_path.suffix}.tmp')

        try:
            # 先写入临时文件
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent, **kwargs)
            # 原子替换
            temp_path.replace(file_path)
        finally:
            # 清理临时文件
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

    @staticmethod
    def write_csv(file_path: Union[str, Path], df: pd.DataFrame, index: bool = False, encoding: str = 'utf-8-sig', **kwargs) -> None:
        """原子写入CSV文件"""
        file_path = Path(file_path)
        temp_path = file_path.with_suffix(f'{file_path.suffix}.tmp')

        try:
            df.to_csv(temp_path, index=index, encoding=encoding, **kwargs)
            temp_path.replace(file_path)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

    @staticmethod
    def write_text(file_path: Union[str, Path], content: str, encoding: str = 'utf-8', **kwargs) -> None:
        """原子写入普通文本文件"""
        file_path = Path(file_path)
        temp_path = file_path.with_suffix(f'{file_path.suffix}.tmp')

        try:
            with open(temp_path, 'w', encoding=encoding, **kwargs) as f:
                f.write(content)
            temp_path.replace(file_path)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
