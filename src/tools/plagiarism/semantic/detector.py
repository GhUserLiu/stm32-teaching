# -*- coding: utf-8 -*-
"""
语义相似度检测器
Semantic Similarity Detector

用于检测改写后的抄袭内容
"""

import re
import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum
from collections import Counter


class SemanticMethod(Enum):
    """语义相似度计算方法"""
    TFIDF = 'tfidf'           # TF-IDF + 余弦相似度（轻量级）
    EMBEDDING = 'embedding'   # 句子嵌入（需要 sentence-transformers）


@dataclass
class SemanticSimilarityResult:
    """语义相似度检测结果"""
    similarity: float              # 语义相似度 0-100
    is_paraphrase: bool           # 是否为改写
    confidence: float             # 检测置信度 0-1
    matched_segments: List[Dict]  # 匹配的段落
    paraphrased_sentences: List[Dict]  # 改写的句子对
    method_used: SemanticMethod   # 使用的方法


class ChineseTextProcessor:
    """中文文本处理器"""

    # 中文停用词
    STOP_WORDS = {
        '的', '了', '是', '在', '我', '有', '和', '就', '不', '人',
        '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
        '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '里',
        '与', '及', '等', '或', '而', '但', '因', '所', '以', '为',
    }

    def __init__(self, use_jieba: bool = True):
        """
        初始化文本处理器

        Args:
            use_jieba: 是否使用 jieba 分词（更精确）
        """
        self.use_jieba = use_jieba
        self.jieba_loaded = False

        if use_jieba:
            try:
                import jieba
                self.jieba = jieba
                # 尝试加载自定义词典（如果有）
                try:
                    self.jieba.load_userdict('tools/plagiarism/jieba_userdict.txt')
                except Exception:
                    pass  # 使用默认词典
                self.jieba_loaded = True
            except ImportError:
                self.jieba_loaded = False

    @staticmethod
    def extract_sentences(text: str) -> List[str]:
        """
        提取句子

        Args:
            text: 输入文本

        Returns:
            句子列表
        """
        # 按句号、问号、感叹号分割
        sentences = re.split(r'[。！？\n]+', text)
        return [s.strip() for s in sentences if len(s.strip()) > 5]

    def tokenize(self, text: str) -> List[str]:
        """
        分词（支持 jieba 精确分词或简单字符分割）

        Args:
            text: 输入文本

        Returns:
            词列表
        """
        # 如果 jieba 可用，使用 jieba 分词
        if self.use_jieba and self.jieba_loaded:
            words = self.jieba.lcut(text)
            # 过滤停用词和单字符标点
            tokens = [
                w for w in words
                if w.strip() and
                w not in self.STOP_WORDS and
                not all(c in '，。！？、；：""''（）【】《》' for c in w)
            ]
            return tokens

        # 回退到简单分词方法
        # 移除标点和空白
        text = re.sub(r'[^\w一-鿿]', ' ', text)
        # 按字符分割（保留2字以上的词）
        tokens = []
        words = re.findall(r'[一-鿿]{2,}|[a-zA-Z]{2,}', text)
        tokens.extend(words)
        return tokens

    @staticmethod
    def remove_stop_words(tokens: List[str]) -> List[str]:
        """移除停用词"""
        return [t for t in tokens if t not in ChineseTextProcessor.STOP_WORDS]


class TfidfCalculator:
    """TF-IDF 计算器"""

    def __init__(self):
        self.idf_cache = {}
        # 复用单个分词器，避免每次 calculate_tf/idf 都 new 一个 ChineseTextProcessor
        # （后者构造时会重新触发 jieba 初始化，批量两两比对时浪费明显）。
        # 注：当前 IDF 仍按"被比较的两个文档"计算（见 _detect_with_tfidf），
        # 真正的语料级 IDF 需把全量提交传入检测器，属更大的架构改动，暂未做。
        self.processor = ChineseTextProcessor()

    def calculate_tf(self, text: str) -> Dict[str, float]:
        """
        计算词频（TF）

        Args:
            text: 输入文本

        Returns:
            {词: TF值}
        """
        processor = self.processor
        tokens = processor.tokenize(text)
        tokens = processor.remove_stop_words(tokens)

        if not tokens:
            return {}

        total = len(tokens)
        tf = Counter(tokens)
        return {word: count / total for word, count in tf.items()}

    def calculate_idf(
        self,
        documents: List[str],
        min_df: int = 1
    ) -> Dict[str, float]:
        """
        计算逆文档频率（IDF）

        Args:
            documents: 文档列表
            min_df: 最小文档频率

        Returns:
            {词: IDF值}
        """
        processor = self.processor
        df = Counter()

        for doc in documents:
            tokens = processor.tokenize(doc)
            tokens = processor.remove_stop_words(tokens)
            unique_tokens = set(tokens)
            df.update(unique_tokens)

        total_docs = len(documents)
        idf = {}

        # 平滑 IDF（sklearn 风格）：log((1+N)/(1+df)) + 1，恒为正、且对稀有词更高。
        # 旧公式 log(N/(1+df)) 对出现在 >=2 篇的词给出 0/负值，使 TF-IDF 退化为 0、
        # 语义相似度恒为 0；配合 min_df=1 让每个语料词都有权重，相似度才有区分力。
        for word, count in df.items():
            if count >= min_df:
                idf[word] = math.log((1 + total_docs) / (1 + count)) + 1

        self.idf_cache = idf
        return idf

    def calculate_tfidf(
        self,
        text: str,
        idf: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """
        计算 TF-IDF

        Args:
            text: 输入文本
            idf: IDF字典（可选）

        Returns:
            {词: TF-IDF值}
        """
        tf = self.calculate_tf(text)
        idf = idf or self.idf_cache

        if not idf:
            return tf

        tfidf = {}
        for word, tf_val in tf.items():
            tfidf[word] = tf_val * idf.get(word, 0)

        return tfidf

    def cosine_similarity(
        self,
        text1: str,
        text2: str,
        idf: Optional[Dict[str, float]] = None
    ) -> float:
        """
        计算余弦相似度

        Args:
            text1: 文本1
            text2: 文本2
            idf: IDF字典

        Returns:
            相似度 0-1
        """
        tfidf1 = self.calculate_tfidf(text1, idf)
        tfidf2 = self.calculate_tfidf(text2, idf)

        if not tfidf1 or not tfidf2:
            return 0.0

        # 计算点积
        all_words = set(tfidf1.keys()) | set(tfidf2.keys())
        dot_product = sum(
            tfidf1.get(word, 0) * tfidf2.get(word, 0)
            for word in all_words
        )

        # 计算模长
        norm1 = math.sqrt(sum(v ** 2 for v in tfidf1.values()))
        norm2 = math.sqrt(sum(v ** 2 for v in tfidf2.values()))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


class SemanticDetector:
    """语义相似度检测器"""

    def __init__(
        self,
        method: SemanticMethod = SemanticMethod.TFIDF,
        threshold: float = 0.6,
        use_jieba: bool = True
    ):
        """
        初始化检测器

        Args:
            method: 检测方法（TFIDF 或 EMBEDDING）
            threshold: 改写判定阈值
            use_jieba: 是否使用 jieba 分词
        """
        self.method = method
        self.threshold = threshold
        self.use_jieba = use_jieba
        self.tfidf_calculator = TfidfCalculator()
        self.text_processor = ChineseTextProcessor(use_jieba=use_jieba)

        # 尝试导入 sentence-transformers（如果使用 EMBEDDING 方法）
        self.embedding_model = None
        if method == SemanticMethod.EMBEDDING:
            try:
                from sentence_transformers import SentenceTransformer
                model_name = 'paraphrase-multilingual-MiniLM-L12-v2'
                self.embedding_model = SentenceTransformer(model_name)
            except ImportError:
                print("Warning: sentence-transformers not installed, falling back to TF-IDF")
                self.method = SemanticMethod.TFIDF

    def precompute_idf(self, documents: List[str]) -> None:
        """用全量文档预计算语料级 IDF，供后续两两比对复用。

        旧实现每对都用 [text1, text2] 两篇文档算 IDF，min_df=2 时 IDF 为负、
        语义上无意义；语料级 IDF 才能正确反映词的稀有度。由 PlagiarismDetector
        在两两比对前调用一次。
        """
        docs = [d for d in documents if d]
        if docs:
            self.tfidf_calculator.calculate_idf(docs)

    def detect(
        self,
        text1: str,
        text2: str,
        compare_sentences: bool = True
    ) -> SemanticSimilarityResult:
        """
        检测语义相似度

        Args:
            text1: 文本1
            text2: 文本2
            compare_sentences: 是否进行句子级别的比较

        Returns:
            语义相似度检测结果
        """
        if self.method == SemanticMethod.EMBEDDING and self.embedding_model:
            return self._detect_with_embedding(text1, text2, compare_sentences)
        else:
            return self._detect_with_tfidf(text1, text2, compare_sentences)

    def _detect_with_tfidf(
        self,
        text1: str,
        text2: str,
        compare_sentences: bool
    ) -> SemanticSimilarityResult:
        """使用 TF-IDF 检测"""
        processor = self.text_processor

        # IDF：优先用预计算的语料级 IDF（precompute_idf 注入）；未预计算时回退到
        # 当前两文档（仅 2 篇时 IDF 退化为负值、语义很弱，仅作兜底）。
        if not self.tfidf_calculator.idf_cache:
            self.tfidf_calculator.calculate_idf([text1, text2])

        # 计算整体相似度
        overall_sim = self.tfidf_calculator.cosine_similarity(text1, text2)

        # 提取句子并比较
        matched_segments = []
        paraphrased_sentences = []

        if compare_sentences:
            sentences1 = processor.extract_sentences(text1)
            sentences2 = processor.extract_sentences(text2)

            for i, sent1 in enumerate(sentences1):
                for j, sent2 in enumerate(sentences2):
                    sent_sim = self.tfidf_calculator.cosine_similarity(sent1, sent2)

                    if sent_sim > self.threshold:
                        matched_segments.append({
                            'text1': sent1[:50] + '...',
                            'text2': sent2[:50] + '...',
                            'similarity': sent_sim * 100,
                            'position1': i,
                            'position2': j
                        })

                    if sent_sim > 0.5 and sent_sim < 0.9:
                        paraphrased_sentences.append({
                            'text1': sent1,
                            'text2': sent2,
                            'similarity': sent_sim * 100
                        })

        # 判断是否改写
        is_paraphrase = (
            overall_sim > 0.5 and
            overall_sim < 0.85 and
            len(paraphrased_sentences) > 0
        )

        # 计算置信度
        confidence = min(1.0, overall_sim + len(matched_segments) * 0.05)

        return SemanticSimilarityResult(
            similarity=overall_sim * 100,
            is_paraphrase=is_paraphrase,
            confidence=confidence,
            matched_segments=matched_segments,
            paraphrased_sentences=paraphrased_sentences,
            method_used=SemanticMethod.TFIDF
        )

    def _detect_with_embedding(
        self,
        text1: str,
        text2: str,
        compare_sentences: bool
    ) -> SemanticSimilarityResult:
        """使用句子嵌入检测"""
        processor = self.text_processor

        # 计算整体嵌入
        emb1 = self.embedding_model.encode(text1)
        emb2 = self.embedding_model.encode(text2)

        # 计算余弦相似度
        import numpy as np
        overall_sim = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))

        # 提取句子并比较
        matched_segments = []
        paraphrased_sentences = []

        if compare_sentences:
            sentences1 = processor.extract_sentences(text1)
            sentences2 = processor.extract_sentences(text2)

            embeddings1 = self.embedding_model.encode(sentences1)
            embeddings2 = self.embedding_model.encode(sentences2)

            for i, (sent1, emb1) in enumerate(zip(sentences1, embeddings1)):
                for j, (sent2, emb2) in enumerate(zip(sentences2, embeddings2)):
                    sent_sim = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))

                    if sent_sim > self.threshold:
                        matched_segments.append({
                            'text1': sent1[:50] + '...',
                            'text2': sent2[:50] + '...',
                            'similarity': sent_sim * 100,
                            'position1': i,
                            'position2': j
                        })

                    if sent_sim > 0.5 and sent_sim < 0.9:
                        paraphrased_sentences.append({
                            'text1': sent1,
                            'text2': sent2,
                            'similarity': sent_sim * 100
                        })

        # 判断是否改写
        is_paraphrase = (
            overall_sim > 0.5 and
            overall_sim < 0.85 and
            len(paraphrased_sentences) > 0
        )

        confidence = min(1.0, overall_sim + len(matched_segments) * 0.05)

        return SemanticSimilarityResult(
            similarity=overall_sim * 100,
            is_paraphrase=is_paraphrase,
            confidence=confidence,
            matched_segments=matched_segments,
            paraphrased_sentences=paraphrased_sentences,
            method_used=SemanticMethod.EMBEDDING
        )

    def batch_detect(
        self,
        submissions: Dict[str, str],
        compare_original: bool = True
    ) -> Dict[str, List[Dict]]:
        """
        批量检测语义相似度

        Args:
            submissions: {学号: 文本}
            compare_original: 是否与原文比较

        Returns:
            {学号: [相似度结果列表]}
        """
        results = {}
        student_ids = list(submissions.keys())

        for i, s1 in enumerate(student_ids):
            similarities = []
            for j in range(i + 1, len(student_ids)):
                s2 = student_ids[j]

                result = self.detect(
                    submissions[s1],
                    submissions[s2]
                )

                similarities.append({
                    'similar_to': s2,
                    'similarity': result.similarity,
                    'is_paraphrase': result.is_paraphrase,
                    'confidence': result.confidence
                })

            if similarities:
                results[s1] = similarities

        return results
