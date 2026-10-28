# -*- coding: utf-8 -*-
"""端到端联调：08-cabin-thermal 学生自检/教师批阅链路验证（模拟提交1份）
走学期模板路径：data/semesters/2026-秋季/"""
import sys, zipfile, shutil
from pathlib import Path

sys.path.insert(0, 'src')
ROOT = Path('.')
SEM = '2026-秋季'
CLS = '新能源测试班'
EXP = '08-cabin-thermal'

# 1) 构造提交目录（processor 约定布局：<学期>/<班级>/<实验>/reports + source）
exp_dir = ROOT / 'data' / 'teaching' / SEM / CLS / EXP
if exp_dir.exists():
    shutil.rmtree(exp_dir)
sub_dir = exp_dir / 'reports'
src_dir = exp_dir / 'source'
sub_dir.mkdir(parents=True)
src_dir.mkdir(parents=True)

# 1a) 报告（含 rubric 关键词的“合格”样例，docx）
report = """# 智能座舱温控系统设计 实验报告

## 1、实训日志与过程资料
实训日志共4次，记录了每日现象记录与问题记录。整理了接线引脚表和数据记录表。

## 2、系统设计
系统框图按感知、决策、执行三层划分。引脚表：DHT11=PB12，热敏=PA6，OLED=PB6/PB7。
组内分工：A负责驱动，B负责联调，C负责报告。

## 3、实现说明
DHT11 采用单总线时序读取，ADC 采样均值滤波；PWM 占空比控制风扇，
OLED 软件 I2C 显示，蜂鸣器报警。温度阈值 28 度滞回控制，30 度全速，32 度报警。

## 4、测试与分析
测试数据记录了温度、湿度、光照共 10 组，对比 DHT11 与热敏读数并分析偏差。
遇到的问题与解决：串口乱码（波特率）、风扇不转（STBY），排查过程见日志。

## 5、总结与参考文献
总结收获：掌握了 HAL 库外设配置与非阻塞调度。体会：先仿真后实物流程规范。
参考文献
[1] STM32F10x 参考手册
[2] 徐亮. STM32单片机仿真开发实例
"""
sid, name = '23071140101', '张三'
from docx import Document
doc = Document()
for line in report.strip().splitlines():
    line = line.strip()
    if not line:
        continue
    if line.startswith('# '):
        doc.add_heading(line[2:], level=0)
    elif line.startswith('## '):
        doc.add_heading(line[3:], level=1)
    else:
        doc.add_paragraph(line)
report_path = sub_dir / f'{CLS}-{sid}-{name}-实验报告.docx'
doc.save(str(report_path))

# 1b) 源码：解压成目录 source/<班级>-<学号>-<姓名>-源代码/（processor 约定）
src_root = ROOT / 'src' / 'projects' / 'f1-cabin-thermal'
f1 = ROOT / 'src' / 'common-f1'
student_src = src_dir / f'{CLS}-{sid}-{name}-源代码'
student_src.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(str(student_src / '_pack.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
    for base, tag in ((src_root, ''), (f1, 'common-f1/')):
        for p in base.rglob('*'):
            if p.is_file() and 'build' not in p.parts:
                z.write(p, tag + p.relative_to(base).as_posix())
with zipfile.ZipFile(str(student_src / '_pack.zip')) as z:
    z.extractall(str(student_src))
(student_src / '_pack.zip').unlink()
print('submission ready:', report_path.name, '->', student_src.name)

# 2) 跑完整批阅流水线（学期模板路径）
from tools.auto_grading.facade import AutoGradingFacade
from tools.auto_grading.config import AutoGradingConfig
facade = AutoGradingFacade(AutoGradingConfig(semester=SEM))
result = facade.run_full_pipeline(None, CLS, EXP, skip_organization=True)
print('submissions:', result.total_submissions, 'graded:', result.successful_graded)
for gr in result.grading_results:
    print('==', gr.student_id)
    for cs in gr.category_scores:
        print('  ', repr(cs)[:150])
