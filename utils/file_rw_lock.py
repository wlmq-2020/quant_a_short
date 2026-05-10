# -*- coding: utf-8 -*-
"""
跨进程文件读写锁，兼容Windows和Linux系统
"""
import os
import time
from pathlib import Path
from typing import Optional, Union

class FileRWLock:
    """跨进程读写锁，基于系统级文件锁实现"""

    def __init__(self, file_path: Union[str, Path], timeout: int = 10):
        """
        初始化读写锁
        :param file_path: 需要加锁的文件路径
        :param timeout: 超时时间，默认10秒
        """
        self.file_path = Path(file_path)
        self.lock_path = self.file_path.with_suffix(f'{self.file_path.suffix}.lock')
        self.timeout = timeout
        self._lock_fd: Optional[int] = None
        self._is_locked = False

    def acquire_read(self) -> bool:
        """获取共享读锁，多个进程可同时读取"""
        return self._acquire(shared=True)

    def acquire_write(self) -> bool:
        """获取排他写锁，同一时间仅一个进程可写入"""
        return self._acquire(shared=False)

    def release(self) -> None:
        """释放锁"""
        if self._lock_fd is not None:
            try:
                if os.name == 'nt':
                    import win32file
                    win32file.UnlockFile(self._lock_fd, 0, 0, 0, 0)
                else:
                    import fcntl
                    fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                os.close(self._lock_fd)
            except Exception:
                pass
            finally:
                self._lock_fd = None
                self._is_locked = False
                # 只有当没有其他进程持有锁的时候才删除锁文件
                # 尝试加临时锁判断是否有其他进程持有
                try:
                    temp_fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR)
                    if os.name == 'nt':
                        import win32file
                        import win32con
                        flags = win32con.LOCKFILE_FAIL_IMMEDIATELY | win32con.LOCKFILE_EXCLUSIVE_LOCK
                        overlapped = win32file.OVERLAPPED()
                        try:
                            win32file.LockFileEx(temp_fd, flags, 0, 0, 0, overlapped)
                            # 可以加锁，说明没有其他进程持有，可以删除
                            self.lock_path.unlink(missing_ok=True)
                            win32file.UnlockFile(temp_fd, 0, 0, 0, 0)
                        except Exception:
                            pass
                    else:
                        import fcntl
                        try:
                            fcntl.flock(temp_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            # 可以加锁，说明没有其他进程持有，可以删除
                            self.lock_path.unlink(missing_ok=True)
                            fcntl.flock(temp_fd, fcntl.LOCK_UN)
                        except Exception:
                            pass
                    os.close(temp_fd)
                except Exception:
                    pass

    def _acquire(self, shared: bool) -> bool:
        """内部获取锁方法"""
        start_time = time.time()
        lock_fd = None
        while time.time() - start_time < self.timeout:
            try:
                # 打开锁文件
                lock_fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR)
                if os.name == 'nt':
                    import win32file
                    import win32con
                    flags = win32con.LOCKFILE_FAIL_IMMEDIATELY
                    if not shared:
                        flags |= win32con.LOCKFILE_EXCLUSIVE_LOCK
                    overlapped = win32file.OVERLAPPED()
                    try:
                        win32file.LockFileEx(lock_fd, flags, 0, 0, 0, overlapped)
                        self._lock_fd = lock_fd
                        self._is_locked = True
                        return True
                    except:
                        os.close(lock_fd)
                        lock_fd = None
                else:
                    import fcntl
                    flags = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
                    flags |= fcntl.LOCK_NB
                    try:
                        fcntl.flock(lock_fd, flags)
                        self._lock_fd = lock_fd
                        self._is_locked = True
                        return True
                    except:
                        os.close(lock_fd)
                        lock_fd = None
            except Exception:
                if lock_fd is not None:
                    try:
                        os.close(lock_fd)
                    except Exception:
                        pass
                    lock_fd = None
            # 等待100ms重试
            time.sleep(0.1)
        return False

    def __enter__(self):
        """上下文管理器默认获取写锁"""
        if not self.acquire_write():
            raise TimeoutError(f"获取文件写锁超时，超时时间：{self.timeout}秒，文件：{self.lock_path}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出时释放锁"""
        self.release()

    def acquire_read(self):
        """获取共享读锁，多个进程可同时读取"""
        if not self._acquire(shared=True):
            raise TimeoutError(f"获取文件读锁超时，超时时间：{self.timeout}秒，文件：{self.lock_path}")
        return self

    def acquire_write(self):
        """获取排他写锁，同一时间仅一个进程可写入"""
        if not self._acquire(shared=False):
            raise TimeoutError(f"获取文件写锁超时，超时时间：{self.timeout}秒，文件：{self.lock_path}")
        return self
