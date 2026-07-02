#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
7z 文件安全验证器
7z File Security Validator

与 zip_validator 对齐的安全解压能力，用于学生提交的 .7z 源码包
（学习通导出的期末综合项目源码常见 .7z 格式）。

安全特性：
- 对内部条目逐条做路径遍历校验（复用 zip_validator.validate_path_traversal）
- 限制解压后总大小与文件数量（防御压缩炸弹）
- py7zr 未安装时抛清晰的 ZipValidationError，由上层优雅降级

作者: STM32F407 教学团队
"""

from pathlib import Path
from typing import Optional

from .zip_validator import ZipValidationError, ZipLimits, validate_path_traversal

try:
    import py7zr  # type: ignore
    _HAS_PY7ZR = True
except ImportError:
    _HAS_PY7ZR = False


def is_safe_7z_file(zip_path: Path, limits: Optional[ZipLimits] = None) -> bool:
    """快速检查 7z 是否可安全解压（路径遍历 / 文件数 / 解压后大小）。"""
    if not _HAS_PY7ZR:
        return False
    limits = limits or ZipLimits()
    try:
        if not zip_path.exists():
            return False
        if zip_path.stat().st_size > limits.max_outer_size:
            return False
        with py7zr.SevenZipFile(zip_path, "r") as zf:
            infos = zf.list()
        if len(infos) > limits.max_file_count:
            return False
        total = sum(getattr(i, "uncompressed", 0) or 0 for i in infos)
        if total > limits.max_outer_size:
            return False
        for info in infos:
            name = getattr(info, "filename", "") or ""
            if name.endswith("/"):
                continue
            validate_path_traversal(name)
        return True
    except ZipValidationError:
        return False
    except Exception:
        return False


def safe_extract_7z(
    zip_path: Path,
    extract_dir: Path,
    limits: Optional[ZipLimits] = None,
) -> None:
    """安全地解压 7z 到指定目录。

    Args:
        zip_path: 7z 文件路径
        extract_dir: 解压目标目录
        limits: 限制配置（可选）

    Raises:
        ZipValidationError: py7zr 未安装、路径遍历、超限或解压失败
    """
    if not _HAS_PY7ZR:
        raise ZipValidationError(
            "未安装 py7zr，无法解压 .7z（教师端请：pip install py7zr）"
        )

    limits = limits or ZipLimits()

    if not zip_path.exists():
        raise ZipValidationError(f"7z 文件不存在: {zip_path}")

    # 大小 / 数量 / 路径遍历校验
    if zip_path.stat().st_size > limits.max_outer_size:
        raise ZipValidationError(
            f"7z 文件过大: {zip_path.stat().st_size:,} bytes"
        )

    try:
        with py7zr.SevenZipFile(zip_path, "r") as zf:
            infos = zf.list()
    except py7zr.Bad7zFile as e:  # type: ignore
        raise ZipValidationError(f"7z 格式错误: {e}")

    if len(infos) > limits.max_file_count:
        raise ZipValidationError(
            f"文件数量超过限制: {len(infos)} > {limits.max_file_count}"
        )

    total_uncompressed = sum(getattr(i, "uncompressed", 0) or 0 for i in infos)
    if total_uncompressed > limits.max_outer_size:
        raise ZipValidationError(
            f"解压后总大小超过限制: {total_uncompressed:,} bytes"
        )

    for info in infos:
        name = getattr(info, "filename", "") or ""
        if name.endswith("/"):
            continue
        validate_path_traversal(name)

    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        with py7zr.SevenZipFile(zip_path, "r") as zf:
            zf.extractall(path=extract_dir)
    except Exception as e:
        raise ZipValidationError(f"解压 7z 失败: {e}")
