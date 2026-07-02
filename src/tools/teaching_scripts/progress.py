# -*- coding: utf-8 -*-
"""
进度追踪与可视化模块
Progress Tracking and Visualization

提供实时进度反馈、ETA计算和彩色输出
"""

import sys
import time
from typing import Callable, Optional, List
from dataclasses import dataclass
from enum import Enum
import threading


class Color(Enum):
    """ANSI颜色代码"""
    RESET = "\033[0m"
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


class Icon(Enum):
    """进度图标"""
    # 进度条字符
    BLOCK_FULL = "█"
    BLOCK_EMPTY = "░"
    BLOCK_MIDDLE = "▒"
    BLOCK_LIGHT = "▓"

    # 状态图标
    PENDING = "○"
    RUNNING = "◐"
    COMPLETED = "●"
    FAILED = "✖"
    SKIPPED = "⊘"

    # 箭头
    ARROW_RIGHT = "→"
    ARROW_DOUBLE = "»"

    # 其他
    CHECK = "✓"
    CROSS = "✗"
    HOURGLASS = "⏳"


@dataclass
class StageProgress:
    """阶段进度"""
    name: str
    current: int
    total: int
    status: str = "pending"
    message: str = ""


class ProgressDisplay:
    """进度显示器"""

    def __init__(self, use_color: bool = True, use_icons: bool = True):
        """
        初始化显示器

        Args:
            use_color: 是否使用彩色输出
            use_icons: 是否使用图标
        """
        self.use_color = use_color and self._supports_color()
        self.use_icons = use_icons
        self.stages: List[StageProgress] = []
        self.current_stage = 0
        self.lock = threading.Lock()

        # 终端宽度
        self.terminal_width = self._get_terminal_width()

    def _supports_color(self) -> bool:
        """检测终端是否支持彩色"""
        # Windows 10+ 支持ANSI
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True
        except (AttributeError, OSError, ctypes.WinError):
            # 非Windows系统通常支持
            return sys.platform != "win32" or "ANSICON" in sys.environ or "WT_SESSION" in sys.environ

    def _get_terminal_width(self) -> int:
        """获取终端宽度"""
        try:
            import shutil
            return shutil.get_terminal_size().columns
        except (OSError, AttributeError):
            return 80

    def add_stage(self, name: str, total: int):
        """添加阶段"""
        with self.lock:
            self.stages.append(StageProgress(name=name, current=0, total=total))

    def update_stage(self, index: int, current: int, status: str = "", message: str = ""):
        """更新阶段进度"""
        with self.lock:
            if 0 <= index < len(self.stages):
                self.stages[index].current = current
                self.stages[index].status = status
                self.stages[index].message = message

    def render(self):
        """渲染进度显示"""
        lines = []

        # 标题行
        lines.append(self._colorize("Progress", Color.CYAN) + ": ")

        # 阶段列表
        for i, stage in enumerate(self.stages):
            # 状态图标
            icon = self._get_status_icon(stage.status)

            # 进度条
            progress = stage.current / stage.total if stage.total > 0 else 0
            bar = self._render_progress_bar(progress, width=20)

            # 状态信息
            info = f"{stage.current}/{stage.total}"

            # 行内容
            line = f"  {icon} {stage.name}: {bar} {info}"

            # 添加消息
            if stage.message:
                available_width = self.terminal_width - len(line) - 5
                if available_width > 10:
                    truncated = stage.message[:available_width] + "..." if len(stage.message) > available_width else stage.message
                    line += f" {self._colorize(truncated, Color.BRIGHT_BLACK)}"

            # 当前阶段高亮
            if i == self.current_stage:
                line = self._colorize(line, Color.BRIGHT_WHITE)

            lines.append(line)

        # 清屏并重绘
        self._clear_and_print("\n".join(lines))

    def _render_progress_bar(self, progress: float, width: int = 20) -> str:
        """渲染进度条"""
        filled = int(width * progress)
        empty = width - filled

        if self.use_icons:
            return (Color.BRIGHT_GREEN.value + Icon.BLOCK_FULL.value * filled +
                    Color.BRIGHT_BLACK.value + Icon.BLOCK_EMPTY.value * empty +
                    Color.RESET.value)
        else:
            return "[" + "=" * filled + " " * empty + "]"

    def _get_status_icon(self, status: str) -> str:
        """获取状态图标"""
        if not self.use_icons:
            return f"[{status[0].upper()}]"

        status_map = {
            "pending": Icon.PENDING.value,
            "running": Icon.RUNNING.value,
            "completed": self._colorize(Icon.COMPLETED.value, Color.BRIGHT_GREEN),
            "failed": self._colorize(Icon.FAILED.value, Color.BRIGHT_RED),
            "skipped": self._colorize(Icon.SKIPPED.value, Color.BRIGHT_BLACK),
        }
        return status_map.get(status, Icon.PENDING.value)

    def _colorize(self, text: str, color: Color) -> str:
        """为文本添加颜色"""
        if not self.use_color:
            return text
        return f"{color.value}{text}{Color.RESET.value}"

    def _clear_and_print(self, text: str):
        """清屏并打印"""
        # 计算需要清除的行数
        lines = text.count('\n') + 2  # +2 for safety

        # 移动光标到顶部
        sys.stdout.write(f"\033[{lines}F")
        sys.stdout.flush()

        # 打印新内容
        sys.stdout.write(text + "\n")
        sys.stdout.flush()


class ProgressBar:
    """简单的进度条"""

    def __init__(
        self,
        total: int,
        description: str = "",
        width: int = 40,
        use_color: bool = True
    ):
        """
        初始化进度条

        Args:
            total: 总数
            description: 描述文本
            width: 进度条宽度
            use_color: 是否使用彩色
        """
        self.total = total
        self.description = description
        self.width = width
        self.use_color = use_color and self._supports_color()
        self.current = 0
        self.start_time = time.time()

    def _supports_color(self) -> bool:
        """检测终端是否支持彩色"""
        return True  # 简化处理

    def update(self, n: int = 1):
        """
        更新进度

        Args:
            n: 增量
        """
        self.current += n
        self.render()

    def set_progress(self, value: int):
        """
        设置进度值

        Args:
            value: 当前进度值
        """
        self.current = value
        self.render()

    def render(self):
        """渲染进度条"""
        progress = self.current / self.total if self.total > 0 else 0

        # 计算ETA
        elapsed = time.time() - self.start_time
        if progress > 0:
            eta = elapsed / progress * (1 - progress)
        else:
            eta = 0

        # 渲染进度条
        filled = int(self.width * progress)
        bar = "█" * filled + "░" * (self.width - filled)

        # 颜色化
        if self.use_color:
            bar = f"\033[92m{bar}\033[0m"

        # 百分比
        percent = f"{progress * 100:.1f}%"

        # ETA格式化
        if eta < 60:
            eta_str = f"{int(eta)}s"
        elif eta < 3600:
            eta_str = f"{int(eta / 60)}m {int(eta % 60)}s"
        else:
            eta_str = f"{int(eta / 3600)}h {int(eta % 3600 / 60)}m"

        # 组合输出
        output = f"\r{self.description}: [{bar}] {percent} ETA: {eta_str}"

        sys.stdout.write(output)
        sys.stdout.flush()

    def finish(self):
        """完成进度条"""
        self.current = self.total
        self.render()
        print()  # 换行


class Spinner:
    """加载动画"""

    def __init__(self, description: str = "", use_color: bool = True):
        """
        初始化加载动画

        Args:
            description: 描述文本
            use_color: 是否使用彩色
        """
        self.description = description
        self.use_color = use_color
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.current_frame = 0
        self.running = False
        self.thread = None

    def _animate(self):
        """动画循环"""
        while self.running:
            frame = self.frames[self.current_frame]
            output = f"\r{frame} {self.description}"
            sys.stdout.write(output)
            sys.stdout.flush()
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            time.sleep(0.1)

    def start(self):
        """启动动画"""
        self.running = True
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()

    def stop(self):
        """停止动画"""
        self.running = False
        if self.thread:
            self.thread.join()
        # 清除动画
        sys.stdout.write("\r" + " " * (len(self.description) + 2) + "\r")
        sys.stdout.flush()

    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.stop()


def create_progress_bar(
    total: int,
    description: str = "",
    width: int = 40
) -> ProgressBar:
    """
    创建进度条（便捷函数）

    Args:
        total: 总数
        description: 描述文本
        width: 进度条宽度

    Returns:
        ProgressBar实例
    """
    return ProgressBar(total, description, width)


def create_spinner(description: str = "") -> Spinner:
    """
    创建加载动画（便捷函数）

    Args:
        description: 描述文本

    Returns:
        Spinner实例
    """
    return Spinner(description)
