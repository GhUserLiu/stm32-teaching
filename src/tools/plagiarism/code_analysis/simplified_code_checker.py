#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简化版代码质量检查器
Simplified Code Quality Checker for Grading

专为评分系统设计的轻量级代码检查，主要检查：
1. 代码存在性（是否包含关键代码元素）
2. 注释覆盖率
3. 函数数量
4. 命名规范（宏定义检查）
5. 关键HAL函数调用
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


class Severity(Enum):
    """问题严重程度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class CodeIssue:
    """代码问题"""
    severity: Severity
    category: str
    message: str
    line_number: int = 0
    suggestion: str = ""


@dataclass
class CodeCheckResult:
    """代码检查结果"""
    total_score: float  # 0-30分
    max_score: float
    sub_scores: Dict[str, float]  # 各项得分
    issues: List[CodeIssue] = field(default_factory=list)
    passed_checks: List[str] = field(default_factory=list)
    summary: str = ""


class SimplifiedCodeChecker:
    """简化版代码检查器"""

    # STM32 HAL 关键函数/宏模式
    STM32_PATTERNS = {
        'gpio_init': r'HAL_GPIO_Init|GPIO_Init',
        'gpio_read': r'HAL_GPIO_ReadPin|GPIO_ReadPin',
        'gpio_write': r'HAL_GPIO_WritePin|GPIO_WritePin',
        'exti_config': r'EXTI.*Config|NVIC.*Config',
        'interrupt_callback': r'HAL_GPIO_EXTI_Callback|EXTI.*_IRQHandler',
        'dwt_counter': r'DWT->CYCCNT|DWT_CYCCNT',
        'delay': r'HAL_Delay|delay_ms',
    }

    # C语言关键字和函数模式
    C_PATTERNS = {
        'function_def': r'(?:void|int|uint\d+_t|char|float|static)\s+(\w+)\s*\([^)]*\)\s*{',
        'macro_define': r'#define\s+(\w+)\s+',
        'enum': r'enum\s+(\w+)',
        'struct': r'struct\s+(\w+)',
        'switch_case': r'switch\s*\([^)]*\)\s*{',
        'if_else': r'if\s*\([^)]*\)\s*{',
        'while_loop': r'while\s*\([^)]*\)\s*{',
        'for_loop': r'for\s*\([^)]*\)\s*{',
    }

    # 注释模式
    COMMENT_PATTERNS = [
        r'//.*$',           # 单行注释
        r'/\*.*?\*/',       # 块注释
    ]

    def __init__(self):
        """初始化检查器"""
        self.code_blocks = []
        self.raw_text = ""

    def extract_code(self, text: str) -> List[str]:
        """
        从报告中提取代码块

        Args:
            text: 报告文本

        Returns:
            代码块列表
        """
        self.raw_text = text

        # 模式1: Markdown代码块
        code_blocks = re.findall(r'```(?:c|cpp)?\s*(.*?)```', text, re.DOTALL)

        # 模式2: 常见代码片段标记
        inline_patterns = [
            r'代码[：:]\s*\n(.*?)(?=\n\n|\n[一二三四五六七八九十])',
            r'程序[：:]\s*\n(.*?)(?=\n\n|\n[一二三四五六七八九十])',
            r'函数[：:]\s*\n(.*?)(?=\n\n|\n[一二三四五六七八九十])',
        ]

        for pattern in inline_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            code_blocks.extend(matches)

        # 模式3: 提取包含关键函数的段落
        lines = text.split('\n')
        current_block = []
        in_code = False

        for line in lines:
            # 检测是否是代码行
            if any(keyword in line for keyword in ['HAL_GPIO', 'EXTI', 'DWT', 'GPIO->', '#define', 'void ', 'uint8_t']):
                if not in_code:
                    in_code = True
                    current_block = []
                current_block.append(line)
            elif in_code:
                # 检查是否继续
                if line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                    in_code = False
                    if current_block:
                        code_blocks.append('\n'.join(current_block))
                else:
                    current_block.append(line)

        if current_block:
            code_blocks.append('\n'.join(current_block))

        self.code_blocks = code_blocks
        return code_blocks

    def check_code_presence(self, required_elements: List[str]) -> Tuple[float, List[CodeIssue]]:
        """
        检查代码存在性（8分）

        Args:
            required_elements: 必需的代码元素列表

        Returns:
            (得分, 问题列表)
        """
        issues = []
        found_elements = set()

        all_code = '\n'.join(self.code_blocks)

        for element in required_elements:
            if element.lower() in all_code.lower():
                found_elements.add(element)
            else:
                issues.append(CodeIssue(
                    severity=Severity.WARNING,
                    category="code_presence",
                    message=f"代码中未找到必需元素: {element}"
                ))

        score = (len(found_elements) / len(required_elements)) * 8 if required_elements else 8
        return score, issues

    def check_comment_ratio(self, min_ratio: float = 0.15, min_absolute: int = 5) -> Tuple[float, List[CodeIssue]]:
        """
        检查注释覆盖率（8分）

        Args:
            min_ratio: 最小注释比例
            min_absolute: 最少注释行数

        Returns:
            (得分, 问题列表)
        """
        issues = []

        all_code = '\n'.join(self.code_blocks)
        lines = all_code.split('\n')

        code_lines = [l for l in lines if l.strip() and not re.match(r'^\s*//', l.strip())]
        comment_lines = [l for l in lines if re.match(r'\s*//', l.strip())]

        ratio = len(comment_lines) / len(code_lines) if code_lines else 0

        if len(comment_lines) < min_absolute:
            issues.append(CodeIssue(
                severity=Severity.INFO,
                category="comment",
                message=f"注释数量偏少: {len(comment_lines)}行 (建议至少{min_absolute}行)"
            ))

        if ratio < min_ratio:
            issues.append(CodeIssue(
                severity=Severity.WARNING,
                category="comment",
                message=f"注释比例偏低: {ratio*100:.1f}% (建议至少{min_ratio*100:.0f}%)"
            ))

        # 评分：比例和数量各占一半
        ratio_score = min(4, (ratio / min_ratio) * 4) if min_ratio > 0 else 4
        count_score = min(4, (len(comment_lines) / min_absolute) * 4) if min_absolute > 0 else 4
        score = ratio_score + count_score

        return score, issues

    def check_function_count(self, min_functions: int = 3) -> Tuple[float, List[CodeIssue]]:
        """
        检查函数数量（4分）

        Args:
            min_functions: 最少函数数量

        Returns:
            (得分, 问题列表)
        """
        issues = []

        all_code = '\n'.join(self.code_blocks)

        # 查找函数定义
        functions = re.findall(self.C_PATTERNS['function_def'], all_code)
        functions.extend(re.findall(r'EXTI.*_IRQHandler', all_code))  # 中断处理函数

        function_count = len(set(functions))  # 去重

        if function_count < min_functions:
            issues.append(CodeIssue(
                severity=Severity.INFO,
                category="modularity",
                message=f"函数数量偏少: {function_count}个 (建议至少{min_functions}个)",
                suggestion="建议将代码拆分为多个函数，提高模块化程度"
            ))

        score = min(4, (function_count / min_functions) * 4) if min_functions > 0 else 4
        return score, issues

    def check_naming_convention(self, check_macros: bool = True) -> Tuple[float, List[CodeIssue]]:
        """
        检查命名规范（4分）

        Args:
            check_macros: 是否检查宏定义命名

        Returns:
            (得分, 问题列表)
        """
        issues = []

        all_code = '\n'.join(self.code_blocks)

        score = 4.0  # 默认满分

        # 检查宏定义命名（应该全大写）
        if check_macros:
            macros = re.findall(self.C_PATTERNS['macro_define'], all_code)
            bad_macros = [m for m in macros if m != m.upper() and '_' not in m]

            if bad_macros:
                issues.append(CodeIssue(
                    severity=Severity.INFO,
                    category="naming",
                    message=f"部分宏定义可能不符合命名规范: {', '.join(bad_macros[:3])}",
                    suggestion="宏定义建议使用全大写加下划线，如: MAX_VALUE"
                ))
                score -= 1.0

        # 检查函数命名（应该小写加下划线或驼峰）
        functions = re.findall(self.C_PATTERNS['function_def'], all_code)
        very_short = [f for f in functions if len(f) < 3]

        if very_short:
            issues.append(CodeIssue(
                severity=Severity.INFO,
                category="naming",
                message=f"部分函数名过短: {', '.join(very_short[:3])}",
                suggestion="函数名应该具有描述性，建议使用有意义的名称"
            ))
            score -= 0.5

        return max(0, score), issues

    def check_stm32_hal_usage(self) -> Tuple[float, List[CodeIssue]]:
        """
        检查STM32 HAL库使用（6分）

        Returns:
            (得分, 问题列表)
        """
        issues = []

        all_code = '\n'.join(self.code_blocks)

        score = 0.0
        total_checks = len(self.STM32_PATTERNS)
        found_checks = 0

        for category, pattern in self.STM32_PATTERNS.items():
            if re.search(pattern, all_code):
                found_checks += 1
            else:
                issues.append(CodeIssue(
                    severity=Severity.INFO,
                    category="stm32_hal",
                    message=f"代码中未找到: {category}"
                ))

        score = (found_checks / total_checks) * 6 if total_checks > 0 else 0

        return score, issues

    def run_full_check(
        self,
        config: Dict = None
    ) -> CodeCheckResult:
        """
        执行完整检查

        Args:
            config: 配置字典
                {
                    'code_presence': {'required_elements': [...]},
                    'comments': {'min_ratio': 0.15, 'min_absolute': 5},
                    'modularity': {'min_functions': 3},
                    'naming': {'check_macros': True}
                }

        Returns:
            检查结果
        """
        if config is None:
            config = self._get_default_config()

        result = CodeCheckResult(
            total_score=0.0,
            max_score=30.0,
            sub_scores={},
            issues=[],
            passed_checks=[],
            summary=""
        )

        if not self.code_blocks:
            result.total_score = 0
            result.summary = "未检测到代码内容"
            result.issues.append(CodeIssue(
                severity=Severity.CRITICAL,
                category="code_presence",
                message="报告中未找到代码内容"
            ))
            return result

        # 1. 代码存在性检查（8分）
        code_cfg = config.get('code_presence', {})
        code_score, code_issues = self.check_code_presence(
            code_cfg.get('required_elements', ['GPIO', 'HAL_GPIO', '中断'])
        )
        result.sub_scores['code_presence'] = code_score
        result.issues.extend(code_issues)
        if code_score >= 6:
            result.passed_checks.append("代码完整性")

        # 2. 注释检查（8分）
        comment_cfg = config.get('comments', {})
        comment_score, comment_issues = self.check_comment_ratio(
            comment_cfg.get('min_ratio', 0.15),
            comment_cfg.get('min_absolute', 5)
        )
        result.sub_scores['comments'] = comment_score
        result.issues.extend(comment_issues)
        if comment_score >= 6:
            result.passed_checks.append("注释质量")

        # 3. 模块化检查（4分）
        mod_cfg = config.get('modularity', {})
        mod_score, mod_issues = self.check_function_count(
            mod_cfg.get('min_functions', 3)
        )
        result.sub_scores['modularity'] = mod_score
        result.issues.extend(mod_issues)

        # 4. 命名规范检查（4分）
        naming_cfg = config.get('naming', {})
        naming_score, naming_issues = self.check_naming_convention(
            naming_cfg.get('check_macros', True)
        )
        result.sub_scores['naming'] = naming_score
        result.issues.extend(naming_issues)

        # 5. STM32 HAL使用检查（6分）
        hal_score, hal_issues = self.check_stm32_hal_usage()
        result.sub_scores['stm32_hal'] = hal_score
        result.issues.extend(hal_issues)
        if hal_score >= 4:
            result.passed_checks.append("HAL库使用")

        # 计算总分
        result.total_score = sum(result.sub_scores.values())

        # 生成总结
        result.summary = self._generate_summary(result)

        return result

    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'code_presence': {
                'required_elements': ['GPIO', 'HAL_GPIO', '中断']
            },
            'comments': {
                'min_ratio': 0.15,
                'min_absolute': 5
            },
            'modularity': {
                'min_functions': 3
            },
            'naming': {
                'check_macros': True
            }
        }

    def _generate_summary(self, result: CodeCheckResult) -> str:
        """生成检查总结"""
        lines = [
            f"代码质量得分: {result.total_score:.1f}/{result.max_score}",
            f"通过项目: {', '.join(result.passed_checks) if result.passed_checks else '无'}",
        ]

        # 按严重程度统计问题
        critical = sum(1 for i in result.issues if i.severity == Severity.CRITICAL)
        errors = sum(1 for i in result.issues if i.severity == Severity.ERROR)
        warnings = sum(1 for i in result.issues if i.severity == Severity.WARNING)

        if critical > 0:
            lines.append(f"严重问题: {critical}个")
        if errors > 0:
            lines.append(f"错误: {errors}个")
        if warnings > 0:
            lines.append(f"警告: {warnings}个")

        return '\n'.join(lines)


def check_code_from_report(
    text: str,
    config: Dict = None
) -> CodeCheckResult:
    """
    从报告文本中检查代码质量

    Args:
        text: 报告文本
        config: 检查配置

    Returns:
        检查结果
    """
    checker = SimplifiedCodeChecker()
    checker.extract_code(text)
    return checker.run_full_check(config)
