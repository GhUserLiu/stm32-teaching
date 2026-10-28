#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
「检测过程」面板
Check Panel — ValidationReport 展示

展示提交完整性/规范校验：pass/fail、issues 表、章节一~七 checklist、思考题 Q1~Q7。
读 shared().state().last_result。
"""

from ...qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox,
    Qt,
)

from tools.student_submission_gui.submission_state import shared
from tools.auto_grading.submission_validator import EXPECTED_SECTIONS

_SEVERITY_LABEL = {"error": "错误", "warning": "警告", "info": "提示"}
_SEVERITY_COLOR = {"error": "#c0392b", "warning": "#e67e22", "info": "#7f8c8d"}


class CheckPanel(QWidget):
    """「检测过程」面板。"""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setup_ui()
        shared().state_changed.connect(self.refresh)
        self.refresh()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 顶部：检测进度与实时日志（由「① 提交作业」的开始按钮驱动）
        layout.addWidget(self._create_progress_group())

        # 主体：提交规范问题（总结论与得分在下方「反馈与改进」区，不重复展示）
        body = QHBoxLayout()
        body.addWidget(self._create_issues_group(), 3)
        right = QVBoxLayout()
        right.addWidget(self._create_sections_group())
        body.addLayout(right, 1)
        layout.addLayout(body, 1)

    # ---------------- 进度与日志（承接自①页，消除重复展示） ----------------
    def _create_progress_group(self):
        from PyQt6.QtWidgets import QProgressBar, QPlainTextEdit
        from PyQt6.QtGui import QFont
        box = QGroupBox("检测进度与日志")
        v = QVBoxLayout()
        self.run_progress = QProgressBar()
        self.run_progress.setFormat("%p%")
        v.addWidget(self.run_progress)
        self.run_detail = QLabel("等待开始——到「① 提交作业」选好文件点开始检测")
        v.addWidget(self.run_detail)
        self.run_log = QPlainTextEdit()
        self.run_log.setReadOnly(True)
        self.run_log.setFont(QFont("Consolas", 9))
        self.run_log.setMaximumHeight(150)
        v.addWidget(self.run_log)
        box.setLayout(v)
        return box

    def begin_run(self):
        """新一轮检测开始：清日志、进度归零。"""
        self.run_log.clear()
        self.run_progress.setRange(0, 100)
        self.run_progress.setValue(0)
        self.run_detail.setText("初始化…")

    def set_detail(self, text: str):
        self.run_detail.setText(text)

    def set_progress(self, cur: int, total: int):
        if total > 0:
            self.run_progress.setRange(0, 100)
            self.run_progress.setValue(int(cur / total * 100))

    def append_log(self, message: str):
        from datetime import datetime
        self.run_log.appendPlainText(f"[{datetime.now():%H:%M:%S}] {message}")

    def finish_run(self):
        self.run_progress.setValue(100)
        self.run_detail.setText("完成 ✓")

    def _create_header(self):
        box = QGroupBox("检测结果")
        row = QHBoxLayout()
        self.badge = QLabel("—")
        self.badge.setStyleSheet("font-size:20px; font-weight:bold;")
        row.addWidget(self.badge)
        row.addStretch()
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("font-size:14px;")
        row.addWidget(self.count_label)
        box.setLayout(row)
        return box

    def _create_issues_group(self):
        box = QGroupBox("提交规范问题（格式 / 章节 / 思考题规范——不直接影响得分）")
        v = QVBoxLayout()
        self.issues_table = QTableWidget(0, 5)
        self.issues_table.setHorizontalHeaderLabels(["严重度", "规则", "章节", "描述", "修正建议"])
        self.issues_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.issues_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        h = self.issues_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        v.addWidget(self.issues_table)
        box.setLayout(v)
        return box

    def _create_sections_group(self):
        box = QGroupBox("章节完整性（一~七）")
        v = QVBoxLayout()
        self.sections_grid = QGridLayout()
        v.addLayout(self.sections_grid)
        v.addStretch()
        box.setLayout(v)
        return box

    def _create_questions_group(self):
        box = QGroupBox("思考题作答（Q1~Q7）")
        v = QVBoxLayout()
        self.questions_label = QLabel("—")
        self.questions_label.setWordWrap(True)
        v.addWidget(self.questions_label)
        v.addStretch()
        box.setLayout(v)
        return box

    # ---------------- 刷新 ----------------
    def refresh(self):
        result = shared().state().last_result
        if not result or result.validation is None:
            self.issues_table.setRowCount(0)
            self._clear_grid(self.sections_grid)
            return

        v = result.validation

        # 自检 warning（非阻塞，如团队表学号位数不规范）不在 issues 表里，
        # 在进度行单独提示：这些项在打包阶段会升级为 blocker，提前可见。
        warnings = list(getattr(result, "warnings", []) or [])
        if warnings:
            self.run_detail.setText(
                f"完成 ✓  ·  错误 {v.error_count} · 警告 {v.warning_count}"
                f"  ·  自检提示 {len(warnings)} 条（打包时会拦截，见日志）")
            self.run_detail.setToolTip(
                "自检提示（非阻塞，但打包时会拦截）：\n" + "\n".join(warnings))
        else:
            self.run_detail.setText(
                f"完成 ✓  ·  错误 {v.error_count} · 警告 {v.warning_count}"
                f" · 提示 {sum(1 for i in v.issues if i.severity == 'info')}")
            self.run_detail.setToolTip("")

        # 问题清单
        issues = sorted(v.issues, key=lambda i: {"error": 0, "warning": 1, "info": 2}.get(i.severity, 3))
        self.issues_table.setRowCount(len(issues))
        for r, it in enumerate(issues):
            sev_cn = _SEVERITY_LABEL.get(it.severity, it.severity)
            cells = [sev_cn, it.rule, it.section, it.message, it.fix or ""]
            for c, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setToolTip(str(val))
                if c == 0:
                    item.setForeground(Qt.GlobalColor.black)
                    item.setForeground(self._brush(it.severity))
                self.issues_table.setItem(r, c, item)

        # 章节 checklist（思考题核对见下方「反馈与改进」区，不重复展示）
        self._render_sections(v.sections)

    @staticmethod
    def _brush(severity: str):
        from ...qt_compat import QColor
        return QColor(_SEVERITY_COLOR.get(severity, "#000"))

    def _render_sections(self, detected_sections: dict):
        grid = self.sections_grid
        self._clear_grid(grid)
        names = detected_sections or {}
        # 一~七：按关键词判定是否在场
        cols = 2
        for idx, (numeral, keywords, _cat, _pts) in enumerate(EXPECTED_SECTIONS):
            present = any(any(kw in n for kw in keywords) for n in names.keys())
            mark = "✅" if present else "❌"
            label = QLabel(f"{mark} {numeral}、（{', '.join(keywords[:1])}…）")
            label.setStyleSheet(f"color:{'#27ae60' if present else '#c0392b'};")
            grid.addWidget(label, idx // cols, idx % cols)

    @staticmethod
    def _clear_grid(grid):
        while grid.count():
            item = grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
