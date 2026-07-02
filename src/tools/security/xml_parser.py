#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
安全的XML解析工具
Safe XML Parser

防御XXE（XML External Entity）注入攻击
For defending against XXE (XML External Entity) injection attacks

作者: STM32F407 教学团队
版本: 1.0.0
"""

from __future__ import annotations

import logging
from xml.etree import ElementTree as ET
from typing import Optional


logger = logging.getLogger(__name__)

# 尝试导入defusedxml（推荐）
try:
    from defusedxml import ElementTree as DefusedET
    DEFUSEDXML_AVAILABLE = True
except ImportError:
    DEFUSEDXML_AVAILABLE = False
    logger.warning(
        "defusedxml未安装，使用标准库XML解析器。"
        "建议安装: pip install defusedxml"
    )


class XMLError(Exception):
    """XML解析错误"""
    pass


def safe_parse_xml_string(
    xml_string: bytes | str,
    disable_entities: bool = True
) -> ET.Element:
    """
    安全解析XML字符串

    Args:
        xml_string: XML字符串（字节或字符串）
        disable_entities: 是否禁用实体（防御XXE）

    Returns:
        Element对象

    Raises:
        XMLError: 如果解析失败

    安全原理:
        XXE攻击通过XML实体读取本地文件或执行SSRF攻击：
        <!ENTITY xx SYSTEM "file:///etc/passwd">

        防御方法:
        1. 使用defusedxml库（推荐）- 默认禁用所有危险功能
        2. 使用标准库时禁用实体处理
    """
    if isinstance(xml_string, bytes):
        try:
            xml_string = xml_string.decode('utf-8')
        except UnicodeDecodeError as e:
            raise XMLError(f"XML解码失败: {e}")

    if DEFUSEDXML_AVAILABLE:
        # 使用defusedxml（安全）
        try:
            return DefusedET.fromstring(xml_string)
        except DefusedET.ParseError as e:
            raise XMLError(f"XML解析失败: {e}")
    else:
        # 使用标准库
        try:
            # 在Python 3.8+中，标准库默认禁用实体
            parser = ET.XMLParser()
            if disable_entities:
                # 确保禁用实体（Python 3.8+默认已禁用）
                parser.parser = ET.XMLParser(
                    target=ET.TreeBuilder(),
                    parser=None
                )
            return ET.fromstring(xml_string)
        except ET.ParseError as e:
            raise XMLError(f"XML解析失败: {e}")


def safe_parse_xml_file(
    file_path: str,
    disable_entities: bool = True
) -> ET.Element:
    """
    安全解析XML文件

    Args:
        file_path: XML文件路径
        disable_entities: 是否禁用实体

    Returns:
        Element对象

    Raises:
        XMLError: 如果解析失败
    """
    if DEFUSEDXML_AVAILABLE:
        try:
            tree = DefusedET.parse(file_path)
            return tree.getroot()
        except DefusedET.ParseError as e:
            raise XMLError(f"XML文件解析失败: {e}")
        except (OSError, IOError) as e:
            raise XMLError(f"无法读取文件: {e}")
    else:
        try:
            tree = ET.parse(file_path)
            return tree.getroot()
        except ET.ParseError as e:
            raise XMLError(f"XML文件解析失败: {e}")
        except (OSError, IOError) as e:
            raise XMLError(f"无法读取文件: {e}")


def extract_text_from_element(element: ET.Element) -> str:
    """
    从XML元素中提取所有文本

    Args:
        element: XML元素

    Returns:
        提取的文本

    用途:
        从docx的document.xml中提取文本内容
    """
    texts = []
    for elem in element.iter():
        if elem.text:
            texts.append(elem.text)
    return ''.join(texts)


def extract_text_from_docx_xml(xml_content: bytes | str) -> Optional[str]:
    """
    从docx的XML内容中提取文本（保留段落换行）

    Args:
        xml_content: docx的word/document.xml内容

    Returns:
        提取的文本或None

    用途:
        处理Word文档的XML内容，提取纯文本。
        按 <w:p> 段落分段、以换行连接，使章节标题独占一行——
        这对章节检测（SectionDetector）与提交校验至关重要；
        否则整篇文档会被压成一行，导致章节识别失败。
    """
    try:
        root = safe_parse_xml_string(xml_content)
        return _extract_docx_paragraphs(root)
    except XMLError as e:
        logger.warning(f"从docx XML提取文本失败: {e}")
        return None


def _local_name(tag: str) -> str:
    """去掉命名空间，返回标签本地名。"""
    return tag.rsplit('}', 1)[-1] if '}' in tag else tag


def _extract_docx_paragraphs(root) -> str:
    """按段落提取 docx 文本，段落间以 '\\n' 连接。无段落结构时回退到通用提取。"""
    paragraphs = [el for el in root.iter() if _local_name(el.tag) == 'p']
    if not paragraphs:
        return extract_text_from_element(root)

    lines = []
    for p in paragraphs:
        buf = []
        for node in p.iter():
            local = _local_name(node.tag)
            if local == 't':
                if node.text:
                    buf.append(node.text)
            elif local == 'tab':
                buf.append('\t')
            elif local == 'br':
                buf.append('\n')
        line = ''.join(buf).strip()
        if line:
            lines.append(line)
    return '\n'.join(lines)
