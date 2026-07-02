#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动评分面板（批量版）
Auto Grading Panel

输入取自「数据源」页（支持多班级），点"开始批阅"对所有已选班级依次执行，
结果合并到一张表（含「班级」列）。
"""

from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QTextEdit, QSplitter, QFileDialog, QMessageBox, QComboBox, QInputDialog,
    QDialog, QApplication,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from tools.auto_grading import AutoGradingConfig
from tools.teaching_management_gui.workers.grading_worker import GradingWorker
from tools.teaching_management_gui.ui.class_report_dialog import ClassReportDialog
from tools.teaching_management_gui.data_source import shared
from tools.teaching_management_gui.path_helper import (
    grading_dir as resolve_grading_dir,
)


class GradingPanel(QWidget):
    """自动评分面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = AutoGradingConfig()
        self.all_results = []          # 跨班级合并的 GradingResult 列表
        self.all_failures = []         # per-student 评分失败清单（{student_id,name,...,error}）
        self.is_grading = False
        self.grading_worker = None
        self.start_time = None

        self.setup_ui()
        # 订阅数据源变化
        shared().entries_changed.connect(self._refresh_data_source_status)
        self._refresh_data_source_status()

    # ---------------- UI ----------------
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        main_layout.addWidget(self._create_data_source_panel())
        main_layout.addWidget(self._create_progress_panel())

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._create_stats_panel())
        splitter.addWidget(self._create_results_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        main_layout.addWidget(splitter, 1)

        main_layout.addWidget(self._create_log_panel())

    def _create_data_source_panel(self):
        group = QGroupBox("数据源")
        layout = QVBoxLayout()

        row = QHBoxLayout()
        self.ds_status = QLabel()
        self.ds_status.setWordWrap(True)
        row.addWidget(self.ds_status, 1)
        go_btn = QPushButton("前往数据源页")
        go_btn.clicked.connect(self._goto_data_source)
        row.addWidget(go_btn)
        layout.addLayout(row)

        self.start_btn = QPushButton("开始批阅（全部班级）")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; font-size: 14px;
                font-weight: bold; border-radius: 5px; padding: 8px 16px; }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        self.start_btn.clicked.connect(self.start_grading)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_grading)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        group.setLayout(layout)
        return group

    def _create_progress_panel(self):
        group = QGroupBox("批阅进度")
        layout = QVBoxLayout()
        row = QHBoxLayout()
        row.addWidget(QLabel("总体:"), 0)
        self.overall_progress = QProgressBar()
        self.overall_progress.setFormat("%p% (%v/%m)")
        row.addWidget(self.overall_progress, 1)
        layout.addLayout(row)
        self.detail_label = QLabel("等待开始...")
        layout.addWidget(self.detail_label)
        group.setLayout(layout)
        return group

    def _create_stats_panel(self):
        group = QGroupBox("批阅结果")
        layout = QHBoxLayout()

        stats = QVBoxLayout()
        self.total_label = QLabel("总提交: 0")
        self.total_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.avg_label = QLabel("平均分: 0.0")
        self.avg_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.time_label = QLabel("用时: 0:00")
        self.time_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        stats.addWidget(self.total_label)
        stats.addWidget(self.avg_label)
        stats.addWidget(self.time_label)
        stats.addStretch()
        layout.addLayout(stats, 1)

        btns = QVBoxLayout()
        view_report_btn = QPushButton("查看班级报告")
        view_report_btn.clicked.connect(self.view_class_report)
        btns.addWidget(view_report_btn)
        export_btn = QPushButton("导出个人报告")
        export_btn.clicked.connect(self.export_all_reports)
        btns.addWidget(export_btn)
        btns.addStretch()
        layout.addLayout(btns, 1)

        group.setLayout(layout)
        return group

    def _create_results_panel(self):
        group = QGroupBox("学生列表")
        layout = QVBoxLayout()
        # 班级筛选（多班级批阅合并时按班定位）
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("筛选班级:"))
        self.class_filter = QComboBox()
        self.class_filter.currentIndexChanged.connect(self._apply_class_filter)
        filter_row.addWidget(self.class_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # 失败清单横幅：N>0 时显示「⚠ N 人批阅失败」，点击弹明细（修静默丢学生）
        self.failure_btn = QPushButton("⚠ 0 人批阅失败")
        self.failure_btn.setStyleSheet(
            "QPushButton { color: #b00; font-weight: bold; text-align: left; padding: 4px 8px; }")
        self.failure_btn.clicked.connect(self._show_failures)
        self.failure_btn.setVisible(False)
        layout.addWidget(self.failure_btn)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(8)
        self.results_table.setHorizontalHeaderLabels([
            "班级", "学号", "姓名", "编译", "代码", "报告", "总分", "等级"
        ])
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.doubleClicked.connect(self.show_student_detail)
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
            self.ds_status.setText(f"✓ 已选 {len(entries)} 个班级：{names}")
            self.ds_status.setStyleSheet("color:#27ae60;font-weight:bold;")
            self.start_btn.setEnabled(not self.is_grading)

    def _goto_data_source(self):
        win = self.window()
        if hasattr(win, "nav_list"):
            win.nav_list.setCurrentRow(0)

    # ---------------- 日志 ----------------
    def log(self, message):
        if hasattr(self, "log_text"):
            ts = datetime.now().strftime("%H:%M:%S")
            self.log_text.append(f"[{ts}] {message}")

    # ---------------- 批量批阅 ----------------
    def _detect_resume(self, entries):
        """检测选中班级有无中断的批阅 checkpoint，弹框询问续跑/重开/取消（Phase B）。

        Returns: True=续跑（跳过已完成）；False=重新开始（已清残留 checkpoint）；None=取消。
        """
        from tools.auto_grading import batch_checkpoint as _bc
        interrupted = []
        semester = shared().semester()
        for e in entries:
            try:
                gdir = self.config.get_output_dir(e.class_name, e.experiment_id, semester)
            except Exception:
                continue
            m = _bc.load_meta(gdir)
            if _bc.is_interrupted(m):
                interrupted.append((e, m))
        if not interrupted:
            return False
        detail = "、".join(
            f"{e.class_name}({len(m['completed_ids'])}/{m['total']})" for e, m in interrupted)
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle("检测到未完成的批阅")
        msg.setText(f"检测到上次批阅中断：{detail}。\n是否继续未完成的部分？")
        b_resume = msg.addButton("继续未完成", QMessageBox.ButtonRole.AcceptRole)
        b_fresh = msg.addButton("重新开始", QMessageBox.ButtonRole.RejectRole)
        b_cancel = msg.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked is b_resume:
            return True
        if clicked is b_fresh:
            for e, _m in interrupted:
                try:
                    _bc.clear_checkpoint(self.config.get_output_dir(
                        e.class_name, e.experiment_id, semester))
                except Exception:
                    pass
            return False
        return None  # 取消

    def start_grading(self):
        # 防止在上一轮 worker 仍存活时覆盖引用（导致 QThread 被提前销毁）
        if self.grading_worker is not None and self.grading_worker.isRunning():
            QMessageBox.information(self, "请稍候", "上一次批阅仍在进行中。")
            return
        entries = shared().entries()
        if not entries:
            QMessageBox.warning(self, "警告", "请先到「数据源」页选择班级压缩包")
            return

        # 断点续跑检测（Phase B）：选中班级里有无上次中断的 checkpoint
        resume = self._detect_resume(entries)
        if resume is None:
            return  # 用户在续跑提示框点了「取消」

        self.is_grading = True
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.log_text.clear()
        self.results_table.setRowCount(0)
        self.overall_progress.setValue(0)
        self.detail_label.setText("初始化...")
        self.start_time = datetime.now()
        self.log(f"开始批量批阅：共 {len(entries)} 个班级")

        self.grading_worker = GradingWorker(entries, shared().semester(), self.config, resume=resume)
        self.grading_worker.stage_started.connect(self.on_stage_started)
        self.grading_worker.stage_progress.connect(self.on_stage_progress)
        self.grading_worker.stage_completed.connect(self.on_stage_completed)
        self.grading_worker.log_message.connect(self.log)
        self.grading_worker.grading_completed.connect(self.on_grading_completed)
        self.grading_worker.grading_failed.connect(self.on_grading_failed)
        self.grading_worker.grading_cancelled.connect(self.on_grading_cancelled)
        # 内置 finished：线程真正结束后丢弃引用，便于回收与新一轮启动
        self.grading_worker.finished.connect(self._on_worker_finished)
        self.grading_worker.start()

    def _on_worker_finished(self):
        """QThread 内置 finished：丢弃 worker 引用，便于对象回收与新一轮启动。"""
        self.grading_worker = None

    def on_stage_started(self, stage_id, stage_name):
        self.detail_label.setText(stage_name)

    def on_stage_progress(self, stage_id, current, total):
        if stage_id == "analyze":
            self.overall_progress.setRange(0, total)
            self.overall_progress.setValue(current)

    def on_stage_completed(self, stage_id):
        pass

    def on_grading_completed(self, results, failures=None):
        self.all_results = results or []
        self.all_failures = failures or []
        self.is_grading = False
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.overall_progress.setValue(self.overall_progress.maximum())
        self.detail_label.setText("批阅完成")

        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            self.time_label.setText(f"用时: {int(elapsed // 60)}:{int(elapsed % 60):02d}")

        # 修正完成数失真：原 len(all_results) 只数成功，漏算被丢弃的失败学生
        ok = len(self.all_results)
        bad = len(self.all_failures)
        total = ok + bad
        avg = (sum(r.total_score for r in self.all_results) / ok) if ok else 0
        self.total_label.setText(f"成功 {ok} · 失败 {bad} · 共 {total}")
        self.avg_label.setText(f"平均分: {avg:.1f}")
        self._update_failure_banner()
        self._fill_results_table()
        self.log(f"批阅完成！成功 {ok} / 失败 {bad} / 共 {total}，平均 {avg:.1f}")

    def _update_failure_banner(self):
        n = len(self.all_failures)
        if n > 0:
            self.failure_btn.setText(f"⚠ {n} 人批阅失败 — 点击查看清单")
            self.failure_btn.setVisible(True)
        else:
            self.failure_btn.setVisible(False)

    def _show_failures(self):
        """弹窗展示 per-student 评分失败清单（学号/姓名/班级/实验/原因），可一键复制。"""
        if not self.all_failures:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"批阅失败清单（{len(self.all_failures)} 人）")
        dlg.resize(820, 420)
        v = QVBoxLayout(dlg)
        table = QTableWidget(len(self.all_failures), 5)
        table.setHorizontalHeaderLabels(["学号", "姓名", "班级", "实验", "失败原因"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        for row, f in enumerate(self.all_failures):
            table.setItem(row, 0, QTableWidgetItem(str(f.get("student_id", ""))))
            table.setItem(row, 1, QTableWidgetItem(str(f.get("name", ""))))
            table.setItem(row, 2, QTableWidgetItem(str(f.get("class_name", ""))))
            table.setItem(row, 3, QTableWidgetItem(str(f.get("experiment_id", ""))))
            table.setItem(row, 4, QTableWidgetItem(str(f.get("error", ""))))
        v.addWidget(table)
        copy_btn = QPushButton("复制全部（供粘贴到通知）")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(
            "\n".join(
                f"{x.get('student_id', '')}\t{x.get('name', '')}\t{x.get('class_name', '')}\t"
                f"{x.get('experiment_id', '')}\t{x.get('error', '')}"
                for x in self.all_failures
            )
        ))
        v.addWidget(copy_btn)
        dlg.exec()

    def on_grading_failed(self, error_message):
        self.is_grading = False
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.detail_label.setText("批阅失败")
        self.log(f"批阅失败: {error_message}")
        QMessageBox.critical(self, "错误", f"批阅失败:\n{error_message}")

    def on_grading_cancelled(self):
        self.is_grading = False
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.detail_label.setText("批阅已取消")
        self.log("批阅已取消（已评部分已保存为 checkpoint，下次「开始批阅」可续跑）")

    def _fill_results_table(self):
        results = self.all_results
        # 填充期间暂停排序，避免每行插入都触发重排；填完再开
        self.results_table.setSortingEnabled(False)
        self.results_table.setRowCount(len(results))
        for row, r in enumerate(results):
            compilation_score = code_score = report_score = 0
            compilation_ok = True
            for cs in r.category_scores:
                if cs.category_id == "compilation":
                    compilation_score = cs.earned_points
                    compilation_ok = compilation_score > 0
                elif cs.category_id == "code_quality":
                    code_score = cs.earned_points
                elif cs.category_id == "report_quality":
                    report_score = cs.earned_points
            row_key = f"{r.class_name}|{r.student_id}"
            grade_color = (Qt.GlobalColor.darkGreen if r.grade == "A"
                           else (Qt.GlobalColor.red if r.grade == "F" else None))
            # (显示文本, 数值排序依据或 None, 前景色或 None)
            coldefs = [
                (r.class_name, None, None),
                (r.student_id, None, None),
                (r.name, None, None),
                ("✓" if compilation_ok else "✗", None,
                 Qt.GlobalColor.green if compilation_ok else Qt.GlobalColor.red),
                (f"{code_score:.0f}", float(code_score), None),
                (f"{report_score:.0f}", float(report_score), None),
                (f"{r.total_score:.1f}", float(r.total_score), None),
                (r.grade, None, grade_color),
            ]
            for col, (text, num, color) in enumerate(coldefs):
                item = QTableWidgetItem()
                item.setData(Qt.ItemDataRole.DisplayRole, text)
                if num is not None:
                    # 数值列给 EditRole 一个 float，点表头时按数值而非字典序排序
                    item.setData(Qt.ItemDataRole.EditRole, num)
                if color is not None:
                    item.setForeground(color)
                if col == 0:
                    # 行键：排序/筛选后行序与 all_results 不再一一对应，据此回查结果
                    item.setData(Qt.ItemDataRole.UserRole, row_key)
                self.results_table.setItem(row, col, item)
        self.results_table.setSortingEnabled(True)
        # 重建班级筛选下拉
        self.class_filter.blockSignals(True)
        self.class_filter.clear()
        classes = []
        for r in results:
            if r.class_name not in classes:
                classes.append(r.class_name)
        self.class_filter.addItem("全部")
        self.class_filter.addItems(classes)
        self.class_filter.blockSignals(False)
        self._apply_class_filter()

    def _apply_class_filter(self, *_):
        """按筛选班级隐藏不匹配的行（与排序兼容：隐藏行不参与显示但不删除）。"""
        cls = self.class_filter.currentText()
        for row in range(self.results_table.rowCount()):
            item = self.results_table.item(row, 0)
            cell_class = item.data(Qt.ItemDataRole.DisplayRole) if item else ""
            self.results_table.setRowHidden(row, cls != "全部" and cell_class != cls)

    def cancel_grading(self):
        if not self.is_grading:
            return
        if QMessageBox.question(self, "确认", "确定取消批阅？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        if self.grading_worker:
            self.grading_worker.cancel()
        self.cancel_btn.setEnabled(False)
        self.detail_label.setText("取消中…（当前编译/阶段结束后停止，部分结果将被丢弃）")
        # 不在 GUI 线程 wait()：批阅中途的 make 编译无法立即中断，wait 会冻结
        # 界面最多 build_timeout。start_btn 保持禁用，待 on_grading_cancelled 信号
        # （线程真正收尾）再恢复——避免在旧 worker 仍运行时启动新一轮，导致
        # self.grading_worker 引用被覆盖、仍 running 的 QThread 被销毁而崩溃。

    def is_running(self) -> bool:
        """后台批阅线程是否仍在运行（供主窗口关窗判断）。"""
        return self.grading_worker is not None and self.grading_worker.isRunning()

    def stop_and_wait(self):
        """窗口关闭前调用：协作取消并等待线程退出，超时强制终止。

        与「取消」按钮不同（仅置标志、不阻塞），本方法会 wait 到线程结束，
        确保关窗时不留仍 running 的 QThread（否则 PyQt6 会警告/闪退），
        也不留孤儿 make/gcc 子进程。
        """
        w = self.grading_worker
        if w is not None and w.isRunning():
            w.cancel()
            if not w.wait(5000):
                w.terminate()
                w.wait(2000)

    # ---------------- 详情 / 报告 ----------------
    def show_student_detail(self, index):
        # 排序/筛选后行序与 all_results 不再对应：用行键（班级|学号）回查
        key_item = self.results_table.item(index.row(), 0)
        if key_item is None:
            return
        row_key = key_item.data(Qt.ItemDataRole.UserRole)
        r = next((x for x in self.all_results
                  if f"{x.class_name}|{x.student_id}" == row_key), None)
        if r is None:
            return
        detail = (
            f"<h3>{r.class_name} - {r.name}</h3>"
            f"<table border=1 cellpadding=4>"
            f"<tr><td>学号</td><td>{r.student_id}</td></tr>"
            f"<tr><td>总分</td><td>{r.total_score:.1f}/{r.max_score:.1f}</td></tr>"
            f"<tr><td>等级</td><td><b>{r.grade}</b></td></tr></table>"
        )
        if r.strengths:
            detail += "<br><b>优点:</b><ul>" + "".join(f"<li>{s}</li>" for s in r.strengths) + "</ul>"
        if r.weaknesses:
            detail += "<br><b>不足:</b><ul>" + "".join(f"<li>{s}</li>" for s in r.weaknesses) + "</ul>"
        QMessageBox.information(self, "学生详情", detail)

    def view_class_report(self):
        """打开班级报告对话框。多班级时让教师选择要查看的班（此前只取 entries[0]，
        其余班的报告 GUI 无入口）。"""
        entries = shared().entries()
        if not entries:
            QMessageBox.warning(self, "提示", "请先在「数据源」页选择班级")
            return
        # 去重 (班级, 实验)，多班级时弹选择框
        uniq = []
        for en in entries:
            if (en.class_name, en.experiment_id) not in uniq:
                uniq.append((en.class_name, en.experiment_id))
        if len(uniq) > 1:
            labels = [f"{c}（{e}）" for c, e in uniq]
            choice, ok = QInputDialog.getItem(
                self, "选择班级", "要查看哪个班级的报告？", labels, 0, False)
            if not ok:
                return
            class_name, experiment_id = uniq[labels.index(choice)]
        else:
            class_name, experiment_id = uniq[0]
        semester = shared().semester()
        report_dir = resolve_grading_dir(class_name, experiment_id, semester)
        if not report_dir.exists():
            QMessageBox.warning(self, "报告不存在",
                f"未找到 {class_name} 的批阅报告：\n{report_dir}\n请先执行批阅。")
            return
        self.log(f"打开班级报告：{class_name}（其它班级报告见各自 results/grading/）")
        ClassReportDialog(class_name, experiment_id, semester, self).exec()

    def export_report(self):
        """供主窗口「导出报告」菜单调用。"""
        self.export_all_reports()

    def export_all_reports(self):
        """把所有已选班级的个人报告导出到一个目录。"""
        entries = shared().entries()
        if not entries:
            QMessageBox.warning(self, "提示", "请先在「数据源」页选择班级")
            return
        export_dir = QFileDialog.getExistingDirectory(self, "选择导出目录", str(Path.cwd() / "exports"))
        if not export_dir:
            return
        export_path = Path(export_dir)
        total = success = 0
        for e in entries:
            individuals = resolve_grading_dir(e.class_name, e.experiment_id, shared().semester()) / "个人报告"
            if not individuals.exists():
                continue
            for rf in individuals.glob("*-评分.json"):
                total += 1
                try:
                    (export_path / f"{e.class_name}-{rf.name}").write_text(
                        rf.read_text(encoding="utf-8"), encoding="utf-8")
                    success += 1
                except Exception as ex:
                    self.log(f"导出失败 {rf.name}: {ex}")
        self.log(f"导出完成: {success}/{total}")
        QMessageBox.information(self, "导出完成", f"成功导出 {success}/{total} 个报告\n{export_path}")
