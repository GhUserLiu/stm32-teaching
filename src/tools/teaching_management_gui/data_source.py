#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GUI 共享数据源
Shared Data Source for Teaching Management GUI

集中管理"选中的班级压缩包 + 班级 + 实验 + 学期"，供评分/查重/反馈
三个面板统一取用，避免各面板各自维护输入、路径不一致。

通过模块级单例 shared() 访问；状态变更通过 Qt 信号通知各面板刷新。
"""

from dataclasses import dataclass
from typing import List

from PyQt6.QtCore import QObject, pyqtSignal


@dataclass
class ClassEntry:
    """一个待处理的班级输入。"""
    class_name: str
    experiment_id: str
    zip_path: str


class DataSourceManager(QObject):
    """数据源管理器（单例）。

    持有当前选中的班级条目列表与学期；变更时发射信号，
    供评分/查重/反馈面板刷新各自的"数据源状态条"。
    """

    entries_changed = pyqtSignal()
    semester_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._entries: List[ClassEntry] = []
        self._semester: str = "2026-春季"

    # ---- entries ----
    def entries(self) -> List[ClassEntry]:
        return list(self._entries)

    def set_entries(self, entries: List[ClassEntry]) -> None:
        self._entries = list(entries)
        self.entries_changed.emit()

    def add_entries(self, new_entries: List[ClassEntry]) -> None:
        # 按 zip_path 去重后追加
        existing = {e.zip_path for e in self._entries}
        merged = list(self._entries)
        for e in new_entries:
            if e.zip_path not in existing:
                merged.append(e)
                existing.add(e.zip_path)
        self.set_entries(merged)

    def clear(self) -> None:
        self.set_entries([])

    # ---- semester ----
    def semester(self) -> str:
        return self._semester

    def set_semester(self, semester: str) -> None:
        semester = (semester or "").strip() or "2026-春季"
        if semester == self._semester:
            return
        self._semester = semester
        self.semester_changed.emit(semester)


# ---- 模块级单例（惰性创建，确保在 QApplication 之后构造 QObject）----
_singleton: "DataSourceManager | None" = None


def shared() -> DataSourceManager:
    """获取共享数据源管理器单例。"""
    global _singleton
    if _singleton is None:
        _singleton = DataSourceManager()
    return _singleton
