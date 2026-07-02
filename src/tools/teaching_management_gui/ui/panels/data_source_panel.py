#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据源面板
Data Source Panel

集中选择输入：支持同时选择多个班级压缩包，自动解析班级与实验，
统一供评分/查重/反馈面板取用（路径保持一致）。
"""

from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QLineEdit, QComboBox, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from tools.teaching_management_gui.path_helper import (
    parse_class_experiment_from_zip,
    match_experiment,
    experiment_choices,
)
from tools.teaching_management_gui.data_source import (
    ClassEntry,
    shared,
)

# 表格列索引
_COL_CLASS = 0
_COL_EXP = 1
_COL_ZIP = 2
_COL_DEL = 3


class DataSourcePanel(QWidget):
    """数据源面板：集中选择多个班级压缩包。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        # 初始同步一次（带上默认学期）
        shared().set_semester(self.semester_edit.text().strip())
        self._refresh_status()

    # ---------------- UI ----------------
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        layout.addWidget(self._create_config_group())
        layout.addWidget(self._create_table_group(), 1)
        layout.addWidget(self._create_status_bar())

    def _create_config_group(self):
        group = QGroupBox("输入选择")
        v = QVBoxLayout()

        # 学期
        sem_layout = QHBoxLayout()
        sem_layout.addWidget(QLabel("学期:"))
        self.semester_edit = QLineEdit(shared().semester())
        self.semester_edit.setPlaceholderText("例如：2026-春季")
        self.semester_edit.editingFinished.connect(self._on_semester_changed)
        sem_layout.addWidget(self.semester_edit)
        sem_layout.addStretch()
        v.addLayout(sem_layout)

        # 添加 / 清空 按钮
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("📂 添加班级压缩包（可多选）")
        self.add_btn.setMinimumHeight(36)
        self.add_btn.setStyleSheet(
            "QPushButton{background-color:#2196F3;color:white;font-weight:bold;"
            "border-radius:5px;padding:6px 14px;}"
            "QPushButton:hover{background-color:#1976D2;}"
        )
        self.add_btn.clicked.connect(self.select_zip_file)
        btn_layout.addWidget(self.add_btn)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.setMinimumHeight(36)
        self.clear_btn.clicked.connect(self.clear_all)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        v.addLayout(btn_layout)

        hint = QLabel("提示：可一次选择多个班的压缩包；班级与实验会自动解析，"
                      "实验可在下表逐行修改。所有面板共享此处的选择。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        v.addWidget(hint)

        group.setLayout(v)
        return group

    def _create_table_group(self):
        group = QGroupBox("已选班级")
        v = QVBoxLayout()
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["班级", "实验", "压缩包路径", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(_COL_CLASS, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(_COL_EXP, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(_COL_ZIP, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(_COL_DEL, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        v.addWidget(self.table)
        group.setLayout(v)
        return group

    def _create_status_bar(self):
        self.status_label = QLabel()
        self.status_label.setStyleSheet("font-weight:bold;padding:4px;")
        return self.status_label

    # ---------------- 业务 ----------------
    def select_zip_file(self):
        """添加班级压缩包（支持多选）。"""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择班级压缩包（可多选）", "", "ZIP文件 (*.zip)"
        )
        if not paths:
            return
        for p in paths:
            stem = Path(p).stem
            class_name, _strict = parse_class_experiment_from_zip(stem)
            exp_id = match_experiment(stem)
            if not exp_id:
                # 取不到时用第一个已知实验作默认
                choices = experiment_choices()
                exp_id = choices[0][0] if choices else ""
            self._append_row(class_name or stem, exp_id, p)
        self._sync_to_shared()
        self.log_added(paths)

    def log_added(self, paths):
        # 简单的状态反馈（数据源页无独立日志区，用状态栏展示）
        self._refresh_status()

    def clear_all(self):
        if self.table.rowCount() == 0:
            return
        if QMessageBox.question(
            self, "确认", "清空所有已选班级？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self.table.setRowCount(0)
        shared().clear()
        self._refresh_status()

    def _on_semester_changed(self):
        shared().set_semester(self.semester_edit.text().strip())
        self._refresh_status()

    # ---- 表格行操作 ----
    def _append_row(self, class_name, exp_id, zip_path):
        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, _COL_CLASS, QTableWidgetItem(class_name))

        combo = QComboBox()
        for eid, ename in experiment_choices():
            combo.addItem(f"{eid} — {ename}", eid)
        # 选中当前实验
        for i in range(combo.count()):
            if combo.itemData(i) == exp_id:
                combo.setCurrentIndex(i)
                break
        combo.currentIndexChanged.connect(self._sync_to_shared)
        self.table.setCellWidget(row, _COL_EXP, combo)

        self.table.setItem(row, _COL_ZIP, QTableWidgetItem(zip_path))

        del_btn = QPushButton("删除")
        del_btn.clicked.connect(lambda _, r=row: self._remove_row(r))
        self.table.setCellWidget(row, _COL_DEL, del_btn)

    def _remove_row(self, row):
        self.table.removeRow(row)
        # 重建"删除"按钮的 lambda 行号绑定：直接重连
        self._rewire_delete_buttons()
        self._sync_to_shared()

    def _rewire_delete_buttons(self):
        for r in range(self.table.rowCount()):
            btn = self.table.cellWidget(r, _COL_DEL)
            if btn:
                try:
                    btn.clicked.disconnect()
                except TypeError:
                    pass
                btn.clicked.connect(lambda _, rr=r: self._remove_row(rr))

    def _collect_entries(self):
        entries = []
        for r in range(self.table.rowCount()):
            class_item = self.table.item(r, _COL_CLASS)
            zip_item = self.table.item(r, _COL_ZIP)
            combo = self.table.cellWidget(r, _COL_EXP)
            if not class_item or not zip_item:
                continue
            exp_id = combo.currentData() if combo else ""
            entries.append(ClassEntry(
                class_name=class_item.text().strip(),
                experiment_id=(exp_id or "").strip(),
                zip_path=zip_item.text().strip(),
            ))
        return entries

    def _sync_to_shared(self):
        shared().set_entries(self._collect_entries())
        self._refresh_status()

    def _refresh_status(self):
        entries = shared().entries()
        if not entries:
            self.status_label.setText("⚠ 尚未选择任何班级压缩包")
            self.status_label.setStyleSheet("font-weight:bold;color:#c0392b;padding:4px;")
        else:
            names = "、".join(e.class_name for e in entries)
            self.status_label.setText(
                f"✓ 已选 {len(entries)} 个班级：{names}"
            )
            self.status_label.setStyleSheet("font-weight:bold;color:#27ae60;padding:4px;")

    def log(self, message):
        # 供主窗口统一日志调用兼容
        pass
