#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强代码深度分析器
Enhanced Code Quality Analyzer

提供全面的代码质量分析，包括：
- 语法正确性检查
- 代码复杂度评估
- 命名规范检查
- 最佳实践验证
- 安全隐患检测
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum


class Severity(Enum):
    """问题严重程度"""
    CRITICAL = "critical"    # 严重错误，必须修复
    HIGH = "high"           # 高优先级，强烈建议修复
    MEDIUM = "medium"       # 中等优先级，建议修复
    LOW = "low"             # 低优先级，可以优化
    INFO = "info"           # 信息提示


@dataclass
class CodeIssue:
    """代码问题"""
    severity: Severity
    category: str          # 问题类别
    message: str          # 问题描述
    line_number: int = 0  # 行号（如果有）
    suggestion: str = ""  # 修复建议
    code_snippet: str = "" # 相关代码片段


@dataclass
class FunctionMetrics:
    """函数度量指标"""
    name: str
    start_line: int
    end_line: int
    lines_of_code: int           # 代码行数
    cyclomatic_complexity: int   # 圈复杂度
    parameter_count: int         # 参数个数
    has_return: bool             # 是否有返回值
    comment_ratio: float         # 注释比例


@dataclass
class CodeAnalysisResult:
    """代码分析结果"""
    total_score: float          # 总分 0-100
    max_score: float
    issues: List[CodeIssue]     # 问题列表
    metrics: Dict[str, any]     # 度量指标
    strengths: List[str]        # 亮点
    function_details: List[FunctionMetrics]  # 函数详情


class CStyleParser:
    """C语言代码解析器"""

    # 函数定义模式
    FUNCTION_PATTERN = re.compile(
        r'(?:^|\n)\s*(?:static\s+)?(?:inline\s+)?(?:\w+\s+)+(\w+)\s*\(([^)]*)\)\s*\{',
        re.MULTILINE
    )

    # HAL函数模式
    HAL_FUNCTION_PATTERN = re.compile(r'HAL_[A-Z_][A-Z0-9_]*\s*\(')

    # GPIO配置模式
    GPIO_CONFIG_PATTERN = re.compile(
        r'GPIO\s*->\s*(MODE|PUPDR|OSPEED|AFR)[HL]\s*=\s*\w+|'
        r'GPIO_Init.*?GPIO_InitTypeDef'
    )

    # 中断相关模式
    INTERRUPT_PATTERN = re.compile(
        r'EXTI.*IRQHandler|HAL_GPIO_EXTI_Callback|NVIC.*Priority'
    )

    # DWT相关模式
    DWT_PATTERN = re.compile(
        r'DWT->CYCCNT|CoreDebug->DEMCR|DWT_CTRL|CYCCNT'
    )

    @staticmethod
    def extract_functions(code: str) -> List[Dict]:
        """提取函数定义"""
        functions = []

        for match in CStyleParser.FUNCTION_PATTERN.finditer(code):
            func_name = match.group(1)
            params = match.group(2)

            # 计算参数个数
            param_count = 0
            if params.strip():
                param_count = len([p.strip() for p in params.split(',') if p.strip()])

            # 找到函数结束位置
            start_pos = match.start()
            brace_count = 0
            in_function = False
            end_pos = start_pos

            for i, char in enumerate(code[start_pos:], start=start_pos):
                if char == '{':
                    brace_count += 1
                    in_function = True
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and in_function:
                        end_pos = i
                        break

            # 计算函数行数
            start_line = code[:start_pos].count('\n') + 1
            end_line = code[:end_pos].count('\n') + 1
            func_code = code[start_pos:end_pos]

            # 计算圈复杂度（简化版）
            complexity = 1
            complexity += len(re.findall(r'\bif\b', func_code))
            complexity += len(re.findall(r'\belse\b', func_code))
            complexity += len(re.findall(r'\bfor\b', func_code))
            complexity += len(re.findall(r'\bwhile\b', func_code))
            complexity += len(re.findall(r'\bswitch\b', func_code))
            complexity += len(re.findall(r'\bcase\b', func_code))
            complexity += len(re.findall(r'\?\s*:', func_code))

            functions.append({
                'name': func_name,
                'params': params,
                'param_count': param_count,
                'start_line': start_line,
                'end_line': end_line,
                'code': func_code,
                'complexity': complexity
            })

        return functions

    @staticmethod
    def extract_comments(code: str) -> Tuple[List[str], List[str]]:
        """提取单行和多行注释"""
        # 单行注释
        single_line = re.findall(r'//(.*)', code)

        # 多行注释
        multi_line = re.findall(r'/\*(.*?)\*/', code, re.DOTALL)

        return single_line, multi_line


class NamingConventionChecker:
    """命名规范检查器"""

    @staticmethod
    def check_function_names(functions: List[Dict]) -> List[CodeIssue]:
        """检查函数命名规范"""
        issues = []

        # 函数命名规范：小写字母+下划线
        # 允许：hal_gpio_init, my_function_name
        # 不允许：MyFunction, MY_FUNCTION
        invalid_pattern = re.compile(r'[A-Z]{2,}|[^a-z0-9_]')
        camel_case = re.compile(r'[a-z][A-Z]')

        for func in functions:
            name = func['name']

            # HAL函数可以全大写
            if name.startswith('HAL_') or name.startswith('EXTI'):
                continue

            if camel_case.search(name):
                issues.append(CodeIssue(
                    severity=Severity.MEDIUM,
                    category="命名规范",
                    message=f"函数名 '{name}' 使用了驼峰命名",
                    suggestion="建议使用小写+下划线命名，如 'my_function_name'",
                    line_number=func['start_line']
                ))

            # 检查是否过短
            if len(name) < 3:
                issues.append(CodeIssue(
                    severity=Severity.LOW,
                    category="命名规范",
                    message=f"函数名 '{name}' 过短，缺乏描述性",
                    suggestion="建议使用更具描述性的函数名",
                    line_number=func['start_line']
                ))

        return issues

    @staticmethod
    def check_variable_names(code: str) -> List[CodeIssue]:
        """检查变量命名"""
        issues = []

        # 单字母变量（除循环变量外）
        single_letter_vars = re.findall(r'\b(int|char|float|double)\s+([a-z])\b', code)
        for type_, var in single_letter_vars:
            if var not in ['i', 'j', 'k', 'x', 'y', 'n', 'p']:  # 常用循环变量
                issues.append(CodeIssue(
                    severity=Severity.LOW,
                    category="命名规范",
                    message=f"变量名 '{var}' 过短",
                    suggestion="建议使用更具描述性的变量名"
                ))

        # 匈牙利命名法（不推荐）
        hungarian = re.findall(r'\b(?:p|n|l|f|sz|dw)[A-Z]\w*', code)
        if hungarian:
            issues.append(CodeIssue(
                severity=Severity.INFO,
                category="命名规范",
                message="检测到可能的匈牙利命名法",
                suggestion="现代C代码推荐使用描述性命名而非匈牙利命名法"
            ))

        return issues


class ComplexityAnalyzer:
    """复杂度分析器"""

    @staticmethod
    def analyze_complexity(functions: List[Dict]) -> Tuple[List[CodeIssue], List[FunctionMetrics]]:
        """分析函数复杂度"""
        issues = []
        metrics = []

        for func in functions:
            # 计算代码行数
            func_code = func['code']
            code_lines = [l for l in func_code.split('\n') if l.strip() and not l.strip().startswith('//')]

            # 计算注释比例
            comment_lines = len([l for l in code_lines if l.strip().startswith('*')])
            loc = len(code_lines) - comment_lines
            comment_ratio = comment_lines / len(code_lines) if code_lines else 0

            # 检查圈复杂度
            complexity = func['complexity']
            if complexity > 15:
                issues.append(CodeIssue(
                    severity=Severity.HIGH,
                    category="复杂度",
                    message=f"函数 '{func['name']}' 圈复杂度过高 ({complexity})",
                    suggestion="建议将函数拆分为更小的函数",
                    line_number=func['start_line']
                ))
            elif complexity > 10:
                issues.append(CodeIssue(
                    severity=Severity.MEDIUM,
                    category="复杂度",
                    message=f"函数 '{func['name']}' 圈复杂度偏高 ({complexity})",
                    suggestion="考虑重构以降低复杂度",
                    line_number=func['start_line']
                ))

            # 检查函数长度
            if loc > 50:
                issues.append(CodeIssue(
                    severity=Severity.HIGH,
                    category="复杂度",
                    message=f"函数 '{func['name']}' 过长 ({loc} 行代码)",
                    suggestion="建议将长函数拆分为多个小函数（建议每函数不超过30行）",
                    line_number=func['start_line']
                ))
            elif loc > 30:
                issues.append(CodeIssue(
                    severity=Severity.MEDIUM,
                    category="复杂度",
                    message=f"函数 '{func['name']}' 较长 ({loc} 行代码)",
                    suggestion="考虑拆分以提高可读性",
                    line_number=func['start_line']
                ))

            # 检查参数个数
            param_count = func['param_count']
            if param_count > 5:
                issues.append(CodeIssue(
                    severity=Severity.HIGH,
                    category="复杂度",
                    message=f"函数 '{func['name']}' 参数过多 ({param_count} 个)",
                    suggestion="考虑使用结构体传递参数",
                    line_number=func['start_line']
                ))

            # 检查返回值
            has_return = 'return' in func_code

            metrics.append(FunctionMetrics(
                name=func['name'],
                start_line=func['start_line'],
                end_line=func['end_line'],
                lines_of_code=loc,
                cyclomatic_complexity=complexity,
                parameter_count=param_count,
                has_return=has_return,
                comment_ratio=comment_ratio
            ))

        return issues, metrics


class BestPracticeChecker:
    """最佳实践检查器"""

    @staticmethod
    def check_hal_usage(code: str) -> List[CodeIssue]:
        """检查HAL库使用规范"""
        issues = []

        # 检查是否检查返回值
        hal_calls = re.findall(r'HAL_[A-Z_][A-Z0-9_]*\s*\([^)]*\)\s*;', code)
        unchecked = [call for call in hal_calls if not re.search(r'if\s*\(' + re.escape(call), code)]

        if unchecked and len(unchecked) > 3:
            issues.append(CodeIssue(
                severity=Severity.MEDIUM,
                category="最佳实践",
                message=f"检测到 {len(unchecked)} 个HAL函数调用未检查返回值",
                suggestion="建议检查HAL函数返回值以处理可能的错误"
            ))

        # 检查GPIO初始化顺序
        if 'GPIO_Init' in code:
            if not re.search(r'GPIO_InitTypeDef.*GPIO_InitStruct', code):
                issues.append(CodeIssue(
                    severity=Severity.HIGH,
                    category="最佳实践",
                    message="GPIO初始化可能不规范",
                    suggestion="建议使用GPIO_InitTypeDef结构体进行GPIO初始化"
                ))

        return issues

    @staticmethod
    def check_interrupt_handling(code: str) -> List[CodeIssue]:
        """检查中断处理规范"""
        issues = []

        # 检查中断回调
        if 'HAL_GPIO_EXTI_Callback' in code:
            callback_match = re.search(r'void\s+HAL_GPIO_EXTI_Callback\s*\([^)]*\)\s*\{([^}]*)\}', code, re.DOTALL)
            if callback_match:
                callback_body = callback_match.group(1)

                # 检查是否有延时
                if 'HAL_Delay' in callback_body or 'delay' in callback_body.lower():
                    issues.append(CodeIssue(
                        severity=Severity.CRITICAL,
                        category="中断安全",
                        message="中断回调函数中包含延时操作",
                        suggestion="中断服务函数应尽快执行，不要在其中使用延时！"
                    ))

        # 检查全局变量在中断中的使用
        if 'IRQHandler' in code or 'EXTI' in code:
            issues.append(CodeIssue(
                severity=Severity.INFO,
                category="中断安全",
                message="使用中断时注意共享变量的保护",
                suggestion="建议使用volatile关键字或关中断保护共享变量"
            ))

        return issues

    @staticmethod
    def check_debouncing(code: str) -> List[CodeIssue]:
        """检查消抖实现"""
        issues = []

        # 检查是否有消抖
        if 'EXTI' in code or 'IRQHandler' in code:
            has_debounce = bool(
                re.search(r'DWT|CYCCNT|消抖|debounce|定时器.*TIM', code, re.IGNORECASE) or
                re.search(r'HAL_Delay.*50|delay.*50', code, re.IGNORECASE)
            )

            if not has_debounce:
                issues.append(CodeIssue(
                    severity=Severity.HIGH,
                    category="最佳实践",
                    message="检测到按键中断但未发现消抖处理",
                    suggestion="强烈建议添加消抖处理（DWT或软件延时），避免按键误触发"
                ))

        # 检查DWT配置
        if 'DWT' in code or 'CYCCNT' in code:
            required_dwt = ['DEMCR', 'CYCCNT', 'LAR']
            missing = [item for item in required_dwt if item not in code]

            if missing:
                issues.append(CodeIssue(
                    severity=Severity.MEDIUM,
                    category="最佳实践",
                    message=f"DWT配置可能不完整，缺少 {', '.join(missing)}",
                    suggestion="请确保完整配置DWT: DEMCR、CYCCNT、LAR"
                ))

        return issues

    @staticmethod
    def check_state_machine(code: str) -> List[CodeIssue]:
        """检查状态机实现"""
        issues = []

        # 检测状态变量
        state_vars = re.findall(r'(?:enum|typedef.*enum).*?state|gear.*state|档位.*状态', code, re.IGNORECASE)

        if state_vars:
            # 检查是否有状态转换逻辑
            has_switch = bool(re.search(r'switch\s*\([^)]*\)\s*\{', code))
            has_if_chain = bool(re.search(r'if.*state.*else\s+if.*state', code, re.IGNORECASE))

            if not (has_switch or has_if_chain):
                issues.append(CodeIssue(
                    severity=Severity.HIGH,
                    category="最佳实践",
                    message="检测到状态变量但未发现完整的状态转换逻辑",
                    suggestion="建议使用switch-case实现状态机"
                ))

            # 检查状态完整性（对于档位实验）
            gears = re.findall(r'[PRND]', code)
            if len(set(gears)) < 4 and '档位' in code:
                issues.append(CodeIssue(
                    severity=Severity.MEDIUM,
                    category="最佳实践",
                    message="状态机可能不完整，缺少部分档位状态",
                    suggestion="确保包含所有档位状态（P/R/N/D）"
                ))

        return issues

    @staticmethod
    def check_magic_numbers(code: str) -> List[CodeIssue]:
        """检查魔法数字"""
        issues = []

        # 常见魔法数字（排除合理的数字）
        magic_numbers = re.findall(r'(?<!\w)(\d{3,})(?!\w)', code)

        # 排除合理的数字（DWT计数值、频率等）
        reasonable = {'168000000', '84000000', '50000000', '42000000', '1000', '500', '100', '50', '0', '1'}
        suspicious = [n for n in magic_numbers if n not in reasonable]

        if suspicious:
            issues.append(CodeIssue(
                severity=Severity.LOW,
                category="代码质量",
                message=f"检测到可能的魔法数字: {', '.join(set(suspicious))}",
                suggestion="建议使用#define或const定义常量，提高代码可读性"
            ))

        return issues


class SecurityChecker:
    """安全检查器"""

    @staticmethod
    def check_common_issues(code: str) -> List[CodeIssue]:
        """检查常见安全问题"""
        issues = []

        # 检查未初始化的变量
        uninitialized = re.findall(r'(?:int|char|float)\s+(\w+)\s*;', code)
        # 这是简化检查，实际需要数据流分析

        # 检查数组越界风险
        risky_array_access = re.findall(r'\w+\[(?!.*size)', code)
        if risky_array_access:
            issues.append(CodeIssue(
                severity=Severity.MEDIUM,
                category="安全",
                message="检测到可能的数组越界风险",
                suggestion="建议检查数组访问是否在有效范围内"
            ))

        # 检查指针使用
        pointer_usage = re.findall(r'\*\s*(\w+)\s*=', code)
        if pointer_usage:
            issues.append(CodeIssue(
                severity=Severity.INFO,
                category="安全",
                message="代码中使用指针",
                suggestion="确保指针正确初始化，避免空指针访问"
            ))

        return issues


class EnhancedCodeAnalyzer:
    """增强代码分析器主类"""

    @staticmethod
    def analyze(code: str, experiment_type: str = "档位实验") -> CodeAnalysisResult:
        """
        全面分析代码质量

        Args:
            code: 代码文本
            experiment_type: 实验类型

        Returns:
            分析结果
        """
        all_issues = []
        strengths = []
        metrics = {}

        # 1. 解析代码结构
        functions = CStyleParser.extract_functions(code)
        metrics['function_count'] = len(functions)
        metrics['has_main'] = bool(re.search(r'\bint\s+main\s*\(', code))

        # 2. 命名规范检查
        naming_issues = NamingConventionChecker.check_function_names(functions)
        naming_issues.extend(NamingConventionChecker.check_variable_names(code))
        all_issues.extend(naming_issues)

        # 3. 复杂度分析
        complexity_issues, function_metrics = ComplexityAnalyzer.analyze_complexity(functions)
        all_issues.extend(complexity_issues)

        # 4. 最佳实践检查
        best_practice_issues = BestPracticeChecker.check_hal_usage(code)
        best_practice_issues.extend(BestPracticeChecker.check_interrupt_handling(code))
        best_practice_issues.extend(BestPracticeChecker.check_debouncing(code))
        best_practice_issues.extend(BestPracticeChecker.check_state_machine(code))
        best_practice_issues.extend(BestPracticeChecker.check_magic_numbers(code))
        all_issues.extend(best_practice_issues)

        # 5. 安全检查
        security_issues = SecurityChecker.check_common_issues(code)
        all_issues.extend(security_issues)

        # 6. 收集亮点
        if functions:
            avg_complexity = sum(f['complexity'] for f in functions) / len(functions)
            if avg_complexity < 5:
                strengths.append("代码结构清晰，函数复杂度控制良好")

        if re.search(r'HAL_GPIO_EXTI_Callback', code):
            strengths.append("正确实现中断回调函数")

        if 'DWT' in code or 'CYCCNT' in code:
            strengths.append("使用DWT实现精确消抖")

        if re.search(r'GPIO.*MODE.*OUTPUT', code):
            strengths.append("GPIO配置规范")

        # 7. 计算总分
        max_score = 100
        score_deductions = {
            Severity.CRITICAL: 15,
            Severity.HIGH: 10,
            Severity.MEDIUM: 5,
            Severity.LOW: 2,
            Severity.INFO: 0
        }

        total_deduction = sum(
            score_deductions[issue.severity]
            for issue in all_issues
        )

        total_score = max(0, max_score - total_deduction)

        # 补充无问题时给予加分
        if not any(i.severity in [Severity.CRITICAL, Severity.HIGH] for i in all_issues):
            total_score = min(max_score, total_score + 10)

        return CodeAnalysisResult(
            total_score=round(total_score, 1),
            max_score=max_score,
            issues=all_issues,
            metrics=metrics,
            strengths=strengths,
            function_details=function_metrics
        )

    @staticmethod
    def generate_report(result: CodeAnalysisResult, format: str = "text") -> str:
        """生成分析报告"""
        if format == "text":
            return EnhancedCodeAnalyzer._generate_text_report(result)
        elif format == "json":
            import json
            return json.dumps({
                'total_score': result.total_score,
                'issues': [
                    {
                        'severity': i.severity.value,
                        'category': i.category,
                        'message': i.message,
                        'suggestion': i.suggestion
                    }
                    for i in result.issues
                ],
                'strengths': result.strengths
            }, ensure_ascii=False, indent=2)

    @staticmethod
    def _generate_text_report(result: CodeAnalysisResult) -> str:
        """生成文本报告"""
        lines = [
            "=" * 60,
            "代码质量分析报告",
            "=" * 60,
            f"总分: {result.total_score}/{result.max_score}",
            ""
        ]

        # 统计问题
        issue_count = {}
        for issue in result.issues:
            issue_count[issue.severity.value] = issue_count.get(issue.severity.value, 0) + 1

        if issue_count:
            lines.append("问题统计:")
            for severity, count in sorted(issue_count.items(), key=lambda x: ['critical', 'high', 'medium', 'low', 'info'].index(x[0])):
                emoji = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢', 'info': '🔵'}
                lines.append(f"  {emoji[severity]} {severity.upper()}: {count}")
            lines.append("")

        # 亮点
        if result.strengths:
            lines.append("代码亮点:")
            for strength in result.strengths:
                lines.append(f"  ✓ {strength}")
            lines.append("")

        # 问题详情（按严重程度分组）
        if result.issues:
            severity_order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]
            for severity in severity_order:
                issues = [i for i in result.issues if i.severity == severity]
                if issues:
                    emoji = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢', 'info': '🔵'}
                    lines.append(f"{emoji[severity.value]} {severity.value.upper()} 级问题:")
                    for issue in issues:
                        lines.append(f"  • [{issue.category}] {issue.message}")
                        if issue.suggestion:
                            lines.append(f"    建议: {issue.suggestion}")
                    lines.append("")

        lines.append("=" * 60)

        return '\n'.join(lines)


def analyze_code_from_report(report_text: str, experiment_type: str = "档位实验") -> CodeAnalysisResult:
    """
    从实验报告中提取代码并进行分析

    Args:
        report_text: 报告全文
        experiment_type: 实验类型

    Returns:
        分析结果
    """
    # 提取代码块（支持多种格式）
    code_blocks = re.findall(r'```(?:c|cpp)?[^\n]*\n(.*?)```', report_text, re.DOTALL)

    if not code_blocks:
        # 尝试其他格式
        code_blocks = re.findall(r'~~[^\n]*\n(.*?)~~~', report_text, re.DOTALL)

    if not code_blocks:
        # 尝试直接查找函数定义
        code_blocks = [report_text]

    # 合并所有代码块
    all_code = '\n'.join(code_blocks)

    if not all_code.strip():
        return CodeAnalysisResult(
            total_score=0,
            max_score=100,
            issues=[CodeIssue(
                severity=Severity.CRITICAL,
                category="代码提取",
                message="未在报告中检测到代码",
                suggestion="请使用```代码块```格式包含代码"
            )],
            metrics={},
            strengths=[],
            function_details=[]
        )

    return EnhancedCodeAnalyzer.analyze(all_code, experiment_type)


# 别名以保持向后兼容
CodeAnalyzer = EnhancedCodeAnalyzer
