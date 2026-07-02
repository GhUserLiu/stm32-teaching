#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generate PDF feedback files from markdown_final
"""
import sys
import re
from pathlib import Path

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print('Warning: reportlab not installed')

def register_chinese_fonts():
    """
    注册中文字体到reportlab

    Returns:
        bool: 是否成功注册至少一个字体
    """
    try:
        font_paths = [
            ('C:/Windows/Fonts/simsun.ttc', 'SimSun', 'SimSun'),
            ('C:/Windows/Fonts/simhei.ttf', 'SimHei', 'SimHei'),
            ('C:/Windows/Fonts/msyh.ttc', 'MicrosoftYaHei', 'MicrosoftYaHei'),
        ]
        for font_path, font_name, substitute_name in font_paths:
            if Path(font_path).exists():
                try:
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                    pdfmetrics.registerFont(TTFont(substitute_name, font_path))
                except (OSError, IOError, RuntimeError):
                    # 字体文件损坏或无法读取，跳过
                    pass
        mono_font = 'C:/Windows/Fonts/consola.ttf'
        if Path(mono_font).exists():
            pdfmetrics.registerFont(TTFont('Consolas', mono_font))
        return True
    except (OSError, AttributeError, ImportError):
        return False

def md_to_pdf(md_file, pdf_file):
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()

    doc = SimpleDocTemplate(str(pdf_file), pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(name='ChineseTitle', parent=styles['Heading1'], fontName='SimHei', fontSize=18, alignment=TA_CENTER, spaceAfter=12))
    styles.add(ParagraphStyle(name='ChineseHeading2', parent=styles['Heading2'], fontName='SimHei', fontSize=14, spaceAfter=8))
    styles.add(ParagraphStyle(name='ChineseHeading3', parent=styles['Heading3'], fontName='SimHei', fontSize=12, spaceAfter=6))
    styles.add(ParagraphStyle(name='ChineseBody', parent=styles['BodyText'], fontName='SimSun', fontSize=10, leading=16, alignment=TA_JUSTIFY))
    styles.add(ParagraphStyle(name='ChineseCode', parent=styles['Code'], fontName='Consolas', fontSize=8, leading=12, leftIndent=20))

    story = []
    lines = content.split('\n')

    in_code_block = False
    code_lines = []
    table_data = []
    in_table = False

    for line in lines:
        if line.startswith('```'):
            if in_code_block:
                if code_lines:
                    code_text = '\n'.join(code_lines)
                    story.append(Paragraph(code_text.replace('<', '&lt;').replace('>', '&gt;'), styles['ChineseCode']))
                    story.append(Spacer(6, 6))
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        if not line.strip():
            if in_table:
                if table_data:
                    t = Table(table_data)
                    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTNAME', (0, 0), (-1, 0), 'SimHei'), ('FONTSIZE', (0, 0), (-1, 0), 10), ('FONTNAME', (0, 1), (-1, -1), 'SimSun'), ('FONTSIZE', (0, 1), (-1, -1), 9), ('BOTTOMPADDING', (0, 0), (-1, 0), 12), ('BACKGROUND', (0, 1), (-1, -1), colors.beige), ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
                    story.append(t)
                    story.append(Spacer(6, 6))
                table_data = []
                in_table = False
            continue

        if '|' in line and line.count('|') >= 2:
            cells = [c.strip() for c in line.split('|')]
            cells = [c for c in cells if c]
            if cells[0].startswith('---'):
                continue
            if not in_table:
                in_table = True
            table_data.append(cells)
            continue

        if line.startswith('# '):
            if table_data:
                t = Table(table_data)
                t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTNAME', (0, 0), (-1, 0), 'SimHei'), ('FONTSIZE', (0, 0), (-1, 0), 10), ('FONTNAME', (0, 1), (-1, -1), 'SimSun'), ('FONTSIZE', (0, 1), (-1, -1), 9), ('BOTTOMPADDING', (0, 0), (-1, 0), 12), ('BACKGROUND', (0, 1), (-1, -1), colors.beige), ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
                story.append(t)
                table_data = []
                in_table = False
            text = line[2:].strip()
            text = re.sub(r'[📊⚠️✅❌📝🎯📚💭🟠🟡🟢🔴📌📖💻📄🎥🌟📋⛔]', '', text)
            story.append(Paragraph(text, styles['ChineseTitle']))
            continue

        if line.startswith('## '):
            if table_data:
                t = Table(table_data)
                t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTNAME', (0, 0), (-1, 0), 'SimHei'), ('FONTSIZE', (0, 0), (-1, 0), 10), ('FONTNAME', (0, 1), (-1, -1), 'SimSun'), ('FONTSIZE', (0, 1), (-1, -1), 9), ('BOTTOMPADDING', (0, 0), (-1, 0), 12), ('BACKGROUND', (0, 1), (-1, -1), colors.beige), ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
                story.append(t)
                table_data = []
                in_table = False
            text = line[3:].strip()
            text = re.sub(r'[📊⚠️✅❌📝🎯📚💭🟠🟡🟢🔴📌📖💻📄🎥🌟📋⛔]', '', text)
            story.append(Paragraph(text, styles['ChineseHeading2']))
            story.append(Spacer(6, 6))
            continue

        if line.startswith('### '):
            if table_data:
                t = Table(table_data)
                t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTNAME', (0, 0), (-1, 0), 'SimHei'), ('FONTSIZE', (0, 0), (-1, 0), 10), ('FONTNAME', (0, 1), (-1, -1), 'SimSun'), ('FONTSIZE', (0, 1), (-1, -1), 9), ('BOTTOMPADDING', (0, 0), (-1, 0), 12), ('BACKGROUND', (0, 1), (-1, -1), colors.beige), ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
                story.append(t)
                table_data = []
                in_table = False
            text = line[4:].strip()
            text = re.sub(r'[📊⚠️✅❌📝🎯📚💭🟠🟡🟢🔴📌📖💻📄🎥🌟📋⛔]', '', text)
            story.append(Paragraph(text, styles['ChineseHeading3']))
            continue

        if line.startswith('- ') or line.startswith('* '):
            if table_data:
                t = Table(table_data)
                t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTNAME', (0, 0), (-1, 0), 'SimHei'), ('FONTSIZE', (0, 0), (-1, 0), 10), ('FONTNAME', (0, 1), (-1, -1), 'SimSun'), ('FONTSIZE', (0, 1), (-1, -1), 9), ('BOTTOMPADDING', (0, 0), (-1, 0), 12), ('BACKGROUND', (0, 1), (-1, -1), colors.beige), ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
                story.append(t)
                table_data = []
                in_table = False
            text = line[2:].strip()
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
            text = re.sub(r'[✓✗△⚡]', '', text)
            story.append(Paragraph(f'• {text}', styles['ChineseBody']))
            continue

        if line.strip() == '---':
            if table_data:
                t = Table(table_data)
                t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTNAME', (0, 0), (-1, 0), 'SimHei'), ('FONTSIZE', (0, 0), (-1, 0), 10), ('FONTNAME', (0, 1), (-1, -1), 'SimSun'), ('FONTSIZE', (0, 1), (-1, -1), 9), ('BOTTOMPADDING', (0, 0), (-1, 0), 12), ('BACKGROUND', (0, 1), (-1, -1), colors.beige), ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
                story.append(t)
                table_data = []
                in_table = False
            story.append(Spacer(12, 12))
            continue

        if line.strip():
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line.strip())
            text = re.sub(r'[📊⚠️✅❌📝🎯📚💭🟠🟡🟢🔴📌📖💻📄🎥🌟📋⛔]', '', text)
            story.append(Paragraph(text, styles['ChineseBody']))

    doc.build(story)
    return pdf_file

def main():
    print('=== Generating PDF Feedback Files ===')

    if not REPORTLAB_AVAILABLE:
        print('Error: reportlab not installed')
        print('Please run: pip install reportlab')
        sys.exit(1)

    print('Registering Chinese fonts...')
    register_chinese_fonts()

    # Paths
    results_dir = Path('docs/teaching/2026-春季/汽服2302B班/07-car-gear/results')
    md_dir = results_dir / 'feedback' / 'md'
    pdf_dir = results_dir / 'feedback' / 'pdf'

    pdf_dir.mkdir(parents=True, exist_ok=True)

    # Get all MD files (from feedback/md subdirectory)
    md_files = list(md_dir.glob('*.md'))
    print(f'Found {len(md_files)} Markdown files')

    success = 0
    fail = 0

    for i, md_file in enumerate(md_files, 1):
        pdf_file = pdf_dir / (md_file.stem + '.pdf')
        try:
            md_to_pdf(md_file, pdf_file)
            success += 1
            print(f'{i}/{len(md_files)}: {md_file.stem} -> PDF')
        except Exception as e:
            fail += 1
            print(f'{i}/{len(md_files)}: FAILED - {md_file.name}: {e}')

    print(f'\n=== Complete ===')
    print(f'Success: {success}')
    print(f'Failed: {fail}')
    print(f'Output: {pdf_dir}')

if __name__ == '__main__':
    main()
