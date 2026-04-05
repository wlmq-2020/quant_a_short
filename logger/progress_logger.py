# -*- coding: utf-8 -*-
"""
进度日志模块
将进度信息保存到文件，支持追加方式
"""
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import json


class ProgressLogger:
    """进度日志记录器"""

    def __init__(self, log_dir: Path, task_name: str = "default"):
        """
        初始化进度日志记录器

        参数:
            log_dir: 日志目录
            task_name: 任务名称，用于生成日志文件名
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 始终使用同一个文件，追加写入
        self.log_file = self.log_dir / f"progress_{task_name}.log"
        self.current_task = task_name
        self.start_time = datetime.now()

        # 写入开始标记
        self._write_log({
            "type": "start",
            "task": task_name,
            "timestamp": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
        })

    def _write_log(self, data: Dict[str, Any]):
        """写入一条日志记录"""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
        except Exception:
            pass  # 静默失败，不影响主程序

    def update(self, current: int, total: int, message: str = "", extra: Optional[Dict] = None):
        """
        更新进度

        参数:
            current: 当前进度
            total: 总进度
            message: 进度消息
            extra: 额外信息字典
        """
        now = datetime.now()
        elapsed = (now - self.start_time).total_seconds()

        # 计算百分比和ETA
        percentage = (current / total * 100) if total > 0 else 0
        if current > 0 and total > 0:
            eta_seconds = elapsed / current * (total - current)
            eta = str(int(eta_seconds)) + "s"
        else:
            eta = "N/A"

        log_data = {
            "type": "progress",
            "task": self.current_task,
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "current": current,
            "total": total,
            "percentage": round(percentage, 2),
            "elapsed_seconds": round(elapsed, 2),
            "eta": eta,
            "message": message,
        }
        if extra:
            log_data["extra"] = extra

        self._write_log(log_data)

    def info(self, message: str, extra: Optional[Dict] = None):
        """记录信息消息"""
        log_data = {
            "type": "info",
            "task": self.current_task,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message": message,
        }
        if extra:
            log_data["extra"] = extra
        self._write_log(log_data)

    def warning(self, message: str, extra: Optional[Dict] = None):
        """记录警告消息"""
        log_data = {
            "type": "warning",
            "task": self.current_task,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message": message,
        }
        if extra:
            log_data["extra"] = extra
        self._write_log(log_data)

    def error(self, message: str, extra: Optional[Dict] = None):
        """记录错误消息"""
        log_data = {
            "type": "error",
            "task": self.current_task,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message": message,
        }
        if extra:
            log_data["extra"] = extra
        self._write_log(log_data)

    def finish(self, success: bool = True, message: str = "", extra: Optional[Dict] = None):
        """
        标记任务完成

        参数:
            success: 是否成功
            message: 完成消息
            extra: 额外信息
        """
        now = datetime.now()
        elapsed = (now - self.start_time).total_seconds()

        log_data = {
            "type": "finish",
            "task": self.current_task,
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "success": success,
            "elapsed_seconds": round(elapsed, 2),
            "message": message,
        }
        if extra:
            log_data["extra"] = extra

        self._write_log(log_data)

    def get_log_file(self) -> Path:
        """获取日志文件路径"""
        return self.log_file

    @staticmethod
    def get_latest_progress(log_dir: Path, task_name: Optional[str] = None) -> Optional[Dict]:
        """
        获取最新进度

        参数:
            log_dir: 日志目录
            task_name: 任务名称，None表示获取最新的

        返回:
            最新进度字典，没有则返回None
        """
        log_dir = Path(log_dir)
        if not log_dir.exists():
            return None

        # 查找日志文件（固定文件名）
        log_file = log_dir / f"progress_{task_name}.log" if task_name else None
        if not log_file or not log_file.exists():
            # 如果指定任务没找到，找任意最新的
            log_files = sorted(log_dir.glob("progress_*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
            if not log_files:
                return None
            log_file = log_files[0]

        # 读取最后一条日志
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
                if lines:
                    return json.loads(lines[-1])
        except Exception:
            pass

        return None

    @staticmethod
    def print_progress_summary(log_dir: Path, task_name: Optional[str] = None):
        """
        打印进度摘要

        参数:
            log_dir: 日志目录
            task_name: 任务名称
        """
        progress = ProgressLogger.get_latest_progress(log_dir, task_name)
        if not progress:
            print("没有找到进度日志")
            return

        print("=" * 80)
        print(f"任务: {progress.get('task', 'N/A')}")
        print(f"类型: {progress.get('type', 'N/A')}")
        print(f"时间: {progress.get('timestamp', 'N/A')}")

        if progress.get('type') == 'progress':
            print(f"进度: {progress.get('current', 0)}/{progress.get('total', 0)} "
                  f"({progress.get('percentage', 0)}%)")
            print(f"已用时间: {progress.get('elapsed_seconds', 0)}s")
            print(f"预计剩余: {progress.get('eta', 'N/A')}")
            if progress.get('message'):
                print(f"消息: {progress.get('message')}")

        elif progress.get('type') == 'finish':
            print(f"状态: {'成功' if progress.get('success') else '失败'}")
            print(f"总耗时: {progress.get('elapsed_seconds', 0)}s")
            if progress.get('message'):
                print(f"消息: {progress.get('message')}")

        print("=" * 80)
