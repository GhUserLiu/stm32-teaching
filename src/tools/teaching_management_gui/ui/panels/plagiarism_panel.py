#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
查重检测面板（批量 + 跨班级版）
Plagiarism Detection Panel

输入取自「数据源」页（多班级），对所有已选班级做查重（含跨班级比对），
结果合并到一张表。
"""

from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QPushButton, QLineEdit,
    QComboBox, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar,
    QTextEdit, QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from tools.teaching_management_gui.workers.plagiarism_worker import (
    PlagiarismWorker,
    METHOD_MAP,
)
from tools.plagiarism.core.detector import SimilarityMethod
from tools.teaching_management_gui.data_source import shared
from tools.teaching_management_gui.path_helper import (
    reports_dir as resolve_reports_dir,
    cross_class_dir as resolve_cross_class_dir,
)


class PlagiarismPanel(QWidget):
    """查重检测面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.plagiarism_worker = None
        self.current_payload = None
        self.is_detecting = False

        self.setup_ui()
        shared().entries_changed.connect(self._refresh_data_source_status)
        self._refresh_data_source_status()

    # ---------------- UI ----------------
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(self._create_config_panel())
        main_layout.addWidget(self._create_progress_panel())
        main_layout.addWidget(self._create_results_panel(), 1)
        main_layout.addWidget(self._create_log_panel())

    def _create_config_panel(self):
        group = QGroupBox("数据源与查重参数")
        layout = QVBoxLayout()

        # 数据源状态
        ds_row = QHBoxLayout()
        self.ds_status = QLabel()
        self.ds_status.setWordWrap(True)
        ds_row.addWidget(self.ds_status, 1)
        go_btn = QPushButton("前往数据源页")
        go_btn.clicked.connect(lambda: self.window().nav_list.setCurrentRow(0))
        ds_row.addWidget(go_btn)
        layout.addLayout(ds_row)

        # 查重方法 + 阈值
        params = QHBoxLayout()
        params.addWidget(QLabel("查重方法:"))
        self.method_combo = QComboBox()
        self.method_combo.addItem("结构相似度")
        self.method_combo.addItem("文本相似度")
        self.method_combo.addItem("语义相似度")
        self.method_combo.addItem("综合检测（推荐）")
        params.addWidget(self.method_combo)
        params.addWidget(QLabel("相似度阈值(%):"))
        self.threshold_spin = QLineEdit("60")
        self.threshold_spin.setMaximumWidth(80)
        params.addWidget(self.threshold_spin)
        params.addStretch()
        layout.addLayout(params)

        # 选项
        opts = QHBoxLayout()
        self.check_code = QCheckBox("代码查重")
        self.check_code.setChecked(True)
        self.check_report = QCheckBox("报告查重")
        self.check_report.setChecked(True)
        opts.addWidget(self.check_code)
        opts.addWidget(self.check_report)
        opts.addStretch()
        layout.addLayout(opts)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.start_btn = QPushButton("开始查重（全部班级）")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet(
            "QPushButton{background-color:#2196F3;color:white;font-weight:bold;"
            "border-radius:5px;padding:8px 16px;}"
            "QPushButton:hover{background-color:#1976D2;}"
            "QPushButton:disabled{background-color:#cccccc;}"
        )
        self.start_btn.clicked.connect(self.start_detection)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_detection)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        group.setLayout(layout)
        return group

    def _create_progress_panel(self):
        group = QGroupBox("查重进度")
        layout = QVBoxLayout()
        row = QHBoxLayout()
        row.addWidget(QLabel("总体:"), 0)
        self.overall_progress = QProgressBar()
        self.overall_progress.setFormat("%p%")
        row.addWidget(self.overall_progress, 1)
        layout.addLayout(row)
        self.detail_label = QLabel("等待开始...")
        layout.addWidget(self.detail_label)
        group.setLayout(layout)
        return group

    def _create_results_panel(self):
        group = QGroupBox("查重结果")
        layout = QVBoxLayout()
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(7)
        self.results_table.setHorizontalHeaderLabels([
            "班级A", "学生A", "班级B", "学生B", "相似度", "类型", "状态"
        ])
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.results_table)
        group.setLayout(layout)
        return group

    def _create_log_panel(self):
        group = QGroupBox("日志输出")
        group.setMaximumHeight(150)
        layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_text)
        group.setLayout(layout)
        return group

    # ---------------- 数据源状态 ----------------
    def _refresh_data_source_status(self):
        entries = shared().entries()
        if not entries:
            self.ds_status.setText("⚠ 尚未选择班级压缩包。请到「数据源」页选择（可多选）。")
            self.ds_status.setStyleSheet("color:#c0392b;font-weight:bold;")
            self.start_btn.setEnabled(False)
        else:
            names = "、".join(e.class_name for e in entries)
            self.ds_status.setText(f"✓ 已选 {len(entries)} 个班级：{names}（将做含跨班级的查重）")
            self.ds_status.setStyleSheet("color:#27ae60;font-weight:bold;")
            self.start_btn.setEnabled(not self.is_detecting)

    def log(self, message):
        if hasattr(self, "log_text"):
            ts = datetime.now().strftime("%H:%M:%S")
            self.log_text.append(f"[{ts}] {message}")

    # ---------------- 查重 ----------------
    def start_detection(self):
        # 防止在上一轮 worker 仍存活时覆盖引用（导致 QThread 被提前销毁）
        if self.plagiarism_worker is not None and self.plagiarism_worker.isRunning():
            QMessageBox.information(self, "请稍候", "上一次查重仍在进行中。")
            return
        entries = shared().entries()
        if not entries:
            QMessageBox.warning(self, "警告", "请先到「数据源」页选择班级压缩包")
            return

        method = METHOD_MAP.get(self.method_combo.currentText(), SimilarityMethod.HYBRID)
        try:
            threshold = float(self.threshold_spin.text().strip())
        except ValueError:
            QMessageBox.warning(self, "警告", "相似度阈值必须是数字")
            return
        if not (self.check_code.isChecked() or self.check_report.isChecked()):
            QMessageBox.warning(self, "警告", "至少选择一种查重内容（代码/报告）")
            return

        self.is_detecting = True
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.log_text.clear()
        self.results_table.setRowCount(0)
        self.overall_progress.setValue(0)
        self.detail_label.setText("初始化...")
        self.log(f"开始查重：共 {len(entries)} 个班级（含跨班级）")

        self.plagiarism_worker = PlagiarismWorker(
            entries=entries,
            semester=shared().semester(),
            method=method,
            threshold=threshold,
            check_code=self.check_code.isChecked(),
            check_report=self.check_report.isChecked(),
        )
        self.plagiarism_worker.log_message.connect(self.log)
        self.plagiarism_worker.progress.connect(self.on_progress)
        self.plagiarism_worker.detail.connect(lambda t: self.detail_label.setText(t))
        self.plagiarism_worker.detection_completed.connect(self.on_detection_completed)
        self.plagiarism_worker.detection_failed.connect(self.on_detection_failed)
        self.plagiarism_worker.detection_cancelled.connect(self.on_detection_cancelled)
        # 内置 finished：线程真正结束后丢弃引用，便于回收与新一轮启动
        self.plagiarism_worker.finished.connect(self._on_worker_finished)
        self.plagiarism_worker.start()

    def _on_worker_finished(self):
        """QThread 内置 finished：丢弃 worker 引用，便于对象回收与新一轮启动。"""
        self.plagiarism_worker = None

    def on_progress(self, percent):
        self.overall_progress.setValue(int(percent))

    def on_detection_completed(self, payload):
        self.current_payload = payload
        self.is_detecting = False
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.overall_progress.setValue(100)
        self.detail_label.setText("查重完成")
        self._fill_results_table(payload)
        cross = sum(1 for p in payload["pairs"] if p["cross_class"])
        self.log(f"查重完成：相似对 {len(payload['pairs'])}（跨班级 {cross}），可疑 {payload['suspicious_count']}")
        if payload.get("saved_path"):
            self.log(f"结果已保存：{payload['saved_path']}")
        if not payload["pairs"]:
            QMessageBox.information(self, "提示",
                f"没有达到阈值 {payload['threshold']}% 的相似对，可尝试降低阈值。")

    def on_detection_failed(self, message):
        self.is_detecting = False
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.detail_label.setText("查重失败")
        self.log(f"查重失败: {message}")
        QMessageBox.critical(self, "错误", f"查重失败:\n{message}")

    def on_detection_cancelled(self):
        self.is_detecting = False
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.detail_label.setText("查重已取消")
        self.log("查重已取消（结果未保留）")

    def _fill_results_table(self, payload):
        pairs = payload.get("pairs", [])
        self.results_table.setRowCount(len(pairs))
        for row, p in enumerate(pairs):
            cells = [
                p["class_a"], f"{p['name_a']}({p['student_a']})",
                p["class_b"], f"{p['name_b']}({p['student_b']})",
                f"{p['overall']}%", p["type"],
                "可疑" if p["suspicious"] else ("跨班" if p["cross_class"] else "—"),
            ]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                if col == 4:  # 相似度着色
                    if p["overall"] >= 85:
                        item.setForeground(Qt.GlobalColor.red)
                    elif p["overall"] >= 70:
                        item.setForeground(QColor("#E67E22"))
                    else:
                        item.setForeground(Qt.GlobalColor.darkYellow)
                if col == 6 and p["suspicious"]:
                    item.setForeground(Qt.GlobalColor.red)
                if col == 6 and (not p["suspicious"]) and p["cross_class"]:
                    item.setForeground(QColor("#2980B9"))
                self.results_table.setItem(row, col, item)

    def cancel_detection(self):
        if not self.is_detecting:
            return
        if QMessageBox.question(self, "确认", "确定取消查重？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        if self.plagiarism_worker:
            self.plagiarism_worker.cancel()
        self.cancel_btn.setEnabled(False)
        self.detail_label.setText("取消中…（当前比对阶段结束后停止）")
        # 不在 GUI 线程 wait()：查重 O(N²) 比对阶段可能整段不响应取消，wait 会
        # 冻结界面。start_btn 保持禁用，待 on_detection_cancelled 信号真正收尾再恢复。

    def is_running(self) -> bool:
        """后台查重线程是否仍在运行（供主窗口关窗判断）。"""
        return self.plagiarism_worker is not None and self.plagiarism_worker.isRunning()

    def stop_and_wait(self):
        """窗口关闭前调用：协作取消并等待线程退出，超时强制终止。"""
        w = self.plagiarism_worker
        if w is not None and w.isRunning():
            w.cancel()
            if not w.wait(5000):
                w.terminate()
                w.wait(2000)

    def export_report(self):
        """导出查重报告（CSV）到 results/reports/。"""
        if not self.current_payload:
            QMessageBox.warning(self, "提示", "请先执行查重，生成结果后再导出。")
            return
        payload = self.current_payload
        try:
            import csv
            entries = shared().entries()
            if not entries:
                return
            semester = shared().semester()
            e0 = entries[0]
            # 多班级时与 worker 的 JSON 同落 _跨班级比对/plagiarism/（中立位置，便于归档）；
            # 单班级仍落该班 results/reports/。
            if len(entries) > 1:
                out_dir = resolve_cross_class_dir(semester, "plagiarism")
            else:
                out_dir = resolve_reports_dir(e0.class_name, e0.experiment_id, semester)
            out_dir.mkdir(parents=True, exist_ok=True)
            base = f"{e0.class_name}_跨班级_查重" if len(entries) > 1 else f"{e0.class_name}_{e0.experiment_id}_查重"
            csv_path = out_dir / f"{base}.csv"
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["班级A", "学号A", "学生A", "班级B", "学号B", "学生B",
                            "整体相似度%", "文本%", "代码%", "结构%", "类型", "跨班级", "是否可疑"])
                for p in payload["pairs"]:
                    w.writerow([p["class_a"], p["student_a"], p["name_a"],
                                p["class_b"], p["student_b"], p["name_b"],
                                p["overall"], p["text_sim"], p["code_sim"], p["structure_sim"],
                                p["type"], "是" if p["cross_class"] else "", "是" if p["suspicious"] else ""])
            self.log(f"查重报告已导出: {csv_path}")
            QMessageBox.information(self, "导出完成", f"查重报告已导出至:\n{csv_path}")
        except Exception as e:
            self.log(f"导出失败: {e}")
            QMessageBox.critical(self, "导出失败", str(e))
