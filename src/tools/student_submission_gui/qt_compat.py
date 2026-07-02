#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PyQt5 / PyQt6 兼容层（学生端 GUI 专用）
PyQt5 / PyQt6 compatibility shim for the student-side GUI.

目的
----
让学生端 GUI 用「同一份代码」跑在两个绑定上：

- **PyQt6**：开发机 / 教师端主线（默认，产物仅支持 Windows 10+）。
- **PyQt5**：Windows 7 兼容构建（CPython 3.8 + PyQt5==5.15.2；Qt 5.15.2 是
  最后一个官方支持 Win7 的 Qt，产物覆盖 Win7 / 8.1 / 10 / 11）。

做法
----
1. 优先导入 PyQt6，缺失则回退 PyQt5。
2. **枚举**：业务调用点统一保留 PyQt6 的全限定写法
   （如 ``Qt.AlignmentFlag.AlignCenter``、``QHeaderView.ResizeMode.Stretch``）。
   PyQt6 原生支持；PyQt5 下由 :func:`_patch_pyqt5_namespaced_enums` 把这些
   命名空间挂到对应类上。关键：命名空间成员**直接指向 PyQt5 的原生扁平枚举值**
   （如 ``Qt.AlignmentFlag.AlignCenter is Qt.AlignCenter``），而非再包一层枚举——
   这样传给 Qt 的严格类型检查 setter、做 ``|`` / ``==`` 都按原生值工作。
   ⇒ **迁移无需改动任何枚举调用点**。
3. **QAction**：PyQt6 在 ``QtGui``、PyQt5 在 ``QtWidgets``，本层统一导出。
4. **事件循环**：:func:`exec_app` 屏蔽 ``exec()`` / ``exec_()`` 差异。

用法
----
学生端 GUI 各模块把 ``from PyQt6.QtXxx import ...`` 改为
``from <本包>.qt_compat import ...``：``main.py``（作为入口）用绝对导入
``from tools.student_submission_gui.qt_compat import ...``，其余子模块用相对导入
（``ui/*.py`` → ``from ..qt_compat``；``ui/panels/*.py`` → ``from ...qt_compat``）。
"""


def _ns(**mapping):
    """构造一个轻量命名空间，其属性值即传入的原生枚举值。

    用 ``type`` 造类而非 :class:`enum.IntEnum`，是为了让成员**就是** PyQt5 的原生
    枚举值（如 ``Qt.AlignCenter``），从而能直接传给 sip 严格类型检查的 setter，
    且 ``|`` / ``==`` 等 flag 语义与原生一致。
    """
    return type("_qt_ns", (), mapping)


# --------------------------------------------------------------------- #
# PyQt5 命名空间枚举补丁（仅 PyQt5 调用）
# --------------------------------------------------------------------- #
def _patch_pyqt5_namespaced_enums() -> None:
    """在 PyQt5 上补齐 PyQt6 风格的「类.枚举族.成员」三级访问。

    PyQt5 只有扁平枚举（``Qt.AlignCenter``），没有 ``Qt.AlignmentFlag`` 命名空间。
    这里把命名空间挂到对应类上，且成员直接取 PyQt5 的原生扁平值，使
    ``Qt.AlignmentFlag.AlignCenter`` 等价于原生 ``Qt.AlignCenter``。
    函数体引用的 Qt/QFrame 等为本模块全局名，在下方导入块中绑定后才会被调用。
    """

    # --- Qt（QtCore.Qt）---
    Qt.AlignmentFlag = _ns(
        AlignLeft=Qt.AlignLeft,
        AlignRight=Qt.AlignRight,
        AlignHCenter=Qt.AlignHCenter,
        AlignTop=Qt.AlignTop,
        AlignBottom=Qt.AlignBottom,
        AlignVCenter=Qt.AlignVCenter,
        AlignCenter=Qt.AlignCenter,
        AlignJustify=Qt.AlignJustify,
    )
    Qt.ItemDataRole = _ns(
        DisplayRole=Qt.DisplayRole,
        DecorationRole=Qt.DecorationRole,
        EditRole=Qt.EditRole,
        ToolTipRole=Qt.ToolTipRole,
        StatusTipRole=Qt.StatusTipRole,
        WhatsThisRole=Qt.WhatsThisRole,
        FontRole=Qt.FontRole,
        TextAlignmentRole=Qt.TextAlignmentRole,
        BackgroundRole=Qt.BackgroundRole,
        ForegroundRole=Qt.ForegroundRole,
        SizeHintRole=Qt.SizeHintRole,
        UserRole=Qt.UserRole,
    )
    Qt.GlobalColor = _ns(
        white=Qt.white,
        black=Qt.black,
        red=Qt.red,
        darkRed=Qt.darkRed,
        green=Qt.green,
        darkGreen=Qt.darkGreen,
        blue=Qt.blue,
        gray=Qt.gray,
        lightGray=Qt.lightGray,
        darkGray=Qt.darkGray,
        cyan=Qt.cyan,
        magenta=Qt.magenta,
        yellow=Qt.yellow,
        transparent=Qt.transparent,
    )

    # --- QFrame（QtWidgets.QFrame）---
    QFrame.Shape = _ns(
        NoFrame=QFrame.NoFrame,
        Box=QFrame.Box,
        Panel=QFrame.Panel,
        StyledPanel=QFrame.StyledPanel,
        HLine=QFrame.HLine,
        VLine=QFrame.VLine,
        WinPanel=QFrame.WinPanel,
    )
    QFrame.Shadow = _ns(
        Plain=QFrame.Plain,
        Raised=QFrame.Raised,
        Sunken=QFrame.Sunken,
    )

    # --- QMessageBox（QtWidgets.QMessageBox）---
    QMessageBox.StandardButton = _ns(
        NoButton=QMessageBox.NoButton,
        Ok=QMessageBox.Ok,
        Open=QMessageBox.Open,
        Save=QMessageBox.Save,
        Cancel=QMessageBox.Cancel,
        Close=QMessageBox.Close,
        Discard=QMessageBox.Discard,
        Apply=QMessageBox.Apply,
        Reset=QMessageBox.Reset,
        RestoreDefaults=QMessageBox.RestoreDefaults,
        Help=QMessageBox.Help,
        SaveAll=QMessageBox.SaveAll,
        Yes=QMessageBox.Yes,
        YesToAll=QMessageBox.YesToAll,
        No=QMessageBox.No,
        NoToAll=QMessageBox.NoToAll,
        Abort=QMessageBox.Abort,
        Retry=QMessageBox.Retry,
        Ignore=QMessageBox.Ignore,
    )

    # --- QTableWidget（QtWidgets.QTableWidget）---
    QTableWidget.EditTrigger = _ns(
        NoEditTriggers=QTableWidget.NoEditTriggers,
        CurrentChanged=QTableWidget.CurrentChanged,
        DoubleClicked=QTableWidget.DoubleClicked,
        SelectedClicked=QTableWidget.SelectedClicked,
        EditKeyPressed=QTableWidget.EditKeyPressed,
        AnyKeyPressed=QTableWidget.AnyKeyPressed,
        AllEditTriggers=QTableWidget.AllEditTriggers,
    )
    QTableWidget.SelectionBehavior = _ns(
        SelectItems=QTableWidget.SelectItems,
        SelectRows=QTableWidget.SelectRows,
        SelectColumns=QTableWidget.SelectColumns,
    )

    # --- QHeaderView（QtWidgets.QHeaderView）---
    QHeaderView.ResizeMode = _ns(
        Interactive=QHeaderView.Interactive,
        Stretch=QHeaderView.Stretch,
        Fixed=QHeaderView.Fixed,
        ResizeToContents=QHeaderView.ResizeToContents,
        Custom=QHeaderView.Custom,
    )


# --------------------------------------------------------------------- #
# 选择绑定：优先 PyQt6，缺失则回退 PyQt5
# --------------------------------------------------------------------- #
try:
    from PyQt6.QtWidgets import (  # noqa: F401
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QListWidget, QStackedWidget, QListWidgetItem, QFrame, QMessageBox,
        QLabel, QGridLayout, QGroupBox, QPushButton, QTableWidget,
        QTableWidgetItem, QHeaderView, QFormLayout, QLineEdit, QComboBox,
        QFileDialog, QProgressBar, QPlainTextEdit,
    )
    from PyQt6.QtCore import Qt, QSize, QObject, pyqtSignal, QThread, QUrl  # noqa: F401
    from PyQt6.QtGui import QAction, QFont, QColor, QDesktopServices  # noqa: F401

    _IS_QT6 = True
except ImportError:  # pragma: no cover - 仅 Win7 构建环境（PyQt5）触发
    from PyQt5.QtWidgets import (  # noqa: F401
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QListWidget, QStackedWidget, QListWidgetItem, QFrame, QMessageBox,
        QLabel, QGridLayout, QGroupBox, QPushButton, QTableWidget,
        QTableWidgetItem, QHeaderView, QFormLayout, QLineEdit, QComboBox,
        QFileDialog, QProgressBar, QPlainTextEdit, QAction,
    )
    from PyQt5.QtCore import Qt, QSize, QObject, pyqtSignal, QThread, QUrl  # noqa: F401
    from PyQt5.QtGui import QFont, QColor, QDesktopServices  # noqa: F401

    _IS_QT6 = False
    _patch_pyqt5_namespaced_enums()


# --------------------------------------------------------------------- #
# 事件循环（屏蔽 exec() / exec_() 差异）
# --------------------------------------------------------------------- #
def exec_app(app):
    """进入 Qt 主事件循环。PyQt6 用 exec()，PyQt5 用 exec_()。"""
    return app.exec() if _IS_QT6 else app.exec_()
