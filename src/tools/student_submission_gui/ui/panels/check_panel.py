#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
「提交检测」面板
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
    """「提交检测」面板。"""

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

        # 头部：徽标 + 计数 + 跳转
        layout.addWidget(self._create_header())

        body = QHBoxLayout()
        body.addWidget(self._create_issues_group(), 3)
        right = QVBoxLayout()
        right.addWidget(self._create_sections_group())
        right.addWidget(self._create_questions_group(), 1)
        body.addLayout(right, 1)
        layout.addLayout(body, 1)

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
        go_grade = QPushButton("查看自评结果 →")
        go_grade.clicked.connect(lambda: self.main_window.navigate("grade"))
        row.addWidget(go_grade)
        box.setLayout(row)
        return box

    def _create_issues_group(self):
        box = QGroupBox("问题清单（含修正建议）")
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
            self.badge.setText("—")
            self.badge.setStyleSheet("font-size:20px; color:#7f8c8d;")
            self.count_label.setText("请先在「我的作业」中开始检测")
            self.count_label.setToolTip("")
            self.count_label.setStyleSheet("font-size:14px;")
            self.issues_table.setRowCount(0)
            self._clear_grid(self.sections_grid)
            self.questions_label.setText("—")
            return

        v = result.validation
        # 徽标
        if v.passed:
            self.badge.setText("✅ 通过")
            self.badge.setStyleSheet("font-size:20px; font-weight:bold; color:#27ae60;")
        else:
            self.badge.setText("❌ 存在问题")
            self.badge.setStyleSheet("font-size:20px; font-weight:bold; color:#c0392b;")
        self.count_label.setText(
            f"错误 {v.error_count} · 警告 {v.warning_count} · "
            f"提示 {sum(1 for i in v.issues if i.severity == 'info')}"
        )
        # 自检 warning（非阻塞，如团队表学号位数不规范）不在 issues 表里，单独提示：
        # 这些项在打包阶段会升级为 blocker，提前在此可见，避免到打包才撞墙。
        warnings = list(getattr(result, "warnings", []) or [])
        if warnings:
            self.count_label.setText(
                self.count_label.text() + f"  · 自检提示 {len(warnings)} 条")
            self.count_label.setToolTip(
                "自检提示（非阻塞，但打包时会拦截）：\n" + "\n".join(warnings))
            self.count_label.setStyleSheet("font-size:14px; color:#e67e22;")
        else:
            self.count_label.setToolTip("")
            self.count_label.setStyleSheet("font-size:14px;")

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

        # 章节 checklist
        self._render_sections(v.sections)

        # 思考题
        grading = result.grading
        answered = [t.get("id") for t in grading.thinking_check if t.get("answered")]
        missing = list(v.missing_questions or [])
        if not grading.thinking_check:
            self.questions_label.setText("（未生成思考题核对）")
        elif missing:
            self.questions_label.setText(
                f"已检测到作答：{', '.join(answered) or '无'}\n"
                f"未检测到题号：{', '.join(missing)}\n"
                "（提示：在七、思考题中按 Q1~Q7 显式标注题号以便核对）"
            )
            self.questions_label.setStyleSheet("color:#e67e22;")
        else:
            self.questions_label.setText("✅ Q1~Q7 均已检测到作答")
            self.questions_label.setStyleSheet("color:#27ae60;")

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
