"""
模板内容排除模块
Template Content Exclusion Module

自动识别和排除报告模板中的公共内容，提高查重准确性
支持结构化模板过滤和章节级别识别
"""

import re
import zipfile
import io
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import List, Dict, Tuple, Set, Optional
from dataclasses import dataclass, field
from collections import Counter, defaultdict

# 复用统一的安全 XML 解析器（防御 XXE），避免本模块直接用裸 ET.fromstring
from tools.security.xml_parser import safe_parse_xml_string
from enum import Enum


class ContentType(Enum):
    """内容类型"""
    HEADING = "heading"       # 标题
    TEXT = "text"            # 正文
    CODE = "code"            # 代码
    LIST = "list"            # 列表
    TABLE = "table"          # 表格
    IMAGE_CAPTION = "image_caption"  # 图片说明


@dataclass
class TemplatePattern:
    """模板匹配模式"""
    content: str           # 模式内容
    weight: float = 1.0    # 权重（出现频率越高，权重越大）
    pattern_type: str = 'text'  # 类型: text, heading, code
    section: Optional[str] = None  # 所属章节
    position_variance: float = 0.0  # 位置方差（用于判断结构稳定性）


class StructuredTemplateFilter:
    """结构化模板过滤器 - 基于章节结构和位置模式的智能过滤"""

    def __init__(self, template_sections: Dict[str, List[str]], tolerance: float = 0.3):
        """
        初始化结构化过滤器

        Args:
            template_sections: 模板章节结构 {'章节名': ['内容1', '内容2', ...]}
            tolerance: 容忍度（0-1），控制模板匹配的严格程度
        """
        self.template_sections = template_sections
        self.tolerance = tolerance
        self._compile_patterns()

    def _compile_patterns(self):
        """编译正则表达式模式"""
        self.compiled_sections = {}

        for section_name, contents in self.template_sections.items():
            compiled = []
            for content in contents:
                try:
                    # 转义并创建灵活的模式
                    escaped = re.escape(content[:50])  # 使用前50字符作为特征
                    flexible = escaped.replace(r'\ ', r'\s*').replace(r'\　', r'\s*')
                    regex = re.compile(flexible)
                    compiled.append((regex, content))
                except re.error:
                    pass
            self.compiled_sections[section_name] = compiled

    def identify_template_sections(self, text: str) -> Dict[str, List[Tuple[int, str]]]:
        """
        识别文本中的模板章节

        Args:
            text: 输入文本

        Returns:
            {章节名: [(位置, 内容), ...]}
        """
        found_sections = defaultdict(list)

        lines = text.split('\n')

        for line_num, line in enumerate(lines):
            cleaned = re.sub(r'\s+', '', line)

            for section_name, patterns in self.compiled_sections.items():
                for regex, original in patterns:
                    if regex.search(cleaned):
                        found_sections[section_name].append((line_num, original))
                        break

        return dict(found_sections)

    def is_template_by_structure(
        self,
        text: str,
        expected_structure: List[str]
    ) -> Tuple[bool, float]:
        """
        基于结构判断是否为模板内容

        Args:
            text: 输入文本
            expected_structure: 期望的章节顺序 ['一、', '二、', ...]

        Returns:
            (是否为模板, 匹配置信度)
        """
        found_sections = self.identify_template_sections(text)

        # 计算结构匹配度
        match_count = 0
        for section in expected_structure:
            if section in found_sections and found_sections[section]:
                match_count += 1

        if not expected_structure:
            return False, 0.0

        match_ratio = match_count / len(expected_structure)

        # 判断位置顺序是否符合预期
        order_score = self._evaluate_section_order(found_sections, expected_structure)

        confidence = (match_ratio * 0.7 + order_score * 0.3)

        return confidence >= (1 - self.tolerance), confidence

    def _evaluate_section_order(
        self,
        found_sections: Dict[str, List[Tuple[int, str]]],
        expected_order: List[str]
    ) -> float:
        """评估章节顺序的匹配度"""
        if not found_sections or not expected_order:
            return 0.0

        # 获取实际出现顺序
        actual_order = []
        for section in expected_order:
            if section in found_sections and found_sections[section]:
                # 获取第一个出现的位置
                pos = found_sections[section][0][0]
                actual_order.append((section, pos))

        if not actual_order:
            return 0.0

        # 检查是否递增（符合预期顺序）
        correct_order = 0
        for i in range(len(actual_order) - 1):
            if actual_order[i][1] < actual_order[i + 1][1]:
                correct_order += 1

        return correct_order / max(len(actual_order) - 1, 1)

    def filter_by_structure(self, text: str) -> str:
        """
        基于结构过滤模板内容

        Args:
            text: 原始文本

        Returns:
            过滤后的文本
        """
        # 按段落分割
        paragraphs = text.split('\n\n')

        filtered = []
        for para in paragraphs:
            cleaned = re.sub(r'\s+', '', para)

            # 检查是否匹配任何模板模式
            is_template = False
            for patterns in self.compiled_sections.values():
                for regex, _ in patterns:
                    if regex.search(cleaned):
                        is_template = True
                        break
                if is_template:
                    break

            if not is_template:
                filtered.append(para)

        return '\n\n'.join(filtered)

    def compute_template_similarity(self, text: str) -> float:
        """
        计算文本与模板的相似度

        Args:
            text: 输入文本

        Returns:
            模板相似度 (0-100)
        """
        found_sections = self.identify_template_sections(text)

        if not self.template_sections:
            return 0.0

        # 计算每个章节的覆盖率
        total_patterns = sum(len(patterns) for patterns in self.template_sections.values())
        if total_patterns == 0:
            return 0.0

        matched_patterns = sum(len(patterns) for patterns in found_sections.values())

        return (matched_patterns / total_patterns) * 100


class TemplateExtractor:
    """模板内容提取器"""

    def __init__(self, min_occurrence: int = 3):
        """
        初始化提取器

        Args:
            min_occurrence: 最小出现次数，低于此次数的内容不被视为模板
        """
        self.min_occurrence = min_occurrence

    def extract_from_docx(self, docx_path: Path) -> List[TemplatePattern]:
        """
        从 docx 模板文件中提取内容

        Args:
            docx_path: 模板文件路径

        Returns:
            模板模式列表
        """
        # 读取 docx 内容
        text = self._read_docx(docx_path)

        if not text:
            return []

        # 提取模式
        patterns = []

        # 1. 提取标题模式
        headings = self._extract_headings(text)
        patterns.extend([TemplatePattern(h, weight=2.0, pattern_type='heading') for h in headings])

        # 2. 提取常见句子
        sentences = self._extract_sentences(text)
        patterns.extend([TemplatePattern(s, weight=1.0, pattern_type='text') for s in sentences])

        # 3. 提取表格标题
        table_headers = self._extract_table_headers(text)
        patterns.extend([TemplatePattern(h, weight=1.5, pattern_type='text') for h in table_headers])

        return patterns

    def extract_from_multiple_reports(
        self,
        report_paths: List[Path],
        sample_size: int = 10
    ) -> Tuple[List[TemplatePattern], Dict[str, List[str]]]:
        """
        从多份报告中分析提取模板内容和结构

        Args:
            report_paths: 报告文件路径列表
            sample_size: 采样数量（分析前N份报告）

        Returns:
            (模板模式列表, 章节结构字典)
        """
        # 采样
        samples = report_paths[:sample_size] if len(report_paths) > sample_size else report_paths

        # 收集所有内容
        all_headings = []
        all_sentences = []
        all_code_patterns = []
        section_structure = defaultdict(list)

        for path in samples:
            text = self._read_docx(path)
            if not text:
                continue

            # 提取标题和章节结构
            headings = self._extract_headings_with_structure(text)
            all_headings.extend([h['text'] for h in headings])

            # 记录章节结构
            for heading in headings:
                if heading['section']:
                    section_structure[heading['section']].append(heading['text'])

            # 提取句子
            sentences = self._extract_sentences(text)
            all_sentences.extend(sentences)

            # 提取代码模式
            code_patterns = self._extract_code_patterns(text)
            all_code_patterns.extend(code_patterns)

        # 统计频率
        patterns = []

        # 标题（出现频率高的是模板）
        heading_counter = Counter(all_headings)
        for heading, count in heading_counter.items():
            if count >= self.min_occurrence:
                # 计算位置方差
                occurrences = self._get_heading_positions(heading, samples)
                position_variance = self._compute_position_variance(occurrences)

                patterns.append(TemplatePattern(
                    heading,
                    weight=float(count) / len(samples),
                    pattern_type='heading',
                    position_variance=position_variance
                ))

        # 句子
        sentence_counter = Counter(all_sentences)
        for sentence, count in sentence_counter.items():
            if count >= self.min_occurrence and len(sentence) > 8:
                patterns.append(TemplatePattern(
                    sentence,
                    weight=float(count) / len(samples),
                    pattern_type='text'
                ))

        # 代码模式
        code_counter = Counter(all_code_patterns)
        for code, count in code_counter.items():
            if count >= self.min_occurrence:
                patterns.append(TemplatePattern(
                    code,
                    weight=float(count) / len(samples),
                    pattern_type='code'
                ))

        # 稳定化章节结构（选择出现频率高的内容）
        stable_structure = {}
        for section, contents in section_structure.items():
            content_counter = Counter(contents)
            stable_structure[section] = [
                content for content, count in content_counter.most_common(10)
                if count >= self.min_occurrence
            ]

        return patterns, stable_structure

    def _read_docx(self, path: Path) -> str:
        """读取 docx 文件内容"""
        try:
            with open(path, 'rb') as f:
                docx_data = f.read()

            with zipfile.ZipFile(io.BytesIO(docx_data), 'r') as docx:
                xml_content = docx.read('word/document.xml')
                root = safe_parse_xml_string(xml_content)
                texts = []

                for elem in root.iter():
                    if elem.tag.endswith('}t'):
                        if elem.text:
                            texts.append(elem.text)

                return ''.join(texts)
        except Exception as e:
            print(f"Warning: Failed to read {path}: {e}")
            return ''

    def _extract_headings(self, text: str) -> List[str]:
        """提取标题"""
        headings = []

        # 常见标题模式
        patterns = [
            r'([一二三四五六七八九十]+[、．.]\s*[一-龥A-Za-z0-9]+)',
            r'(\d+[、．.]\s*[一-龥A-Za-z0-9]+)',
            r'(实验[目的内容原理步骤结果讨论]+)',
            r'([一二三四五六七八九十]+、)',
            r'(\d+\s*\.\s*[一-龥]+)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            headings.extend(matches)

        return list(set([h.strip() for h in headings if h.strip()]))

    def _extract_headings_with_structure(self, text: str) -> List[Dict]:
        """提取标题及章节结构信息"""
        headings = []
        lines = text.split('\n')
        current_section = None

        section_patterns = [
            (r'^([一二三四五六七八九十]+)[、．.]', 'section_num'),
            (r'^(\d+)[、．.]', 'section_digit'),
            (r'^(实验[目的原理内容步骤结果讨论]+)', 'section_exp'),
        ]

        for line_num, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # 检测章节变化
            for pattern, section_type in section_patterns:
                match = re.match(pattern, line)
                if match:
                    current_section = match.group(1)
                    break

            # 检测标题
            for pattern in [
                r'([一二三四五六七八九十]+[、．.]\s*[一-龥A-Za-z0-9]+)',
                r'(\d+[、．.]\s*[一-龥A-Za-z0-9]+)',
                r'([一-龥]{2,8}(说明|要求|定义|分析))',
            ]:
                matches = re.findall(pattern, line)
                for match in matches:
                    headings.append({
                        'text': match,
                        'position': line_num,
                        'section': current_section
                    })

        return headings

    def _get_heading_positions(self, heading: str, samples: List[Path]) -> List[int]:
        """获取标题在样本中的出现位置"""
        positions = []

        for path in samples:
            text = self._read_docx(path)
            if not text:
                continue

            lines = text.split('\n')
            for line_num, line in enumerate(lines):
                if re.sub(r'\s+', '', heading) in re.sub(r'\s+', '', line):
                    positions.append(line_num)
                    break

        return positions

    def _compute_position_variance(self, positions: List[int]) -> float:
        """计算位置方差（用于判断模板位置的稳定性）"""
        if not positions or len(positions) < 2:
            return 0.0

        mean = sum(positions) / len(positions)
        variance = sum((p - mean) ** 2 for p in positions) / len(positions)
        return float(variance)

    def _extract_sentences(self, text: str) -> List[str]:
        """提取句子"""
        # 按句号、问号、感叹号分割
        sentences = re.split(r'[。！？\n]', text)

        # 过滤
        filtered = []
        for sent in sentences:
            sent = sent.strip()
            # 长度在 8-50 字符之间
            if 8 <= len(sent) <= 50:
                # 不全是数字或符号
                if not re.match(r'^[\d\s\-\(\)（）]+$', sent):
                    filtered.append(sent)

        return filtered

    def _extract_table_headers(self, text: str) -> List[str]:
        """提取表格标题"""
        # 常见表格标题模式
        patterns = [
            r'(引脚\s*[功能定义说明]+)',
            r'(序号\s*名称\s*[功能说明]+)',
            r'(步骤\s*现象\s*说明)',
            r'(项目\s*内容\s*分值)',
        ]

        headers = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            headers.extend(matches)

        return list(set(headers))

    def _extract_code_patterns(self, text: str) -> List[str]:
        """提取代码模式"""
        patterns = []

        # HAL 函数调用模式
        hal_calls = re.findall(r'HAL_GPIO_\w+\([^)]*\)', text)
        patterns.extend(hal_calls)

        # GPIO 常量
        gpio_consts = re.findall(r'GPIO_PIN_\w+', text)
        patterns.extend(gpio_consts)

        # include 语句
        includes = re.findall(r'#include\s*<[^>]+>', text)
        patterns.extend(includes)

        return list(set(patterns))


class TemplateFilter:
    """模板过滤器"""

    def __init__(self, patterns: List[TemplatePattern], threshold: float = 0.5):
        """
        初始化过滤器

        Args:
            patterns: 模板模式列表
            threshold: 匹配阈值（0-1），高于此值被视为模板内容
        """
        self.patterns = patterns
        self.threshold = threshold
        self._compile_patterns()

    def _compile_patterns(self):
        """编译正则表达式"""
        self.compiled_patterns = []

        for pattern in self.patterns:
            try:
                # 转义特殊字符
                escaped = re.escape(pattern.content)
                # 允许一定的变化（空格、标点）
                flexible = escaped.replace(r'\ ', r'\s*').replace(r'\，', r'[，、]?\s*')

                regex = re.compile(flexible)
                self.compiled_patterns.append((regex, pattern.weight, pattern.pattern_type))
            except re.error:
                pass

    def is_template_content(self, text: str) -> bool:
        """
        判断文本是否为模板内容

        Args:
            text: 待判断的文本

        Returns:
            是否为模板内容
        """
        if not text or len(text.strip()) < 5:
            return True  # 短内容视为模板

        cleaned = re.sub(r'\s+', '', text)

        # 检查是否匹配任何模式
        for regex, weight, pattern_type in self.compiled_patterns:
            if regex.search(cleaned):
                # 权重越高，越可能是模板
                if weight >= self.threshold:
                    return True

        return False

    def filter_text(self, text: str, return_segments: bool = False) -> str:
        """
        过滤掉模板内容

        Args:
            text: 原始文本
            return_segments: 是否返回分段信息

        Returns:
            过滤后的文本
        """
        # 按段落分割
        paragraphs = re.split(r'\n\n+|\n\s*\n', text)

        filtered = []

        for para in paragraphs:
            if not self.is_template_content(para):
                filtered.append(para)

        return '\n\n'.join(filtered)

    def get_template_ratio(self, text: str) -> float:
        """
        计算文本中模板内容的比例

        Args:
            text: 文本内容

        Returns:
            模板内容占比 (0-1)
        """
        # 按段落分割
        paragraphs = re.split(r'\n\n+|\n\s*\n', text)

        template_count = 0
        total_count = len(paragraphs)

        for para in paragraphs:
            if self.is_template_content(para):
                template_count += 1

        if total_count == 0:
            return 0.0

        return template_count / total_count

    def extract_non_template_segments(self, text: str) -> List[Tuple[str, bool]]:
        """
        提取非模板段落

        Args:
            text: 原始文本

        Returns:
            [(段落内容, 是否为模板), ...]
        """
        # 按段落分割
        paragraphs = re.split(r'(\n\n+|\n\s*\n)', text)

        segments = []

        for i in range(0, len(paragraphs), 2):
            content = paragraphs[i].strip()
            if content:
                is_template = self.is_template_content(content)
                segments.append((content, is_template))

        return segments


def load_template_from_file(template_path: Path) -> TemplateFilter:
    """
    从模板文件加载过滤器

    Args:
        template_path: 模板文件路径

    Returns:
        模板过滤器
    """
    extractor = TemplateExtractor(min_occurrence=2)
    patterns = extractor.extract_from_docx(template_path)

    return TemplateFilter(patterns, threshold=0.3)


def create_filter_from_reports(
    report_paths: List[Path],
    min_occurrence: int = 3,
    threshold: float = 0.4
) -> TemplateFilter:
    """
    从多份报告创建过滤器

    Args:
        report_paths: 报告文件路径列表
        min_occurrence: 最小出现次数
        threshold: 匹配阈值

    Returns:
        模板过滤器
    """
    extractor = TemplateExtractor(min_occurrence=min_occurrence)
    patterns, structure = extractor.extract_from_multiple_reports(report_paths)

    return TemplateFilter(patterns, threshold=threshold)


def create_structured_filter_from_reports(
    report_paths: List[Path],
    min_occurrence: int = 3,
    tolerance: float = 0.3
) -> StructuredTemplateFilter:
    """
    从多份报告创建结构化过滤器

    Args:
        report_paths: 报告文件路径列表
        min_occurrence: 最小出现次数
        tolerance: 容忍度

    Returns:
        结构化模板过滤器
    """
    extractor = TemplateExtractor(min_occurrence=min_occurrence)
    patterns, structure = extractor.extract_from_multiple_reports(report_paths)

    return StructuredTemplateFilter(structure, tolerance=tolerance)


def load_template_from_file(template_path: Path) -> TemplateFilter:
    """
    从模板文件加载过滤器

    Args:
        template_path: 模板文件路径

    Returns:
        模板过滤器
    """
    extractor = TemplateExtractor(min_occurrence=2)
    patterns, structure = extractor.extract_from_multiple_reports([template_path])

    return TemplateFilter(patterns, threshold=0.3)


def create_combined_filter(
    template_path: Optional[Path] = None,
    report_paths: Optional[List[Path]] = None,
    min_occurrence: int = 3,
    threshold: float = 0.4,
    use_structure: bool = True
) -> Tuple[TemplateFilter, Optional[StructuredTemplateFilter]]:
    """
    创建组合过滤器（包含传统和结构化过滤器）

    Args:
        template_path: 模板文件路径（可选）
        report_paths: 报告文件路径列表（可选）
        min_occurrence: 最小出现次数
        threshold: 匹配阈值
        use_structure: 是否使用结构化过滤

    Returns:
        (传统过滤器, 结构化过滤器)
    """
    extractor = TemplateExtractor(min_occurrence=min_occurrence)

    if template_path:
        patterns, structure = extractor.extract_from_multiple_reports([template_path])
    elif report_paths:
        patterns, structure = extractor.extract_from_multiple_reports(report_paths)
    else:
        patterns, structure = [], {}

    traditional = TemplateFilter(patterns, threshold=threshold) if patterns else None
    structured = StructuredTemplateFilter(structure, tolerance=0.3) if (use_structure and structure) else None

    return (traditional, structured)
