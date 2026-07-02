# -*- coding: utf-8 -*-
"""
实验报告验证器
Lab Report Validators

针对实验报告的特定图片类型进行质量验证
"""

import numpy as np
from PIL import Image, ImageFilter
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class CircuitDiagramResult:
    """电路图验证结果"""
    is_valid: bool                 # 是否有效
    clarity_score: float           # 清晰度分数
    has_labels: bool              # 是否有标注
    line_completeness: float      # 连线完整性
    issues: List[str]             # 问题列表


@dataclass
class ExperimentPhotoResult:
    """实验照片验证结果"""
    is_valid: bool                 # 是否有效
    clarity_score: float           # 清晰度分数
    shows_hardware: bool           # 是否显示硬件
    shows_action: bool             # 是否显示操作
    lighting_quality: float        # 光照质量
    issues: List[str]             # 问题列表


@dataclass
class WaveformResult:
    """波形图验证结果"""
    is_valid: bool                 # 是否有效
    clarity_score: float           # 清晰度分数
    has_axis_labels: bool          # 是否有坐标轴标注
    has_grid: bool                 # 是否有网格
    signal_quality: float          # 信号质量
    issues: List[str]             # 问题列表


class LabReportValidator:
    """实验报告特定验证器"""

    # 电路图验证阈值
    CIRCUIT_MIN_EDGE_DENSITY = 0.15
    CIRCUIT_MIN_LINE_COUNT = 10

    # 实验照片验证阈值
    PHOTO_MIN_EDGE_DENSITY = 0.1
    PHOTO_MIN_BRIGHTNESS = 80
    PHOTO_MAX_BRIGHTNESS = 200

    # 波形图验证阈值
    WAVEFORM_MIN_EDGE_DENSITY = 0.2

    @staticmethod
    def validate_circuit_diagram(image: Image.Image) -> CircuitDiagramResult:
        """
        验证电路图质量

        Args:
            image: PIL图片对象

        Returns:
            电路图验证结果
        """
        from .metrics import QualityMetrics
        from .content_analyzer import ContentAnalyzer

        issues = []

        # 转换为灰度图
        gray = image.convert('L')
        img_array = np.array(gray)

        # 计算边缘密度
        edge_density = LabReportValidator._calculate_edge_density(img_array)

        # 检查清晰度
        sharpness = QualityMetrics.calculate_sharpness(image)
        clarity_score = sharpness.score

        if clarity_score < 40:
            issues.append("电路图清晰度不足，线条模糊")

        # 检查连线完整性（简化版：检查边缘连续性）
        line_completeness = LabReportValidator._check_line_completeness(img_array)
        if line_completeness < 0.6:
            issues.append("电路连线可能不完整")

        # 检查是否有标注（检测文字区域）
        text_result = ContentAnalyzer.detect_text_regions(image)
        has_labels = text_result.has_text

        if not has_labels:
            issues.append("电路图缺少标注（引脚、元件名称等）")

        # 综合判断
        is_valid = (
            clarity_score >= 30 and
            line_completeness >= 0.4 and
            edge_density >= LabReportValidator.CIRCUIT_MIN_EDGE_DENSITY
        )

        return CircuitDiagramResult(
            is_valid=is_valid,
            clarity_score=clarity_score,
            has_labels=has_labels,
            line_completeness=line_completeness,
            issues=issues
        )

    @staticmethod
    def validate_experiment_photo(image: Image.Image) -> ExperimentPhotoResult:
        """
        验证实验照片质量

        Args:
            image: PIL图片对象

        Returns:
            实验照片验证结果
        """
        from .metrics import QualityMetrics

        issues = []

        # 计算清晰度
        sharpness = QualityMetrics.calculate_sharpness(image)
        clarity_score = sharpness.score

        if clarity_score < 30:
            issues.append("照片清晰度不足，可能模糊")

        # 检查光照质量
        brightness = QualityMetrics.calculate_brightness(image)

        if brightness.is_too_dark:
            issues.append("照片过暗，难以看清细节")
            lighting_quality = 0.3
        elif brightness.is_too_bright:
            issues.append("照片过亮，可能曝光过度")
            lighting_quality = 0.5
        else:
            lighting_quality = 0.9

        # 检查对比度
        contrast = QualityMetrics.calculate_contrast(image)
        if contrast.score < 40:
            issues.append("照片对比度较低，细节不明显")

        # 检查是否显示硬件（检测规整形状和电子元件特征）
        shows_hardware = LabReportValidator._detect_hardware_features(image)

        if not shows_hardware:
            issues.append("照片可能未显示硬件/实验板")

        # 检查是否显示操作（难以自动判断，给中等分数）
        shows_action = True  # 默认假设有

        # 综合判断
        is_valid = (
            clarity_score >= 25 and
            lighting_quality >= 0.4 and
            contrast.score >= 30
        )

        return ExperimentPhotoResult(
            is_valid=is_valid,
            clarity_score=clarity_score,
            shows_hardware=shows_hardware,
            shows_action=shows_action,
            lighting_quality=lighting_quality,
            issues=issues
        )

    @staticmethod
    def validate_waveform_chart(image: Image.Image) -> WaveformResult:
        """
        验证波形图质量

        Args:
            image: PIL图片对象

        Returns:
            波形图验证结果
        """
        from .metrics import QualityMetrics

        issues = []

        # 计算清晰度
        sharpness = QualityMetrics.calculate_sharpness(image)
        clarity_score = sharpness.score

        if clarity_score < 40:
            issues.append("波形图清晰度不足")

        # 转换为灰度图
        gray = image.convert('L')
        img_array = np.array(gray)

        # 检查边缘密度（波形应该有清晰的边缘）
        edge_density = LabReportValidator._calculate_edge_density(img_array)

        if edge_density < LabReportValidator.WAVEFORM_MIN_EDGE_DENSITY:
            issues.append("波形边缘不清晰")

        # 检查是否有网格（检测规则的水平垂直线）
        has_grid = LabReportValidator._detect_grid_pattern(img_array)

        if not has_grid:
            issues.append("建议添加网格线以便读数")

        # 检查是否有坐标轴标注
        from .content_analyzer import ContentAnalyzer
        text_result = ContentAnalyzer.detect_text_regions(image)
        has_axis_labels = text_result.has_text

        if not has_axis_labels:
            issues.append("波形图缺少坐标轴标注")

        # 评估信号质量（基于波形连续性）
        signal_quality = LabReportValidator._assess_signal_quality(img_array)

        if signal_quality < 0.5:
            issues.append("波形信号质量不佳，可能有噪声或断点")

        # 综合判断
        is_valid = (
            clarity_score >= 30 and
            edge_density >= LabReportValidator.WAVEFORM_MIN_EDGE_DENSITY
        )

        return WaveformResult(
            is_valid=is_valid,
            clarity_score=clarity_score,
            has_axis_labels=has_axis_labels,
            has_grid=has_grid,
            signal_quality=signal_quality,
            issues=issues
        )

    @staticmethod
    def _calculate_edge_density(img_array: np.ndarray) -> float:
        """计算边缘密度"""
        rows, cols = img_array.shape
        edge_count = 0

        for i in range(1, rows - 1):
            for j in range(1, cols - 1):
                gradient = abs(int(img_array[i, j]) - int(img_array[i-1, j])) + \
                          abs(int(img_array[i, j]) - int(img_array[i, j-1]))
                if gradient > 30:
                    edge_count += 1

        return edge_count / (rows * cols)

    @staticmethod
    def _check_line_completeness(img_array: np.ndarray) -> float:
        """检查连线完整性"""
        # 简化版：检查边缘的连通性
        rows, cols = img_array.shape

        # 二值化
        threshold = 128
        binary = (img_array < threshold).astype(int)

        # 检查水平连通性
        h_connected = 0
        for i in range(rows):
            segments = 0
            in_segment = False
            for j in range(cols):
                if binary[i, j] == 1:
                    if not in_segment:
                        in_segment = True
                        segments += 1
                else:
                    in_segment = False
            h_connected += min(segments, 5) / 5  # 最多5段也算完整

        # 检查垂直连通性
        v_connected = 0
        for j in range(cols):
            segments = 0
            in_segment = False
            for i in range(rows):
                if binary[i, j] == 1:
                    if not in_segment:
                        in_segment = True
                        segments += 1
                else:
                    in_segment = False
            v_connected += min(segments, 5) / 5

        # 归一化
        total_possible = (rows + cols) / 10
        return (h_connected + v_connected) / total_possible if total_possible > 0 else 0

    @staticmethod
    def _detect_hardware_features(image: Image.Image) -> bool:
        """检测硬件特征"""
        # 简化版：检测规整形状和矩形区域
        gray = image.convert('L')
        img_array = np.array(gray)

        # 检测矩形区域（PCB、开发板等）
        # 使用简单的边缘检测和形状分析

        # 检查是否有明显的矩形边界
        edges = LabReportValidator._detect_edges(img_array)
        edge_ratio = np.sum(edges) / edges.size

        # 硬件照片通常有适度的边缘密度
        return 0.1 < edge_ratio < 0.4

    @staticmethod
    def _detect_edges(img_array: np.ndarray) -> np.ndarray:
        """检测边缘"""
        rows, cols = img_array.shape
        edges = np.zeros_like(img_array)

        for i in range(1, rows - 1):
            for j in range(1, cols - 1):
                gradient = abs(int(img_array[i, j]) - int(img_array[i-1, j])) + \
                          abs(int(img_array[i, j]) - int(img_array[i, j-1]))
                edges[i, j] = 255 if gradient > 30 else 0

        return edges

    @staticmethod
    def _detect_grid_pattern(img_array: np.ndarray) -> bool:
        """检测网格模式"""
        rows, cols = img_array.shape

        # 检测水平线
        h_lines = 0
        for i in range(rows):
            row_edges = 0
            for j in range(cols - 1):
                if abs(int(img_array[i, j]) - int(img_array[i, j + 1])) > 50:
                    row_edges += 1
            if row_edges > cols * 0.7:  # 大部分都是边缘
                h_lines += 1

        # 检测垂直线
        v_lines = 0
        for j in range(cols):
            col_edges = 0
            for i in range(rows - 1):
                if abs(int(img_array[i, j]) - int(img_array[i + 1, j])) > 50:
                    col_edges += 1
            if col_edges > rows * 0.7:
                v_lines += 1

        # 网格通常有均匀分布的水平线和垂直线
        return h_lines >= 3 and v_lines >= 3

    @staticmethod
    def _assess_signal_quality(img_array: np.ndarray) -> float:
        """评估信号质量"""
        # 简化版：检查中间部分的连续性
        rows, cols = img_array.shape
        center_row = rows // 2
        center_col = cols // 2

        # 检查中心区域的边缘连续性
        signal_area = img_array[center_row-20:center_row+20, center_col-50:center_col+50]

        # 计算方差（好的信号应该有变化）
        variance = np.var(signal_area)

        # 归一化质量分数
        quality = min(1.0, variance / 2000)

        return quality
