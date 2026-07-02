# -*- coding: utf-8 -*-
"""
教学管理工具 - 统一CLI入口
Teaching Manager - Unified CLI Interface

整合所有教学管理功能，提供统一的命令行接口
"""

import argparse
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional
import shutil

# 添加工具路径
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(PROJECT_ROOT / "tools" / "plagiarism"))
sys.path.insert(0, str(PROJECT_ROOT))


class TeachingManager:
    """教学管理器 - 统一管理所有教学相关操作"""

    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化管理器

        Args:
            config_path: 配置文件路径（可选）
        """
        self.config_path = config_path or SCRIPT_DIR.parent / "config.yaml"
        self.config = self._load_config()

        # 设置路径
        self.base_dir = PROJECT_ROOT
        self.teaching_dir = self.base_dir / "docs" / "teaching"
        self.common_dir = self.teaching_dir / "common"

    def _load_config(self) -> Dict:
        """加载配置文件"""
        if self.config_path.exists():
            try:
                import yaml
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            except ImportError:
                print("Warning: PyYAML not installed, using default config")
            except Exception as e:
                print(f"Warning: Error loading config: {e}")

        # 默认配置
        return {
            'experiments': {},
            'classes': {},
            'thresholds': {
                'suspicious': 60,
                'high_risk': 75,
                'plagiarism': 85
            },
            'features': {
                'enable_semantic': True,
                'enable_adaptive_threshold': True
            }
        }

    def process_submissions(
        self,
        experiment: str,
        class_name: str,
        input_file: Path
    ) -> Dict:
        """
        处理学生提交

        Args:
            experiment: 实验编号 (如 "07-car-gear")
            class_name: 班级名称
            input_file: 提交文件路径 (ZIP)

        Returns:
            处理结果
        """
        print(f"Processing submissions for {experiment} - {class_name}")

        # 设置实验目录
        experiment_dir = self.teaching_dir / "2026-春季" / class_name / experiment
        experiment_dir.mkdir(parents=True, exist_ok=True)

        submissions_dir = experiment_dir / "submissions"
        processed_dir = experiment_dir / "processed"
        submissions_dir.mkdir(exist_ok=True)
        processed_dir.mkdir(exist_ok=True)

        # 解压文件
        print("  Extracting ZIP file...")
        import zipfile
        with zipfile.ZipFile(input_file, 'r') as zip_ref:
            zip_ref.extractall(submissions_dir)

        print(f"  Extracted to: {submissions_dir}")

        return {
            'status': 'success',
            'submissions_dir': str(submissions_dir),
            'processed_dir': str(processed_dir)
        }

    def evaluate(
        self,
        experiment: str,
        class_name: str,
        enable_semantic: bool = False,
        enable_enhanced: bool = False
    ) -> Dict:
        """
        评估学生报告

        Args:
            experiment: 实验编号
            class_name: 班级名称
            enable_semantic: 启用语义评分
            enable_enhanced: 启用增强反馈

        Returns:
            评估结果
        """
        print(f"Evaluating reports for {experiment} - {class_name}")

        # 设置路径
        experiment_dir = self.teaching_dir / "2026-春季" / class_name / experiment
        processed_dir = experiment_dir / "processed"

        # 检查提取的内容是否存在
        content_path = processed_dir / "extracted_content.json"
        if not content_path.exists():
            # 先运行内容提取
            print("  Extracting content first...")
            self._extract_content(experiment_dir, processed_dir)

        # 运行评估
        print("  Running evaluation...")

        # 构建命令
        cmd = [sys.executable, str(SCRIPT_DIR / "evaluate.py")]

        if enable_semantic:
            cmd.append('--semantic')
        if enable_enhanced:
            cmd.append('--enhanced')

        cmd.extend(['--experiment-dir', str(experiment_dir)])

        # 执行
        import subprocess
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')

        print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr, file=sys.stderr)

        return {
            'status': 'success' if result.returncode == 0 else 'failed',
            'experiment_dir': str(experiment_dir)
        }

    def detect_plagiarism(
        self,
        experiment: str,
        class_name: str,
        enable_adaptive: bool = True
    ) -> Dict:
        """
        执行查重检测

        Args:
            experiment: 实验编号
            class_name: 班级名称
            enable_adaptive: 启用自适应阈值

        Returns:
            检测结果
        """
        print(f"Running plagiarism detection for {experiment} - {class_name}")

        # 设置路径
        experiment_dir = self.teaching_dir / "2026-春季" / class_name / experiment
        processed_dir = experiment_dir / "processed"

        # 运行查重
        print("  Running detection...")

        # 使用 core 模块
        try:
            # 尝试直接导入
            from tools.plagiarism.core import PlagiarismDetector, SimilarityMethod
        except ImportError:
            try:
                from plagiarism.core import PlagiarismDetector, SimilarityMethod
            except ImportError:
                # 最后尝试从路径导入
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    "core",
                    str(PROJECT_ROOT / "tools" / "plagiarism" / "core.py")
                )
                core_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(core_module)
                PlagiarismDetector = core_module.PlagiarismDetector
                SimilarityMethod = core_module.SimilarityMethod

        # 加载提取的内容
        content_path = processed_dir / "extracted_content.json"
        if not content_path.exists():
            print("  Error: extracted_content.json not found")
            return {'status': 'error', 'message': 'Content not extracted'}

        with open(content_path, 'r', encoding='utf-8') as f:
            extracted_data = json.load(f)

        # 构建提交字典
        submissions = {}
        for item in extracted_data:
            submissions[item['student_id']] = {
                'name': item.get('name', ''),
                'text': item.get('full_text', '')
            }

        # 运行检测
        detector = PlagiarismDetector(
            method=SimilarityMethod.HYBRID,
            enable_adaptive_threshold=enable_adaptive
        )

        all_results, suspicious, adaptive_report = detector.detect(submissions)

        # 保存结果
        output_path = processed_dir / "plagiarism_results.json"
        results_data = {
            'suspicious_count': len(suspicious),
            'adaptive_report': adaptive_report,
            'suspicious': [
                {
                    'student_id': r.student_id,
                    'similar_to': r.similar_to,
                    'similarity': r.overall_similarity,
                    'is_cross_group': r.is_cross_group
                }
                for r in suspicious
            ]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)

        print(f"  Found {len(suspicious)} suspicious cases")
        print(f"  Results saved to: {output_path}")

        return {
            'status': 'success',
            'suspicious_count': len(suspicious),
            'output_path': str(output_path)
        }

    def generate_report(
        self,
        experiment: str,
        class_name: str,
        format: str = 'excel',
        include_feedback: bool = True
    ) -> Dict:
        """
        生成报告

        Args:
            experiment: 实验编号
            class_name: 班级名称
            format: 报告格式 ('excel', 'pdf', 'html')
            include_feedback: 是否包含学生反馈

        Returns:
            生成结果
        """
        print(f"Generating report for {experiment} - {class_name}")

        # 设置路径
        experiment_dir = self.teaching_dir / "2026-春季" / class_name / experiment
        processed_dir = experiment_dir / "processed"
        results_dir = experiment_dir / "results"
        results_dir.mkdir(exist_ok=True)

        # 运行报告生成
        print(f"  Generating {format} report...")

        # 这里可以调用 generate_output.py
        cmd = [sys.executable, str(SCRIPT_DIR / "generate_output.py")]
        cmd.extend(['--experiment-dir', str(experiment_dir)])

        if format == 'excel':
            cmd.append('--excel')
        elif format == 'html':
            cmd.append('--html')

        if include_feedback:
            cmd.append('--feedback')

        import subprocess
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')

        print(result.stdout)

        return {
            'status': 'success' if result.returncode == 0 else 'failed',
            'results_dir': str(results_dir)
        }

    def workflow(
        self,
        experiment: str,
        class_name: str,
        input_file: Path,
        stages: Optional[List[str]] = None
    ) -> Dict:
        """
        执行完整工作流

        Args:
            experiment: 实验编号
            class_name: 班级名称
            input_file: 提交文件
            stages: 指定执行的阶段 (默认全部)

        Returns:
            工作流结果
        """
        print(f"Running full workflow for {experiment} - {class_name}")
        print("=" * 50)

        default_stages = ['extract', 'evaluate', 'plagiarism', 'report']
        stages = stages or default_stages

        results = {}

        for stage in stages:
            print(f"\n[Stage: {stage.upper()}]")
            try:
                if stage == 'extract':
                    result = self.process_submissions(experiment, class_name, input_file)
                    results['extract'] = result
                elif stage == 'evaluate':
                    result = self.evaluate(experiment, class_name, enable_semantic=True)
                    results['evaluate'] = result
                elif stage == 'plagiarism':
                    result = self.detect_plagiarism(experiment, class_name)
                    results['plagiarism'] = result
                elif stage == 'report':
                    result = self.generate_report(experiment, class_name)
                    results['report'] = result
                else:
                    print(f"  Unknown stage: {stage}")
            except Exception as e:
                print(f"  Error in {stage}: {e}")
                results[stage] = {'status': 'error', 'message': str(e)}

        print("\n" + "=" * 50)
        print("Workflow completed!")
        print(f"Results: {sum(1 for r in results.values() if r.get('status') == 'success')}/{len(results)} stages succeeded")

        return results

    def _extract_content(self, experiment_dir: Path, processed_dir: Path) -> None:
        """提取内容（内部方法）"""
        import subprocess
        cmd = [sys.executable, str(SCRIPT_DIR / "extract_content.py"),
               '--experiment-dir', str(experiment_dir)]
        subprocess.run(cmd, check=True)


def create_parser() -> argparse.ArgumentParser:
    """创建命令行解析器"""
    parser = argparse.ArgumentParser(
        description='教学管理工具 - 统一CLI接口',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 处理提交并执行完整工作流
  python teaching_manager.py workflow 07-car-gear 汽服2302B班 submissions.zip

  # 仅评估报告
  python teaching_manager.py evaluate 07-car-gear 汽服2302B班 --semantic

  # 执行查重检测
  python teaching_manager.py plagiarism 07-car-gear 汽服2302B班

  # 生成报告
  python teaching_manager.py report 07-car-gear 汽服2302B班 --format excel
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # workflow 命令
    workflow_parser = subparsers.add_parser('workflow', help='执行完整工作流')
    workflow_parser.add_argument('experiment', help='实验编号')
    workflow_parser.add_argument('class_name', help='班级名称')
    workflow_parser.add_argument('input_file', type=Path, help='提交文件(ZIP)')
    workflow_parser.add_argument('--stages', nargs='+', choices=['extract', 'evaluate', 'plagiarism', 'report'],
                                   help='指定执行阶段')

    # evaluate 命令
    eval_parser = subparsers.add_parser('evaluate', help='评估学生报告')
    eval_parser.add_argument('experiment', help='实验编号')
    eval_parser.add_argument('class_name', help='班级名称')
    eval_parser.add_argument('--semantic', action='store_true', help='启用语义评分')
    eval_parser.add_argument('--enhanced', action='store_true', help='启用增强反馈')

    # plagiarism 命令
    plag_parser = subparsers.add_parser('plagiarism', help='执行查重检测')
    plag_parser.add_argument('experiment', help='实验编号')
    plag_parser.add_argument('class_name', help='班级名称')
    plag_parser.add_argument('--no-adaptive', action='store_true', help='禁用自适应阈值')

    # report 命令
    report_parser = subparsers.add_parser('report', help='生成报告')
    report_parser.add_argument('experiment', help='实验编号')
    report_parser.add_argument('class_name', help='班级名称')
    report_parser.add_argument('--format', choices=['excel', 'html'], default='excel', help='报告格式')
    report_parser.add_argument('--no-feedback', action='store_true', help='不包含学生反馈')

    # process 命令
    proc_parser = subparsers.add_parser('process', help='处理学生提交')
    proc_parser.add_argument('experiment', help='实验编号')
    proc_parser.add_argument('class_name', help='班级名称')
    proc_parser.add_argument('input_file', type=Path, help='提交文件(ZIP)')

    return parser


def main():
    """主函数"""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 创建管理器
    manager = TeachingManager()

    try:
        if args.command == 'workflow':
            manager.workflow(
                experiment=args.experiment,
                class_name=args.class_name,
                input_file=args.input_file,
                stages=args.stages
            )
        elif args.command == 'evaluate':
            manager.evaluate(
                experiment=args.experiment,
                class_name=args.class_name,
                enable_semantic=args.semantic,
                enable_enhanced=args.enhanced
            )
        elif args.command == 'plagiarism':
            manager.detect_plagiarism(
                experiment=args.experiment,
                class_name=args.class_name,
                enable_adaptive=not args.no_adaptive
            )
        elif args.command == 'report':
            manager.generate_report(
                experiment=args.experiment,
                class_name=args.class_name,
                format=args.format,
                include_feedback=not args.no_feedback
            )
        elif args.command == 'process':
            manager.process_submissions(
                experiment=args.experiment,
                class_name=args.class_name,
                input_file=args.input_file
            )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
