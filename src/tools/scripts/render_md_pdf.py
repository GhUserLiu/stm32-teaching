#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
render_md_pdf.py — 稳健的 Markdown → PDF 渲染器（reportlab + 中文字体）

适用场景：weasyprint 不可用（缺 GTK）时的中文 PDF 生成。
特性：
  - 注册中文字体（SimSun 正文 / SimHei 标题 / 微软雅黑 / Consolas 代码）
  - 支持 #~#### 标题、管道表格、有序/无序列表、**加粗**、`行内代码`、```代码块```、--- 分隔线、> 引用
  - 表格单元格自动换行（中文友好），列宽自适应
  - 页眉（文档标题）/ 页脚（页码）

用法：
  python render_md_pdf.py input.md output.pdf [文档副标题]
  python render_md_pdf.py --all "目录"        # 渲染目录下全部 .md
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# --------------------------------------------------------------------------- #
# 字体注册
# --------------------------------------------------------------------------- #
_FONT_DIR = "C:/Windows/Fonts"
_FONT_CANDIDATES = {
    "SimSun": ["simsun.ttc"],
    "SimHei": ["simhei.ttf"],
    "MicrosoftYaHei": ["msyh.ttc"],
    "FangSong": ["simfang.ttf"],
    "KaiTi": ["simkai.ttf"],
    "Consolas": ["consola.ttf", "consolab.ttf"],
}


def register_chinese_fonts() -> dict[str, str]:
    """注册中文字体，返回 {逻辑名: 已注册名}。缺字体则跳过。"""
    registered: dict[str, str] = {}
    for name, files in _FONT_CANDIDATES.items():
        for f in files:
            path = os.path.join(_FONT_DIR, f)
            if Path(path).exists():
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                    registered[name] = name
                    break
                except (OSError, IOError, RuntimeError):
                    continue
    # 正文字体族（让 <b> 自动用 SimHei）
    if "SimSun" in registered and "SimHei" in registered:
        try:
            registerFontFamily(
                "SimSun",
                normal="SimSun",
                bold="SimHei",
                italic="KaiTi" if "KaiTi" in registered else "SimSun",
                boldItalic="SimHei",
            )
        except Exception:
            pass
    return registered


FONTS = register_chinese_fonts()
BODY_FONT = FONTS.get("SimSun", "Helvetica")
BOLD_FONT = FONTS.get("SimHei", "Helvetica-Bold")
HEAD_FONT = FONTS.get("SimHei", "Helvetica")
MONO_FONT = FONTS.get("Consolas", "Courier")

# --------------------------------------------------------------------------- #
# 样式
# --------------------------------------------------------------------------- #
ACCENT = colors.HexColor("#1F3A5F")
ACCENT_LIGHT = colors.HexColor("#E8EEF5")
RULE = colors.HexColor("#BBBBBB")
CODE_BG = colors.HexColor("#F5F5F5")
TABLE_HEAD_BG = colors.HexColor("#1F3A5F")
TABLE_ZEBRA = colors.HexColor("#F4F6F9")


def build_styles(title: str) -> dict:
    base = getSampleStyleSheet()
    s = {}
    s["title"] = ParagraphStyle(
        "DocTitle", parent=base["Title"], fontName=HEAD_FONT,
        fontSize=20, leading=28, alignment=TA_CENTER, textColor=ACCENT,
        spaceBefore=6, spaceAfter=10,
    )
    s["subtitle"] = ParagraphStyle(
        "DocSubtitle", fontName=BODY_FONT, fontSize=11, leading=16,
        alignment=TA_CENTER, textColor=colors.HexColor("#555555"), spaceAfter=16,
    )
    s["h1"] = ParagraphStyle(
        "H1", fontName=HEAD_FONT, fontSize=15, leading=22, textColor=ACCENT,
        spaceBefore=14, spaceAfter=8, keepWithNext=1,
    )
    s["h2"] = ParagraphStyle(
        "H2", fontName=HEAD_FONT, fontSize=13, leading=19, textColor=ACCENT,
        spaceBefore=11, spaceAfter=6, keepWithNext=1,
    )
    s["h3"] = ParagraphStyle(
        "H3", fontName=HEAD_FONT, fontSize=11.5, leading=17, textColor=colors.HexColor("#222222"),
        spaceBefore=8, spaceAfter=4, keepWithNext=1,
    )
    s["h4"] = ParagraphStyle(
        "H4", fontName=BOLD_FONT, fontSize=10.5, leading=15, textColor=colors.HexColor("#333333"),
        spaceBefore=6, spaceAfter=3, keepWithNext=1,
    )
    s["body"] = ParagraphStyle(
        "Body", fontName=BODY_FONT, fontSize=10.5, leading=17, alignment=TA_JUSTIFY,
        textColor=colors.HexColor("#222222"), spaceAfter=4, firstLineIndent=0,
    )
    s["li"] = ParagraphStyle(
        "ListItem", fontName=BODY_FONT, fontSize=10.5, leading=16, alignment=TA_JUSTIFY,
        textColor=colors.HexColor("#222222"), spaceAfter=2, leftIndent=14, bulletIndent=2,
    )
    s["cell"] = ParagraphStyle(
        "Cell", fontName=BODY_FONT, fontSize=9.5, leading=13, alignment=TA_LEFT,
        textColor=colors.HexColor("#222222"),
    )
    s["cell_c"] = ParagraphStyle(
        "CellC", parent=s["cell"], alignment=TA_CENTER,
    )
    s["cell_head"] = ParagraphStyle(
        "CellHead", fontName=HEAD_FONT, fontSize=9.5, leading=13, alignment=TA_CENTER,
        textColor=colors.white,
    )
    s["code"] = ParagraphStyle(
        "Code", fontName=MONO_FONT, fontSize=8.5, leading=12, textColor=colors.HexColor("#222222"),
        leftIndent=8, rightIndent=8, backColor=CODE_BG, borderPadding=4,
        spaceBefore=4, spaceAfter=6,
    )
    s["quote"] = ParagraphStyle(
        "Quote", fontName=BODY_FONT, fontSize=10, leading=15, textColor=colors.HexColor("#444444"),
        leftIndent=12, borderColor=RULE, borderWidth=0, spaceAfter=4,
    )
    return s


# --------------------------------------------------------------------------- #
# Markdown 内联解析（加粗 / 行内代码 / 删除线）
# --------------------------------------------------------------------------- #
def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(text: str) -> str:
    """把一段 Markdown 行内文本转为 reportlab Paragraph 支持的 XML。"""
    # 先保护行内代码
    codes: list[str] = []

    def save_code(m: re.Match) -> str:
        codes.append(m.group(1))
        return f"\x00CODE{len(codes) - 1}\x00"

    text = _esc(text)
    text = re.sub(r"\`([^\`]+)\`", save_code, text)
    # 加粗
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    # 删除线
    text = re.sub(r"~~(.+?)~~", r"<strike>\1</strike>", text)
    # 还原行内代码（着色）
    def restore_code(m: re.Match) -> str:
        idx = int(m.group(1))
        return f'<font face="{MONO_FONT}" color="#B5312E">{codes[idx]}</font>'

    text = re.sub(r"\x00CODE(\d+)\x00", restore_code, text)
    return text


# --------------------------------------------------------------------------- #
# 表格
# --------------------------------------------------------------------------- #
def _is_table_separator(line: str) -> bool:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c)


def _parse_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def build_table(rows: list[list[str]], styles: dict, avail_width: float) -> Table:
    ncol = max(len(r) for r in rows)
    # 补齐
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    header, body = rows[0], rows[1:]

    # 列宽：根据各列字符数加权，最少 1.6cm
    weights = []
    for ci in range(ncol):
        lens = [len(str(r[ci])) for r in rows]
        weights.append(max(sum(lens) / len(lens), 1))
    tot = sum(weights)
    col_widths = [max(avail_width * (w / tot), 1.6 * cm) for w in weights]
    # 归一化到可用宽度
    scale = avail_width / sum(col_widths)
    col_widths = [w * scale for w in col_widths]

    data = [[Paragraph(inline(c), styles["cell_head"]) for c in header]]
    for row in body:
        data.append([Paragraph(inline(c), styles["cell_c"]) for c in row])

    tbl = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEAD_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), HEAD_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9AA7B8")),
        ("BOX", (0, 0), (-1, -1), 0.8, ACCENT),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.add("BACKGROUND", (0, i), (-1, i), TABLE_ZEBRA)
    tbl.setStyle(style)
    return tbl


# --------------------------------------------------------------------------- #
# 主解析
# --------------------------------------------------------------------------- #
def parse_markdown(md: str, styles: dict, avail_width: float) -> list:
    flow: list = []
    lines = md.split("\n")
    i = 0
    n = len(lines)
    pending_list: list[tuple[str, str]] | None = None  # (marker, text)

    def flush_list():
        nonlocal pending_list
        if not pending_list:
            return
        # 渲染为保持一起的一组段落
        items = []
        for idx, (marker, text) in enumerate(pending_list):
            if marker == "ul":
                items.append(Paragraph(f"• {inline(text)}", styles["li"]))
            else:
                items.append(Paragraph(f"{idx + 1}. {inline(text)}", styles["li"]))
        # 短列表整体保持在一起；长列表直接展开为独立 flowable，避免把 list 嵌入 flow
        if len(items) <= 4:
            flow.append(KeepTogether(items))
        else:
            flow.extend(items)
        flow.append(Spacer(1, 3))
        pending_list = None

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # 代码块
        if stripped.startswith("```"):
            flush_list()
            code_lines: list[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # 跳过结束 ```
            code = _esc("\n".join(code_lines))
            # 用 <br/> 换行，保持空格
            code = code.replace(" ", "&nbsp;").replace("\n", "<br/>")
            flow.append(Paragraph(code, styles["code"]))
            continue

        # 表格
        if "|" in stripped and stripped.startswith("|") and i + 1 < n and _is_table_separator(lines[i + 1]):
            flush_list()
            rows = [_parse_row(stripped)]
            i += 2
            while i < n and lines[i].strip().startswith("|"):
                if not _is_table_separator(lines[i]):
                    rows.append(_parse_row(lines[i]))
                i += 1
            flow.append(build_table(rows, styles, avail_width))
            flow.append(Spacer(1, 6))
            continue

        # 分隔线
        if stripped in {"---", "***", "___"}:
            flush_list()
            flow.append(Spacer(1, 4))
            flow.append(Table([[""]], colWidths=[avail_width], style=TableStyle([
                ("LINEBELOW", (0, 0), (-1, -1), 0.6, RULE),
            ])))
            flow.append(Spacer(1, 4))
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush_list()
            level = len(m.group(1))
            text = inline(m.group(2).strip())
            if level == 1:
                flow.append(Paragraph(text, styles["title"]))
            elif level == 2:
                flow.append(Paragraph(text, styles["h1"]))
            elif level == 3:
                flow.append(Paragraph(text, styles["h2"]))
            else:
                flow.append(Paragraph(text, styles["h3"] if level == 4 else styles["h4"]))
            i += 1
            continue

        # 引用
        if stripped.startswith(">"):
            flush_list()
            flow.append(Paragraph(inline(stripped.lstrip(">").strip()), styles["quote"]))
            i += 1
            continue

        # 列表项
        m_ul = re.match(r"^[-*+]\s+(.*)$", stripped)
        m_ol = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m_ul or m_ol:
            if pending_list is None:
                pending_list = []
            if m_ul:
                pending_list.append(("ul", m_ul.group(1)))
            else:
                pending_list.append(("ol", m_ol.group(2)))
            i += 1
            continue
        else:
            flush_list()

        # 空行
        if not stripped:
            i += 1
            continue

        # 普通段落（合并连续非空行为一段）
        para = [stripped]
        i += 1
        while i < n and lines[i].strip() and not re.match(r"^(#{1,6}\s|[-*+]\s|\d+\.\s|>)", lines[i].strip()) \
                and not lines[i].strip().startswith("|") \
                and not lines[i].strip().startswith("```") \
                and lines[i].strip() not in {"---", "***", "___"}:
            para.append(lines[i].strip())
            i += 1
        flow.append(Paragraph(inline(" ".join(para)), styles["body"]))

    flush_list()
    return flow


# --------------------------------------------------------------------------- #
# 文档模板（页眉页脚）
# --------------------------------------------------------------------------- #
def _make_page_templates(doc_title: str, width, height, margin):
    def on_page(canvas, doc):
        canvas.saveState()
        # 页眉
        canvas.setFont(HEAD_FONT, 8.5)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(margin, height - margin + 10, doc_title)
        canvas.drawRightString(width - margin, height - margin + 10, "汽车微处理器原理与应用 · 2026春季")
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.line(margin, height - margin + 6, width - margin, height - margin + 6)
        # 页脚
        canvas.setFont(BODY_FONT, 8.5)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawCentredString(width / 2, margin - 14, f"— {doc.page} —")
        canvas.restoreState()

    frame = Frame(margin, margin, width - 2 * margin, height - 2 * margin, id="main",
                  leftPadding=0, rightPadding=0, topPadding=4, bottomPadding=4)
    return [PageTemplate(id="main", frames=[frame], onPage=on_page)]


def md_to_pdf(md_path: str | Path, pdf_path: str | Path, subtitle: str | None = None) -> Path:
    md_path = Path(md_path)
    pdf_path = Path(pdf_path)
    md = md_path.read_text(encoding="utf-8")

    # 标题：取第一个 # 标题，否则文件名
    m = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    title = m.group(1).strip() if m else md_path.stem

    styles = build_styles(title)

    width, height = A4
    margin = 2.0 * cm
    avail_width = width - 2 * margin

    doc = BaseDocTemplate(
        str(pdf_path), pagesize=A4,
        leftMargin=margin, rightMargin=margin, topMargin=margin, bottomMargin=margin,
        title=title, author="汽车微处理器原理与应用课程组",
    )
    doc.addPageTemplates(_make_page_templates(title, width, height, margin))

    flow: list = []
    # 文档主标题（若 md 首行已是 # 标题，parse 时会再画一次；这里统一去掉重复）
    # 处理：若首行是 # 标题，跳过 parse 中的 title，改用更显眼的封面式标题
    lines = md.split("\n")
    start = 0
    first_title = None
    if lines and lines[0].strip().startswith("# "):
        first_title = re.sub(r"^#\s+", "", lines[0]).strip()
        start = 1
    if first_title:
        flow.append(Paragraph(inline(first_title), styles["title"]))
        if subtitle:
            flow.append(Paragraph(inline(subtitle), styles["subtitle"]))
        else:
            flow.append(Spacer(1, 6))
    body_md = "\n".join(lines[start:])
    flow.extend(parse_markdown(body_md, styles, avail_width))

    doc.build(flow)
    return pdf_path


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] == "--all":
        d = Path(sys.argv[2])
        for md in sorted(d.glob("*.md")):
            pdf = md.with_suffix(".pdf")
            try:
                md_to_pdf(md, pdf)
                print(f"OK  {md.name} -> {pdf.name}")
            except Exception as e:
                print(f"ERR {md.name}: {e}")
        return
    md_path, pdf_path = sys.argv[1], sys.argv[2]
    subtitle = sys.argv[3] if len(sys.argv) > 3 else None
    out = md_to_pdf(md_path, pdf_path, subtitle)
    print(f"OK  -> {out}  ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
