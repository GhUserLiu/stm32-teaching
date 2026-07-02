#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""使用fpdf2生成PDF"""

import sys
import re
sys.stdout.reconfigure(encoding='utf-8')

from fpdf import FPDF
from fpdf.fonts import FontFace

# 读取Markdown文件
with open('创AI案例-开发与应用报告.md', 'r', encoding='utf-8') as f:
    md_content = f.read()

# 创建PDF
pdf = FPDF()
pdf.set_left_margin(20)
pdf.set_right_margin(20)
pdf.set_top_margin(20)
pdf.set_auto_page_break(auto=True, margin=20)
pdf.add_page()

# 尝试添加中文字体
# Windows常见中文字体路径
font_paths = [
    ('C:/Windows/Fonts/msyh.ttc', 'Microsoft YaHei'),
    ('C:/Windows/Fonts/simhei.ttf', 'SimHei'),
    ('C:/Windows/Fonts/simsun.ttc', 'SimSun'),
]

font_added = False
for font_path, font_name in font_paths:
    try:
        # 添加常规字体
        pdf.add_font('CN', '', font_path)
        # 添加粗体字体（使用同一文件）
        pdf.add_font('CN', 'B', font_path)
        font_added = True
        print(f'使用字体: {font_name}')
        break
    except:
        continue

if not font_added:
    print('警告: 无法添加中文字体，尝试使用内置字体')
    pdf.set_font('Arial', '', 12)

# 当前字体设置
current_font_size = 12

def add_title(text, level=1):
    """添加标题"""
    global current_font_size
    sizes = {1: 20, 2: 16, 3: 14, 4: 12}
    size = sizes.get(level, 12)

    if level == 1:
        pdf.set_font('CN', 'B', size)
        pdf.ln(5)
        pdf.multi_cell(0, 10, text, align='C')
        pdf.ln(3)
    elif level == 2:
        pdf.ln(5)
        pdf.set_font('CN', 'B', size)
        pdf.multi_cell(0, 8, text)
        pdf.ln(2)
    else:
        pdf.ln(3)
        pdf.set_font('CN', 'B', size)
        pdf.multi_cell(0, 7, text)
        pdf.ln(1)

    current_font_size = 12

def add_paragraph(text):
    """添加段落"""
    pdf.set_font('CN', '', 11)

    # 处理可能的格式标记
    text = text.replace('**', '')  # 移除粗体标记
    text = text.replace('`', '')   # 移除代码标记

    # 移除链接格式 [text](url) -> text
    import re
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    pdf.multi_cell(0, 7, text)

def add_code(code_text):
    """添加代码块"""
    pdf.set_font('Courier', '', 9)
    pdf.ln(3)

    # 处理代码中的特殊字符
    code_text = code_text.replace('"""', '\"\"\"')

    lines = code_text.split('\n')
    for line in lines:
        # 如果行太长，进行分割
        if pdf.get_string_width(line) > pdf.epw:
            # 简单分割
            for i in range(0, len(line), 90):
                pdf.cell(0, 5, line[i:i+90], ln=True)
        else:
            pdf.cell(0, 5, line, ln=True)

    pdf.ln(2)

def add_table(headers, rows):
    """添加表格"""
    pdf.ln(5)

    # 计算列宽
    col_width = pdf.epw / len(headers)

    # 表头
    pdf.set_font('CN', 'B', 11)
    for header in headers:
        pdf.cell(col_width, 8, header, border=1, align='C')
    pdf.ln()

    # 表格内容
    pdf.set_font('CN', '', 10)
    for row in rows:
        for cell in row:
            pdf.cell(col_width, 7, cell, border=1, align='L')
        pdf.ln()

    pdf.ln(3)

def add_list(items, ordered=False):
    """添加列表"""
    pdf.set_font('CN', '', 12)
    pdf.ln(3)

    for i, item in enumerate(items):
        if ordered:
            prefix = f"{i+1}. "
        else:
            prefix = "• "
        pdf.multi_cell(0, 7, prefix + item)

    pdf.ln(2)

# 解析Markdown内容
lines = md_content.split('\n')
in_code_block = False
code_buffer = []
in_table = False
table_headers = []
table_rows = []
list_items = []

i = 0
while i < len(lines):
    line = lines[i]

    # 代码块处理
    if line.startswith('```'):
        if not in_code_block:
            in_code_block = True
        else:
            # 代码块结束
            add_code('\n'.join(code_buffer))
            code_buffer = []
            in_code_block = False
        i += 1
        continue

    if in_code_block:
        code_buffer.append(line)
        i += 1
        continue

    # 标题处理
    if line.startswith('#'):
        match = re.match(r'^(#{1,4})\s+(.+)$', line)
        if match:
            level = len(match.group(1))
            text = match.group(2)
            add_title(text, level)
            i += 1
            continue

    # 表格处理
    if line.startswith('|'):
        if i + 1 < len(lines) and lines[i + 1].startswith('|---'):
            # 表头
            table_headers = [h.strip() for h in line.split('|')[1:-1]]
            i += 2
            # 收集表格行
            table_rows = []
            while i < len(lines) and lines[i].startswith('|'):
                cells = [c.strip() for c in lines[i].split('|')[1:-1]]
                table_rows.append(cells)
                i += 1
            add_table(table_headers, table_rows)
            continue

    # 列表处理
    if line.strip().startswith('- '):
        # 收集连续的列表项
        list_items = []
        while i < len(lines) and lines[i].strip().startswith('- '):
            list_items.append(lines[i].strip()[2:])
            i += 1
        add_list(list_items, ordered=False)
        continue

    if re.match(r'^\d+\. ', line.strip()):
        list_items = []
        while i < len(lines) and re.match(r'^\d+\. ', lines[i].strip()):
            content = re.sub(r'^\d+\. ', '', lines[i].strip())
            list_items.append(content)
            i += 1
        add_list(list_items, ordered=True)
        continue

    # 分隔线
    if line.strip() in ['---', '***']:
        pdf.ln(5)
        pdf.line(10, pdf.y, pdf.epw + 10, pdf.y)
        pdf.ln(5)
        i += 1
        continue

    # 空行
    if line.strip() == '':
        pdf.ln(2)
        i += 1
        continue

    # 普通段落
    if line.strip():
        try:
            add_paragraph(line.strip())
        except Exception as e:
            print(f'警告: 无法渲染行 {i}: {line[:50]}...')
            print(f'错误: {e}')
            pdf.ln(5)

    i += 1

# 保存PDF
output_file = '创AI案例-开发与应用报告.pdf'
pdf.output(output_file)

print(f'PDF生成成功: {output_file}')
