#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
教学管理系统主窗口
Teaching Management System Main Window

统一入口，支持多个功能模块：
- 查重检测
- 自动评分
- 反馈生成
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QStackedWidget, QListWidgetItem,
    QFrame, QMessageBox, QStatusBar, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

# 导入各模块面板
from tools.teaching_management_gui.ui.panels.data_source_panel import DataSourcePanel
from tools.teaching_management_gui.ui.panels.grading_panel import GradingPanel
from tools.teaching_management_gui.ui.panels.plagiarism_panel import PlagiarismPanel
from tools.teaching_management_gui.ui.panels.feedback_panel import FeedbackPanel
from tools.teaching_management_gui import __version__


# 全局视觉主题（与学生端同款：现代蓝 60-30-10 / 浅灰白底 / 白卡片）
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
    background-color: #eef3fb; color: #1f2937;
    border: 1px solid #c9d6ea; border-radius: 6px;
    padding: 6px 16px;
}
QPushButton:hover { background-color: #dfe9f9; border-color: #a9bede; }
QPushButton:pressed { background-color: #cfe0f7; }
QPushButton:disabled { color: #93a3b8; background-color: #f2f5fa; }

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    border: 1px solid #c9d6ea; border-radius: 5px;
    padding: 4px 8px;
    selection-background-color: #dbeafe;
}
QLineEdit:focus, QComboBox:focus { border: 1px solid #2563eb; }
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
QProgressBar::chunk { background-color: #2563eb; border-radius: 4px; }

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


class MainWindow(QMainWindow):
    """教学管理系统主窗口"""

    def __init__(self):
        super().__init__()
        self.setStyleSheet(APP_QSS)

        self.setup_ui()
        self.setup_menu_bar()

    def setup_ui(self):
        """设置界面"""
        self.setWindowTitle(f"单片机课程教学管理系统 v{__version__}")
        self.setMinimumSize(1200, 800)

        # 创建中央窗口
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. 侧边栏导航
        self.sidebar = self.create_sidebar()
        main_layout.addWidget(self.sidebar)

        # 添加分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setFixedWidth(1)
        main_layout.addWidget(separator)

        # 2. 内容区域（使用 QStackedWidget 切换不同面板）
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack, 1)

        # 3. 创建状态栏（必须在 create_panels 之前：create_panels 会触发
        #    导航首项切换 setCurrentRow(0) → on_navigation_changed，后者访问 self._status_bar）
        self._status_bar = self.statusBar()  # 调用方法获取 statusBar 对象
        self._status_bar.showMessage("欢迎使用教学管理系统")

        # 4. 创建并添加各个面板
        self.create_panels()
        self._disable_combo_wheel()   # 滚轮不再误改下拉选项

    def _disable_combo_wheel(self):
        """屏蔽所有下拉框的鼠标滚轮（防止滑轮滑过时误切选项）。"""
        from PyQt6.QtWidgets import QComboBox
        from PyQt6.QtCore import QObject, QEvent

        class _WheelBlocker(QObject):
            def eventFilter(self, obj, ev):
                if ev.type() == QEvent.Type.Wheel and isinstance(obj, QComboBox):
                    ev.ignore()
                    return True
                return False

        self._combo_wheel_filter = _WheelBlocker(self)
        for combo in self.findChildren(QComboBox):
            combo.installEventFilter(self._combo_wheel_filter)

    def create_sidebar(self):
        """创建侧边栏导航"""
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("""
            QWidget {
                background-color: #1e40af;
                color: white;
            }
            QListWidget {
                background-color: transparent;
                border: none;
                padding: 10px;
            }
            QListWidget::item {
                padding: 15px;
                margin: 2px 0;
                border-radius: 5px;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #2f6fed;
            }
            QListWidget::item:selected {
                background-color: #2563eb;
                font-weight: bold;
            }
            QLabel {
                padding: 10px;
                font-size: 14px;
                font-weight: bold;
            }
        """)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题
        title = QLabel("功能导航")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 导航列表
        self.nav_list = QListWidget()
        from PyQt6.QtCore import QSize
        self.nav_list.setIconSize(QSize(24, 24))

        # 添加导航项（两页结构：数据源 / 批阅与查重同页；反馈页默认隐藏）
        import os
        nav_items = [
            ("data_source", "① 数据源", "选择班级压缩包（可多选），选学期与课程类型"),
            ("grade_plag", "② 批阅与查重", "一键批阅+查重，出分数与相似对"),
        ]
        if os.environ.get("SHOW_FEEDBACK_PANEL", "") == "1":
            nav_items.append(("feedback", "💬 反馈生成", "生成学生反馈报告"))

        for item_id, item_name, item_tooltip in nav_items:
            list_item = QListWidgetItem(item_name)
            list_item.setData(Qt.ItemDataRole.UserRole, item_id)
            list_item.setToolTip(item_tooltip)
            self.nav_list.addItem(list_item)

        # 连接信号
        self.nav_list.currentRowChanged.connect(self.on_navigation_changed)

        layout.addWidget(self.nav_list)

        # 底部信息
        layout.addStretch()

        version_label = QLabel(f"v{__version__}<br>汽车工程学院单片机课程组")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #95a5a6; font-size: 12px;")
        layout.addWidget(version_label)

        return sidebar

    def create_panels(self):
        """创建并添加各个功能面板（两页：数据源 / 批阅与查重同页纵排）"""

        # 0. 数据源面板（集中选择输入）
        self.data_source_panel = DataSourcePanel(self)
        self.content_stack.addWidget(self.data_source_panel)

        # 1+2. 批阅与查重同页（纵排滚动，消除两页重复的进度/状态区）
        self.grading_panel = GradingPanel(self)
        self.plagiarism_panel = PlagiarismPanel(self)
        from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea
        page = QWidget()
        pv = QVBoxLayout(page)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.addWidget(self.grading_panel)
        pv.addWidget(self.plagiarism_panel)
        pv.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        self.content_stack.addWidget(scroll)

        # 3. 反馈面板（默认隐藏；保留实例供环境变量恢复时挂载）
        self.feedback_panel = FeedbackPanel(self)

        # 默认显示第一个面板（数据源）
        self.nav_list.setCurrentRow(0)

    def on_navigation_changed(self, index):
        """导航切换处理"""
        if index < 0:
            return

        # 切换面板
        self.content_stack.setCurrentIndex(index)

        # 获取当前面板信息
        item = self.nav_list.item(index)
        panel_id = item.data(Qt.ItemDataRole.UserRole)

        # 更新状态栏
        status_messages = {
            "data_source": "数据源 - 选择班级压缩包（可多选），选学期与课程类型",
            "grade_plag": "批阅与查重 - 一键出分数与相似对",
            "feedback": "反馈生成 - 生成学生反馈报告"
        }

        self._status_bar.showMessage(status_messages.get(panel_id, ""))

    def setup_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")

        open_action = QAction("打开压缩包(&O)", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.on_open_file)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 视图菜单（与两页导航一致）
        view_menu = menubar.addMenu("视图(&V)")

        data_source_action = QAction("数据源(&D)", self)
        data_source_action.setShortcut("Ctrl+D")
        data_source_action.triggered.connect(lambda: self.nav_list.setCurrentRow(0))
        view_menu.addAction(data_source_action)

        grade_plag_action = QAction("批阅与查重(&G)", self)
        grade_plag_action.setShortcut("Ctrl+G")
        grade_plag_action.triggered.connect(lambda: self.nav_list.setCurrentRow(1))
        view_menu.addAction(grade_plag_action)

        # 工具菜单
        tools_menu = menubar.addMenu("工具(&T)")

        export_action = QAction("导出报告(&E)", self)
        export_action.triggered.connect(self.on_export_report)
        tools_menu.addAction(export_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")

        intro_action = QAction("功能介绍(&I)", self)
        intro_action.triggered.connect(self.show_intro)
        help_menu.addAction(intro_action)

        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def on_open_file(self):
        """打开文件"""
        # 根据当前面板执行相应的打开操作
        current_panel = self.content_stack.currentWidget()

        if hasattr(current_panel, 'select_zip_file'):
            current_panel.select_zip_file()

    def on_export_report(self):
        """导出报告"""
        current_panel = self.content_stack.currentWidget()

        if hasattr(current_panel, 'export_report'):
            current_panel.export_report()

    def show_intro(self):
        """简短功能介绍（弹窗，不占页面）"""
        QMessageBox.information(
            self, "功能介绍",
            "<b>两步完成批阅：</b><br>"
            "① <b>数据源</b>：选学期/课程类型 → 添加班级压缩包（可多选）<br>"
            "② <b>批阅与查重</b>：点「🚀 一键：批阅→查重」，自动出分数与相似对<br><br>"
            "<b>常用操作：</b><br>"
            "· 结果表<b>双击学生行</b> → 现场调整教师实测项（出勤/答辩等，改完自动重算总分）<br>"
            "· 「查看班级报告」→ 分数分布与排名；「导出个人报告」→ 批量导出<br>"
            "· 调整查重阈值/方法后，可用「↺ 仅重跑查重」单独复跑<br><br>"
            "<b>说明：</b>详细改进反馈由学生在学生端自检获得，本系统专注评分与查重。"
        )

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于",
            f"""
            <h3>单片机课程教学管理系统 v{__version__}</h3>
            <p>单片机课程教学辅助工具（评分 / 查重 / 成绩管理）</p>
            <p><b>功能模块：</b></p>
            <ul>
                <li>📁 数据源 - 班级压缩包选择</li>
                <li>📊 自动评分 - 批量批阅学生作业</li>
                <li>🔍 查重检测 - 检测作业相似度</li>
            </ul>
            <p><b>开发者：</b>汽车工程学院单片机课程组</p>
            """
        )

    def log(self, message):
        """输出日志（委托给当前面板）"""
        current_panel = self.content_stack.currentWidget()
        if hasattr(current_panel, 'log'):
            current_panel.log(message)

    def closeEvent(self, event):
        """关闭前停止后台 worker，避免在批阅/查重/反馈运行中销毁 QThread。

        学生端 MainWindow 已有等价 closeEvent→cleanup_worker；教师端此前缺失，
        运行中点 X/Ctrl+Q 会让仍 running 的 QThread 被销毁（PyQt6 警告/闪退），
        并留下孤儿 make/gcc 子进程。任一 worker 在跑时先确认，给教师保留长任务。
        """
        panels = [getattr(self, name, None)
                  for name in ("grading_panel", "plagiarism_panel", "feedback_panel")]
        if any(p is not None and hasattr(p, "is_running") and p.is_running() for p in panels):
            if QMessageBox.question(
                self, "确认退出",
                "有任务正在进行中，退出将终止后台任务（当前编译/比对阶段会运行至结束）。\n确认退出？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        for panel in panels:
            if panel is not None and hasattr(panel, "stop_and_wait"):
                try:
                    panel.stop_and_wait()
                except Exception:
                    pass
        super().closeEvent(event)
