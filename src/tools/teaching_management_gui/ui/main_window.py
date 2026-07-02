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


class MainWindow(QMainWindow):
    """教学管理系统主窗口"""

    def __init__(self):
        super().__init__()

        self.setup_ui()
        self.setup_menu_bar()

    def setup_ui(self):
        """设置界面"""
        self.setWindowTitle(f"教学管理系统 v{__version__}")
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

    def create_sidebar(self):
        """创建侧边栏导航"""
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("""
            QWidget {
                background-color: #2c3e50;
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
                background-color: #34495e;
            }
            QListWidget::item:selected {
                background-color: #3498db;
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

        # 添加导航项
        nav_items = [
            ("data_source", "📁 数据源", "选择班级压缩包（可多选）"),
            ("grading", "📊 自动评分", "自动批阅学生作业"),
            ("plagiarism", "🔍 查重检测", "检测作业相似度"),
            ("feedback", "💬 反馈生成", "生成学生反馈报告"),
        ]

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

        version_label = QLabel(f"v{__version__}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #95a5a6; font-size: 12px;")
        layout.addWidget(version_label)

        return sidebar

    def create_panels(self):
        """创建并添加各个功能面板"""

        # 0. 数据源面板（集中选择输入）
        self.data_source_panel = DataSourcePanel(self)
        self.content_stack.addWidget(self.data_source_panel)

        # 1. 自动评分面板
        self.grading_panel = GradingPanel(self)
        self.content_stack.addWidget(self.grading_panel)

        # 2. 查重检测面板
        self.plagiarism_panel = PlagiarismPanel(self)
        self.content_stack.addWidget(self.plagiarism_panel)

        # 3. 反馈生成面板
        self.feedback_panel = FeedbackPanel(self)
        self.content_stack.addWidget(self.feedback_panel)

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
            "data_source": "数据源 - 选择班级压缩包（可多选），供各面板共用",
            "grading": "自动评分 - 批量批阅学生作业",
            "plagiarism": "查重检测 - 检测作业相似度",
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

        # 视图菜单
        view_menu = menubar.addMenu("视图(&V)")

        data_source_action = QAction("数据源(&D)", self)
        data_source_action.setShortcut("Ctrl+D")
        data_source_action.triggered.connect(lambda: self.nav_list.setCurrentRow(0))
        view_menu.addAction(data_source_action)

        grading_action = QAction("自动评分(&G)", self)
        grading_action.setShortcut("Ctrl+G")
        grading_action.triggered.connect(lambda: self.nav_list.setCurrentRow(1))
        view_menu.addAction(grading_action)

        plagiarism_action = QAction("查重检测(&P)", self)
        plagiarism_action.setShortcut("Ctrl+P")
        plagiarism_action.triggered.connect(lambda: self.nav_list.setCurrentRow(2))
        view_menu.addAction(plagiarism_action)

        feedback_action = QAction("反馈生成(&F)", self)
        feedback_action.setShortcut("Ctrl+F")
        feedback_action.triggered.connect(lambda: self.nav_list.setCurrentRow(3))
        view_menu.addAction(feedback_action)

        # 工具菜单
        tools_menu = menubar.addMenu("工具(&T)")

        export_action = QAction("导出报告(&E)", self)
        export_action.triggered.connect(self.on_export_report)
        tools_menu.addAction(export_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")

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

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于",
            f"""
            <h3>教学管理系统 v{__version__}</h3>
            <p>STM32F407 嵌入式教学平台专用工具</p>
            <p><b>功能模块：</b></p>
            <ul>
                <li>📊 自动评分 - 批量批阅学生作业</li>
                <li>🔍 查重检测 - 检测作业相似度</li>
                <li>💬 反馈生成 - 生成学生反馈报告</li>
            </ul>
            <p><b>开发者：</b>STM32F407教学团队</p>
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
