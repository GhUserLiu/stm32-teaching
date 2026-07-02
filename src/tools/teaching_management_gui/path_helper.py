#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GUI 统一路径解析工具
Path Helper for Teaching Management GUI

所有面板/对话框通过本模块解析实验路径，避免硬编码 "outputs/grading"。
路径约定统一走 src/tools/common/path_config.py 的 ExperimentPaths，
即 data/teaching/<学期>/<班级>/<实验>/results/{reports,feedback,grading,plagiarism}/，
与 auto_grading 后端、teaching_scripts 链路保持一致。
"""

import sys
import re
from pathlib import Path
from typing import Optional, Tuple

# 定位项目根目录
# - 开发态：本文件位于 src/tools/teaching_management_gui/，向上 4 级到仓库根
# - 冻结态（PyInstaller）：__file__ 在 sys._MEIPASS 下，且 pathex=['src'] 会把 src/
#   这一级剥离，再向上 4 级会落到 _MEIPASS 的「父目录」而找不到 data/。
#   故冻结态直接以 sys._MEIPASS（onefile）或 exe 同级（onedir）为根。
def _resolve_project_root() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).parent.parent.parent.parent


PROJECT_ROOT = _resolve_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 默认学期；后续可改为下拉选择
DEFAULT_SEMESTER = "2026-春季"

from tools.common.path_config import get_experiment_paths, ExperimentPaths  # noqa: E402


def resolve_experiment(
    class_name: str,
    experiment_id: str,
    semester: Optional[str] = None,
) -> ExperimentPaths:
    """解析实验路径配置。

    Args:
        class_name: 班级名称，如 "汽服2302B班"
        experiment_id: 实验 ID，如 "07-car-gear"
        semester: 学期，默认 DEFAULT_SEMESTER

    Returns:
        ExperimentPaths 实例（含 grading_dir / plagiarism_dir / feedback_dir / reports_dir 等）
    """
    return get_experiment_paths(
        semester or DEFAULT_SEMESTER,
        class_name,
        experiment_id,
        project_root=PROJECT_ROOT,
    )


def grading_dir(class_name: str, experiment_id: str, semester: Optional[str] = None) -> Path:
    """批阅产物目录：results/grading"""
    return resolve_experiment(class_name, experiment_id, semester).grading_dir


def plagiarism_dir(class_name: str, experiment_id: str, semester: Optional[str] = None) -> Path:
    """查重产物目录：results/plagiarism"""
    return resolve_experiment(class_name, experiment_id, semester).plagiarism_dir


def feedback_dir(class_name: str, experiment_id: str, semester: Optional[str] = None) -> Path:
    """反馈产物目录：results/feedback"""
    return resolve_experiment(class_name, experiment_id, semester).feedback_dir


def reports_dir(class_name: str, experiment_id: str, semester: Optional[str] = None) -> Path:
    """教师报告目录：results/reports"""
    return resolve_experiment(class_name, experiment_id, semester).reports_dir


def cross_class_dir(semester: Optional[str] = None, kind: str = "plagiarism") -> Path:
    """跨班级产物目录（学期根下 ``_跨班级比对/<kind>/``）。

    多班级查重等「合并结果」此前只落到 ``entries[0]`` 班级目录，其余班归档时无痕迹；
    统一落到学期根下的中立目录，位置可预测、各班都能找到。
    """
    from tools.common.path_config import get_teaching_paths
    sem = semester or DEFAULT_SEMESTER
    tp = get_teaching_paths(PROJECT_ROOT)
    return tp.get_semester_dir(sem) / "_跨班级比对" / kind


# 实验 ID 合法形态：字母/数字/下划线/短横线（如 07-car-gear），不含中文/空格/括号
_EXPERIMENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def parse_class_experiment_from_zip(stem: str) -> Tuple[str, Optional[str]]:
    """从班级压缩包文件名（去扩展名）解析班级名与实验ID。

    约定的合法命名形如 ``班级-实验ID``（例：``汽服2302B班-07-car-gear``）。
    现实中学习通导出的文件名常为 ``班级-_实验报告（第N次实验 …）(附件) (k).zip``，
    这类后缀不是实验 ID，不能误填，否则产物会落到垃圾路径。

    Args:
        stem: 文件名（不含扩展名）

    Returns:
        (class_name, experiment_id_or_None)
        - class_name: 第一个 ``-`` 之前的部分（班级名）
        - experiment_id: 仅当后缀符合实验ID形态时返回，否则返回 None（留给用户手动填写）
    """
    if not stem:
        return "", None
    parts = stem.split("-", 1)
    class_name = parts[0]
    experiment_id: Optional[str] = None
    if len(parts) == 2:
        candidate = parts[1]
        if _EXPERIMENT_ID_RE.match(candidate):
            experiment_id = candidate
    return class_name, experiment_id


# ---- 已知实验（下拉框数据源 + 自动匹配）----
# 优先从 data/config/teaching/config.yaml 的 experiments 段读取；读取失败时回退内置清单
_DEFAULT_EXPERIMENTS = [
    {"id": "07-car-gear", "name": "汽车档位模拟器设计"},
    {"id": "01-turn-signal", "name": "转向灯控制系统"},
]


def load_experiments() -> list:
    """读取已知实验列表 [{id, name}, ...]。优先 config.yaml，失败回退内置清单。"""
    try:
        import yaml  # PyYAML（可选）
        cfg_path = PROJECT_ROOT / "data" / "config" / "teaching" / "config.yaml"
        if cfg_path.exists():
            with open(cfg_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            exps = data.get("experiments") or {}
            result = []
            for eid, info in exps.items():
                if not isinstance(info, dict):
                    continue
                result.append({"id": eid, "name": info.get("name", eid)})
            if result:
                return result
    except Exception:
        pass
    return list(_DEFAULT_EXPERIMENTS)


def experiment_choices() -> list:
    """[(id, name), ...] 供下拉框使用。"""
    return [(e["id"], e["name"]) for e in load_experiments()]


def match_experiment(text: str) -> Optional[str]:
    """从文本（如 ZIP 文件名）自动匹配实验 ID。

    匹配规则：文本中包含实验 ID 或实验中文名即命中。
    例：文件名含「汽车档位模拟器设计」→ 命中 07-car-gear。
    匹配不到返回 None（由用户从下拉框选择）。
    """
    if not text:
        return None
    for exp in load_experiments():
        eid = exp.get("id", "")
        name = exp.get("name", "")
        if eid and eid in text:
            return eid
        if name and name in text:
            return eid
    return None
