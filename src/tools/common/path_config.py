#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
教学系统统一路径配置
Unified Path Configuration for Teaching System

定义所有教学相关脚本的统一目录结构和路径约定
确保所有模块使用一致的输出路径
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExperimentPaths:
    """
    实验目录路径配置

    定义单个实验的完整目录结构，包括：
    - 提交文件目录
    - 处理中间数据目录
    - 最终输出目录
    """

    # 基础路径
    experiment_dir: Path

    # 提交相关目录
    submissions_dir: Path = field(init=False)
    extracted_dir: Path = field(init=False)

    # 处理中间数据目录
    processed_dir: Path = field(init=False)

    # 最终输出目录
    results_dir: Path = field(init=False)

    # results 下的子目录
    reports_dir: Path = field(init=False)      # 教师用报告
    feedback_dir: Path = field(init=False)    # 学生反馈文件
    grading_dir: Path = field(init=False)     # 评分数据
    plagiarism_dir: Path = field(init=False)  # 查重数据

    def __post_init__(self):
        """初始化所有子目录路径"""
        base = self.experiment_dir

        # 提交相关
        self.submissions_dir = base / "submissions"
        self.extracted_dir = self.submissions_dir / "extracted"

        # 处理中间数据
        self.processed_dir = base / "processed"

        # 最终输出
        self.results_dir = base / "results"
        self.reports_dir = self.results_dir / "reports"
        self.feedback_dir = self.results_dir / "feedback"
        self.grading_dir = self.results_dir / "grading"
        self.plagiarism_dir = self.results_dir / "plagiarism"

    def create_all(self) -> None:
        """创建所有目录"""
        self.submissions_dir.mkdir(parents=True, exist_ok=True)
        self.extracted_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        self.grading_dir.mkdir(parents=True, exist_ok=True)
        self.plagiarism_dir.mkdir(parents=True, exist_ok=True)

    # ===== 输出文件路径快捷方法 =====

    # 报告文件（教师用）
    def report_excel(self, class_name: str, experiment_name: str) -> Path:
        """查重报告 Excel 路径"""
        return self.reports_dir / f"{class_name}_{experiment_name}_查重报告.xlsx"

    def report_html(self, class_name: str, experiment_name: str) -> Path:
        """查重报告 HTML 路径"""
        return self.reports_dir / f"{class_name}_{experiment_name}_查重报告.html"

    def grading_excel(self, class_name: str, experiment_name: str) -> Path:
        """成绩表 Excel 路径"""
        return self.reports_dir / f"{class_name}_{experiment_name}_成绩表.xlsx"

    def detailed_grading_excel(self, class_name: str, experiment_name: str) -> Path:
        """详细评分表 Excel 路径"""
        return self.reports_dir / f"{class_name}_{experiment_name}_详细评分表.xlsx"

    # 反馈文件（学生用）
    def student_feedback_docx(self, student_id: str) -> Path:
        """学生反馈 Word 文档路径"""
        return self.feedback_dir / f"{student_id}_反馈.docx"

    def student_feedback_md(self, student_id: str) -> Path:
        """学生反馈 Markdown 路径"""
        return self.feedback_dir / "md" / f"{student_id}_反馈.md"

    def student_feedback_pdf(self, student_id: str) -> Path:
        """学生反馈 PDF 路径"""
        return self.feedback_dir / "pdf" / f"{student_id}_反馈.pdf"

    # JSON 数据文件
    def grading_json(self) -> Path:
        """评分结果 JSON 路径"""
        return self.grading_dir / "grading_results.json"

    def plagiarism_json(self) -> Path:
        """查重结果 JSON 路径"""
        return self.plagiarism_dir / "plagiarism_results.json"

    def evaluations_json(self) -> Path:
        """评估结果 JSON 路径"""
        return self.processed_dir / "evaluations.json"

    def extracted_content_json(self) -> Path:
        """提取内容 JSON 路径"""
        return self.processed_dir / "extracted_content.json"

    # 处理中间文件
    def extracted_content(self) -> Path:
        """提取内容 JSON 路径（同上）"""
        return self.extracted_content_json()


@dataclass
class TeachingPaths:
    """
    教学系统顶层路径配置

    管理整个教学系统的目录结构
    """

    # 项目根目录
    project_root: Path

    # 教学数据目录
    teaching_data_dir: Path = field(init=False)

    # 学期目录
    semester_dir: Path = field(init=False)

    def __post_init__(self):
        """初始化教学数据目录"""
        self.teaching_data_dir = self.project_root / "data" / "teaching"

    def get_semester_dir(self, semester: str) -> Path:
        """获取学期目录"""
        return self.teaching_data_dir / semester

    def get_class_dir(self, semester: str, class_name: str) -> Path:
        """获取班级目录"""
        return self.get_semester_dir(semester) / class_name

    def get_experiment_paths(
        self,
        semester: str,
        class_name: str,
        experiment: str
    ) -> ExperimentPaths:
        """
        获取实验路径配置

        Args:
            semester: 学期（如 "2026-春季"）
            class_name: 班级名称（如 "汽服2301B班"）
            experiment: 实验编号（如 "07-car-gear"）

        Returns:
            ExperimentPaths 实例
        """
        experiment_dir = self.get_class_dir(semester, class_name) / experiment
        return ExperimentPaths(experiment_dir=experiment_dir)

    def list_classes(self, semester: str) -> list[Path]:
        """列出学期下的所有班级"""
        semester_path = self.get_semester_dir(semester)
        if not semester_path.exists():
            return []
        # 跳过下划线开头的非班级目录（如多班级合并产物 _跨班级比对/），避免被当成班级
        return [d for d in semester_path.iterdir()
                if d.is_dir() and not d.name.startswith("_")]


# ===== 全局实例 =====

def get_teaching_paths(project_root: Optional[Path] = None) -> TeachingPaths:
    """
    获取教学路径配置实例

    Args:
        project_root: 项目根目录，默认自动检测

    Returns:
        TeachingPaths 实例
    """
    if project_root is None:
        # 自动检测项目根目录
        project_root = Path(__file__).parent.parent.parent.parent
    return TeachingPaths(project_root=project_root)


def get_experiment_paths(
    semester: str,
    class_name: str,
    experiment: str,
    project_root: Optional[Path] = None
) -> ExperimentPaths:
    """
    直接获取实验路径配置

    Args:
        semester: 学期（如 "2026-春季"）
        class_name: 班级名称（如 "汽服2301B班"）
        experiment: 实验编号（如 "07-car-gear"）
        project_root: 项目根目录，默认自动检测

    Returns:
        ExperimentPaths 实例
    """
    teaching_paths = get_teaching_paths(project_root)
    return teaching_paths.get_experiment_paths(semester, class_name, experiment)


# ===== 常用路径快捷方法 =====

def get_results_dir(experiment_dir: Path) -> Path:
    """
    获取结果目录路径（兼容旧代码）

    Args:
        experiment_dir: 实验目录

    Returns:
        结果目录路径
    """
    paths = ExperimentPaths(experiment_dir=experiment_dir)
    return paths.results_dir


def get_reports_dir(experiment_dir: Path) -> Path:
    """
    获取报告目录路径

    Args:
        experiment_dir: 实验目录

    Returns:
        报告目录路径
    """
    paths = ExperimentPaths(experiment_dir=experiment_dir)
    return paths.reports_dir


def get_feedback_dir(experiment_dir: Path) -> Path:
    """
    获取反馈目录路径

    Args:
        experiment_dir: 实验目录

    Returns:
        反馈目录路径
    """
    paths = ExperimentPaths(experiment_dir=experiment_dir)
    return paths.feedback_dir


# ===== 目录结构说明（供文档使用） =====

DIRECTORY_STRUCTURE = """
教学系统标准目录结构
======================

experiment_dir/                    # 实验根目录（如：汽服2301B班/07-car-gear）
├── submissions/                   # 提交文件目录
│   └── extracted/                # 提取后的提交文件
├── processed/                     # 处理中间数据
│   ├── extracted_content.json    # 提取的内容
│   └── evaluations.json          # 评估结果
└── results/                       # 最终输出（统一）
    ├── reports/                   # 教师用报告文件
    │   ├── 查重报告.xlsx
    │   ├── 查重报告.html
    │   ├── 成绩表.xlsx
    │   └── 详细评分表.xlsx
    ├── feedback/                  # 学生反馈文件
    │   ├── 学号_反馈.docx         # Word 格式反馈
    │   ├── md/                    # Markdown 格式（可选）
    │   └── pdf/                   # PDF 格式（可选）
    ├── grading/                   # 评分数据
    │   └── grading_results.json
    └── plagiarism/                # 查重数据
        └── plagiarism_results.json


路径使用约定
============

1. 教师报告文件
   - 查重报告：results/reports/
   - 成绩表格：results/reports/
   - 详细评分：results/reports/

2. 学生反馈文件
   - Word 反馈：results/feedback/
   - Markdown：results/feedback/md/
   - PDF：results/feedback/pdf/

3. JSON 数据文件
   - 评分数据：results/grading/
   - 查重数据：results/plagiarism/
   - 评估数据：processed/

4. 提交文件
   - 原始提交：submissions/
   - 提取内容：submissions/extracted/
"""


if __name__ == "__main__":
    # 打印目录结构说明
    print(DIRECTORY_STRUCTURE)

    # 示例：获取路径
    paths = get_experiment_paths(
        semester="2026-春季",
        class_name="汽服2301B班",
        experiment="07-car-gear"
    )

    print("\n示例路径：")
    print(f"实验目录: {paths.experiment_dir}")
    print(f"提交目录: {paths.submissions_dir}")
    print(f"结果目录: {paths.results_dir}")
    print(f"报告目录: {paths.reports_dir}")
    print(f"反馈目录: {paths.feedback_dir}")
