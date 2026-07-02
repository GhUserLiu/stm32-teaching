"""
查重核心模块
Core Plagiarism Detection Module

提供文本预处理、相似度计算和检测结果管理
支持自适应阈值和风险评估
"""

import re
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict
from enum import Enum

try:
    import numpy as np
    HAS_NUMPY = True
except (ImportError, RuntimeError) as e:
    # RuntimeError: "CPU dispatcher tracer already initialized"
    # This can happen in PyInstaller frozen environments
    HAS_NUMPY = False
    np = None
    import sys
    print(f"[WARNING] NumPy not available: {e}", file=sys.stderr)
    # 清除可能损坏的 NumPy 模块
    modules_to_remove = [k for k in sys.modules.keys() if k.startswith('numpy')]
    for m in modules_to_remove:
        del sys.modules[m]


class SimilarityMethod(Enum):
    """相似度计算方法"""
    SEQUENCE = 'sequence'       # 序列匹配 (difflib)
    COSINE = 'cosine'          # 余弦相似度 (TF-IDF)
    JACCARD = 'jaccard'        # Jaccard 相似度
    LEVENSHTEIN = 'levenshtein'  # 编辑距离
    HYBRID = 'hybrid'          # 混合方法
    # 新增方法
    SEMANTIC = 'semantic'      # 语义相似度 (基于嵌入模型)
    SEMANTIC_HYBRID = 'semantic_hybrid'  # 语义+传统混合
    CODE_OBFUSCATION = 'code_obfuscation'  # 代码混淆检测


@dataclass
class SimilarityResult:
    """相似度检测结果"""
    student_id: str
    similar_to: str
    overall_similarity: float  # 整体相似度 0-100
    text_similarity: float     # 文本相似度
    code_similarity: float     # 代码相似度
    structure_similarity: float # 结构相似度
    method: SimilarityMethod
    is_cross_group: bool = False
    is_suspicious: bool = False
    shared_paragraphs: List[Dict] = field(default_factory=list)
    shared_code_blocks: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    # 新增字段（保持向后兼容）
    semantic_similarity: float = 0.0          # 语义相似度 0-100
    is_paraphrase: bool = False                # 是否为改写
    code_obfuscation_score: float = 0.0        # 代码混淆分数 0-100
    ai_generation_probability: float = 0.0     # AI生成概率 0-1
    image_similarities: List[Dict] = field(default_factory=list)  # 图片相似度列表
    # 组信息不确定性标记
    group_info_uncertain: bool = False         # 组信息是否不确定（缺失）


@dataclass
class TextSegment:
    """文本段落"""
    content: str
    segment_type: str  # 'text', 'code', 'heading', 'list'
    position: int
    hash: str = ''
    cleaned: str = ''

    def __post_init__(self):
        if not self.hash:
            self.hash = hashlib.md5(self.content.encode('utf-8')).hexdigest()[:16]


class TextPreprocessor:
    """文本预处理器"""

    # 需要过滤的常见停用词
    STOP_WORDS = {
        '的', '了', '是', '在', '我', '有', '和', '就', '不', '人',
        '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
        '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '里',
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
    }

    # 代码块识别模式
    CODE_PATTERNS = [
        r'```.*?```',                    # Markdown代码块
        r'~~~.*?~~~',                    # Markdown代码块变体
        r'void\s+\w+\([^)]*\)\s*{',      # C函数声明
        r'#include\s*[<"][^>"]+[>"]',    # Include语句
        r'HAL_\w+\([^)]*\)',             # HAL函数调用
        r'GPIO_\w+',                     # GPIO常量
        r'int\s+\w+\s*[=;]',             # 整数变量
        r'uint\d+_t\s+\w+',              # 类型定义
    ]

    # 章节标题模式
    SECTION_PATTERNS = [
        r'^[一二三四五六七八九十]+[、．.]\s*\w+',
        r'^\d+[、．.]\s*\w+',
        r'^[一二三四五六七八九十]+、\s*',
        r'^\d+\s*\.',
        r'^\#{1,3}\s+\w+',
    ]

    def __init__(self, remove_template: bool = True, template_content: str = '', use_nlp_filter: bool = True):
        """
        初始化预处理器

        Args:
            remove_template: 是否移除模板内容
            template_content: 模板内容（将被从文本中排除）
            use_nlp_filter: 是否使用NLP增强模板过滤器
        """
        self.remove_template = remove_template
        self.template_content = template_content
        self.use_nlp_filter = use_nlp_filter

        # 尝试导入NLP增强过滤器
        self.advanced_filter = None
        if use_nlp_filter and template_content:
            try:
                from .nlp.template_filter import AdvancedTemplateFilter
                self.advanced_filter = AdvancedTemplateFilter(
                    template_content=template_content,
                    ngram_sizes=[3, 4, 5],
                    similarity_threshold=0.7
                )
            except ImportError:
                # NLP模块不可用，使用传统方法
                pass

        # 传统模式的模式列表
        self.template_patterns = self._extract_template_patterns(template_content)

    def _extract_template_patterns(self, template_content: str) -> List[str]:
        """从模板内容中提取特征模式（传统方法，作为后备）"""
        if not template_content:
            return []

        patterns = []
        # 提取模板中的常见句子（长度>10的句子）
        sentences = re.split(r'[。！？\n]', template_content)
        for sent in sentences:
            sent = sent.strip()
            if len(sent) > 10 and not re.match(r'^\d+$', sent):
                # 转换为正则模式，允许一定的变化
                pattern = re.escape(sent[:20])  # 取前20字符作为特征
                patterns.append(pattern)

        return patterns[:20]  # 最多保留20个模式

    def extract_segments(self, text: str) -> List[TextSegment]:
        """
        提取文本段落和代码块

        Args:
            text: 原始文本

        Returns:
            文本段落列表
        """
        segments = []
        position = 0

        # 先提取代码块
        code_blocks = []
        for pattern in self.CODE_PATTERNS:
            for match in re.finditer(pattern, text, re.DOTALL | re.MULTILINE):
                code_blocks.append((match.start(), match.end()))

        # 按位置排序并去重叠
        code_blocks = self._merge_overlaps(code_blocks)

        # 提取非代码块的文本段落
        prev_end = 0
        for start, end in code_blocks:
            # 添加代码块前的文本
            if start > prev_end:
                text_content = text[prev_end:start].strip()
                if text_content:
                    paragraphs = self._split_paragraphs(text_content)
                    for para in paragraphs:
                        if para.strip():
                            seg_type = self._detect_segment_type(para)
                            segments.append(TextSegment(
                                content=para,
                                segment_type=seg_type,
                                position=position
                            ))
                            position += 1

            # 添加代码块
            code_content = text[start:end].strip()
            if code_content:
                segments.append(TextSegment(
                    content=code_content,
                    segment_type='code',
                    position=position
                ))
                position += 1

            prev_end = end

        # 处理剩余文本
        if prev_end < len(text):
            remaining = text[prev_end:].strip()
            if remaining:
                paragraphs = self._split_paragraphs(remaining)
                for para in paragraphs:
                    if para.strip():
                        seg_type = self._detect_segment_type(para)
                        segments.append(TextSegment(
                            content=para,
                            segment_type=seg_type,
                            position=position
                        ))
                        position += 1

        return segments

    def _merge_overlaps(self, intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """合并重叠区间"""
        if not intervals:
            return []

        sorted_intervals = sorted(intervals, key=lambda x: x[0])
        merged = [sorted_intervals[0]]

        for current in sorted_intervals[1:]:
            last = merged[-1]
            if current[0] <= last[1]:  # 有重叠
                merged[-1] = (last[0], max(last[1], current[1]))
            else:
                merged.append(current)

        return merged

    def _split_paragraphs(self, text: str) -> List[str]:
        """分割文本段落"""
        # 按空行或特定标记分割
        paragraphs = re.split(r'\n\n+|\n\s*\n|=====+|------+', text)
        return [p.strip() for p in paragraphs if len(p.strip()) > 5]

    def _detect_segment_type(self, text: str) -> str:
        """检测段落类型"""
        for pattern in self.SECTION_PATTERNS:
            if re.match(pattern, text):
                return 'heading'

        if text.startswith(('- ', '*', '•', '1.', '2.')):
            return 'list'

        return 'text'

    def clean_text(self, text: str) -> str:
        """
        清理文本（去除空白、标点、停用词等）

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        # 移除空白字符
        text = re.sub(r'\s+', '', text)

        # 如果需要移除模板内容
        if self.remove_template:
            # 优先使用NLP增强过滤器
            if self.advanced_filter:
                try:
                    from .nlp.template_filter import FilterMethod
                    filter_result = self.advanced_filter.filter(text, FilterMethod.HYBRID)
                    return filter_result.filtered_text
                except Exception:
                    # NLP过滤失败，回退到传统方法
                    pass

            # 传统方法
            if self.template_patterns:
                for pattern in self.template_patterns:
                    text = re.sub(pattern, '', text)

        return text

    def normalize_for_comparison(self, segments: List[TextSegment]) -> List[TextSegment]:
        """
        标准化文本用于比较

        Args:
            segments: 原始段落列表

        Returns:
            标准化后的段落列表
        """
        normalized = []

        for seg in segments:
            # 清理内容
            cleaned = self.clean_text(seg.content)

            # 过滤太短的内容
            if len(cleaned) < 10:
                continue

            # 创建标准化段落
            normalized_seg = TextSegment(
                content=seg.content,
                segment_type=seg.segment_type,
                position=seg.position,
                cleaned=cleaned
            )
            normalized.append(normalized_seg)

        return normalized


class PlagiarismDetector:
    """查重检测器 - 支持自适应阈值和风险评估"""

    def __init__(
        self,
        method: SimilarityMethod = SimilarityMethod.HYBRID,
        threshold: float = 60.0,
        remove_template: bool = True,
        template_content: str = '',
        group_info: Optional[Dict[str, str]] = None,
        config: Optional['PlagiarismConfig'] = None,
        enable_adaptive_threshold: bool = True,
        enable_nlp_enhancements: bool = True
    ):
        """
        初始化检测器

        Args:
            method: 相似度计算方法
            threshold: 可疑阈值（0-100），作为基准值
            remove_template: 是否移除模板内容
            template_content: 模板内容
            group_info: 学生小组信息 {学号: 小组号}
            config: 完整配置对象（优先级高于单独参数）
            enable_adaptive_threshold: 是否启用自适应阈值
            enable_nlp_enhancements: 是否启用NLP增强功能
        """
        # 如果提供了配置对象，使用配置中的值
        if config is not None:
            self.config = config
            self.threshold = config.thresholds.suspicious
            self.method = method  # method参数优先
            self.remove_template = config.features.enable_template_filter
            self.template_content = config.template_content
            self.group_info = config.group_info
        else:
            self.config = None
            self.threshold = threshold
            self.method = method
            self.remove_template = remove_template
            self.template_content = template_content
            self.group_info = group_info or {}

        self.enable_adaptive_threshold = enable_adaptive_threshold
        self.enable_nlp_enhancements = enable_nlp_enhancements

        # 初始化预处理器（支持NLP增强）
        self.preprocessor = TextPreprocessor(
            self.remove_template,
            self.template_content,
            use_nlp_filter=enable_nlp_enhancements
        )

        # 初始化语义检测器（如果启用）
        self.semantic_detector = None
        self.enhanced_semantic_detector = None
        if (config and config.features.enable_semantic_detection) or config is None:
            try:
                # 注意：semantic 模块在 tools/plagiarism/semantic（本文件位于 core/），
                # 必须用 ..semantic。旧代码写成 .semantic（解析为 core.semantic，不存在），
                # 触发 ImportError 被 except 吞掉，导致语义检测整体被静默禁用。
                from ..semantic import SemanticDetector, SemanticMethod, EnhancedSemanticDetector
                use_jieba = config.features.enable_jieba if config else True
                semantic_method = SemanticMethod.TFIDF
                if config and config.features.prefer_embedding:
                    semantic_method = SemanticMethod.EMBEDDING

                self.semantic_detector = SemanticDetector(
                    method=semantic_method,
                    use_jieba=use_jieba
                )

                # 同时初始化增强的语义检测器
                self.enhanced_semantic_detector = EnhancedSemanticDetector(
                    method=semantic_method,
                    use_jieba=use_jieba
                )
            except ImportError:
                pass

        # 初始化自适应阈值引擎
        self.adaptive_engine = None
        if enable_adaptive_threshold and HAS_NUMPY:
            try:
                from .adaptive_threshold import AdaptiveThresholdEngine, RiskLevel
                self.adaptive_engine = AdaptiveThresholdEngine(baseline_threshold=self.threshold)
                self.risk_level_enum = RiskLevel
            except ImportError:
                self.enable_adaptive_threshold = False

        # 存储相似度矩阵用于自适应分析
        self.similarity_matrix = None
        self.student_id_map = []

    def detect(
        self,
        submissions: Dict[str, Dict],
        enable_risk_assessment: bool = True
    ) -> Tuple[Dict[str, List[SimilarityResult]], List[SimilarityResult], Optional[Dict]]:
        """
        执行查重检测

        Args:
            submissions: 提交内容 {学号: {name, text, ...}}
            enable_risk_assessment: 是否启用风险评估

        Returns:
            (每个学生的相似度结果, 可疑结果列表, 自适应阈值报告)
        """
        # 预处理所有提交
        processed = {}
        for student_id, submission in submissions.items():
            text = submission.get('text', '')
            segments = self.preprocessor.extract_segments(text)
            normalized = self.preprocessor.normalize_for_comparison(segments)

            processed[student_id] = {
                'name': submission.get('name', ''),
                'segments': segments,
                'normalized': normalized,
                'full_text': text,
                'group': self.group_info.get(student_id)
            }

        # 计算相似度矩阵
        all_results = defaultdict(list)
        suspicious = []

        student_ids = list(processed.keys())
        self.student_id_map = student_ids

        # 预计算语料级 IDF（语义检测用全量文档，而非每对仅 2 篇——后者 IDF 退化为负值）
        if self.semantic_detector:
            corpus_docs = [processed[sid].get('full_text') for sid in student_ids]
            self.semantic_detector.precompute_idf(corpus_docs)

        # 初始化相似度矩阵
        n = len(student_ids)
        if HAS_NUMPY and self.enable_adaptive_threshold:
            self.similarity_matrix = np.zeros((n, n))

        for i, s1 in enumerate(student_ids):
            for j in range(i + 1, len(student_ids)):
                s2 = student_ids[j]

                result = self._compare_pair(
                    processed[s1],
                    processed[s2],
                    s1,
                    s2
                )

                # 填充相似度矩阵
                if self.similarity_matrix is not None:
                    self.similarity_matrix[i, j] = result.overall_similarity
                    self.similarity_matrix[j, i] = result.overall_similarity

                # 使用自适应阈值或固定阈值
                threshold_to_use = self.threshold
                if self.adaptive_engine and self.enable_adaptive_threshold:
                    # 先收集所有相似度，后续再计算最优阈值
                    threshold_to_use = self.threshold

                if result.overall_similarity >= threshold_to_use:
                    # 判断是否跨组
                    is_cross_group, group_uncertain = self._is_cross_group(s1, s2)
                    result.is_cross_group = is_cross_group
                    result.group_info_uncertain = group_uncertain

                    # 使用风险评估
                    if enable_risk_assessment and self.adaptive_engine:
                        risk_assessment = self.adaptive_engine.evaluate_risk_level(
                            result.overall_similarity,
                            {
                                'is_cross_group': result.is_cross_group,
                                'group_info_uncertain': result.group_info_uncertain,
                                'semantic_similarity': result.semantic_similarity,
                                'code_similarity': result.code_similarity,
                                'structure_similarity': result.structure_similarity,
                                'shared_paragraphs': len(result.shared_paragraphs)
                            }
                        )
                        result.is_suspicious = risk_assessment.risk_level.value in ['high', 'critical']
                        result.metadata['risk_assessment'] = {
                            'level': risk_assessment.risk_level.value,
                            'confidence': risk_assessment.confidence,
                            'probability': risk_assessment.probability,
                            'factors': risk_assessment.key_factors,
                            'action': risk_assessment.recommended_action
                        }
                    else:
                        # 基础可疑判定：跨组或组信息不确定时，降低阈值
                        cross_group_threshold = 80 if result.group_info_uncertain else 85
                        result.is_suspicious = result.is_cross_group or result.overall_similarity >= cross_group_threshold

                    all_results[s1].append(result)
                    all_results[s2].append(result)

                    if result.is_suspicious:
                        suspicious.append(result)

        # 生成自适应阈值报告
        adaptive_report = None
        if self.enable_adaptive_threshold and self.adaptive_engine and self.similarity_matrix is not None:
            adaptive_report = self._generate_adaptive_report()

        return dict(all_results), suspicious, adaptive_report

    def _generate_adaptive_report(self) -> Dict:
        """生成自适应阈值分析报告"""
        if self.similarity_matrix is None or not self.adaptive_engine:
            return None

        # 分析相似度分布
        stats = self.adaptive_engine.analyze_similarity_distribution(self.similarity_matrix)

        # 推荐最优阈值
        recommendation = self.adaptive_engine.compute_optimal_thresholds(self.similarity_matrix)

        return {
            'distribution_stats': stats,
            'recommended_thresholds': {
                'suspicious': recommendation.suspicious_threshold,
                'high_risk': recommendation.high_risk_threshold,
                'plagiarism': recommendation.plagiarism_threshold,
                'confidence': recommendation.confidence,
                'reasoning': recommendation.reasoning
            },
            'current_threshold': self.threshold,
            'should_adjust': abs(recommendation.suspicious_threshold - self.threshold) > 5
        }

    def _compare_pair(
        self,
        sub1: Dict,
        sub2: Dict,
        id1: str,
        id2: str
    ) -> SimilarityResult:
        """比较两个提交的相似度"""
        from .algorithms import compute_similarity

        # 提取纯文本和代码
        text1 = ' '.join([s.cleaned for s in sub1['normalized'] if s.segment_type == 'text'])
        text2 = ' '.join([s.cleaned for s in sub2['normalized'] if s.segment_type == 'text'])

        code1 = ' '.join([s.cleaned for s in sub1['normalized'] if s.segment_type == 'code'])
        code2 = ' '.join([s.cleaned for s in sub2['normalized'] if s.segment_type == 'code'])

        # 计算基础相似度
        text_sim = compute_similarity(text1, text2, self.method)
        code_sim = compute_similarity(code1, code2, SimilarityMethod.SEQUENCE) if code1 and code2 else 0

        # 计算结构相似度（基于章节顺序）
        structure_sim = self._compute_structure_similarity(sub1, sub2)

        # 计算语义相似度（如果启用）
        semantic_sim = 0.0
        is_paraphrase = False
        if self.semantic_detector:
            full_text1 = sub1['full_text']
            full_text2 = sub2['full_text']
            semantic_result = self.semantic_detector.detect(full_text1, full_text2)
            semantic_sim = semantic_result.similarity
            is_paraphrase = semantic_result.is_paraphrase

        # 根据配置或默认值计算总体相似度
        if self.config and self.config.weights:
            w = self.config.weights
            overall_sim = (
                text_sim * w.text +
                code_sim * w.code +
                structure_sim * w.structure +
                semantic_sim * w.semantic
            )
        else:
            # 默认权重：文本60% + 代码40%
            overall_sim = text_sim * 0.6 + code_sim * 0.4

        # 查找共享段落
        shared_paragraphs = self._find_shared_paragraphs(sub1, sub2)
        shared_code = self._find_shared_code(sub1, sub2)

        return SimilarityResult(
            student_id=id1,
            similar_to=id2,
            overall_similarity=overall_sim,
            text_similarity=text_sim,
            code_similarity=code_sim,
            structure_similarity=structure_sim,
            method=self.method,
            shared_paragraphs=shared_paragraphs,
            shared_code_blocks=shared_code,
            metadata={
                'name1': sub1['name'],
                'name2': sub2['name'],
                'group1': sub1['group'],
                'group2': sub2['group']
            },
            semantic_similarity=semantic_sim,
            is_paraphrase=is_paraphrase
        )

    def _find_shared_paragraphs(
        self,
        sub1: Dict,
        sub2: Dict
    ) -> List[Dict]:
        """查找共享的文本段落"""
        from .algorithms import compute_similarity

        shared = []

        for seg1 in sub1['normalized']:
            if seg1.segment_type != 'text':
                continue

            for seg2 in sub2['normalized']:
                if seg2.segment_type != 'text':
                    continue

                sim = compute_similarity(
                    seg1.cleaned,
                    seg2.cleaned,
                    SimilarityMethod.SEQUENCE
                )

                if sim >= 80:  # 段落相似度阈值
                    shared.append({
                        'content': seg1.content[:50] + '...',
                        'similarity': sim,
                        'position1': seg1.position,
                        'position2': seg2.position
                    })
                    break

        return shared

    def _find_shared_code(
        self,
        sub1: Dict,
        sub2: Dict
    ) -> List[Dict]:
        """查找共享的代码块"""
        from .algorithms import sequence_similarity

        shared = []

        code_segments_1 = [s for s in sub1['normalized'] if s.segment_type == 'code']
        code_segments_2 = [s for s in sub2['normalized'] if s.segment_type == 'code']

        for seg1 in code_segments_1:
            for seg2 in code_segments_2:
                sim = sequence_similarity(seg1.cleaned, seg2.cleaned)

                if sim >= 85:  # 代码相似度阈值
                    shared.append({
                        'content': seg1.content[:50] + '...',
                        'similarity': sim,
                        'type': 'code'
                    })
                    break

        return shared

    def _compute_structure_similarity(
        self,
        sub1: Dict,
        sub2: Dict
    ) -> float:
        """计算结构相似度（章节顺序）"""
        headings1 = [s for s in sub1['segments'] if s.segment_type == 'heading']
        headings2 = [s for s in sub2['segments'] if s.segment_type == 'heading']

        if not headings1 or not headings2:
            return 50.0  # 默认中等相似度

        # 简单计算：检查标题的顺序相似度
        matches = 0
        min_len = min(len(headings1), len(headings2))

        for i in range(min_len):
            h1_clean = self.preprocessor.clean_text(headings1[i].content)
            h2_clean = self.preprocessor.clean_text(headings2[i].content)

            if h1_clean == h2_clean or h1_clean in h2_clean or h2_clean in h1_clean:
                matches += 1

        return (matches / max(len(headings1), len(headings2))) * 100

    def _is_cross_group(self, id1: str, id2: str) -> Tuple[bool, bool]:
        """
        判断是否跨组（改进版）

        Returns:
            (is_cross_group, group_info_uncertain)
            - is_cross_group: 是否跨组
            - group_info_uncertain: 组信息是否不确定
        """
        group1 = self.group_info.get(id1)
        group2 = self.group_info.get(id2)

        # 情况1: 两者组信息都缺失
        if group1 is None and group2 is None:
            # 标记为不确定，需要人工复核
            return False, True

        # 情况2: 其中一个组信息缺失
        if group1 is None or group2 is None:
            # 保守策略：如果相似度较高，应该视为可疑
            # 返回 True (跨组) 因为无法确认是同组
            return True, True

        # 情况3: 两者组信息都已知
        return group1 != group2, False

    def detect_groups(
        self,
        suspicious_results: List[SimilarityResult]
    ) -> List[Dict]:
        """
        检测抄袭团伙（多人互相高度相似）

        Args:
            suspicious_results: 可疑结果列表

        Returns:
            抄袭团伙列表
        """
        # 构建相似图
        graph = defaultdict(set)

        for result in suspicious_results:
            graph[result.student_id].add(result.similar_to)
            graph[result.similar_to].add(result.student_id)

        # 找连通分量（团伙）
        groups = []
        visited = set()

        for student_id in graph:
            if student_id in visited:
                continue

            # BFS 找连通分量
            group = set()
            queue = [student_id]

            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue

                visited.add(current)
                group.add(current)
                queue.extend(graph[current] - visited)

            if len(group) >= 2:
                groups.append({
                    'members': list(group),
                    'size': len(group)
                })

        # 按团伙大小排序
        groups.sort(key=lambda x: x['size'], reverse=True)

        return groups
