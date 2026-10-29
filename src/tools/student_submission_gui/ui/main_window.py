#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
学生端作业自检与自评系统 主窗口
Student Self-Check & Self-Grade Main Window

侧边栏三面板：
- 提交作业：选报告 + 选源码 + 身份 + 实验 + 开始检测
- 检测过程：完整性/规范校验结果（ValidationReport）
- 反馈与改进：rubric 预测得分 + 失分与改进（GradingResult）
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


# 全局视觉主题（浅底卡片风）：主窗口设置后作用于全部子控件
APP_QSS = """
QWidget { background-color: #f4f6f9; color: #1f2937; font-size: 13px; font-family: "Microsoft YaHei","PingFang SC",sans-serif; }
QLabel { background: transparent; }

QGroupBox {
    background-color: #ffffff;
    border: 1px solid #dde5f0;
    border-radius: 8px;
    margin-top: 20px;
    padding: 16px 12px 12px 12px;
    font-weight: bold;
    color: #2563eb;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px; top: 2px; padding: 0 4px;
    color: #2563eb;
}

QPushButton {
    background-color: #ffffff; color: #1f2937;
    border: 1px solid #c9d6ea; border-radius: 6px;
    padding: 6px 16px;
}
QPushButton:hover { background-color: #eef4ff; border-color: #2563eb; color: #2563eb; }
QPushButton:pressed { background-color: #dbeafe; }
QPushButton:disabled { color: #93a3b8; background-color: #f8fafc; border-color: #e2e8f0; }

QLineEdit, QComboBox {
    background-color: #ffffff;
    border: 1px solid #c9d6ea; border-radius: 5px;
    padding: 4px 8px;
    selection-background-color: #dbeafe;
}
QLineEdit:focus, QComboBox:focus { border: 1px solid #3498db; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: #ffffff; border: 1px solid #c9d6ea;
    selection-background-color: #dbeafe; selection-color: #1f2937;
}

QTableWidget {
    background-color: #ffffff;
    border: 1px solid #dde5f0; border-radius: 6px;
    gridline-color: #e6ecf5;
    alternate-background-color: #f6f9fd;
}
QHeaderView::section {
    background-color: #2563eb; color: #ffffff;
    border: none; padding: 6px 8px;
    font-weight: bold;
}
QTableWidget::item { padding: 4px 6px; }
QTableWidget::item:selected { background-color: #dbeafe; color: #1f2937; }

QProgressBar {
    background-color: #ffffff; border: 1px solid #dde5f0;
    border-radius: 5px; text-align: center; height: 16px;
}
QProgressBar::chunk { background-color: #16a085; border-radius: 4px; }

QPlainTextEdit, QTextEdit {
    background-color: #ffffff;
    border: 1px solid #dde5f0; border-radius: 6px;
}

QScrollArea { border: none; background: transparent; }
QStatusBar { background-color: #ffffff; border-top: 1px solid #dde5f0; }
QMenuBar { background-color: #ffffff; }
QMenuBar::item:selected { background-color: #dbeafe; }
QMenu { background-color: #ffffff; border: 1px solid #dde5f0; }
QMenu::item:selected { background-color: #dbeafe; }
"""

# 导航项：(id, 显示名, tooltip, 状态栏文案)
NAV_ITEMS = [
    ("files", "① 提交作业", "选学期/专业/实验，选择报告与源码",
     "提交作业 — 选择报告与源码"),
    ("result", "② 反馈与改进", "检测进度与日志、提交规范问题清单、逐项得分与改进建议",
     "反馈与改进 — 问题清单、得分与改进建议"),
]


class MainWindow(QMainWindow):
    """学生端主窗口。"""

    def __init__(self):
        super().__init__()
        self.setStyleSheet(APP_QSS)
        self._panel_index = {}   # panel_id -> stacked index
        self.setup_ui()
        self.setup_menu_bar()
        # 订阅状态变化以刷新状态栏
        shared().state_changed.connect(self._refresh_status)

    # ---------------- UI ----------------
    def setup_ui(self):
        self.setWindowTitle(f"单片机课程 · 作业自检与自评系统 v{__version__}")
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
            QWidget { background-color: #1f2937; color: white; }
            QListWidget { background-color: transparent; border: none; padding: 10px; }
            QListWidget::item { padding: 15px; margin: 2px 0; border-radius: 5px; color: white; }
            QListWidget::item:hover { background-color: #2563eb; }
            QListWidget::item:selected { background-color: #2563eb; font-weight: bold; }
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
        hint = QLabel("提交前自检\n机器预测，以教师为准\n汽车工程学院单片机课程组")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #95a5a6; font-size: 12px;")
        layout.addWidget(hint)
        return sidebar

    def _create_panels(self):
        self.files_panel = FilesPanel(self)
        self.check_panel = CheckPanel(self)
        self.grade_panel = GradePanel(self)

        # ② 反馈与改进 = 检测过程 + 得分改进 同页纵排（消除两页内容重复）
        from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea
        result_page = QWidget()
        rp_layout = QVBoxLayout(result_page)
        rp_layout.setContentsMargins(0, 0, 0, 0)
        self.check_panel.setSizePolicy(self.check_panel.sizePolicy())
        rp_layout.addWidget(self.check_panel)
        rp_layout.addWidget(self.grade_panel)
        rp_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(result_page)

        for panel_id, panel in [
            ("files", self.files_panel),
            ("result", scroll),
        ]:
            idx = self.content_stack.addWidget(panel)
            self._panel_index[panel_id] = idx
        self.nav_list.setCurrentRow(0)

    # ---------------- 导航 ----------------
    def navigate(self, panel_id: str):
        """供面板调用切换（如检测完成后跳到「检测过程」）。"""
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
            <h3>单片机课程 · 作业自检与自评系统 v{__version__}</h3>
            <p>提交前用本地文件自检与自评的辅助工具。</p>
            <p><b>功能：</b></p>
            <ul>
                <li>✅ 检测过程：报告/源码格式、章节、思考题等规范校验</li>
                <li>📊 反馈与改进：按评分标准预测得分与改进建议</li>
            </ul>
            <p><b>说明：</b>编译检查需本机安装 make + arm-none-eabi-gcc；未安装时该项记 0 分但状态为「已跳过」，不代表代码无法编译。
            学习态度为教师评定项；组长加分由报告团队信息自动判定；机器预测分仅供参考。</p>
            <p><b>开发者：</b>汽车工程学院单片机课程组</p>
            """
        )

    def log(self, message: str):
        cur = self.content_stack.currentWidget()
        if hasattr(cur, "log"):
            cur.log(message)
