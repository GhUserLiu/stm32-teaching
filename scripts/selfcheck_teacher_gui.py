# -*- coding: utf-8 -*-
"""教师端自检：全包编译 + 离屏实例化 + 关键控件存在性"""
import os, sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, 'src')
fails = []

import compileall
ok = compileall.compile_dir('src/tools/teaching_management_gui', quiet=2, force=True)
print('1) 全包编译:', 'OK' if ok else 'FAIL')
if not ok: fails.append('compile')

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
app = QApplication([])
from tools.teaching_management_gui.ui.main_window import MainWindow
w = MainWindow()
nav_labels = [w.nav_list.item(i).text() for i in range(w.nav_list.count())]
print('2) 主窗口实例化: OK  导航:', nav_labels, ' 栈页数:', w.content_stack.count())
for i in range(w.nav_list.count()):
    w.nav_list.setCurrentRow(i)

dsp, gp, pp = w.data_source_panel, w.grading_panel, w.plagiarism_panel
checks = {
    '学期下拉': hasattr(dsp, 'semester_edit'),
    '专业下拉': hasattr(dsp, 'major_combo'),
    '开始批阅按钮(数据源页)': hasattr(dsp, 'start_grading_btn'),
    '类型下拉': hasattr(dsp, 'ctype_combo'),
    '一键按钮': getattr(gp, 'one_click_btn', None) is None,
    '结果表': hasattr(gp, 'results_table'),
    '调分对话框方法': hasattr(gp, '_open_adjust_dialog'),
    '查重小按钮': hasattr(pp, 'start_btn'),
    '查重独立导航已并': not any(('查重' in lbl) and ('批阅' not in lbl) for lbl in nav_labels),
}
for name, passed in checks.items():
    print(f'   {name}:', 'OK' if passed else 'FAIL')
    if not passed: fails.append(name)

print('== 教师端自检:', '全部通过 ✅' if not fails else f'失败: {fails}')
sys.exit(0 if not fails else 1)
