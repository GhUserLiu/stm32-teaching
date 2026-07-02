#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
路径验证工具
Path Validation Utilities

用于防御路径遍历攻击
For defending against Path Traversal attacks

作者: STM32F407 教学团队
版本: 1.0.0
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Optional, Tuple


logger = logging.getLogger(__name__)


class PathValidationError(Exception):
    """路径验证错误异常"""

    def __init__(self, message: str, path: Optional[str] = None):
        """
        初始化异常

        Args:
            message: 错误信息
            path: 相关的路径（可选）
        """
        self.path = path
        full_message = f"路径验证失败: {message}"
        if path:
            full_message += f" (路径: {path})"
        super().__init__(full_message)


def validate_path_allowed(
    path: Path,
    allowed_dirs: List[Path],
    check_exists: bool = False
) -> Path:
    """
    验证路径是否在允许的目录内

    Args:
        path: 要验证的路径
        allowed_dirs: 允许的目录列表
        check_exists: 是否检查路径存在

    Returns:
        解析后的绝对路径

    Raises:
        PathValidationError: 如果路径不在允许目录内

    安全原理:
        - 使用resolve()获取绝对路径，消除..和符号链接
        - 使用relative_to()检查路径关系
        - 如果不在允许目录内，抛出异常
    """
    try:
        # 转换为绝对路径（解析..和符号链接）
        abs_path = path.resolve()
    except (OSError, RuntimeError) as e:
        raise PathValidationError(f"无法解析路径: {e}", str(path))

    # 检查是否在允许的目录内
    for allowed_dir in allowed_dirs:
        try:
            allowed_abs = allowed_dir.resolve()
            # 检查abs_path是否在allowed_abs内
            abs_path.relative_to(allowed_abs)
            return abs_path
        except ValueError:
            continue

    # 构建错误信息
    allowed_str = ", ".join(str(d.resolve()) for d in allowed_dirs)
    raise PathValidationError(
        f"路径 '{abs_path}' 不在允许的目录内。允许的目录: [{allowed_str}]"
    )


def validate_experiment_dir(
    path: Path,
    base_dir: Optional[Path] = None
) -> Path:
    """
    验证实验目录路径

    Args:
        path: 实验目录路径
        base_dir: 基础目录（默认为项目根目录的docs/teaching）

    Returns:
        验证后的路径

    Raises:
        PathValidationError: 如果路径不在允许范围内

    用途:
        验证用户提供的实验目录路径是否在允许的范围内
        防止路径遍历攻击访问敏感文件
    """
    if base_dir is None:
        # 默认允许的目录
        try:
            # 获取项目根目录
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent
            base_dir = project_root / 'docs' / 'teaching'
        except (OSError, RuntimeError):
            # 如果无法获取项目根目录，使用当前目录
            base_dir = Path.cwd() / 'docs' / 'teaching'

    allowed_dirs = [base_dir]

    try:
        return validate_path_allowed(path, allowed_dirs, check_exists=False)
    except PathValidationError as e:
        raise PathValidationError(
            f"实验目录验证失败: {e}",
            str(path)
        )


def safe_path_join(base: Path, *parts) -> Path:
    """
    安全地拼接路径，防止路径遍历

    Args:
        base: 基础路径
        *parts: 路径部分

    Returns:
        安全拼接后的路径

    Raises:
        PathValidationError: 如果检测到路径遍历

    安全原理:
        - 检查每个部分是否包含..或绝对路径
        - 确保结果在基础路径内
    """
    result = base

    for part in parts:
        part_str = str(part)

        # 检查路径遍历序列：仅拒绝整段等于 '..' 的组件（真正的目录上跳），
        # 而非任何含 '..' 子串（会误伤 backup..v2 等合法文件名）；
        # 下方 resolve().relative_to() 仍是逃逸的权威兜底。
        if any(p == '..' for p in Path(part_str).parts):
            raise PathValidationError(
                f"路径包含遍历序列 (..): {part}",
                str(result / part)
            )

        # 检查绝对路径
        part_path = Path(part_str)
        if part_path.is_absolute():
            raise PathValidationError(
                f"路径为绝对路径: {part}",
                str(result / part)
            )

        # 拼接路径
        result = result / part

    # 确保结果在基础路径内
    try:
        result.resolve().relative_to(base.resolve())
    except ValueError:
        raise PathValidationError(
            f"拼接路径超出基础目录",
            str(result)
        )

    return result


def validate_filename_safe(filename: str) -> None:
    """
    验证文件名是否安全

    Args:
        filename: 文件名

    Raises:
        PathValidationError: 如果文件名不安全

    检查项:
        - 路径遍历序列
        - 绝对路径
        - 特殊设备文件名（Windows）
        - 控制字符
    """
    if not filename:
        raise PathValidationError("文件名为空")

    # 检查路径遍历
    if '..' in filename or '/' in filename or '\\' in filename:
        raise PathValidationError(f"文件名包含路径分隔符: {filename}")

    # 检查驱动器字母（Windows绝对路径）
    if len(filename) >= 2 and filename[1] == ':':
        raise PathValidationError(f"文件名包含驱动器字母: {filename}")

    # 检查Windows设备文件名
    windows_devices = [
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    ]
    filename_upper = filename.upper().split('.')[0]
    if filename_upper in windows_devices:
        raise PathValidationError(f"文件名为Windows设备名: {filename}")

    # 检查控制字符
    if any(ord(c) < 32 for c in filename):
        raise PathValidationError(f"文件名包含控制字符: {filename}")

    # 检查保留字符
    reserved_chars = '<>:"|?*'
    if any(c in filename for c in reserved_chars):
        raise PathValidationError(f"文件名包含保留字符: {filename}")


def sanitize_filename(filename: str, replacement: str = '_') -> str:
    """
    清理文件名，移除不安全字符

    Args:
        filename: 原始文件名
        replacement: 替换字符（默认为下划线）

    Returns:
        清理后的文件名

    用途:
        当用户提供的文件名可能不安全时，
        使用此函数清理而非直接拒绝
    """
    # 移除路径分隔符
    result = filename.replace('/', replacement).replace('\\', replacement)

    # 移除驱动器字母
    if len(result) >= 2 and result[1] == ':':
        result = result[0] + replacement + result[2:]

    # 替换保留字符
    reserved_chars = '<>:"|?*'
    for c in reserved_chars:
        result = result.replace(c, replacement)

    # 替换控制字符
    result = ''.join(c if ord(c) >= 32 else replacement for c in result)

    # 限制长度
    if len(result) > 255:
        name, ext = os.path.splitext(result)
        result = name[:255-len(ext)] + ext

    return result


def validate_student_id(student_id: str) -> bool:
    """
    验证学号格式

    Args:
        student_id: 学号字符串

    Returns:
        是否有效

    规则:
        - 11位数字
        - 不包含其他字符
    """
    if not student_id:
        return False

    # 检查长度和格式
    if len(student_id) != 11:
        return False

    if not student_id.isdigit():
        return False

    return True


def extract_safe_student_id(filename: str) -> Optional[str]:
    """
    从文件名中安全提取学号

    Args:
        filename: 文件名

    Returns:
        学号或None

    用途:
        从ZIP文件名中提取学号，同时验证格式
    """
    import re

    # 搜索11位数字
    match = re.search(r'(\d{11})', filename)
    if not match:
        return None

    student_id = match.group(1)

    # 验证学号格式
    if validate_student_id(student_id):
        return student_id

    return None
