# -*- coding: utf-8 -*-
"""
查重系统配置
Plagiarism Detection Configuration

管理查重系统的各种权重、阈值和参数
"""
from dataclasses import dataclass, field
from typing import Dict, Optional
from pathlib import Path
import json


@dataclass
class SimilarityWeights:
    """相似度计算权重配置"""
    text: float = 0.5           # 文本相似度权重
    code: float = 0.3           # 代码相似度权重
    structure: float = 0.1      # 结构相似度权重
    semantic: float = 0.1       # 语义相似度权重

    def validate(self) -> bool:
        """验证权重总和为1"""
        total = sum([self.text, self.code, self.structure, self.semantic])
        return 0.99 <= total <= 1.01

    def normalize(self) -> 'SimilarityWeights':
        """标准化权重使其总和为1"""
        total = sum([self.text, self.code, self.structure, self.semantic])
        if total == 0:
            return SimilarityWeights()

        return SimilarityWeights(
            text=self.text / total,
            code=self.code / total,
            structure=self.structure / total,
            semantic=self.semantic / total
        )


@dataclass
class ThresholdConfig:
    """阈值配置"""
    suspicious: float = 60.0        # 可疑阈值
    high_similarity: float = 70.0   # 高相似度阈值
    plagiarism: float = 85.0        # 抄袭阈值
    paraphrase_min: float = 50.0    # 改写最小相似度
    paraphrase_max: float = 85.0    # 改写最大相似度
    code_similar: float = 85.0      # 代码相似阈值
    paragraph_similar: float = 80.0  # 段落相似阈值


@dataclass
class FeatureConfig:
    """功能开关配置"""
    enable_template_filter: bool = True       # 启用模板过滤
    enable_semantic_detection: bool = True    # 启用语义检测
    enable_code_obfuscation: bool = True      # 启用代码混淆检测
    enable_ai_detection: bool = False        # 启用AI生成检测（实验性）
    enable_image_similarity: bool = True      # 启用图片相似度检测
    enable_jieba: bool = True                 # 启用jieba分词

    # 语义检测方法配置
    semantic_method: str = 'auto'             # 'auto', 'tfidf', 'embedding'
    prefer_embedding: bool = False           # 优先使用嵌入模型（需要安装sentence-transformers）

    # AI检测配置
    ai_detection_threshold: float = 0.7       # AI生成判定阈值

    # NLP增强配置
    enable_nlp_enhancements: bool = True      # 启用NLP增强功能
    enable_fuzzy_matching: bool = True        # 启用模糊关键词匹配
    fuzzy_threshold: float = 0.85             # 模糊匹配阈值 (0.7-0.95)
    enable_term_variants: bool = True         # 启用术语变体词典
    enable_ast_analysis: bool = True          # 启用代码AST分析
    template_filter_strictness: float = 0.7   # 模板过滤严格程度 (0.5-0.9)


@dataclass
class PlagiarismConfig:
    """查重系统总配置"""
    weights: SimilarityWeights = field(default_factory=SimilarityWeights)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    features: FeatureConfig = field(default_factory=FeatureConfig)

    # 小组信息
    group_info: Dict[str, str] = field(default_factory=dict)

    # 模板内容
    template_content: str = ''

    def validate(self) -> bool:
        """验证配置"""
        return self.weights.validate()

    def normalize(self) -> 'PlagiarismConfig':
        """标准化配置"""
        return PlagiarismConfig(
            weights=self.weights.normalize(),
            thresholds=self.thresholds,
            features=self.features,
            group_info=self.group_info,
            template_content=self.template_content
        )

    @classmethod
    def from_json(cls, path: Path) -> 'PlagiarismConfig':
        """从JSON文件加载配置"""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return cls(
            weights=SimilarityWeights(**data.get('weights', {})),
            thresholds=ThresholdConfig(**data.get('thresholds', {})),
            features=FeatureConfig(**data.get('features', {})),
            group_info=data.get('group_info', {}),
            template_content=data.get('template_content', '')
        )

    def to_json(self, path: Path):
        """保存配置到JSON文件"""
        data = {
            'weights': {
                'text': self.weights.text,
                'code': self.weights.code,
                'structure': self.weights.structure,
                'semantic': self.weights.semantic
            },
            'thresholds': {
                'suspicious': self.thresholds.suspicious,
                'high_similarity': self.thresholds.high_similarity,
                'plagiarism': self.thresholds.plagiarism,
                'paraphrase_min': self.thresholds.paraphrase_min,
                'paraphrase_max': self.thresholds.paraphrase_max,
                'code_similar': self.thresholds.code_similar,
                'paragraph_similar': self.thresholds.paragraph_similar
            },
            'features': {
                'enable_template_filter': self.features.enable_template_filter,
                'enable_semantic_detection': self.features.enable_semantic_detection,
                'enable_code_obfuscation': self.features.enable_code_obfuscation,
                'enable_ai_detection': self.features.enable_ai_detection,
                'enable_image_similarity': self.features.enable_image_similarity,
                'enable_jieba': self.features.enable_jieba,
                'semantic_method': self.features.semantic_method,
                'prefer_embedding': self.features.prefer_embedding,
                'ai_detection_threshold': self.features.ai_detection_threshold,
                # NLP增强配置
                'enable_nlp_enhancements': self.features.enable_nlp_enhancements,
                'enable_fuzzy_matching': self.features.enable_fuzzy_matching,
                'fuzzy_threshold': self.features.fuzzy_threshold,
                'enable_term_variants': self.features.enable_term_variants,
                'enable_ast_analysis': self.features.enable_ast_analysis,
                'template_filter_strictness': self.features.template_filter_strictness
            },
            'group_info': self.group_info,
            'template_content': self.template_content
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# 默认配置实例
default_config = PlagiarismConfig()
