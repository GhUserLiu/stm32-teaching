#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
「我的作业」面板
Files Panel — 输入入口

选报告 + 选源码 + 身份 + 实验 + 「开始检测与自评」。
身份从文件名自动回填（匹配则填，不匹配留空手填）。
"""

from datetime import datetime
from pathlib import Path

from ...qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QLineEdit, QComboBox,
    QFileDialog, QProgressBar, QPlainTextEdit, QMessageBox, QFrame,
    QFont, Qt,
)

from tools.student_submission_gui.id_card import StudentIdentity
from tools.student_submission_gui.submission_state import shared, SourceKind
from tools.student_submission_gui.experiments import experiment_choices
from tools.student_submission_gui.self_checker import SelfChecker
from tools.student_submission_gui.workers.check_worker import CheckWorker


def _has_py7zr() -> bool:
    """当前环境是否可导入 py7zr（解压 .7z 所需，打包 exe 已内置，源码直跑可能缺）。"""
    try:
        import importlib.util
        return importlib.util.find_spec("py7zr") is not None
    except Exception:
        return False


class FilesPanel(QWidget):
    """「我的作业」面板。"""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.worker = None
        self._live_tempdirs = []          # 当前展示结果持有的临时解压目录
        self._suppress_identity_signal = False
        self.setup_ui()
        shared().state_changed.connect(self._refresh)
        self._refresh()

    # ---------------- UI ----------------
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(self._create_info_banner())
        layout.addWidget(self._create_files_group())
        layout.addWidget(self._create_identity_group())
        layout.addWidget(self._create_action_group())
        layout.addWidget(self._create_progress_group(), 1)

    def _create_info_banner(self):
        box = QGroupBox("使用说明")
        v = QVBoxLayout()
        msg = QLabel(
            "1) 选择实验报告（.docx 推荐）与源代码（.zip / .7z）；\n"
            "2) 填写班级/学号/姓名（文件名规范时会自动回填）；\n"
            "3) 选择实验，点「开始检测与自评」。\n"
            "说明：编译检查需 make + arm-none-eabi-gcc；未安装时编译项记 0 分但状态为「已跳过」，不代表代码无法编译。\n"
            "⚠ 源码工程须含顶层 Makefile（用 CubeMX → Project Manager → Toolchain/IDE 选 Makefile 生成）；"
            "纯 Keil(.uvprojx) 工程机器编译计 0 分。"
        )
        msg.setWordWrap(True)
        msg.setStyleSheet("color: #555;")
        v.addWidget(msg)
        box.setLayout(v)
        return box

    def _create_files_group(self):
        box = QGroupBox("一、文件选择")
        grid = QGridLayout()

        # 报告
        grid.addWidget(QLabel("实验报告："), 0, 0)
        self.report_edit = QLineEdit()
        self.report_edit.setReadOnly(True)
        self.report_edit.setPlaceholderText("必选 · 推荐 .docx")
        grid.addWidget(self.report_edit, 0, 1)
        rep_btn = QPushButton("选择报告…")
        rep_btn.clicked.connect(self._pick_report)
        grid.addWidget(rep_btn, 0, 2)
        self.report_badge = QLabel("")
        grid.addWidget(self.report_badge, 1, 1)
        # PDF 横幅
        self.pdf_banner = QLabel(
            "⚠ PDF 报告无法自动提取文本，建议另存为 .docx 后再自检；当前结果仅供参考。"
        )
        self.pdf_banner.setWordWrap(True)
        self.pdf_banner.setStyleSheet("color: #c0392b; background:#fdecea; padding:6px; border-radius:4px;")
        self.pdf_banner.hide()
        grid.addWidget(self.pdf_banner, 2, 1)

        # 源码
        grid.addWidget(QLabel("源代码："), 3, 0)
        self.source_edit = QLineEdit()
        self.source_edit.setReadOnly(True)
        self.source_edit.setPlaceholderText("可选 · .zip / .7z 压缩包（影响编译/代码质量分）")
        grid.addWidget(self.source_edit, 3, 1)
        src_row = QHBoxLayout()
        zip_btn = QPushButton("选源码包…")
        zip_btn.clicked.connect(self._pick_source)
        clr_btn = QPushButton("清除")
        clr_btn.clicked.connect(self._clear_source)
        src_row.addWidget(zip_btn)
        src_row.addWidget(clr_btn)
        w = QWidget(); w.setLayout(src_row)
        grid.addWidget(w, 3, 2)
        self.source_badge = QLabel("")
        grid.addWidget(self.source_badge, 4, 1)
        # 源码工程状态横幅（自检后按 source_state 显示，如纯 Keil → 编译计 0 提示）
        self.source_state_banner = QLabel("")
        self.source_state_banner.setWordWrap(True)
        self.source_state_banner.setStyleSheet(
            "color:#c0392b; background:#fdecea; padding:6px; border-radius:4px;"
        )
        self.source_state_banner.hide()
        grid.addWidget(self.source_state_banner, 5, 1)

        grid.setColumnStretch(1, 1)
        box.setLayout(grid)
        return box

    def _create_identity_group(self):
        box = QGroupBox("二、学生信息（自动回填，可修改）")
        form = QFormLayout()
        self.class_edit = QLineEdit()
        self.class_edit.setPlaceholderText("如 汽服2302B班")
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("11 位学号")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("2~4 字姓名")

        for ed in (self.class_edit, self.id_edit, self.name_edit):
            ed.editingFinished.connect(self._on_identity_edited)

        form.addRow("班级：", self.class_edit)
        form.addRow("学号：", self.id_edit)
        form.addRow("姓名：", self.name_edit)

        # 实验下拉
        self.experiment_combo = QComboBox()
        for eid, name in experiment_choices():
            self.experiment_combo.addItem(f"{name}（{eid}）", eid)
        self.experiment_combo.currentIndexChanged.connect(self._on_experiment_changed)
        form.addRow("实验：", self.experiment_combo)

        box.setLayout(form)
        # 选中默认实验并同步到 state
        self._select_default_experiment()
        return box

    def _select_default_experiment(self):
        """选中默认实验（07-car-gear）并显式同步到 state。

        显式调用 _on_experiment_changed，避免「无索引变化」时 Qt 不触发
        currentIndexChanged 导致 combo 与 state 不一致。
        """
        target = "07-car-gear"
        for i in range(self.experiment_combo.count()):
            if self.experiment_combo.itemData(i) == target:
                self.experiment_combo.setCurrentIndex(i)
                break
        self._on_experiment_changed()

    def _create_action_group(self):
        w = QWidget()
        row = QHBoxLayout()
        self.run_btn = QPushButton("🚀 开始检测与自评")
        self.run_btn.setMinimumHeight(44)
        self.run_btn.setStyleSheet("""
            QPushButton { background-color: #16a085; color: white; font-size: 15px;
                font-weight: bold; border-radius: 6px; padding: 8px 24px; }
            QPushButton:hover { background-color: #1abc9c; }
            QPushButton:disabled { background-color: #bdc3c7; }
        """)
        self.run_btn.clicked.connect(self._start)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setMinimumHeight(44)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)
        self.status_pill = QLabel("")
        self.status_pill.setStyleSheet("font-weight:bold;")
        row.addWidget(self.status_pill, 1)
        row.addWidget(self.run_btn)
        row.addWidget(self.cancel_btn)
        w.setLayout(row)
        return w

    def _create_progress_group(self):
        box = QGroupBox("进度与日志")
        v = QVBoxLayout()
        self.progress = QProgressBar()
        self.progress.setFormat("%p%")
        v.addWidget(self.progress)
        self.detail_label = QLabel("等待开始…")
        v.addWidget(self.detail_label)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Consolas", 9))
        v.addWidget(self.log_view, 1)
        box.setLayout(v)
        return box

    # ---------------- 文件选择 ----------------
    def _pick_report(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择实验报告", str(Path.home()),
            "Word 文档 (*.docx);;Word 97-2003 (*.doc);;PDF (*.pdf);;所有文件 (*)"
        )
        if not path:
            return
        p = Path(path)
        shared().update(report_path=p)
        self.report_edit.setText(str(p))
        self._refresh_report_badge(p)

        # 身份自动回填
        ident = StudentIdentity.from_filename(p.stem)
        if ident.is_complete():
            self._suppress_identity_signal = True
            self.class_edit.setText(ident.class_name)
            self.id_edit.setText(ident.student_id)
            self.name_edit.setText(ident.name)
            self._suppress_identity_signal = False
            self._on_identity_edited()

    def _refresh_report_badge(self, p: Path):
        canonical = StudentIdentity.filename_is_canonical(p.stem)
        if canonical:
            self.report_badge.setText("✓ 文件名符合规范（班级-学号-姓名-实验报告）")
            self.report_badge.setStyleSheet("color:#27ae60;")
        else:
            self.report_badge.setText(
                "ℹ 文件名不符合规范。教师端按「班级-学号-姓名-实验报告」整理，建议改名以便后续批阅。"
            )
            self.report_badge.setStyleSheet("color:#7f8c8d;")
        self.pdf_banner.setVisible(p.suffix.lower() == ".pdf")

    def _pick_source(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择源代码压缩包", str(Path.home()),
            "压缩包 (*.zip *.7z);;ZIP 压缩包 (*.zip);;7z 压缩包 (*.7z)")
        if not path:
            return
        p = Path(path)
        kind = SourceKind.SEVEN_ZIP if p.suffix.lower() == ".7z" else SourceKind.ZIP
        shared().update(source_path=p, source_kind=kind)
        # 源码变更已作废上次自检结果：清理上一轮临时解压目录，避免残留 tempdir
        # 让旧源码路径仍可被访问/打包。
        SelfChecker.cleanup(self._live_tempdirs)
        self._live_tempdirs = []
        self.source_edit.setText(str(p))
        self.source_badge.setText(f"已选源码（{p.suffix.lower().lstrip('.')}）")
        self.source_badge.setStyleSheet("color:#27ae60;")

    def _clear_source(self):
        shared().update(source_path=None, source_kind=SourceKind.NONE)
        # 清除源码同样作废上次结果：清理上一轮临时解压目录。
        SelfChecker.cleanup(self._live_tempdirs)
        self._live_tempdirs = []
        self.source_edit.clear()
        self.source_badge.setText("")

    # ---------------- 身份 / 实验 ----------------
    def _on_identity_edited(self):
        if self._suppress_identity_signal:
            return
        ident = StudentIdentity(
            self.class_edit.text().strip(),
            self.id_edit.text().strip(),
            self.name_edit.text().strip(),
        )
        shared().update(identity=ident)

    def _on_experiment_changed(self):
        eid = self.experiment_combo.currentData()
        shared().update(experiment_code=eid or "")

    # ---------------- 运行 ----------------
    def _start(self):
        # 防止在上一轮 worker 仍存活时覆盖引用（导致 QThread 被提前销毁）
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, "请稍候", "上一次检测仍在进行中。")
            return
        if not shared().is_runnable():
            QMessageBox.warning(self, "无法开始", "请先选择实验报告并填写完整的学生信息。")
            return
        self._set_running(True)
        self.log_view.clear()
        self.progress.setValue(0)
        self.detail_label.setText("初始化…")
        self.log(f"[{datetime.now():%H:%M:%S}] 开始检测与自评")

        self.worker = CheckWorker()
        self.worker.stage_started.connect(self._on_stage_started)
        self.worker.stage_progress.connect(self._on_stage_progress)
        self.worker.stage_completed.connect(lambda sid: None)
        self.worker.log_message.connect(self.log)
        self.worker.result_ready.connect(self._on_result)
        self.worker.cancelled.connect(self._on_cancelled)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished_run.connect(lambda: self._set_running(False))
        # 内置 finished：线程真正结束后丢弃引用，允许对象回收
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _cancel(self):
        w = self.worker
        if w is None or not w.isRunning():
            return
        w.cancel()
        self.log("已请求取消（后台编译需运行至结束，结果将被忽略）")
        self.detail_label.setText("取消中…")
        self.cancel_btn.setEnabled(False)
        # 不在 GUI 线程 wait：长编译会冻结界面。按钮最终态由 finished_run 哨兵
        # （线程真正结束）恢复，避免在旧 worker 仍运行时启动新一轮。

    def cleanup_worker(self) -> bool:
        """窗口关闭前调用：等待并清理后台线程与临时解压目录。

        返回 True（尽力清理；超时则 terminate 后再等待）。确保关闭时不会
        在编译/读取过程中销毁 QThread。
        """
        w = self.worker
        if w is not None and w.isRunning():
            w.cancel()
            if not w.wait(5000):
                w.terminate()
                w.wait(2000)
        self.worker = None
        SelfChecker.cleanup(self._live_tempdirs)
        self._live_tempdirs = []
        return True

    def _set_running(self, running: bool):
        self.run_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)

    def _on_stage_started(self, sid, name):
        self.detail_label.setText(name)

    def _on_stage_progress(self, sid, cur, total):
        if total > 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(int(cur / total * 100))

    def _on_worker_finished(self):
        """QThread 内置 finished：丢弃 worker 引用，便于对象回收与新一轮启动。"""
        self.worker = None

    def _on_cancelled(self):
        self.detail_label.setText("已取消")
        self.log("已取消，结果未应用。")

    def _on_result(self, result):
        self.progress.setValue(100)
        self.detail_label.setText("完成")
        # 清理上一轮遗留的临时解压目录；本轮 tempdir 由结果持有，展示期间保留
        SelfChecker.cleanup(self._live_tempdirs)
        self._live_tempdirs = list(result.temp_dirs)
        shared().set_result(result)
        # 先刷新结果面板，再依次跳转
        self.main_window.check_panel.refresh()
        self.main_window.grade_panel.refresh()
        QMessageBox.information(
            self, "自检完成",
            f"预测得分：{result.grading.total_score:.1f}/{result.grading.max_score:.1f}（等级 {result.grading.grade}）\n"
            "请查看「提交检测」与「自评结果」。"
        )
        self.main_window.navigate("check")

    def _on_failed(self, msg):
        self.detail_label.setText("失败")
        QMessageBox.critical(self, "自检失败", msg)

    # ---------------- 刷新 ----------------
    def log(self, message: str):
        self.log_view.appendPlainText(f"[{datetime.now():%H:%M:%S}] {message}")

    def refresh(self):
        """供主窗口「重置」调用：清空本地输入并恢复默认实验。"""
        self.report_edit.clear()
        self.source_edit.clear()
        self.report_badge.setText("")
        self.source_badge.setText("")
        self.pdf_banner.hide()
        self.class_edit.clear()
        self.id_edit.clear()
        self.name_edit.clear()
        self.log_view.clear()
        self.progress.setValue(0)
        self.detail_label.setText("等待开始…")
        SelfChecker.cleanup(self._live_tempdirs)
        self._live_tempdirs = []
        # 恢复默认实验并同步 state（避免 combo 显示实验而 state 为空）
        self._select_default_experiment()
        self._refresh()

    def _refresh(self):
        s = shared().state()
        # 身份回显（外部重置时同步）
        if not self._suppress_identity_signal:
            if self.class_edit.text() != s.identity.class_name:
                self.class_edit.setText(s.identity.class_name)
            if self.id_edit.text() != s.identity.student_id:
                self.id_edit.setText(s.identity.student_id)
            if self.name_edit.text() != s.identity.name:
                self.name_edit.setText(s.identity.name)
        # 状态药丸 + 按钮启用
        if shared().is_runnable():
            self.status_pill.setText("✓ 可开始检测与自评")
            self.status_pill.setStyleSheet("color:#27ae60; font-weight:bold;")
            if not self.worker or not self.worker.isRunning():
                self.run_btn.setEnabled(True)
        else:
            missing = []
            if not s.report_path:
                missing.append("实验报告")
            if not s.identity.is_complete():
                missing.append("学生信息")
            if not s.experiment_code:
                missing.append("实验")
            self.status_pill.setText("⚠ 请补全：" + "、".join(missing))
            self.status_pill.setStyleSheet("color:#e67e22; font-weight:bold;")
            self.run_btn.setEnabled(False)
        # 源码工程状态横幅：反映最近一次自检结果（如纯 Keil → 编译计 0 提示）
        self._refresh_source_state_banner()

    def _refresh_source_state_banner(self):
        """刷新源码横幅：优先反映最近一次自检的 source_state；无结果时反映当前
        选择的源码是否存在环境问题（.7z 缺 py7zr）。

        - 有结果且 source_state 非 ok：Keil-only → 提示用 CubeMX 重生成 Makefile；
          其余 → 提示源码不可机器编译。
        - 无结果（或 ok）但当前选了 .7z 且环境无 py7zr：提示解压缺失，源码将视为
          缺失、编译/代码质量记 0，建议改选 .zip。
        - 其余：隐藏。
        """
        last = shared().state().last_result
        sstate = getattr(last, "source_state", "") if last else ""
        if sstate and sstate != "ok":
            if sstate == "keil_only":
                self.source_state_banner.setText(
                    "⚠ 检测到纯 Keil 工程（无 Makefile），机器编译将计 0 分。"
                    "请在 STM32CubeMX → Project Manager → Toolchain/IDE 选「Makefile」"
                    "重新生成工程后再提交。"
                )
            else:
                reason = getattr(last, "source_state_reason", "") or "未找到可编译的工程结构"
                self.source_state_banner.setText(f"⚠ 源码工程无法机器编译：{reason}")
            self.source_state_banner.show()
            return
        s = shared().state()
        if s.source_kind is SourceKind.SEVEN_ZIP and not _has_py7zr():
            self.source_state_banner.setText(
                "⚠ .7z 需 py7zr 才能解压，当前环境未安装。源码将被视为缺失，"
                "编译/代码质量记 0 分。建议改选 .zip，或安装 py7zr 后再自检。"
            )
            self.source_state_banner.show()
        else:
            self.source_state_banner.hide()
