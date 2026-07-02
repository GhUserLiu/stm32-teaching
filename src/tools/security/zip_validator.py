#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZIP文件安全验证器
ZIP File Security Validator

用于防御Zip炸弹攻击和路径遍历攻击
For defending against Zip Bomb and Path Traversal attacks

作者: STM32F407 教学团队
版本: 1.0.0
"""

import zipfile
import io
import logging
from pathlib import Path
from typing import Optional, Tuple, List
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class ZipLimits:
    """
    ZIP处理限制配置

    Attributes:
        max_outer_size: 外层ZIP最大大小（字节）
        max_inner_size: 内层ZIP单个文件最大大小（字节）
        max_file_count: 最大文件数量
        max_nesting_level: 最大嵌套层级
        max_filename_length: 文件名最大长度
        allow_symlinks: 是否允许符号链接
    """
    max_outer_size: int = 100 * 1024 * 1024    # 100MB
    max_inner_size: int = 50 * 1024 * 1024     # 50MB
    max_file_count: int = 1000                  # 1000个文件
    max_nesting_level: int = 2                  # 2层嵌套
    max_filename_length: int = 255             # 255字符
    allow_symlinks: bool = False               # 不允许符号链接


class ZipValidationError(Exception):
    """ZIP验证错误异常"""

    def __init__(self, message: str, zip_file: Optional[str] = None):
        """
        初始化异常

        Args:
            message: 错误信息
            zip_file: 相关的ZIP文件名（可选）
        """
        self.zip_file = zip_file
        # 保留未加前缀的原文，供上层拼接时避免重复前缀（如 safe_extract_zip）
        self.raw_message = message
        full_message = f"ZIP验证失败: {message}"
        if zip_file:
            full_message += f" (文件: {zip_file})"
        super().__init__(full_message)


def validate_path_traversal(filename: str) -> None:
    """
    检查路径遍历攻击

    检测ZIP文件中的路径是否包含遍历序列（..）或绝对路径

    Args:
        filename: ZIP内文件名

    Raises:
        ZipValidationError: 如果检测到路径遍历攻击

    安全原理:
        - 禁止..防止访问父目录
        - 禁止绝对路径防止访问系统文件
        - 限制路径长度防止缓冲区溢出
    """
    if not filename:
        raise ZipValidationError("文件名为空")

    # 检查..路径遍历
    if '..' in filename:
        raise ZipValidationError(f"检测到路径遍历攻击 (包含'..'): {filename}")

    # 检查绝对路径
    if filename.startswith('/') or (len(filename) >= 2 and filename[1] == ':'):
        raise ZipValidationError(f"检测到绝对路径: {filename}")

    # Windows路径遍历检查
    if ':' in filename and '\\' in filename:
        raise ZipValidationError(f"检测到Windows绝对路径: {filename}")

    # 检查过长的路径
    if len(filename) > 255:
        raise ZipValidationError(f"文件名过长 ({len(filename)} > 255): {filename[:50]}...")

    # 检查设备文件（Windows）
    windows_devices = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
                       'LPT1', 'LPT2', 'LPT3', 'LPT4']
    filename_upper = filename.upper().split('.')[0]
    if filename_upper in windows_devices:
        raise ZipValidationError(f"检测到Windows设备文件名: {filename}")


def validate_zip_size(zip_file: zipfile.ZipFile, limits: ZipLimits) -> None:
    """
    验证ZIP文件大小和文件数量

    Args:
        zip_file: ZipFile对象
        limits: 限制配置

    Raises:
        ZipValidationError: 如果超过限制

    安全原理:
        - Zip炸弹通过嵌套压缩使小文件解压后变成超大文件
        - 通过限制解压后大小和文件数量防御
        - 检查压缩比率防止高压缩比攻击
    """
    file_list = zip_file.filelist

    # 检查文件数量
    if len(file_list) > limits.max_file_count:
        raise ZipValidationError(
            f"文件数量超过限制: {len(file_list)} > {limits.max_file_count}"
        )

    # 检查解压后总大小
    total_uncompressed = sum(z.file_size for z in file_list)
    total_compressed = sum(z.compress_size for z in file_list)

    if total_uncompressed > limits.max_outer_size:
        raise ZipValidationError(
            f"解压后总大小超过限制: {total_uncompressed:,} bytes > {limits.max_outer_size:,} bytes"
        )

    # 检查压缩比（防御高压缩比攻击）
    if total_compressed > 0:
        compression_ratio = total_uncompressed / total_compressed
        if compression_ratio > 100:  # 压缩比超过100倍可疑
            logger.warning(f"高压缩比检测: {compression_ratio:.1f}:1 (可能为Zip炸弹)")


def safe_extract_inner_zip(
    outer_zip: zipfile.ZipFile,
    inner_filename: str,
    limits: ZipLimits
) -> zipfile.ZipFile:
    """
    安全提取内层ZIP

    Args:
        outer_zip: 外层ZipFile对象
        inner_filename: 内层ZIP文件名
        limits: 限制配置

    Returns:
        内层ZipFile对象

    Raises:
        ZipValidationError: 如果验证失败

    安全原理:
        - 先验证路径安全性
        - 限制读取数据大小
        - 验证内层ZIP结构
    """
    # 验证路径
    validate_path_traversal(inner_filename)

    # 获取文件信息
    try:
        info = outer_zip.getinfo(inner_filename)
    except KeyError:
        raise ZipValidationError(f"内层ZIP文件不存在: {inner_filename}")

    # 检查文件大小
    if info.file_size > limits.max_outer_size:
        raise ZipValidationError(
            f"内层ZIP文件过大: {info.file_size:,} bytes > {limits.max_outer_size:,} bytes"
        )

    # 读取内层数据
    try:
        inner_data = outer_zip.read(inner_filename)
    except zipfile.BadZipFile as e:
        raise ZipValidationError(f"读取内层ZIP失败: {e}")

    if len(inner_data) > limits.max_outer_size:
        raise ZipValidationError(
            f"内层ZIP数据过大: {len(inner_data):,} bytes"
        )

    # 创建内层ZIP对象
    try:
        inner_zip = zipfile.ZipFile(io.BytesIO(inner_data), 'r')
    except zipfile.BadZipFile as e:
        raise ZipValidationError(f"内层ZIP格式错误: {e}")

    # 验证内层ZIP
    validate_zip_size(inner_zip, limits)

    # 检查所有内层文件路径
    for zinfo in inner_zip.filelist:
        validate_path_traversal(zinfo.filename)

    return inner_zip


def is_safe_zip_file(
    zip_path: Path,
    limits: Optional[ZipLimits] = None
) -> Tuple[bool, str]:
    """
    检查ZIP文件是否安全

    Args:
        zip_path: ZIP文件路径
        limits: 限制配置（可选）

    Returns:
        (是否安全, 错误信息)

    用途:
        在处理ZIP文件前快速检查安全性
    """
    if limits is None:
        limits = ZipLimits()

    try:
        if not zip_path.exists():
            return False, "文件不存在"

        # 检查文件大小
        file_size = zip_path.stat().st_size
        if file_size > limits.max_outer_size:
            return False, f"文件过大: {file_size:,} bytes"

        with zipfile.ZipFile(zip_path, 'r') as zf:
            validate_zip_size(zf, limits)

            # 检查所有文件路径
            for zinfo in zf.filelist:
                validate_path_traversal(zinfo.filename)

        return True, ""

    except ZipValidationError as e:
        return False, e.raw_message
    except Exception as e:
        return False, f"验证异常: {e}"


def safe_extract_zip(
    zip_path: Path,
    extract_dir: Path,
    limits: Optional[ZipLimits] = None
) -> None:
    """
    安全地解压ZIP文件到指定目录

    Args:
        zip_path: ZIP文件路径
        extract_dir: 解压目标目录
        limits: 限制配置（可选）

    Raises:
        ZipValidationError: 如果验证失败或解压失败

    安全特性:
        - 验证ZIP文件大小
        - 验证解压后的文件数量
        - 检查路径遍历攻击
        - 防止Zip炸弹攻击
    """
    if limits is None:
        limits = ZipLimits()

    # 验证ZIP文件安全性
    is_safe, error_msg = is_safe_zip_file(zip_path, limits)
    if not is_safe:
        # error_msg 已是未加前缀的原文；ZipValidationError.__init__ 会补一层「ZIP验证失败:」前缀，
        # 此处不再额外包装，避免出现「ZIP验证失败:ZIP文件验证失败:ZIP验证失败:…」的三重前缀。
        raise ZipValidationError(error_msg)

    # 创建解压目录
    extract_dir.mkdir(parents=True, exist_ok=True)

    # 安全解压
    with zipfile.ZipFile(zip_path, 'r') as zf:
        # 再次检查所有文件路径
        for zinfo in zf.filelist:
            validate_path_traversal(zinfo.filename)

        # 验证文件数量
        if len(zf.filelist) > limits.max_file_count:
            raise ZipValidationError(
                f"文件数量过多: {len(zf.filelist)} > {limits.max_file_count}"
            )

        # 解压所有文件
        for zinfo in zf.filelist:
            # 跳过目录
            if zinfo.filename.endswith('/'):
                continue

            # 验证路径
            validate_path_traversal(zinfo.filename)

            # 检查文件名长度
            if len(zinfo.filename) > limits.max_filename_length:
                raise ZipValidationError(
                    f"文件名过长: {len(zinfo.filename)} > {limits.max_filename_length}"
                )

            # 检查是否为符号链接（如果不允许）
            if not limits.allow_symlinks:
                # 检查是否为符号链接（兼容不同Python版本）
                is_link = False
                if hasattr(zinfo, 'is_symlink'):
                    is_link = zinfo.is_symlink()
                elif zinfo.external_attr & 0xA000:  # Unix symlink bit
                    is_link = True

                if is_link:
                    raise ZipValidationError(f"不允许符号链接: {zinfo.filename}")

            # 解压文件（处理中文文件名编码）
            try:
                # 尝试处理中文文件名编码
                # Windows上ZIP文件通常用CP437编码，但中文可能是GBK
                try:
                    # 尝试用GBK解码文件名
                    decoded_name = zinfo.filename.encode('cp437').decode('gbk')
                    target_path = extract_dir / decoded_name
                    # 创建父目录
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    # 写入文件
                    with open(target_path, 'wb') as f:
                        f.write(zf.read(zinfo))
                except (UnicodeDecodeError, UnicodeEncodeError):
                    # 如果编码转换失败，使用原始方式
                    zf.extract(zinfo, extract_dir)
            except OSError as e:
                # 文件系统层错误：最常见为 Windows MAX_PATH(260) 超长——学生源码包里
                # CubeMX 生成的 CMSIS/NN/NN_Lib_Tests 等深层目录路径轻易超过 260，
                # 若某个深层文件写失败就让整体解压中断，会连累真工程（Makefile/Core/Drivers，
                # 路径较短）也被判"解压失败→编译跳过→0 分"。此处仅跳过该单个文件并记日志，
                # 不中断整体解压；真正的工程文件仍能正常落盘，编译不受影响。
                logger.warning("跳过无法写入的文件（可能路径超过 Windows 260 限制）: %s (%s)",
                               zinfo.filename, e)
                continue
            except Exception as e:
                raise ZipValidationError(f"解压文件失败 {zinfo.filename}: {e}")


def safe_extract_text_from_docx(
    docx_data: bytes,
    limits: Optional[ZipLimits] = None
) -> Optional[str]:
    """
    安全从docx文件中提取文本

    Args:
        docx_data: docx文件二进制数据
        limits: 限制配置（可选）

    Returns:
        提取的文本或None

    注意:
        此函数只提取文本，不执行XML解析
        XML解析由xml_parser模块处理
    """
    if limits is None:
        limits = ZipLimits()

    try:
        # 检查数据大小
        if len(docx_data) > limits.max_inner_size:
            logger.warning(f"docx数据过大: {len(docx_data):,} bytes")
            return None

        with zipfile.ZipFile(io.BytesIO(docx_data), 'r') as docx:
            # 验证docx ZIP结构
            validate_zip_size(docx, limits)

            # 读取document.xml
            try:
                xml_content = docx.read('word/document.xml')
            except KeyError:
                logger.warning("docx文件缺少document.xml")
                return None

            # XML解析由xml_parser模块处理
            return xml_content

    except ZipValidationError as e:
        logger.warning(f"ZIP验证失败: {e}")
        return None
    except Exception as e:
        logger.error(f"提取docx失败: {e}")
        return None
