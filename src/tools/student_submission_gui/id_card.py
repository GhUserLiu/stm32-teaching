#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
学生身份信息
StudentIdentity

从实验报告文件名解析（班级-学号-姓名-实验报告）或由学生手动填写。
复用教师端 SubmissionProcessor.FILENAME_PATTERN 同一正则，保证自检端
自动回填与教师端后续解析口径一致。
"""

import re
from dataclasses import dataclass


# 与 tools.auto_grading.submission_processor.FILENAME_PATTERN 完全一致
FILENAME_PATTERN = re.compile(r'(.+)-(\d{11})-([一-龥]{2,4})-实验报告')


@dataclass
class StudentIdentity:
    """学生身份（班级 / 学号 / 姓名）。"""
    class_name: str = ""
    student_id: str = ""
    name: str = ""

    def is_complete(self) -> bool:
        """三项均非空视为完整。"""
        return bool(self.class_name and self.student_id and self.name)

    @classmethod
    def from_filename(cls, stem: str) -> "StudentIdentity":
        """从文件名（去扩展名）解析身份。

        匹配 `{班级}-{11位学号}-{2~4字姓名}-实验报告`。
        不匹配返回空身份（由 UI 让用户手填）。
        """
        if not stem:
            return cls()
        m = FILENAME_PATTERN.search(stem)
        if not m:
            return cls()
        class_name, student_id, name = m.groups()
        return cls(class_name=class_name, student_id=student_id, name=name)

    @staticmethod
    def filename_is_canonical(stem: str) -> bool:
        """文件名是否符合提交命名规范（用于显示规范状态徽标）。"""
        return bool(stem and FILENAME_PATTERN.search(stem))
