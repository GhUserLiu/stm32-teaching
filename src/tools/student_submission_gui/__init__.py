#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
学生端作业自检与自评系统
Student Submission Self-Check & Self-Grade GUI

学生在提交前用本地文件（报告 + 源码）做两件事：
1. 检测输入文件——是否符合提交规范（格式/齐全/章节/代码/图片/思考题）
2. 自评——按 rubric 预测得分 + 逐项失分与改进建议

单份提交编排，复用教师端 auto_grading 后端（读报告 / 校验 / rubric 评分），
不含查重（查重是跨学生比对，学生无法自检）。
"""

__version__ = "2.5.0"
__author__ = "STM32F407 Teaching Team"
