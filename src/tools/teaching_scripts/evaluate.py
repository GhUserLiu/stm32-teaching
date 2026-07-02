# -*- coding: utf-8 -*-
"""
基于新评分标准的评估引擎
所有评分都基于实验报告内容
支持增强反馈生成和精准评分
支持语义相似度评分
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# 导入统一路径配置
from tools.common import ExperimentPaths, atomic_write_json

BASE_DIR = Path(__file__).parent.parent.parent.parent.parent  # Go up to project root
DEFAULT_EXPERIMENT_DIR = BASE_DIR / "data" / "teaching" / "2026-春季" / "汽服2302B班" / "07-car-gear"
DATA_DIR = Path(__file__).parent.parent / "rubrics"

# 全局路径配置
paths: ExperimentPaths = None

ENABLE_ENHANCED_FEEDBACK = False
ENABLE_ENHANCED_GRADING = False
ENABLE_SEMANTIC_SCORING = False


def calculate_grade(score, grading_scale):
    """Convert numeric score to letter grade"""
    for grade, range_data in grading_scale.items():
        if range_data['min'] <= score <= range_data['max']:
            return grade, range_data['label']
    return 'F', '不及格'


def evaluate_by_criteria(text, category):
    """Evaluate a category based on its criteria"""
    score = 0
    feedback = []

    for criterion in category['criteria']:
        points = criterion['points']
        keywords = criterion.get('keywords', [])

        if keywords:
            found = sum(1 for kw in keywords if kw in text)
            coverage = found / len(keywords)

            if coverage >= 0.6:
                earned_points = points
            elif found >= 1:
                earned_points = int(points * 0.7)
            else:
                earned_points = 0

            score += earned_points

            if earned_points >= points:
                feedback.append(criterion['description'])
            elif earned_points >= points * 0.6:
                feedback.append(f"{criterion['description']}(-{points - earned_points}分)")
            elif earned_points > 0:
                feedback.append(f"{criterion['description']}(-{points - earned_points}分)")
            else:
                feedback.append(f"{criterion['description']}(-{points}分)")
        else:
            score += points
            note = criterion.get('note', '')
            if note:
                feedback.append(f"{criterion['description']}({note})")
            else:
                feedback.append(criterion['description'])

    return min(score, category['points']), feedback


def evaluate_report(extracted_content, rubric, quality_info=None, semantic_engine=None):
    """
    评估单个学生的实验报告

    整合基础评分（关键词匹配）和质量调整（平衡策略）
    支持语义相似度评分
    """
    text = extracted_content.get('full_text', '')

    evaluation = {
        'student_id': extracted_content['student_id'],
        'name': extracted_content.get('name', ''),
        'scores': {},
        'feedback': {},
        'total_score': 0,
        'grade': None,
        'grade_label': None,
        'quality_info': quality_info or {},
        'scoring_method': {}
    }

    if extracted_content.get('missing'):
        evaluation['total_score'] = 0
        evaluation['grade'] = 'F'
        evaluation['grade_label'] = '不及格'
        evaluation['scores'] = {
            'team_collaboration': 0,
            'attitude': 0,
            'principle_understanding': 0,
            'completion': 0,
            'code_quality': 0,
            'report_quality': 0
        }
        evaluation['feedback'] = {'overall': ['未提交实验报告']}
        return evaluation

    # 1. 基础评分（关键词匹配 + 语义评分）
    for category in rubric['categories']:
        cat_id = category['id']

        if category.get('manual_evaluation'):
            evaluation['scores'][cat_id] = category['criteria'][0]['points']
            note = category['criteria'][0].get('note', '需教师手工评定')
            evaluation['feedback'][cat_id] = [
                f"{category['criteria'][0]['description']}: {note}"
            ]
            evaluation['scoring_method'][cat_id] = 'manual'
        else:
            # 基础关键词评分
            keyword_score, keyword_feedback = evaluate_by_criteria(text, category)

            # 语义评分（如果启用）
            semantic_score = 0
            semantic_feedback = []
            if semantic_engine and ENABLE_SEMANTIC_SCORING:
                try:
                    semantic_score, semantic_matches = semantic_engine.score_by_semantics(text, category)
                    if semantic_matches:
                        semantic_feedback = [
                            f"语义匹配: {m.matched_text[:30]}... (相似度{m.similarity:.0f}%)"
                            for m in semantic_matches[:3]  # 限制数量
                        ]
                except Exception as e:
                    print(f"Warning: Semantic scoring failed for {cat_id}: {e}")

            # 融合评分
            if semantic_score > 0 and ENABLE_SEMANTIC_SCORING:
                # 加权融合
                final_score = _aggregate_scores(keyword_score, semantic_score, category['points'])
                combined_feedback = keyword_feedback + semantic_feedback
                evaluation['scoring_method'][cat_id] = 'hybrid'
            else:
                final_score = keyword_score
                combined_feedback = keyword_feedback
                evaluation['scoring_method'][cat_id] = 'keyword'

            evaluation['scores'][cat_id] = final_score
            evaluation['feedback'][cat_id] = combined_feedback

        evaluation['total_score'] += evaluation['scores'][cat_id]

    # 2. 质量调整（基于类别质量，平衡策略）
    if quality_info:
        category_qualities = quality_info.get('category_qualities', {})
        quality_adjustments = []

        for cat_id, quality in category_qualities.items():
            if cat_id not in evaluation['scores']:
                continue

            base_score = evaluation['scores'][cat_id]
            quality_score = quality.get('quality_score', 70)
            max_points = quality.get('max_points', 10)

            # 平衡策略：线性调整
            if quality_score < 60:
                reduction_ratio = (60 - quality_score) / 10 * 0.05
                reduction = int(max_points * reduction_ratio)
                evaluation['scores'][cat_id] = max(0, base_score - reduction)
                quality_adjustments.append(f"{cat_id}: 质量{quality_score:.0f}分，扣{reduction}分")
            elif quality_score > 70:
                bonus_ratio = (quality_score - 70) / 10 * 0.03
                bonus = int(max_points * bonus_ratio)
                if base_score < max_points:
                    evaluation['scores'][cat_id] = min(max_points, base_score + bonus)
                    quality_adjustments.append(f"{cat_id}: 质量{quality_score:.0f}分，加{bonus}分")

        evaluation['total_score'] = sum(evaluation['scores'].values())

        if quality_adjustments:
            evaluation['feedback']['quality_adjustment'] = quality_adjustments
            evaluation['quality_adjustment_details'] = quality_adjustments

    # 3. 保存类别质量信息
    if quality_info and 'category_qualities' in quality_info:
        evaluation['category_quality'] = quality_info['category_qualities']
        evaluation['overall_quality'] = quality_info.get('overall_quality', 0)

    grading_scale = rubric['grading_scale']
    grade, label = calculate_grade(evaluation['total_score'], grading_scale)
    evaluation['grade'] = grade
    evaluation['grade_label'] = label

    return evaluation


def _aggregate_scores(keyword_score: float, semantic_score: float, max_points: float) -> float:
    """
    融合关键词评分和语义评分

    Args:
        keyword_score: 关键词评分
        semantic_score: 语义评分
        max_points: 满分

    Returns:
        融合后的评分
    """
    # 使用加权融合，关键词作为基础，语义作为增强
    keyword_weight = 0.6
    semantic_weight = 0.4

    # 如果两个评分差异过大，使用较低的（保守策略）
    diff_ratio = abs(keyword_score - semantic_score) / max(max_points, 1)

    if diff_ratio > 0.3:
        # 差异大，使用保守策略
        return min(keyword_score, semantic_score)
    else:
        # 差异小，加权融合
        aggregated = keyword_score * keyword_weight + semantic_score * semantic_weight
        return round(aggregated, 1)


def apply_enhanced_grading(extracted_data, evaluations, paths: ExperimentPaths, rubric_path):
    """应用增强精准评分（使用统一路径配置）"""
    try:
        tools_path = BASE_DIR / "tools" / "plagiarism"
        if str(tools_path) not in sys.path:
            sys.path.insert(0, str(tools_path))

        from enhanced_grading import EnhancedGradingEngine

        submissions = {}
        for content in extracted_data:
            submissions[content['student_id']] = {
                'name': content.get('name', ''),
                'text': content.get('full_text', '')
            }

        engine = EnhancedGradingEngine(rubric_path=rubric_path)

        enhanced_results = []
        for eval_data in evaluations:
            student_id = eval_data['student_id']
            submission = submissions.get(student_id)

            if not submission or not submission['text']:
                continue

            enhanced = engine.grade(
                student_id=student_id,
                name=submission['name'],
                text=submission['text'],
                original_score=eval_data['total_score'],
                original_category_scores=eval_data.get('scores', {})
            )

            enhanced_results.append(enhanced)

            eval_data['original_total_score'] = eval_data['total_score']
            eval_data['total_score'] = enhanced.adjusted_score
            eval_data['grade'] = enhanced.grade

            if enhanced.category_scores:
                eval_data['scores'] = enhanced.category_scores

            eval_data['grading_adjustments'] = [
                {
                    'issue_title': adj.issue_title,
                    'category': adj.category,
                    'deduction': adj.deduction,
                    'reason': adj.reason
                }
                for adj in enhanced.adjustments
            ]

            eval_data['grading_confidence'] = enhanced.confidence

            print(f"  {student_id}: {eval_data['original_total_score']:.1f} -> {enhanced.adjusted_score:.1f} (-{enhanced.total_deduction:.1f})")

        enhanced_output_path = paths.processed_dir / "enhanced_grading_details.json"
        atomic_write_json(
            enhanced_output_path,
            [
                {
                    'student_id': r.student_id,
                    'name': r.name,
                    'original_score': r.original_score,
                    'adjusted_score': r.adjusted_score,
                    'total_deduction': r.total_deduction,
                    'grade': r.grade,
                    'confidence': r.confidence,
                    'adjustments': [
                        {
                            'issue_title': adj.issue_title,
                            'category': adj.category,
                            'deduction': adj.deduction,
                            'reason': adj.reason
                        }
                        for adj in r.adjustments
                    ]
                }
                for r in enhanced_results
            ],
            ensure_ascii=False,
            indent=2,
        )

        output_path = paths.evaluations_json()
        atomic_write_json(output_path, evaluations, ensure_ascii=False, indent=2)

        print(f"\nEnhanced grading applied!")
        print(f"   Adjustments saved to: {enhanced_output_path}")

        if enhanced_results:
            total_deduction = sum(r.total_deduction for r in enhanced_results)
            avg_deduction = total_deduction / len(enhanced_results)
            max_deduction = max(r.total_deduction for r in enhanced_results)
            print(f"\nGrading adjustment statistics:")
            print(f"   Total adjustments: {sum(1 for r in enhanced_results if r.total_deduction > 0)} students")
            print(f"   Average deduction: {avg_deduction:.1f} points")
            print(f"   Maximum deduction: {max_deduction:.1f} points")

    except ImportError as e:
        print(f"Warning: Could not import enhanced grading module: {e}")
    except Exception as e:
        print(f"Warning: Error applying enhanced grading: {e}")
        import traceback
        traceback.print_exc()


def main():
    global ENABLE_ENHANCED_FEEDBACK, ENABLE_ENHANCED_GRADING, ENABLE_SEMANTIC_SCORING, paths

    parser = argparse.ArgumentParser(description='评估学生实验报告')
    parser.add_argument('--enhanced', '-e', action='store_true', help='启用增强反馈生成')
    parser.add_argument('--enhanced-grading', '-g', action='store_true', help='启用增强精准评分')
    parser.add_argument('--semantic', '-s', action='store_true', help='启用语义相似度评分')
    parser.add_argument('--experiment-dir', type=str, default=str(DEFAULT_EXPERIMENT_DIR), help='实验目录路径')
    args = parser.parse_args()

    ENABLE_ENHANCED_FEEDBACK = args.enhanced or args.enhanced_grading
    ENABLE_ENHANCED_GRADING = args.enhanced_grading
    ENABLE_SEMANTIC_SCORING = args.semantic

    # 使用统一路径配置
    experiment_dir = Path(args.experiment_dir)
    paths = ExperimentPaths(experiment_dir=experiment_dir)

    # 初始化语义评分引擎（如果启用）
    semantic_engine = None
    if ENABLE_SEMANTIC_SCORING:
        try:
            from semantic_evaluation import create_semantic_scorer
            rubric_path = DATA_DIR / "rubric.json"
            semantic_engine = create_semantic_scorer(rubric_path)
            print("Semantic scoring engine initialized!")
        except ImportError as e:
            print(f"Warning: Could not import semantic scoring module: {e}")
            ENABLE_SEMANTIC_SCORING = False
        except Exception as e:
            print(f"Warning: Error initializing semantic scoring: {e}")
            ENABLE_SEMANTIC_SCORING = False

    print(f"Evaluating student reports for: {experiment_dir}")

    if ENABLE_ENHANCED_FEEDBACK:
        print("Enhanced feedback enabled!")

    if ENABLE_ENHANCED_GRADING:
        print("Enhanced precision grading enabled!")

    content_path = paths.extracted_content_json()
    if not content_path.exists():
        print(f"Error: {content_path} not found. Run extract_content.py first.")
        return

    with open(content_path, 'r', encoding='utf-8') as f:
        extracted_data = json.load(f)

    rubric_path = DATA_DIR / "rubric.json"
    with open(rubric_path, 'r', encoding='utf-8') as f:
        rubric = json.load(f)

    quality_path = paths.processed_dir / "quality_assessment.json"
    quality_data = None
    if quality_path.exists():
        with open(quality_path, 'r', encoding='utf-8') as f:
            quality_data = json.load(f)
        print("Using category-based quality assessment data...")

    evaluations = []
    quality_scores = quality_data.get('quality_scores', {}) if quality_data else {}

    for content in extracted_data:
        student_id = content['student_id']
        quality_info = quality_scores.get(student_id) if quality_scores else None
        eval_result = evaluate_report(content, rubric, quality_info, semantic_engine)
        evaluations.append(eval_result)

        # 显示评分方法
        method_str = ""
        if eval_result.get('scoring_method'):
            methods = [f"{cat}:{method}" for cat, method in eval_result['scoring_method'].items()]
            method_str = f" [{', '.join(methods)}]"

        print(f"  {eval_result['student_id']}: {eval_result['total_score']}分 ({eval_result['grade_label']}){method_str}")

    output_path = paths.evaluations_json()
    atomic_write_json(output_path, evaluations, ensure_ascii=False, indent=2)

    print(f"\nEvaluated {len(evaluations)} reports")
    print(f"Results saved to: {output_path}")

    if ENABLE_ENHANCED_FEEDBACK:
        print("\nGenerating enhanced feedback...")
        try:
            tools_path = BASE_DIR / "tools" / "plagiarism"
            if str(tools_path) not in sys.path:
                sys.path.insert(0, str(tools_path))

            from enhanced_feedback import EnhancedFeedbackGenerator, save_enhanced_feedback

            generator = EnhancedFeedbackGenerator()
            feedback_dir = PROCESSED_DIR / "enhanced_feedback"
            feedback_dir.mkdir(exist_ok=True)

            for i, content in enumerate(extracted_data):
                student_id = content['student_id']
                name = content.get('name', '')
                text = content.get('full_text', '')

                eval_result = next((e for e in evaluations if e['student_id'] == student_id), None)
                if not eval_result:
                    continue

                from types import SimpleNamespace
                grading_result = SimpleNamespace(
                    total_score=eval_result['total_score'],
                    total_possible=100,
                    percentage=eval_result['total_score'],
                    grade=eval_result['grade']
                )

                enhanced_result = generator.generate_enhanced_feedback(
                    student_id, name, text, grading_result
                )
                save_enhanced_feedback(enhanced_result, feedback_dir, generator)
                print(f"  [{i+1}/{len(extracted_data)}] Generated feedback for {student_id}")

            print(f"\nEnhanced feedback saved to: {feedback_dir}")

            if ENABLE_ENHANCED_GRADING:
                print("\nApplying enhanced precision grading...")
                apply_enhanced_grading(extracted_data, evaluations, paths, rubric_path)

        except ImportError as e:
            print(f"Warning: Could not import enhanced feedback module: {e}")
        except Exception as e:
            print(f"Warning: Error generating enhanced feedback: {e}")

    scores = [e['total_score'] for e in evaluations]
    print(f"\nSummary:")
    print(f"  Average score: {sum(scores)/len(scores):.1f}")
    print(f"  Highest score: {max(scores)}")
    print(f"  Lowest score: {min(scores)}")
    print(f"  Grade distribution:")
    grade_counts = {}
    for e in evaluations:
        grade_counts[e['grade_label']] = grade_counts.get(e['grade_label'], 0) + 1
    for grade, count in sorted(grade_counts.items()):
        print(f"    {grade}: {count}")


if __name__ == "__main__":
    main()
