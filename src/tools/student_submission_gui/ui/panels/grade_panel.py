#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
「自评结果」面板
Grade Panel — GradingResult 展示

预测得分、各类别得分（编译行按 SKIPPED/FAILED/SUCCESS 区分着色）、
结构化失分与改进、思考题核对、导出自检报告。
"""

from pathlib import Path

from ...qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox,
    QUrl, QDesktopServices, QColor, Qt,
)

from tools.student_submission_gui.submission_state import shared
from tools.student_submission_gui.self_checker import build_status_of
from tools.student_submission_gui.self_check_report import write_report
from tools.student_submission_gui.runtime import writable_root
from tools.auto_grading.build_checker import BuildStatus


_GRADE_COLOR = {"A": "#27ae60", "B": "#2980b9", "C": "#f39c12", "D": "#e67e22", "F": "#c0392b"}
_METHOD_LABEL = {
    "build": "编译", "code_analysis": "静态分析", "source_check": "源码检查",
    "keyword": "关键词", "manual": "教师评定", "conditional": "条件",
}


class GradePanel(QWidget):
    """「自评结果」面板。"""

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

        # 常驻声明
        disclaimer = QLabel(
            "⚠ 本结果为机器预测分，仅供参考。学习态度为教师评定项（默认预测）；"
            "组长加分由报告团队信息自动判定。"
        )
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet("background:#fff8e1; color:#b8860b; padding:8px; border-radius:4px;")
        layout.addWidget(disclaimer)

        layout.addWidget(self._create_score_group())
        layout.addWidget(self._create_categories_group(), 2)
        bottom = QHBoxLayout()
        bottom.addWidget(self._create_issues_group(), 2)
        bottom.addWidget(self._create_thinking_group(), 1)
        layout.addLayout(bottom, 2)

        # 操作行
        ops = QHBoxLayout()
        export_btn = QPushButton("💾 导出自检报告（md+json）")
        export_btn.setStyleSheet(
            "QPushButton{background:#2980b9;color:white;font-weight:bold;padding:8px 16px;border-radius:5px;}"
            "QPushButton:hover{background:#3498db;}"
        )
        export_btn.clicked.connect(self._export)
        self.pack_btn = QPushButton("📦 打包提交")
        self.pack_btn.setToolTip("生成可直接上传学习通的规范提交压缩包（须先通过格式自检）")
        self.pack_btn.setStyleSheet(
            "QPushButton{background:#27ae60;color:white;font-weight:bold;padding:8px 16px;border-radius:5px;}"
            "QPushButton:hover{background:#2ecc71;}"
            "QPushButton:disabled{background:#bdc3c7;}"
        )
        self.pack_btn.clicked.connect(self._pack_submission)
        rerun_btn = QPushButton("↺ 重新检测")
        rerun_btn.clicked.connect(lambda: self.main_window.navigate("files"))
        ops.addStretch()
        ops.addWidget(self.pack_btn)
        ops.addWidget(export_btn)
        ops.addWidget(rerun_btn)
        layout.addLayout(ops)

        self._pkg_worker = None        # 持有 PackageWorker 引用防 GC
        self._last_gate = None         # 缓存 assess_gate 结果，按钮即时响应

    def _create_score_group(self):
        box = QGroupBox("预测得分")
        h = QHBoxLayout()
        self.score_label = QLabel("—")
        self.score_label.setStyleSheet("font-size:32px; font-weight:bold; color:#2c3e50;")
        h.addWidget(self.score_label)
        col = QVBoxLayout()
        self.grade_label = QLabel("")
        self.grade_label.setStyleSheet("font-size:22px; font-weight:bold;")
        self.bonus_label = QLabel("")
        self.bonus_label.setStyleSheet("font-size:13px; color:#555;")
        col.addWidget(self.grade_label)
        col.addWidget(self.bonus_label)
        col.addStretch()
        h.addLayout(col)
        h.addStretch()
        box.setLayout(h)
        return box

    def _create_categories_group(self):
        box = QGroupBox("各类别得分")
        v = QVBoxLayout()
        self.cat_table = QTableWidget(0, 6)
        self.cat_table.setHorizontalHeaderLabels(["类别", "得分", "满分", "得分率", "评定方式", "备注"])
        self.cat_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.cat_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        h = self.cat_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in (1, 2, 3, 4):
            h.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        v.addWidget(self.cat_table)
        box.setLayout(v)
        return box

    def _create_issues_group(self):
        box = QGroupBox("失分与改进建议")
        v = QVBoxLayout()
        self.issues_table = QTableWidget(0, 5)
        self.issues_table.setHorizontalHeaderLabels(["类别", "准则", "失分", "问题/缺失", "修正建议"])
        self.issues_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.issues_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        h = self.issues_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        v.addWidget(self.issues_table)
        box.setLayout(v)
        return box

    def _create_thinking_group(self):
        box = QGroupBox("思考题核对（参考答案）")
        v = QVBoxLayout()
        self.thinking_table = QTableWidget(0, 3)
        self.thinking_table.setHorizontalHeaderLabels(["题号", "作答", "参考方向"])
        self.thinking_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.thinking_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        h = self.thinking_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        v.addWidget(self.thinking_table)
        box.setLayout(v)
        return box

    # ---------------- 刷新 ----------------
    def refresh(self):
        result = shared().state().last_result
        if not result:
            self.score_label.setText("—")
            self.score_label.setStyleSheet("font-size:32px; color:#7f8c8d;")
            self.grade_label.setText("")
            self.bonus_label.setText("请先在「我的作业」中开始检测与自评")
            self.cat_table.setRowCount(0)
            self.issues_table.setRowCount(0)
            self.thinking_table.setRowCount(0)
            self._last_gate = None
            self.pack_btn.setEnabled(False)
            return

        # 缓存打包闸门结果，供按钮即时响应（纯函数，<1ms）
        from tools.student_submission_gui.submission_packager import assess_gate
        identity = shared().state().identity
        ok, blockers, warnings = assess_gate(result, identity)
        self._last_gate = (ok, blockers, warnings)
        self.pack_btn.setEnabled(True)

        g = result.grading
        self.score_label.setText(f"{g.total_score:.1f} / {g.max_score:.0f}")
        self.grade_label.setText(f"等级 {g.grade}")
        self.grade_label.setStyleSheet(f"font-size:22px; font-weight:bold; color:{_GRADE_COLOR.get(g.grade, '#333')};")
        bs = build_status_of(g)
        bonus_text = f"基础分外加分：{g.bonus_total:.0f}"
        if g.is_team_leader:
            bonus_text += "（报告声明组长）"
        # SKIPPED/FAILED 的真实原因按源码工程状态区分，避免把「源码不可评估」误说成「未装工具链」
        sstate = getattr(result, "source_state", "") or ""
        if bs == BuildStatus.SKIPPED:
            if sstate == "ok":
                bonus_text += "\n（编译未检测：未安装工具链，已按可评类别折算等级）"
            elif sstate in ("corrupted", "nested_archive", "empty", "not_submitted"):
                reason = getattr(result, "source_state_reason", "") or "源码不可评估"
                bonus_text += f"\n（编译未计入：{reason}）"
        elif bs == BuildStatus.FAILED and sstate == "keil_only":
            bonus_text += "\n（编译判 0：纯 Keil 工程，无 Makefile）"
        if sstate in ("not_submitted", "empty"):
            bonus_text = "未提交源码——可自评，但无法打包提交。\n" + bonus_text
        self.bonus_label.setText(bonus_text)

        self.cat_table.setRowCount(len(g.category_scores))
        for r, cs in enumerate(g.category_scores):
            method = self._method_of(cs)
            note = self._note_of(cs, g, bs)
            cells = [
                cs.category_name,
                f"{cs.earned_points:.1f}",
                f"{cs.max_points:.0f}",
                f"{(cs.earned_points / cs.max_points * 100) if cs.max_points else 0:.0f}%",
                _METHOD_LABEL.get(method, method),
                note,
            ]
            for c, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setToolTip(str(val))
                if c == 1:  # 得分列着色
                    item.setForeground(self._score_color(cs, method, bs))
                self.cat_table.setItem(r, c, item)

        # 失分项
        issues = [it for it in g.issues if it.get("severity") in ("error", "warning") or it.get("points_lost", 0) > 0]
        self.issues_table.setRowCount(len(issues))
        for r, it in enumerate(issues):
            desc = it.get("message", "")
            if it.get("missing_keywords"):
                desc += "（缺：" + ", ".join(it["missing_keywords"]) + "）"
            cells = [
                it.get("category", ""), it.get("criterion", ""),
                f"-{it.get('points_lost', 0):g}" if it.get("points_lost") else "",
                desc, it.get("fix", ""),
            ]
            for c, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setToolTip(it.get("expected", "") or str(val))
                self.issues_table.setItem(r, c, item)

        # 思考题
        tc = g.thinking_check or []
        self.thinking_table.setRowCount(len(tc))
        for r, t in enumerate(tc):
            mark = "✅" if t.get("answered") else "❌"
            cells = [t.get("id", ""), mark, t.get("expected", "")]
            for c, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setToolTip(str(val))
                if c == 1:
                    item.setForeground(QColor("#27ae60" if t.get("answered") else "#c0392b"))
                self.thinking_table.setItem(r, c, item)

    # ---------------- 辅助 ----------------
    @staticmethod
    def _method_of(cs):
        if cs.details and isinstance(cs.details[0], dict):
            if "build_result" in cs.details[0]:
                return "build"
            if "analysis" in cs.details[0]:
                return "code_analysis"
            if "violations" in cs.details[0] or "hit_count" in cs.details[0]:
                return "source_check"
        return "keyword"

    def _note_of(self, cs, g, bs):
        if cs.category_id == "compilation":
            if cs.details and isinstance(cs.details[0], dict):
                msg = cs.details[0].get("feedback") or cs.details[0].get("error_message", "")
            else:
                msg = ""
            if bs == BuildStatus.SKIPPED:
                return "已跳过（未安装工具链，未计入总分）—安装 make + arm-none-eabi-gcc 后可获真实编译反馈"
            if bs == BuildStatus.FAILED:
                return f"编译失败：{msg}"
            if bs == BuildStatus.SUCCESS:
                return "编译通过"
            return msg
        if cs.category_id == "attitude":
            return "预测值（教师评定项）"
        if cs.category_id == "functionality":
            return "教师实测评定（功能实现），不在机器预测分内"
        if cs.category_id == "team_leader_bonus":
            return "已计入" if g.is_team_leader else "未声明组长，未计入"
        if not cs.details:
            return ""
        # keyword 类别：展示命中情况摘要
        fb = cs.details[0].get("feedback", "") if isinstance(cs.details[0], dict) else ""
        return fb

    @staticmethod
    def _score_color(cs, method, bs):
        if cs.max_points <= 0:
            return QColor("#333")
        if method == "build":
            # 编译行：按 build 状态上色
            return {
                BuildStatus.SUCCESS: QColor("#27ae60"),
                BuildStatus.SKIPPED: QColor("#7f8c8d"),
                BuildStatus.FAILED: QColor("#c0392b"),
            }.get(bs, QColor("#e67e22"))
        ratio = cs.earned_points / cs.max_points
        if ratio >= 0.9:
            return QColor("#27ae60")
        if ratio >= 0.6:
            return QColor("#e67e22")
        return QColor("#c0392b")

    # ---------------- 导出 ----------------
    def _export(self):
        result = shared().state().last_result
        if not result:
            QMessageBox.information(self, "无结果", "请先完成一次检测与自评。")
            return
        try:
            out_dir = write_report(result, writable_root())
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))
            return
        QMessageBox.information(
            self, "导出完成",
            f"自检报告已生成：\n{out_dir}\n（自检报告.md / 自检报告.json）"
        )
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(out_dir)))

    # ---------------- 打包提交 ----------------
    def _pack_submission(self):
        """格式合规则生成规范提交 zip；否则弹拦截框列出 blockers，不产出 zip。"""
        result = shared().state().last_result
        if not result:
            QMessageBox.information(self, "无结果", "请先完成一次检测与自评。")
            return
        if self._pkg_worker is not None and self._pkg_worker.isRunning():
            QMessageBox.information(self, "请稍候", "上一次打包仍在进行中。")
            return
        identity = shared().state().identity
        gate = getattr(self, "_last_gate", None)
        if gate is None:
            from tools.student_submission_gui.submission_packager import assess_gate
            gate = assess_gate(result, identity)
        ok, blockers, warnings = gate
        if not ok:
            QMessageBox.warning(
                self, "暂无法打包",
                "存在以下格式问题，需先修正后再自检、再打包：\n\n• " + "\n• ".join(blockers)
            )
            return
        # 通过 → 后台打包（拷贝/zip 大源码树不卡 GUI）
        self.pack_btn.setEnabled(False)
        from tools.student_submission_gui.workers.check_worker import PackageWorker
        self._pkg_worker = PackageWorker(result, identity, writable_root())
        self._pkg_worker.done.connect(lambda p, w=warnings: self._on_pack_done(p, w))
        self._pkg_worker.blocked.connect(self._on_pack_blocked)
        self._pkg_worker.failed.connect(self._on_pack_failed)
        self._pkg_worker.finished_pack.connect(self._on_pack_finished)
        self._pkg_worker.start()

    def _on_pack_done(self, zip_path, warnings):
        msg = f"已生成规范提交压缩包：\n{zip_path}\n\n请用此 zip（不要改名）上传学习通。"
        if warnings:
            msg += "\n\n提示：\n• " + "\n• ".join(warnings)
        QMessageBox.information(self, "打包完成", msg)
        # 打开所在文件夹，方便学生立即上传
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(zip_path).parent)))

    def _on_pack_blocked(self, blockers):
        QMessageBox.warning(
            self, "暂无法打包",
            "存在以下格式问题，需先修正后再自检、再打包：\n\n• " + "\n• ".join(blockers)
        )

    def _on_pack_failed(self, msg):
        QMessageBox.critical(self, "打包失败", msg)

    def _on_pack_finished(self):
        self.pack_btn.setEnabled(True)
