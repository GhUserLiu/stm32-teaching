#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成补充图片"""

import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

import matplotlib.pyplot as plt
import matplotlib
import json
from matplotlib.patches import Rectangle, FancyBboxPatch
import numpy as np

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

# 输出目录
output_dir = r'd:\4-Workspace\MCU_Research\project_test\NewProjectF407\关于开展2026年山西省教师人工智能应用案例征集活动的通知\2.创AI案例征集指南与模板\创AI模板材料\pic'

# 数据路径
data_dir = r'd:\4-Workspace\MCU_Research\project_test\NewProjectF407\docs\teaching\2026-春季\汽服2302B班\07-car-gear\results'

print('开始生成补充图片...')

# === 图片11：查重结果界面 ===
print('\\n生成图片11: 查重结果界面')
fig, ax = plt.subplots(figsize=(12, 7))
ax.axis('off')
ax.set_xlim(0, 12)
ax.set_ylim(0, 8)

# 标题栏
title_bar = FancyBboxPatch((0.5, 7.2), 11, 0.5, boxstyle='round,pad=0.02',
                           facecolor='#2c3e50', edgecolor='black')
ax.add_patch(title_bar)
ax.text(6, 7.45, '查重检测结果 - 汽服2302B班', ha='center', va='center',
        fontsize=14, fontweight='bold', color='white')

# 左侧面板 - 文件列表
left_panel = FancyBboxPatch((0.5, 1), 4, 6, boxstyle='round,pad=0.02',
                            facecolor='#ecf0f1', edgecolor='#bdc3c7')
ax.add_patch(left_panel)
ax.text(2.5, 6.8, '报告文件列表', ha='center', fontsize=12, fontweight='bold')

# 模拟文件列表
files = ['董雨航_23071140201.docx', '陈乐莹_23071140202.docx', '董欣怡_23071140203.docx',
         '崔向宇_23071140242.docx', '张攀博_23071140240.docx', '...']
for i, file in enumerate(files):
    y_pos = 6.2 - i * 0.5
    ax.text(0.8, y_pos, f'{i+1}.', fontsize=10)
    ax.text(1.2, y_pos, file[:20] + '...' if len(file) > 20 else file, fontsize=9)

# 右侧面板 - 相似度结果
right_panel = FancyBboxPatch((5, 1), 6.5, 6, boxstyle='round,pad=0.02',
                             facecolor='white', edgecolor='#bdc3c7')
ax.add_patch(right_panel)
ax.text(8.25, 6.8, '相似度检测结果', ha='center', fontsize=12, fontweight='bold')

# 模拟相似度结果
results = [
    {'name': '董雨航 vs 张攀博', 'sim': 99.2, 'status': '🔴 高风险'},
    {'name': '董雨航 vs 陈子默', 'sim': 97.3, 'status': '🔴 高风险'},
    {'name': '董雨航 vs 崔向宇', 'sim': 72.1, 'status': '🟡 中风险'},
    {'name': '陈乐莹 vs 董欣怡', 'sim': 45.2, 'status': '🟢 正常'},
]

for i, result in enumerate(results):
    y_pos = 6 - i * 0.8
    # 结果条
    bar_color = '#e74c3c' if result['sim'] > 80 else '#f39c12' if result['sim'] > 60 else '#2ecc71'
    result_bar = FancyBboxPatch((5.3, y_pos - 0.25), 5.8, 0.5, boxstyle='round,pad=0.02',
                                facecolor='#f8f9fa', edgecolor=bar_color, linewidth=2)
    ax.add_patch(result_bar)

    ax.text(5.5, y_pos, result['name'], fontsize=9)
    ax.text(10.5, y_pos, f"{result['sim']}%", fontsize=10, fontweight='bold', color=bar_color)
    ax.text(5.5, y_pos - 0.2, result['status'], fontsize=8)

# 统计信息
stats_box = FancyBboxPatch((5.3, 0.5), 5.8, 0.4, boxstyle='round,pad=0.02',
                           facecolor='#3498db', edgecolor='black')
ax.add_patch(stats_box)
ax.text(8.25, 0.7, '检测完成: 41份报告 | 平均相似度: 68.7%',
        ha='center', va='center', fontsize=10, color='white')

plt.tight_layout()
plt.savefig(os.path.join(output_dir, '11_查重结果界面.png'), dpi=150, bbox_inches='tight')
plt.close()
print('  ✓ 完成')

# === 图片12：设置界面 ===
print('\\n生成图片12: 设置界面')
fig, ax = plt.subplots(figsize=(12, 7))
ax.axis('off')
ax.set_xlim(0, 12)
ax.set_ylim(0, 8)

# 标题栏
title_bar = FancyBboxPatch((0.5, 7.2), 11, 0.5, boxstyle='round,pad=0.02',
                           facecolor='#2c3e50', edgecolor='black')
ax.add_patch(title_bar)
ax.text(6, 7.45, '系统设置', ha='center', va='center',
        fontsize=14, fontweight='bold', color='white')

# 选项卡
tabs = ['通用设置', '评分标准', '查重设置', '报告输出']
tab_x = [0.5, 3, 5.5, 8]
colors_tab = ['#3498db', '#ecf0f1', '#ecf0f1', '#ecf0f1']
for i, (tab, x, color) in enumerate(zip(tabs, tab_x, colors_tab)):
    tab_box = FancyBboxPatch((x, 6.5), 2.5, 0.5, boxstyle='round,pad=0.02',
                              facecolor=color, edgecolor='#bdc3c7')
    ax.add_patch(tab_box)
    ax.text(x + 1.25, 6.75, tab, ha='center', va='center', fontsize=11,
            fontweight='bold' if i == 0 else False)

# 设置面板
settings_panel = FancyBboxPatch((0.5, 1), 11, 5.3, boxstyle='round,pad=0.02',
                                facecolor='white', edgecolor='#bdc3c7')
ax.add_patch(settings_panel)

# 设置项
settings = [
    {'label': '相似度阈值:', 'value': '65%', 'type': 'slider'},
    {'label': '默认算法:', 'value': 'Hybrid (混合)', 'type': 'dropdown'},
    {'label': '启用语义检测:', 'value': '是', 'type': 'checkbox'},
    {'label': '输出格式:', 'value': 'Excel / HTML / Markdown', 'type': 'multi'},
]

for i, setting in enumerate(settings):
    y_pos = 6 - i * 0.9
    # 标签
    ax.text(1.5, y_pos, setting['label'], fontsize=11, va='center')
    # 控件
    if setting['type'] == 'slider':
        # 滑块
        ax.plot([4, 9], [y_pos, y_pos], color='#bdc3c7', lw=3)
        ax.plot([6.5], [y_pos], 'o', color='#3498db', markersize=12)
        ax.text(9.5, y_pos, setting['value'], fontsize=10, va='center', color='#3498db')
    elif setting['type'] == 'dropdown':
        # 下拉框
        dropdown = FancyBboxPatch((4, y_pos - 0.2), 3, 0.4, boxstyle='round,pad=0.02',
                                  facecolor='white', edgecolor='#95a5a6')
        ax.add_patch(dropdown)
        ax.text(5.5, y_pos, setting['value'], fontsize=10, va='center')
        ax.text(7.5, y_pos, '▼', fontsize=8, va='center')
    elif setting['type'] == 'checkbox':
        # 复选框
        checkbox = Rectangle((4, y_pos - 0.15), 0.3, 0.3, facecolor='#3498db', edgecolor='black')
        ax.add_patch(checkbox)
        ax.text(4.15, y_pos, '✓', fontsize=10, color='white', va='center')
    elif setting['type'] == 'multi':
        # 多选框
        for j, opt in enumerate(['Excel', 'HTML', 'Markdown']):
            opt_x = 4 + j * 2
            checkbox = Rectangle((opt_x, y_pos - 0.15), 0.25, 0.25, facecolor='#3498db', edgecolor='black')
            ax.add_patch(checkbox)
            ax.text(opt_x + 0.12, y_pos, '✓', fontsize=8, color='white', va='center')
            ax.text(opt_x + 0.4, y_pos, opt, fontsize=9, va='center')

# 保存按钮
save_btn = FancyBboxPatch((9, 0.3), 2, 0.5, boxstyle='round,pad=0.02',
                          facecolor='#2ecc71', edgecolor='black')
ax.add_patch(save_btn)
ax.text(10, 0.55, '保存设置', ha='center', va='center', fontsize=11, fontweight='bold', color='white')

plt.tight_layout()
plt.savefig(os.path.join(output_dir, '12_设置界面.png'), dpi=150, bbox_inches='tight')
plt.close()
print('  ✓ 完成')

# === 图片13：评分标准配置文件 ===
print('\\n生成图片13: 评分标准配置文件')
fig, ax = plt.subplots(figsize=(12, 8))
ax.axis('off')

ax.text(0.5, 0.95, '评分标准配置文件 (rubric.json)', ha='left', va='top',
        fontsize=16, fontweight='bold', transform=ax.transAxes)

# 模拟JSON内容
json_content = '''{
  "dimensions": [
    {
      "name": "技术准确性",
      "weight": 0.30,
      "criteria": [
        {"desc": "GPIO配置正确", "points": 10, "keywords": ["GPIO引脚", "配置模式"]},
        {"desc": "中断设置正确", "points": 10, "keywords": ["中断优先级", "触发方式"]},
        {"desc": "状态机逻辑完整", "points": 10, "keywords": ["状态切换", "循环逻辑"]}
      ]
    },
    {
      "name": "内容完整性",
      "weight": 0.25,
      "criteria": [
        {"desc": "实验原理清晰", "points": 8, "keywords": ["原理", "工作机制"]},
        {"desc": "硬件连接图完整", "points": 8, "keywords": ["连接图", "引脚图"]},
        {"desc": "代码实现完整", "points": 10, "keywords": ["完整代码", "功能实现"]}
      ]
    },
    {
      "name": "分析深度",
      "weight": 0.15,
      "criteria": [
        {"desc": "问题分析透彻", "points": 8, "keywords": ["问题分析", "原因分析"]},
        {"desc": "解决方案讨论", "points": 7, "keywords": ["解决方案", "改进建议"]}
      ]
    }
  ],
  "grading_scale": {
    "A": {"min": 90, "desc": "优秀"},
    "B": {"min": 80, "desc": "良好"},
    "C": {"min": 70, "desc": "中等"},
    "D": {"min": 60, "desc": "及格"},
    "F": {"min": 0, "desc": "不及格"}
  }
}'''

# 绘制代码框
code_box = FancyBboxPatch((0.5, 0.5), 11, 8, boxstyle='round,pad=0.02',
                           facecolor='#2c3e50', edgecolor='black')
ax.add_patch(code_box)

# 逐行绘制JSON
lines = json_content.split('\n')
y_start = 7.8
for i, line in enumerate(lines):
    y_pos = y_start - i * 0.25
    if y_pos < 1:
        break
    # 简单的语法高亮
    color = '#ecf0f1'  # 默认白色
    if '"' in line and ':' in line:
        # 键值对
        parts = line.split(':')
        if len(parts) >= 2:
            ax.text(0.8, y_pos, parts[0], fontsize=9, color='#3498db')
            ax.text(0.8 + len(parts[0]) * 0.05, y_pos, ':', fontsize=9, color='#95a5a6')
            ax.text(0.8 + len(parts[0]) * 0.05 + 0.1, y_pos, parts[1].strip(), fontsize=9, color='#2ecc71')
        else:
            ax.text(0.8, y_pos, line, fontsize=9, color=color)
    else:
        ax.text(0.8, y_pos, line, fontsize=9, color=color)

# 文件信息
ax.text(0.5, 0.3, '文件路径: docs/teaching/common/rubrics/rubric.json | 可自定义编辑',
        fontsize=9, color='#7f8c8d')

plt.tight_layout()
plt.savefig(os.path.join(output_dir, '13_评分标准配置.png'), dpi=150, bbox_inches='tight')
plt.close()
print('  ✓ 完成')

# === 图片14：个人反馈报告示例 ===
print('\\n生成图片14: 个人反馈报告示例')
fig, ax = plt.subplots(figsize=(11, 8))
ax.axis('off')

# 报告标题
ax.text(0.5, 0.95, '实验报告评分反馈', ha='center', fontsize=16, fontweight='bold', transform=ax.transAxes)

# 学生信息
info_box = FancyBboxPatch((0.5, 0.82), 10, 0.1, boxstyle='round,pad=0.02',
                          facecolor='#ecf0f1', edgecolor='#bdc3c7', transform=ax.transAxes)
ax.add_patch(info_box)
ax.text(0.5, 0.87, '学号: 23071140201  姓名: 董雨航  总分: 69.6/100  等级: D',
        ha='left', fontsize=11, transform=ax.transAxes)

# 评分详情
categories = [
    {'name': '团队协作', 'score': 3.4, 'total': 5, 'percent': 68, 'status': '⚠️'},
    {'name': '实验态度', 'score': 6, 'total': 10, 'percent': 60, 'status': '⚠️'},
    {'name': '实验原理与认知', 'score': 8.8, 'total': 10, 'percent': 88, 'status': '✅'},
    {'name': '实验完成度', 'score': 23.2, 'total': 35, 'percent': 66, 'status': '⚠️'},
    {'name': '代码质量', 'score': 21, 'total': 30, 'percent': 70, 'status': '⚠️'},
    {'name': '实验报告质量', 'score': 7.2, 'total': 10, 'percent': 72, 'status': '⚠️'},
]

y_pos = 0.75
for cat in categories:
    # 类别栏
    cat_box = FancyBboxPatch((0.5, y_pos - 0.06), 10, 0.07, boxstyle='round,pad=0.01',
                            facecolor='#34495e' if cat['status'] == '✅' else '#e67e22',
                            edgecolor='black', transform=ax.transAxes)
    ax.add_patch(cat_box)

    ax.text(0.52, y_pos, f"{cat['status']} {cat['name']}", fontsize=11, fontweight='bold',
           color='white', transform=ax.transAxes)
    ax.text(0.95, y_pos, f"{cat['score']}/{cat['total']} ({cat['percent']}%)",
           fontsize=10, color='white', transform=ax.transAxes)

    # 反馈内容（简略）
    if cat['name'] == '代码质量':
        ax.text(0.52, y_pos - 0.04, "✓ 关键代码完整  △ 代码注释详尽  △ 模块划分合理",
               fontsize=8, color='#555', transform=ax.transAxes)

    y_pos -= 0.11

# 改进建议
ax.text(0.5, y_pos, '改进建议', fontsize=12, fontweight='bold', transform=ax.transAxes)
y_pos -= 0.05

suggestions = [
    '🔴 建议1: 完善GPIO模式配置说明',
    '🔴 建议2: 增加代码注释的详细程度',
    '🟡 建议3: 补充模块划分的说明',
]

for suggestion in suggestions:
    ax.text(0.52, y_pos, suggestion, fontsize=10, transform=ax.transAxes)
    y_pos -= 0.05

plt.tight_layout()
plt.savefig(os.path.join(output_dir, '14_个人反馈报告示例.png'), dpi=150, bbox_inches='tight')
plt.close()
print('  ✓ 完成')

# === 图片15：处理进度界面 ===
print('\\n生成图片15: 处理进度界面')
fig, ax = plt.subplots(figsize=(10, 6))
ax.axis('off')
ax.set_xlim(0, 10)
ax.set_ylim(0, 6)

# 标题
ax.text(5, 5.2, '正在处理报告...', ha='center', fontsize=14, fontweight='bold')

# 进度条背景
progress_bg = Rectangle((2, 3.5), 6, 0.8, facecolor='#ecf0f1', edgecolor='#bdc3c7', linewidth=2)
ax.add_patch(progress_bg)

# 进度条（75%完成）
progress_bar = Rectangle((2, 3.5), 4.5, 0.8, facecolor='#3498db', edgecolor='black')
ax.add_patch(progress_bar)

# 进度文字
ax.text(5, 3.9, '75%', ha='center', va='center', fontsize=12, fontweight='bold', color='white')

# 状态信息
status_text = '''
正在处理: 陈乐莹_23071140202.docx
已完成: 30/41 份报告
预计剩余时间: 45秒
'''
ax.text(5, 2.5, status_text, ha='center', fontsize=11, color='#555')

# 当前任务
task_box = FancyBboxPatch((2, 0.8), 6, 1.2, boxstyle='round,pad=0.02',
                          facecolor='#f8f9fa', edgecolor='#3498db')
ax.add_patch(task_box)

ax.text(5, 1.7, '当前任务: 质量评估', ha='center', fontsize=11, fontweight='bold')
ax.text(5, 1.3, '正在检查技术要点...', ha='center', fontsize=10, color='#7f8c8d')

plt.tight_layout()
plt.savefig(os.path.join(output_dir, '15_处理进度界面.png'), dpi=150, bbox_inches='tight')
plt.close()
print('  ✓ 完成')

# === 图片16：团伙检测结果详情 ===
print('\\n生成图片16: 团伙检测结果详情')
try:
    with open(os.path.join(data_dir, '查重报告.json'), 'r', encoding='utf-8') as f:
        plag_data = json.load(f)

    groups = plag_data.get('groups', [])
    suspicious = plag_data.get('suspicious_details', [])

    fig, ax = plt.subplots(figsize=(11, 8))
    ax.axis('off')
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)

    # 标题
    ax.text(6, 7.5, '团伙检测结果', ha='center', fontsize=16, fontweight='bold')

    # 团伙信息
    if groups:
        y_pos = 6.8
        for i, group in enumerate(groups[:3]):  # 最多显示3个团伙
            members = group.get('members', [])
            size = group.get('size', len(members))

            # 团伙框
            group_box = FancyBboxPatch((1, y_pos - 1), 10, 1.1, boxstyle='round,pad=0.02',
                                      facecolor='#fff5f5', edgecolor='#e74c3c', linewidth=2)
            ax.add_patch(group_box)

            ax.text(1.5, y_pos - 0.5, f'🔴 疑似团伙 #{i+1}', fontsize=12, fontweight='bold', color='#e74c3c')
            ax.text(1.5, y_pos - 0.8, f'成员数: {size}人', fontsize=10)
            ax.text(3.5, y_pos - 0.8, f'成员: {", ".join(members[:4])}{"..." if len(members) > 4 else ""}',
                   fontsize=9, color='#555')

            y_pos -= 1.3

    # 高相似度对列表
    y_pos = 3
    ax.text(1, y_pos, '高相似度报告对 (>90%):', fontsize=12, fontweight='bold')
    y_pos -= 0.5

    # 过滤高相似度
    high_sim = [s for s in suspicious if s.get('overall_similarity', 0) > 90][:5]

    for item in high_sim:
        s1 = item.get('student1', '')
        s2 = item.get('student2', '')
        sim = item.get('overall_similarity', 0)

        # 结果条
        result_bar = FancyBboxPatch((1, y_pos - 0.25), 10, 0.4, boxstyle='round,pad=0.01',
                                    facecolor='#ffe5e5', edgecolor='#e74c3c')
        ax.add_patch(result_bar)

        ax.text(1.2, y_pos - 0.05, f'{s1[-4:]} ↔ {s2[-4:]}', fontsize=10)
        ax.text(10, y_pos - 0.05, f'{sim}%', fontsize=11, fontweight='bold', color='#e74c3c')

        y_pos -= 0.4

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '16_团伙检测结果.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print('  ✓ 完成')

except Exception as e:
    print(f'  ✗ 失败: {e}')
    # 创建模拟图
    fig, ax = plt.subplots(figsize=(11, 8))
    ax.axis('off')
    ax.text(0.5, 0.5, '团伙检测结果\n(模拟数据)', ha='center', fontsize=14)
    plt.savefig(os.path.join(output_dir, '16_团伙检测结果.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print('  ✓ 使用模拟数据完成')

print(f'\\n✅ 所有补充图片生成完成！保存位置: {output_dir}')
