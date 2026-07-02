"""
将 Markdown 文件转换为 HTML 和 PDF
"""

import re
import sys
from pathlib import Path


def md_to_html(md_path, html_path=None):
    """将 Markdown 转换为 HTML"""
    md_path = Path(md_path)
    if html_path is None:
        html_path = md_path.with_suffix('.html')
    else:
        html_path = Path(html_path)

    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 读取标题
    title = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    title = title.group(1) if title else md_path.stem

    # 先处理代码块（临时替换）
    code_blocks = []
    def save_code_block(m):
        code_blocks.append((m.group(1), m.group(2)))
        return f"__CODE_BLOCK_{len(code_blocks)-1}__"

    content = re.sub(r'```(\w*)\n(.+?)```', save_code_block, content, flags=re.DOTALL)

    # 标题（从大到小处理，避免冲突）
    content = re.sub(r'^####\s+(.+)$', r'<h4>\1</h4>', content, flags=re.MULTILINE)
    content = re.sub(r'^###\s+(.+)$', r'<h3>\1</h3>', content, flags=re.MULTILINE)
    content = re.sub(r'^##\s+(.+)$', r'<h2>\1</h2>', content, flags=re.MULTILINE)
    content = re.sub(r'^#\s+(.+)$', r'<h1>\1</h1>', content, flags=re.MULTILINE)

    # 加粗
    content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)

    # 水平线
    content = re.sub(r'^---$', r'<hr>', content, flags=re.MULTILINE)

    # 表格
    lines = content.split('\n')
    new_lines = []
    in_table = False
    table_rows = []
    is_header = True

    for line in lines:
        if line.strip().startswith('|') and '|' in line[1:]:
            cells = [c.strip() for c in line.split('|')]
            cells = cells[1:-1] if line.startswith('|') else cells
            if any(c.startswith('---') for c in cells):
                continue  # 跳过分隔行
            table_rows.append((is_header, cells))
            is_header = False
        else:
            if table_rows:
                new_lines.append('<table class="md-table">')
                for header, row in table_rows:
                    tag = 'th' if header else 'td'
                    new_lines.append('<tr>')
                    for cell in row:
                        new_lines.append(f'<{tag}>{cell}</{tag}>')
                    new_lines.append('</tr>')
                new_lines.append('</table>')
                table_rows = []
                is_header = True
            new_lines.append(line)

    content = '\n'.join(new_lines)

    # 恢复代码块并转换为 HTML
    def restore_code_block(m):
        idx = int(m.group(1))
        lang, code = code_blocks[idx]
        # 检查是否是 ASCII 艺术（包含特殊绘图字符）
        is_ascii_art = any(c in code for c in '┌┐└┘│─├┤┬┴┼▲△▲')
        if is_ascii_art:
            return f'<pre class="ascii-art"><code class="{lang}">{code}</code></pre>'
        return f'<pre><code class="{lang}">{code}</code></pre>'

    content = re.sub(r'__CODE_BLOCK_(\d+)__', restore_code_block, content)

    # 保护 pre 块不被段落处理
    pre_blocks = []
    def save_pre_block(m):
        pre_blocks.append(m.group(0))
        return f"__PRE_BLOCK_{len(pre_blocks)-1}__"

    content = re.sub(r'<pre[^>]*>.*?</pre>', save_pre_block, content, flags=re.DOTALL)

    # 列表处理（注意顺序，先处理数字列表）
    # 用占位符保护数字列表
    numbered_items = []
    def save_numbered(m):
        numbered_items.append(m.group(2))
        return f"__NUM_ITEM_{len(numbered_items)-1}__"

    content = re.sub(r'^(\d+)\.\s+(.+)$', save_numbered, content, flags=re.MULTILINE)

    # 处理无序列表
    content = re.sub(r'^[-\*]\s+(.+)$', r'<li>\1</li>', content, flags=re.MULTILINE)

    # 恢复数字列表
    content = re.sub(r'__NUM_ITEM_(\d+)__', r'<li>\1</li>', content)

    # 处理列表和段落
    lines = content.split('\n')
    new_lines = []
    in_ul = False
    in_ol = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 列表项
        if stripped.startswith('<li>'):
            # 检查前一行是否也是列表
            prev_is_list = i > 0 and lines[i-1].strip().startswith('<li>')

            if not in_ul:
                new_lines.append('<ul>')
                in_ul = True

            new_lines.append(line)
        else:
            if in_ul:
                # 检查下一行是否也是列表
                next_is_list = i < len(lines)-1 and lines[i+1].strip().startswith('<li>')
                if not next_is_list:
                    new_lines.append('</ul>')
                    in_ul = False

            # 空行
            if not stripped:
                new_lines.append('<br>')
            # HTML 标签行直接保留
            elif stripped.startswith('<'):
                new_lines.append(line)
            # 普通段落
            else:
                new_lines.append(f'<p>{line}</p>')

    content = '\n'.join(new_lines)

    # 恢复 pre 块
    def restore_pre_block(m):
        idx = int(m.group(1))
        return pre_blocks[idx]

    content = re.sub(r'__PRE_BLOCK_(\d+)__', restore_pre_block, content)

    # 生成完整 HTML
    full_html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        @page {{
            size: A4;
            margin: 2cm;
        }}
        body {{
            font-family: "SimSun", "Microsoft YaHei", serif;
            line-height: 1.8;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
            font-size: 12pt;
        }}
        h1 {{
            font-size: 22pt;
            text-align: center;
            margin: 20px 0 30px 0;
            font-family: "SimHei", "Microsoft YaHei", sans-serif;
            font-weight: bold;
        }}
        h2 {{
            font-size: 16pt;
            margin: 20px 0 12px 0;
            border-bottom: 2px solid #333;
            padding-bottom: 8px;
            font-family: "SimHei", "Microsoft YaHei", sans-serif;
            font-weight: bold;
            page-break-after: avoid;
        }}
        h3 {{
            font-size: 14pt;
            margin: 15px 0 10px 0;
            font-family: "SimHei", "Microsoft YaHei", sans-serif;
            font-weight: bold;
            page-break-after: avoid;
        }}
        h4 {{
            font-size: 13pt;
            margin: 12px 0 8px 0;
            font-family: "SimHei", "Microsoft YaHei", sans-serif;
            font-weight: bold;
        }}
        p {{
            margin: 8px 0;
            text-align: justify;
        }}
        h1 + p, h2 + p, h3 + p, h4 + p {{
            text-indent: 0;
        }}
        pre {{
            background: #f8f8f8;
            border: 1px solid #ddd;
            padding: 12px;
            border-radius: 4px;
            margin: 12px 0;
            page-break-inside: avoid;
        }}
        .ascii-art {{
            font-family: "NSimSun", "SimSun-ExtB", "Consolas", "Courier New", monospace;
            font-size: 10pt;
            line-height: 1.1;
            letter-spacing: 0.1em;
            white-space: pre;
            background: #f0f0f0;
            border: 1px solid #ccc;
        }}
        code {{
            font-family: "Consolas", "Courier New", monospace;
            background: #f0f0f0;
            padding: 2px 5px;
            border-radius: 3px;
            font-size: 11pt;
        }}
        pre code {{
            background: none;
            padding: 0;
            font-size: inherit;
        }}
        table.md-table {{
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
            page-break-inside: avoid;
        }}
        table.md-table th, table.md-table td {{
            border: 1px solid #333;
            padding: 8px 12px;
            text-align: center;
        }}
        table.md-table th {{
            background: #e0e0e0;
            font-weight: bold;
            font-family: "SimHei", sans-serif;
        }}
        ul {{
            margin: 8px 0;
            padding-left: 2em;
        }}
        li {{
            margin: 4px 0;
        }}
        strong {{
            font-weight: bold;
        }}
        hr {{
            border: none;
            border-top: 1px solid #ccc;
            margin: 20px 0;
        }}
        @media print {{
            body {{ margin: 0; padding: 15mm; }}
            h2 {{ page-break-before: auto; }}
            h1, h2, h3, h4, pre, table {{ page-break-after: avoid; }}
        }}
    </style>
</head>
<body>
{content}
</body>
</html>'''

    html_path.write_text(full_html, encoding='utf-8')
    return html_path, full_html


def try_weasyprint():
    """尝试使用 weasyprint 生成 PDF"""
    try:
        from weasyprint import HTML, CSS
        # 测试是否真正可用
        HTML(string='<p>test</p>')
        return True
    except (ImportError, OSError):
        return False


def try_docx2pdf():
    """尝试使用 docx2pdf"""
    try:
        from docx2pdf import convert
        return True
    except ImportError:
        return False


def md_to_pdf_weasyprint(md_path, pdf_path):
    """使用 weasyprint 直接生成 PDF"""
    from weasyprint import HTML, CSS

    html_path, html_content = md_to_html(md_path)

    # 添加额外的打印样式
    print_css = CSS(string='''
        @page {
            size: A4;
            margin: 2cm;
        }
        body {
            font-size: 12pt;
        }
    ''')

    HTML(string=html_content).write_pdf(pdf_path, stylesheets=[print_css])
    return pdf_path


def md_to_pdf_docx2pdf(md_path, pdf_path):
    """使用 docx2pdf 生成 PDF（需要 Word）"""
    from docx2pdf import convert
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from convert_md_to_docx import md_to_docx

    # 先转为 docx
    docx_path = Path(md_path).with_suffix('.docx')
    md_to_docx(md_path, docx_path)

    # 再转为 pdf
    convert(docx_path, pdf_path)
    return pdf_path


def main():
    """转换指定的文件"""
    import webbrowser

    base_dir = Path(__file__).parent.parent
    md_file = base_dir / 'docs' / '07_car_gear_experiment.md'

    if len(sys.argv) > 1 and sys.argv[1] == '--pdf':
        print('正在转换为 PDF...')
        pdf_path = base_dir / 'docs' / '07_car_gear_experiment.pdf'

        # 优先尝试 docx2pdf (Windows 上更可靠)
        if try_docx2pdf():
            print('使用 docx2pdf 生成 PDF (需要 Word)...')
            try:
                md_to_pdf_docx2pdf(md_file, pdf_path)
                print(f'OK: {pdf_path.name}')
                print(f'PDF 文件已保存: {pdf_path}')
                return
            except Exception as e:
                print(f'docx2pdf 失败: {e}')

        # 尝试 weasyprint
        if try_weasyprint():
            print('使用 weasyprint 生成 PDF...')
            try:
                md_to_pdf_weasyprint(md_file, pdf_path)
                print(f'OK: {pdf_path.name}')
                print(f'PDF 文件已保存: {pdf_path}')
                return
            except Exception as e:
                print(f'weasyprint 失败: {e}')

        # 都失败了
        print('\n错误: 无法生成 PDF')
        print('请确保安装了以下工具之一:')
        print('  1. Microsoft Word (用于 docx2pdf)')
        print('  2. GTK libraries (用于 weasyprint)')
        sys.exit(1)
    else:
        print('正在转换为 HTML...')
        html_path, _ = md_to_html(md_file)
        print(f'OK: {html_path.name}')

        # 自动打开浏览器
        webbrowser.open(html_path.absolute().as_uri())

        print('\n转换完成！')
        print('HTML 文件已在浏览器中打开')
        print('使用浏览器打印功能保存为 PDF，或使用:')
        print('  python scripts/convert_md_to_pdf.py --pdf')
        print('\n如需直接生成 PDF，请安装:')
        print('  pip install weasyprint')


if __name__ == '__main__':
    main()
