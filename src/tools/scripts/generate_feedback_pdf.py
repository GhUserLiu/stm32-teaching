#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量生成反馈PDF文件
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.utils import simpleSplit
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("警告: reportlab 未安装")
    print("请运行: pip install reportlab")


def register_chinese_fonts():
    """注册中文字体"""
    try:
        # 尝试注册常见的中文字体
        font_paths = [
            ('C:/Windows/Fonts/simsun.ttc', 'SimSun', 'SimSun'),  # 宋体
            ('C:/Windows/Fonts/simhei.ttf', 'SimHei', 'SimHei'),  # 黑体
            ('C:/Windows/Fonts/msyh.ttc', 'MicrosoftYaHei', 'MicrosoftYaHei'),  # 微软雅黑
        ]

        for font_path, font_name, substitute_name in font_paths:
            if Path(font_path).exists():
                try:
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                    pdfmetrics.registerFont(TTFont(substitute_name, font_path))
                    print(f"注册字体: {font_name}")
                except Exception as e:
                    pass

        # 注册等宽字体用于代码
        mono_font = 'C:/Windows/Fonts/consola.ttf'
        if Path(mono_font).exists():
            pdfmetrics.registerFont(TTFont('Consolas', mono_font))

        return True
    except Exception as e:
        print(f"字体注册警告: {e}")
        return False


def md_to_pdf(md_file, pdf_file):
    """将Markdown文件转换为PDF"""
    import re

    # 读取Markdown内容
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 创建PDF文档
    doc = SimpleDocTemplate(
        str(pdf_file),
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    # 创建样式
    styles = getSampleStyleSheet()

    # 自定义样式
    styles.add(ParagraphStyle(
        name='ChineseTitle',
        parent=styles['Heading1'],
        fontName='SimHei',
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=12
    ))

    styles.add(ParagraphStyle(
        name='ChineseHeading2',
        parent=styles['Heading2'],
        fontName='SimHei',
        fontSize=14,
        spaceAfter=8
    ))

    styles.add(ParagraphStyle(
        name='ChineseHeading3',
        parent=styles['Heading3'],
        fontName='SimHei',
        fontSize=12,
        spaceAfter=6
    ))

    styles.add(ParagraphStyle(
        name='ChineseBody',
        parent=styles['BodyText'],
        fontName='SimSun',
        fontSize=10,
        leading=16,
        alignment=TA_JUSTIFY
    ))

    styles.add(ParagraphStyle(
        name='ChineseCode',
        parent=styles['Code'],
        fontName='Consolas',
        fontSize=8,
        leading=12,
        leftIndent=20
    ))

    # 构建PDF内容
    story = []
    lines = content.split('\n')

    in_code_block = False
    code_lines = []
    table_data = []
    in_table = False
    is_table_header = False

    for line in lines:
        # 处理代码块
        if line.startswith('```'):
            if in_code_block:
                # 结束代码块
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

        # 跳过空行
        if not line.strip():
            if in_table:
                # 结束表格
                if table_data:
                    t = Table(table_data)
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'SimHei'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('FONTNAME', (0, 1), (-1, -1), 'SimSun'),
                        ('FONTSIZE', (0, 1), (-1, -1), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))
                    story.append(t)
                    story.append(Spacer(6, 6))
                table_data = []
                in_table = False
            continue

        # 处理表格
        if '|' in line and line.count('|') >= 2:
            cells = [c.strip() for c in line.split('|')]
            cells = [c for c in cells if c]

            if cells[0].startswith('---'):
                # 表格分隔行，跳过
                continue

            if not in_table:
                in_table = True
                is_table_header = True
            table_data.append(cells)
            continue

        # 处理标题
        if line.startswith('# '):
            if table_data:
                # 保存之前的表格
                t = Table(table_data)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'SimHei'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('FONTNAME', (0, 1), (-1, -1), 'SimSun'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(t)
                table_data = []
                in_table = False

            text = line[2:].strip()
            # 移除emoji
            text = re.sub(r'[📊⚠️✅❌📝🎯📚💭🟠🟡🟢🔴📌📖💻📄🎥🌟📋]', '', text)
            story.append(Paragraph(text, styles['ChineseTitle']))
            continue

        if line.startswith('## '):
            if table_data:
                t = Table(table_data)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'SimHei'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('FONTNAME', (0, 1), (-1, -1), 'SimSun'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(t)
                table_data = []
                in_table = False

            text = line[3:].strip()
            text = re.sub(r'[📊⚠️✅❌📝🎯📚💭🟠🟡🟢🔴📌📖💻📄🎥🌟📋]', '', text)
            story.append(Paragraph(text, styles['ChineseHeading2']))
            story.append(Spacer(6, 6))
            continue

        if line.startswith('### '):
            if table_data:
                t = Table(table_data)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'SimHei'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('FONTNAME', (0, 1), (-1, -1), 'SimSun'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(t)
                table_data = []
                in_table = False

            text = line[4:].strip()
            text = re.sub(r'[📊⚠️✅❌📝🎯📚💭🟠🟡🟢🔴📌📖💻📄🎥🌟📋]', '', text)
            story.append(Paragraph(text, styles['ChineseHeading3']))
            continue

        # 处理列表项
        if line.startswith('- ') or line.startswith('* '):
            if table_data:
                t = Table(table_data)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'SimHei'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('FONTNAME', (0, 1), (-1, -1), 'SimSun'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(t)
                table_data = []
                in_table = False

            text = line[2:].strip()
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
            text = re.sub(r'[✓✗△⚡]', '', text)
            story.append(Paragraph(f'• {text}', styles['ChineseBody']))
            continue

        # 处理编号列表
        match = re.match(r'^(\d+)\.\s+(.+)$', line)
        if match:
            if table_data:
                t = Table(table_data)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'SimHei'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('FONTNAME', (0, 1), (-1, -1), 'SimSun'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(t)
                table_data = []
                in_table = False

            num = match.group(1)
            text = match.group(2).strip()
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
            story.append(Paragraph(f'{num}. {text}', styles['ChineseBody']))
            continue

        # 处理水平线
        if line.strip() == '---':
            if table_data:
                t = Table(table_data)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'SimHei'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('FONTNAME', (0, 1), (-1, -1), 'SimSun'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(t)
                table_data = []
                in_table = False

            story.append(Spacer(12, 12))
            continue

        # 普通段落
        if line.strip():
            # 处理粗体
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line.strip())
            # 移除特殊字符
            text = re.sub(r'[📊⚠️✅❌📝🎯📚💭🟠🟡🟢🔴📌📖💻📄🎥🌟📋]', '', text)
            story.append(Paragraph(text, styles['ChineseBody']))

    # 构建PDF
    doc.build(story)
    return pdf_file


def main():
    """批量生成PDF"""
    if not REPORTLAB_AVAILABLE:
        print("\n请先安装 reportlab:")
        print("  pip install reportlab")
        return

    print("注册中文字体...")
    register_chinese_fonts()

    feedback_dir = Path('docs/teaching/2026-春季/汽服2302B班/07-car-gear/results/feedback')
    md_dir = feedback_dir / 'md'
    pdf_dir = feedback_dir / 'pdf'

    pdf_dir.mkdir(parents=True, exist_ok=True)

    md_files = list(md_dir.glob('*.md'))

    print(f"找到 {len(md_files)} 个反馈文件")
    print("开始转换为 PDF...\n")

    success = 0
    fail = 0

    for i, md_file in enumerate(md_files, 1):
        pdf_file = pdf_dir / (md_file.stem + '.pdf')
        try:
            md_to_pdf(md_file, pdf_file)
            success += 1
            if i % 5 == 0:
                print(f"进度: {i}/{len(md_files)}")
        except Exception as e:
            fail += 1
            print(f"失败: {md_file.name} - {e}")

    print(f"\n========== 完成 ==========")
    print(f"成功: {success}")
    print(f"失败: {fail}")
    print(f"输出目录: {pdf_dir}")


if __name__ == '__main__':
    main()
