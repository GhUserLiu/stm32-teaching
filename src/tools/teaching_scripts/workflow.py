# -*- coding: utf-8 -*-
"""
工作流引擎
Workflow Engine

支持自动依赖检查、断点续传、并行处理和进度追踪
"""

import json

from tools.common import atomic_write_json
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import concurrent.futures
import threading


class StageStatus(Enum):
    """阶段状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    """阶段执行结果"""
    stage_name: str
    status: StageStatus
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration: float = 0.0
    output: Dict = field(default_factory=dict)
    error: Optional[str] = None
    dependencies_met: bool = True


@dataclass
class WorkflowState:
    """工作流状态"""
    current_stage: str = ""
    completed_stages: List[str] = field(default_factory=list)
    stage_results: Dict[str, StageResult] = field(default_factory=dict)
    start_time: float = 0
    last_update: float = 0
    is_resumed: bool = False


class ProgressTracker:
    """进度追踪器"""

    def __init__(self, total_stages: int):
        self.total_stages = total_stages
        self.current_stage = 0
        self.stage_progress = 0.0
        self.lock = threading.Lock()
        self.start_time = time.time()
        self.callbacks = []

    def register_callback(self, callback: Callable):
        """注册进度回调"""
        self.callbacks.append(callback)

    def update(self, stage: str, progress: float, message: str = ""):
        """更新进度"""
        with self.lock:
            self.stage_progress = progress
            for callback in self.callbacks:
                callback(stage, progress, message)

    def next_stage(self, stage_name: str):
        """进入下一阶段"""
        with self.lock:
            self.current_stage += 1
            for callback in self.callbacks:
                callback(stage_name, 0.0, "Starting")

    def get_eta(self) -> float:
        """估算剩余时间"""
        elapsed = time.time() - self.start_time
        if self.current_stage == 0:
            return 0.0
        avg_time_per_stage = elapsed / self.current_stage
        remaining_stages = self.total_stages - self.current_stage
        return avg_time_per_stage * remaining_stages

    def get_overall_progress(self) -> float:
        """获取总体进度"""
        if self.total_stages == 0:
            return 0.0
        return (self.current_stage + self.stage_progress) / self.total_stages


class WorkflowEngine:
    """工作流引擎"""

    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化工作流引擎

        Args:
            config_path: 工作流配置文件路径
        """
        self.config_path = config_path
        self.stages = self._load_stages()
        self.state = WorkflowState()
        self.state_file = Path(".workflow_state.json")

    def _load_stages(self) -> Dict:
        """加载工作流阶段配置"""
        if self.config_path and self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('stages', {})

        # 默认工作流配置
        return {
            'extract': {
                'name': 'Extract Content',
                'dependencies': [],
                'function': 'extract_content',
                'outputs': ['extracted_content.json']
            },
            'evaluate': {
                'name': 'Evaluate Reports',
                'dependencies': ['extract'],
                'function': 'evaluate',
                'outputs': ['evaluations.json']
            },
            'plagiarism': {
                'name': 'Plagiarism Detection',
                'dependencies': ['extract'],
                'function': 'detect_plagiarism',
                'outputs': ['plagiarism_results.json'],
                'parallel_with': ['evaluate']
            },
            'report': {
                'name': 'Generate Report',
                'dependencies': ['evaluate', 'plagiarism'],
                'function': 'generate_report',
                'outputs': ['gradebook.xlsx']
            }
        }

    def run(
        self,
        target_stage: Optional[str] = None,
        resume: bool = True,
        parallel: bool = True
    ) -> Dict[str, StageResult]:
        """
        执行工作流

        Args:
            target_stage: 目标阶段（执行到此阶段后停止）
            resume: 是否从断点恢复
            parallel: 是否启用并行处理

        Returns:
            所有阶段的结果
        """
        # 加载之前的状态
        if resume and self.state_file.exists():
            self._load_state()

        self.state.start_time = time.time()
        self.state.is_resumed = resume and bool(self.state.completed_stages)

        # 创建进度追踪器
        tracker = ProgressTracker(len(self.stages))

        # 注册默认的进度显示
        tracker.register_callback(self._default_progress_callback)

        # 确定执行顺序
        execution_order = self._determine_execution_order(target_stage)

        # 执行各阶段
        for stage_name in execution_order:
            if stage_name in self.state.completed_stages:
                print(f"  [SKIP] {stage_name} already completed")
                self.state.stage_results[stage_name] = StageResult(
                    stage_name=stage_name,
                    status=StageStatus.SKIPPED
                )
                continue

            # 检查依赖
            if not self._check_dependencies(stage_name):
                print(f"  [ERROR] Dependencies not met for {stage_name}")
                self.state.stage_results[stage_name] = StageResult(
                    stage_name=stage_name,
                    status=StageStatus.FAILED,
                    dependencies_met=False
                )
                continue

            # 执行阶段
            tracker.next_stage(stage_name)
            result = self._execute_stage(stage_name, tracker)

            self.state.stage_results[stage_name] = result

            if result.status == StageStatus.COMPLETED:
                self.state.completed_stages.append(stage_name)
            elif result.status == StageStatus.FAILED:
                print(f"  Stage {stage_name} failed, stopping workflow")
                break

            # 保存状态（支持断点续传）
            self._save_state()

        self.state.last_update = time.time()

        return self.state.stage_results

    def _determine_execution_order(self, target_stage: Optional[str]) -> List[str]:
        """确定执行顺序"""
        if target_stage and target_stage in self.stages:
            # 找到到达目标阶段的路径
            order = []
            to_visit = [target_stage]
            visited = set()

            while to_visit:
                stage = to_visit.pop(0)
                if stage in visited:
                    continue
                visited.add(stage)

                deps = self.stages[stage].get('dependencies', [])
                for dep in deps:
                    if dep not in visited:
                        to_visit.append(dep)

                order.append(stage)

            return sorted(order, key=lambda x: (
                self.stages[x].get('dependencies', '').index(x) if x in self.stages[x].get('dependencies', '') else 0
            ))
        else:
            return list(self.stages.keys())

    def _check_dependencies(self, stage_name: str) -> bool:
        """检查依赖是否满足"""
        stage_config = self.stages.get(stage_name, {})
        dependencies = stage_config.get('dependencies', [])

        for dep in dependencies:
            if dep not in self.state.completed_stages:
                return False

        return True

    def _execute_stage(self, stage_name: str, tracker: ProgressTracker) -> StageResult:
        """执行单个阶段"""
        stage_config = self.stages[stage_name]
        result = StageResult(
            stage_name=stage_name,
            status=StageStatus.RUNNING,
            start_time=time.time()
        )

        print(f"  [RUN] {stage_name}")

        try:
            # 这里应该调用实际的执行函数
            # 为了演示，使用模拟执行
            output = self._simulate_execution(stage_name, tracker)

            result.status = StageStatus.COMPLETED
            result.output = output
            result.end_time = time.time()
            result.duration = result.end_time - result.start_time

            print(f"  [DONE] {stage_name} ({result.duration:.2f}s)")

        except Exception as e:
            result.status = StageStatus.FAILED
            result.error = str(e)
            result.end_time = time.time()
            print(f"  [FAIL] {stage_name}: {e}")

        return result

    def _simulate_execution(self, stage_name: str, tracker: ProgressTracker) -> Dict:
        """模拟执行（实际应用中替换为真实调用）"""
        import time
        import random

        steps = random.randint(3, 8)
        for i in range(steps + 1):
            progress = i / steps
            tracker.update(stage_name, progress, f"Step {i}/{steps}")
            time.sleep(0.1)

        return {'status': 'success', 'items_processed': random.randint(10, 100)}

    def _default_progress_callback(self, stage: str, progress: float, message: str):
        """默认进度回调"""
        overall = ProgressTracker(len(self.stages))
        bar_len = 40
        filled = int(bar_len * progress)
        bar = '█' * filled + '░' * (bar_len - filled)
        print(f"\r  [{stage}] [{bar}] {progress*100:.0f}% - {message}", end='', flush=True)

        if progress >= 1.0:
            print()  # 换行

    def _save_state(self):
        """保存工作流状态"""
        state_data = {
            'current_stage': self.state.current_stage,
            'completed_stages': self.state.completed_stages,
            'stage_results': {
                name: {
                    'stage_name': r.stage_name,
                    'status': r.status.value,
                    'duration': r.duration,
                    'error': r.error
                }
                for name, r in self.state.stage_results.items()
            },
            'start_time': self.state.start_time,
            'last_update': self.state.last_update
        }

        atomic_write_json(self.state_file, state_data, indent=2)

    def _load_state(self):
        """加载工作流状态"""
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)

            self.state.completed_stages = state_data.get('completed_stages', [])
            self.state.start_time = state_data.get('start_time', time.time())

            print(f"Resumed from state: {len(self.state.completed_stages)} stages completed")
        except Exception as e:
            print(f"Warning: Could not load state: {e}")

    def reset(self):
        """重置工作流状态"""
        self.state = WorkflowState()
        if self.state_file.exists():
            self.state_file.unlink()

    def get_status(self) -> Dict:
        """获取当前状态"""
        return {
            'total_stages': len(self.stages),
            'completed_stages': len(self.state.completed_stages),
            'current_progress': len(self.state.completed_stages) / len(self.stages) if self.stages else 0,
            'stage_results': {
                name: {
                    'status': r.status.value,
                    'duration': r.duration
                }
                for name, r in self.state.stage_results.items()
            }
        }


def create_workflow_engine(config_path: Optional[Path] = None) -> WorkflowEngine:
    """
    创建工作流引擎（便捷函数）

    Args:
        config_path: 配置文件路径

    Returns:
        工作流引擎实例
    """
    return WorkflowEngine(config_path)
