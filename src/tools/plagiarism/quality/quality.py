"""
增强质量评估模块
Enhanced Quality Assessment Module

提供多维度报告质量评估和AI辅助评分
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from enum import Enum


class QualityDimension(Enum):
    """质量维度"""
    CONTENT_COMPLETENESS = 'content_completeness'    # 内容完整性
    TECHNICAL_ACCURACY = 'technical_accuracy'       # 技术准确性
    WRITING_QUALITY = 'writing_quality'             # 写作质量
    CODE_QUALITY = 'code_quality'                   # 代码质量
    ORIGINALITY = 'originality'                     # 原创性
    DEPTH_OF_ANALYSIS = 'depth_of_analysis'         # 分析深度


@dataclass
class QualityScore:
    """质量得分"""
    dimension: QualityDimension
    score: float  # 0-100
    max_score: float
    details: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)


@dataclass
class AssessmentResult:
    """评估结果"""
    student_id: str
    name: str
    overall_score: float  # 0-100
    grade: str
    dimension_scores: Dict[QualityDimension, QualityScore]
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    plagiarism_risk: float = 0.0  # 0-1
    ai_confidence: float = 0.0   # AI评估置信度


class TechnicalValidator:
    """技术内容验证器"""

    # 常见技术错误模式
    ERROR_PATTERNS = {
        'gpio_config': [
            (r'GPIO.*MODE.*OUTPUT', 'GPIO输出配置'),
            (r'HAL_GPIO_Init', 'GPIO初始化'),
        ],
        'interrupt': [
            (r'EXTI.*IRQHandler', '外部中断处理'),
            (r'HAL_GPIO_EXTI_Callback', 'GPIO回调函数'),
        ],
        'debounce': [
            (r'DWT.*CYCCNT', 'DWT计数器'),
            (r'__HAL_ATOMIC', '原子操作'),
        ],
        'state_machine': [
            (r'[PRND].*状态', '状态机状态'),
            (r'switch.*case', 'switch-case结构'),
        ]
    }

    # 技术要点检查
    TECHNICAL_CHECKS = {
        '档位实验': [
            (r'PE4.*下降沿', 'PE4下降沿触发', 10),
            (r'PF9.*LED', 'PF9 LED配置', 10),
            (r'PF10.*LED', 'PF10 LED配置', 10),
            (r'P.*R.*N.*D', '档位状态机', 15),
            (r'DWT.*消抖', 'DWT消抖实现', 15),
            (r'EXTI.*中断', '外部中断配置', 10),
            (r'NVIC.*优先级', '中断优先级设置', 10),
            (r'测试|验证|现象', '测试验证', 10),
        ],
        '转向灯实验': [
            (r'GPIO.*输出', 'GPIO输出配置', 15),
            (r'延时|delay', '延时控制', 15),
            (r'左转|右转|紧急', '转向灯模式', 20),
            (r'闪烁|频率', '闪烁频率', 15),
            (r'测试|现象', '测试验证', 15),
        ]
    }

    @classmethod
    def validate_technical_content(
        cls,
        text: str,
        experiment_type: str = '档位实验'
    ) -> Tuple[float, List[str], List[str]]:
        """
        验证技术内容

        Args:
            text: 报告文本
            experiment_type: 实验类型

        Returns:
            (得分, 问题列表, 亮点列表)
        """
        checks = cls.TECHNICAL_CHECKS.get(experiment_type, cls.TECHNICAL_CHECKS['档位实验'])

        score = 0.0
        max_score = sum(points for _, _, points in checks)
        issues = []
        strengths = []

        for pattern, name, points in checks:
            if re.search(pattern, text, re.IGNORECASE):
                score += points
                strengths.append(f"技术要点正确: {name}")
            else:
                issues.append(f"缺少或错误: {name}")

        # 归一化到0-100
        normalized_score = (score / max_score * 100) if max_score > 0 else 0

        return normalized_score, issues, strengths


class ContentAnalyzer:
    """内容分析器"""

    # 分析深度指标
    DEPTH_INDICATORS = {
        'high': [
            (r'原理[是为因].{20,}', '原理阐述详细'),
            (r'实现.{20,}(方式|方法|过程)', '实现描述详细'),
            (r'问题.{20,}(解决|处理|分析)', '问题分析深入'),
            (r'(心得|体会|收获).{20,}', '有深度思考'),
            (r'优化|改进|提升', '有优化建议'),
        ],
        'medium': [
            (r'原理', '提及原理'),
            (r'实现', '提及实现'),
            (r'测试', '提及测试'),
        ]
    }

    # 章节完整性检查
    SECTION_CHECKS = [
        (r'实验目的', '实验目的'),
        (r'实验原理|设计思路', '实验原理'),
        (r'硬件.*连接|接线|电路', '硬件连接'),
        (r'软件.*设计|程序|代码', '软件设计'),
        (r'测试|结果|现象', '测试结果'),
        (r'问题.*讨论|心得|体会', '问题讨论'),
        (r'总结|结论', '总结'),
    ]

    @classmethod
    def analyze_depth(cls, text: str) -> float:
        """
        分析内容深度

        Args:
            text: 报告文本

        Returns:
            深度得分 (0-100)
        """
        score = 0.0

        # 检查高级指标
        for pattern, desc in cls.DEPTH_INDICATORS['high']:
            if re.search(pattern, text, re.DOTALL):
                score += 15

        # 检查中级指标
        for pattern, desc in cls.DEPTH_INDICATORS['medium']:
            if re.search(pattern, text):
                score += 5

        # 检查字数（合理的字数范围）
        char_count = len(re.sub(r'\s', '', text))
        if 1000 <= char_count <= 5000:
            score += 10
        elif char_count > 5000:
            score += 5

        return min(score, 100)

    @classmethod
    def check_completeness(cls, text: str) -> Tuple[float, List[str]]:
        """
        检查内容完整性

        Args:
            text: 报告文本

        Returns:
            (完整性得分, 缺失章节列表)
        """
        score = 0.0
        missing = []
        max_score = len(cls.SECTION_CHECKS) * (100 / len(cls.SECTION_CHECKS))

        for pattern, name in cls.SECTION_CHECKS:
            if re.search(pattern, text):
                score += max_score
            else:
                missing.append(name)

        return min(score, 100), missing


class WritingQualityAssessor:
    """写作质量评估器"""

    @classmethod
    def assess(cls, text: str) -> Tuple[float, List[str]]:
        """
        评估写作质量

        Args:
            text: 报告文本

        Returns:
            (写作质量得分, 问题列表)
        """
        score = 60.0  # 基础分
        issues = []

        # 检查结构
        section_count = len(re.findall(r'[一二三四五六七八九十]+[、．.]\s*\w+', text))
        if section_count >= 5:
            score += 15
        elif section_count >= 3:
            score += 10
        else:
            issues.append('报告结构不完整，缺少章节划分')
            score -= 10

        # 检查代码格式
        if '```' in text or '~~~' in text:
            score += 10
        else:
            code_blocks = len(re.findall(r'void\s+\w+|HAL_|GPIO_', text))
            if code_blocks >= 3:
                score += 5
            else:
                issues.append('代码格式不规范，建议使用代码块')

        # 检查图表引用
        if re.search(r'图.*\d+|表.*\d+', text):
            score += 5

        # 检查排版（空行使用）
        paragraphs = re.split(r'\n\n+', text)
        if len(paragraphs) >= 5:
            score += 5
        else:
            issues.append('排版紧凑，建议增加空行分隔段落')

        # 检查标题层级
        heading_levels = set(re.findall(r'^(#{1,3})|\[([一二三四]+)\]', text, re.MULTILINE))
        if len(heading_levels) >= 2:
            score += 5

        return min(max(score, 0), 100), issues


class CodeQualityAssessor:
    """代码质量评估器"""

    @classmethod
    def assess(cls, text: str) -> Tuple[float, List[str]]:
        """
        评估代码质量

        Args:
            text: 包含代码的报告文本

        Returns:
            (代码质量得分, 问题列表)
        """
        score = 0.0
        issues = []
        strengths = []

        # 提取代码块
        code_blocks = re.findall(r'```.*?```', text, re.DOTALL)
        if not code_blocks:
            # 尝试其他方式提取
            code_blocks = re.findall(
                r'(void\s+\w+[^{]*{.*?}|HAL_GPIO_[^;]+;|GPIO_Init[^;]+;)',
                text, re.DOTALL
            )

        if not code_blocks:
            return 0.0, ['未检测到代码']

        all_code = '\n'.join(code_blocks)

        # 检查注释
        comment_ratio = 0.0
        if code_blocks:
            comment_lines = 0
            total_lines = 0

            for block in code_blocks:
                lines = block.split('\n')
                for line in lines:
                    if line.strip():
                        total_lines += 1
                        if re.match(r'^\s*//|^\s*\*', line.strip()):
                            comment_lines += 1

            if total_lines > 0:
                comment_ratio = comment_lines / total_lines

        if comment_ratio >= 0.2:
            score += 20
            strengths.append('代码注释充分')
        elif comment_ratio >= 0.1:
            score += 10
        else:
            issues.append('代码注释不足，建议添加说明')

        # 检查函数命名规范
        if re.search(r'[a-z_]+_[a-z_]+\([^)]*\)', all_code):
            score += 15
            strengths.append('函数命名符合规范')
        else:
            issues.append('建议使用规范的小写+下划线命名')

        # 检查错误处理
        if re.search(r'if.*\(.*\)|HAL.*Error', all_code):
            score += 15
            strengths.append('有错误处理逻辑')

        # 检查关键配置
        key_configs = [
            ('GPIO.*MODE', 'GPIO模式配置'),
            ('GPIO.*PULL', 'GPIO上下拉配置'),
            ('EXTI.*LINE', '外部中断线配置'),
            ('NVIC.*Priority', '中断优先级配置'),
        ]

        for pattern, name in key_configs:
            if re.search(pattern, all_code):
                score += 10
                strengths.append(f'关键配置完整: {name}')
            else:
                issues.append(f'可能缺少: {name}')

        return min(score, 100), issues


class EnhancedQualityAssessor:
    """增强质量评估器"""

    def __init__(self, experiment_type: str = '档位实验'):
        """
        初始化评估器

        Args:
            experiment_type: 实验类型
        """
        self.experiment_type = experiment_type
        self.technical_validator = TechnicalValidator()
        self.content_analyzer = ContentAnalyzer()
        self.writing_assessor = WritingQualityAssessor()
        self.code_assessor = CodeQualityAssessor()

    def assess(
        self,
        student_id: str,
        name: str,
        text: str,
        plagiarism_data: Optional[Dict] = None
    ) -> AssessmentResult:
        """
        综合评估报告质量

        Args:
            student_id: 学号
            name: 姓名
            text: 报告文本
            plagiarism_data: 抄袭数据

        Returns:
            评估结果
        """
        dimension_scores = {}

        # 1. 技术准确性
        tech_score, tech_issues, tech_strengths = self.technical_validator.validate_technical_content(
            text, self.experiment_type
        )
        dimension_scores[QualityDimension.TECHNICAL_ACCURACY] = QualityScore(
            dimension=QualityDimension.TECHNICAL_ACCURACY,
            score=tech_score,
            max_score=100,
            details=tech_issues,
            strengths=tech_strengths
        )

        # 2. 内容完整性
        complete_score, missing_sections = self.content_analyzer.check_completeness(text)
        dimension_scores[QualityDimension.CONTENT_COMPLETENESS] = QualityScore(
            dimension=QualityDimension.CONTENT_COMPLETENESS,
            score=complete_score,
            max_score=100,
            details=[f'缺少章节: {", ".join(missing_sections)}'] if missing_sections else [],
            suggestions=['请补充缺失的章节'] if missing_sections else []
        )

        # 3. 分析深度
        depth_score = self.content_analyzer.analyze_depth(text)
        dimension_scores[QualityDimension.DEPTH_OF_ANALYSIS] = QualityScore(
            dimension=QualityDimension.DEPTH_OF_ANALYSIS,
            score=depth_score,
            max_score=100
        )

        # 4. 写作质量
        write_score, write_issues = self.writing_assessor.assess(text)
        dimension_scores[QualityDimension.WRITING_QUALITY] = QualityScore(
            dimension=QualityDimension.WRITING_QUALITY,
            score=write_score,
            max_score=100,
            details=write_issues
        )

        # 5. 代码质量
        code_score, code_issues = self.code_assessor.assess(text)
        dimension_scores[QualityDimension.CODE_QUALITY] = QualityScore(
            dimension=QualityDimension.CODE_QUALITY,
            score=code_score,
            max_score=100,
            details=code_issues
        )

        # 6. 原创性（基于抄袭检测）
        originality_score = 100.0
        plagiarism_risk = 0.0

        if plagiarism_data and student_id in plagiarism_data:
            similar_items = plagiarism_data[student_id]
            if similar_items:
                max_sim = max(item.get('weighted', item.get('overall', 0))
                             for item in similar_items)
                originality_score = max(0, 100 - max_sim)
                plagiarism_risk = max_sim / 100

        dimension_scores[QualityDimension.ORIGINALITY] = QualityScore(
            dimension=QualityDimension.ORIGINALITY,
            score=originality_score,
            max_score=100,
            details=[f'抄袭风险: {plagiarism_risk*100:.1f}%'] if plagiarism_risk > 0.5 else []
        )

        # 计算总分（加权平均）
        weights = {
            QualityDimension.TECHNICAL_ACCURACY: 0.30,
            QualityDimension.CONTENT_COMPLETENESS: 0.25,
            QualityDimension.DEPTH_OF_ANALYSIS: 0.15,
            QualityDimension.WRITING_QUALITY: 0.10,
            QualityDimension.CODE_QUALITY: 0.10,
            QualityDimension.ORIGINALITY: 0.10,
        }

        overall_score = sum(
            dimension_scores[dim].score * weights[dim]
            for dim in QualityDimension
        )

        # 确定等级
        if overall_score >= 90:
            grade = 'A'
        elif overall_score >= 80:
            grade = 'B'
        elif overall_score >= 70:
            grade = 'C'
        elif overall_score >= 60:
            grade = 'D'
        else:
            grade = 'F'

        # 收集所有问题
        all_issues = []
        all_recommendations = []

        for dim_score in dimension_scores.values():
            all_issues.extend(dim_score.details)
            all_recommendations.extend(dim_score.suggestions)

        # AI 置信度（基于评估完整性）
        ai_confidence = 0.85  # 默认置信度

        return AssessmentResult(
            student_id=student_id,
            name=name,
            overall_score=round(overall_score, 1),
            grade=grade,
            dimension_scores=dimension_scores,
            issues=all_issues,
            recommendations=all_recommendations,
            plagiarism_risk=plagiarism_risk,
            ai_confidence=ai_confidence
        )


def batch_assess(
    submissions: Dict[str, Dict],
    experiment_type: str = '档位实验',
    plagiarism_data: Optional[Dict] = None
) -> List[AssessmentResult]:
    """
    批量评估报告

    Args:
        submissions: 提交内容 {学号: {name, text}}
        experiment_type: 实验类型
        plagiarism_data: 抄袭数据

    Returns:
        评估结果列表
    """
    assessor = EnhancedQualityAssessor(experiment_type)

    results = []

    for student_id, submission in submissions.items():
        name = submission.get('name', '')
        text = submission.get('text', '')

        if not text:
            # 未提交
            results.append(AssessmentResult(
                student_id=student_id,
                name=name,
                overall_score=0.0,
                grade='F',
                dimension_scores={},
                issues=['未提交报告'],
                recommendations=['请尽快提交实验报告']
            ))
            continue

        result = assessor.assess(student_id, name, text, plagiarism_data)
        results.append(result)

    return results
