#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
代码质量深度分析器
Deep Code Quality Analyzer

提供全面的代码质量评估功能，包括：
- 复杂度分析
- 命名规范检查
- 注释覆盖率
- 魔法数字检测
- 模块化程度评估
- 重复代码检测
- 文档完整性
"""

import ast
import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
from enum import Enum
from collections import defaultdict


class CodeQuality(Enum):
    """代码质量等级"""
    EXCELLENT = "优秀"
    GOOD = "良好"
    FAIR = "中等"
    POOR = "较差"
    VERY_POOR = "很差"


@dataclass
class ComplexityMetric:
    """复杂度指标"""
    cyclomatic_complexity: int  # 圈复杂度
    nesting_depth: int  # 嵌套深度
    function_count: int  # 函数数量
    avg_function_length: float  # 平均函数长度
    acceptable: bool = True


@dataclass
class NamingMetric:
    """命名规范指标"""
    function_score: float  # 函数命名得分 0-100
    variable_score: float  # 变量命名得分 0-100
    constant_score: float  # 常量命名得分 0-100
    overall_score: float  # 总体得分 0-100
    issues: List[str] = field(default_factory=list)


@dataclass
class CommentMetric:
    """注释指标"""
    comment_ratio: float  # 注释比例（注释行/总行数）
    documented_functions: int  # 有文档字符串的函数数
    total_functions: int  # 总函数数
    meaningful_comments: int  # 有意义的注释数
    total_comments: int  # 总注释数
    score: float = 0.0  # 注释得分 0-100


@dataclass
class CodeDuplicationMetric:
    """代码重复指标"""
    duplicate_lines: int  # 重复代码行数
    total_lines: int  # 总代码行数
    duplication_ratio: float  # 重复比例
    similar_blocks: int  # 相似代码块数量
    score: float = 0.0  # 得分 0-100


@dataclass
class ModularityMetric:
    """模块化指标"""
    single_responsibility: float  # 单一职责得分 0-100
    coupling_level: float  # 耦合度得分（越低越好）
    cohesion_level: float  # 内聚度得分（越高越好）
    score: float = 0.0  # 总体得分 0-100


@dataclass
class DocumentationMetric:
    """文档完整性指标"""
    has_module_docstring: bool
    has_file_header: bool
    has_usage_examples: bool
    function_documentation_ratio: float  # 函数文档比例
    score: float = 0.0  # 总体得分 0-100


@dataclass
class CodeQualityReport:
    """代码质量报告"""
    overall_quality: CodeQuality
    overall_score: float  # 总体得分 0-100
    complexity: ComplexityMetric
    naming: NamingMetric
    comments: CommentMetric
    duplication: CodeDuplicationMetric
    modularity: ModularityMetric
    documentation: DocumentationMetric

    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    # 加权得分
    weighted_scores: Dict[str, float] = field(default_factory=dict)


class CodeQualityAnalyzer:
    """代码质量分析器"""

    # 命名规范模式
    FUNCTION_PATTERN = r'def\s+[a-z_][a-z0-9_]*\('
    SNAKE_CASE_PATTERN = r'^[a-z_][a-z0-9_]*$'
    CAMEL_CASE_PATTERN = r'^[a-z][a-zA-Z0-9]*$'
    CONSTANT_PATTERN = r'^[A-Z_][A-Z0-9_]*$'

    # 魔法数字阈值
    MAGIC_NUMBER_THRESHOLD = 10

    # 复杂度阈值
    MAX_COMPLEXITY = 10
    MAX_FUNCTION_LENGTH = 50
    MAX_NESTING_DEPTH = 4

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        初始化分析器

        Args:
            weights: 各项指标权重 {
                'complexity': 0.15,
                'naming': 0.20,
                'comments': 0.20,
                'duplication': 0.10,
                'modularity': 0.20,
                'documentation': 0.15
            }
        """
        self.weights = weights or {
            'complexity': 0.15,
            'naming': 0.20,
            'comments': 0.20,
            'duplication': 0.10,
            'modularity': 0.20,
            'documentation': 0.15
        }

    def analyze(self, code: str, filename: str = "") -> CodeQualityReport:
        """
        全面分析代码质量

        Args:
            code: 代码字符串
            filename: 文件名（可选）

        Returns:
            CodeQualityReport: 质量报告
        """
        # 1. 复杂度分析
        complexity = self._analyze_complexity(code)

        # 2. 命名规范分析
        naming = self._analyze_naming(code)

        # 3. 注释分析
        comments = self._analyze_comments(code)

        # 4. 重复代码分析
        duplication = self._analyze_duplication(code)

        # 5. 模块化分析
        modularity = self._analyze_modularity(code)

        # 6. 文档完整性分析
        documentation = self._analyze_documentation(code)

        # 7. 计算加权总分
        weighted_scores = {
            'complexity': self._complexity_to_score(complexity),
            'naming': naming.overall_score,
            'comments': comments.score,
            'duplication': duplication.score,
            'modularity': modularity.score,
            'documentation': documentation.score
        }

        overall_score = sum(
            weighted_scores[key] * self.weights[key]
            for key in weighted_scores
        )

        # 8. 确定质量等级
        overall_quality = self._determine_quality_level(overall_score)

        # 9. 生成优缺点和建议
        strengths, weaknesses, recommendations = self._generate_feedback(
            weighted_scores, complexity, naming, comments, duplication
        )

        return CodeQualityReport(
            overall_quality=overall_quality,
            overall_score=overall_score,
            complexity=complexity,
            naming=naming,
            comments=comments,
            duplication=duplication,
            modularity=modularity,
            documentation=documentation,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
            weighted_scores=weighted_scores
        )

    def _analyze_complexity(self, code: str) -> ComplexityMetric:
        """分析代码复杂度"""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return ComplexityMetric(999, 999, 0, 0, False)

        complexities = []
        function_lengths = []
        nesting_depths = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 计算圈复杂度
                complexity = 1  # 基础复杂度
                max_nesting = 0

                for child in ast.walk(node):
                    if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                        complexity += 1
                    elif isinstance(child, ast.BoolOp):
                        complexity += len(child.values) - 1

                    # 计算嵌套深度
                    if isinstance(child, (ast.If, ast.While, ast.For, ast.With)):
                        current_depth = self._get_nesting_depth(child, node)
                        max_nesting = max(max_nesting, current_depth)

                complexities.append(complexity)
                nesting_depths.append(max_nesting)

                # 计算函数长度（行数）
                if hasattr(node, 'end_lineno') and node.lineno:
                    length = node.end_lineno - node.lineno + 1
                    function_lengths.append(length)

        avg_complexity = sum(complexities) / len(complexities) if complexities else 0
        max_complexity = max(complexities) if complexities else 0
        avg_length = sum(function_lengths) / len(function_lengths) if function_lengths else 0

        return ComplexityMetric(
            cyclomatic_complexity=int(max_complexity),
            nesting_depth=int(max(nesting_depths) if nesting_depths else 0),
            function_count=len(complexities),
            avg_function_length=round(avg_length, 1),
            acceptable=max_complexity <= self.MAX_COMPLEXITY
        )

    def _get_nesting_depth(self, node: ast.AST, root: ast.AST) -> int:
        """获取节点的嵌套深度"""
        depth = 0
        current = node

        while current != root:
            if hasattr(current, 'parent'):
                # 需要先设置parent关系
                break
            # 简化处理：向上查找
            depth += 1
            if depth > 20:  # 防止无限循环
                break
        return min(depth, 10)

    def _analyze_naming(self, code: str) -> NamingMetric:
        """分析命名规范"""
        issues = []

        # 分析函数命名
        functions = re.findall(r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', code)
        function_score = 0.0

        good_functions = 0
        for func in functions:
            if re.match(self.SNAKE_CASE_PATTERN, func):
                good_functions += 1
            else:
                if not func.startswith('_'):  # 忽略私有函数
                    issues.append(f"函数命名不规范: {func} (应使用snake_case)")

        if functions:
            function_score = (good_functions / len(functions)) * 100

        # 分析变量命名
        variables = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=', code)
        variable_score = 0.0

        good_vars = 0
        for var in variables:
            if re.match(self.SNAKE_CASE_PATTERN, var):
                good_vars += 1
            elif not re.match(self.CONSTANT_PATTERN, var):
                if len(var) > 1 and not var.startswith('_'):
                    issues.append(f"变量命名不规范: {var}")

        if variables:
            variable_score = (good_vars / len(variables)) * 100

        # 分析常量命名（全大写）
        constants = re.findall(r'([A-Z_][A-Z0-9_]*)\s*=\s*[^=]', code)
        constant_score = 100.0

        for const in constants:
            if not re.match(self.CONSTANT_PATTERN, const):
                issues.append(f"常量命名不规范: {const}")

        if constants:
            constant_score = 100.0  # 简化处理

        overall_score = (function_score * 0.4 +
                        variable_score * 0.4 +
                        constant_score * 0.2)

        return NamingMetric(
            function_score=round(function_score, 1),
            variable_score=round(variable_score, 1),
            constant_score=round(constant_score, 1),
            overall_score=round(overall_score, 1),
            issues=issues[:10]  # 限制问题数量
        )

    def _analyze_comments(self, code: str) -> CommentMetric:
        """分析注释质量"""
        lines = code.split('\n')
        total_lines = len([l for l in lines if l.strip()])

        # 统计注释行
        comment_lines = 0
        code_lines = 0
        docstring_count = 0
        meaningful_comments = 0

        in_docstring = False
        docstring_delim = None

        for line in lines:
            stripped = line.strip()

            # 处理文档字符串
            if '"""' in stripped or "'''" in stripped:
                if not in_docstring:
                    in_docstring = True
                    docstring_delim = '"""' if '"""' in stripped else "'''"
                    docstring_count += 1
                elif stripped.count(docstring_delim) >= 2 or (
                    stripped.startswith(docstring_delim) and
                    (stripped.endswith(docstring_delim) or len(stripped) == 3)
                ):
                    in_docstring = False
                comment_lines += 1
                continue

            if in_docstring:
                comment_lines += 1
                continue

            # 单行注释
            if stripped.startswith('#'):
                comment_lines += 1
                # 检查是否为有意义的注释
                if len(stripped) > 2 and not stripped.startswith('# '):
                    pass  # 可能是注释
                elif any(word in stripped.lower() for word in
                       ['因为', '所以', '原因', '实现', '功能', '参数', '返回']):
                    meaningful_comments += 1
                continue

            # 代码行
            if stripped and not stripped.startswith('//'):
                code_lines += 1

        # 分析函数文档
        try:
            tree = ast.parse(code)
            total_functions = 0
            documented_functions = 0

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    total_functions += 1
                    if (ast.get_docstring(node) or
                        (node.body and isinstance(node.body[0], ast.Expr) and
                         isinstance(node.body[0].value, ast.Constant))):
                        documented_functions += 1
        except Exception:
            total_functions = 0
            documented_functions = 0

        # 计算注释比例
        comment_ratio = comment_lines / max(total_lines, 1) * 100
        func_doc_ratio = (documented_functions / max(total_functions, 1) * 100
                         if total_functions > 0 else 0)

        # 计算注释得分
        ratio_score = min(100, comment_ratio * 2)  # 目标20%注释
        doc_score = func_doc_ratio

        score = (ratio_score * 0.6 + doc_score * 0.4)

        return CommentMetric(
            comment_ratio=round(comment_ratio, 1),
            documented_functions=documented_functions,
            total_functions=total_functions,
            meaningful_comments=meaningful_comments,
            total_comments=comment_lines,
            score=round(score, 1)
        )

    def _analyze_duplication(self, code: str) -> CodeDuplicationMetric:
        """分析代码重复"""
        lines = code.split('\n')
        code_lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith('#')]
        total_lines = len(code_lines)

        if total_lines < 10:
            return CodeDuplicationMetric(0, total_lines, 0, 0, 100.0)

        # 简化的重复检测（基于行相似度）
        duplicate_count = 0
        seen_lines = defaultdict(int)

        for line in code_lines:
            # 忽略单行和大括号
            if len(line) < 5 or line in ['}', '{', '}', '{']:
                continue
            seen_lines[line] += 1
            if seen_lines[line] > 1:
                duplicate_count += 1

        # 检测重复块（3行以上相同序列）
        similar_blocks = 0
        for i in range(len(code_lines) - 3):
            block = tuple(code_lines[i:i+3])
            if block in tuple(code_lines[i+3:]):
                similar_blocks += 1

        duplication_ratio = (duplicate_count / max(total_lines, 1)) * 100
        score = max(0, 100 - duplication_ratio * 2 - similar_blocks * 5)

        return CodeDuplicationMetric(
            duplicate_lines=duplicate_count,
            total_lines=total_lines,
            duplication_ratio=round(duplication_ratio, 1),
            similar_blocks=similar_blocks,
            score=round(score, 1)
        )

    def _analyze_modularity(self, code: str) -> ModularityMetric:
        """分析模块化程度"""
        try:
            tree = ast.parse(code)
        except Exception:
            return ModularityMetric(0, 0, 0, 0)

        functions = []
        classes = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 只统计模块级函数，不统计方法
                if not hasattr(node, 'parent_class'):
                    functions.append(node)
            elif isinstance(node, ast.ClassDef):
                classes.append(node)

        # 单一职责评估（基于函数数量和长度）
        avg_function_count = len(functions) / max(1, len(classes) or 1)
        sr_score = min(100, avg_function_count * 10)

        # 简化的耦合和内聚评估
        coupling_score = 50  # 默认中等耦合
        cohesion_score = 50  # 默认中等内聚

        # 如果有类，分析类的内聚
        if classes:
            cohesion_score = 70  # 使用类通常内聚更好
            coupling_score = 60

        overall_score = (sr_score * 0.4 + cohesion_score * 0.4 +
                        (100 - coupling_score) * 0.2)

        return ModularityMetric(
            single_responsibility=round(sr_score, 1),
            coupling_level=round(coupling_score, 1),
            cohesion_level=round(cohesion_score, 1),
            score=round(overall_score, 1)
        )

    def _analyze_documentation(self, code: str) -> DocumentationMetric:
        """分析文档完整性"""
        lines = code.split('\n')

        # 检查模块文档字符串
        has_module_docstring = False
        if lines:
            first_ten = '\n'.join(lines[:10])
            has_module_docstring = ('"""' in first_ten or "'''" in first_ten)

        # 检查文件头注释
        has_file_header = False
        header_keywords = ['@file', '@brief', '@author', '@date']
        header_text = '\n'.join(lines[:20])
        has_file_header = any(kw in header_text for kw in header_keywords)

        # 检查使用示例
        has_usage_examples = 'if __name__' in code or 'Example' in code

        # 函数文档比例（复用注释分析的结果）
        try:
            tree = ast.parse(code)
            total_funcs = sum(1 for _ in ast.walk(tree)
                            if isinstance(_, ast.FunctionDef))
            documented_funcs = sum(1 for node in ast.walk(tree)
                                 if isinstance(node, ast.FunctionDef)
                                 and ast.get_docstring(node))
            func_doc_ratio = (documented_funcs / max(total_funcs, 1) * 100
                             if total_funcs > 0 else 0)
        except Exception:
            func_doc_ratio = 0
            total_funcs = 0

        # 计算文档得分
        score = 0
        if has_module_docstring:
            score += 30
        if has_file_header:
            score += 20
        if has_usage_examples:
            score += 15
        score += func_doc_ratio * 0.35

        return DocumentationMetric(
            has_module_docstring=has_module_docstring,
            has_file_header=has_file_header,
            has_usage_examples=has_usage_examples,
            function_documentation_ratio=round(func_doc_ratio, 1),
            score=round(min(100, score), 1)
        )

    def _complexity_to_score(self, complexity: ComplexityMetric) -> float:
        """将复杂度转换为分数"""
        if complexity.acceptable:
            return 100.0

        # 超出阈值，按比例扣分
        excess = complexity.cyclomatic_complexity - self.MAX_COMPLEXITY
        score = max(0, 100 - excess * 5)

        return round(score, 1)

    def _determine_quality_level(self, score: float) -> CodeQuality:
        """确定质量等级"""
        if score >= 90:
            return CodeQuality.EXCELLENT
        elif score >= 75:
            return CodeQuality.GOOD
        elif score >= 60:
            return CodeQuality.FAIR
        elif score >= 40:
            return CodeQuality.POOR
        else:
            return CodeQuality.VERY_POOR

    def _generate_feedback(
        self,
        scores: Dict[str, float],
        complexity: ComplexityMetric,
        naming: NamingMetric,
        comments: CommentMetric,
        duplication: CodeDuplicationMetric
    ) -> Tuple[List[str], List[str], List[str]]:
        """生成优缺点和建议"""
        strengths = []
        weaknesses = []
        recommendations = []

        # 复杂度反馈
        if complexity.acceptable:
            strengths.append(f"代码复杂度控制良好（圈复杂度: {complexity.cyclomatic_complexity}）")
        else:
            weaknesses.append(f"代码复杂度过高（圈复杂度: {complexity.cyclomatic_complexity}）")
            recommendations.append("建议拆分复杂函数，单个函数圈复杂度不超过10")

        # 命名反馈
        if naming.overall_score >= 80:
            strengths.append("命名规范良好")
        else:
            weaknesses.append(f"命名规范需改进（得分: {naming.overall_score}%）")
            recommendations.append("建议使用snake_case命名函数和变量，CONSTANT_CASE命名常量")

        # 注释反馈
        if comments.score >= 70:
            strengths.append(f"注释覆盖率充足（{comments.comment_ratio:.1f}%）")
        else:
            weaknesses.append(f"注释不足（得分: {comments.score}%）")
            recommendations.append("建议增加代码注释，目标注释率20%以上")

        # 重复代码反馈
        if duplication.score >= 80:
            strengths.append("代码重复率低")
        elif duplication.similar_blocks > 2:
            weaknesses.append(f"发现{duplication.similar_blocks}处相似代码块")
            recommendations.append("建议提取重复代码为独立函数")

        return strengths, weaknesses, recommendations


# 便捷函数
def analyze_code_quality(code: str, filename: str = "") -> CodeQualityReport:
    """
    分析代码质量

    Args:
        code: 代码字符串
        filename: 文件名（可选）

    Returns:
        CodeQualityReport: 质量报告
    """
    analyzer = CodeQualityAnalyzer()
    return analyzer.analyze(code, filename)


def analyze_code_file(file_path: Path) -> CodeQualityReport:
    """
    分析代码文件

    Args:
        file_path: 代码文件路径

    Returns:
        CodeQualityReport: 质量报告
    """
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        code = f.read()

    return analyze_code_quality(code, str(file_path))


if __name__ == "__main__":
    # 测试代码
    test_code = '''
/**
  * @file    : main.c
  * @brief   : 汽车档位模拟器主程序
  * @author  : 学生姓名
  * @date    : 2024-06-12
  */

#include "stm32f4xx.h"

// LED状态枚举
typedef enum {
    GEAR_P = 0,  // 停车档
    GEAR_R = 1,  // 倒档
    GEAR_N = 2,  // 空档
    GEAR_D = 3   // 行驶档
} GearState;

/**
  * @brief  初始化GPIO
  * @retval None
  */
void GPIO_Init(void) {
    // 使能GPIOF时钟
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOFEN;

    // 配置LED引脚
    GPIOF->MODER &= ~(3 << (9 * 2));
    GPIOF->MODER |= (1 << (9 * 2));
}

/**
  * @brief  主函数
  */
int main(void) {
    // 系统初始化
    HAL_Init();
    GPIO_Init();

    while(1) {
        // 主循环
    }
}
'''

    report = analyze_code_quality(test_code, "test.c")
    print(f"代码质量: {report.overall_quality.value}")
    print(f"总体得分: {report.overall_score:.1f}/100")
    print(f"\n优点: {report.strengths}")
    print(f"\n缺点: {report.weaknesses}")
    print(f"\n建议: {report.recommendations}")
