#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多班级批量处理工具
Batch Multi-Class Processor

命令行工具，用于批量处理多个班级的查重检测。

用法:
    python tools/batch_class_processor.py \\
        --base-dir "docs/teaching/2026-春季" \\
        --experiment "07-car-gear" \\
        --enable-cross-class \\
        --output "multi_class_results"

作者: STM32F407 教学团队
版本: 1.0.0
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.plagiarism.core.multi_class_detector import (
    MultiClassDetector,
    create_multi_class_config,
    MultiClassDetectionResult
)
from tools.plagiarism.report.multi_class_report import MultiClassReportGenerator


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='多班级批量查重检测工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 自动发现并处理所有班级
  python tools/batch_class_processor.py \\
    --base-dir "docs/teaching/2026-春季" \\
    --experiment "07-car-gear"

  # 指定输出目录
  python tools/batch_class_processor.py \\
    --base-dir "docs/teaching/2026-春季" \\
    --experiment "07-car-gear" \\
    --output "results"

  # 禁用跨班级检测
  python tools/batch_class_processor.py \\
    --base-dir "docs/teaching/2026-春季" \\
    --experiment "07-car-gear" \\
    --no-cross-class

  # 指定相似度阈值
  python tools/batch_class_processor.py \\
    --base-dir "docs/teaching/2026-春季" \\
    --experiment "07-car-gear" \\
    --threshold 70
        """
    )

    parser.add_argument(
        '--base-dir',
        type=Path,
        default=Path('.'),
        help='基础目录 (默认: 当前目录)'
    )

    parser.add_argument(
        '--semester',
        type=str,
        default='2026-春季',
        help='学期 (默认: 2026-春季)'
    )

    parser.add_argument(
        '--experiment',
        type=str,
        required=True,
        help='实验编号 (如: 07-car-gear)'
    )

    parser.add_argument(
        '--class-pattern',
        type=str,
        default='*班',
        help='班级名称模式 (默认: *班)'
    )

    parser.add_argument(
        '--output',
        type=Path,
        default=None,
        help='输出目录 (默认: <base-dir>/multi_class_results)'
    )

    parser.add_argument(
        '--threshold',
        type=float,
        default=60.0,
        help='相似度阈值 (默认: 60.0)'
    )

    parser.add_argument(
        '--method',
        type=str,
        default='hybrid',
        choices=['sequence', 'cosine', 'jaccard', 'levenshtein', 'hybrid'],
        help='相似度计算方法 (默认: hybrid)'
    )

    parser.add_argument(
        '--no-cross-class',
        action='store_true',
        help='禁用跨班级检测'
    )

    parser.add_argument(
        '--formats',
        type=str,
        default='excel,json,pdf,word',
        help='报告格式 (逗号分隔, 默认: excel,json,pdf,word)'
    )

    parser.add_argument(
        '--project-name',
        type=str,
        default=None,
        help='项目名称 (默认: 自动生成)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='显示详细输出'
    )

    parser.add_argument(
        '--yes',
        action='store_true',
        help='跳过确认提示'
    )

    args = parser.parse_args()

    # 转换方法名
    method_map = {
        'sequence': 1,
        'cosine': 2,
        'jaccard': 3,
        'levenshtein': 4,
        'hybrid': 5
    }
    # 使用延迟导入以避免循环导入
    from tools.plagiarism.core.detector import SimilarityMethod
    method = SimilarityMethod(args.method)

    # 设置输出目录
    if args.output is None:
        output_dir = args.base_dir / 'multi_class_results' / args.experiment
    else:
        output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    # 设置项目名称
    if args.project_name is None:
        project_name = f"{args.semester}_{args.experiment}"
    else:
        project_name = args.project_name

    print("=" * 70)
    print("多班级批量查重检测工具")
    print("=" * 70)
    print(f"基础目录: {args.base_dir}")
    print(f"学期: {args.semester}")
    print(f"实验: {args.experiment}")
    print(f"阈值: {args.threshold}%")
    print(f"方法: {args.method}")
    print(f"跨班级检测: {'启用' if not args.no_cross_class else '禁用'}")
    print(f"输出目录: {output_dir}")
    print("=" * 70)

    # 创建多班级配置
    print("\n扫描班级目录...")
    class_configs = create_multi_class_config(
        base_dir=args.base_dir,
        semester=args.semester,
        experiment=args.experiment,
        class_pattern=args.class_pattern
    )

    if not class_configs:
        print("错误: 未找到任何班级")
        print(f"请检查目录是否存在: {args.base_dir / 'docs/teaching' / args.semester}")
        return 1

    print(f"发现 {len(class_configs)} 个班级:")
    for config in class_configs:
        print(f"  - {config['class_name']} ({config['submissions_dir']})")

    # 确认是否继续
    if not args.yes:
        try:
            response = input("\n是否继续处理? (y/n): ")
            if response.lower() != 'y':
                print("已取消")
                return 0
        except EOFError:
            # 非交互模式，自动继续
            print("\n非交互模式，自动继续...")

    # 进度回调函数
    def progress_callback(progress: int, message: str):
        if args.verbose:
            print(f"[{progress:3d}%] {message}")
        else:
            # 简单进度条
            bars = '=' * (progress // 5)
            spaces = ' ' * (20 - progress // 5)
            print(f"\r[{bars}{spaces}] {progress}%", end='', flush=True)

    # 创建检测器
    print("\n初始化检测器...")
    detector = MultiClassDetector(
        class_configs=class_configs,
        threshold=args.threshold,
        method=method,
        enable_cross_class=not args.no_cross_class,
        progress_callback=progress_callback
    )

    # 执行检测
    print("\n开始检测...")
    start_time = datetime.now()

    results = detector.detect_all()

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    if not args.verbose:
        print()  # 换行

    # 显示统计
    print("\n" + "=" * 70)
    print("检测完成!")
    print("=" * 70)

    summary = results.get_summary()
    print(f"总班级数: {summary['total_classes']}")
    print(f"总学生数: {summary['total_students']}")
    print(f"班级内可疑对: {summary['total_suspicious_pairs']}")
    print(f"跨班级可疑对: {summary['cross_class_suspicious_pairs']}")
    print(f"耗时: {duration:.1f} 秒")

    # 班级详情
    if args.verbose:
        print("\n班级详情:")
        for class_id, class_result in results.class_results.items():
            print(f"  {class_result.class_name}:")
            print(f"    学生数: {class_result.student_count}")
            print(f"    可疑对: {class_result.suspicious_pairs}")
            print(f"    可疑率: {class_result.suspicious_pairs / class_result.student_count * 100:.1f}%")

    # 跨班级结果
    if results.cross_class_results:
        print(f"\n跨班级可疑对 ({len(results.cross_class_results)}):")
        for result in results.cross_class_results[:10]:  # 只显示前10个
            print(f"  {result.student_id} ({result.metadata.get('class_name_1', '')}) & "
                  f"{result.similar_to} ({result.metadata.get('class_name_2', '')}): "
                  f"{result.overall_similarity:.1f}%")
        if len(results.cross_class_results) > 10:
            print(f"  ... 还有 {len(results.cross_class_results) - 10} 对")

    # 生成报告
    print("\n生成报告...")
    formats = args.formats.split(',')

    report_gen = MultiClassReportGenerator(
        output_dir=output_dir,
        project_name=project_name
    )

    # 加载评分数据
    print("加载评分数据...")
    report_gen.load_grading_data(class_configs)

    report_paths = report_gen.generate_all(results, formats=formats)

    for path in report_paths:
        print(f"  - {path}")

    # 保存完整结果
    json_path = output_dir / f"{project_name}_完整结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    # 序列化结果
    results_data = {
        'summary': summary,
        'classes': {
            class_id: {
                'class_name': result.class_name,
                'student_count': result.student_count,
                'suspicious_pairs': result.suspicious_pairs,
                'groups': result.groups
            }
            for class_id, result in results.class_results.items()
        },
        'cross_class_results': [
            {
                'student1': r.student_id,
                'class1': r.metadata.get('class_name_1', ''),
                'student2': r.similar_to,
                'class2': r.metadata.get('class_name_2', ''),
                'similarity': r.overall_similarity
            }
            for r in results.cross_class_results
        ],
        'class_comparisons': results.class_comparisons,
        'timestamp': results.timestamp
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results_data, f, ensure_ascii=False, indent=2)

    print(f"  - {json_path}")

    print("\n" + "=" * 70)
    print("处理完成!")
    print(f"所有结果已保存到: {output_dir}")
    print("=" * 70)

    return 0


if __name__ == '__main__':
    sys.exit(main())
