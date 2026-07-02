#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
处理汽服2301B班实验报告
Process 2301B Class Lab Reports
"""

import sys
import re
import zipfile
import io
import json
from pathlib import Path
from datetime import datetime

# 导入安全工具
from tools.security.zip_validator import ZipLimits, validate_zip_size, safe_extract_inner_zip, validate_path_traversal
from tools.security.xml_parser import extract_text_from_docx_xml
from tools.plagiarism.core.detector import PlagiarismDetector, SimilarityMethod

# 导入统一路径配置
from tools.common import ExperimentPaths

def extract_student_info_2301b(extract_dir, limits=None):
    """
    从2301B班提交中提取学生信息
    修改版：不依赖文件名中的"答题记录"字符串匹配
    """
    if limits is None:
        limits = ZipLimits()

    student_info = {}

    for zip_file in extract_dir.glob('*.zip'):
        # 从文件名提取学号
        match = re.search(r'(\d{11})', zip_file.name)
        if not match:
            continue
        student_id = match.group(1)

        info = {'name': None, 'time': None, 'content': None}

        try:
            with zipfile.ZipFile(zip_file, 'r') as outer:
                # 验证外层ZIP
                validate_zip_size(outer, limits)

                files = outer.namelist()
                if len(files) > 0 and files[0].endswith('.zip'):
                    # 安全提取内层ZIP
                    inner = safe_extract_inner_zip(outer, files[0], limits)
                    inner_files = inner.namelist()

                    # 查找.doc文件（答题记录）- 不检查文件名内容
                    doc_files = [f for f in inner_files if f.endswith('.doc')]
                    if doc_files:
                        # 验证文件路径
                        validate_path_traversal(doc_files[0])

                        doc_data = inner.read(doc_files[0])
                        doc_str = str(doc_data, errors='ignore')

                        pattern1 = r'<w:t>答题人：[^<]*</w:t>\s*.*?<w:t>([^<]+)</w:t>'
                        name_match = re.search(pattern1, doc_str, re.DOTALL)
                        if name_match:
                            info['name'] = name_match.group(1).strip()

                        pattern2 = r'<w:t>提交时间：[^<]*</w:t>\s*.*?<w:t>(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})[^<]*</w:t>'
                        time_match = re.search(pattern2, doc_str, re.DOTALL)
                        if time_match:
                            info['time'] = time_match.group(1).strip()

                    # 查找.docx文件（实验报告）
                    docx_files = [f for f in inner_files if f.endswith('.docx')]
                    if docx_files:
                        # 验证文件路径
                        validate_path_traversal(docx_files[0])

                        docx_data = inner.read(docx_files[0])

                        # 提取文本
                        with zipfile.ZipFile(io.BytesIO(docx_data), 'r') as docx:
                            xml_content = docx.read('word/document.xml')
                            text = extract_text_from_docx_xml(xml_content)
                            if text:
                                content = re.sub(r'\s+', '', text)
                                info['content'] = content

                    # 保存学生信息（即使没有姓名）
                    if info.get('content'):
                        student_info[student_id] = info

        except Exception as e:
            print(f"处理失败 {student_id}: {e}")

    return student_info


def run_plagiarism_detection(submissions, threshold=60):
    """
    运行查重检测
    """
    print("\n" + "="*60)
    print("执行查重检测")
    print("="*60)

    detector = PlagiarismDetector(
        method=SimilarityMethod.HYBRID,
        threshold=threshold
    )

    all_results, suspicious, _ = detector.detect(submissions)

    print(f"检测人数: {len(submissions)}")
    print(f"可疑对数: {len(suspicious)} (≥{threshold}%)")

    if suspicious:
        print("\n最高相似度对:")
        top = sorted(suspicious, key=lambda x: x.overall_similarity, reverse=True)[:5]
        for r in top:
            print(f"  {r.student_id} & {r.similar_to}: {r.overall_similarity:.1f}%")

    return all_results, suspicious


def simple_grading(submissions, all_results):
    """
    简单评分系统
    """
    print("\n" + "="*60)
    print("执行评分")
    print("="*60)

    grades = {}
    for student_id, submission in submissions.items():
        content = submission.get('text', '')
        content_len = len(content)

        # 基础评分
        score = 60  # 基础分

        # 内容长度评分
        if content_len > 5000:
            score += 20
        elif content_len > 3000:
            score += 15
        elif content_len > 1000:
            score += 10

        # 相似度扣分
        if student_id in all_results and all_results[student_id]:
            max_sim = max(r.overall_similarity for r in all_results[student_id])
            if max_sim > 80:
                score -= 30
            elif max_sim > 70:
                score -= 20
            elif max_sim > 60:
                score -= 10

        # 确保分数在0-100之间
        score = max(0, min(100, score))

        # 确定等级
        if score >= 90:
            grade = 'A'
        elif score >= 80:
            grade = 'B'
        elif score >= 70:
            grade = 'C'
        elif score >= 60:
            grade = 'D'
        else:
            grade = 'F'

        grades[student_id] = {
            'score': score,
            'grade': grade,
            'content_length': content_len,
            'name': submission.get('name', '未知')
        }

        print(f"{student_id} ({submission.get('name', '未知')}): {score}分 ({grade})")

    return grades


def save_results(paths: ExperimentPaths, all_results, suspicious, grades):
    """
    保存结果（使用统一路径配置）

    Args:
        paths: ExperimentPaths 实例
        all_results: 查重结果
        suspicious: 可疑对列表
        grades: 评分结果
    """
    # 确保输出目录存在
    paths.plagiarism_dir.mkdir(parents=True, exist_ok=True)
    paths.grading_dir.mkdir(parents=True, exist_ok=True)

    # 保存查重结果到 results/plagiarism/
    plagiarism_data = {
        'timestamp': datetime.now().isoformat(),
        'total_students': len(grades),
        'suspicious_pairs': len(suspicious),
        'results': []
    }

    for sid, results in all_results.items():
        for r in results:
            plagiarism_data['results'].append({
                'student_id': sid,
                'similar_to': r.similar_to,
                'similarity': r.overall_similarity,
                'is_cross_group': r.is_cross_group
            })

    plagiarism_path = paths.plagiarism_json()
    with open(plagiarism_path, 'w', encoding='utf-8') as f:
        json.dump(plagiarism_data, f, ensure_ascii=False, indent=2)

    # 保存评分结果到 results/grading/
    grading_data = {
        'timestamp': datetime.now().isoformat(),
        'grades': grades
    }

    grading_path = paths.grading_json()
    with open(grading_path, 'w', encoding='utf-8') as f:
        json.dump(grading_data, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {paths.results_dir}")
    print(f"  - {plagiarism_path.relative_to(paths.experiment_dir)}")
    print(f"  - {grading_path.relative_to(paths.experiment_dir)}")


def main():
    """主函数"""
    # 使用统一路径配置
    paths = ExperimentPaths(
        experiment_dir=Path('data/teaching/2026-春季/汽服2301B班/07-car-gear')
    )

    # 创建必要的目录
    paths.extracted_dir.mkdir(parents=True, exist_ok=True)
    paths.results_dir.mkdir(parents=True, exist_ok=True)

    print("="*60)
    print("汽服2301B班实验报告处理系统")
    print("="*60)
    print(f"实验目录: {paths.experiment_dir}")

    # 1. 提取学生信息
    print("\n提取学生信息...")
    student_info = extract_student_info_2301b(paths.extracted_dir)
    print(f"成功提取 {len(student_info)} 份报告")

    if not student_info:
        print("错误: 没有提取到学生信息")
        return 1

    # 显示学生列表
    print("\n学生列表:")
    for sid, info in sorted(student_info.items()):
        name = info.get('name', '未知')
        content_len = len(info.get('content', ''))
        print(f"  {sid} ({name}): {content_len} 字符")

    # 2. 运行查重检测
    all_results, suspicious = run_plagiarism_detection(student_info, threshold=60)

    # 3. 评分
    grades = simple_grading(student_info, all_results)

    # 4. 保存结果（使用统一路径配置）
    save_results(paths, all_results, suspicious, grades)

    print("\n" + "="*60)
    print("处理完成!")
    print("="*60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
