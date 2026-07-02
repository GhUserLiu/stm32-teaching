#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
学生端 · 作业自检与自评系统 GUI 主入口
Main Entry Point for Student Self-Check & Self-Grade GUI

启动：PYTHONPATH=src python -m tools.student_submission_gui.main
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from tools.student_submission_gui.qt_compat import QApplication, Qt, exec_app

from tools.student_submission_gui.ui.main_window import MainWindow


def main():
    """主函数。"""
    # 必须在创建 QApplication 之前设置高 DPI 属性
    # setHighDpiScaleFactorRoundingPolicy 为 Qt5.14+/Qt6 API；PyQt5 早期版本或
    # 无此方法/枚举，失败时静默回退到默认 Round，不影响功能。
    if hasattr(QApplication, "setHighDpiScaleFactorRoundingPolicy"):
        try:
            QApplication.setHighDpiScaleFactorRoundingPolicy(
                Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
            )
        except (AttributeError, TypeError):
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("学生端作业自检与自评")
    app.setOrganizationName("STM32F407 Teaching")

    # Windows 平台：设置进程 DPI 感知
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass

    window = MainWindow()
    window.show()
    sys.exit(exec_app(app))


if __name__ == "__main__":
    main()
