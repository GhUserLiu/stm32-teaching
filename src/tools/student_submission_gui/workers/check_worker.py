#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
学生端自检工作线程
Self-Check Worker Thread

在后台线程执行「构建提交 → 校验 → 评分」，避免阻塞 GUI。
镜像教师端 workers.grading_worker 的信号设计；单份提交故更简：
无班级循环、无 ObservableFacade，一次性 SelfChecker.run。

注意：
- 取消为「尽力而为」：标志位仅在阶段切换处检查；后台 make 编译一旦启动
  无法立即中断，会运行至结束，但结果会被丢弃（不应用、不跳转）。
- 临时解压目录不在工作线程里清理——交由 GUI 侧在结果应用/新一轮/关闭时
  统一清理，保证结果展示期间 source_path 仍有效。
"""

from pathlib import Path
from typing import Optional

from ..qt_compat import QThread, pyqtSignal

from tools.auto_grading.config import AutoGradingConfig
from tools.auto_grading.submission_validator import detect_report_format
from tools.student_submission_gui.self_checker import SelfChecker, SelfCheckResult
from tools.student_submission_gui.submission_state import shared
from tools.student_submission_gui.runtime import bundle_root


# 报告体积护栏：超过此大小直接拒绝，避免一次性 read() 占用过大内存
MAX_REPORT_BYTES = 50 * 1024 * 1024  # 50 MB


def _diagnose_report_format(report_path: Path) -> str:
    """报告文本提取为空时，按真实格式给出可操作提示（复用 detect_report_format）。

    把「旧版 .doc / RTF / PDF 被改名 .docx → python-docx 静默返回空 → 关键词类 0 分」
    这类陷阱转成清晰的诊断与修正指引。格式嗅探的单一事实来源是
    submission_validator.detect_report_format，本函数仅负责组织面向用户的句子。
    """
    fmt = detect_report_format(report_path)
    tail = "当前关键词类得分将计 0。"
    if fmt == "doc":
        ext_note = "但扩展名是 .docx，" if report_path.suffix.lower() == ".docx" else ""
        return (f"该文件实为旧版 Word .doc（97-2003 OLE 格式），{ext_note}python-docx 无法解析。"
                "请在 Word 中『另存为 → Word 文档(.docx)』后重新选择。" + tail)
    if fmt == "pdf":
        return "该文件实为 PDF（非 .docx），无法提取文本；请导出/另存为 .docx 后重选。" + tail
    if fmt == "rtf":
        return "该文件实为 RTF（非 .docx），请在 Word 中另存为 .docx 后重选。" + tail
    if fmt == "docx":
        return ("docx 结构异常（可能损坏或缺少 word/document.xml），请用 Word 重新另存为 .docx。" + tail)
    return "报告文本为空或无法解析（未知格式），建议提交真正的 .docx 源文件。" + tail


class CheckWorker(QThread):
    """自检工作线程（单份提交）。"""

    # 阶段信号
    stage_started = pyqtSignal(str, str)        # (stage_id, stage_name)
    stage_progress = pyqtSignal(str, int, int)  # (stage_id, current, total)
    stage_completed = pyqtSignal(str)           # (stage_id)
    log_message = pyqtSignal(str)               # (message)
    # 结果信号
    result_ready = pyqtSignal(object)           # SelfCheckResult 成功
    cancelled = pyqtSignal()                    # 已取消（结果被丢弃）
    failed = pyqtSignal(str)                    # 错误信息
    finished_run = pyqtSignal()                 # 总是最后发，用于恢复按钮

    def __init__(self, config: Optional[AutoGradingConfig] = None):
        super().__init__()
        self.config = config or AutoGradingConfig(project_root=bundle_root())
        self._checker = SelfChecker(self.config)
        self._cancelled = False

    def run(self):
        s = shared().state()
        try:
            self.log_message.emit("=" * 60)
            self.log_message.emit("开始作业自检与自评")
            self.log_message.emit("=" * 60)

            if not s.report_path:
                self.failed.emit("未选择实验报告文件")
                return

            # 体积护栏：避免读取超大报告造成长时间内存占用 / UI 卡顿
            try:
                size = Path(s.report_path).stat().st_size
            except OSError as e:
                self.failed.emit(f"无法读取报告文件：{e}")
                return
            if size > MAX_REPORT_BYTES:
                self.failed.emit(
                    f"报告文件过大（{size / 1024 / 1024:.0f} MB，上限 {MAX_REPORT_BYTES // 1024 // 1024} MB），"
                    "请压缩图片或拆分后再试。"
                )
                return

            # 阶段1：读取与构建
            self.stage_started.emit("build", "读取报告与源码")
            self.stage_progress.emit("build", 1, 3)
            self.log_message.emit(f"报告：{Path(s.report_path).name}")
            self.log_message.emit(
                f"源码：{Path(s.source_path).name if s.source_path else '（未提供）'}"
            )

            # 阶段2：校验 + 评分
            self.stage_progress.emit("build", 2, 3)
            self.stage_started.emit("grade", "检测与评分")
            if self._cancelled:
                self.cancelled.emit()
                return

            try:
                result: SelfCheckResult = self._checker.run(
                    Path(s.report_path),
                    Path(s.source_path) if s.source_path else None,
                    s.identity,
                    s.experiment_code,
                )
            except Exception:
                # SelfChecker.run 异常时已自行清理其 tempdir；这里直接向上抛
                raise

            # 运行期间若被取消：丢弃结果（不应用、不跳转），并清理 tempdir
            if self._cancelled:
                self.log_message.emit("已取消，结果未应用")
                SelfChecker.cleanup(result.temp_dirs)
                self.cancelled.emit()
                return

            # 非致命降级提示（如源码包无法解压已忽略）
            for w in result.warnings:
                self.log_message.emit(f"⚠ {w}")

            # 报告文本为空：嗅探真实格式并给出可操作提示（常见陷阱：旧版 .doc/RTF/PDF 被改名 .docx）
            if not result.submission.report_text:
                self.log_message.emit("⚠ " + _diagnose_report_format(Path(s.report_path)))

            g = result.grading
            self.stage_progress.emit("grade", 3, 3)
            self.stage_completed.emit("grade")
            self.log_message.emit(
                f"完成：{g.total_score:.1f}/{g.max_score:.1f}"
                f"（加分 {g.bonus_total:.0f}）等级 {g.grade}"
            )
            v = result.validation
            if v:
                self.log_message.emit(
                    f"检测：{'通过' if v.passed else '存在问题'}，"
                    f"错误 {v.error_count} / 警告 {v.warning_count}"
                )

            self.result_ready.emit(result)

        except Exception as e:
            self.log_message.emit(f"自检失败：{e}")
            self.failed.emit(str(e))
        finally:
            # 总是通知面板本轮结束（恢复按钮）。tempdir 不在此清理（交 GUI 侧）。
            self.finished_run.emit()

    def cancel(self):
        """请求取消（尽力而为）。

        阶段切换处检查标志；后台 make 编译一旦启动无法立即中断，会运行至结束，
        但其结果会被丢弃。
        """
        self._cancelled = True
        self.log_message.emit("正在取消…")


class PackageWorker(QThread):
    """打包提交工作线程。

    自检通过后，若格式合规，生成规范提交 zip（拷贝源码→flatten→打内层 zip→装外层 zip）。
    放后台线程：源码树可达数千文件/数百 MB，inline 会卡死 GUI。

    闸门 assess_gate 是纯函数、<1ms，GUI 线程已即时跑过给拦截框；这里运行期再复检一次
    作为安全网（source_path 可能在排队期间被清理）。
    """

    done = pyqtSignal(object)        # zip Path（成功）
    blocked = pyqtSignal(list)       # blockers（运行期复检不过）
    failed = pyqtSignal(str)         # 异常信息
    finished_pack = pyqtSignal()     # 总是最后发，用于恢复按钮

    def __init__(self, result, identity, project_root, out_dir=None):
        super().__init__()
        self._args = (result, identity, project_root, out_dir)

    def run(self):
        from tools.student_submission_gui.submission_packager import (
            assess_gate, package_submission, PackagingError,
        )
        result, identity, project_root, out_dir = self._args
        try:
            gate_ok, blockers, _ = assess_gate(result, identity)
            if not gate_ok:
                self.blocked.emit(blockers)
                return
            zip_path = package_submission(result, identity, project_root, out_dir=out_dir)
            self.done.emit(zip_path)
        except PackagingError as e:
            self.blocked.emit([str(e)])
        except Exception as e:
            self.failed.emit(str(e))
        finally:
            self.finished_pack.emit()
