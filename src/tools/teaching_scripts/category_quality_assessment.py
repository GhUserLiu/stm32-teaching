#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基于 Rubric 类别的质量评估模块
Category-Based Quality Assessment Module

每个质量维度直接对应一个 rubric 类别，提供深度质量分析
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class CategoryQualityResult:
    """单个类别的质量评估结果"""
    category_id: str
    category_name: str
    quality_score: float           # 0-100 质量分
    max_points: int                # 该类别满分
    quality_issues: List[str] = field(default_factory=list)
    quality_strengths: List[str] = field(default_factory=list)
    depth_indicators: Dict[str, bool] = field(default_factory=dict)


class CategoryQualityAssessor:
    """类别质量评估器"""

    def __init__(self, rubric: Dict):
        """
        初始化评估器

        Args:
            rubric: rubric 数据字典
        """
        self.rubric = rubric
        self.categories = {cat['id']: cat for cat in rubric.get('categories', [])}

    def assess_category_quality(
        self,
        text: str,
        category_id: str,
        category: Dict
    ) -> CategoryQualityResult:
        """
        评估单个类别的质量

        Args:
            text: 报告文本
            category_id: 类别ID
            category: 类别数据

        Returns:
            CategoryQualityResult
        """
        assessor_map = {
            'team_collaboration': self._assess_team_collaboration,
            'principle_understanding': self._assess_principle_understanding,
            'completion': self._assess_completion,
            'code_quality': self._assess_code_quality,
            'report_quality': self._assess_report_quality,
        }

        assessor = assessor_map.get(category_id, self._assess_generic)
        return assessor(text, category)

    def calculate_overall_quality(
        self,
        category_qualities: Dict[str, CategoryQualityResult]
    ) -> float:
        """
        计算加权整体质量分

        Args:
            category_qualities: 各类别质量评估结果

        Returns:
            整体质量分 (0-100)
        """
        if not category_qualities:
            return 0.0

        # 按类别满分加权平均
        total_weight = 0
        weighted_score = 0

        for cat_id, quality in category_qualities.items():
            weight = quality.max_points
            weighted_score += quality.quality_score * weight
            total_weight += weight

        return weighted_score / total_weight if total_weight > 0 else 0

    # ========== 各类别质量评估方法 ==========

    def _assess_team_collaboration(
        self,
        text: str,
        category: Dict
    ) -> CategoryQualityResult:
        """评估团队协作质量 (5分)"""
        issues = []
        strengths = []
        indicators = {}

        # 1. 成员信息深度
        member_section = self._extract_section_by_keywords(
            text, ['成员', '团队', '小组', '学号', '姓名']
        )
        has_student_id = bool(re.search(r'\d{11,12}', member_section))
        has_roles = bool(re.search(r'(负责|承担|担任|分工)', member_section))
        has_multiple_members = len(re.findall(r'(成员|组员)', member_section)) >= 2

        if has_student_id and has_roles and has_multiple_members:
            strengths.append("成员信息完整，包含学号和角色分工")
            indicators['member_info'] = True
        elif has_roles and has_multiple_members:
            strengths.append("成员信息较完整，缺少学号")
            indicators['member_info'] = True
        else:
            issues.append("成员信息不完整，应包含学号、姓名、角色")
            indicators['member_info'] = False

        # 2. 分工具体性
        collaboration_section = self._extract_section_by_keywords(
            text, ['分工', '协作', '任务', '职责']
        )
        division_detail = len(collaboration_section) > 50  # 超过50字
        has_specific_tasks = bool(re.search(
            r'(负责|承担|担任|主要|协作).{10,}',
            collaboration_section
        ))

        if division_detail and has_specific_tasks:
            strengths.append("分工描述详细具体")
            indicators['division_detail'] = True
        elif has_specific_tasks:
            strengths.append("有分工描述但可以更详细")
            indicators['division_detail'] = True
        else:
            issues.append("分工描述过于简单，应说明具体任务")
            indicators['division_detail'] = False

        # 3. 协作过程证据
        has_collaboration_record = bool(re.search(
            r'(讨论|会议|交流|配合|协作|共同).{15,}',
            text
        ))
        if has_collaboration_record:
            strengths.append("有协作过程记录")
            indicators['collaboration_evidence'] = True
        else:
            issues.append("缺少协作过程记录")
            indicators['collaboration_evidence'] = False

        # 计算质量分
        quality_score = self._calculate_category_score(
            indicators, ['member_info', 'division_detail', 'collaboration_evidence']
        )

        return CategoryQualityResult(
            category_id='team_collaboration',
            category_name='团队协作',
            quality_score=quality_score,
            max_points=category['points'],
            quality_issues=issues,
            quality_strengths=strengths,
            depth_indicators=indicators
        )

    def _assess_principle_understanding(
        self,
        text: str,
        category: Dict
    ) -> CategoryQualityResult:
        """评估原理理解质量 (10分)"""
        issues = []
        strengths = []
        indicators = {}

        # 1. 目的清晰度
        purpose_section = self._extract_section_by_keywords(
            text, ['实验目的', '目的', '目标']
        )
        purpose_complete = len(purpose_section) > 30  # 超过30字
        has_objectives = bool(re.search(
            r'(掌握|学习|了解|理解|实现).{10,}',
            purpose_section
        ))

        if purpose_complete and has_objectives:
            strengths.append("实验目的阐述清晰完整")
            indicators['purpose_clarity'] = True
        else:
            issues.append("实验目的阐述不够完整")
            indicators['purpose_clarity'] = False

        # 2. 原理深度
        principle_section = self._extract_section_by_keywords(
            text, ['实验原理', '原理', '基本原理']
        )
        # 检查是否解释了"为什么"
        has_explanation = bool(re.search(
            r'(原理|因为|由于|原因|机制).{20,}',
            principle_section
        ))
        # 检查关键技术点
        has_key_technical = bool(re.search(
            r'(外部中断|EXTI|DWT|消抖|状态机|GPIO).{10,}',
            principle_section
        ))

        if has_explanation and has_key_technical:
            strengths.append("原理阐述深入，有关键技术点说明")
            indicators['principle_depth'] = True
        elif has_key_technical:
            strengths.append("有关键技术点但原理阐述可更深入")
            indicators['principle_depth'] = True
        else:
            issues.append("原理阐述不够深入，缺少关键技术点说明")
            indicators['principle_depth'] = False

        # 3. 应用场景
        has_application = bool(re.search(
            r'(汽车|TCU|ECU|档位传感器|变速器|应用|场景).{15,}',
            text
        ))
        if has_application:
            strengths.append("联系了汽车电子应用场景")
            indicators['application_scenario'] = True
        else:
            issues.append("缺少汽车电子应用场景说明")
            indicators['application_scenario'] = False

        quality_score = self._calculate_category_score(
            indicators, ['purpose_clarity', 'principle_depth', 'application_scenario']
        )

        return CategoryQualityResult(
            category_id='principle_understanding',
            category_name='实验原理与认知',
            quality_score=quality_score,
            max_points=category['points'],
            quality_issues=issues,
            quality_strengths=strengths,
            depth_indicators=indicators
        )

    def _assess_completion(
        self,
        text: str,
        category: Dict
    ) -> CategoryQualityResult:
        """评估完成度质量 (35分)"""
        issues = []
        strengths = []
        indicators = {}

        # 1. 硬件图质量
        hardware_section = self._extract_section_by_keywords(
            text, ['硬件', '连接', '接线', '电路', '三、']
        )
        has_diagram = bool(re.search(
            r'(连接图|接线图|硬件图|电路图|原理图)',
            hardware_section
        ))
        diagram_clear = has_diagram and len(hardware_section) > 100

        if diagram_clear:
            strengths.append("硬件连接图清晰完整")
            indicators['hardware_diagram'] = True
        elif has_diagram:
            strengths.append("有硬件图但说明可更详细")
            indicators['hardware_diagram'] = True
        else:
            issues.append("缺少或硬件连接图不清晰")
            indicators['hardware_diagram'] = False

        # 2. 引脚说明完整性
        has_pe4 = 'PE4' in text
        has_pf9 = 'PF9' in text
        has_pf10 = 'PF10' in text
        pins_complete = has_pe4 and has_pf9 and has_pf10

        # 检查引脚功能说明
        has_pin_function = bool(re.search(
            r'(PE4.*按键|KEY0|PF9.*LED|PF10.*LED|引脚.*功能)',
            text
        ))

        if pins_complete and has_pin_function:
            strengths.append("引脚配置说明完整，包含功能描述")
            indicators['pin_config'] = True
        elif pins_complete:
            strengths.append("引脚说明完整")
            indicators['pin_config'] = True
        else:
            missing_pins = []
            if not has_pe4:
                missing_pins.append('PE4')
            if not has_pf9:
                missing_pins.append('PF9')
            if not has_pf10:
                missing_pins.append('PF10')
            issues.append(f"引脚说明不完整，缺少: {', '.join(missing_pins)}")
            indicators['pin_config'] = False

        # 3. 实验结果详细性
        result_section = self._extract_section_by_keywords(
            text, ['实验结果', '测试', '现象', '五、']
        )
        result_detail = len(result_section) > 80
        has_led_states = bool(re.search(
            r'(LED.*状态|档位|P.*R.*N.*D|亮|灭)',
            result_section
        ))

        if result_detail and has_led_states:
            strengths.append("实验结果记录详细")
            indicators['result_detail'] = True
        elif has_led_states:
            strengths.append("有实验结果记录")
            indicators['result_detail'] = True
        else:
            issues.append("实验结果记录不够详细")
            indicators['result_detail'] = False

        # 4. 结果分析深度
        has_analysis = bool(re.search(
            r'(结果分析|对比|预期|差异|符合|一致).{20,}',
            result_section
        ))
        if has_analysis:
            strengths.append("有结果对比分析")
            indicators['result_analysis'] = True
        else:
            issues.append("缺少结果对比分析")
            indicators['result_analysis'] = False

        # 5. 照片/截图
        has_photo = bool(re.search(
            r'(照片|截图|图片|图.*实验|实物)',
            result_section
        ))
        if has_photo:
            strengths.append("配有实验照片或截图")
            indicators['has_photo'] = True
        else:
            issues.append("缺少实验照片或截图")
            indicators['has_photo'] = False

        quality_score = self._calculate_category_score(
            indicators,
            ['hardware_diagram', 'pin_config', 'result_detail', 'result_analysis', 'has_photo']
        )

        return CategoryQualityResult(
            category_id='completion',
            category_name='实验完成度',
            quality_score=quality_score,
            max_points=category['points'],
            quality_issues=issues,
            quality_strengths=strengths,
            depth_indicators=indicators
        )

    def _assess_code_quality(
        self,
        text: str,
        category: Dict
    ) -> CategoryQualityResult:
        """评估代码质量深度 (30分)"""
        issues = []
        strengths = []
        indicators = {}

        # 1. 流程图逻辑性
        code_section = self._extract_section_by_keywords(
            text, ['软件', '代码', '程序', '四、']
        )
        has_flowchart = bool(re.search(
            r'(流程图|程序流程|框图)',
            code_section
        ))
        # 检查流程图是否完整（有开始和结束）
        flowchart_complete = has_flowchart and bool(re.search(
            r'(开始|结束|Start|End|初始化)',
            code_section
        ))

        if flowchart_complete:
            strengths.append("代码流程图完整清晰")
            indicators['flowchart'] = True
        elif has_flowchart:
            strengths.append("有流程图")
            indicators['flowchart'] = True
        else:
            issues.append("缺少代码流程图")
            indicators['flowchart'] = False

        # 2. 代码完整性
        has_enum = 'enum' in text or 'typedef enum' in text
        has_switch = 'switch' in text
        has_gpio = 'GPIO' in text
        has_hal = 'HAL_' in text

        code_elements = sum([has_enum, has_switch, has_gpio, has_hal])
        if code_elements >= 3:
            strengths.append("关键代码展示完整")
            indicators['code_completeness'] = True
        elif code_elements >= 2:
            strengths.append("有关键代码展示")
            indicators['code_completeness'] = True
        else:
            issues.append("关键代码展示不完整")
            indicators['code_completeness'] = False

        # 3. 注释密度
        # 提取代码块
        code_blocks = re.findall(r'```.*?```', text, re.DOTALL)
        all_code = ' '.join(code_blocks)
        if all_code:
            # 计算注释行占比
            code_lines = all_code.split('\n')
            comment_lines = [l for l in code_lines if re.match(r'^\s*//|^\s*\*', l)]
            comment_ratio = len(comment_lines) / len(code_lines) if code_lines else 0

            if comment_ratio >= 0.15:
                strengths.append(f"代码注释充分（{comment_ratio*100:.0f}%）")
                indicators['comment_density'] = True
            elif comment_ratio >= 0.05:
                strengths.append(f"有代码注释（{comment_ratio*100:.0f}%）")
                indicators['comment_density'] = True
            else:
                issues.append("代码注释不足")
                indicators['comment_density'] = False
        else:
            issues.append("缺少代码块或代码注释")
            indicators['comment_density'] = False

        # 4. 中断说明
        has_interrupt_desc = bool(re.search(
            r'(中断|EXTI|回调|Callback|消抖).{20,}',
            text
        ))
        if has_interrupt_desc:
            strengths.append("中断服务程序说明详细")
            indicators['interrupt_desc'] = True
        else:
            issues.append("中断服务程序说明不足")
            indicators['interrupt_desc'] = False

        quality_score = self._calculate_category_score(
            indicators,
            ['flowchart', 'code_completeness', 'comment_density', 'interrupt_desc']
        )

        return CategoryQualityResult(
            category_id='code_quality',
            category_name='代码质量',
            quality_score=quality_score,
            max_points=category['points'],
            quality_issues=issues,
            quality_strengths=strengths,
            depth_indicators=indicators
        )

    def _assess_report_quality(
        self,
        text: str,
        category: Dict
    ) -> CategoryQualityResult:
        """评估报告质量深度 (10分)"""
        issues = []
        strengths = []
        indicators = {}

        # 1. 问题真实性
        problem_section = self._extract_section_by_keywords(
            text, ['问题', '调试', '讨论', '六、']
        )
        # 检查是否有具体问题（不是通用套话）
        has_specific_problem = bool(re.search(
            r'(编译|错误|bug|异常|问题|不通|不亮).{15,}',
            problem_section
        ))
        # 检查是否有解决过程
        has_solution = bool(re.search(
            r'(解决|修改|调整|排查|检查).{15,}',
            problem_section
        ))

        if has_specific_problem and has_solution:
            strengths.append("调试问题记录真实具体，有解决过程")
            indicators['problem_authenticity'] = True
        elif has_specific_problem:
            strengths.append("有调试问题记录")
            indicators['problem_authenticity'] = True
        else:
            issues.append("调试问题记录不够具体或缺少解决过程")
            indicators['problem_authenticity'] = False

        # 2. 团队协作证据
        has_collaboration = bool(re.search(
            r'(讨论|协作|团队|配合|共同).{15,}',
            problem_section
        ))
        if has_collaboration:
            strengths.append("有团队协作解决问题的记录")
            indicators['team_collaboration'] = True
        else:
            issues.append("缺少团队协作解决问题的记录")
            indicators['team_collaboration'] = False

        # 3. 心得独立性
        reflection_section = self._extract_section_by_keywords(
            text, ['心得', '体会', '总结', '收获', '感悟']
        )
        # 检查是否过于通用
        generic_phrases = [
            '学到了很多', '收获很大', '提高能力', '认真完成',
            '加深了理解', '掌握了知识'
        ]
        is_generic = any(phrase in reflection_section for phrase in generic_phrases)
        has_specific_reflection = len(reflection_section) > 50 and not is_generic

        if has_specific_reflection:
            strengths.append("个人心得具体深刻")
            indicators['reflection_independence'] = True
        elif len(reflection_section) > 20:
            strengths.append("有个人心得")
            indicators['reflection_independence'] = True
        else:
            issues.append("个人心得过于简单或通用")
            indicators['reflection_independence'] = False

        # 4. 思考题完整性
        thinking_section = self._extract_section_by_keywords(
            text, ['思考题', '问题', '七、']
        )
        # 统计思考题数量 (Q1-Q7 或 问题1-7)
        question_count = len(re.findall(
            r'[Qq][1-7]|问题[1-7]|[一二三四五六七]、',
            thinking_section
        ))
        if question_count >= 7:
            strengths.append("思考题回答完整")
            indicators['thinking_completeness'] = True
        elif question_count >= 4:
            strengths.append(f"思考题回答{question_count}题")
            indicators['thinking_completeness'] = True
        else:
            issues.append(f"思考题回答不完整（{question_count}/7）")
            indicators['thinking_completeness'] = False

        quality_score = self._calculate_category_score(
            indicators,
            ['problem_authenticity', 'team_collaboration',
             'reflection_independence', 'thinking_completeness']
        )

        return CategoryQualityResult(
            category_id='report_quality',
            category_name='实验报告质量',
            quality_score=quality_score,
            max_points=category['points'],
            quality_issues=issues,
            quality_strengths=strengths,
            depth_indicators=indicators
        )

    def _assess_generic(
        self,
        text: str,
        category: Dict
    ) -> CategoryQualityResult:
        """通用评估方法（用于未定义的类别）"""
        return CategoryQualityResult(
            category_id=category.get('id', 'unknown'),
            category_name=category.get('name', 'Unknown'),
            quality_score=70.0,  # 默认中等质量
            max_points=category.get('points', 0),
            quality_issues=[],
            quality_strengths=["使用默认评估"],
            depth_indicators={}
        )

    # ========== 辅助方法 ==========

    def _extract_section_by_keywords(
        self,
        text: str,
        keywords: List[str]
    ) -> str:
        """
        根据关键词提取相关章节内容

        Args:
            text: 完整文本
            keywords: 关键词列表

        Returns:
            相关章节内容
        """
        lines = text.split('\n')
        result_lines = []

        for line in lines:
            if any(keyword in line for keyword in keywords):
                # 找到匹配行，收集前后几行
                result_lines.append(line)

        return '\n'.join(result_lines)

    def _calculate_category_score(
        self,
        indicators: Dict[str, bool],
        indicator_keys: List[str]
    ) -> float:
        """
        根据指标计算类别质量分

        Args:
            indicators: 指标字典
            indicator_keys: 需要计算的指标键列表

        Returns:
            质量分 (0-100)
        """
        if not indicator_keys:
            return 70.0

        scores = []
        for key in indicator_keys:
            if indicators.get(key, False):
                scores.append(100)
            else:
                scores.append(40)  # 缺失指标给40分

        return sum(scores) / len(scores)


def assess_category_quality(
    extracted_data: List[Dict],
    rubric_path: Path
) -> Dict[str, Dict]:
    """
    批量评估所有报告的类别质量

    Args:
        extracted_data: 提取的内容列表
        rubric_path: rubric 文件路径

    Returns:
        {学号: 质量评估结果}
    """
    # 加载 rubric
    with open(rubric_path, 'r', encoding='utf-8') as f:
        rubric = json.load(f)

    # 创建评估器
    assessor = CategoryQualityAssessor(rubric)

    quality_scores = {}

    for item in extracted_data:
        student_id = item['student_id']

        if item.get('missing'):
            quality_scores[student_id] = {
                'category_qualities': {},
                'overall_quality': 0.0,
                'issues': ['未提交报告']
            }
            continue

        text = item.get('full_text', '')

        # 评估每个类别
        category_qualities = {}
        for category in rubric.get('categories', []):
            if category.get('manual_evaluation'):
                continue  # 跳过手工评定项

            cat_id = category['id']
            quality = assessor.assess_category_quality(text, cat_id, category)
            category_qualities[cat_id] = {
                'category_id': quality.category_id,
                'category_name': quality.category_name,
                'quality_score': quality.quality_score,
                'max_points': quality.max_points,
                'quality_issues': quality.quality_issues,
                'quality_strengths': quality.quality_strengths,
                'depth_indicators': quality.depth_indicators
            }

        # 计算整体质量
        overall_quality = assessor.calculate_overall_quality(
            {k: CategoryQualityResult(**v) for k, v in category_qualities.items()}
        )

        quality_scores[student_id] = {
            'category_qualities': category_qualities,
            'overall_quality': overall_quality
        }

    return quality_scores


# 导出
__all__ = [
    'CategoryQualityResult',
    'CategoryQualityAssessor',
    'assess_category_quality'
]
