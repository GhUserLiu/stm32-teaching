#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
图片质量评估测试脚本
Test Script for Image Quality Assessment
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / 'tools' / 'plagiarism'))

from image_quality import ImageQualityAssessor, ImageType

def test_single_image():
    """测试单张图片评估"""
    print("=" * 60)
    print("图片质量评估测试")
    print("=" * 60)

    # 创建评估器
    assessor = ImageQualityAssessor()

    # 测试图片
    test_images = [
        r"D:\4-Workspace\MCU_Research\project_test\NewProjectF407\.pack\Keil\STM32F4xx_DFP.3.1.1\CMSIS\SVD\_htmresc\st_logo.png",
        r"D:\4-Workspace\MCU_Research\project_test\NewProjectF407\.pack\Keil\STM32F4xx_DFP.3.1.1\Documents\UV-CubeMX.png",
        r"D:\4-Workspace\MCU_Research\project_test\NewProjectF407\.pack\Keil\STM32F4xx_DFP.3.1.1\Documents\VSCode-CubeMX.png",
    ]

    for image_path in test_images:
        print(f"\n{'='*60}")
        print(f"评估图片: {Path(image_path).name}")
        print(f"{'='*60}")

        try:
            result = assessor.assess(image_path)

            print(f"\n【评估结果】")
            print(f"  技术质量分数: {result.technical_score:.1f}/100")
            print(f"  内容质量分数: {result.content_score:.1f}/100")
            print(f"  整体质量分数: {result.overall_quality:.1f}/100")
            print(f"  图片类型: {result.image_type.value}")

            if result.issues:
                print(f"\n【发现的问题】")
                for i, issue in enumerate(result.issues, 1):
                    print(f"  {i}. {issue}")
            else:
                print("\n【发现的问题】无")

            if result.suggestions:
                print(f"\n【改进建议】")
                for i, suggestion in enumerate(result.suggestions, 1):
                    print(f"  {i}. {suggestion}")
            else:
                print("\n【改进建议】无")

            # 显示详细指标
            print(f"\n【详细指标】")
            metrics = result.metrics
            if 'technical' in metrics:
                tech = metrics['technical']
                print(f"  清晰度: {tech['sharpness']:.1f}/100")
                print(f"  亮度: {tech['brightness']:.1f}/100")
                print(f"  对比度: {tech['contrast']:.1f}/100")
                print(f"  分辨率: {tech['resolution']:.1f}/100")
                print(f"  噪点水平: {tech['noise']:.2f}")

            if 'content' in metrics:
                content = metrics['content']
                print(f"  内容类型置信度: {content['type_confidence']:.2f}")
                print(f"  是否空白: {'是' if content['is_blank'] else '否'}")

        except Exception as e:
            print(f"\n错误: {e}")

def test_batch_assessment():
    """测试批量评估"""
    print("\n\n" + "=" * 60)
    print("批量评估测试")
    print("=" * 60)

    assessor = ImageQualityAssessor()

    test_images = [
        r"D:\4-Workspace\MCU_Research\project_test\NewProjectF407\.pack\Keil\STM32F4xx_DFP.3.1.1\CMSIS\SVD\_htmresc\st_logo.png",
        r"D:\4-Workspace\MCU_Research\project_test\NewProjectF407\.pack\Keil\STM32F4xx_DFP.3.1.1\Documents\UV-CubeMX.png",
        r"D:\4-Workspace\MCU_Research\project_test\NewProjectF407\.pack\Keil\STM32F4xx_DFP.3.1.1\Documents\VSCode-CubeMX.png",
    ]

    batch_result = assessor.batch_assess(test_images)

    print(f"\n【批量评估汇总】")
    summary = batch_result.summary

    print(f"  总图片数: {summary['total_images']}")
    print(f"  平均技术质量: {summary['average_technical_score']:.1f}/100")
    print(f"  平均内容质量: {summary['average_content_score']:.1f}/100")
    print(f"  平均整体质量: {summary['average_overall_quality']:.1f}/100")

    print(f"\n【质量等级分布】")
    for grade, count in summary['grade_distribution'].items():
        print(f"  {grade}: {count} 张")

    print(f"\n【图片类型分布】")
    for img_type, count in summary['type_distribution'].items():
        print(f"  {img_type}: {count} 张")

    print(f"\n【问题统计】")
    print(f"  总问题数: {summary['total_issues']}")
    print(f"  有问题的图片: {summary['images_with_issues']} 张")

if __name__ == "__main__":
    test_single_image()
    test_batch_assessment()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
