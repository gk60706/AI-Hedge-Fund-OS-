"""跨进程文件锁。

V3.9.3 的进化历史是 append-only JSONL。单进程内已有 ``threading.Lock``，
但多个实验进程同时写同一文件会互相覆盖或写出半行。这里提供一个
基于操作系统 advisory lock 的轻量互斥：

- Windows: ``msvcrt.locking``（字节区间锁）
- POSIX: ``fcntl.flock``

用法::

    with FileLock(history_path):
        ...

锁文件是目标文件同目录的 ``<name>.lock`` 侧车文件，内容只有 1 个填充
字节；锁随进程退出自动释放，残留的锁文件不影响后续加锁。
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from types import TracebackType
from typing import Optional, Type

__all__ = [
    "FileLock",
    "FileLockError",
    "FileLockTimeoutError",
]

if os.name == "nt":  # pragma: no cover - 平台分支
    import msvcrt
else:  # pragma: no cover - 平台分支
    import fcntl


class FileLockError(RuntimeError):
    """文件锁操作失败。"""


class FileLockTimeoutError(FileLockError):
    """在给定时间内没有拿到文件锁。"""


class FileLock:
    """目标文件旁的跨进程排他锁。"""

    def __init__(
        self,
        target: str | Path,
        *,
        timeout: Optional[float] = 10.0,
        poll_interval: float = 0.05,
        suffix: str = ".lock",
    ) -> None:
        target_path = Path(target)
        self.path = target_path.with_name(target_path.name + suffix)
        if timeout is not None and timeout <= 0:
            raise ValueError("timeout must be positive when set")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._handle = None

    # ------------------------------------------------------------------
    # context manager
    # ------------------------------------------------------------------
    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        try:
            self._ensure_lock_byte(handle)
            self._acquire(handle)
        except BaseException:
            handle.close()
            raise
        self._handle = handle
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> bool:
        handle = self._handle
        self._handle = None
        if handle is None:
            return False
        try:
            self._release(handle)
        finally:
            handle.close()
        return False

    # ------------------------------------------------------------------
    # platform primitives
    # ------------------------------------------------------------------
    @staticmethod
    def _ensure_lock_byte(handle) -> None:
        """Windows 的字节区间锁要求文件至少 1 字节。"""
        if os.fstat(handle.fileno()).st_size == 0:
            handle.seek(0)
            handle.write(b"\0")
            handle.flush()

    def _acquire(self, handle) -> None:
        deadline = (
            None
            if self.timeout is None
            else time.monotonic() + self.timeout
        )
        while True:
            handle.seek(0)
            try:
                if os.name == "nt":  # pragma: no cover - 平台分支
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:  # pragma: no cover - 平台分支
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except OSError as exc:
                if deadline is not None and time.monotonic() >= deadline:
                    raise FileLockTimeoutError(
                        f"Could not acquire file lock {self.path} "
                        f"within {self.timeout}s"
                    ) from exc
                time.sleep(self.poll_interval)

    def _release(self, handle) -> None:
        try:
            if os.name == "nt":  # pragma: no cover - 平台分支
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:  # pragma: no cover - 平台分支
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError as exc:  # 释放失败不应掩盖业务异常
            raise FileLockError(
                f"Could not release file lock {self.path}: {exc}"
            ) from exc
