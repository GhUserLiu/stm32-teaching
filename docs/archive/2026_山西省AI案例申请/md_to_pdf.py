#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Markdown转PDF脚本"""

import sys
import re
sys.stdout.reconfigure(encoding='utf-8')

# 读取Markdown文件
with open('创AI案例-开发与应用报告.md', 'r', encoding='utf-8') as f:
    md_content = f.read()

# 创建HTML
html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>基于多算法融合的STM32实验报告智能评估系统 - 开发与应用报告</title>
    <style>
        @page {{
            size: A4;
            margin: 2.5cm;
            @top-right {{
                content: counter(page);
                font-size: 10pt;
            }}
        }}
        body {{
            font-family: 'Microsoft YaHei', 'SimSun', sans-serif;
            line-height: 1.8;
            color: #333;
            font-size: 11pt;
            max-width: 100%;
            margin: 0;
            padding: 0;
        }}
        h1 {{
            font-size: 20pt;
            font-weight: bold;
            text-align: center;
            margin: 20pt 0 15pt 0;
            color: #1a5490;
            page-break-before: auto;
            page-break-after: avoid;
        }}
        h2 {{
            font-size: 16pt;
            font-weight: bold;
            margin: 15pt 0 10pt 0;
            color: #2c3e50;
            page-break-after: avoid;
        }}
        h3 {{
            font-size: 14pt;
            font-weight: bold;
            margin: 12pt 0 8pt 0;
            color: #34495e;
            page-break-after: avoid;
        }}
        h4 {{
            font-size: 12pt;
            font-weight: bold;
            margin: 10pt 0 6pt 0;
            color: #5d6d7e;
        }}
        p {{
            margin: 6pt 0;
            text-align: justify;
            text-indent: 2em;
        }}
        .no-indent {{
            text-indent: 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10pt 0;
            font-size: 10pt;
            page-break-inside: avoid;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 6px 10px;
            text-align: left;
        }}
        th {{
            background-color: #f2f2f2;
            font-weight: bold;
            color: #333;
        }}
        code {{
            font-family: 'Consolas', 'Courier New', monospace;
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 9pt;
        }}
        pre {{
            background-color: #f4f4f4;
            border: 1px solid #ddd;
            border-left: 4px solid #2c3e50;
            padding: 10px;
            overflow-x: auto;
            font-size: 9pt;
            font-family: 'Consolas', 'Courier New', monospace;
            line-height: 1.4;
            page-break-inside: avoid;
        }}
        ul, ol {{
            margin: 6pt 0;
            padding-left: 2em;
        }}
        li {{
            margin: 3pt 0;
        }}
        .metadata {{
            text-align: center;
            margin: 15pt 0;
            padding: 10pt;
            background-color: #f8f9fa;
            border-radius: 5px;
        }}
        .appendix {{
            margin-top: 20pt;
            padding-top: 15pt;
            border-top: 2px solid #ddd;
        }}
        .page-break {{
            page-break-after: always;
        }}
        strong {{
            color: #2c3e50;
        }}
        hr {{
            border: none;
            border-top: 1px solid #ddd;
            margin: 15pt 0;
        }}
        blockquote {{
            margin: 10pt 0;
            padding: 10pt 20pt;
            border-left: 4px solid #2c3e50;
            background-color: #f8f9fa;
            page-break-inside: avoid;
        }}
    </style>
</head>
<body>
'''

# 处理Markdown内容
lines = md_content.split('\n')
in_code_block = False
code_lang = ''
code_buffer = []
in_table = False
table_headers = []

i = 0
while i < len(lines):
    line = lines[i]

    # 代码块处理
    if line.startswith('```'):
        if not in_code_block:
            in_code_block = True
            code_lang = line[3:].strip()
            html_content += '<pre><code>'
        else:
            in_code_block = False
            html_content += '</code></pre>\n'
        i += 1
        continue

    if in_code_block:
        html_content += line + '\n'
        i += 1
        continue

    # 标题处理
    if line.startswith('# '):
        html_content += f'<h1>{line[2:]}</h1>\n'
    elif line.startswith('## '):
        html_content += f'<h2>{line[3:]}</h2>\n'
    elif line.startswith('### '):
        html_content += f'<h3>{line[4:]}</h3>\n'
    elif line.startswith('#### '):
        html_content += f'<h4>{line[5:]}</h4>\n'
    elif line.startswith('##### '):
        html_content += f'<h5>{line[6:]}</h5>\n'

    # 表格处理
    elif line.startswith('|') and '|' in line:
        if i + 1 < len(lines) and lines[i + 1].startswith('|---'):
            # 开始表格
            html_content += '<table>\n'
            headers = [h.strip() for h in line.split('|')[1:-1]]
            html_content += '<thead><tr>'
            for h in headers:
                html_content += f'<th>{h}</th>'
            html_content += '</tr></thead>\n<tbody>'
            i += 2  # 跳过表头和分隔符
            while i < len(lines) and lines[i].startswith('|'):
                cells = [c.strip() for c in lines[i].split('|')[1:-1]]
                html_content += '<tr>'
                for c in cells:
                    html_content += f'<td>{c}</td>'
                html_content += '</tr>\n'
                i += 1
            html_content += '</tbody>\n</table>\n'
            continue

    # 列表处理（简化版）
    elif line.strip().startswith('- '):
        html_content += f'<ul><li>{line.strip()[2:]}</li></ul>\n'
    elif re.match(r'^\d+\. ', line.strip()):
        content = re.sub(r'^\d+\. ', '', line.strip())
        html_content += f'<ol><li>{content}</li></ol>\n'

    # 分隔线
    elif line.strip() == '---' or line.strip() == '***':
        html_content += '<hr>\n'

    # 空行
    elif line.strip() == '':
        html_content += '<p class="no-indent"> </p>\n'

    # 普通段落
    elif line.strip():
        # 处理内联格式
        para = line.strip()
        # 粗体
        para = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', para)
        # 行内代码
        para = re.sub(r'`(.+?)`', r'<code>\1</code>', para)
        # 链接
        para = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', para)
        html_content += f'<p>{para}</p>\n'

    i += 1

html_content += '</body>\n</html>'

# 保存HTML
with open('temp_report.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print('HTML生成完成，开始转换为PDF...')

# 使用weasyprint转换为PDF
try:
    from weasyprint import HTML
    HTML('temp_report.html').write_pdf('创AI案例-开发与应用报告.pdf')
    print('PDF生成成功: 创AI案例-开发与应用报告.pdf')
except Exception as e:
    print(f'PDF生成失败: {e}')
