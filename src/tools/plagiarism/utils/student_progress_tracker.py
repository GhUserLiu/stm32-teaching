#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
学生进步追踪模块
Student Progress Tracker

追踪学生在多个实验中的表现，提供学习建议
"""

import json
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
from statistics import mean, linear_regression


class Trend(Enum):
    """进步趋势"""
    IMPROVING = "improving"      # 持续进步
    STABLE = "stable"            # 稳定
    DECLINING = "declining"      # 下滑
    INSUFFICIENT_DATA = "insufficient_data"  # 数据不足


@dataclass
class ExperimentRecord:
    """单次实验记录"""
    experiment_id: str
    experiment_name: str
    date: datetime
    total_score: float
    max_score: float
    grade: str

    # 分类得分
    code_quality: float = 0.0
    principle_understanding: float = 0.0
    report_quality: float = 0.0
    team_collaboration: float = 0.0

    # 标记
    plagiarism_detected: bool = False
    needs_review: bool = False


@dataclass
class StudentProfile:
    """学生档案"""
    student_id: str
    name: str
    class_name: str

    # 实验记录
    experiments: List[ExperimentRecord] = field(default_factory=list)

    # 统计信息
    total_experiments: int = 0
    average_score: float = 0.0
    best_score: float = 0.0
    worst_score: float = 0.0

    # 趋势分析
    score_trend: Trend = Trend.INSUFFICIENT_DATA
    recent_trend: str = ""  # 最近表现描述

    # 薄弱环节
    weak_areas: List[str] = field(default_factory=list)
    strong_areas: List[str] = field(default_factory=list)

    # 学习建议
    suggestions: List[str] = field(default_factory=list)

    # 风险标记
    at_risk: bool = False
    risk_reasons: List[str] = field(default_factory=list)


class StudentProgressTracker:
    """学生进步追踪器"""

    def __init__(self, data_dir: Path = None):
        """
        初始化追踪器

        Args:
            data_dir: 数据存储目录
        """
        if data_dir is None:
            project_root = Path(__file__).parents[3]
            data_dir = project_root / 'student_profiles'

        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 使用SQLite数据库
        self.db_path = self.data_dir / 'progress.db'
        self._init_database()

    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 学生表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                name TEXT,
                class_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 实验记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                experiment_id TEXT,
                experiment_name TEXT,
                date TIMESTAMP,
                total_score REAL,
                max_score REAL,
                grade TEXT,
                code_quality REAL DEFAULT 0,
                principle_understanding REAL DEFAULT 0,
                report_quality REAL DEFAULT 0,
                team_collaboration REAL DEFAULT 0,
                plagiarism_detected BOOLEAN DEFAULT 0,
                needs_review BOOLEAN DEFAULT 0,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                UNIQUE(student_id, experiment_id)
            )
        ''')

        # 分类得分表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS category_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_record_id INTEGER,
                category_id TEXT,
                score REAL,
                max_score REAL,
                FOREIGN KEY (experiment_record_id) REFERENCES experiments(id)
            )
        ''')

        conn.commit()
        conn.close()

    def add_experiment_record(
        self,
        student_id: str,
        name: str,
        class_name: str,
        experiment_id: str,
        experiment_name: str,
        grading_result: dict
    ) -> bool:
        """
        添加实验记录

        Args:
            student_id: 学号
            name: 姓名
            class_name: 班级
            experiment_id: 实验ID
            experiment_name: 实验名称
            grading_result: 评分结果字典

        Returns:
            是否成功
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 添加/更新学生信息
            cursor.execute('''
                INSERT OR REPLACE INTO students (student_id, name, class_name, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (student_id, name, class_name))

            # 提取分类得分
            category_scores_dict = grading_result.get('category_scores', {})

            # 添加实验记录
            cursor.execute('''
                INSERT OR REPLACE INTO experiments
                (student_id, experiment_id, experiment_name, date, total_score, max_score, grade,
                 code_quality, principle_understanding, report_quality, team_collaboration,
                 plagiarism_detected, needs_review)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                student_id,
                experiment_id,
                experiment_name,
                datetime.now(),
                grading_result.get('total_score', 0),
                grading_result.get('max_score', 100),
                grading_result.get('grade', 'F'),
                category_scores_dict.get('code_quality', {}).get('earned', 0),
                category_scores_dict.get('principle_understanding', {}).get('earned', 0),
                category_scores_dict.get('report_quality', {}).get('earned', 0),
                category_scores_dict.get('team_collaboration', {}).get('earned', 0),
                grading_result.get('plagiarism_info', {}).get('penalty_applied', 0) > 0,
                grading_result.get('auto_confidence', 1.0) < 0.7
            ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"[进步追踪] 添加记录失败: {e}")
            return False

    def get_student_profile(self, student_id: str) -> Optional[StudentProfile]:
        """
        获取学生档案

        Args:
            student_id: 学号

        Returns:
            学生档案
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 获取学生基本信息
            cursor.execute('''
                SELECT student_id, name, class_name FROM students WHERE student_id = ?
            ''', (student_id,))

            student_data = cursor.fetchone()
            if not student_data:
                conn.close()
                return None

            # 获取实验记录
            cursor.execute('''
                SELECT experiment_id, experiment_name, date, total_score, max_score, grade,
                       code_quality, principle_understanding, report_quality, team_collaboration,
                       plagiarism_detected, needs_review
                FROM experiments WHERE student_id = ?
                ORDER BY date ASC
            ''', (student_id,))

            records = []
            for row in cursor.fetchall():
                records.append(ExperimentRecord(
                    experiment_id=row[0],
                    experiment_name=row[1],
                    date=datetime.fromisoformat(row[2]),
                    total_score=row[3],
                    max_score=row[4],
                    grade=row[5],
                    code_quality=row[6],
                    principle_understanding=row[7],
                    report_quality=row[8],
                    team_collaboration=row[9],
                    plagiarism_detected=row[10],
                    needs_review=row[11]
                ))

            conn.close()

            # 创建档案并分析
            profile = StudentProfile(
                student_id=student_data[0],
                name=student_data[1],
                class_name=student_data[2],
                experiments=records
            )

            self._analyze_profile(profile)
            return profile

        except Exception as e:
            print(f"[进步追踪] 获取档案失败: {e}")
            return None

    def _analyze_profile(self, profile: StudentProfile):
        """分析学生档案"""
        if not profile.experiments:
            return

        # 基本统计
        profile.total_experiments = len(profile.experiments)
        scores = [e.total_score for e in profile.experiments]
        profile.average_score = mean(scores)
        profile.best_score = max(scores)
        profile.worst_score = min(scores)

        # 趋势分析
        if len(profile.experiments) >= 3:
            profile.score_trend = self._calculate_trend(scores)

        # 分类分析
        self._analyze_categories(profile)

        # 风险评估
        self._assess_risk(profile)

        # 生成建议
        self._generate_suggestions(profile)

    def _calculate_trend(self, scores: List[float]) -> Trend:
        """计算得分趋势"""
        if len(scores) < 3:
            return Trend.INSUFFICIENT_DATA

        # 计算最近3次的趋势
        recent = scores[-3:]
        if recent[-1] > recent[0] + 5:
            return Trend.IMPROVING
        elif recent[-1] < recent[0] - 5:
            return Trend.DECLINING
        else:
            return Trend.STABLE

    def _analyze_categories(self, profile: StudentProfile):
        """分析分类得分"""
        categories = {
            'code_quality': '代码质量',
            'principle_understanding': '实验原理',
            'report_quality': '报告质量',
            'team_collaboration': '团队协作'
        }

        avg_scores = {}
        for cat_key, cat_name in categories.items():
            scores = [getattr(e, cat_key, 0) for e in profile.experiments]
            if scores:
                avg_scores[cat_key] = mean(scores)

        # 识别薄弱环节（平均分低于70%）
        for cat_key, cat_name in categories.items():
            if cat_key in avg_scores and avg_scores[cat_key] < 70:
                profile.weak_areas.append(cat_name)
            elif cat_key in avg_scores and avg_scores[cat_key] >= 85:
                profile.strong_areas.append(cat_name)

    def _assess_risk(self, profile: StudentProfile):
        """评估风险学生"""
        profile.at_risk = False
        profile.risk_reasons = []

        # 条件1: 平均分低于60
        if profile.average_score < 60:
            profile.at_risk = True
            profile.risk_reasons.append(f"平均分低于60分 ({profile.average_score:.1f}分)")

        # 条件2: 最近两次持续下滑
        if len(profile.experiments) >= 2:
            recent = profile.experiments[-2:]
            if recent[-1].total_score < recent[0].total_score - 10:
                profile.at_risk = True
                profile.risk_reasons.append("最近两次实验成绩持续下滑")

        # 条件3: 有抄袭记录
        if any(e.plagiarism_detected for e in profile.experiments):
            profile.at_risk = True
            profile.risk_reasons.append("存在抄袭检测记录")

        # 条件4: 代码质量持续偏低
        code_scores = [e.code_quality for e in profile.experiments if e.code_quality > 0]
        if code_scores and mean(code_scores) < 60:
            profile.at_risk = True
            profile.risk_reasons.append("代码质量持续偏低")

    def _generate_suggestions(self, profile: StudentProfile):
        """生成学习建议"""
        profile.suggestions = []

        # 基于薄弱环节
        if '代码质量' in profile.weak_areas:
            profile.suggestions.append(
                "建议加强代码规范训练：增加注释、优化函数结构、学习HAL库使用"
            )
        if '实验原理' in profile.weak_areas:
            profile.suggestions.append(
                "建议深入理解实验原理：复习相关理论知识、理解硬件工作原理"
            )
        if '报告质量' in profile.weak_areas:
            profile.suggestions.append(
                "建议提高报告质量：详细记录实验过程、补充实验现象分析、认真回答思考题"
            )

        # 基于趋势
        if profile.score_trend == Trend.IMPROVING:
            profile.suggestions.append("👍 进步明显，继续保持！")
        elif profile.score_trend == Trend.DECLINING:
            profile.suggestions.append("⚠️ 成绩有所下滑，建议调整学习状态，及时复习")

        # 风险学生
        if profile.at_risk:
            profile.suggestions.append("🚨 建议与教师沟通，制定针对性的学习计划")

    def get_class_summary(self, class_name: str) -> Dict:
        """
        获取班级汇总

        Args:
            class_name: 班级名称

        Returns:
            班级汇总信息
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 获取所有学生
            cursor.execute('''
                SELECT student_id FROM students WHERE class_name = ?
            ''', (class_name,))

            students = [row[0] for row in cursor.fetchall()]

            # 分析每个学生
            profiles = []
            at_risk_count = 0
            improving_count = 0

            for student_id in students:
                profile = self.get_student_profile(student_id)
                if profile:
                    profiles.append(profile)
                    if profile.at_risk:
                        at_risk_count += 1
                    if profile.score_trend == Trend.IMPROVING:
                        improving_count += 1

            conn.close()

            return {
                'total_students': len(profiles),
                'at_risk_count': at_risk_count,
                'improving_count': improving_count,
                'average_score': mean([p.average_score for p in profiles]) if profiles else 0,
                'profiles': profiles
            }

        except Exception as e:
            print(f"[进步追踪] 获取班级汇总失败: {e}")
            return {}

    def export_student_report(self, student_id: str, output_path: Path = None) -> Path:
        """
        导出学生学习报告

        Args:
            student_id: 学号
            output_path: 输出路径

        Returns:
            报告文件路径
        """
        profile = self.get_student_profile(student_id)
        if not profile:
            return None

        if output_path is None:
            output_path = self.data_dir / 'reports' / f'{student_id}_学习报告.md'
            output_path.parent.mkdir(parents=True, exist_ok=True)

        # 生成Markdown报告
        lines = [
            f"# 学生学习报告",
            f"",
            f"## 基本信息",
            f"- **学号**: {profile.student_id}",
            f"- **姓名**: {profile.name}",
            f"- **班级**: {profile.class_name}",
            f"- **已完成实验**: {profile.total_experiments}次",
            f"",
            f"## 成绩概览",
            f"- **平均分**: {profile.average_score:.1f}分",
            f"- **最高分**: {profile.best_score:.1f}分",
            f"- **最低分**: {profile.worst_score:.1f}分",
            f"- **进步趋势**: {self._trend_to_emoji(profile.score_trend)} {self._trend_to_text(profile.score_trend)}",
            f"",
            f"## 实验记录",
            f""
        ]

        for exp in profile.experiments:
            lines.append(f"### {exp.experiment_name}")
            lines.append(f"- **日期**: {exp.date.strftime('%Y-%m-%d')}")
            lines.append(f"- **得分**: {exp.total_score:.1f}/{exp.max_score}")
            lines.append(f"- **等级**: {exp.grade}")

            if exp.code_quality > 0:
                lines.append(f"  - 代码质量: {exp.code_quality:.1f}分")
            if exp.principle_understanding > 0:
                lines.append(f"  - 实验原理: {exp.principle_understanding:.1f}分")
            if exp.report_quality > 0:
                lines.append(f"  - 报告质量: {exp.report_quality:.1f}分")
            if exp.team_collaboration > 0:
                lines.append(f"  - 团队协作: {exp.team_collaboration:.1f}分")

            if exp.plagiarism_detected:
                lines.append(f"  - ⚠️ 存在抄袭检测记录")

            lines.append("")

        if profile.weak_areas:
            lines.append(f"## 薄弱环节")
            for area in profile.weak_areas:
                lines.append(f"- **{area}**: 需要加强")
            lines.append("")

        if profile.strong_areas:
            lines.append(f"## 优势领域")
            for area in profile.strong_areas:
                lines.append(f"- **{area}**: 表现良好")
            lines.append("")

        if profile.suggestions:
            lines.append(f"## 学习建议")
            for i, suggestion in enumerate(profile.suggestions, 1):
                lines.append(f"{i}. {suggestion}")
            lines.append("")

        if profile.at_risk:
            lines.append(f"## ⚠️ 风险提示")
            for reason in profile.risk_reasons:
                lines.append(f"- {reason}")
            lines.append("")

        # 保存
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return output_path

    def _trend_to_emoji(self, trend: Trend) -> str:
        """趋势转emoji"""
        return {
            Trend.IMPROVING: "📈",
            Trend.STABLE: "➡️",
            Trend.DECLINING: "📉",
            Trend.INSUFFICIENT_DATA: "❓"
        }.get(trend, "")

    def _trend_to_text(self, trend: Trend) -> str:
        """趋势转文本"""
        return {
            Trend.IMPROVING: "持续进步",
            Trend.STABLE: "保持稳定",
            Trend.DECLINING: "有所下滑",
            Trend.INSUFFICIENT_DATA: "数据不足"
        }.get(trend, "")


# 便捷函数
def track_student_progress(
    student_id: str,
    name: str,
    class_name: str,
    experiment_id: str,
    experiment_name: str,
    grading_result: dict
) -> bool:
    """
    追踪学生进步（便捷函数）

    Args:
        student_id: 学号
        name: 姓名
        class_name: 班级
        experiment_id: 实验ID
        experiment_name: 实验名称
        grading_result: 评分结果

    Returns:
        是否成功
    """
    tracker = StudentProgressTracker()
    return tracker.add_experiment_record(
        student_id, name, class_name,
        experiment_id, experiment_name,
        grading_result
    )


def get_student_report(student_id: str) -> Optional[StudentProfile]:
    """
    获取学生档案（便捷函数）

    Args:
        student_id: 学号

    Returns:
        学生档案
    """
    tracker = StudentProgressTracker()
    return tracker.get_student_profile(student_id)
