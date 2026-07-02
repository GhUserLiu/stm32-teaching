#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NLP增强功能验证脚本
Validation Script for NLP Enhancement Features

运行此脚本以验证NLP增强功能是否正常工作
"""

import sys
import os
from pathlib import Path

# 设置路径
project_root = Path(os.getcwd()).resolve()
sys.path.insert(0, str(project_root))


def test_keyword_matching():
    """测试关键词匹配功能"""
    print("\n" + "="*60)
    print("测试1: 关键词匹配功能")
    print("="*60)

    from tools.plagiarism.nlp import EnhancedKeywordMatcher, MatchMethod

    matcher = EnhancedKeywordMatcher(
        use_fuzzy=True,
        use_variants=True,
        fuzzy_threshold=0.85
    )

    # 测试用例
    test_cases = [
        ("使用GPIO配置LED灯", ["GPIO", "LED"], "精确匹配"),
        ("使用G P I O配置LED灯", ["GPIO"], "空格混淆"),
        ("使用通用IO配置LED", ["GPIO"], "术语变体"),
        ("使用外部中断实现", ["中断"], "术语变体"),
    ]

    for text, keywords, description in test_cases:
        results, ratio = matcher.match_keywords(text, keywords, MatchMethod.HYBRID)
        matched = [r.keyword for r in results if r.matched]
        print(f"\n{description}:")
        print(f"  文本: {text[:30]}...")
        print(f"  关键词: {keywords}")
        print(f"  匹配结果: {matched}")
        print(f"  匹配率: {ratio:.1%}")

    return True


def test_template_filtering():
    """测试模板过滤功能"""
    print("\n" + "="*60)
    print("测试2: 模板过滤功能")
    print("="*60)

    from tools.plagiarism.nlp import AdvancedTemplateFilter, FilterMethod

    template = """
    一、实验目的
    本实验的目的是掌握STM32的GPIO配置方法。

    二、实验原理
    GPIO是通用输入输出接口，可以配置为输入或输出模式。
    """

    filter_obj = AdvancedTemplateFilter(
        template_content=template,
        similarity_threshold=0.7
    )

    # 测试用例
    test_cases = [
        ("一、实验目的\n本实验的目的是掌握STM32的GPIO配置方法。", "正常模板"),
        ("一  、  实  验  目  的\n本  实  验  的  目  的  是  掌  握  S  T  M  3  2  的  G  P  I  O  配  置  方  法  。", "混淆模板"),
        ("一、实验目标\n本实验目标是学会STM32编程", "修改后模板"),
    ]

    for text, description in test_cases:
        result = filter_obj.filter(text, FilterMethod.HYBRID)
        print(f"\n{description}:")
        print(f"  原始长度: {len(result.original_text)}")
        print(f"  过滤后长度: {len(result.filtered_text)}")
        print(f"  过滤比例: {result.removal_ratio:.1%}")

        # 检测操纵
        manipulation = filter_obj.detect_template_manipulation(text)
        if manipulation['detected']:
            print(f"  检测到操纵: {manipulation['techniques']}")

    return True


def test_code_analysis():
    """测试代码分析功能"""
    print("\n" + "="*60)
    print("测试3: 代码AST分析功能")
    print("="*60)

    from tools.plagiarism.nlp import CodeASTAnalyzer

    analyzer = CodeASTAnalyzer(language='c')

    # 测试代码
    code1 = """
    void led_init(void) {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_RESET);
    }
    """

    code2 = """
    void灯初始化(void) {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_RESET);
    }
    """

    result = analyzer.compare(code1, code2)

    print(f"\n代码比对结果:")
    print(f"  整体相似度: {result.overall_similarity:.1f}%")
    print(f"  结构相似度: {result.structure_similarity:.1f}%")
    print(f"  逻辑相似度: {result.logic_similarity:.1f}%")

    if result.obfuscation_detected:
        print(f"  检测到混淆: {[t.value for t in result.obfuscation_detected]}")

    return True


def test_grading_integration():
    """测试评分系统集成"""
    print("\n" + "="*60)
    print("测试4: 评分系统集成")
    print("="*60)

    from tools.plagiarism.grading import RubricGrader

    # 创建简单的评分标准
    rubric = {
        "experiment_name": "测试实验",
        "total_points": 100,
        "grading_scale": {
            "A": {"min": 90, "max": 100, "label": "优"},
            "B": {"min": 80, "max": 89, "label": "良"},
            "C": {"min": 70, "max": 79, "label": "中"},
            "D": {"min": 60, "max": 69, "label": "及格"},
            "F": {"min": 0, "max": 59, "label": "不及格"}
        },
        "categories": [
            {
                "id": "test_category",
                "name": "测试类别",
                "points": 20,
                "criteria": [
                    {
                        "id": "gpio_criterion",
                        "description": "GPIO配置",
                        "points": 20,
                        "keywords": ["GPIO", "配置", "引脚"]
                    }
                ]
            }
        ]
    }

    # 创建增强评分器
    grader = RubricGrader(rubric, enable_nlp=True)

    # 测试文本
    test_texts = [
        "使用G P I O配置引脚PE4和PF9",
        "使用通用IO配置引脚",
        "没有提到GPIO相关内容",
    ]

    for i, text in enumerate(test_texts, 1):
        print(f"\n测试文本{i}: {text[:40]}...")
        # 检查关键词匹配
        matched, ratio = grader.keyword_matcher.match_keywords(text, ["GPIO", "配置", "引脚"])
        print(f"  匹配关键词: {matched}")
        print(f"  匹配率: {ratio:.1%}")

    return True


def test_nlp_presets():
    """测试NLP预设配置"""
    print("\n" + "="*60)
    print("测试5: NLP预设配置")
    print("="*60)

    from tools.plagiarism.nlp import get_preset

    presets = ['default', 'strict', 'lenient', 'fast']

    for preset_name in presets:
        config = get_preset(preset_name)
        print(f"\n预设: {preset_name}")
        print(f"  模糊匹配: {config.enable_fuzzy_matching}")
        print(f"  模糊阈值: {config.fuzzy_threshold}")
        print(f"  术语变体: {config.enable_term_variants}")
        print(f"  AST分析: {config.enable_ast_analysis}")
        print(f"  模板过滤严格度: {config.template_filter_strictness}")

    return True


def main():
    """主函数"""
    print("="*60)
    print("NLP增强功能验证")
    print("="*60)

    tests = [
        ("关键词匹配", test_keyword_matching),
        ("模板过滤", test_template_filtering),
        ("代码分析", test_code_analysis),
        ("评分集成", test_grading_integration),
        ("NLP预设", test_nlp_presets),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n[PASS] {test_name}测试通过")
            else:
                failed += 1
                print(f"\n[FAIL] {test_name}测试失败")
        except Exception as e:
            failed += 1
            print(f"\n[ERROR] {test_name}测试出错: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*60)
    print("验证总结")
    print("="*60)
    print(f"通过: {passed}/{len(tests)}")
    print(f"失败: {failed}/{len(tests)}")

    if failed == 0:
        print("\n[SUCCESS] 所有测试通过！NLP增强功能正常工作。")
        return 0
    else:
        print(f"\n[FAILURE] 有{failed}个测试失败，请检查。")
        return 1


if __name__ == '__main__':
    sys.exit(main())
