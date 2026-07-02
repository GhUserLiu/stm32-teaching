#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动化批阅统一门面
Auto Grading Facade

提供统一的入口，协调所有模块：
1. 整理提交格式（SubmissionOrganizer）
2. 处理提交数据（SubmissionProcessor）
3. 执行编译检查（BuildChecker）
4. 运行评分引擎（AutoGradingEngine）
5. 生成最终报告

使用示例:
    facade = AutoGradingFacade()
    result = facade.run_full_pipeline("汽服2302B班", "07-car-gear")
"""

import json
import shutil

from tools.common import atomic_write_json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime

from .config import AutoGradingConfig
from .submission_organizer import SubmissionOrganizer, OrganizationResult
from .submission_processor import SubmissionProcessor, ProcessedSubmission
from .grading_engine import AutoGradingEngine, GradingResult
from .build_checker import BuildResult, BuildStatus


def serialize_details(details):
    """序列化details中的不可序列化对象"""
    if isinstance(details, list):
        return [serialize_details(item) for item in details]
    elif isinstance(details, dict):
        return {k: serialize_details(v) for k, v in details.items()}
    elif isinstance(details, BuildResult):
        return {
            'status': details.status.value if isinstance(details.status, BuildStatus) else str(details.status),
            'project_name': details.project_name,
            'success': details.success,
            'duration': details.duration,
            'error_count': details.error_count,
            'warning_count': details.warning_count,
            'error_message': details.error_message,
            'output': details.output
        }
    else:
        return details


@dataclass
class PipelineResult:
    """批阅流水线结果"""
    class_name: str                  # 班级
    experiment_id: str                # 实验

    # 各阶段结果
    organization_result: Optional[OrganizationResult] = None
    grading_results: List[GradingResult] = field(default_factory=list)

    # 统计
    total_submissions: int = 0
    successful_graded: int = 0

    # 部分失败清单：per-student 评分异常被收集（不再静默丢弃），供 GUI 展示「⚠ N 人批阅失败」。
    # 每条 = {student_id, name, class_name, experiment_id, error, stage}
    failures: List[Dict] = field(default_factory=list)

    # 时间戳
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class AutoGradingFacade:
    """自动化批阅统一门面"""

    def __init__(self, config: Optional[AutoGradingConfig] = None):
        """
        初始化门面

        Args:
            config: 配置对象
        """
        self.config = config or AutoGradingConfig()

        # 初始化子模块
        # 输入侧也统一到学期树下：data/teaching/<学期>/<班级>/<实验>/
        # 与 get_output_dir（results/grading）落在同一棵实验树，
        # 避免在 data/<班级>/ 下滋生游离目录（多学期/多项目可并存）
        input_base = self.config.teaching_dir / self.config.semester
        self.organizer = SubmissionOrganizer(input_base)
        self.processor = SubmissionProcessor(input_base)

        # 接通 rubric（单一事实来源）；facade 强制加载，避免引擎退化为简单评分。
        # 此处用通用 rubric.json 作默认引擎（兼容 run_full_pipeline 前访问 facade.engine 的场景）；
        # 真正评分时 run_full_pipeline 会按 experiment_id 重新装载对应 rubric。
        rubric_path = self.config.rubrics_dir / "rubric.json"
        self.engine = AutoGradingEngine(
            self.config,
            rubric_path=rubric_path if rubric_path.exists() else None
        )

    def _make_engine(self, experiment_id: str) -> AutoGradingEngine:
        """按实验 id 定位 rubric 并构造引擎（单一事实来源：AutoGradingConfig.get_rubric_path）。

        - final-project → data/rubrics/final-project.json
        - 07-car-gear    → data/rubrics/07-car-gear.json 不存在 → 回退 rubric.json（行为不变）
        避免 facade 永远只装 rubric.json、让综合项目被汽车档位标准误评。

        注意：每次调用都新建 AutoGradingEngine，会重置其编译结果缓存（_build_cache），
        故应在流水线起始处调用一次、整条流水线复用同一引擎，切勿中途换引擎。
        """
        rubric_path = self.config.get_rubric_path(experiment_id)
        return AutoGradingEngine(
            self.config,
            rubric_path=rubric_path if rubric_path.exists() else None,
        )

    def run_full_pipeline(
        self,
        class_zip: Path,
        class_name: str,
        experiment_id: str,
        skip_organization: bool = False
    ) -> PipelineResult:
        """
        运行完整的批阅流水线

        Args:
            class_zip: 班级压缩包路径
            class_name: 班级名称
            experiment_id: 实验ID
            skip_organization: 跳过整理阶段（如果已经整理过）

        Returns:
            流水线结果
        """
        result = PipelineResult(
            class_name=class_name,
            experiment_id=experiment_id
        )

        print("=" * 70)
        print("自动化批阅系统")
        print("=" * 70)
        print(f"班级: {class_name}")
        print(f"实验: {experiment_id}")
        print(f"开始时间: {result.started_at.strftime('%Y-%m-%d %H:%M:%S')}")

        # 按实验 id 装载对应 rubric（不同实验不同 rubric，如 final-project.json）
        self.engine = self._make_engine(experiment_id)
        print(f"rubric: {getattr(self.engine.rubric, 'get', lambda *a: None)('experiment_name', None) or self.engine.rubric_path or '(默认)'}")
        print()

        # 阶段1: 整理提交格式
        if not skip_organization:
            print("阶段1: 整理提交格式")
            print("-" * 70)

            org_result = self.organizer.process_class_submission(
                class_zip,
                class_name,
                experiment_id
            )

            result.organization_result = org_result
            print(f"  成功: {org_result.successful}/{org_result.total_students}")
            print()

            if org_result.total_students == 0:
                print("警告: 没有找到学生提交，终止处理")
                return result
        else:
            print("阶段1: 跳过（已整理）")
            print()

        # 阶段2: 处理提交数据
        print("阶段2: 处理提交数据")
        print("-" * 70)

        submissions = self.processor.process_class_submissions(
            class_name,
            experiment_id,
            expand_team=True,   # 批阅按团队成员展开为每人一条；查重链路保持默认 False
        )

        result.total_submissions = len(submissions)
        print(f"  处理完成: {len(submissions)} 个提交")
        print()

        if not submissions:
            print("警告: 没有找到提交数据，终止处理")
            return result

        # 阶段3: 批量评分
        print("阶段3: 批量评分")
        print("-" * 70)

        grading_results = self.engine.batch_grade(submissions)
        result.grading_results = grading_results
        result.successful_graded = len(grading_results)

        print()

        # 阶段4: 生成报告
        print("阶段4: 生成报告")
        print("-" * 70)

        result.completed_at = datetime.now()

        class_report = self.engine.generate_class_report(grading_results)
        self._save_reports(result, class_report)

        print(f"  班级报告已生成")
        print(f"  个人报告已生成")

        print()
        print("=" * 70)
        print("批阅完成！")
        print("=" * 70)
        print(f"平均分: {class_report['average_score']:.1f}")
        print(f"等级分布: {class_report['grade_distribution']}")
        print(f"完成时间: {result.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"耗时: {(result.completed_at - result.started_at).total_seconds():.1f}秒")

        return result

    def run_single_submission(
        self,
        report_path: Path,
        source_path: Optional[Path] = None,
        experiment_id: Optional[str] = None
    ) -> Optional[GradingResult]:
        """
        评分单个提交

        Args:
            report_path: 报告文件路径
            source_path: 源代码目录路径（可选）
            experiment_id: 实验 ID（可选）；提供时按其装载对应 rubric，
                与 run_full_pipeline 一致，避免误用默认 rubric.json

        Returns:
            评分结果
        """
        print(f"评分单个提交: {report_path.name}")

        # 按实验 id 装载对应 rubric（与 run_full_pipeline 一致）
        if experiment_id:
            self.engine = self._make_engine(experiment_id)

        # 处理提交
        submission = self.processor.process_single_submission(
            report_path,
            source_path
        )

        if not submission:
            print("错误: 无法处理提交")
            return None

        # 评分
        result = self.engine.grade_submission(submission)

        print(f"  得分: {result.total_score:.1f}/{result.max_score:.1f} ({result.grade})")

        return result

    def _save_reports(self, pipeline_result: PipelineResult, class_report: Dict):
        """
        保存报告

        Args:
            pipeline_result: 流水线结果
            class_report: 班级报告
        """
        output_dir = self.config.get_output_dir(
            pipeline_result.class_name,
            pipeline_result.experiment_id
        )

        output_dir.mkdir(parents=True, exist_ok=True)

        # 保存班级报告
        report_path = output_dir / "班级报告.json"
        atomic_write_json(report_path, class_report, ensure_ascii=False, indent=2)

        # 保存个人报告
        individuals_dir = output_dir / "个人报告"
        # 每次批阅前清空个人报告目录：下游 class_analysis.load_class_reports 会 glob 整目录
        # 读取，若不清空，上次运行里"本次已不在班级/已改组"的学生评分文件会残留，污染
        # 班级统计/排名/反馈（"第二次小范围查询却显示全班"的根因）。
        shutil.rmtree(individuals_dir, ignore_errors=True)
        individuals_dir.mkdir(parents=True, exist_ok=True)

        for grading_result in pipeline_result.grading_results:
            filename = f"{grading_result.student_id}-{grading_result.name}-评分.json"
            individual_path = individuals_dir / filename

            # 准备个人报告数据
            individual_report = {
                'student_id': grading_result.student_id,
                'name': grading_result.name,
                'class_name': grading_result.class_name,
                'total_score': grading_result.total_score,
                'max_score': grading_result.max_score,
                'bonus_total': grading_result.bonus_total,
                'grade': grading_result.grade,
                'group_key': grading_result.group_key,
                'group_members': grading_result.group_members,
                'group_submitter_count': grading_result.group_submitter_count,
                'group_reporter_count': grading_result.group_reporter_count,
                'is_team_leader': grading_result.is_team_leader,
                'detected_task': grading_result.detected_task,
                'detected_task_name': grading_result.detected_task_name,
                'detected_task_source': grading_result.detected_task_source,
                'detected_task_ambiguous': grading_result.detected_task_ambiguous,
                'evaluation_score': grading_result.evaluation_score,
                'difficulty_ratio': grading_result.difficulty_ratio,
                'task_full_marks': grading_result.task_full_marks,
                'category_scores': [
                    {
                        'category_id': cs.category_id,
                        'category_name': cs.category_name,
                        'max_points': cs.max_points,
                        'earned_points': cs.earned_points,
                        'details': serialize_details(cs.details)
                    }
                    for cs in grading_result.category_scores
                ],
                'strengths': grading_result.strengths,
                'weaknesses': grading_result.weaknesses,
                'suggestions': grading_result.suggestions,
                'issues': grading_result.issues,
                'thinking_check': grading_result.thinking_check,
                'validation_report': (
                    grading_result.validation_report.to_dict()
                    if grading_result.validation_report else None
                ),
                'graded_at': grading_result.graded_at.isoformat()
            }

            atomic_write_json(individual_path, individual_report, ensure_ascii=False, indent=2)

        # 保存汇总报告（JSON格式，供GUI使用）
        summary_json_path = output_dir / "批阅汇总.json"
        summary_data = {
            'class_name': pipeline_result.class_name,
            'experiment_id': pipeline_result.experiment_id,
            'completed_at': pipeline_result.completed_at.isoformat() if pipeline_result.completed_at else None,
            'statistics': {
                'total_submissions': pipeline_result.total_submissions,
                'successful_graded': pipeline_result.successful_graded,
                'average_score': class_report.get('average_score', 0),
                'max_score': class_report.get('max_score', 100),
                'grade_distribution': class_report.get('grade_distribution', {})
            },
            'grading_results': [
                {
                    'student_id': gr.student_id,
                    'name': gr.name,
                    'total_score': gr.total_score,
                    'grade': gr.grade
                }
                for gr in pipeline_result.grading_results
            ]
        }

        atomic_write_json(summary_json_path, summary_data, ensure_ascii=False, indent=2)

        # 保存汇总报告（文本格式）
        summary_path = output_dir / "批阅汇总.txt"
        self._save_summary_report(pipeline_result, class_report, summary_path)

    def _save_summary_report(
        self,
        pipeline_result: PipelineResult,
        class_report: Dict,
        output_path: Path
    ):
        """保存汇总报告（文本格式）"""
        lines = [
            "=" * 70,
            "自动化批阅汇总报告",
            "=" * 70,
            f"班级: {pipeline_result.class_name}",
            f"实验: {pipeline_result.experiment_id}",
            f"批阅时间: {pipeline_result.completed_at.strftime('%Y-%m-%d %H:%M:%S') if pipeline_result.completed_at else '进行中'}",
            "",
            "统计信息",
            "-" * 70,
            f"总提交数: {pipeline_result.total_submissions}",
            f"成功批阅: {pipeline_result.successful_graded}",
            f"平均分: {class_report['average_score']:.1f}",
            f"满分: {class_report['max_score']:.1f}",
            "",
            "等级分布",
            "-" * 70,
        ]

        for grade, count in sorted(class_report['grade_distribution'].items()):
            lines.append(f"  {grade}: {count}人")

        lines.extend([
            "",
            "各类别平均分",
            "-" * 70,
        ])

        for cat_id, stats in class_report['category_stats'].items():
            lines.append(f"  {stats['name']}: {stats['average']:.1f}/{stats['max_average']:.1f}")

        lines.extend([
            "",
            "个人得分",
            "-" * 70,
        ])

        # 按得分排序
        sorted_results = sorted(
            class_report['individual_results'],
            key=lambda x: x['score'],
            reverse=True
        )

        for item in sorted_results:
            lines.append(f"  {item['student_id']}-{item['name']}: {item['score']:.1f} ({item['grade']})")

        lines.append("=" * 70)

        output_path.write_text("\n".join(lines), encoding='utf-8')


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description='自动化批阅系统')
    parser.add_argument('class_zip', type=Path, help='班级压缩包路径')
    parser.add_argument('class_name', type=str, help='班级名称')
    parser.add_argument('experiment_id', type=str, help='实验ID')
    parser.add_argument('--skip-organization', action='store_true', help='跳过整理阶段')
    parser.add_argument('--base-dir', type=Path, default='data/teaching/2026-春季/', help='基础目录')

    args = parser.parse_args()

    # 创建门面
    facade = AutoGradingFacade()

    # 运行流水线
    result = facade.run_full_pipeline(
        args.class_zip,
        args.class_name,
        args.experiment_id,
        skip_organization=args.skip_organization
    )

    print()
    print(f"报告已保存到: {facade.config.get_output_dir(args.class_name, args.experiment_id)}")


if __name__ == '__main__':
    main()
