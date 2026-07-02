# -*- coding: utf-8 -*-
"""
自适应阈值系统
Adaptive Threshold System

基于数据分布动态调整相似度阈值，提高查重准确性
"""

from __future__ import annotations  # 延迟类型注解求值，避免 np=None 时的问题

import sys
try:
    import numpy as np
    HAS_NUMPY = True
except (ImportError, RuntimeError) as e:
    # RuntimeError: "CPU dispatcher tracer already initialized"
    # This can happen in PyInstaller frozen environments
    HAS_NUMPY = False
    np = None
    print(f"[WARNING] NumPy not available in adaptive_threshold: {e}", file=sys.stderr)
    # 清除可能损坏的 NumPy 模块
    modules_to_remove = [k for k in sys.modules.keys() if k.startswith('numpy')]
    for m in modules_to_remove:
        del sys.modules[m]

from typing import Dict, List, Tuple, Optional, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path

if TYPE_CHECKING:
    import numpy as np_typing
    NDArray = np_typing.ndarray
else:
    # 运行时使用字符串类型，避免 AttributeError
    NDArray = 'np.ndarray'


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"              # 低风险 (<60%)
    MEDIUM = "medium"        # 中风险 (60-75%)
    HIGH = "high"            # 高风险 (75-85%)
    CRITICAL = "critical"    # 极高风险 (>=85%)
    PARAPHRASE = "paraphrase"  # 改写 (50-85%, 语义相似但文本不同)


@dataclass
class ThresholdRecommendation:
    """阈值推荐结果"""
    suspicious_threshold: float      # 可疑阈值
    high_risk_threshold: float       # 高风险阈值
    plagiarism_threshold: float       # 抄袭阈值
    confidence: float                 # 推荐置信度 (0-1)
    reasoning: List[str]              # 推荐理由


@dataclass
class RiskAssessment:
    """风险评估结果"""
    risk_level: RiskLevel
    confidence: float                # 评估置信度 (0-1)
    probability: float               # 抄袭概率 (0-1)
    key_factors: List[str]           # 关键因素
    recommended_action: str          # 建议操作


class AdaptiveThresholdEngine:
    """自适应阈值引擎"""

    def __init__(self, baseline_threshold: float = 60.0):
        """
        初始化引擎

        Args:
            baseline_threshold: 基准阈值（作为分析的起点）
        """
        self.baseline = baseline_threshold
        self._historical_data: List[Dict] = []

    def analyze_similarity_distribution(
        self,
        similarity_matrix: np.ndarray
    ) -> Dict[str, float]:
        """
        分析相似度分布，提取统计特征

        Args:
            similarity_matrix: 相似度矩阵 (NxN)

        Returns:
            分布特征字典
        """
        # 提取上三角矩阵（排除对角线和重复）
        upper_tri = similarity_matrix[np.triu_indices_from(similarity_matrix, k=1)]

        if len(upper_tri) == 0:
            return {
                'mean': 0.0,
                'std': 0.0,
                'median': 0.0,
                'q75': 0.0,
                'q90': 0.0,
                'q95': 0.0,
                'min': 0.0,
                'max': 0.0,
                'skewness': 0.0
            }

        stats = {
            'mean': float(np.mean(upper_tri)),
            'std': float(np.std(upper_tri)),
            'median': float(np.median(upper_tri)),
            'q75': float(np.percentile(upper_tri, 75)),
            'q90': float(np.percentile(upper_tri, 90)),
            'q95': float(np.percentile(upper_tri, 95)),
            'min': float(np.min(upper_tri)),
            'max': float(np.max(upper_tri)),
            # 计算偏度
            'skewness': self._compute_skewness(upper_tri)
        }

        return stats

    def _compute_skewness(self, data: np.ndarray) -> float:
        """计算偏度"""
        if len(data) < 3:
            return 0.0

        mean = np.mean(data)
        std = np.std(data)
        if std == 0:
            return 0.0

        n = len(data)
        skew = np.sum(((data - mean) / std) ** 3) / n
        return float(skew)

    def compute_optimal_thresholds(
        self,
        similarity_matrix: np.ndarray,
        known_pairs: Optional[Dict[Tuple[str, str], bool]] = None
    ) -> ThresholdRecommendation:
        """
        计算最优阈值

        Args:
            similarity_matrix: 相似度矩阵
            known_pairs: 已知的抄袭对 {(id1, id2): is_plagiarism}，可选

        Returns:
            阈值推荐结果
        """
        stats = self.analyze_similarity_distribution(similarity_matrix)

        reasoning = []
        confidence = 0.5

        # 策略1: 基于分布统计
        suspicious = stats['median'] + stats['std']
        high_risk = stats['q75']
        plagiarism = stats['q90']

        reasoning.append(f"基于分布统计: 中位数={stats['median']:.1f}, 标准差={stats['std']:.1f}")

        # 策略2: 基于偏度调整
        if stats['skewness'] > 0.5:
            # 正偏态：大部分相似度低，少数高
            # 降低阈值以捕捉更多可疑对
            adjustment_factor = 0.9
            reasoning.append("检测到正偏态分布，适度降低阈值")
            confidence += 0.1
        elif stats['skewness'] < -0.5:
            # 负偏态：大部分相似度高
            # 提高阈值以减少误判
            adjustment_factor = 1.1
            reasoning.append("检测到负偏态分布，适度提高阈值")
            confidence += 0.1
        else:
            adjustment_factor = 1.0

        # 应用调整
        suspicious *= adjustment_factor
        high_risk *= adjustment_factor
        plagiarism *= adjustment_factor

        # 策略3: 有监督学习（如果提供了已知数据）
        if known_pairs:
            supervised_thresholds = self._compute_thresholds_from_known_pairs(
                similarity_matrix, known_pairs
            )
            # _compute_thresholds_from_known_pairs 在正/负样本任一为空时返回 {}，
            # 此时不能直接取键，否则 KeyError。
            if supervised_thresholds:
                # 加权融合
                suspicious = 0.7 * suspicious + 0.3 * supervised_thresholds['suspicious']
                high_risk = 0.7 * high_risk + 0.3 * supervised_thresholds['high_risk']
                plagiarism = 0.7 * plagiarism + 0.3 * supervised_thresholds['plagiarism']
                reasoning.append("结合历史验证数据调整")
                confidence += 0.2
            else:
                reasoning.append("已知对正/负样本不足，仅使用分布统计")

        # 策略4: 边界检查
        suspicious = np.clip(suspicious, 40, 80)
        high_risk = np.clip(high_risk, 60, 90)
        plagiarism = np.clip(plagiarism, 70, 95)

        # 确保阈值顺序
        suspicious = min(suspicious, high_risk - 5, plagiarism - 10)
        high_risk = min(high_risk, plagiarism - 5)

        confidence = min(confidence, 0.95)

        return ThresholdRecommendation(
            suspicious_threshold=round(suspicious, 1),
            high_risk_threshold=round(high_risk, 1),
            plagiarism_threshold=round(plagiarism, 1),
            confidence=round(confidence, 2),
            reasoning=reasoning
        )

    def _compute_thresholds_from_known_pairs(
        self,
        similarity_matrix: np.ndarray,
        known_pairs: Dict[Tuple[str, str], bool]
    ) -> Dict[str, float]:
        """从已知数据计算最优阈值"""
        # 提取已知对的相似度
        plagiarism_sims = []
        non_plagiarism_sims = []

        for (i, j), is_plag in known_pairs.items():
            # 这里需要ID到索引的映射，简化处理
            sim = similarity_matrix[min(i, j), max(i, j)]  # 假设可以直接索引
            if is_plag:
                plagiarism_sims.append(sim)
            else:
                non_plagiarism_sims.append(sim)

        if not plagiarism_sims or not non_plagiarism_sims:
            return {}

        # 使用Youden指数找最优阈值
        thresholds = np.arange(0, 101, 1)
        best_threshold = 60
        best_jouden = -1

        for t in thresholds:
            tp = sum(1 for s in plagiarism_sims if s >= t)
            fp = sum(1 for s in non_plagiarism_sims if s >= t)
            fn = len(plagiarism_sims) - tp
            tn = len(non_plagiarism_sims) - fp

            sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
            specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
            jouden = sensitivity + specificity - 1

            if jouden > best_jouden:
                best_jouden = jouden
                best_threshold = t

        return {
            'suspicious': best_threshold - 10,
            'high_risk': best_threshold - 5,
            'plagiarism': best_threshold + 5
        }

    def evaluate_risk_level(
        self,
        similarity: float,
        context: Dict
    ) -> RiskAssessment:
        """
        综合评估风险等级

        Args:
            similarity: 相似度 (0-100)
            context: 上下文信息 {
                'is_cross_group': bool,
                'group_info_uncertain': bool,  # 组信息是否不确定
                'semantic_similarity': float,
                'code_similarity': float,
                'structure_similarity': float,
                'shared_paragraphs': int
            }

        Returns:
            风险评估结果
        """
        key_factors = []
        probability = 0.0
        confidence = 0.5

        # 基础风险判定
        if similarity >= 85:
            risk_level = RiskLevel.CRITICAL
            probability = 0.95
            key_factors.append(f"相似度极高({similarity:.1f}%)")
        elif similarity >= 75:
            risk_level = RiskLevel.HIGH
            probability = 0.75
            key_factors.append(f"相似度高({similarity:.1f}%)")
        elif similarity >= 60:
            risk_level = RiskLevel.MEDIUM
            probability = 0.50
            key_factors.append(f"相似度中等({similarity:.1f}%)")
        else:
            risk_level = RiskLevel.LOW
            probability = 0.10
            key_factors.append(f"相似度低({similarity:.1f}%)")

        # 调整因子
        is_cross_group = context.get('is_cross_group', False)
        group_info_uncertain = context.get('group_info_uncertain', False)

        # 跨组检测（包括组信息不确定的情况）
        if is_cross_group and similarity >= 50:
            probability += 0.15
            if group_info_uncertain:
                key_factors.append("组信息缺失但高度相似(需人工复核)")
                confidence -= 0.05  # 降低置信度因为组信息不确定
            else:
                key_factors.append("跨组相似")
            confidence += 0.1

        # 组信息不确定但相似度较高：降低可疑阈值
        if group_info_uncertain and similarity >= 70:
            if not is_cross_group:  # 如果未被标记为跨组，仍然需要关注
                key_factors.append("组信息缺失，相似度较高(需确认是否跨组)")
                probability += 0.1
                confidence -= 0.05

        # 语义相似度检查（改写检测）
        semantic_sim = context.get('semantic_similarity', 0)
        if semantic_sim >= 70 and similarity < 70:
            risk_level = RiskLevel.PARAPHRASE
            probability = max(probability, 0.70)
            key_factors.append(f"语义高度相似但文本不同(可能是改写, 语义{semantic_sim:.1f}%)")
            confidence += 0.15

        # 代码相似度检查
        code_sim = context.get('code_similarity', 0)
        if code_sim >= 85 and similarity < 70:
            probability += 0.20
            key_factors.append(f"代码高度相似({code_sim:.1f}%)")
            confidence += 0.1

        # 结构相似度检查
        structure_sim = context.get('structure_similarity', 0)
        if structure_sim >= 80:
            probability += 0.10
            key_factors.append(f"结构高度相似({structure_sim:.1f}%)")

        # 共享段落数量
        shared_count = context.get('shared_paragraphs', 0)
        if shared_count >= 3:
            probability += 0.10
            key_factors.append(f"共享多个段落({shared_count}个)")

        confidence = min(confidence, 0.95)
        probability = min(probability, 0.98)

        # 建议操作
        if risk_level == RiskLevel.CRITICAL:
            action = "强烈建议人工审核，极大概率抄袭"
        elif risk_level == RiskLevel.HIGH:
            action = "建议人工审核，高度疑似抄袭"
        elif risk_level == RiskLevel.PARAPHRASE:
            action = "检查是否为改写抄袭，建议重点对比"
        elif risk_level == RiskLevel.MEDIUM:
            action = "需要关注，建议查看相似部分"
        else:
            action = "正常范围，无需特别关注"

        return RiskAssessment(
            risk_level=risk_level,
            confidence=round(confidence, 2),
            probability=round(probability, 2),
            key_factors=key_factors,
            recommended_action=action
        )

    def recommend_threshold_for_class(
        self,
        student_count: int,
        historical_similarity_avg: float,
        previous_cases_count: int
    ) -> Dict[str, float]:
        """
        为特定班级推荐阈值

        Args:
            student_count: 学生人数
            historical_similarity_avg: 历史平均相似度
            previous_cases_count: 既往抄袭案例数

        Returns:
            推荐的阈值配置
        """
        # 基于班级规模调整
        if student_count > 100:
            base_threshold = 55.0  # 大班，降低阈值避免漏检
        elif student_count > 50:
            base_threshold = 60.0
        else:
            base_threshold = 65.0  # 小班，提高阈值减少误判

        # 基于历史数据调整
        if historical_similarity_avg > 70:
            # 历史上相似度普遍高，可能实验结构固定
            base_threshold += 5
        elif historical_similarity_avg < 40:
            base_threshold -= 5

        # 基于既往案例调整
        if previous_cases_count > 5:
            # 抄袭案例多，提高警惕
            base_threshold -= 3

        return {
            'suspicious': max(40, base_threshold),
            'high_risk': max(55, base_threshold + 10),
            'plagiarism': max(70, base_threshold + 20)
        }

    def save_analysis_report(
        self,
        stats: Dict,
        recommendation: ThresholdRecommendation,
        output_path: Path
    ):
        """保存分析报告"""
        report = {
            'distribution_stats': stats,
            'recommendation': {
                'suspicious_threshold': recommendation.suspicious_threshold,
                'high_risk_threshold': recommendation.high_risk_threshold,
                'plagiarism_threshold': recommendation.plagiarism_threshold,
                'confidence': recommendation.confidence,
                'reasoning': recommendation.reasoning
            }
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)


# 便捷函数
def auto_detect_thresholds(
    similarity_scores: List[float],
    baseline: float = 60.0
) -> ThresholdRecommendation:
    """
    自动检测最优阈值（便捷函数）

    Args:
        similarity_scores: 相似度分数列表
        baseline: 基准阈值

    Returns:
        阈值推荐
    """
    engine = AdaptiveThresholdEngine(baseline)

    # 构建相似度矩阵
    n = len(similarity_scores)
    if n < 2:
        return ThresholdRecommendation(
            suspicious_threshold=baseline,
            high_risk_threshold=baseline + 10,
            plagiarism_threshold=baseline + 20,
            confidence=0.0,
            reasoning=["数据不足，使用默认阈值"]
        )

    # 从列表构建简单矩阵（实际应用中应该直接传入矩阵）
    # 这里假设 scores 已经是两两比较的结果
    matrix = np.zeros((n, n))
    # 填充上三角
    idx = 0
    for i in range(n):
        for j in range(i + 1, n):
            if idx < len(similarity_scores):
                matrix[i, j] = similarity_scores[idx]
                matrix[j, i] = similarity_scores[idx]
                idx += 1

    return engine.compute_optimal_thresholds(matrix)
