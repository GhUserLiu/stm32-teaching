#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强质量评估系统 - 演示脚本
Demonstration of Enhanced Quality Assessment System v2.5.0
"""

import sys
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入新模块
from tools.plagiarism.code_analysis.code_analyzer import (
    EnhancedCodeAnalyzer,
    analyze_code_from_report,
    Severity
)
from tools.plagiarism.feedback.smart_feedback import (
    SmartFeedbackEngine,
    generate_smart_feedback_report
)
from tools.plagiarism.grading.grading_validator import (
    GradingValidator,
    validate_grading_results
)


def demo_code_analysis():
    """演示代码深度分析功能"""
    print("\n" + "="*70)
    print("[演示 1: 代码深度分析功能 (v2.5.0 新增)]")
    print("="*70)

    # 示例代码（档位实验）
    sample_code = '''
```c
// DWT初始化
void DWT_Init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

// 状态切换
void gear_switch(void)
{
    switch(current_gear)
    {
        case GEAR_P:
            current_gear = GEAR_R;
            break;
        case GEAR_R:
            current_gear = GEAR_N;
            break;
        case GEAR_N:
            current_gear = GEAR_D;
            break;
        case GEAR_D:
            current_gear = GEAR_P;
            break;
    }
    gear_update_led();
}

// 中断回调
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    static uint32_t last_tick = 0;

    if(DWT_Time_Elapsed(last_tick, DEBOUNCE_CYCLES))
    {
        last_tick = DWT_Get_Tick();
        gear_switch();
    }
}
```
'''

    # 分析代码
    print("\n正在分析示例代码...")
    result = EnhancedCodeAnalyzer.analyze(sample_code, "档位实验")

    print(f"\n[OK] 代码分析结果:")
    print(f"  总分: {result.total_score}/{result.max_score}")
    print(f"  函数数量: {result.metrics['function_count']}")
    print(f"  检测到问题: {len(result.issues)} 个")
    print(f"  代码亮点: {len(result.strengths)} 个")

    if result.issues:
        print("\n[!] 检测到的问题:")
        for issue in result.issues[:5]:
            emoji_map = {'critical': '[CRITICAL]', 'high': '[HIGH]', 'medium': '[MEDIUM]', 'low': '[LOW]', 'info': '[INFO]'}
            print(f"  {emoji_map[issue.severity.value]} [{issue.category}] {issue.message}")

    if result.strengths:
        print("\n[OK] 代码亮点:")
        for strength in result.strengths[:3]:
            print(f"  * {strength}")


def demo_smart_feedback():
    """演示智能反馈建议功能"""
    print("\n" + "="*70)
    print("[演示 2: 智能反馈建议系统 (v2.5.0 新增)]")
    print("="*70)

    # 模拟评分结果
    from dataclasses import dataclass
    from tools.plagiarism.grading import CategoryScore, CriterionScore

    @dataclass
    class MockGradingResult:
        student_id: str
        name: str
        total_score: float
        total_possible: float
        percentage: float
        grade: str
        category_scores: dict
        strengths: list
        weaknesses: list
        recommendations: list

    mock_result = MockGradingResult(
        student_id="23071140201",
        name="张三",
        total_score=65.0,
        total_possible=100.0,
        percentage=65.0,
        grade="D",
        category_scores={
            "code_quality": CategoryScore(
                category_id="code_quality",
                name="代码质量",
                points_earned=18.0,
                points_possible=30.0,
                percentage=60.0,
                criteria_scores=[],
                feedback=["代码注释详尽", "关键代码完整规范"]
            )
        },
        strengths=["代码流程图清晰"],
        weaknesses=["缺少DWT消抖实现", "GPIO配置说明不完整"],
        recommendations=["请补充DWT消抖实现"]
    )

    # 模拟技术检查结果
    mock_technical = (45.0, [], ["✓ LED0引脚配置正确"], ["✗ 缺少或错误: DWT消抖实现", "✗ 缺少或错误: 状态机逻辑"])

    print("\n正在生成智能反馈建议...")

    feedback = generate_smart_feedback_report(
        mock_result.student_id,
        mock_result.name,
        mock_result,
        mock_technical,
        None
    )

    print("\n[REPORT] 智能反馈报告预览:")
    print(feedback[:1000] + "...")


def demo_validation():
    """演示评分一致性校验功能"""
    print("\n" + "="*70)
    print("[演示 3: 评分一致性校验 (v2.5.0 新增)]")
    print("="*70)

    # 读取现有评分数据
    eval_path = Path("docs/teaching/2026-春季/汽服2302B班/07-car-gear/processed/evaluations.json")

    if eval_path.exists():
        print(f"\n正在读取评分数据: {eval_path}")

        with open(eval_path, 'r', encoding='utf-8') as f:
            eval_data = json.load(f)

        print(f"读取到 {len(eval_data)} 个学生评分数据")

        # 转换为校验格式
        results_data = []
        for item in eval_data[:10]:  # 只处理前10个作为演示
            results_data.append({
                'student_id': item.get('student_id'),
                'name': item.get('name'),
                'total_score': item.get('total_score'),
                'percentage': item.get('total_score'),  # 假设百分制
                'grade': item.get('grade'),
                'category_scores': {},
                'strengths': [],
                'weaknesses': [],
                'plagiarism_risk': 0
            })

        # 加载评分标准
        rubric_path = Path("data/rubrics/rubric.json")
        with open(rubric_path, 'r', encoding='utf-8') as f:
            rubric = json.load(f)

        # 执行校验
        print("\n正在执行评分一致性校验...")
        report = validate_grading_results(
            results_data,
            rubric,
            Path("docs/teaching/2026-春季/汽服2302B班/07-car-gear/results")
        )

        print(f"\n[OK] 校验完成:")
        print(f"  验证状态: {'[PASS]' if report.validation_passed else '[FAIL]'}")
        print(f"  学生总数: {report.total_students}")
        print(f"  问题数量: {report.issue_count}")
        print(f"  平均分: {report.statistics['average_score']:.1f}")

        if report.recommendations:
            print(f"\n[TIP] 改进建议:")
            for rec in report.recommendations[:3]:
                print(f"  * {rec}")

        print(f"\n[FILE] 校验报告已保存到: results/grading_validation_report.md")

    else:
        print(f"评分数据文件不存在: {eval_path}")


def main():
    """主函数"""
    # 设置控制台编码
    if sys.platform == 'win32':
        import io as io_module
        sys.stdout = io_module.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io_module.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    print("\n" + "="*70)
    print("[增强质量评估系统 v2.5.0 - 功能演示]")
    print("="*70)
    print("\n本演示将展示以下新增功能:")
    print("  1. [代码深度分析器]")
    print("  2. [智能反馈建议系统]")
    print("  3. [评分一致性校验]")

    try:
        # 演示1: 代码分析
        demo_code_analysis()

        # 演示2: 智能反馈
        demo_smart_feedback()

        # 演示3: 评分校验
        demo_validation()

        print("\n" + "="*70)
        print("[演示完成！]")
        print("="*70)
        print("\n详细文档请参阅: docs/ENHANCED_QUALITY_ASSESSMENT.md")

    except Exception as e:
        print(f"\n[ERROR] 演示过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
