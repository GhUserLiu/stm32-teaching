# -*- coding: utf-8 -*-
"""
图片相似度检测器
Image Similarity Detector

检测图片相似度，用于查重实验报告中的截图
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
from PIL import Image
import io

from .hash import ImageHasher, HashType


@dataclass
class ImageSimilarityResult:
    """图片相似度检测结果"""
    similarity: float               # 相似度 0-1
    is_similar: bool                # 是否相似
    hash_distance: int              # 哈希距离
    hash_type: HashType             # 哈希类型
    image1_path: str
    image2_path: str
    image1_hash: str = ''
    image2_hash: str = ''


class ImageDetector:
    """图片相似度检测器"""

    def __init__(
        self,
        hash_algorithm: str = 'dhash',
        similarity_threshold: float = 0.85
    ):
        """
        初始化检测器

        Args:
            hash_algorithm: 哈希算法 ('ahash', 'dhash', 'phash')
            similarity_threshold: 相似度阈值
        """
        self.hash_type = HashType(hash_algorithm)
        self.threshold = similarity_threshold
        self.hasher = ImageHasher()

    def detect(
        self,
        image_path1: str,
        image_path2: str
    ) -> ImageSimilarityResult:
        """
        检测图片相似度

        Args:
            image_path1: 图片1路径
            image_path2: 图片2路径

        Returns:
            图片相似度检测结果
        """
        # 加载图片
        img1 = self._load_image(image_path1)
        img2 = self._load_image(image_path2)

        if img1 is None or img2 is None:
            return ImageSimilarityResult(
                similarity=0.0,
                is_similar=False,
                hash_distance=999,
                hash_type=self.hash_type,
                image1_path=image_path1,
                image2_path=image_path2
            )

        # 计算哈希
        hash1 = self.hasher.calculate_hash(img1, self.hash_type)
        hash2 = self.hasher.calculate_hash(img2, self.hash_type)

        # 计算距离
        distance = self.hasher.hamming_distance(hash1, hash2)

        # 计算相似度
        max_distance = len(hash1)
        similarity = self.hasher.hash_to_similarity(hash1, hash2, max_distance)

        # 判断是否相似
        is_similar = similarity >= self.threshold

        return ImageSimilarityResult(
            similarity=similarity,
            is_similar=is_similar,
            hash_distance=distance,
            hash_type=self.hash_type,
            image1_path=image_path1,
            image2_path=image_path2,
            image1_hash=hash1,
            image2_hash=hash2
        )

    def batch_detect_images(
        self,
        submission1: Dict,
        submission2: Dict
    ) -> Dict[str, ImageSimilarityResult]:
        """
        批量检测提交中的图片

        Args:
            submission1: 提交1 {'docx_path': str, 'images': [str], ...}
            submission2: 提交2

        Returns:
            {图片对key: 相似度结果}
        """
        results = {}

        # 获取图片列表
        images1 = submission1.get('images', [])
        images2 = submission2.get('images', [])

        # 如果有docx路径，尝试提取图片
        if not images1 and 'docx_path' in submission1:
            images1 = self.extract_images_from_docx(submission1['docx_path'])
        if not images2 and 'docx_path' in submission2:
            images2 = self.extract_images_from_docx(submission2['docx_path'])

        # 两两比较
        for i, img1 in enumerate(images1):
            for j, img2 in enumerate(images2):
                result = self.detect(img1, img2)
                if result.is_similar:
                    key = f"{i}_{j}"
                    results[key] = result

        return results

    def extract_images_from_docx(self, docx_path: str) -> List[str]:
        """
        从Word文档提取图片

        Args:
            docx_path: Word文档路径

        Returns:
            提取的图片路径列表
        """
        try:
            from docx import Document
        except ImportError:
            return []

        images = []
        doc = Document(docx_path)

        # 创建临时目录
        temp_dir = Path(docx_path).parent / 'temp_images'
        temp_dir.mkdir(exist_ok=True)

        # 提取图片
        image_index = 0
        for rel in doc.part.rels.values():
            if "image" in rel.target_ref:
                try:
                    image_data = rel.target_blob
                    image_ext = rel.target_ref.split('.')[-1]
                    image_path = temp_dir / f"image_{image_index}.{image_ext}"

                    with open(image_path, 'wb') as f:
                        f.write(image_data)

                    images.append(str(image_path))
                    image_index += 1
                except Exception:
                    continue

        return images

    def extract_images_from_text(self, text: str, image_dir: Path) -> List[str]:
        """
        从文本中提取图片路径

        Args:
            text: 文本内容
            image_dir: 图片目录

        Returns:
            图片路径列表
        """
        import re

        # 匹配图片路径模式
        patterns = [
            r'!\[.*?\]\(([^)]+)\)',  # Markdown
            r'<img[^>]+src=["\']([^"\']+)["\']',  # HTML
            r'图片[:：]?[：\s]*([^\s]+\.(png|jpg|jpeg|gif|bmp))',  # 中文描述
        ]

        images = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    path = match[0]
                else:
                    path = match

                # 转换为绝对路径
                image_path = Path(text)
                if not image_path.is_absolute():
                    image_path = image_dir / path

                if image_path.exists():
                    images.append(str(image_path))

        return images

    def _load_image(self, image_path: str) -> Optional[Image.Image]:
        """加载图片"""
        try:
            return Image.open(image_path)
        except Exception:
            return None

    def detect_visual_duplicates(
        self,
        images: List[str]
    ) -> List[Tuple[str, str, float]]:
        """
        检测视觉重复图片

        Args:
            images: 图片路径列表

        Returns:
            [(图片1, 图片2, 相似度), ...]
        """
        duplicates = []

        for i in range(len(images)):
            for j in range(i + 1, len(images)):
                result = self.detect(images[i], images[j])
                if result.is_similar:
                    duplicates.append((
                        images[i],
                        images[j],
                        result.similarity
                    ))

        # 按相似度排序
        duplicates.sort(key=lambda x: x[2], reverse=True)

        return duplicates
