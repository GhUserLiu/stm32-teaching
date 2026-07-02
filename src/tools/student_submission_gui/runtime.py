#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
冻结态（PyInstaller 打包）运行时路径解析
Runtime path resolver for frozen (PyInstaller) mode

本应用的路径逻辑原本假设「在仓库根运行」：AutoGradingConfig.project_root = cwd，
data/rubrics/rubric.json 相对仓库根定位。打包成单文件 exe 后该假设失效——
cwd 是用户启动 exe 的任意目录，而只读资源（rubric、config）在解包目录里。

本模块提供两个根：
- bundle_root()：只读资源根（data/ 在此之下）
    · 未冻结：cwd（保留开发态行为）
    · 冻结 onefile：sys._MEIPASS（PyInstaller 临时解压目录）
    · 冻结 onedir：exe 同级目录
- writable_root()：可写输出根（outputs/ 在此之下）
    · 未冻结：cwd
    · 冻结：用户主目录下的固定文件夹（可预测、可写、跨次运行保留）
"""

import sys
from pathlib import Path

APP_DIR_NAME = "STM32学生自检"


def is_frozen() -> bool:
    """是否运行在 PyInstaller 冻结态。"""
    return getattr(sys, "frozen", False)


def bundle_root() -> Path:
    """只读资源根目录（data/、rubric.json 在此之下）。"""
    if is_frozen():
        # onefile：PyInstaller 把资源解压到 sys._MEIPASS
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        # onedir：资源就铺在 exe 同级目录
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def writable_root() -> Path:
    """可写输出根目录（outputs/student_self_check/ 在此之下）。"""
    if is_frozen():
        # 冻结态下 exe 可能位于只读/任意位置（Downloads、桌面、临时目录），
        # 统一回退到用户主目录下的固定文件夹：可预测、可写、跨次运行保留。
        home_dir = Path.home() / APP_DIR_NAME
        home_dir.mkdir(parents=True, exist_ok=True)
        return home_dir
    return Path.cwd()
