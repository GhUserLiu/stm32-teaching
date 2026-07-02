"""
相似度计算算法模块
Similarity Calculation Algorithms

提供多种文本相似度计算方法
"""

import re
import math
from collections import Counter
from difflib import SequenceMatcher
from typing import List, Dict, Tuple
from .detector import SimilarityMethod


def sequence_similarity(text1: str, text2: str) -> float:
    """
    序列相似度（基于 difflib.SequenceMatcher）

    Args:
        text1: 第一个文本
        text2: 第二个文本

    Returns:
        相似度百分比 (0-100)
    """
    if not text1 or not text2:
        return 0.0

    return SequenceMatcher(None, text1, text2).ratio() * 100


def cosine_similarity(text1: str, text2: str) -> float:
    """
    余弦相似度（基于 TF-IDF）

    Args:
        text1: 第一个文本
        text2: 第二个文本

    Returns:
        相似度百分比 (0-100)
    """
    if not text1 or not text2:
        return 0.0

    # 分词（简单按字符分割，支持中文）
    words1 = _tokenize(text1)
    words2 = _tokenize(text2)

    if not words1 or not words2:
        return 0.0

    # 计算词频
    freq1 = Counter(words1)
    freq2 = Counter(words2)

    # 计算余弦相似度
    dot_product = sum(freq1[w] * freq2.get(w, 0) for w in freq1)
    norm1 = math.sqrt(sum(v ** 2 for v in freq1.values()))
    norm2 = math.sqrt(sum(v ** 2 for v in freq2.values()))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return (dot_product / (norm1 * norm2)) * 100


def jaccard_similarity(text1: str, text2: str) -> float:
    """
    Jaccard 相似度（集合交集/并集）

    Args:
        text1: 第一个文本
        text2: 第二个文本

    Returns:
        相似度百分比 (0-100)
    """
    if not text1 or not text2:
        return 0.0

    words1 = set(_tokenize(text1))
    words2 = set(_tokenize(text2))

    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2

    if not union:
        return 0.0

    return (len(intersection) / len(union)) * 100


def levenshtein_similarity(text1: str, text2: str) -> float:
    """
    编辑距离相似度（基于 Levenshtein 距离）

    Args:
        text1: 第一个文本
        text2: 第二个文本

    Returns:
        相似度百分比 (0-100)
    """
    if not text1 or not text2:
        return 0.0

    # 限制文本长度以提高性能
    if len(text1) > 1000 or len(text2) > 1000:
        # 对长文本，只比较前1000字符
        text1 = text1[:1000]
        text2 = text2[:1000]

    distance = _levenshtein_distance(text1, text2)
    max_len = max(len(text1), len(text2))

    if max_len == 0:
        return 100.0

    return (1 - distance / max_len) * 100


def _levenshtein_distance(s1: str, s2: str) -> int:
    """计算 Levenshtein 编辑距离"""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))

    for i, c1 in enumerate(s1):
        current_row = [i + 1]

        for j, c2 in enumerate(s2):
            # 计算替换、插入、删除的成本
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)

            current_row.append(min(insertions, deletions, substitutions))

        previous_row = current_row

    return previous_row[-1]


def _tokenize(text: str) -> List[str]:
    """
    分词函数（支持中文）

    Args:
        text: 输入文本

    Returns:
        词语列表
    """
    # 对于中文，按字符分割（简单有效）
    # 对于英文，按单词分割
    tokens = []

    for char in text:
        if '一' <= char <= '鿿':  # 中文字符
            tokens.append(char)
        elif char.isalnum():  # 字母数字
            tokens.append(char.lower())

    # 对于英文，合并连续的字母
    merged = []
    i = 0

    while i < len(tokens):
        if tokens[i].isalpha():
            # 收集连续的字母
            word = tokens[i]
            j = i + 1

            while j < len(tokens) and tokens[j].isalpha():
                word += tokens[j]
                j += 1

            merged.append(word)
            i = j
        else:
            merged.append(tokens[i])
            i += 1

    # 过滤单个英文字符（保留中文单字）；但若过滤后为空则回退到原列表，
    # 否则仅含单字符的英文文档（如 "a"）会得到空词表，自相似度为 0。
    filtered = [t for t in merged if len(t) > 1 or ('一' <= t <= '鿿')]
    return filtered if filtered else merged


def hybrid_similarity(text1: str, text2: str) -> float:
    """
    混合相似度（综合多种算法）

    Args:
        text1: 第一个文本
        text2: 第二个文本

    Returns:
        综合相似度百分比 (0-100)
    """
    # 计算各种相似度
    seq_sim = sequence_similarity(text1, text2)
    cos_sim = cosine_similarity(text1, text2)
    jac_sim = jaccard_similarity(text1, text2)

    # 加权平均
    weights = {
        'sequence': 0.4,
        'cosine': 0.4,
        'jaccard': 0.2
    }

    hybrid = (
        seq_sim * weights['sequence'] +
        cos_sim * weights['cosine'] +
        jac_sim * weights['jaccard']
    )

    return min(hybrid, 100.0)


def compute_similarity(
    text1: str,
    text2: str,
    method: SimilarityMethod = SimilarityMethod.HYBRID
) -> float:
    """
    计算文本相似度（统一接口）

    Args:
        text1: 第一个文本
        text2: 第二个文本
        method: 计算方法

    Returns:
        相似度百分比 (0-100)
    """
    # 清理文本
    text1 = re.sub(r'\s+', '', text1)
    text2 = re.sub(r'\s+', '', text2)

    if not text1 or not text2:
        return 0.0

    # 根据方法选择算法
    if method == SimilarityMethod.SEQUENCE:
        return sequence_similarity(text1, text2)
    elif method == SimilarityMethod.COSINE:
        return cosine_similarity(text1, text2)
    elif method == SimilarityMethod.JACCARD:
        return jaccard_similarity(text1, text2)
    elif method == SimilarityMethod.LEVENSHTEIN:
        return levenshtein_similarity(text1, text2)
    elif method == SimilarityMethod.HYBRID:
        return hybrid_similarity(text1, text2)
    else:
        return sequence_similarity(text1, text2)


def ngram_similarity(
    text1: str,
    text2: str,
    n: int = 3
) -> float:
    """
    N-gram 相似度（用于检测局部相似）

    Args:
        text1: 第一个文本
        text2: 第二个文本
        n: N-gram 大小

    Returns:
        相似度百分比 (0-100)
    """
    if not text1 or not text2:
        return 0.0

    # 清理文本
    text1 = re.sub(r'\s+', '', text1)
    text2 = re.sub(r'\s+', '', text2)

    # 生成 N-gram
    def generate_ngrams(text, n):
        return [text[i:i+n] for i in range(len(text) - n + 1)]

    ngrams1 = set(generate_ngrams(text1, n))
    ngrams2 = set(generate_ngrams(text2, n))

    if not ngrams1 or not ngrams2:
        return 0.0

    # Jaccard 相似度
    intersection = ngrams1 & ngrams2
    union = ngrams1 | ngrams2

    if not union:
        return 0.0

    return (len(intersection) / len(union)) * 100


def find_similar_segments(
    text1: str,
    text2: str,
    threshold: float = 80.0,
    min_length: int = 20
) -> List[Dict]:
    """
    查找相似的文本片段（用于定位抄袭位置）

    Args:
        text1: 第一个文本
        text2: 第二个文本
        threshold: 相似度阈值
        min_length: 最小片段长度

    Returns:
        相似片段列表 [{'text1': ..., 'text2': ..., 'similarity': ..., 'start1': ..., 'start2': ...}]
    """
    # 按句子分割
    sentences1 = re.split(r'[。！？\n]', text1)
    sentences2 = re.split(r'[。！？\n]', text2)

    similar_segments = []

    for i, sent1 in enumerate(sentences1):
        if len(sent1.strip()) < min_length:
            continue

        for j, sent2 in enumerate(sentences2):
            if len(sent2.strip()) < min_length:
                continue

            sim = compute_similarity(sent1, sent2, SimilarityMethod.SEQUENCE)

            if sim >= threshold:
                similar_segments.append({
                    'text1': sent1.strip(),
                    'text2': sent2.strip(),
                    'similarity': sim,
                    'position1': i,
                    'position2': j
                })

    return similar_segments
