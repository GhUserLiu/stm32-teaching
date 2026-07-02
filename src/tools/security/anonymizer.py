#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据脱敏工具
Data Anonymization Tools

保护敏感学生信息
For protecting sensitive student information

作者: STM32F407 教学团队
版本: 1.0.0
"""

import re
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class AnonymizationConfig:
    """
    脱敏配置

    Attributes:
        mask_student_id: 是否脱敏学号
        mask_name: 是否脱敏姓名
        preserve_last_digits: 保留学号后N位
        preserve_name_length: 保留姓名长度（用星号）
        mask_pattern: 默认脱敏符号
    """
    mask_student_id: bool = True           # 脱敏学号
    mask_name: bool = True                  # 脱敏姓名
    preserve_last_digits: int = 4          # 保留学号后4位
    preserve_name_length: bool = True      # 保留姓名长度
    mask_pattern: str = '***'              # 默认脱敏符号


class StudentDataAnonymizer:
    """
    学生数据脱敏器

    用于在报告生成时脱敏学生敏感信息
    """

    def __init__(self, config: Optional[AnonymizationConfig] = None):
        """
        初始化脱敏器

        Args:
            config: 脱敏配置（可选）
        """
        self.config = config or AnonymizationConfig()

    def anonymize_student_id(self, student_id: str) -> str:
        """
        脱敏学号

        Args:
            student_id: 原始学号（11位）

        Returns:
            脱敏后的学号，如 "*******1234"

        示例:
            >>> anonymizer = StudentDataAnonymizer()
            >>> anonymizer.anonymize_student_id("20230011234")
            '*******1234'
        """
        if not self.config.mask_student_id:
            return student_id

        if not student_id:
            return self.config.mask_pattern

        # 如果学号长度异常，返回完全脱敏
        if len(student_id) < self.config.preserve_last_digits:
            return self.config.mask_pattern

        # 保留后N位
        visible_length = self.config.preserve_last_digits
        masked_length = len(student_id) - visible_length

        return '*' * masked_length + student_id[-visible_length:]

    def anonymize_name(self, name: str) -> str:
        """
        脱敏姓名

        Args:
            name: 原始姓名

        Returns:
            脱敏后的姓名，如 "张**" 或 "***"

        示例:
            >>> anonymizer = StudentDataAnonymizer()
            >>> anonymizer.anonymize_name("张三")
            '张*'
            >>> anonymizer.anonymize_name("欧阳娜娜")
            '欧***'
        """
        if not self.config.mask_name or not name:
            return name

        if self.config.preserve_name_length:
            # 保留姓氏和长度
            if len(name) <= 1:
                return name[0] + '*'
            return name[0] + '*' * (len(name) - 1)
        else:
            return self.config.mask_pattern

    def anonymize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        脱敏字典中的学生信息

        Args:
            data: 包含学生信息的字典

        Returns:
            脱敏后的字典

        支持的字段:
            - student_id, student1, student2: 学号
            - name, name1, name2: 姓名
            - similar_to: 学号
        """
        result = data.copy()

        # 脱敏学号字段
        for key in ['student_id', 'student1', 'student2', 'similar_to']:
            if key in result and result[key]:
                result[key] = self.anonymize_student_id(str(result[key]))

        # 脱敏姓名字段
        for key in ['name', 'name1', 'name2']:
            if key in result and result[key]:
                result[key] = self.anonymize_name(str(result[key]))

        return result

    def anonymize_similarity_result(self, result: Dict) -> Dict:
        """
        脱敏相似度检测结果

        Args:
            result: 相似度结果字典

        Returns:
            脱敏后的结果
        """
        anonymized = result.copy()

        # 脱敏学生信息
        if 'student_id' in anonymized:
            anonymized['student_id'] = self.anonymize_student_id(anonymized['student_id'])
        if 'similar_to' in anonymized:
            anonymized['similar_to'] = self.anonymize_student_id(anonymized['similar_to'])

        # 脱敏metadata中的姓名
        if 'metadata' in anonymized and isinstance(anonymized['metadata'], dict):
            metadata = anonymized['metadata'].copy()
            if 'name1' in metadata:
                metadata['name1'] = self.anonymize_name(metadata['name1'])
            if 'name2' in metadata:
                metadata['name2'] = self.anonymize_name(metadata['name2'])
            anonymized['metadata'] = metadata

        return anonymized

    def anonymize_report_data(self, data: Dict) -> Dict:
        """
        脱敏完整报告数据

        Args:
            data: 报告数据字典

        Returns:
            脱敏后的报告数据
        """
        anonymized = data.copy()

        # 脱敏汇总信息
        if 'summary' in anonymized and isinstance(anonymized['summary'], dict):
            summary = anonymized['summary'].copy()
            # 这里可以添加更多汇总信息的脱敏逻辑
            anonymized['summary'] = summary

        # 脱敏详细信息列表
        if 'suspicious_details' in anonymized and isinstance(anonymized['suspicious_details'], list):
            anonymized['suspicious_details'] = [
                self.anonymize_similarity_result(item)
                for item in anonymized['suspicious_details']
            ]

        # 脱敏团伙信息
        if 'groups' in anonymized and isinstance(anonymized['groups'], list):
            anonymized['groups'] = [
                {
                    **group,
                    'members': [
                        self.anonymize_student_id(member)
                        for member in group.get('members', [])
                    ]
                }
                for group in anonymized['groups']
            ]

        return anonymized


def create_anonymized_mapping(original_ids: List[str]) -> Dict[str, str]:
    """
    创建学号到匿名ID的映射

    Args:
        original_ids: 原始学号列表

    Returns:
        映射字典 {原学号: 匿名ID}

    用途:
        在需要完全匿名的情况下，用随机ID替换学号
    """
    import random
    import string

    mapping = {}
    for i, student_id in enumerate(original_ids):
        # 生成格式为 S001, S002 的匿名ID
        anonymous_id = f"S{i+1:03d}"
        mapping[student_id] = anonymous_id

    return mapping


def apply_id_mapping(data: Dict, id_mapping: Dict[str, str]) -> Dict:
    """
    应用ID映射到数据

    Args:
        data: 原始数据
        id_mapping: ID映射字典

    Returns:
        应用映射后的数据
    """
    if not data or not id_mapping:
        return data

    result = data.copy()

    # 递归替换所有学号
    if isinstance(result, dict):
        for key, value in result.items():
            if key in ['student_id', 'student1', 'student2', 'similar_to']:
                if isinstance(value, str) and value in id_mapping:
                    result[key] = id_mapping[value]
            elif isinstance(value, (dict, list)):
                result[key] = apply_id_mapping(value, id_mapping)
    elif isinstance(result, list):
        result = [apply_id_mapping(item, id_mapping) for item in result]

    return result
