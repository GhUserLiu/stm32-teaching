# -*- coding: utf-8 -*-
"""
代码AST分析器
Code AST Analyzer

使用抽象语法树(AST)分析来增强代码相似度检测
能够检测变量重命名、注释添加/删除、空行插入等混淆手段
"""

import re
import ast
import hashlib
from typing import List, Dict, Tuple, Set, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import Counter, defaultdict


class ObfuscationType(Enum):
    """混淆类型"""
    VARIABLE_RENAMING = "variable_renaming"       # 变量重命名
    COMMENT_INSERTION = "comment_insertion"       # 注释插入
    WHITESPACE_CHANGE = "whitespace_change"       # 空白变化
    STATEMENT_REORDERING = "statement_reordering" # 语句重排序
    FUNCTION_SPLITTING = "function_splitting"     # 函数拆分
    CONTROL_FLOW_CHANGE = "control_flow_change"  # 控制流变化
    NONE = "none"


@dataclass
class CodeStructure:
    """代码结构特征"""
    functions: List[Dict] = field(default_factory=list)
    variables: Set[str] = field(default_factory=set)
    control_structures: Dict[str, int] = field(default_factory=dict)
    call_signatures: List[str] = field(default_factory=list)
    structure_hash: str = ""


@dataclass
class SimilarityResult:
    """相似度结果"""
    overall_similarity: float        # 整体相似度 0-100
    structure_similarity: float      # 结构相似度 0-100
    logic_similarity: float          # 逻辑相似度 0-100
    obfuscation_detected: List[ObfuscationType] = field(default_factory=list)
    matched_blocks: List[Dict] = field(default_factory=list)
    confidence: float = 0.0


class CCodeParser:
    """C代码解析器（简化版，无需完整C解析器）"""

    # C函数模式
    FUNCTION_PATTERN = re.compile(
        r'(?:\w+\s+)+(\w+)\s*\(([^)]*)\)\s*\{',
        re.MULTILINE
    )

    # 函数调用模式
    CALL_PATTERN = re.compile(
        r'(\w+)\s*\(([^)]*)\)',
        re.MULTILINE
    )

    # 控制结构模式
    CONTROL_PATTERNS = {
        'if': r'\bif\s*\(',
        'else': r'\belse\b',
        'for': r'\bfor\s*\(',
        'while': r'\bwhile\s*\(',
        'switch': r'\bswitch\s*\(',
        'case': r'\bcase\s+\w+:',
        'break': r'\bbreak\b',
        'continue': r'\bcontinue\b',
        'return': r'\breturn\b',
    }

    # 变量声明模式
    VAR_DECL_PATTERN = re.compile(
        r'(?:const\s+)?(?:\w+\s+)+(\w+)\s*(?:\[|\)|=|;)',
        re.MULTILINE
    )

    @staticmethod
    def extract_functions(code: str) -> List[Dict]:
        """
        提取函数信息

        Args:
            code: C代码

        Returns:
            函数列表 [{name, params, body, start, end}]
        """
        functions = []

        for match in CCodeParser.FUNCTION_PATTERN.finditer(code):
            func_name = match.group(1)
            params = match.group(2)

            # 找到函数体
            start = match.start()
            brace_count = 0
            end = start

            for i in range(start, len(code)):
                if code[i] == '{':
                    brace_count += 1
                elif code[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break

            functions.append({
                'name': func_name,
                'params': params,
                'body': code[start:end],
                'start': start,
                'end': end
            })

        return functions

    @staticmethod
    def extract_variables(code: str) -> Set[str]:
        """提取变量名"""
        variables = set()

        for match in CCodeParser.VAR_DECL_PATTERN.finditer(code):
            var_name = match.group(1)
            # 过滤关键字
            if var_name not in ['if', 'else', 'for', 'while', 'return', 'int', 'void', 'char']:
                variables.add(var_name)

        return variables

    @staticmethod
    def extract_control_structures(code: str) -> Dict[str, int]:
        """提取控制结构统计"""
        counts = defaultdict(int)

        for name, pattern in CCodeParser.CONTROL_PATTERNS.items():
            matches = re.findall(pattern, code)
            counts[name] = len(matches)

        return dict(counts)

    @staticmethod
    def extract_call_signatures(code: str) -> List[str]:
        """提取函数调用签名（参数个数）"""
        signatures = []

        for match in CCodeParser.CALL_PATTERN.finditer(code):
            func_name = match.group(1)
            params = match.group(2)

            # 计算参数个数（简单计数逗号）
            param_count = 0
            if params.strip():
                param_count = params.count(',') + 1

            signatures.append(f"{func_name}_{param_count}")

        return signatures

    @staticmethod
    def normalize_code(code: str) -> str:
        """
        规范化代码（移除不影响语义的部分）

        Args:
            code: 原始代码

        Returns:
            规范化后的代码
        """
        # 移除注释
        code = re.sub(r'//.*?$', '', code, flags=re.MULTILINE)
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)

        # 规范化空白
        code = re.sub(r'\s+', ' ', code)

        # 移除多余的分号和逗号后的空格
        code = re.sub(r'\s*([;,])\s*', r'\1', code)

        return code.strip()


class CodeASTAnalyzer:
    """代码AST分析器"""

    def __init__(self, language: str = 'c'):
        """
        初始化分析器

        Args:
            language: 编程语言 ('c', 'python', 'java')
        """
        self.language = language
        self.parser = CCodeParser() if language == 'c' else None

    def analyze(self, code: str) -> CodeStructure:
        """
        分析代码结构

        Args:
            code: 代码字符串

        Returns:
            代码结构特征
        """
        if self.language == 'c':
            return self._analyze_c_code(code)
        else:
            return CodeStructure()

    def _analyze_c_code(self, code: str) -> CodeStructure:
        """分析C代码"""
        # 提取函数
        functions = self.parser.extract_functions(code)

        # 提取变量
        variables = self.parser.extract_variables(code)

        # 提取控制结构
        control_structures = self.parser.extract_control_structures(code)

        # 提取函数调用
        call_signatures = self.parser.extract_call_signatures(code)

        # 计算结构哈希
        structure_hash = self._compute_structure_hash(
            functions, control_structures, call_signatures
        )

        return CodeStructure(
            functions=functions,
            variables=variables,
            control_structures=control_structures,
            call_signatures=call_signatures,
            structure_hash=structure_hash
        )

    def _compute_structure_hash(
        self,
        functions: List[Dict],
        control_structures: Dict[str, int],
        call_signatures: List[str]
    ) -> str:
        """计算代码结构哈希"""
        # 提取结构特征
        feature_str = ""

        # 函数名序列
        func_names = [f['name'] for f in functions]
        feature_str += "|".join(func_names)

        # 控制结构序列
        control_seq = []
        for name, count in sorted(control_structures.items()):
            control_seq.extend([name] * count)
        feature_str += "|" + "|".join(control_seq)

        # 调用签名序列
        feature_str += "|" + "|".join(sorted(call_signatures))

        return hashlib.md5(feature_str.encode('utf-8')).hexdigest()[:16]

    def compare(
        self,
        code1: str,
        code2: str
    ) -> SimilarityResult:
        """
        比较两段代码的相似度

        Args:
            code1: 代码1
            code2: 代码2

        Returns:
            相似度结果
        """
        # 分析代码结构
        struct1 = self.analyze(code1)
        struct2 = self.analyze(code2)

        # 计算各维度相似度
        structure_sim = self._compute_structure_similarity(struct1, struct2)
        logic_sim = self._compute_logic_similarity(struct1, struct2)

        # 检测混淆
        obfuscations = self._detect_obfuscation(struct1, struct2)

        # 查找匹配的代码块
        matched_blocks = self._find_matched_blocks(code1, code2)

        # 计算整体相似度
        overall_sim = (
            structure_sim * 0.4 +
            logic_sim * 0.4 +
            (len(matched_blocks) / max(len(struct1.functions), 1)) * 20
        )

        # 计算置信度
        confidence = min(1.0, overall_sim / 100 + 0.1)

        return SimilarityResult(
            overall_similarity=min(overall_sim, 100),
            structure_similarity=structure_sim,
            logic_similarity=logic_sim,
            obfuscation_detected=obfuscations,
            matched_blocks=matched_blocks,
            confidence=confidence
        )

    def _compute_structure_similarity(
        self,
        struct1: CodeStructure,
        struct2: CodeStructure
    ) -> float:
        """计算结构相似度"""
        score = 0.0
        total_checks = 0

        # 1. 函数数量相似度
        func_count_sim = 1 - abs(len(struct1.functions) - len(struct2.functions)) / max(len(struct1.functions), 1)
        score += func_count_sim * 20
        total_checks += 20

        # 2. 控制结构相似度
        all_controls = set(struct1.control_structures.keys()) | set(struct2.control_structures.keys())
        if all_controls:
            control_sim = sum(
                1 - abs(struct1.control_structures.get(c, 0) - struct2.control_structures.get(c, 0)) / max(struct1.control_structures.get(c, 0) + struct2.control_structures.get(c, 0), 1)
                for c in all_controls
            ) / len(all_controls)
            score += control_sim * 30
        else:
            score += 30
        total_checks += 30

        # 3. 调用签名相似度
        sig_set1 = set(struct1.call_signatures)
        sig_set2 = set(struct2.call_signatures)
        if sig_set1 or sig_set2:
            sig_sim = len(sig_set1 & sig_set2) / len(sig_set1 | sig_set2)
            score += sig_sim * 30
        else:
            score += 30
        total_checks += 30

        # 4. 结构哈希匹配
        if struct1.structure_hash == struct2.structure_hash:
            score += 20
        total_checks += 20

        return (score / total_checks) * 100 if total_checks > 0 else 0

    def _compute_logic_similarity(
        self,
        struct1: CodeStructure,
        struct2: CodeStructure
    ) -> float:
        """计算逻辑相似度"""
        score = 0.0
        total_checks = 0

        # 1. 函数名相似度（变量重命名检测）
        func_names1 = {f['name'] for f in struct1.functions}
        func_names2 = {f['name'] for f in struct2.functions}

        if func_names1 or func_names2:
            name_sim = len(func_names1 & func_names2) / len(func_names1 | func_names2)
            score += name_sim * 30
        else:
            score += 30
        total_checks += 30

        # 2. 变量集合相似度
        var_set1 = struct1.variables
        var_set2 = struct2.variables

        if var_set1 or var_set2:
            var_sim = len(var_set1 & var_set2) / len(var_set1 | var_set2)
            score += var_sim * 20
        else:
            score += 20
        total_checks += 20

        # 3. 控制流模式相似度
        control_sim = 0
        all_controls = set(struct1.control_structures.keys()) | set(struct2.control_structures.keys())
        if all_controls:
            for control in all_controls:
                count1 = struct1.control_structures.get(control, 0)
                count2 = struct2.control_structures.get(control, 0)
                if count1 > 0 and count2 > 0:
                    ratio = min(count1, count2) / max(count1, count2)
                    control_sim += ratio

            control_sim = control_sim / len(all_controls) if all_controls else 0

        score += control_sim * 50
        total_checks += 50

        return (score / total_checks) * 100 if total_checks > 0 else 0

    def _detect_obfuscation(
        self,
        struct1: CodeStructure,
        struct2: CodeStructure
    ) -> List[ObfuscationType]:
        """检测混淆类型"""
        detected = []

        # 1. 变量重命名检测
        var_overlap = len(struct1.variables & struct2.variables)
        var_union = len(struct1.variables | struct2.variables)
        if var_union > 3 and var_overlap / var_union < 0.3:
            detected.append(ObfuscationType.VARIABLE_RENAMING)

        # 2. 控制流变化检测
        control_diff = 0
        all_controls = set(struct1.control_structures.keys()) | set(struct2.control_structures.keys())
        for control in all_controls:
            count1 = struct1.control_structures.get(control, 0)
            count2 = struct2.control_structures.get(control, 0)
            control_diff += abs(count1 - count2)

        if control_diff > 3:
            detected.append(ObfuscationType.CONTROL_FLOW_CHANGE)

        # 3. 语句重排序检测
        if (struct1.structure_hash != struct2.structure_hash and
            self._compute_structure_similarity(struct1, struct2) > 60):
            detected.append(ObfuscationType.STATEMENT_REORDERING)

        return detected

    def _find_matched_blocks(
        self,
        code1: str,
        code2: str
    ) -> List[Dict]:
        """查找匹配的代码块"""
        matched = []

        # 分析代码1的函数
        functions1 = self.parser.extract_functions(code1)
        functions2 = self.parser.extract_functions(code2)

        for func1 in functions1:
            for func2 in functions2:
                # 比较函数体
                norm_body1 = self.parser.normalize_code(func1['body'])
                norm_body2 = self.parser.normalize_code(func2['body'])

                # 计算相似度
                similarity = self._sequence_similarity(norm_body1, norm_body2)

                if similarity >= 0.7:
                    matched.append({
                        'type': 'function',
                        'name1': func1['name'],
                        'name2': func2['name'],
                        'similarity': similarity * 100
                    })

        return matched

    def _sequence_similarity(self, s1: str, s2: str) -> float:
        """计算序列相似度"""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, s1, s2).ratio()


def compare_code_blocks(
    code1: str,
    code2: str,
    language: str = 'c'
) -> SimilarityResult:
    """
    比较两段代码的相似度（便捷函数）

    Args:
        code1: 代码1
        code2: 代码2
        language: 编程语言

    Returns:
        相似度结果
    """
    analyzer = CodeASTAnalyzer(language=language)
    return analyzer.compare(code1, code2)


def batch_compare_code(
    code_map: Dict[str, str],
    language: str = 'c'
) -> Dict[str, Dict[str, SimilarityResult]]:
    """
    批量比较代码

    Args:
        code_map: {ID: 代码}
        language: 编程语言

    Returns:
        {ID1: {ID2: 相似度结果}}
    """
    analyzer = CodeASTAnalyzer(language=language)
    results = {}

    ids = list(code_map.keys())

    for i, id1 in enumerate(ids):
        results[id1] = {}
        for id2 in ids[i+1:]:
            result = analyzer.compare(code_map[id1], code_map[id2])
            results[id1][id2] = result

    return results
