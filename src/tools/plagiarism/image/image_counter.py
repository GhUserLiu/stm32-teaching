#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
图片数量检测器
Image Counter for Grading

检测报告中的图片数量，用于评分
"""

import re
from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path


@dataclass
class ImageCountResult:
    """图片检测结果"""
    image_count: int
    score: float
    max_score: float
    passed: bool
    details: List[str]
    summary: str


class ImageCounter:
    """图片数量检测器"""

    # 图片相关关键词
    IMAGE_KEYWORDS = [
        '图', '图片', '照片', '截图', '接线图', '电路图', '原理图',
        '连接图', '硬件图', '波形图', '示波器', 'LED状态',
        'figure', 'fig', 'image', 'img', 'photo', 'picture'
    ]

    # 图片标记模式
    IMAGE_PATTERNS = [
        r'图\s*\d+[.、．]',           # 图1、图2.
        r'Figure\s*\d+',              # Figure 1
        r'Fig\.\s*\d+',              # Fig. 1
        r'\[图片?[^\]]*\]',          # [图片]标记
        r'\[图片?\d*\]',             # [图1]
        r'(?:接线|电路|原理)图',      # 接线图、电路图、原理图
        r'截图[：:]?\s*(\d+)?',      # 截图: 或 截图1
    ]

    def __init__(self):
        """初始化检测器"""
        pass

    def count_from_text(self, text: str) -> int:
        """
        从文本中统计图片数量

        Args:
            text: 报告文本

        Returns:
            图片数量
        """
        count = 0

        # 方法1: 检测图片标记
        for pattern in self.IMAGE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            count += len(matches)

        # 方法2: 检测图片相关关键词出现的段落
        lines = text.split('\n')
        image_lines = 0

        for line in lines:
            line_lower = line.lower()
            # 检查是否包含图片关键词
            if any(keyword.lower() in line_lower for keyword in self.IMAGE_KEYWORDS):
                # 进一步检查是否真的在描述图片
                if any(word in line for word in ['如下', '所示', '见图', '见图中', '显示']):
                    image_lines += 1

        # 取两种方法的较大值，避免重复计数
        count = max(count, image_lines)

        return count

    def count_from_docx(self, docx_path: Path) -> int:
        """
        从Word文档中统计图片数量

        Args:
            docx_path: Word文档路径

        Returns:
            图片数量
        """
        try:
            from docx import Document

            # 安全前置校验：python-docx 会把 .docx 当作 zip 直接打开，绕过
            # security/ 的 zip 炸弹/尺寸/文件数防护。先用安全包装校验通过再解析，
            # 与 submission_processor._read_report（safe_extract_text_from_docx）同口径。
            # 校验不过→抛 ZipValidationError→外层 except 退化为 0（与既有失败口径一致）。
            from ...security.zip_validator import validate_zip_size, ZipLimits
            import zipfile as _zf
            _limits = ZipLimits()
            docx_path = Path(docx_path)
            if docx_path.stat().st_size > _limits.max_outer_size:
                print(f"[警告] docx 过大，跳过图片统计: {docx_path.name} "
                      f"({docx_path.stat().st_size:,} bytes)")
                return 0
            with _zf.ZipFile(docx_path, 'r') as _zf_check:
                validate_zip_size(_zf_check, _limits)

            doc = Document(docx_path)
            image_count = 0

            # 方法1: 检查文档关系中的图片
            for rel in doc.part.rels.values():
                if "image" in rel.target_ref:
                    image_count += 1

            # 方法2: 检查段落中的图片引用
            for paragraph in doc.paragraphs:
                for run in paragraph.runs:
                    if hasattr(run, '_element') and run._element.xpath('.//pic:pic'):
                        image_count += 1

            return image_count

        except Exception as e:
            print(f"[警告] 无法从Word文档提取图片: {e}")
            return 0

    def grade(
        self,
        text: str = None,
        docx_path: Path = None,
        min_images: int = 3,
        scoring_rules: Dict[int, int] = None
    ) -> ImageCountResult:
        """
        评估图片得分

        Args:
            text: 报告文本
            docx_path: Word文档路径
            min_images: 最少图片数量
            scoring_rules: 得分规则 {数量: 得分}
                例如: {0: 0, 1: 1, 2: 3, 3: 5, 4: 5}

        Returns:
            评估结果
        """
        # 默认评分规则
        if scoring_rules is None:
            scoring_rules = {
                0: 0,
                1: 1,
                2: 3,
                3: 5,
                4: 5,
                5: 5
            }

        # 统计图片数量
        count = 0

        if docx_path:
            count = self.count_from_docx(docx_path)

        if text:
            text_count = self.count_from_text(text)
            count = max(count, text_count)  # 取较大值

        # 计算得分
        score = scoring_rules.get(0, 0)  # 默认0分
        for img_count, pts in sorted(scoring_rules.items()):
            if count >= img_count:
                score = pts

        max_score = max(scoring_rules.values()) if scoring_rules else 5
        passed = count >= min_images

        # 生成详情
        details = [
            f"检测到图片数量: {count}张"
        ]

        if count < min_images:
            details.append(f"最少需要{min_images}张图片，当前{count}张")
        else:
            details.append(f"图片数量符合要求")

        # 检测图片类型
        if text:
            types = self._detect_image_types(text)
            if types:
                details.append(f"图片类型: {', '.join(types)}")

        # 生成总结
        summary = f"图片得分: {score}/{max_score}"
        if passed:
            summary += " (符合要求)"
        else:
            summary += f" (缺少{min_images - count}张)"

        return ImageCountResult(
            image_count=count,
            score=score,
            max_score=max_score,
            passed=passed,
            details=details,
            summary=summary
        )

    def _detect_image_types(self, text: str) -> List[str]:
        """检测图片类型"""
        types = []

        if '接线图' in text or '电路图' in text:
            types.append('接线图')
        if '截图' in text:
            types.append('截图')
        if '照片' in text or '实物图' in text:
            types.append('实物照片')
        if '波形' in text or '示波器' in text:
            types.append('波形图')
        if '流程图' in text or '框图' in text:
            types.append('流程图')

        return types


def check_image_count(
    text: str = None,
    docx_path: Path = None,
    min_images: int = 3,
    max_score: int = 5
) -> ImageCountResult:
    """
    检查图片数量的便捷函数

    Args:
        text: 报告文本
        docx_path: Word文档路径
        min_images: 最少图片数量
        max_score: 最高得分

    Returns:
        检测结果
    """
    counter = ImageCounter()

    # 动态生成评分规则
    step = max_score / (min_images + 1)
    scoring_rules = {}
    current = 0

    for i in range(min_images + 2):
        scoring_rules[i] = min(int(current), max_score)
        current += step

    # 确保达到最少数量给满分
    for i in range(min_images, min_images + 10):
        scoring_rules[i] = max_score

    return counter.grade(
        text=text,
        docx_path=docx_path,
        min_images=min_images,
        scoring_rules=scoring_rules
    )
