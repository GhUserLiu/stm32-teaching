#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
教学管理系统GUI主入口
Main Entry Point for Teaching Management System GUI
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from tools.teaching_management_gui.ui.main_window import MainWindow


def main():
    """主函数"""
    # 关键修复：在创建QApplication之前设置高DPI属性
    # 这必须在QApplication实例化之前完成
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("教学管理系统")
    app.setOrganizationName("STM32F407 Teaching")

    # Windows平台特定设置：禁用自动窗口管理功能
    # 这可以防止窗口在拖动时自动吸附和调整大小
    if sys.platform == 'win32':
        import ctypes
        # 禁用Windows的窗口动画和过渡效果
        try:
            # 设置进程DPI感知
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            # 老版/无头 Windows 无 shcore.SetProcessDpiAwareness，安全降级
            pass

    # 创建主窗口
    window = MainWindow()
    window.show()

    # 运行应用
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
