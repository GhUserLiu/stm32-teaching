#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强质量评估系统 - 统一入口
Enhanced Quality Assessment System - Unified Entry Point

整合所有质量评估功能，提供一站式评分体验

v2.5.0 - 新增代码深度分析、智能反馈建议、图像质量检测、评分一致性校验
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# 导入核心模块（指向真实子模块路径；历史代码误从顶层 tools.plagiarism 导入，
# 而该包未绑定这些名称，导致整个脚本导入即崩）
from tools.plagiarism.grading.grading import (
    batch_grade,
    load_rubric_for_experiment,
    GradingResult,
)
from tools.plagiarism.quality.technical_checks import (
    TechnicalChecker,
    ExperimentType,
)
from tools.plagiarism.feedback.feedback import save_student_feedback
from tools.plagiarism.code_analysis.code_analyzer import (
    analyze_code_from_report,
    CodeAnalysisResult,
)
from tools.plagiarism.feedback.smart_feedback import generate_smart_feedback_report
from tools.plagiarism.image.image_quality_checker import (
    ImageQualityChecker,
    ImageRelevanceChecker,
)
from tools.plagiarism.grading.grading_validator import validate_grading_results


class EnhancedQualityAssessmentSystem:
    """增强质量评估系统"""

    def __init__(
        self,
        experiment_dir: Path,
        experiment_type: str = "档位实验",
        class_name: str = "未知班级",
        enable_code_analysis: bool = True,
        enable_smart_feedback: bool = True,
        enable_image_check: bool = True,
        enable_validation: bool = True
    ):
        """
        初始化系统

        Args:
            experiment_dir: 实验目录
            experiment_type: 实验类型
            class_name: 班级名称
            enable_code_analysis: 是否启用代码深度分析
            enable_smart_feedback: 是否启用智能反馈建议
            enable_image_check: 是否启用图像质量检测
            enable_validation: 是否启用评分一致性校验
        """
        self.experiment_dir = experiment_dir
        self.experiment_type = experiment_type
        self.class_name = class_name

        # 功能开关
        self.enable_code_analysis = enable_code_analysis
        self.enable_smart_feedback = enable_smart_feedback
        self.enable_image_check = enable_image_check
        self.enable_validation = enable_validation

        # 目录设置
        self.submissions_dir = experiment_dir / 'submissions' / 'extracted'
        self.output_dir = experiment_dir / 'results'
        self.output_dir.mkdir(exist_ok=True)

        # 数据
        self.submissions: Dict[str, Dict] = {}
        self.grading_results: List[GradingResult] = []
        self.technical_results: Dict = {}
        self.code_analysis_results: Dict[str, CodeAnalysisResult] = {}
        self.image_analysis_results: Dict = {}

    def load_submissions(self) -> bool:
        """加载学生提交"""
        print("\n" + "=" * 60)
        print("加载学生提交")
        print("=" * 60)

        from tools.submission_utils import (
            get_student_info,
            extract_team_leader_info,
            extract_personal_experience
        )

        student_info = get_student_info(self.submissions_dir)
        print(f"提取到 {len(student_info)} 个学生信息")

        leader_count = 0
        experience_stats = {'missing': 0, 'poor': 0, 'fair': 0, 'good': 0}

        for student_id, info in student_info.items():
            content = info.get('content')
            if content:
                # 提取组长信息
                is_leader = extract_team_leader_info(content, student_id)
                if is_leader:
                    leader_count += 1

                # 提取心得体会
                experience = extract_personal_experience(content)
                quality = experience.get('quality', 'missing')
                experience_stats[quality] = experience_stats.get(quality, 0) + 1

                self.submissions[student_id] = {
                    'name': info.get('name', ''),
                    'text': content,
                    'raw_content': content,
                    'is_leader': is_leader,
                    'experience': experience
                }

        print(f"成功加载 {len(self.submissions)} 份有效报告")
        print(f"  - 组长: {leader_count} 人")
        print(f"  - 心得体会质量分布:")
        for quality, count in experience_stats.items():
            if count > 0:
                print(f"      {quality}: {count} 人")

        return len(self.submissions) > 0

    def run_grading(self):
        """执行评分"""
        print("\n" + "=" * 60)
        print("执行Rubric评分")
        print("=" * 60)

        rubric = load_rubric_for_experiment(self.experiment_type)
        self.grading_results = batch_grade(
            self.submissions,
            rubric,
            self.experiment_type
        )

        # 统计
        grades = {}
        for r in self.grading_results:
            grades[r.grade] = grades.get(r.grade, 0) + 1

        print(f"\n评分人数: {len(self.grading_results)}")
        print(f"等级分布:")
        for grade in ['A', 'B', 'C', 'D', 'F']:
            count = grades.get(grade, 0)
            if count > 0:
                print(f"  {grade}: {count} 人")

        avg_score = sum(r.total_score for r in self.grading_results) / len(self.grading_results) if self.grading_results else 0
        print(f"平均分: {avg_score:.1f}")

    def run_technical_checks(self):
        """执行技术要点检查"""
        print("\n" + "=" * 60)
        print("执行技术要点检查")
        print("=" * 60)

        exp_type = ExperimentType.CAR_GEAR if '档位' in self.experiment_type else ExperimentType.TURN_SIGNAL

        for student_id, submission in self.submissions.items():
            text = submission.get('text', '')
            if text:
                result = TechnicalChecker.check_all(text, exp_type)
                self.technical_results[student_id] = result

        print(f"技术检查完成")

    def run_code_analysis(self):
        """执行代码深度分析"""
        if not self.enable_code_analysis:
            return

        print("\n" + "=" * 60)
        print("执行代码深度分析 (v2.5.0 新增)")
        print("=" * 60)

        for student_id, submission in self.submissions.items():
            text = submission.get('text', '')
            if text:
                try:
                    result = analyze_code_from_report(text, self.experiment_type)
                    self.code_analysis_results[student_id] = result
                except Exception as e:
                    print(f"  警告: {student_id} 代码分析失败: {e}")

        print(f"代码分析完成")

        # 统计
        if self.code_analysis_results:
            avg_score = sum(r.total_score for r in self.code_analysis_results.values()) / len(self.code_analysis_results)
            print(f"平均代码质量分: {avg_score:.1f}")

            # 统计问题
            from tools.plagiarism.code_analyzer import Severity
            total_issues = 0
            critical_issues = 0
            for result in self.code_analysis_results.values():
                for issue in result.issues:
                    total_issues += 1
                    if issue.severity == Severity.CRITICAL:
                        critical_issues += 1

            print(f"检测到代码问题: {total_issues}个 (严重: {critical_issues}个)")

    def run_smart_feedback_generation(self):
        """生成智能反馈建议"""
        if not self.enable_smart_feedback:
            return

        print("\n" + "=" * 60)
        print("生成智能反馈建议 (v2.5.0 新增)")
        print("=" * 60)

        feedback_dir = self.output_dir / 'smart_feedback'
        feedback_dir.mkdir(exist_ok=True)

        generated_count = 0

        for grading_result in self.grading_results:
            student_id = grading_result.student_id

            # 获取相关数据
            technical_result = self.technical_results.get(student_id)
            code_result = self.code_analysis_results.get(student_id)

            # 生成智能反馈
            try:
                feedback_content = generate_smart_feedback_report(
                    student_id,
                    grading_result.name,
                    grading_result,
                    technical_result,
                    code_result
                )

                # 保存
                feedback_path = feedback_dir / f"{student_id}_{grading_result.name}_智能反馈.md"
                with open(feedback_path, 'w', encoding='utf-8') as f:
                    f.write(feedback_content)

                generated_count += 1
            except Exception as e:
                print(f"  警告: {student_id} 智能反馈生成失败: {e}")

        print(f"智能反馈生成完成: {generated_count} 个")

    def run_validation(self):
        """执行评分一致性校验"""
        if not self.enable_validation:
            return

        print("\n" + "=" * 60)
        print("执行评分一致性校验 (v2.5.0 新增)")
        print("=" * 60)

        # 准备数据
        results_data = []
        for r in self.grading_results:
            results_data.append({
                'student_id': r.student_id,
                'name': r.name,
                'total_score': r.total_score,
                'percentage': r.percentage,
                'grade': r.grade,
                'category_scores': {
                    cat_id: {
                        'name': score.name,
                        'points_earned': score.points_earned,
                        'points_possible': score.points_possible
                    }
                    for cat_id, score in r.category_scores.items()
                },
                'strengths': r.strengths,
                'weaknesses': r.weaknesses,
                'plagiarism_risk': 0  # 如果有抄袭数据可以添加
            })

        rubric = load_rubric_for_experiment(self.experiment_type)

        # 执行校验
        validation_report = validate_grading_results(
            results_data,
            rubric,
            self.output_dir
        )

        # 输出结果
        stats = validation_report.statistics
        print(f"\n校验结果:")
        print(f"  状态: {'[OK] 通过' if validation_report.validation_passed else '[FAIL] 未通过'}")
        print(f"  平均分: {stats['average_score']:.1f}")
        print(f"  问题数: {stats['total_issues']} (严重: {stats['critical_issues']}, 错误: {stats['error_issues']})")

        if validation_report.recommendations:
            print(f"\n建议:")
            for rec in validation_report.recommendations[:3]:
                print(f"  - {rec}")

    def save_grading_results(self):
        """保存详细评分结果到JSON"""
        print("\n保存详细评分结果...")

        output = []
        for grading_result in self.grading_results:
            student_id = grading_result.student_id

            # 获取技术检查结果
            tech_result = self.technical_results.get(student_id, (0, [], [], []))

            result_dict = {
                'student_id': student_id,
                'name': grading_result.name,
                'total_score': grading_result.total_score,
                'total_possible': grading_result.total_possible,
                'percentage': grading_result.percentage,
                'grade': grading_result.grade,
                'category_scores': {
                    cat_id: {
                        'name': score.name,
                        'earned': score.points_earned,
                        'possible': score.points_possible,
                        'percentage': score.percentage,
                        'feedback': score.feedback
                    }
                    for cat_id, score in grading_result.category_scores.items()
                },
                'technical_check': {
                    'score': tech_result[0],
                    'strengths': tech_result[2],
                    'weaknesses': tech_result[3]
                },
                'strengths': grading_result.strengths,
                'weaknesses': grading_result.weaknesses,
                'recommendations': grading_result.recommendations,
                'auto_confidence': grading_result.auto_confidence
            }

            # 添加代码分析结果
            if student_id in self.code_analysis_results:
                code_result = self.code_analysis_results[student_id]
                result_dict['code_analysis'] = {
                    'total_score': code_result.total_score,
                    'issues_count': len(code_result.issues)
                }

            output.append(result_dict)

        output_path = self.output_dir / 'grading_results.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"详细评分结果: {output_path}")
        return output_path

    def run_full_analysis(self):
        """运行完整分析流程"""
        print("\n" + "=" * 60)
        print(f"增强质量评估系统 v2.5.0")
        print(f"实验类型: {self.experiment_type}")
        print(f"班级: {self.class_name}")
        print(f"功能配置:")
        print(f"  - 代码深度分析: {'[Y]' if self.enable_code_analysis else '[N]'}")
        print(f"  - 智能反馈建议: {'[Y]' if self.enable_smart_feedback else '[N]'}")
        print(f"  - 图像质量检测: {'[Y]' if self.enable_image_check else '[N]'}")
        print(f"  - 评分一致性校验: {'[Y]' if self.enable_validation else '[N]'}")
        print("=" * 60)

        start_time = datetime.now()

        # 1. 加载提交
        if not self.load_submissions():
            print("错误: 无法加载提交内容")
            return False

        # 2. Rubric评分
        self.run_grading()

        # 3. 技术检查
        self.run_technical_checks()

        # 4. 代码深度分析
        self.run_code_analysis()

        # 5. 生成智能反馈
        self.run_smart_feedback_generation()

        # 6. 保存评分结果
        self.save_grading_results()

        # 7. 评分一致性校验
        self.run_validation()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print("\n" + "=" * 60)
        print(f"[OK] 分析完成! 耗时: {duration:.1f} 秒")
        print(f"[DIR] 结果目录: {self.output_dir}")
        print(f"   - grading_validation_report.md/json (评分校验报告)")
        print(f"   - smart_feedback/ (智能反馈建议)")
        print("=" * 60)

        return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='增强质量评估系统 v2.5.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 完整分析（所有功能）
  python tools/enhanced_quality_assessment.py

  # 指定实验目录
  python tools/enhanced_quality_assessment.py --experiment-dir "docs/teaching/2026-春季/汽服2302B班/07-car-gear"

  # 仅评分和反馈（跳过代码分析）
  python tools/enhanced_quality_assessment.py --no-code-analysis

  # 仅评分校验
  python tools/enhanced_quality_assessment.py --validation-only
        """
    )

    parser.add_argument(
        '--experiment-dir',
        type=Path,
        default=Path('docs/teaching/2026-春季/汽服2302B班/07-car-gear'),
        help='实验目录路径'
    )

    parser.add_argument(
        '--experiment-type',
        type=str,
        default='档位实验',
        choices=['档位实验', '转向灯实验'],
        help='实验类型'
    )

    parser.add_argument(
        '--class-name',
        type=str,
        default='汽服2302B班',
        help='班级名称'
    )

    parser.add_argument(
        '--no-code-analysis',
        action='store_true',
        help='禁用代码深度分析'
    )

    parser.add_argument(
        '--no-smart-feedback',
        action='store_true',
        help='禁用智能反馈建议'
    )

    parser.add_argument(
        '--no-validation',
        action='store_true',
        help='禁用评分一致性校验'
    )

    parser.add_argument(
        '--validation-only',
        action='store_true',
        help='仅执行评分一致性校验'
    )

    args = parser.parse_args()

    # 创建系统
    system = EnhancedQualityAssessmentSystem(
        experiment_dir=args.experiment_dir,
        experiment_type=args.experiment_type,
        class_name=args.class_name,
        enable_code_analysis=not args.no_code_analysis and not args.validation_only,
        enable_smart_feedback=not args.no_smart_feedback and not args.validation_only,
        enable_image_check=True,
        enable_validation=True
    )

    # 执行分析
    if args.validation_only:
        # 仅校验
        system.load_submissions()
        system.run_grading()
        system.run_validation()
    else:
        # 完整流程
        system.run_full_analysis()

    return 0


if __name__ == '__main__':
    sys.exit(main())
