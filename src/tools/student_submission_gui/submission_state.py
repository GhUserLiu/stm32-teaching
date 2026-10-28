#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
学生端共享状态
Shared Submission State

集中管理学生端「选中的报告 + 源码 + 身份 + 实验 + 上次自检结果」，
供「提交作业 / 检测过程 / 反馈与改进」三个面板统一取用。

通过模块级单例 shared() 访问；状态变更通过 Qt 信号通知各面板刷新。
镜像教师端 tools.teaching_management_gui.data_source 的设计。
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from .qt_compat import QObject, pyqtSignal

from .id_card import StudentIdentity


class SourceKind(str, Enum):
    """源代码输入类型。"""
    NONE = "none"
    DIRECTORY = "directory"
    ZIP = "zip"
    SEVEN_ZIP = "7z"


@dataclass
class SubmissionState:
    """学生端当前状态。"""
    report_path: Optional[Path] = None
    source_path: Optional[Path] = None
    source_kind: SourceKind = SourceKind.NONE
    identity: StudentIdentity = field(default_factory=StudentIdentity)
    experiment_code: str = ""           # 如 "07-car-gear"
    last_result: object = None          # SelfCheckResult 缓存，便于面板间切换


class SubmissionStateManager(QObject):
    """状态管理器（单例）。

    持有当前选中的报告/源码/身份/实验及上次结果；变更时发射 state_changed，
    供各面板刷新。
    """

    state_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._state = SubmissionState()

    def state(self) -> SubmissionState:
        return self._state

    # 改变这些字段意味着「输入已变更」，必须作废上次自检结果（last_result）：
    # 否则面板会展示与当前输入不符的旧分数/旧源码状态，打包也会基于旧源码
    # 产出与最终版本不符的 zip（外层命新名、内层装旧源码）。
    _RESULT_AFFECTING = frozenset({
        "report_path", "source_path", "source_kind", "identity", "experiment_code",
    })

    def update(self, **kwargs) -> None:
        """合并更新字段；仅当值真正变化时发射信号。

        输入类字段（报告/源码/身份/实验）变化时，自动作废上次自检结果。
        ``last_result`` 的赋值走 ``set_result()``；直接 ``update(last_result=...)``
        也可，但不触发作废逻辑。
        """
        changed = False
        invalidate = False
        for k, v in kwargs.items():
            if not hasattr(self._state, k):
                continue
            if getattr(self._state, k) != v:
                setattr(self._state, k, v)
                changed = True
                if k in self._RESULT_AFFECTING:
                    invalidate = True
        if invalidate and self._state.last_result is not None:
            self._state.last_result = None
            changed = True
        if changed:
            self.state_changed.emit()

    def set_result(self, result: object) -> None:
        """缓存最近一次自检结果并通知面板。"""
        self._state.last_result = result
        self.state_changed.emit()

    def is_runnable(self) -> bool:
        """是否满足「开始检测」条件：身份完整 + 已选实验（报告与源码均可选）。

        - 缺源码：丢编译/代码质量反馈
        - 缺报告（模板未发/阶段自检）：只跑代码侧反馈，报告类按缺失计
        - 两者全缺：无意义，不允许开始
        """
        s = self._state
        if not (s.identity.is_complete() and bool(s.experiment_code)):
            return False
        has_report = bool(s.report_path and Path(s.report_path).exists())
        has_source = bool(s.source_path and Path(s.source_path).exists())
        return has_report or has_source

    def clear(self) -> None:
        self._state = SubmissionState()
        self.state_changed.emit()


# ---- 模块级单例（惰性创建，确保在 QApplication 之后构造 QObject）----
_singleton: "SubmissionStateManager | None" = None


def shared() -> SubmissionStateManager:
    """获取共享状态管理器单例。"""
    global _singleton
    if _singleton is None:
        _singleton = SubmissionStateManager()
    return _singleton
