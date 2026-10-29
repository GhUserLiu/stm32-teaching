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


def _seed_portable_data():
    """打包 exe 首启：把 _internal 内的种子数据（config/ 与 data/）拷到 exe 旁。

    便携式布局：exe 根目录的 config/、data/ 为工作副本（可编辑、可写入成绩），
    升级时替换整个文件夹即可保留用户数据。源码运行时是空操作。
    """
    import sys as _sys
    if not getattr(_sys, "frozen", False):
        return
    import shutil
    exe_root = Path(_sys.executable).resolve().parent
    internal = exe_root / "_internal"
    if not internal.exists():
        return
    for name in ("config", "data"):
        src = internal / name
        dst = exe_root / name
        if not src.exists():
            continue
        if not dst.exists():
            shutil.copytree(src, dst)
        else:
            # 逐文件补齐（不覆盖已有，保护教师已改的模板/已产生的成绩）
            for p in src.rglob("*"):
                if p.is_file():
                    rel = p.relative_to(src)
                    target = dst / rel
                    if not target.exists():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(p, target)


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
    _seed_portable_data()
    main()
