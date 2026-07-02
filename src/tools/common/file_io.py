#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
原子文件写入工具

为教学管线（评分/查重/成绩册）提供“先写临时文件再 os.replace”的写入语义，
避免进程在写入中途崩溃（OOM、断电、KeyboardInterrupt）时留下截断/空文件——
那种截断文件会被下游阶段当作“空提交”，静默产出 0 分或空报告。

os.replace 在同一卷上是原子的：要么完整切到新内容，要么保留旧内容，
不存在“写了一半”的中间态。
"""

import json
import os
from pathlib import Path
from typing import Any, Union

PathLike = Union[str, Path]


def atomic_write_json(path: PathLike, data: Any, **json_kwargs: Any) -> Path:
    """原子写入 JSON。

    Args:
        path: 目标路径。父目录会自动创建。
        data: 可被 json 序列化的对象。
        **json_kwargs: 透传给 json.dump（如 ensure_ascii=False, indent=2）。

    Returns:
        最终写入的目标 Path。
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, **json_kwargs)
    os.replace(tmp, target)
    return target


def atomic_write_text(path: PathLike, text: str, encoding: str = "utf-8") -> Path:
    """原子写入纯文本。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with open(tmp, "w", encoding=encoding) as f:
        f.write(text)
    os.replace(tmp, target)
    return target
