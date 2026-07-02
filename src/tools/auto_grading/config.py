#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动化批阅系统配置
Auto Grading System Configuration

定义系统所需的各种配置参数，包括：
- 工具链路径
- 超时设置
- 项目白名单
- 输出路径（统一走 path_config）
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class ToolchainConfig:
    """工具链配置"""
    # GCC工具链配置
    gcc_enabled: bool = True
    make_path: str = "make"
    arm_none_eabi_prefix: str = "arm-none-eabi-"

    # Keil工具链配置（可选）
    keil_enabled: bool = False
    keil_uv4_path: Optional[str] = None  # 例如: r"C:\Keil_v5\UV4\UV4.exe"

    # 超时设置
    build_timeout: int = 60  # 编译超时时间（秒）

    def get_make_command(self, project: str, target: str = "all") -> List[str]:
        """获取Make命令"""
        return [self.make_path, f"PROJECT={project}", target]

    def get_keil_command(self, project_path: str) -> List[str]:
        """获取Keil命令（如果启用）"""
        if not self.keil_enabled or not self.keil_uv4_path:
            raise RuntimeError("Keil工具链未配置")
        return [self.keil_uv4_path, "-r", "-j0", project_path]


@dataclass
class ProjectConfig:
    """项目配置"""
    # 允许的项目列表（与Makefile白名单同步）
    allowed_projects: List[str] = field(default_factory=lambda: [
        "01-turn-signal",
        "07-car-gear",
        "_template",
        "Test6"
    ])

    # 项目类型映射
    project_types: Dict[str, str] = field(default_factory=lambda: {
        "01-turn-signal": "simple",
        "07-car-gear": "cubemx",
        "_template": "simple",
        "Test6": "simple"
    })

    # 源文件模式
    source_patterns: List[str] = field(default_factory=lambda: [
        "*.c",
        "*.h",
        "*.cpp"
    ])

    # 主文件模式
    main_file_patterns: List[str] = field(default_factory=lambda: [
        "main.c",
        "main.cpp",
        "main_interrupt.c"
    ])

    def is_project_allowed(self, project_name: str) -> bool:
        """检查项目是否在白名单中"""
        return project_name in self.allowed_projects

    def get_project_type(self, project_name: str) -> str:
        """获取项目类型"""
        return self.project_types.get(project_name, "simple")


@dataclass
class GradingConfig:
    """评分配置（保留字段以备后续扩展）

    说明：当前总分 = 各 rubric category 的 earned_points 之和
    （见 grading_engine.AutoGradingEngine.grade_submission 的累加逻辑），
    rubric.json 的 categories 为唯一分值来源。
    历史上此处的 compilation/code_quality/report_quality 权重字段
    从未被使用，已删除以消除配置与实现脱节。
    """
    pass


@dataclass
class SecurityConfig:
    """安全配置"""
    # ZIP文件大小限制（与zip_validator.py同步）
    max_zip_size: int = 100 * 1024 * 1024  # 100MB

    # 最大文件数量
    max_file_count: int = 1000

    # 允许的文件扩展名
    allowed_extensions: List[str] = field(default_factory=lambda: [
        ".c", ".h", ".cpp", ".hpp",
        ".zip",
        ".docx", ".doc",
        ".pdf", ".png", ".jpg"
    ])

    # 路径验证
    allow_absolute_paths: bool = False
    allow_parent_references: bool = False


@dataclass
class AutoGradingConfig:
    """自动化批阅系统主配置"""
    # 项目根目录
    project_root: Path = field(default_factory=lambda: Path.cwd())

    # 当前学期（用于按学期定位实验目录）
    semester: str = "2026-春季"

    # 工具链配置
    toolchain: ToolchainConfig = field(default_factory=ToolchainConfig)

    # 项目配置
    project: ProjectConfig = field(default_factory=ProjectConfig)

    # 评分配置
    grading: GradingConfig = field(default_factory=GradingConfig)

    # 安全配置
    security: SecurityConfig = field(default_factory=SecurityConfig)

    # 数据目录
    data_dir: Path = field(init=False)
    rubrics_dir: Path = field(init=False)
    teaching_dir: Path = field(init=False)
    outputs_dir: Path = field(init=False)

    def __post_init__(self):
        """初始化路径"""
        self.data_dir = self.project_root / "data"
        self.rubrics_dir = self.data_dir / "rubrics"
        self.teaching_dir = self.data_dir / "teaching"
        self.outputs_dir = self.project_root / "outputs"

    def get_rubric_path(self, experiment_code: str) -> Path:
        """获取评分标准路径。

        优先按实验代码定位（如 07_car_gear_experiment.json）；
        若不存在则回退到通用 rubric.json（当前主链路使用的规范文件）。
        """
        specific = self.rubrics_dir / f"{experiment_code}.json"
        if specific.exists():
            return specific
        # 未找到该实验专属 rubric：回退通用 rubric.json。
        # 07-car-gear 等本就以 rubric.json 为标准，属预期；其它 experiment 多半是
        # 拼写错误或漏建 rubric——回退会被当成汽车档位标准误评，故显式告警提示核对。
        fallback = self.rubrics_dir / "rubric.json"
        print(f"[评分标准] 未找到 {specific.name}，回退到 {fallback.name}"
              f"（请确认 experiment '{experiment_code}' 是否应使用此标准）")
        return fallback

    def get_class_dir(self, semester: str, class_name: str) -> Path:
        """获取班级目录"""
        return self.teaching_dir / semester / class_name

    def get_submission_dir(self, semester: str, class_name: str, experiment_id: str) -> Path:
        """获取提交目录"""
        class_dir = self.get_class_dir(semester, class_name)
        return class_dir / experiment_id / "submissions"

    def get_experiment_paths(self, class_name: str, experiment_id: str, semester: Optional[str] = None):
        """获取实验路径配置（复用 path_config 的 ExperimentPaths）

        统一产物路径：data/teaching/<学期>/<班级>/<实验>/results/{reports,feedback,grading,plagiarism}/
        """
        from tools.common.path_config import get_experiment_paths
        return get_experiment_paths(
            semester or self.semester,
            class_name,
            experiment_id,
            project_root=self.project_root,
        )

    def get_output_dir(self, class_name: str, experiment_id: str, semester: Optional[str] = None) -> Path:
        """获取批阅产物输出目录（统一走 path_config）。

        返回 results/grading 子目录，与 teaching_scripts 链路完全一致，
        消除历史上 outputs/grading 与 data/teaching/.../results 两套路径的分叉。
        """
        return self.get_experiment_paths(class_name, experiment_id, semester).grading_dir


# 默认配置实例
default_config = AutoGradingConfig()


def get_config() -> AutoGradingConfig:
    """获取默认配置"""
    return default_config


def load_config_from_file(config_path: Path) -> AutoGradingConfig:
    """从文件加载配置（未来扩展）"""
    # TODO: 实现JSON/YAML配置文件加载
    return default_config
