#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新学生反馈，添加相似度信息
Update student feedback with similarity information
"""

import json
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

# 导入统一路径配置
from tools.common import ExperimentPaths


def load_plagiarism_data(json_path: Path) -> Dict:
    """加载查重报告数据"""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_grading_data(json_path: Path) -> List[Dict]:
    """加载评分数据"""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_similarity_map(plagiarism_data: Dict) -> Dict[str, List[Dict]]:
    """构建学生相似度映射表

    返回格式: {学号: [{学号, 姓名, 相似度, 是否跨组, 共享段落数, 共享代码数}]}
    """
    similarity_map = defaultdict(list)

    suspicious_pairs = plagiarism_data.get('suspicious_details', [])

    for pair in suspicious_pairs:
        student1 = pair['student1']
        student2 = pair['student2']
        similarity = pair['overall_similarity']
        is_cross_group = pair.get('is_cross_group', False)
        shared_paragraphs = pair.get('shared_paragraphs', 0)
        shared_code_blocks = pair.get('shared_code_blocks', 0)

        # 双向添加
        similarity_map[student1].append({
            'similar_to': student2,
            'similarity': similarity,
            'is_cross_group': is_cross_group,
            'shared_paragraphs': shared_paragraphs,
            'shared_code_blocks': shared_code_blocks
        })

        similarity_map[student2].append({
            'similar_to': student1,
            'similarity': similarity,
            'is_cross_group': is_cross_group,
            'shared_paragraphs': shared_paragraphs,
            'shared_code_blocks': shared_code_blocks
        })

    # 按相似度降序排序
    for student_id in similarity_map:
        similarity_map[student_id].sort(key=lambda x: x['similarity'], reverse=True)

    return similarity_map


def generate_similarity_section(
    student_id: str,
    student_name: str,
    similarity_list: List[Dict]
) -> str:
    """生成相似度信息章节"""
    if not similarity_list:
        return ""

    # 只显示相似度 >= 60% 的
    high_similarity = [s for s in similarity_list if s['similarity'] >= 60.0]

    if not high_similarity:
        return ""

    section = "\n## ⚠️ 相似度检测报告\n\n"
    section += f"您的报告与以下同学存在较高相似度（需注意）：\n\n"

    for item in high_similarity:
        similar_id = item['similar_to']
        similarity = item['similarity']
        is_cross = item['is_cross_group']
        shared_para = item['shared_paragraphs']
        shared_code = item['shared_code_blocks']

        # 判断风险等级
        if similarity >= 85:
            risk_level = "🔴 极高"
            advice = "（可能存在抄袭，请立即修改）"
        elif similarity >= 75:
            risk_level = "🟠 高"
            advice = "（建议重写相关部分）"
        elif similarity >= 65:
            risk_level = "🟡 中"
            advice = "（请注意改写）"
        else:
            risk_level = "🟢 低"
            advice = "（请参考）"

        group_note = "跨组" if is_cross else "同组"

        section += f"- **{similar_id}** ({group_note}): 相似度 **{similarity:.1f}%** {risk_level}{advice}\n"
        section += f"  - 共享段落: {shared_para} 个\n"
        section += f"  - 共享代码: {shared_code} 个\n\n"

    # 添加说明
    section += "---\n"
    section += "**说明**: 相似度检测基于文本内容和代码片段分析。"
    section += "如果您的报告与其他同学报告相似度高，请：\n"
    section += "1. 检查是否有直接复制粘贴\n"
    section += "2. 使用自己的语言重新表达相同的概念\n"
    section += "3. 添加自己的分析和见解\n"
    section += "4. 确保代码注释是自己写的\n\n"

    return section


def update_feedback_with_similarity(
    grading_data: List[Dict],
    similarity_map: Dict[str, List[Dict]],
    grading_data_path: Path
) -> None:
    """更新评分数据，添加相似度信息"""
    updated_count = 0

    for student in grading_data:
        student_id = student['student_id']
        name = student['name']

        if student_id in similarity_map:
            similarity_list = similarity_map[student_id]
            student['similarity_info'] = similarity_list

            # 添加最高相似度标记
            if similarity_list:
                max_sim = similarity_list[0]['similarity']
                student['max_similarity'] = max_sim

                # 计算相似度风险
                if max_sim >= 85:
                    student['similarity_risk'] = 'high'
                elif max_sim >= 70:
                    student['similarity_risk'] = 'medium'
                else:
                    student['similarity_risk'] = 'low'

            updated_count += 1

    # 保存更新后的数据
    with open(grading_data_path, 'w', encoding='utf-8') as f:
        json.dump(grading_data, f, ensure_ascii=False, indent=2)

    print(f"已更新 {updated_count} 个学生的相似度信息")


def generate_updated_feedback_files(
    grading_data: List[Dict],
    similarity_map: Dict[str, List[Dict]],
    paths: ExperimentPaths
) -> None:
    """生成包含相似度信息的反馈文件（使用统一路径配置）

    Args:
        grading_data: 评分数据
        similarity_map: 相似度映射
        paths: ExperimentPaths 实例
    """
    md_dir = paths.feedback_dir / 'md'
    md_dir.mkdir(parents=True, exist_ok=True)

    for student in grading_data:
        student_id = student['student_id']
        name = student['name']

        # 获取相似度信息
        similarity_list = similarity_map.get(student_id, [])

        # 生成反馈内容
        feedback = f"# 学习反馈报告\n\n"
        feedback += f"**学号**: {student_id}\n"
        feedback += f"**姓名**: {name}\n"
        feedback += f"**总分**: {student['total_score']}/{student['total_possible']} ({student['percentage']}%)\n"
        feedback += f"**等级**: {student['grade']}\n\n"

        # 添加相似度章节
        similarity_section = generate_similarity_section(
            student_id, name, similarity_list
        )
        if similarity_section:
            feedback += similarity_section
            feedback += "\n---\n\n"

        # 添加各类别评分
        feedback += "## 📊 详细评分\n\n"

        category_scores = student.get('category_scores', {})
        for cat_id, cat_score in category_scores.items():
            cat_name = cat_score['name']
            earned = cat_score['earned']
            possible = cat_score['possible']
            percentage = cat_score['percentage']

            feedback += f"### {cat_name}: {earned}/{possible} ({percentage:.0f}%)\n\n"

            feedback_items = cat_score.get('feedback', [])
            for item in feedback_items:
                feedback += f"- {item}\n"
            feedback += "\n"

        # 添加技术检查
        tech_check = student.get('technical_check', {})
        if tech_check:
            feedback += "## 🔧 技术要点检查\n\n"

            strengths = tech_check.get('strengths', [])
            if strengths:
                feedback += "### ✅ 优点\n\n"
                for s in strengths:
                    feedback += f"- {s}\n"
                feedback += "\n"

            weaknesses = tech_check.get('weaknesses', [])
            if weaknesses:
                feedback += "### ❌ 不足\n\n"
                for w in weaknesses:
                    feedback += f"- {w}\n"
                feedback += "\n"

        # 添加改进建议
        recommendations = student.get('recommendations', [])
        if recommendations:
            feedback += "## 💡 改进建议\n\n"
            for rec in recommendations:
                feedback += f"- {rec}\n"
            feedback += "\n"

        feedback += "---\n\n"
        feedback += "*本报告由评分系统自动生成*"

        # 保存文件
        filename = f"{student_id}_{name}_反馈.md"
        filepath = md_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(feedback)

    print(f"已生成 {len(grading_data)} 个反馈文件到 {md_dir}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='更新学生反馈，添加相似度信息'
    )

    parser.add_argument(
        '--experiment-dir',
        type=Path,
        default=Path('data/teaching/2026-春季/汽服2302B班/07-car-gear'),
        help='实验目录路径'
    )

    parser.add_argument(
        '--plagiarism-report',
        type=Path,
        default=None,
        help='查重报告JSON路径（默认从实验目录查找）'
    )

    parser.add_argument(
        '--grading-results',
        type=Path,
        default=None,
        help='评分结果JSON路径（默认从实验目录查找）'
    )

    args = parser.parse_args()

    # 使用统一路径配置
    paths = ExperimentPaths(experiment_dir=args.experiment_dir)

    # 确定文件路径
    if args.plagiarism_report is None:
        plagiarism_report = paths.plagiarism_json()
    else:
        plagiarism_report = args.plagiarism_report

    if args.grading_results is None:
        grading_results = paths.grading_json()
    else:
        grading_results = args.grading_results

    # 加载数据
    print("加载查重报告...")
    plagiarism_data = load_plagiarism_data(plagiarism_report)

    print("加载评分数据...")
    grading_data = load_grading_data(grading_results)

    # 构建相似度映射
    print("构建相似度映射...")
    similarity_map = build_similarity_map(plagiarism_data)

    # 更新评分数据
    print("更新评分数据...")
    update_feedback_with_similarity(
        grading_data,
        similarity_map,
        grading_results
    )

    # 生成更新的反馈文件
    print("生成更新的反馈文件...")
    generate_updated_feedback_files(
        grading_data,
        similarity_map,
        paths
    )

    print("\n✅ 完成!")


if __name__ == '__main__':
    main()
