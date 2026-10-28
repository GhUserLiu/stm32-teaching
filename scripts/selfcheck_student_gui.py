# -*- coding: utf-8 -*-
"""学生端自检：全包编译 + 离屏实例化主窗口 + 关键逻辑单测"""
import os, sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, 'src')
root = os.getcwd()

fails = []

# 1) 全包编译
import compileall
ok = compileall.compile_dir('src/tools/student_submission_gui', quiet=2, force=True)
print('1) 全包编译:', 'OK' if ok else 'FAIL')
if not ok: fails.append('compile')

# 2) 离屏实例化主窗口（构造器/信号/refresh 全链路）
from PyQt6.QtWidgets import QApplication
app = QApplication([])
from tools.student_submission_gui.ui.main_window import MainWindow, NAV_ITEMS, APP_QSS
w = MainWindow()
w.show()
print('2) 主窗口实例化: OK  导航项:', [n[1] for n in NAV_ITEMS])
# 导航切换两页
for i in range(len(NAV_ITEMS)):
    w.nav_list.setCurrentRow(i)
print('   页面切换: OK  栈页数 =', w.content_stack.count())

# 3) 关键控件存在性（去重重构后的引用完整性）
fp, cp, gp = w.files_panel, w.check_panel, w.grade_panel
checks = {
    '学期下拉': hasattr(fp, 'semester_combo'),
    '专业下拉': hasattr(fp, 'major_combo'),
    '课程类型下拉': hasattr(fp, 'ctype_combo'),
    '实验下拉': hasattr(fp, 'experiment_combo'),
    '②页进度条': hasattr(cp, 'run_progress'),
    '②页日志': hasattr(cp, 'run_log'),
    '②页问题表': hasattr(cp, 'issues_table'),
    '②页已删徽标': not hasattr(cp, 'badge'),
    '③得分标签': hasattr(gp, 'score_label'),
    '③类别表': hasattr(gp, 'cat_table'),
    '①页无日志区': not hasattr(fp, 'log_view'),
}
for name, passed in checks.items():
    print(f'   {name}:', 'OK' if passed else 'FAIL')
    if not passed: fails.append(name)

# 4) 实验四级联动（离屏下操作 combo）
sem = fp.semester_combo
sem_names = [sem.itemText(i) for i in range(sem.count())]
print('4) 学期列表:', sem_names)
sem.setCurrentText('2026-秋季') if '2026-秋季' in sem_names else None
maj = fp.major_combo
maj_names = [maj.itemText(i) for i in range(maj.count())]
print('   专业列表:', maj_names)
if '新能源' in maj_names: maj.setCurrentText('新能源')
ct = fp.ctype_combo
ct_names = [ct.itemText(i) for i in range(ct.count())]
print('   类型列表:', ct_names)
if '整周实训' in ct_names: ct.setCurrentText('整周实训')
exp_names = [fp.experiment_combo.itemText(i) for i in range(fp.experiment_combo.count())]
print('   实验列表(新能源+整周实训):', exp_names)
if not any('智能座舱' in n for n in exp_names):
    fails.append('联动过滤')

# 5) is_runnable 逻辑（报告可选）
from tools.student_submission_gui.submission_state import shared
from tools.student_submission_gui.id_card import StudentIdentity
s = shared()
s.update(identity=StudentIdentity('新能源2601班', '26010101001', '张三'),
         experiment_code='08-cabin-thermal', report_path=None, source_path=None)
r0 = s.is_runnable()
s.update(report_path='不存在的路径.docx', source_path=None)
r1 = s.is_runnable()
print(f'5) 全空不可跑: {not r0} / 假报告+无源码不可跑: {not r1}',
      'OK' if (not r0 and not r1) else 'FAIL')
if r0 or r1: fails.append('is_runnable')

print()
print('== 自检结果:', '全部通过 ✅' if not fails else f'失败项: {fails}')
