#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批阅工作线程（Qt 胶水层）
Grading Worker Thread -- Qt glue only

P2 之后管线编排逻辑上提到 core/services/grading_service.py（Qt-free，
可独立单测）；本模块只负责：
1. 把 Qt 信号适配成 ProgressCallbacks；
2. 把线程生命周期（启动/取消/完成/失败信号）映射到 service 调用。

ObservableFacade 保留为兼容适配器：既有单测（test_grading_failures /
test_grading_resume）经 object.__new__ 注入桩门面并直接调用其
run_full_pipeline，接口必须保持不变。
"""

import threading
from pathlib import Path
from typing import Optional, Set

from PyQt6.QtCore import QThread, pyqtSignal

from tools.auto_grading import AutoGradingFacade, AutoGradingConfig
from tools.auto_grading.facade import PipelineResult

from core.services.grading_service import (
    GradingService,
    ProgressCallbacks,
    _LogTee,          # re-export: tests/unit/test_log_tee.py imports it from here
    build_auto_grading_config,
)

__all__ = ["GradingWorker", "ObservableFacade", "_LogTee"]


class GradingWorker(QThread):
    """批阅工作线程（批量：遍历多个班级条目）"""

    # 定义信号
    stage_started = pyqtSignal(str, str)  # (stage_id, stage_name)
    stage_progress = pyqtSignal(str, int, int)  # (stage_id, current, total)
    stage_completed = pyqtSignal(str)  # (stage_id)
    log_message = pyqtSignal(str)  # (message)
    grading_completed = pyqtSignal(object, object)  # (list[GradingResult], list[失败dict])，跨班级合并
    grading_cancelled = pyqtSignal()  # 取消：不发部分结果，避免被面板当成"完成"
    grading_failed = pyqtSignal(str)  # (error_message)

    def __init__(
        self,
        entries,
        semester: str = "2026-春季",
        config: Optional[AutoGradingConfig] = None,
        resume: bool = False,
    ):
        """
        初始化批量批阅工作线程

        Args:
            entries: ClassEntry 列表（班级/实验/压缩包）
            semester: 学期（决定产物路径）
            config: 配置对象；未提供时经统一配置层（P1 schemas）桥接构造，
                值与旧默认 1:1（P1 parity 已验证）
        """
        super().__init__()
        self.entries = list(entries)
        self.semester = semester
        if config is None:
            config = build_auto_grading_config(semester=semester)
        self.config = config
        self.config.semester = semester
        self.resume = resume   # Phase B: True 时跳过各班 checkpoint 里已完成的学号
        self.is_cancelled = False
        # 取消事件：cancel() 置位后，引擎内 build_checker 正在跑的 make 编译会在
        # 下一次轮询（~0.2s）被 kill，而不必等它跑完或超时。
        self._cancel_event = threading.Event()

    def run(self):
        """对每个班级条目依次执行批阅，合并所有 GradingResult（逻辑在 GradingService）。"""
        try:
            service = GradingService(self.config, ProgressCallbacks(
                stage_started=self.stage_started.emit,
                stage_progress=self.stage_progress.emit,
                stage_completed=self.stage_completed.emit,
                log=self.log_message.emit,
                is_cancelled=lambda: self.is_cancelled,
                cancel_event=self._cancel_event,
            ))
            all_results, all_failures = service.run_batch(
                self.entries, resume=self.resume)

            # 取消时不发 grading_completed（避免部分结果被当成"完成"），改发取消信号
            if self.is_cancelled:
                self.log_message.emit(f"批阅已取消（已丢弃 {len(all_results)} 条部分结果）")
                self.grading_cancelled.emit()
            else:
                self.grading_completed.emit(all_results, all_failures)

        except Exception as e:
            self.grading_failed.emit(str(e))

    def cancel(self):
        """取消批阅"""
        self.is_cancelled = True
        self._cancel_event.set()   # 通知引擎内 build_checker kill 当前 make 子进程
        self.log_message.emit("正在取消...")


class ObservableFacade:
    """可观察的门面（兼容适配器，用于向GUI发送信号）。

    P2 起管线编排在 core.services.grading_service.GradingService；本类仅为
    既有调用方/单测保留原构造签名与 run_full_pipeline 接口。经
    object.__new__ 装配的实例同样可用（属性在调用时读取）。
    """

    def __init__(
        self,
        config: AutoGradingConfig,
        stage_started_sig,
        stage_progress_sig,
        stage_completed_sig,
        log_message_sig,
        is_cancelled_func,
        cancel_event: Optional[threading.Event] = None,
    ):
        """
        初始化

        Args:
            config: 配置对象
            stage_started_sig: 阶段开始信号
            stage_progress_sig: 阶段进度信号
            stage_completed_sig: 阶段完成信号
            log_message_sig: 日志消息信号
            is_cancelled_func: 检查是否取消的函数
            cancel_event: 取消事件（注入引擎 build_checker，使 make 编译可被中断）
        """
        self.config = config
        self.stage_started = stage_started_sig
        self.stage_progress = stage_progress_sig
        self.stage_completed = stage_completed_sig
        self.log_message = log_message_sig
        self.is_cancelled = is_cancelled_func
        self._cancel_event = cancel_event

        # 创建实际的门面
        self.facade = AutoGradingFacade(config)

    def run_full_pipeline(
        self,
        class_zip: Path,
        class_name: str,
        experiment_id: str,
        skip_organization: bool = False,
        resume_completed_ids: Optional[Set[str]] = None,
    ) -> PipelineResult:
        """运行完整流水线（带信号通知）——委托给 GradingService.run_class"""
        service = GradingService(
            config=self.config,
            callbacks=ProgressCallbacks(
                stage_started=self.stage_started.emit,
                stage_progress=self.stage_progress.emit,
                stage_completed=self.stage_completed.emit,
                log=self.log_message.emit,
                is_cancelled=self.is_cancelled,
                cancel_event=self._cancel_event,
            ),
            facade=self.facade,
        )
        return service.run_class(
            class_zip, class_name, experiment_id,
            skip_organization, resume_completed_ids,
        )
