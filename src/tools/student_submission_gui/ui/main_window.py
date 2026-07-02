#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
学生端作业自检与自评系统 主窗口
Student Self-Check & Self-Grade Main Window

侧边栏三面板：
- 我的作业：选报告 + 选源码 + 身份 + 实验 + 开始检测
- 提交检测：完整性/规范校验结果（ValidationReport）
- 自评结果：rubric 预测得分 + 失分与改进（GradingResult）
"""

from ..qt_compat import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QStackedWidget, QListWidgetItem,
    QFrame, QMessageBox, QLabel,
    QAction, QSize, Qt,
)

from tools.student_submission_gui.ui.panels.files_panel import FilesPanel
from tools.student_submission_gui.ui.panels.check_panel import CheckPanel
from tools.student_submission_gui.ui.panels.grade_panel import GradePanel
from tools.student_submission_gui.submission_state import shared
from tools.student_submission_gui import __version__


# 导航项：(id, 显示名, tooltip, 状态栏文案)
NAV_ITEMS = [
    ("files", "📁 我的作业", "选择报告与源码，填写身份后开始检测与自评",
     "我的作业 — 选择报告与源码"),
    ("check", "✅ 提交检测", "检查文件格式/齐全/章节/思考题等提交规范",
     "提交检测 — 提交规范与完整性校验"),
    ("grade", "📊 自评结果", "查看预测得分、逐项失分与改进建议",
     "自评结果 — 预测得分与改进建议（仅供参考）"),
]


class MainWindow(QMainWindow):
    """学生端主窗口。"""

    def __init__(self):
        super().__init__()
        self._panel_index = {}   # panel_id -> stacked index
        self.setup_ui()
        self.setup_menu_bar()
        # 订阅状态变化以刷新状态栏
        shared().state_changed.connect(self._refresh_status)

    # ---------------- UI ----------------
    def setup_ui(self):
        self.setWindowTitle(f"学生端 · 作业自检与自评系统 v{__version__}")
        self.setMinimumSize(1100, 760)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 侧边栏
        self.sidebar = self._create_sidebar()
        main_layout.addWidget(self.sidebar)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setFixedWidth(1)
        main_layout.addWidget(sep)

        # 内容栈
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack, 1)

        # 状态栏（create_panels 切换首项会触发导航 → 访问 _status_bar）
        self._status_bar = self.statusBar()
        self._status_bar.showMessage("欢迎使用作业自检与自评系统")
        # 永久角标：显示当前身份/实验摘要
        self._identity_label = QLabel("未填写身份")
        self._identity_label.setStyleSheet("color:#555; padding:0 8px;")
        self._status_bar.addPermanentWidget(self._identity_label)

        self._create_panels()
        self._refresh_status()

    def _create_sidebar(self):
        sidebar = QWidget()
        sidebar.setFixedWidth(210)
        sidebar.setStyleSheet("""
            QWidget { background-color: #2c3e50; color: white; }
            QListWidget { background-color: transparent; border: none; padding: 10px; }
            QListWidget::item { padding: 15px; margin: 2px 0; border-radius: 5px; color: white; }
            QListWidget::item:hover { background-color: #34495e; }
            QListWidget::item:selected { background-color: #16a085; font-weight: bold; }
            QLabel { padding: 10px; font-size: 14px; font-weight: bold; }
        """)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("功能导航")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.nav_list = QListWidget()
        self.nav_list.setIconSize(QSize(22, 22))
        for panel_id, name, tooltip, _ in NAV_ITEMS:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, panel_id)
            item.setToolTip(tooltip)
            self.nav_list.addItem(item)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        layout.addWidget(self.nav_list)

        layout.addStretch()
        hint = QLabel("提交前自检\n机器预测，以教师为准")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #95a5a6; font-size: 12px;")
        layout.addWidget(hint)
        return sidebar

    def _create_panels(self):
        self.files_panel = FilesPanel(self)
        self.check_panel = CheckPanel(self)
        self.grade_panel = GradePanel(self)
        for panel_id, panel in [
            ("files", self.files_panel),
            ("check", self.check_panel),
            ("grade", self.grade_panel),
        ]:
            idx = self.content_stack.addWidget(panel)
            self._panel_index[panel_id] = idx
        self.nav_list.setCurrentRow(0)

    # ---------------- 导航 ----------------
    def navigate(self, panel_id: str):
        """供面板调用切换（如检测完成后跳到「提交检测」）。"""
        idx = self._panel_index.get(panel_id)
        if idx is not None:
            self.nav_list.setCurrentRow(idx)

    def _on_nav_changed(self, index):
        if index < 0:
            return
        self.content_stack.setCurrentIndex(index)
        item = self.nav_list.item(index)
        panel_id = item.data(Qt.ItemDataRole.UserRole)
        status = dict((pid, msg) for pid, _, _, msg in NAV_ITEMS)
        self._status_bar.showMessage(status.get(panel_id, ""))

    def _refresh_status(self):
        """刷新状态栏永久角标：当前身份/实验摘要。"""
        s = shared().state()
        if s.identity.is_complete():
            text = f"{s.identity.class_name} · {s.identity.student_id} · {s.identity.name}"
        else:
            text = "未填写身份"
        if s.experiment_code:
            text += f"  |  实验：{s.experiment_code}"
        self._identity_label.setText(text)

    # ---------------- 菜单 ----------------
    def setup_menu_bar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件(&F)")
        reset_action = QAction("重置全部(&R)", self)
        reset_action.setShortcut("Ctrl+R")
        reset_action.triggered.connect(self._on_reset)
        file_menu.addAction(reset_action)
        file_menu.addSeparator()
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menubar.addMenu("视图(&V)")
        for i, (panel_id, name, _, _) in enumerate(NAV_ITEMS):
            act = QAction(name, self)
            act.triggered.connect(lambda _=False, idx=i: self.nav_list.setCurrentRow(idx))
            view_menu.addAction(act)

        help_menu = menubar.addMenu("帮助(&H)")
        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _on_reset(self):
        if QMessageBox.question(
            self, "确认", "清空当前选择与结果？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            shared().clear()
            self.check_panel.refresh()
            self.grade_panel.refresh()
            self.files_panel.refresh()
            self.navigate("files")

    def closeEvent(self, event):
        """关闭前等待后台检测线程退出，避免在编译/读取过程中销毁 QThread。"""
        try:
            self.files_panel.cleanup_worker()
        except Exception:
            pass
        super().closeEvent(event)

    def _show_about(self):
        QMessageBox.about(
            self, "关于",
            f"""
            <h3>学生端 · 作业自检与自评系统 v{__version__}</h3>
            <p>提交前用本地文件自检与自评的辅助工具。</p>
            <p><b>功能：</b></p>
            <ul>
                <li>✅ 提交检测：报告/源码格式、章节、思考题等规范校验</li>
                <li>📊 自评结果：按评分标准预测得分与改进建议</li>
            </ul>
            <p><b>说明：</b>编译检查需本机安装 make + arm-none-eabi-gcc；未安装时该项记 0 分但状态为「已跳过」，不代表代码无法编译。
            学习态度为教师评定项；组长加分由报告团队信息自动判定；机器预测分仅供参考。</p>
            <p><b>开发者：</b>STM32F407 教学团队</p>
            """
        )

    def log(self, message: str):
        cur = self.content_stack.currentWidget()
        if hasattr(cur, "log"):
            cur.log(message)
