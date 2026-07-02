#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
学生提交源码规整器
Submission Normalizer

消除学生源码包解压后多余的「包装层」目录嵌套，让真正的 STM32 工程根
（含 Makefile / Core / MDK-ARM / .ioc 等）落到源码目录顶层，从而被
BuildChecker 与 SubmissionProcessor 正确识别。

典型场景（期末综合项目实测）::

    ...-源代码/                ← 源码根（ organizer 解压源码包到此）
      └─ QIMO/                 ← 包装层 1
         └─ QIMO/              ← 包装层 2（真正的 CubeMX 工程根）
            ├─ Makefile
            ├─ Core/  Drivers/  MDK-ARM/
            └─ QIMO.ioc

flatten() 后::

    ...-源代码/
      ├─ Makefile
      ├─ Core/  Drivers/  MDK-ARM/
      └─ QIMO.ioc

设计要点（破坏式扁平化的安全性）
- **仅在「纯包装链」时执行**：从源码根下探，要求每一层中间目录有且仅有一个
  子目录、且无散落文件；否则视为不可安全移动，原样保留并返回放弃原因。
- **ABORT 路径绝不改动目录树**；只有全部校验通过后才移动文件。
- **移动前碰撞预检**：工程根的每个条目名不得已存在于源码根，绝不覆盖。
- **永不跟随符号链接**：链中一旦出现 symlink 立即放弃。
- 工程根标记刻意**不**含裸 ``*.c``/``*.h``（会误判任何含 .c 的目录），
  要求结构性标记（Makefile / Core / MDK-ARM / Drivers / .ioc / .uvprojx / .mxproject）。
"""

import os
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple, List

__all__ = ["SubmissionNormalizer", "NormalizeResult"]


@dataclass
class NormalizeResult:
    """flatten() 的返回结果。"""
    flattened: bool                       # 是否执行了扁平化（移动了文件）
    source_dir: Path                      # 源码根目录
    located_root: Optional[Path]          # 定位到的真正工程根（未找到则 None）
    original_depth: int                   # 工程根相对 source_dir 的层数（0=已在顶层）
    reason: str                           # 人类可读说明
    skip_cause: Optional[str] = None      # 放弃原因码（见 _CAUSE_*）

    # 放弃原因码
    _CAUSE_ALREADY_FLAT = "already_flat"
    _CAUSE_NO_PROJECT = "no_project_root"
    _CAUSE_AMBIGUOUS = "ambiguous_siblings"
    _CAUSE_EXTRA_FILES = "wrapper_has_extra_files"
    _CAUSE_COLLISION = "name_collision"
    _CAUSE_MULTIPLE = "multiple_candidates"
    _CAUSE_SYMLINK = "symlink_encountered"
    _CAUSE_PERMISSION = "permission_error"


class SubmissionNormalizer:
    """学生提交源码规整器（无实例状态，全部 classmethod/staticmethod）。"""

    # 工程根标记：必须有**文件型构建标记**。不能仅凭 Core/MDK-ARM/Drivers 目录名判定——
    # 否则"源码根只含一个同名包装目录(如 Drivers/)"会被误判为工程根，flatten 漏修嵌套
    # （刘烊宏场景：包多套一层 Drivers/，根目录无 Makefile → 误判 already_flat）。
    _FILE_MARKERS: Tuple[str, ...] = ("Makefile", ".mxproject")          # 根目录精确文件
    _GLOB_MARKERS: Tuple[str, ...] = ("*.ioc", "*.uvprojx")              # 根目录 glob 文件
    _SUB_GLOB_MARKERS: Tuple[str, ...] = ("MDK-ARM/*.uvprojx",)          # Keil: .uvprojx 在 MDK-ARM/ 下

    # 下探深度上限：真实嵌套为 2 层；8 层防病态/恶意树与无限循环
    MAX_DEPTH = 8
    # locate_project_root 自由搜索时的节点上限（防爆栈式 CMSIS 树）
    _MAX_LOCATE_NODES = 20000

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------
    @classmethod
    def is_project_root(cls, d: Path) -> bool:
        """目录 d 是否为一个 STM32 工程根——必须含**文件型构建标记**
        (Makefile / .mxproject / *.ioc / *.uvprojx / MDK-ARM/*.uvprojx)。

        刻意**不**仅凭 Core/Drivers/MDK-ARM 目录名判定：那会把"只含一个同名包装目录"
        的源码根误判为工程根(如 Drivers/ 包装层)，导致 flatten 误认 already_flat、嵌套
        工程无法自动修复。真实工程根必有构建文件（GCC 有 Makefile，CubeMX 有 .ioc，
        Keil 有 .uvprojx）。
        """
        if not d.is_dir():
            return False
        for name in cls._FILE_MARKERS:
            if (d / name).is_file():
                return True
        for pat in cls._GLOB_MARKERS:
            if any(d.glob(pat)):
                return True
        for pat in cls._SUB_GLOB_MARKERS:
            if any(d.glob(pat)):
                return True
        return False

    @classmethod
    def locate_project_root(cls, root: Path) -> Optional[Tuple[Path, int]]:
        """在 root 子树中找**最浅**的工程根，返回 (路径, 相对层数)；root 自身算第 0 层。

        用广度优先逐层搜索，命中即返回（保证最浅）。找不到返回 None。
        不跟随符号链接；深度与节点数有上限。
        """
        if not root.is_dir():
            return None
        if cls.is_project_root(root):
            return (root, 0)
        frontier: List[Path] = [root]
        seen = 0
        for depth in range(1, cls.MAX_DEPTH + 1):
            nxt: List[Path] = []
            for d in frontier:
                try:
                    names = os.listdir(d)
                except (PermissionError, OSError):
                    continue
                for name in names:
                    seen += 1
                    if seen > cls._MAX_LOCATE_NODES:
                        return None
                    e = d / name
                    if e.is_symlink():
                        continue
                    if not e.is_dir():
                        continue
                    if cls.is_project_root(e):
                        return (e, depth)
                    nxt.append(e)
            if not nxt:
                return None
            frontier = nxt
        return None

    @classmethod
    def flatten(cls, source_dir: Path) -> NormalizeResult:
        """破坏式扁平化：若 source_dir 下存在纯包装链通向工程根，
        则把工程根的内容上移到 source_dir 顶层并删除空壳目录。

        任何不安全情形都原样保留目录树并返回带 skip_cause 的 NormalizeResult。
        本方法**永不抛异常**（供 organizer 在普通流程中直接调用）。
        """
        source_dir = Path(source_dir)

        # STEP 0：守卫
        if not source_dir.exists() or not source_dir.is_dir():
            return NormalizeResult(
                flattened=False, source_dir=source_dir, located_root=None,
                original_depth=0,
                reason="源码目录不存在或不可访问",
                skip_cause=NormalizeResult._CAUSE_PERMISSION,
            )

        # STEP 1：工程已在顶层 → 无需处理
        if cls.is_project_root(source_dir):
            return NormalizeResult(
                flattened=False, source_dir=source_dir, located_root=source_dir,
                original_depth=0,
                reason="工程根已在源码目录顶层，无需扁平化",
                skip_cause=NormalizeResult._CAUSE_ALREADY_FLAT,
            )

        # STEP 2：沿「单子包装链」下探，定位工程根
        current = source_dir
        wrappers: List[Path] = []      # 中间包装层（待删除），不含 source_dir 与工程根本体
        project_root: Optional[Path] = None
        project_depth = 0

        for depth in range(1, cls.MAX_DEPTH + 1):
            try:
                entries = [current / n for n in os.listdir(current)]
            except (PermissionError, OSError):
                return NormalizeResult(
                    flattened=False, source_dir=source_dir, located_root=None,
                    original_depth=0,
                    reason=f"读取目录失败：{current}",
                    skip_cause=NormalizeResult._CAUSE_PERMISSION,
                )

            # 永不跟随符号链接
            if any(e.is_symlink() for e in entries):
                return NormalizeResult(
                    flattened=False, source_dir=source_dir, located_root=None,
                    original_depth=0,
                    reason=f"包装链中存在符号链接：{current}",
                    skip_cause=NormalizeResult._CAUSE_SYMLINK,
                )

            n = len(entries)
            if n == 0:
                return NormalizeResult(
                    flattened=False, source_dir=source_dir, located_root=None,
                    original_depth=0,
                    reason=f"未找到工程根（链断于空目录：{current}）",
                    skip_cause=NormalizeResult._CAUSE_NO_PROJECT,
                )
            if n > 1:
                return NormalizeResult(
                    flattened=False, source_dir=source_dir, located_root=None,
                    original_depth=0,
                    reason=f"目录含多个条目，无法安全扁平化：{current}",
                    skip_cause=NormalizeResult._CAUSE_AMBIGUOUS,
                )

            only = entries[0]
            # 唯一子是文件（或非常规目录）→ 不是工程，不可继续
            if not only.is_dir():
                return NormalizeResult(
                    flattened=False, source_dir=source_dir, located_root=None,
                    original_depth=0,
                    reason=f"包装层唯一子不是目录：{only}",
                    skip_cause=NormalizeResult._CAUSE_EXTRA_FILES,
                )

            # 命中工程根 → 记录并停止（最浅优先）
            if cls.is_project_root(only):
                project_root = only
                project_depth = depth
                break

            # 继续下探
            wrappers.append(only)
            current = only
        else:
            # 循环耗尽仍未找到工程根
            return NormalizeResult(
                flattened=False, source_dir=source_dir, located_root=None,
                original_depth=0,
                reason=f"超过 {cls.MAX_DEPTH} 层仍未找到工程根",
                skip_cause=NormalizeResult._CAUSE_NO_PROJECT,
            )

        # STEP 3：交叉验证——自由搜索应定位到同一工程根，否则视为多工程/歧义
        located = cls.locate_project_root(source_dir)
        if located is None or located[0] != project_root:
            return NormalizeResult(
                flattened=False, source_dir=source_dir, located_root=project_root,
                original_depth=project_depth,
                reason="检测到多个候选工程根或定位不一致，放弃扁平化",
                skip_cause=NormalizeResult._CAUSE_MULTIPLE,
            )

        # STEP 4：移动前碰撞预检（绝不覆盖）
        try:
            existing = set(os.listdir(source_dir))
            project_entries = os.listdir(project_root)
        except (PermissionError, OSError):
            return NormalizeResult(
                flattened=False, source_dir=source_dir, located_root=project_root,
                original_depth=project_depth,
                reason=f"列举目录失败（权限）：{project_root}",
                skip_cause=NormalizeResult._CAUSE_PERMISSION,
            )
        # source_dir 现存条目里，除包装链顶层外，若与工程根条目同名则碰撞
        top_wrapper = wrappers[0].name if wrappers else project_root.name
        for name in project_entries:
            if name in existing and name != top_wrapper:
                return NormalizeResult(
                    flattened=False, source_dir=source_dir, located_root=project_root,
                    original_depth=project_depth,
                    reason=f"移动将覆盖已存在的条目：{name}",
                    skip_cause=NormalizeResult._CAUSE_COLLISION,
                )

        # STEP 5+6：上移工程根全部内容到 source_dir。
        # 经同卷临时目录中转，避开"工程根某子条目与工程根/包装层同名"的移动碰撞——如工程根
        # 名为 Drivers、其下又有 HAL 的 Drivers/（刘烊宏场景），直接 move 会让 Drivers/Drivers
        # 落到仍存在的工程根上而失败。同卷 rename 不拷贝内容，深树也不受 Windows 路径长限制。
        # 流程：工程根内容 → 临时目录 → 删空工程根/包装层(释放同名) → 临时目录内容 → source_dir。
        import tempfile
        work = Path(tempfile.mkdtemp(prefix="_flatten_", dir=str(source_dir.parent)))
        try:
            for name in project_entries:
                shutil.move(str(project_root / name), str(work / name))
            # 删除空的工程根 + 包装层，释放可能同名的位置（含工程根本身的名字）
            for d in [project_root] + list(reversed(wrappers)):
                try:
                    d.rmdir()
                except OSError:
                    pass
            # 此时 source_dir 中原包装链已清空，同名位置空出；把临时目录内容回搬
            for name in os.listdir(work):
                shutil.move(str(work / name), str(source_dir / name))
        except (PermissionError, OSError) as e:
            # 移动中途失败：source_dir 原结构基本未动（内容先去了临时目录），尽力保留可识别状态
            return NormalizeResult(
                flattened=False, source_dir=source_dir, located_root=project_root,
                original_depth=project_depth,
                reason=f"移动文件失败（部分内容可能已转存到临时目录）：{e}",
                skip_cause=NormalizeResult._CAUSE_PERMISSION,
            )
        finally:
            try:
                work.rmdir()   # 已搬空则删；非空(best-effort)忽略
            except OSError:
                pass

        return NormalizeResult(
            flattened=True, source_dir=source_dir, located_root=source_dir,
            original_depth=project_depth,
            reason=f"已扁平化（原嵌套 {project_depth} 层）",
            skip_cause=None,
        )
