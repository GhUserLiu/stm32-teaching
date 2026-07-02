#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
应用抄袭惩罚
根据相似度自动调整评分
"""

import json
from pathlib import Path
from datetime import datetime


# 配置路径
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / 'data'

# 输入文件
EVALUATIONS_INPUT = DATA_DIR / 'evaluations.json'
QUALITY_PATH = DATA_DIR / 'quality_assessment.json'

# 输出文件
EVALUATIONS_OUTPUT = DATA_DIR / 'evaluations_adjusted.json'
EVALUATIONS_BACKUP = DATA_DIR / f'evaluations_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'


def calculate_penalty_score(original_score, similarity):
    """
    根据相似度计算扣分后的分数

    规则:
    - 相似度 > 90%: 抄袭，分数设为0
    - 相似度 60-90%: 警告，按比例扣分

    扣分公式:
    - 60-70%: 扣除原分数的 20%
    - 70-80%: 扣除原分数的 40%
    - 80-90%: 扣除原分数的 60%
    """
    if similarity > 90:
        return 0, '抄袭'
    elif similarity > 80:
        penalty_rate = 0.6
        return original_score * (1 - penalty_rate), f'警告(扣除{penalty_rate*100:.0f}%)'
    elif similarity > 70:
        penalty_rate = 0.4
        return original_score * (1 - penalty_rate), f'警告(扣除{penalty_rate*100:.0f}%)'
    elif similarity > 60:
        penalty_rate = 0.2
        return original_score * (1 - penalty_rate), f'警告(扣除{penalty_rate*100:.0f}%)'
    else:
        return original_score, '原创'


def apply_plagiarism_penalty():
    """应用抄袭惩罚"""
    print("=== 应用抄袭惩罚 ===\n")

    # 1. 加载原始评分数据
    print("1. 加载评分数据...")
    with open(EVALUATIONS_INPUT, 'r', encoding='utf-8') as f:
        evaluations = json.load(f)
    print(f"   - 加载 {len(evaluations)} 条评分记录")

    # 备份原始数据
    print("2. 备份原始数据...")
    with open(EVALUATIONS_BACKUP, 'w', encoding='utf-8') as f:
        json.dump(evaluations, f, ensure_ascii=False, indent=2)
    print(f"   - 备份至: {EVALUATIONS_BACKUP.name}")

    # 2. 加载质量评估数据
    print("\n3. 加载抄袭检测数据...")
    with open(QUALITY_PATH, 'r', encoding='utf-8') as f:
        quality_data = json.load(f)

    plagiarism_results = quality_data.get('plagiarism_data', {}).get('plagiarism_results', {})
    print(f"   - 有抄袭检测数据的学生: {len(plagiarism_results)} 人")

    # 3. 应用惩罚
    print("\n4. 应用抄袭惩罚...")

    stats = {
        'total': len(evaluations),
        'original': 0,
        'warning': 0,
        'plagiarism': 0,
        'no_submit': 0,
        'no_change': 0
    }

    adjustments = []

    for eval_data in evaluations:
        student_id = eval_data['student_id']
        original_score = eval_data.get('total_score', 0)

        # 获取最大相似度
        max_similarity = 0
        if student_id in plagiarism_results:
            sim_data = plagiarism_results[student_id]
            for other, info in sim_data.items():
                overall = info.get('overall', 0)
                if overall > max_similarity:
                    max_similarity = overall

        # 计算扣分
        new_score, status = calculate_penalty_score(original_score, max_similarity)

        # 如果没有名字且分数为0，标记为未提交
        if not eval_data.get('name', '').strip() and original_score == 0:
            status = '未提交'
            new_score = 0

        # 总是更新状态（即使分数没变）
        eval_data['plagiarism_status'] = status
        if max_similarity > 0:
            eval_data['similarity'] = max_similarity

        if new_score != original_score or (not eval_data.get('name', '').strip() and original_score == 0):
            # 记录调整
            adjustments.append({
                'student_id': student_id,
                'name': eval_data.get('name', ''),
                'original_score': original_score,
                'similarity': max_similarity,
                'new_score': new_score,
                'deduction': original_score - new_score,
                'status': status
            })

            # 更新评分
            eval_data['original_total_score'] = original_score
            eval_data['total_score'] = round(new_score, 1)  # 保留 1 位小数，避免 int 截断导致边界丢分
            eval_data['plagiarism_status'] = status
            eval_data['similarity'] = max_similarity

            # 更新等级
            if new_score >= 90:
                eval_data['grade'] = 'A'
            elif new_score >= 80:
                eval_data['grade'] = 'B'
            elif new_score >= 70:
                eval_data['grade'] = 'C'
            elif new_score >= 60:
                eval_data['grade'] = 'D'
            else:
                eval_data['grade'] = 'F'

            # 更新统计
            if status == '抄袭':
                stats['plagiarism'] += 1
            elif status == '警告':
                stats['warning'] += 1
            elif status == '未提交':
                stats['no_submit'] += 1
        else:
            # 分数没有变化，但仍需更新统计
            if status == '原创':
                stats['original'] += 1
            elif status == '抄袭':
                stats['plagiarism'] += 1
            elif status == '警告':
                stats['warning'] += 1
            elif status == '未提交':
                stats['no_submit'] += 1

        if original_score == 0 and status not in ['未提交', '抄袭']:
            stats['no_change'] += 1

    # 4. 保存调整后的数据
    print("\n5. 保存调整后的数据...")
    with open(EVALUATIONS_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(evaluations, f, ensure_ascii=False, indent=2)
    print(f"   - 保存至: {EVALUATIONS_OUTPUT.name}")

    # 同时覆盖原文件
    with open(EVALUATIONS_INPUT, 'w', encoding='utf-8') as f:
        json.dump(evaluations, f, ensure_ascii=False, indent=2)
    print(f"   - 已更新: {EVALUATIONS_INPUT.name}")

    # 6. 打印调整详情
    print("\n=== 统计结果 ===")
    print(f"总人数: {stats['total']}")
    print(f"原创: {stats['original']} 人")
    print(f"警告: {stats['warning']} 人")
    print(f"抄袭: {stats['plagiarism']} 人")
    print(f"未提交: {stats['no_submit']} 人")

    # 打印调整详情（按扣分排序）
    if adjustments:
        print("\n=== 调整详情（按相似度排序）===")
        adjustments.sort(key=lambda x: x['similarity'], reverse=True)

        print(f"{'学号':<12} {'姓名':<12} {'原分':<6} {'相似度':<8} {'新分':<6} {'扣分':<6} {'状态':<8}")
        print("-" * 70)

        for adj in adjustments:
            print(f"{adj['student_id']:<12} {adj['name'][:10]:<12} {adj['original_score']:<6} "
                  f"{adj['similarity']:<8.1f} {adj['new_score']:<6.0f} {adj['deduction']:<6.0f} {adj['status']:<8}")

        # 计算平均分变化
        original_avg = sum(a['original_score'] for a in adjustments) / len(adjustments) if adjustments else 0
        new_avg = sum(a['new_score'] for a in adjustments) / len(adjustments) if adjustments else 0

        print()
        print(f"调整学生平均分: {original_avg:.1f} → {new_avg:.1f}")


if __name__ == '__main__':
    try:
        apply_plagiarism_penalty()
        print("\n✅ 抄袭惩罚应用完成!")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
