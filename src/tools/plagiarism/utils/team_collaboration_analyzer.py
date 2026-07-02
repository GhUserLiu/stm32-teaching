#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
小组协作分析模块
Team Collaboration Analyzer

分析小组内学生报告的相似度，识别潜在问题：
- 互相抄袭（组员间报告高度相似）
- 搭便车现象（个人心得与其他成员雷同）
- 分工不合理（代码重复度高）
"""

import sys
import io
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict
from difflib import SequenceMatcher

# Windows控制台编码修复
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


@dataclass
class TeamSimilarity:
    """组员相似度"""
    student1_id: str
    student1_name: str
    student2_id: str
    student2_name: str

    # 相似度指标
    overall_similarity: float  # 整体相似度
    text_similarity: float     # 文本相似度
    code_similarity: float     # 代码相似度
    experience_similarity: float  # 心得相似度

    # 风险评估
    risk_level: str  # 'low', 'medium', 'high'
    issues: List[str] = field(default_factory=list)


@dataclass
class TeamAnalysisResult:
    """小组分析结果"""
    team_id: str
    member_count: int
    members: List[str]

    # 相似度矩阵
    similarities: List[TeamSimilarity]

    # 分析结果
    overall_collaboration_quality: str  # 'good', 'fair', 'poor'
    potential_free_riders: List[str]   # 潜在搭便车者
    potential_plagiarism_pairs: List[Tuple[str, str]]  # 潜在抄袭对子

    # 建议
    recommendations: List[str] = field(default_factory=list)


class TeamCollaborationAnalyzer:
    """小组协作分析器"""

    def __init__(self):
        """初始化分析器"""
        pass

    def analyze_team(
        self,
        team_members: Dict[str, dict],
        team_id: str = None
    ) -> TeamAnalysisResult:
        """
        分析小组协作情况

        Args:
            team_members: {学号: {name, text, experience}}
            team_id: 小组ID

        Returns:
            分析结果
        """
        member_ids = list(team_members.keys())

        # 计算组员间相似度
        similarities = []
        for i, id1 in enumerate(member_ids):
            for id2 in member_ids[i+1:]:
                similarity = self._calculate_member_similarity(
                    id1, team_members[id1],
                    id2, team_members[id2]
                )
                similarities.append(similarity)

        # 分析协作质量
        quality, free_riders, plagiarism_pairs = self._assess_collaboration(
            similarities, team_members
        )

        # 生成建议
        recommendations = self._generate_recommendations(
            quality, free_riders, plagiarism_pairs, similarities
        )

        return TeamAnalysisResult(
            team_id=team_id or 'unknown',
            member_count=len(team_members),
            members=member_ids,
            similarities=similarities,
            overall_collaboration_quality=quality,
            potential_free_riders=free_riders,
            potential_plagiarism_pairs=plagiarism_pairs,
            recommendations=recommendations
        )

    def _calculate_member_similarity(
        self,
        id1: str, member1: dict,
        id2: str, member2: dict
    ) -> TeamSimilarity:
        """计算两个成员的相似度"""
        text1 = member1.get('text', '')
        text2 = member2.get('text', '')
        exp1 = member1.get('experience', {})
        exp2 = member2.get('experience', {})

        # 整体相似度
        overall_sim = self._text_similarity(text1, text2)

        # 提取代码块
        code1 = self._extract_code(text1)
        code2 = self._extract_code(text2)
        code_sim = self._text_similarity(code1, code2) if code1 and code2 else 0

        # 提取心得体会
        exp_text1 = exp1.get('content', '')
        exp_text2 = exp2.get('content', '')
        exp_sim = self._text_similarity(exp_text1, exp_text2) if exp_text1 and exp_text2 else 0

        # 文本相似度（排除代码和心得）
        text_sim = overall_sim

        # 风险评估
        risk_level, issues = self._assess_similarity_risk(
            overall_sim, code_sim, exp_sim, id1, id2
        )

        return TeamSimilarity(
            student1_id=id1,
            student1_name=member1.get('name', id1),
            student2_id=id2,
            student2_name=member2.get('name', id2),
            overall_similarity=overall_sim,
            text_similarity=text_sim,
            code_similarity=code_sim,
            experience_similarity=exp_sim,
            risk_level=risk_level,
            issues=issues
        )

    def _text_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        if not text1 or not text2:
            return 0.0

        # 使用 SequenceMatcher
        return SequenceMatcher(None, text1, text2).ratio() * 100

    def _extract_code(self, text: str) -> str:
        """提取代码块"""
        patterns = [
            r'```(?:c|cpp)?\s*(.*?)```',
            r'void\s+\w+\([^)]*\)\s*{.*?}',
            r'HAL_GPIO[^;]*;'
        ]

        code_blocks = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            code_blocks.extend(matches)

        return '\n'.join(code_blocks)

    def _assess_similarity_risk(
        self,
        overall_sim: float,
        code_sim: float,
        exp_sim: float,
        id1: str,
        id2: str
    ) -> Tuple[str, List[str]]:
        """评估相似度风险"""
        issues = []
        risk_level = 'low'

        # 整体相似度过高
        if overall_sim >= 85:
            risk_level = 'high'
            issues.append(f"报告整体相似度过高 ({overall_sim:.1f}%)")
        elif overall_sim >= 70:
            risk_level = 'medium'
            issues.append(f"报告整体相似度较高 ({overall_sim:.1f}%)")

        # 代码相似度过高
        if code_sim >= 80:
            if risk_level != 'high':
                risk_level = 'medium'
            issues.append(f"代码相似度过高 ({code_sim:.1f}%)")

        # 心得相似度过高（疑似搭便车）
        if exp_sim >= 75:
            if exp_sim >= 90:
                risk_level = 'high'
                issues.append(f"心得体会几乎完全相同 ({exp_sim:.1f}%) - 疑似搭便车")
            else:
                if risk_level == 'low':
                    risk_level = 'medium'
                issues.append(f"心得体会相似度较高 ({exp_sim:.1f}%)")

        return risk_level, issues

    def _assess_collaboration(
        self,
        similarities: List[TeamSimilarity],
        team_members: Dict[str, dict]
    ) -> Tuple[str, List[str], List[Tuple[str, str]]]:
        """评估协作质量"""
        high_risk_count = sum(1 for s in similarities if s.risk_level == 'high')
        total_pairs = len(similarities)

        # 协作质量
        if high_risk_count == 0:
            quality = 'good'
        elif high_risk_count <= total_pairs / 3:
            quality = 'fair'
        else:
            quality = 'poor'

        # 潜在搭便车者
        free_riders = []
        exp_similarities = defaultdict(list)

        for sim in similarities:
            if sim.experience_similarity >= 75:
                exp_similarities[sim.student1_id].append(sim.student2_id)
                exp_similarities[sim.student2_id].append(sim.student1_id)

        # 与多个成员心得都高度相似，可能是搭便车
        for member_id, similar_members in exp_similarities.items():
            if len(similar_members) >= 2:
                free_riders.append(member_id)

        # 潜在抄袭对子
        plagiarism_pairs = []
        for sim in similarities:
            if sim.overall_similarity >= 80 or sim.code_similarity >= 85:
                plagiarism_pairs.append((sim.student1_id, sim.student2_id))

        return quality, free_riders, plagiarism_pairs

    def _generate_recommendations(
        self,
        quality: str,
        free_riders: List[str],
        plagiarism_pairs: List[Tuple[str, str]],
        similarities: List[TeamSimilarity]
    ) -> List[str]:
        """生成建议"""
        recommendations = []

        if quality == 'good':
            recommendations.append("✅ 小组协作良好，成员报告独立性强")
        elif quality == 'fair':
            recommendations.append("⚠️ 小组协作存在一些问题，建议关注")
        else:
            recommendations.append("🚨 小组协作存在严重问题，需要干预")

        if free_riders:
            names = [f"{mid}({team_members.get(mid, {}).get('name', mid)})" for mid in free_riders]
            recommendations.append(f"疑似搭便车: {', '.join(names)}")

        if plagiarism_pairs:
            pair_descs = []
            for id1, id2 in plagiarism_pairs:
                pair_descs.append(f"{id1}-{id2}")
            recommendations.append(f"疑似抄袭对子: {', '.join(pair_descs)}")

        # 检查代码问题
        high_code_sim = [s for s in similarities if s.code_similarity >= 80]
        if high_code_sim:
            recommendations.append(f"注意: {len(high_code_sim)}对成员代码相似度过高")

        return recommendations

    def analyze_all_teams(
        self,
        submissions: Dict[str, dict],
        group_info: Dict[str, str]
    ) -> Dict[str, TeamAnalysisResult]:
        """
        分析所有小组

        Args:
            submissions: 所有提交
            group_info: 小组信息 {学号: 小组号}

        Returns:
            {小组号: 分析结果}
        """
        # 按小组分组
        teams = defaultdict(dict)
        for student_id, submission in submissions.items():
            group_id = group_info.get(student_id, 'unknown')
            teams[group_id][student_id] = submission

        # 分析每个小组
        results = {}
        for group_id, members in teams.items():
            if len(members) >= 2:  # 至少2人才能分析
                results[group_id] = self.analyze_team(members, group_id)

        return results


def analyze_team_collaboration(
    team_members: Dict[str, dict],
    team_id: str = None
) -> TeamAnalysisResult:
    """
    分析小组协作（便捷函数）

    Args:
        team_members: {学号: {name, text, experience}}
        team_id: 小组ID

    Returns:
        分析结果
    """
    analyzer = TeamCollaborationAnalyzer()
    return analyzer.analyze_team(team_members, team_id)


def generate_team_report(analysis: TeamAnalysisResult) -> str:
    """
    生成小组分析报告

    Args:
        analysis: 分析结果

    Returns:
        Markdown报告
    """
    lines = [
        f"# 小组协作分析报告",
        f"",
        f"## 基本信息",
        f"- **小组ID**: {analysis.team_id}",
        f"- **成员数量**: {analysis.member_count}",
        f"- **成员学号**: {', '.join(analysis.members)}",
        f"",
        f"## 协作质量",
        f"- **整体评价**: {analysis.overall_collaboration_quality}",
        f""
    ]

    if analysis.recommendations:
        lines.append("## 建议")
        for rec in analysis.recommendations:
            lines.append(f"- {rec}")
        lines.append("")

    if analysis.potential_free_riders:
        lines.append("## 疑似搭便车者")
        for rider in analysis.potential_free_riders:
            lines.append(f"- {rider}")
        lines.append("")

    if analysis.potential_plagiarism_pairs:
        lines.append("## 疑似抄袭对子")
        for id1, id2 in analysis.potential_plagiarism_pairs:
            lines.append(f"- {id1} ↔ {id2}")
        lines.append("")

    lines.append("## 相似度详情")
    lines.append("")
    lines.append(f"{'成员1':<15} {'成员2':<15} {'整体相似度':<12} {'代码相似度':<12} {'心得相似度':<12} {'风险'}")
    lines.append("-" * 80)

    for sim in analysis.similarities:
        lines.append(
            f"{sim.student1_name:<15} {sim.student2_name:<15} "
            f"{sim.overall_similarity:<12.1f} {sim.code_similarity:<12.1f} "
            f"{sim.experience_similarity:<12.1f} {sim.risk_level}"
        )

        if sim.issues:
            for issue in sim.issues:
                lines.append(f"  ⚠️ {issue}")

    return '\n'.join(lines)


if __name__ == '__main__':
    # 测试代码
    print("小组协作分析模块测试")
    print("=" * 60)

    # 模拟数据
    team_members = {
        '23071140201': {
            'name': '张三',
            'text': '本实验使用STM32F407开发板，通过外部中断检测按键...',
            'experience': {'content': '通过本次实验，我深入理解了中断的工作原理'}
        },
        '23071140202': {
            'name': '李四',
            'text': '本次实验基于STM32F407，使用EXTI外部中断实现档位切换...',
            'experience': {'content': '这次实验让我学会了如何配置GPIO和中断'}
        },
        '23071140203': {
            'name': '王五',
            'text': '本实验使用STM32F407开发板，通过外部中断检测按键...',  # 故意与张三相同
            'experience': {'content': '通过本次实验，我深入理解了中断的工作原理'}  # 故意相同
        }
    }

    analyzer = TeamCollaborationAnalyzer()
    result = analyzer.analyze_team(team_members, 'test_team')

    print(f"小组ID: {result.team_id}")
    print(f"成员数量: {result.member_count}")
    print(f"协作质量: {result.overall_collaboration_quality}")
    print(f"\n建议:")
    for rec in result.recommendations:
        print(f"  {rec}")

    print(f"\n相似度详情:")
    for sim in result.similarities:
        print(f"  {sim.student1_name} - {sim.student2_name}: {sim.overall_similarity:.1f}%")
        if sim.issues:
            for issue in sim.issues:
                print(f"    ⚠️ {issue}")
