"""
质量评估模块（基于 Rubric 类别）
Quality Assessment Module (Category-Based)

重构版本：质量评估维度直接对应 rubric 类别
"""

import json
import re
from pathlib import Path
from collections import defaultdict
from difflib import SequenceMatcher

# 导入新的类别质量评估模块
# 兼容两种运行方式：脚本目录直接运行（裸导入）与 PYTHONPATH=src 包导入
try:
    from category_quality_assessment import (
        CategoryQualityAssessor,
        assess_category_quality
    )
except ModuleNotFoundError:
    from tools.teaching_scripts.category_quality_assessment import (
        CategoryQualityAssessor,
        assess_category_quality
    )

BASE_DIR = Path(__file__).parent.parent.parent.parent.parent  # Go up to project root
EXPERIMENT_DIR = BASE_DIR / "docs" / "teaching" / "2026-春季" / "汽服2302B班" / "07-car-gear"
PROCESSED_DIR = EXPERIMENT_DIR / "processed"


def extract_code_blocks(text):
    """Extract code blocks from report text"""
    code_patterns = [
        r'```.*?```',
        r'void\s+\w+\([^)]*\)\s*{[^}]*}',
        r'#include\s*<[^>]+>',
        r'HAL_GPIO_\w+\([^)]+\)',
        r'GPIO_[A-Z_]+',
    ]

    code_blocks = []
    for pattern in code_patterns:
        matches = re.findall(pattern, text, re.DOTALL | re.MULTILINE)
        code_blocks.extend(matches)

    return code_blocks


def extract_paragraphs(text):
    """Extract meaningful paragraphs for comparison"""
    paragraphs = re.split(r'\n\n+|\n\s*\n', text)
    meaningful = [p.strip() for p in paragraphs if len(p.strip()) > 30 and not p.strip().startswith('#')]
    return meaningful


def calculate_similarity(text1, text2):
    """Calculate similarity ratio between two texts"""
    return SequenceMatcher(None, text1, text2).ratio()


def extract_group_number(name):
    """Extract group number from student name"""
    if not name:
        return None
    match = re.search(r'第?([一二三四五六七八九十1-9]\d*)\s*组', name)
    if match:
        chinese_nums = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
                       '六': '6', '七': '7', '八': '8', '九': '9', '十': '10'}
        group_str = match.group(1)
        if group_str in chinese_nums:
            group_str = chinese_nums[group_str]
        try:
            return int(group_str)
        except ValueError:
            return group_str
    return None


def assess_quality(extracted_data, rubric_path=None):
    """
    基于 rubric 类别的质量评估

    Args:
        extracted_data: 提取的学生报告列表
        rubric_path: rubric 文件路径

    Returns:
        {学号: 质量评估结果}
    """
    print("Running category-based quality assessment...")

    # 默认 rubric 路径
    if rubric_path is None:
        rubric_path = Path(__file__).parent.parent / "rubrics" / "rubric.json"

    # 使用新的类别质量评估
    quality_scores = assess_category_quality(extracted_data, rubric_path)

    print(f"  Assessed quality for {len(quality_scores)} reports")

    return quality_scores


def detect_plagiarism(extracted_data):
    """Detect plagiarism among student reports"""
    print("Running plagiarism detection...")
    print("  Note: Same-group reports are allowed to be similar (except personal reflections)")

    submissions = [s for s in extracted_data if not s.get('missing')]

    for s in submissions:
        s['group'] = extract_group_number(s.get('name', ''))

    plagiarism_results = {}
    suspicious_pairs = []

    for i, s1 in enumerate(submissions):
        s1_id = s1['student_id']
        s1_group = s1.get('group')
        s1_text = s1.get('full_text', '')
        s1_para = extract_paragraphs(s1_text)

        similarities = defaultdict(dict)

        for j, s2 in enumerate(submissions):
            if i >= j:
                continue

            s2_id = s2['student_id']
            s2_group = s2.get('group')
            s2_text = s2.get('full_text', '')

            # Skip if same group
            if s1_group is not None and s2_group is not None:
                if s1_group == s2_group:
                    continue

            overall_sim = calculate_similarity(s1_text[:3000], s2_text[:3000])

            s1_code = extract_code_blocks(s1_text)
            s2_code = extract_code_blocks(s2_text)
            code_sim = 0
            if s1_code and s2_code:
                s1_code_str = ' '.join(s1_code)
                s2_code_str = ' '.join(s2_code)
                code_sim = calculate_similarity(s1_code_str, s2_code_str)

            s2_para = extract_paragraphs(s2_text)
            para_matches = 0
            for p1 in s1_para:
                for p2 in s2_para:
                    if calculate_similarity(p1, p2) > 0.85:
                        para_matches += 1
                        break

            weighted_sim = (overall_sim * 0.4 + code_sim * 0.4 +
                          (para_matches / max(len(s1_para), 1)) * 0.2)

            if weighted_sim > 0.5 or overall_sim > 0.7 or code_sim > 0.8:
                similarities[s2_id] = {
                    'overall': round(overall_sim * 100, 1),
                    'code': round(code_sim * 100, 1),
                    'paragraphs': para_matches,
                    'weighted': round(weighted_sim * 100, 1)
                }

                if weighted_sim > 0.6:
                    suspicious_pairs.append({
                        's1': s1_id,
                        's2': s2_id,
                        's1_name': s1.get('name', ''),
                        's2_name': s2.get('name', ''),
                        'similarity': round(weighted_sim * 100, 1)
                    })

        if similarities:
            plagiarism_results[s1_id] = dict(similarities)

    print(f"  Found {len(suspicious_pairs)} suspicious pairs (>60% similarity)")

    return {
        'plagiarism_results': plagiarism_results,
        'suspicious_pairs': suspicious_pairs
    }


def generate_personalized_suggestions(evaluations, quality_scores, plagiarism_data):
    """Generate personalized suggestions for each student"""
    print("Generating personalized suggestions...")

    suggestions = {}

    for eval in evaluations:
        student_id = eval['student_id']

        student_suggestions = {
            'student_id': student_id,
            'suggestions': [],
            'warnings': [],
            'plagiarism_warning': False
        }

        # Check for plagiarism
        plagiarism_results = plagiarism_data.get('plagiarism_results', {})
        if student_id in plagiarism_results:
            similar_students = plagiarism_results[student_id]
            if any(sim['weighted'] > 70 for sim in similar_students.values()):
                student_suggestions['plagiarism_warning'] = True
                student_suggestions['warnings'].append("⚠️ 报告内容与其他同学高度相似，请确认是否为原创")

        # Get quality info
        quality = quality_scores.get(student_id, {})
        category_qualities = quality.get('category_qualities', {})

        # Generate suggestions based on weak categories
        scores = eval.get('scores', {})

        # Team collaboration
        team_quality = category_qualities.get('team_collaboration', {})
        if team_quality.get('quality_score', 100) < 70:
            for issue in team_quality.get('quality_issues', []):
                student_suggestions['suggestions'].append(f"团队协作：{issue}")

        # Principle understanding
        principle_quality = category_qualities.get('principle_understanding', {})
        if principle_quality.get('quality_score', 100) < 70:
            for issue in principle_quality.get('quality_issues', []):
                student_suggestions['suggestions'].append(f"原理理解：{issue}")

        # Completion
        completion_quality = category_qualities.get('completion', {})
        if completion_quality.get('quality_score', 100) < 70:
            for issue in completion_quality.get('quality_issues', []):
                student_suggestions['suggestions'].append(f"实验完成度：{issue}")

        # Code quality
        code_quality = category_qualities.get('code_quality', {})
        if code_quality.get('quality_score', 100) < 70:
            for issue in code_quality.get('quality_issues', []):
                student_suggestions['suggestions'].append(f"代码质量：{issue}")

        # Report quality
        report_quality = category_qualities.get('report_quality', {})
        if report_quality.get('quality_score', 100) < 70:
            for issue in report_quality.get('quality_issues', []):
                student_suggestions['suggestions'].append(f"报告质量：{issue}")

        # Overall quality based suggestions
        overall_quality = quality.get('overall_quality', 0)
        if overall_quality < 60:
            student_suggestions['suggestions'].append("整体建议：报告内容需要大幅完善，建议参考优秀同学的结构")
        elif overall_quality >= 85:
            student_suggestions['suggestions'].append("整体表现优秀！继续保持")

        suggestions[student_id] = student_suggestions

    print(f"  Generated suggestions for {len(suggestions)} students")

    return suggestions


def main():
    """Run quality assessment and plagiarism detection"""
    print("=" * 60)
    print("质量评估与抄袭检测（基于 Rubric 类别）")
    print("=" * 60)

    # Load extracted content
    content_path = PROCESSED_DIR / "extracted_content.json"
    with open(content_path, 'r', encoding='utf-8') as f:
        extracted_data = json.load(f)

    # Load rubric
    rubric_path = Path(__file__).parent.parent / "rubrics" / "rubric.json"

    # Run category-based quality assessment
    quality_scores = assess_quality(extracted_data, rubric_path)

    # Run plagiarism detection
    plagiarism_data = detect_plagiarism(extracted_data)

    # Load evaluations for suggestions
    eval_path = PROCESSED_DIR / "evaluations.json"
    if eval_path.exists():
        with open(eval_path, 'r', encoding='utf-8') as f:
            evaluations = json.load(f)

        # Generate personalized suggestions
        suggestions = generate_personalized_suggestions(
            evaluations, quality_scores, plagiarism_data
        )
    else:
        suggestions = {}
        print("  Note: evaluations.json not found, skipping suggestions")

    # Save results
    output = {
        'plagiarism_data': plagiarism_data,
        'quality_scores': quality_scores,
        'suggestions': suggestions
    }

    output_path = PROCESSED_DIR / "quality_assessment.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print(f"\nResults saved to: {output_path}")

    # Print summary
    print("\n--- Summary ---")
    print(f"Suspicious pairs (>60% similarity): {len(plagiarism_data['suspicious_pairs'])}")
    if plagiarism_data['suspicious_pairs']:
        print("\nTop suspicious pairs:")
        for pair in sorted(plagiarism_data['suspicious_pairs'],
                          key=lambda x: x['similarity'], reverse=True)[:5]:
            print(f"  {pair['s1']} & {pair['s2']}: {pair['similarity']}% similarity")

    # Quality distribution
    quality_levels = defaultdict(int)
    for q in quality_scores.values():
        overall = q.get('overall_quality', 0)
        if overall >= 85:
            quality_levels['优秀'] += 1
        elif overall >= 70:
            quality_levels['良好'] += 1
        elif overall >= 60:
            quality_levels['及格'] += 1
        else:
            quality_levels['需改进'] += 1

    print(f"\nQuality distribution:")
    for level, count in sorted(quality_levels.items()):
        print(f"  {level}: {count}")


if __name__ == "__main__":
    main()
