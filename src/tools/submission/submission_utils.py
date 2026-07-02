#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
学生提交内容提取工具（安全加固版）
Student Submission Extraction Utilities (Security Hardened)

从提交的ZIP文件中提取学生信息、小组编号和报告内容
安全加固：防御Zip炸弹、路径遍历、XXE注入攻击

作者: STM32F407 教学团队
版本: 2.0.0 - 安全增强版
"""

import zipfile
import io
import re
import logging
from pathlib import Path
from typing import Dict, Optional

# 导入安全工具模块
from tools.security.zip_validator import (
    ZipLimits, ZipValidationError,
    validate_path_traversal, validate_zip_size, safe_extract_inner_zip
)
from tools.security.xml_parser import safe_parse_xml_string, extract_text_from_docx_xml
from tools.security.path_validator import extract_safe_student_id

# 配置日志
logger = logging.getLogger(__name__)


def extract_text_from_docx(docx_data, limits=None):
    """
    从docx文件中提取文本（安全版本）

    Args:
        docx_data: docx文件二进制数据
        limits: ZIP限制配置（可选）

    Returns:
        提取的文本或None

    安全改进:
        - 使用安全XML解析器防御XXE攻击
        - 验证ZIP文件大小和结构
        - 检测并跳过旧的.doc格式文件
    """
    if limits is None:
        limits = ZipLimits()

    # 检查是否为空的.doc文件（旧Word格式）
    if len(docx_data) >= 8 and docx_data[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
        logger.warning("检测到旧版.doc格式文件，此工具仅支持.docx格式")
        return None

    # 检查是否为有效的ZIP文件（.docx是ZIP格式）
    if len(docx_data) >= 4 and docx_data[:4] != b'PK\x03\x04':
        logger.warning(f"文件不是有效的ZIP/docx格式（文件头: {docx_data[:4].hex()}）")
        return None

    try:
        with zipfile.ZipFile(io.BytesIO(docx_data), 'r') as docx:
            # 验证docx ZIP结构（防御Zip炸弹）
            validate_zip_size(docx, limits)

            # 读取document.xml
            xml_content = docx.read('word/document.xml')

            # 使用安全XML解析器（防御XXE攻击）
            return extract_text_from_docx_xml(xml_content)

    except ZipValidationError as e:
        logger.warning(f"ZIP验证失败: {e}")
        return None
    except zipfile.BadZipFile as e:
        logger.warning(f"文件不是有效的ZIP格式: {e}")
        return None
    except Exception as e:
        logger.error(f"提取docx文本失败: {e}")
        return None


def get_student_info(extract_dir, limits=None):
    """
    从答题记录和实验报告中提取学生信息（安全版本）

    Args:
        extract_dir: 提取后的提交目录
        limits: ZIP限制配置（可选）

    Returns:
        {学号: {'name': 姓名, 'time': 提交时间, 'content': 报告内容}}

    安全改进:
        - ZIP炸弹防护（文件大小、数量限制）
        - 路径遍历防护
        - 异常日志记录
    """
    if limits is None:
        limits = ZipLimits()

    student_info = {}

    for zip_file in extract_dir.glob('*.zip'):
        # 使用安全的学号提取函数
        student_id = extract_safe_student_id(zip_file.name)
        if not student_id:
            continue

        info = {'name': None, 'time': None, 'content': None}

        try:
            with zipfile.ZipFile(zip_file, 'r') as outer:
                # 验证外层ZIP（防御Zip炸弹）
                validate_zip_size(outer, limits)

                files = outer.namelist()
                if len(files) > 0 and files[0].endswith('.zip'):
                    # 安全提取内层ZIP
                    inner = safe_extract_inner_zip(outer, files[0], limits)
                    inner_files = inner.namelist()

                    # 从答题记录提取姓名和时间
                    doc_files = [f for f in inner_files if '答题记录' in f and f.endswith('.doc')]

                    # 如果没有找到包含"答题记录"的文件，尝试查找所有.doc文件
                    if not doc_files:
                        doc_files = [f for f in inner_files if f.endswith('.doc')]

                    if doc_files:
                        # 验证文件路径（防御路径遍历）
                        validate_path_traversal(doc_files[0])

                        doc_data = inner.read(doc_files[0])
                        doc_str = str(doc_data, errors='ignore')

                        pattern1 = r'<w:t>答题人：[^<]*</w:t>\s*.*?<w:t>([^<]+)</w:t>'
                        name_match = re.search(pattern1, doc_str, re.DOTALL)
                        if name_match:
                            info['name'] = name_match.group(1).strip()

                        pattern2 = r'<w:t>提交时间：[^<]*</w:t>\s*.*?<w:t>(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})[^<]*</w:t>'
                        time_match = re.search(pattern2, doc_str, re.DOTALL)
                        if time_match:
                            info['time'] = time_match.group(1).strip()

                    # 从实验报告提取内容
                    docx_files = [f for f in inner_files if f.endswith('.docx') and '答题记录' not in f]
                    if docx_files:
                        # 验证文件路径
                        validate_path_traversal(docx_files[0])

                        docx_data = inner.read(docx_files[0])
                        text = extract_text_from_docx(docx_data, limits)
                        if text:
                            content = re.sub(r'\s+', '', text)
                            info['content'] = content

                    if info['name'] or info['time']:
                        student_info[student_id] = info

        except ZipValidationError as e:
            logger.error(f"ZIP验证失败 ({student_id}): {e}")
        except Exception as e:
            logger.error(f"处理学生ZIP失败 ({student_id}): {e}")

    return student_info


def get_student_info_from_docx(extract_dir, limits=None):
    """
    从已提取的docx文件中提取学生信息

    Args:
        extract_dir: 包含docx文件的目录
        limits: ZIP限制配置（可选）

    Returns:
        {学号: {'name': 姓名, 'time': 提交时间, 'content': 报告内容}}

    说明:
        此函数用于处理已经解压的提交，文件名格式为: 学号-姓名.docx
    """
    if limits is None:
        limits = ZipLimits()

    student_info = {}

    # 匹配学号-姓名格式的文件名
    # 例如: 23071140102-杨凯辉.docx, 23071140201-董雨航.docx
    filename_pattern = re.compile(r'^(\d{11})-([^-]+)\.docx$')

    for docx_file in extract_dir.glob('*.docx'):
        filename = docx_file.name
        match = filename_pattern.match(filename)

        if not match:
            continue

        student_id = match.group(1)
        name = match.group(2)

        info = {'name': name, 'time': None, 'content': None}

        try:
            # 读取docx文件内容
            with open(docx_file, 'rb') as f:
                docx_data = f.read()

            # 验证文件大小
            if len(docx_data) > limits.max_outer_size:
                logger.warning(f"文件过大: {filename}")
                continue

            # 提取文本内容
            text = extract_text_from_docx(docx_data, limits)
            if text:
                content = re.sub(r'\s+', '', text)
                info['content'] = content
                student_info[student_id] = info
            else:
                logger.warning(f"无法从文件中提取文本，已跳过: {filename}")

        except Exception as e:
            logger.error(f"处理docx文件失败 ({filename}): {e}")

    return student_info


def get_student_info(extract_dir, limits=None):
    """
    从答题记录和实验报告中提取学生信息（安全版本）

    自动检测文件类型：
    - 如果目录中包含 .zip 文件，使用 ZIP 提取模式
    - 如果目录中包含 学号-姓名.docx 格式的文件，使用 DOCX 提取模式

    Args:
        extract_dir: 提取后的提交目录
        limits: ZIP限制配置（可选）

    Returns:
        {学号: {'name': 姓名, 'time': 提交时间, 'content': 报告内容}}

    安全改进:
        - ZIP炸弹防护（文件大小、数量限制）
        - 路径遍历防护
        - 异常日志记录
    """
    if limits is None:
        limits = ZipLimits()

    extract_dir = Path(extract_dir)

    # 检查目录中是否有 .zip 文件
    zip_files = list(extract_dir.glob('*.zip'))

    # 检查是否有 学号-姓名.docx 格式的文件
    docx_pattern = re.compile(r'^\d{11}-[^-]+\.docx$')
    docx_files = [f for f in extract_dir.glob('*.docx') if docx_pattern.match(f.name)]

    # 如果有 zip 文件，使用 ZIP 模式
    if zip_files:
        return _get_student_info_from_zip(extract_dir, limits)

    # 如果有 docx 文件，使用 DOCX 模式
    if docx_files:
        return get_student_info_from_docx(extract_dir, limits)

    # 如果都没有，返回空字典
    logger.warning(f"目录中没有找到有效的提交文件: {extract_dir}")
    return {}


def _get_student_info_from_zip(extract_dir, limits=None):
    """
    从ZIP文件中提取学生信息（内部函数）

    Args:
        extract_dir: 提取后的提交目录
        limits: ZIP限制配置（可选）

    Returns:
        {学号: {'name': 姓名, 'time': 提交时间, 'content': 报告内容}}
    """
    if limits is None:
        limits = ZipLimits()

    student_info = {}

    for zip_file in extract_dir.glob('*.zip'):
        # 使用安全的学号提取函数
        student_id = extract_safe_student_id(zip_file.name)
        if not student_id:
            continue

        info = {'name': None, 'time': None, 'content': None}

        try:
            with zipfile.ZipFile(zip_file, 'r') as outer:
                # 验证外层ZIP（防御Zip炸弹）
                validate_zip_size(outer, limits)

                files = outer.namelist()
                if len(files) > 0 and files[0].endswith('.zip'):
                    # 安全提取内层ZIP
                    inner = safe_extract_inner_zip(outer, files[0], limits)
                    inner_files = inner.namelist()

                    # 从答题记录提取姓名和时间
                    doc_files = [f for f in inner_files if '答题记录' in f and f.endswith('.doc')]

                    # 如果没有找到包含"答题记录"的文件，尝试查找所有.doc文件
                    if not doc_files:
                        doc_files = [f for f in inner_files if f.endswith('.doc')]

                    if doc_files:
                        # 验证文件路径（防御路径遍历）
                        validate_path_traversal(doc_files[0])

                        doc_data = inner.read(doc_files[0])
                        doc_str = str(doc_data, errors='ignore')

                        pattern1 = r'<w:t>答题人：[^<]*</w:t>\s*.*?<w:t>([^<]+)</w:t>'
                        name_match = re.search(pattern1, doc_str, re.DOTALL)
                        if name_match:
                            info['name'] = name_match.group(1).strip()

                        pattern2 = r'<w:t>提交时间：[^<]*</w:t>\s*.*?<w:t>(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})[^<]*</w:t>'
                        time_match = re.search(pattern2, doc_str, re.DOTALL)
                        if time_match:
                            info['time'] = time_match.group(1).strip()

                    # 从实验报告提取内容
                    docx_files = [f for f in inner_files if f.endswith('.docx') and '答题记录' not in f]
                    if docx_files:
                        # 验证文件路径
                        validate_path_traversal(docx_files[0])

                        docx_data = inner.read(docx_files[0])
                        text = extract_text_from_docx(docx_data, limits)
                        if text:
                            content = re.sub(r'\s+', '', text)
                            info['content'] = content

                    if info['name'] or info['time']:
                        student_info[student_id] = info

        except ZipValidationError as e:
            logger.error(f"ZIP验证失败 ({student_id}): {e}")
        except Exception as e:
            logger.error(f"处理学生ZIP失败 ({student_id}): {e}")

    return student_info


def extract_team_number(text):
    """
    从文本中提取小组编号

    Args:
        text: 报告文本

    Returns:
        小组编号字符串或None
    """
    # 优先匹配更明确的格式
    patterns = [
        r'第(\d+)组',          # 第X组
        r'组号[：:\s]*(\d+)',  # 组号:X
        r'组长[：:\s]*[^\d]*(\d+)',  # 组长后的数字
        r'组员[：:\s]*[^\d]{0,50}第?(\d+)组',  # 组员后跟第X组
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            team_num = match.group(1)
            # 排除学号（11位）
            if len(team_num) != 11:
                return team_num

    # 如果都没匹配到，尝试搜索"组"周围的数字
    team_matches = re.findall(r'[^\d](\d{1,2})组|[^\d](\d{1,2})组组长', text)
    if team_matches:
        for match in team_matches:
            num = match[0] if match[0] else match[1]
            if num and len(num) <= 2:
                return num

    return None


def get_student_teams(extract_dir, limits=None):
    """
    获取学生的实验小组编号（安全版本）

    Args:
        extract_dir: 提取后的提交目录
        limits: ZIP限制配置（可选）

    Returns:
        {学号: 小组编号}

    安全改进:
        - ZIP炸弹防护
        - 路径遍历防护
        - 异常日志记录
    """
    if limits is None:
        limits = ZipLimits()

    student_teams = {}

    for zip_file in extract_dir.glob('*.zip'):
        # 使用安全的学号提取函数
        student_id = extract_safe_student_id(zip_file.name)
        if not student_id:
            continue

        try:
            with zipfile.ZipFile(zip_file, 'r') as outer:
                # 验证外层ZIP
                validate_zip_size(outer, limits)

                files = outer.namelist()
                if len(files) > 0 and files[0].endswith('.zip'):
                    # 安全提取内层ZIP
                    inner = safe_extract_inner_zip(outer, files[0], limits)

                    docx_files = [f for f in inner.namelist() if f.endswith('.docx') and '答题记录' not in f]
                    if docx_files:
                        # 验证文件路径
                        validate_path_traversal(docx_files[0])

                        docx_data = inner.read(docx_files[0])
                        text = extract_text_from_docx(docx_data, limits)
                        if text:
                            team = extract_team_number(text)
                            if team:
                                student_teams[student_id] = team
        except ZipValidationError as e:
            logger.error(f"ZIP验证失败 ({student_id}): {e}")
        except Exception as e:
            logger.error(f"处理学生ZIP失败 ({student_id}): {e}")

    return student_teams


def extract_team_leader_info(text: str, student_id: str) -> bool:
    """
    从报告中提取是否是组长的信息

    Args:
        text: 报告文本
        student_id: 学生学号

    Returns:
        True if the student is the team leader
    """
    # 查找"组长"后跟学号的情况
    patterns = [
        r'组长[：:\s]*[^\d]*({})'.format(student_id),  # 组长后直接跟学号
        r'组长[：:\s]*(\d+).*?{}'.format(student_id),  # 组长后有其他内容，然后提到学号
    ]

    for pattern in patterns:
        try:
            match = re.search(pattern, text)
            if match:
                return True
        except re.error:
            continue

    # 查找团队成员表格或列表
    # 尝试匹配团队成员区域
    team_patterns = [
        r'1\.1\s*团队成员[^\n]*[\s\S]*?1\.2\s*个人分工',
        r'一、[^\n]*团队[^\n]*[\s\S]*?二、',
        r'团队[^\n]*成员[^\n]*[\s\S]*?分工',
    ]

    for team_pattern in team_patterns:
        team_section = re.search(team_pattern, text)
        if team_section:
            team_text = team_section.group(0)
            # 检查是否在组长行中
            if '组长' in team_text:
                # 尝试多种格式
                lines = team_text.split('\n')
                for i, line in enumerate(lines):
                    if '组长' in line:
                        # 检查当前行和下一行是否包含学号
                        current_content = line
                        if i + 1 < len(lines):
                            current_content += ' ' + lines[i + 1]

                        if student_id in current_content:
                            return True

    return False


def extract_personal_experience(text: str) -> dict:
    """
    从报告中提取心得体会内容和质量评估

    Args:
        text: 报告文本

    Returns:
        {
            'has_experience': bool,
            'content': str,
            'quality': 'good' | 'fair' | 'poor' | 'missing',
            'word_count': int
        }
    """
    # 尝试多种模式匹配心得体会
    patterns = [
        r'个人心得体会[：:：\s\（\(]*.*?[\）\)]*\s*([\s\S]+?)(?=思考题|七、|附录|六、|$)',
        r'6\.3\s*个人心得体会[：:：\s]*([\s\S]+?)(?=七、|思考题|$)',
        r'六、[^\n]*问题与讨论[\s\S]*?个人心得[：:：\s]*([\s\S]+?)(?=思考题|七、|$)',
        r'心得体会[：:：\s]*([\s\S]+?)(?=思考题|七、|附录|$)',
    ]

    content = None
    for pattern in patterns:
        try:
            match = re.search(pattern, text)
            if match:
                content = match.group(1).strip()
                if len(content) > 20:  # 确保内容有意义
                    break
        except re.error:
            continue

    if not content or len(content) < 20:
        return {
            'has_experience': False,
            'content': '',
            'quality': 'missing',
            'word_count': 0
        }

    # 去除多余空白
    content = re.sub(r'\s+', ' ', content).strip()
    word_count = len(content)

    # 评估质量
    quality = 'poor'
    if word_count < 50:
        quality = 'poor'
    elif word_count < 150:
        quality = 'fair'
    else:
        # 检查是否有具体内容
        specific_keywords = ['理解', '学会', '掌握', '实现', '解决', '问题', '收获', '体会', '总结']
        if any(kw in content for kw in specific_keywords):
            quality = 'good'
        else:
            quality = 'fair'

    return {
        'has_experience': True,
        'content': content,
        'quality': quality,
        'word_count': word_count
    }
