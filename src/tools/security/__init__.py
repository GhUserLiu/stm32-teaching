# -*- coding: utf-8 -*-
"""
安全工具模块
Security Tools Module

提供文件处理、路径验证、XML解析、数据脱敏等安全功能

作者: STM32F407 教学团队
版本: 1.0.0
"""

from .zip_validator import (
    ZipLimits,
    ZipValidationError,
    validate_zip_size,
    validate_path_traversal,
    safe_extract_inner_zip
)

from .path_validator import (
    PathValidationError,
    validate_path_allowed,
    validate_experiment_dir,
    safe_path_join
)

from .xml_parser import (
    safe_parse_xml_string,
    safe_parse_xml_file,
    extract_text_from_docx_xml
)

from .anonymizer import (
    StudentDataAnonymizer,
    AnonymizationConfig,
    create_anonymized_mapping,
    apply_id_mapping
)

__all__ = [
    # ZIP验证
    'ZipLimits',
    'ZipValidationError',
    'validate_zip_size',
    'validate_path_traversal',
    'safe_extract_inner_zip',

    # 路径验证
    'PathValidationError',
    'validate_path_allowed',
    'validate_experiment_dir',
    'safe_path_join',

    # XML解析
    'safe_parse_xml_string',
    'safe_parse_xml_file',
    'extract_text_from_docx_xml',

    # 数据脱敏
    'StudentDataAnonymizer',
    'AnonymizationConfig',
    'create_anonymized_mapping',
    'apply_id_mapping',
]
