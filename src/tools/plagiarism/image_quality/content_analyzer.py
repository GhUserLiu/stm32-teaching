# -*- coding: utf-8 -*-
"""
内容分析器
Content Analyzer

分析图片内容类型，检测空白、截图等特征
"""

import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
from typing import List, Dict, Optional, Tuple
from enum import Enum
from dataclasses import dataclass


class ImageType(Enum):
    """图片类型"""
    PHOTO = 'photo'              # 实验照片
    CIRCUIT = 'circuit'          # 电路图/接线图
    CHART = 'chart'              # 图表/波形图
    SCREENSHOT = 'screenshot'    # 截图
    DIAGRAM = 'diagram'         # 原理图/框图
    TEXT_DOCUMENT = 'text_document'  # 文档截图
    BLANK = 'blank'             # 空白图片
    UNKNOWN = 'unknown'         # 未知类型


@dataclass
class ContentTypeResult:
    """内容类型检测结果"""
    image_type: ImageType           # 图片类型
    confidence: float               # 置信度 0-1
    features: Dict                  # 特征详情


@dataclass
class TextRegionResult:
    """文字区域检测结果"""
    has_text: bool                  # 是否包含文字
    text_ratio: float               # 文字区域占比
    text_regions: List[Dict]        # 文字区域列表
    is_likely_screenshot: bool      # 是否可能是截图


@dataclass
class BlankDetectionResult:
    """空白检测结果"""
    is_blank: bool                  # 是否为空白
    blank_ratio: float              # 空白占比 0-1
    dominant_color: Optional[Tuple] # 主色调


class ContentAnalyzer:
    """内容分析器"""

    # 截图特征模式
    SCREENSHOT_FEATURES = {
        'ui_elements': ['按钮', '菜单', '工具栏', 'statusbar', 'titlebar'],
        'window_patterns': ['最大化', '最小化', '关闭', '×', '—', '□'],
        'browser_elements': ['地址栏', '刷新', '后退', 'home', 'https://'],
    }

    # 电路图特征
    CIRCUIT_FEATURES = {
        'symbols': ['电阻', '电容', '电感', '二极管', '三极管', '芯片', 'IC'],
        'connections': ['连线', '导线', 'trace', 'net', 'bus'],
        'labels': ['VCC', 'GND', 'VDD', 'VSS', 'VIN', 'OUT'],
    }

    @staticmethod
    def analyze_type(image: Image.Image) -> ContentTypeResult:
        """
        分析图片类型

        Args:
            image: PIL图片对象

        Returns:
            内容类型检测结果
        """
        features = ContentAnalyzer._extract_features(image)

        # 基于特征判断类型
        image_type, confidence = ContentAnalyzer._classify_by_features(features)

        return ContentTypeResult(
            image_type=image_type,
            confidence=confidence,
            preferences=features
        )

    @staticmethod
    def _extract_features(image: Image.Image) -> Dict:
        """提取图片特征"""
        gray = image.convert('L')
        img_array = np.array(gray)

        # 计算基本特征
        features = {
            'edge_density': ContentAnalyzer._calculate_edge_density(img_array),
            'color_diversity': ContentAnalyzer._calculate_color_diversity(image),
            'brightness_variance': np.var(img_array),
            'aspect_ratio': image.size[0] / image.size[1],
            'size_category': ContentAnalyzer._categorize_size(image.size),
            'text_like_ratio': ContentAnalyzer._estimate_text_ratio(img_array),
        }

        # 检测直线（电路图、图表特征）
        features['line_count'] = ContentAnalyzer._count_lines(gray)

        # 检测曲线（波形图特征）
        features['curve_likelihood'] = ContentAnalyzer._detect_curves(gray)

        return features

    @staticmethod
    def _calculate_edge_density(img_array: np.ndarray) -> float:
        """计算边缘密度"""
        # 简单的边缘检测
        rows, cols = img_array.shape
        edge_count = 0

        for i in range(1, rows - 1):
            for j in range(1, cols - 1):
                # 检查梯度
                gradient = abs(int(img_array[i, j]) - int(img_array[i-1, j])) + \
                          abs(int(img_array[i, j]) - int(img_array[i, j-1]))
                if gradient > 30:
                    edge_count += 1

        return edge_count / (rows * cols)

    @staticmethod
    def _calculate_color_diversity(image: Image.Image) -> float:
        """计算颜色多样性"""
        # 如果是彩色图，计算颜色丰富度
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # 缩小图片加速处理
        small = image.resize((100, 100), Image.LANCZOS)
        colors = small.getcolors(maxcolors=10000)

        if colors:
            color_count = len(colors)
            total_pixels = sum(count for count, _ in colors)
            return color_count / total_pixels if total_pixels > 0 else 0
        return 0

    @staticmethod
    def _categorize_size(size: Tuple[int, int]) -> str:
        """分类图片尺寸"""
        width, height = size
        area = width * height

        if area < 300 * 200:
            return 'small'
        elif area < 800 * 600:
            return 'medium'
        elif area < 1920 * 1080:
            return 'large'
        else:
            return 'xlarge'

    @staticmethod
    def _estimate_text_ratio(img_array: np.ndarray) -> float:
        """估算文字占比（基于连通区域）"""
        # 二值化
        threshold = 128
        binary = (img_array > threshold).astype(int)

        # 简单的文字区域估计
        # 检查水平和垂直的过渡
        rows, cols = img_array.shape
        text_regions = 0

        for i in range(0, rows - 1, 5):  # 采样
            for j in range(0, cols - 1, 5):
                # 检查局部对比度
                local_area = binary[i:i+5, j:j+5]
                if np.sum(local_area) > 0 and np.sum(local_area) < 25:
                    text_regions += 1

        total_samples = (rows // 5) * (cols // 5)
        return text_regions / total_samples if total_samples > 0 else 0

    @staticmethod
    def _count_lines(image: Image.Image) -> int:
        """检测直线数量（使用霍夫变换的简化版）"""
        # 简化版：检测水平和垂直线
        img_array = np.array(image.convert('L'))

        # 水平线检测
        h_lines = 0
        for row in img_array:
            # 检查是否有长的水平线
            edges = np.abs(np.diff(row.astype(int))) > 50
            if np.sum(edges) > img_array.shape[1] * 0.3:
                h_lines += 1

        # 垂直线检测
        v_lines = 0
        for col in img_array.T:
            edges = np.abs(np.diff(col.astype(int))) > 50
            if np.sum(edges) > img_array.shape[0] * 0.3:
                v_lines += 1

        return h_lines + v_lines

    @staticmethod
    def _detect_curves(image: Image.Image) -> float:
        """检测曲线可能性"""
        # 简化版：检测非直线边缘
        img_array = np.array(image.convert('L'))

        # 计算梯度的方向变化
        from scipy.ndimage import sobel
        try:
            gx = sobel(img_array, axis=1)
            gy = sobel(img_array, axis=0)

            # 计算方向一致性
            angles = np.arctan2(gy, gx)
            angle_variance = np.var(angles[~np.isnan(angles)])

            # 高方差表示有曲线
            return min(1.0, angle_variance / (np.pi / 4))
        except ImportError:
            # 无scipy时的简化处理
            return 0.5

    @staticmethod
    def _classify_by_features(features: Dict) -> Tuple[ImageType, float]:
        """基于特征分类图片类型"""
        # 规则分类
        edge_density = features['edge_density']
        line_count = features['line_count']
        curve_likelihood = features['curve_likelihood']
        text_like_ratio = features['text_like_ratio']

        # 空白检测
        if edge_density < 0.05 and features['brightness_variance'] < 100:
            return ImageType.BLANK, 0.9

        # 截图检测（高文字占比 + 特定长宽比）
        if text_like_ratio > 0.3 and features['aspect_ratio'] > 1.2:
            return ImageType.SCREENSHOT, 0.7
        if text_like_ratio > 0.5:
            return ImageType.TEXT_DOCUMENT, 0.8

        # 图表/波形图（曲线 + 规则结构）
        if curve_likelihood > 0.6 and line_count > 5:
            return ImageType.CHART, 0.7

        # 电路图（大量直线 + 低颜色多样性）
        if line_count > 20 and features['color_diversity'] < 0.3:
            return ImageType.CIRCUIT, 0.75

        # 照片（高边缘密度 + 高颜色多样性）
        if edge_density > 0.2 and features['color_diversity'] > 0.4:
            return ImageType.PHOTO, 0.7

        # 原理图（中等边缘 + 中等直线）
        if 0.1 < edge_density < 0.3 and 10 < line_count < 30:
            return ImageType.DIAGRAM, 0.6

        return ImageType.UNKNOWN, 0.3

    @staticmethod
    def detect_text_regions(image: Image.Image) -> TextRegionResult:
        """
        检测文字区域

        Args:
            image: PIL图片对象

        Returns:
            文字区域检测结果
        """
        gray = image.convert('L')
        img_array = np.array(gray)

        # 使用形态学操作检测文字区域
        # 简化版：检测高对比度的小区域

        # 二值化
        threshold = 128
        binary = (img_array < threshold).astype(int)

        # 统计黑色像素聚集度
        text_ratio = np.sum(binary) / binary.size

        # 判断是否有文字
        has_text = text_ratio > 0.1 and text_ratio < 0.9

        # 判断是否可能是截图
        # 截图通常有规整的边缘和文字
        aspect_ratio = image.size[0] / image.size[1]
        is_likely_screenshot = (
            has_text and
            (1.3 < aspect_ratio < 1.8 or 0.5 < aspect_ratio < 0.8)
        )

        return TextRegionResult(
            has_text=has_text,
            text_ratio=text_ratio,
            text_regions=[],
            is_likely_screenshot=is_likely_screenshot
        )

    @staticmethod
    def detect_blank(image: Image.Image) -> BlankDetectionResult:
        """
        检测是否为空白图片

        Args:
            image: PIL图片对象

        Returns:
            空白检测结果
        """
        # 转换为numpy数组
        img_array = np.array(image)

        # 如果是彩色图，取第一个通道
        if len(img_array.shape) == 3:
            img_array = img_array[:, :, 0]

        # 计算方差
        variance = np.var(img_array)

        # 计算空白占比（接近背景色的像素）
        mean_color = np.mean(img_array)
        threshold = 10  # 容差
        blank_pixels = np.sum(np.abs(img_array - mean_color) < threshold)
        blank_ratio = blank_pixels / img_array.size

        # 判断是否为空白
        is_blank = variance < 100 or blank_ratio > 0.95

        # 获取主色调
        if len(image.getbands()) == 1:
            dominant_color = (int(mean_color), int(mean_color), int(mean_color))
        else:
            # 彩色图，简化处理
            dominant_color = None

        return BlankDetectionResult(
            is_blank=is_blank,
            blank_ratio=blank_ratio,
            dominant_color=dominant_color
        )

    @staticmethod
    def detect_screenshot_pattern(image: Image.Image) -> bool:
        """
        检测截图特征

        Args:
            image: PIL图片对象

        Returns:
            是否可能是截图
        """
        # 检查是否有典型的截图特征
        # 1. 检查边缘是否有UI元素（简化版：检查规整的边框）

        gray = image.convert('L')
        img_array = np.array(gray)

        # 检查顶部和底部是否有深色区域（可能是标题栏）
        top_section = img_array[:20, :]
        bottom_section = img_array[-20:, :]

        top_dark = np.mean(top_section) < 100
        bottom_dark = np.mean(bottom_section) < 100

        # 检查长宽比
        width, height = image.size
        aspect_ratio = width / height

        # 截图通常有特定比例
        typical_ratio = 0.8 < aspect_ratio < 1.8

        return (top_dark or bottom_dark) and typical_ratio
