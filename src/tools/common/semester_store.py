# -*- coding: utf-8 -*-
"""学期模板存储（共享层）：两端 GUI 的实验清单/专业/课程类型统一数据源。

2026-10 结构收口：原先住在 teaching_management_gui.path_helper（教师端包），
学生端跨包反向依赖；现下沉至 tools/common，两端同等 import。
path_helper 保留同名转发（旧调用方零改动）。
"""
import sys
from pathlib import Path

from tools.common.path_config import PROJECT_ROOT

SEMESTERS_DIR = PROJECT_ROOT / "data" / "semesters"

# 最后回退清单（仅当学期模板与 config.yaml 均不可用时）
_DEFAULT_EXPERIMENTS = [
    {"id": "07-car-gear", "name": "汽车档位模拟器设计"},
    {"id": "01-turn-signal", "name": "转向灯控制系统"},
]


def list_semesters() -> list:
    """列出已有学期模板（data/semesters/ 下含 experiments.yaml 的目录），新→旧排序。"""
    result = []
    try:
        if SEMESTERS_DIR.exists():
            for d in SEMESTERS_DIR.iterdir():
                if d.is_dir() and (d / "experiments.yaml").exists():
                    result.append(d.name)
    except Exception:
        pass
    return sorted(result, reverse=True)


def load_experiments(semester: str = None, major: str = None,
                     course_type: str = None) -> list:
    """读取实验列表 [{'id','name'}]。

    过滤维度：学期（模板定位）→ 专业（majors 声明，缺省通用）→ 课程类型
    （type 声明，缺省不限）。加载链：学期模板 → 全局 config.yaml（冻结）→ 内置。
    """
    def _major_ok(info: dict) -> bool:
        if not major:
            return True
        majors = info.get("majors")
        if not majors:
            return True
        return any(major in m for m in majors)

    def _type_ok(info: dict) -> bool:
        if not course_type or course_type in ("", "全部"):
            return True
        return info.get("type") == course_type

    # 1) 学期模板
    if semester:
        try:
            import yaml
            sem_path = SEMESTERS_DIR / semester / "experiments.yaml"
            if sem_path.exists():
                with open(sem_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                exps = data.get("experiments") or {}
                result = []
                for eid, info in exps.items():
                    if not isinstance(info, dict):
                        continue
                    if not _major_ok(info) or not _type_ok(info):
                        continue
                    result.append({"id": eid, "name": info.get("name", eid)})
                if result:
                    return result
        except Exception:
            pass
    # 2) 全局 config.yaml（冻结回退）
    try:
        import yaml
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


def list_majors(semester: str = None) -> list:
    """某学期出现过的专业（条目 majors 字段并集，支持"专业A、专业B"分组写法）。"""
    try:
        import yaml
        if not semester:
            return []
        sem_path = SEMESTERS_DIR / semester / "experiments.yaml"
        if not sem_path.exists():
            return []
        with open(sem_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        majors = []
        for info in (data.get("experiments") or {}).values():
            if isinstance(info, dict):
                for grp in info.get("majors") or []:
                    for m in str(grp).split("、"):
                        m = m.strip()
                        if m and m not in majors:
                            majors.append(m)
        return majors
    except Exception:
        return []


def list_course_types(semester: str = None) -> list:
    """某学期出现过的课程类型（条目 type 字段并集）。"""
    try:
        import yaml
        if not semester:
            return []
        sem_path = SEMESTERS_DIR / semester / "experiments.yaml"
        if not sem_path.exists():
            return []
        with open(sem_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        types = []
        for info in (data.get("experiments") or {}).values():
            if isinstance(info, dict):
                t = info.get("type")
                if t and t not in types:
                    types.append(t)
        return types
    except Exception:
        return []


def experiment_choices(semester: str = None, major: str = None,
                       course_type: str = None) -> list:
    """[(id, name), ...] 供下拉框使用。"""
    return [(e["id"], e["name"]) for e in
            load_experiments(semester, major, course_type)]


def match_experiment(text: str, semester: str = None) -> str:
    """从文本（如 ZIP 文件名）匹配实验 ID（包含 id 或中文名即命中）。"""
    if not text:
        return None
    for exp in load_experiments(semester):
        eid = exp.get("id", "")
        name = exp.get("name", "")
        if eid and eid in text:
            return eid
        if name and name in text:
            return eid
    return None
