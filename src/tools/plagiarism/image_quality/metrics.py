# -*- coding: utf-8 -*-
"""
质量指标计算器
Quality Metrics Calculator

计算图片的各种质量指标：清晰度、亮度、对比度、噪点等
"""

import numpy as np
from PIL import Image
from typing import Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class SharpnessResult:
    """清晰度检测结果"""
    score: float                  # 清晰度分数 0-100
    method: str                   # 使用的检测方法
    laplacian_variance: float     # 拉普拉斯方差值
    edge_density: float           # 边缘密度


@dataclass
class BrightnessResult:
    """亮度检测结果"""
    score: float                  # 亮度分数 0-100
    mean_brightness: float        # 平均亮度 0-255
    is_too_dark: bool             # 是否过暗
    is_too_bright: bool           # 是否过亮
    histogram: Dict               # 直方图数据


@dataclass
class ContrastResult:
    """对比度检测结果"""
    score: float                  # 对比度分数 0-100
    standard_deviation: float     # 标准差
    dynamic_range: float          # 动态范围
    rms_contrast: float           # RMS对比度


@dataclass
class ResolutionResult:
    """分辨率检测结果"""
    score: float                  # 分数 0-100
    width: int                    # 宽度
    height: int                   # 高度
    is_adequate: bool             # 是否足够
    megapixels: float             # 百万像素数


class QualityMetrics:
    """质量指标计算器"""

    # 清晰度阈值
    SHARPNESS_THRESHOLDS = {
        'excellent': 100.0,
        'good': 50.0,
        'acceptable': 20.0,
        'poor': 10.0
    }

    # 亮度阈值
    BRIGHTNESS_THRESHOLDS = {
        'too_dark': 50.0,         # 过暗
        'dark': 100.0,
        'optimal_min': 120.0,     # 最佳范围
        'optimal_max': 200.0,
        'bright': 220.0,
        'too_bright': 240.0       # 过亮
    }

    # 对比度阈值
    CONTRAST_THRESHOLDS = {
        'excellent': 60.0,
        'good': 45.0,
        'acceptable': 30.0,
        'poor': 15.0
    }

    # 分辨率要求
    MIN_RESOLUTION = (640, 480)    # 最低可接受分辨率
    OPTIMAL_RESOLUTION = (1280, 960)  # 最佳分辨率

    @staticmethod
    def calculate_sharpness(image: Image.Image) -> SharpnessResult:
        """
        计算清晰度（使用拉普拉斯算子）

        Args:
            image: PIL图片对象

        Returns:
            清晰度检测结果
        """
        # 转换为灰度图
        gray = image.convert('L')

        # 转换为numpy数组
        img_array = np.array(gray)

        # 应用拉普拉斯算子
        laplacian = np.array([
            [0, 1, 0],
            [1, -4, 1],
            [0, 1, 0]
        ])

        # 卷积运算
        from scipy.signal import convolve2d
        try:
            edges = convolve2d(img_array, laplacian, mode='same', boundary='symm')
        except ImportError:
            # 如果没有scipy，使用简单的边缘检测
            edges = QualityMetrics._simple_edge_detection(img_array)

        # 计算方差
        variance = np.var(edges)

        # 计算边缘密度
        edge_pixels = np.count_nonzero(edges > 50)
        edge_density = edge_pixels / (img_array.shape[0] * img_array.shape[1])

        # 计算清晰度分数
        score = QualityMetrics._sharpness_variance_to_score(variance)

        return SharpnessResult(
            score=score,
            method='laplacian',
            laplacian_variance=variance,
            edge_density=edge_density
        )

    @staticmethod
    def _simple_edge_detection(img_array: np.ndarray) -> np.ndarray:
        """简单的边缘检测（无scipy时的备选方案）"""
        # 使用Sobel算子
        sobel_x = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]])
        sobel_y = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]])

        # 简单卷积
        rows, cols = img_array.shape
        edges = np.zeros_like(img_array, dtype=float)

        for i in range(1, rows - 1):
            for j in range(1, cols - 1):
                gx = np.sum(img_array[i-1:i+2, j-1:j+2] * sobel_x)
                gy = np.sum(img_array[i-1:i+2, j-1:j+2] * sobel_y)
                edges[i, j] = np.sqrt(gx**2 + gy**2)

        return edges

    @staticmethod
    def _sharpness_variance_to_score(variance: float) -> float:
        """将拉普拉斯方差转换为清晰度分数"""
        if variance >= QualityMetrics.SHARPNESS_THRESHOLDS['excellent']:
            return min(100, 60 + (variance - 100) / 10)
        elif variance >= QualityMetrics.SHARPNESS_THRESHOLDS['good']:
            return 60 + (variance - 50) / 50 * 30
        elif variance >= QualityMetrics.SHARPNESS_THRESHOLDS['acceptable']:
            return 30 + (variance - 20) / 30 * 30
        elif variance >= QualityMetrics.SHARPNESS_THRESHOLDS['poor']:
            return (variance - 10) / 10 * 30
        else:
            return max(0, variance)

    @staticmethod
    def calculate_brightness(image: Image.Image) -> BrightnessResult:
        """
        计算亮度分析

        Args:
            image: PIL图片对象

        Returns:
            亮度检测结果
        """
        # 转换为灰度图
        gray = image.convert('L')
        img_array = np.array(gray)

        # 计算平均亮度
        mean_brightness = np.mean(img_array)

        # 判断是否过暗或过亮
        is_too_dark = mean_brightness < QualityMetrics.BRIGHTNESS_THRESHOLDS['too_dark']
        is_too_bright = mean_brightness > QualityMetrics.BRIGHTNESS_THRESHOLDS['too_bright']

        # 计算直方图
        hist, bins = np.histogram(img_array.flatten(), bins=256, range=[0, 256])
        histogram = {'bins': bins.tolist(), 'counts': hist.tolist()}

        # 计算亮度分数
        score = QualityMetrics._brightness_to_score(mean_brightness)

        return BrightnessResult(
            score=score,
            mean_brightness=mean_brightness,
            is_too_dark=is_too_dark,
            is_too_bright=is_too_bright,
            histogram=histogram
        )

    @staticmethod
    def _brightness_to_score(mean_brightness: float) -> float:
        """将平均亮度转换为分数"""
        optimal_min = QualityMetrics.BRIGHTNESS_THRESHOLDS['optimal_min']
        optimal_max = QualityMetrics.BRIGHTNESS_THRESHOLDS['optimal_max']

        if optimal_min <= mean_brightness <= optimal_max:
            # 最佳范围，100分
            return 100.0
        elif mean_brightness < optimal_min:
            # 过暗，线性扣分
            dark_threshold = QualityMetrics.BRIGHTNESS_THRESHOLDS['too_dark']
            if mean_brightness <= dark_threshold:
                return 0.0
            ratio = (mean_brightness - dark_threshold) / (optimal_min - dark_threshold)
            return ratio * 80
        else:
            # 过亮，线性扣分
            bright_threshold = QualityMetrics.BRIGHTNESS_THRESHOLDS['too_bright']
            if mean_brightness >= bright_threshold:
                return 0.0
            ratio = (bright_threshold - mean_brightness) / (bright_threshold - optimal_max)
            return ratio * 80

    @staticmethod
    def calculate_contrast(image: Image.Image) -> ContrastResult:
        """
        计算对比度

        Args:
            image: PIL图片对象

        Returns:
            对比度检测结果
        """
        # 转换为灰度图
        gray = image.convert('L')
        img_array = np.array(gray, dtype=float)

        # 计算标准差
        std_dev = np.std(img_array)

        # 计算动态范围
        dynamic_range = np.max(img_array) - np.min(img_array)

        # 计算RMS对比度
        rms_contrast = std_dev / np.mean(img_array) if np.mean(img_array) > 0 else 0

        # 计算对比度分数
        score = QualityMetrics._contrast_to_score(std_dev)

        return ContrastResult(
            score=score,
            standard_deviation=std_dev,
            dynamic_range=dynamic_range,
            rms_contrast=rms_contrast
        )

    @staticmethod
    def _contrast_to_score(std_dev: float) -> float:
        """将标准差转换为对比度分数"""
        if std_dev >= QualityMetrics.CONTRAST_THRESHOLDS['excellent']:
            return 100.0
        elif std_dev >= QualityMetrics.CONTRAST_THRESHOLDS['good']:
            return 80 + (std_dev - 45) / 15 * 20
        elif std_dev >= QualityMetrics.CONTRAST_THRESHOLDS['acceptable']:
            return 50 + (std_dev - 30) / 15 * 30
        elif std_dev >= QualityMetrics.CONTRAST_THRESHOLDS['poor']:
            return (std_dev - 15) / 15 * 50
        else:
            return max(0, std_dev / 15 * 50)

    @staticmethod
    def detect_noise(image: Image.Image) -> float:
        """
        检测噪点水平

        Args:
            image: PIL图片对象

        Returns:
            噪点水平 0-1（1表示噪点很多）
        """
        # 转换为灰度图
        gray = image.convert('L')
        img_array = np.array(gray, dtype=float)

        # 使用高频分量估计噪点
        # 简单方法：平滑后比较差异
        from scipy.ndimage import gaussian_filter
        try:
            smoothed = gaussian_filter(img_array, sigma=2)
            noise = np.mean(np.abs(img_array - smoothed))
        except ImportError:
            # 备选方案：使用简单的邻域平均
            smoothed = QualityMetrics._simple_smooth(img_array)
            noise = np.mean(np.abs(img_array - smoothed))

        # 归一化到0-1
        noise_level = min(1.0, noise / 50.0)

        return noise_level

    @staticmethod
    def _simple_smooth(img_array: np.ndarray) -> np.ndarray:
        """简单的平滑滤波（无scipy时的备选方案）"""
        rows, cols = img_array.shape
        smoothed = np.zeros_like(img_array)

        for i in range(1, rows - 1):
            for j in range(1, cols - 1):
                # 3x3邻域平均
                neighborhood = img_array[i-1:i+2, j-1:j+2]
                smoothed[i, j] = np.mean(neighborhood)

        return smoothed

    @staticmethod
    def check_resolution(
        image: Image.Image,
        min_size: Tuple[int, int] = None
    ) -> ResolutionResult:
        """
        检查分辨率

        Args:
            image: PIL图片对象
            min_size: 最小尺寸要求 (width, height)

        Returns:
            分辨率检测结果
        """
        if min_size is None:
            min_size = QualityMetrics.MIN_RESOLUTION

        width, height = image.size
        is_adequate = width >= min_size[0] and height >= min_size[1]

        # 计算百万像素数
        megapixels = (width * height) / 1_000_000

        # 计算分数
        optimal_width, optimal_height = QualityMetrics.OPTIMAL_RESOLUTION
        if width >= optimal_width and height >= optimal_height:
            score = 100.0
        elif is_adequate:
            # 根据接近最优的程度给分
            width_ratio = width / optimal_width
            height_ratio = height / optimal_height
            score = min(width_ratio, height_ratio) * 100
        else:
            # 分辨率不足
            width_ratio = width / min_size[0]
            height_ratio = height / min_size[1]
            score = min(width_ratio, height_ratio) * 50

        return ResolutionResult(
            score=max(0, min(100, score)),
            width=width,
            height=height,
            is_adequate=is_adequate,
            megapixels=megapixels
        )

    @staticmethod
    def calculate_all_metrics(image: Image.Image) -> Dict:
        """
        计算所有质量指标

        Args:
            image: PIL图片对象

        Returns:
            所有指标的字典
        """
        return {
            'sharpness': QualityMetrics.calculate_sharpness(image),
            'brightness': QualityMetrics.calculate_brightness(image),
            'contrast': QualityMetrics.calculate_contrast(image),
            'noise': QualityMetrics.detect_noise(image),
            'resolution': QualityMetrics.check_resolution(image)
        }
