#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
学生源码工程状态分类器
Source State Classifier

把「源码工程在批阅流水线里处于什么状态、为何无法机器编译」归纳为有限几种情形，
并为每种情形给出**具体的反馈原因 + 具体的改进方法**，让学生知道该怎么改。

状态分类（source_state）：
- ok            : 正常可编译的 GCC 工程（含 Makefile）—— 不产生格式反馈
- keil_only     : 纯 Keil 工程（有 MDK-ARM/.uvprojx，无 Makefile）—— GCC 编不了，判 0 + 改进方法
- nested_project: 根目录无 Makefile，但子目录里有 Makefile/.c（压缩包多套一层/多工程混装）—— 简要提示
- empty         : 源码目录为空（解压失败被清空 / 源码包内容为空）—— 简要提示
- corrupted     : 源码包损坏或格式异常（非有效 zip / 7z 改名 / 其它解压错误）—— 简要提示
- nested_archive: 解压出来仍是压缩包（zip 套 7z 等）—— 简要提示
- not_submitted : 未提交源码工程 —— 简要提示

判定依据（按优先级，命中即止）：
  1. 源码目录不存在 / 为空            → empty / not_submitted（依是否有提交记录）
  2. 目录里仍含 .zip/.7z（未解包完）  → nested_archive
  3. 有 Makefile                      → ok
  4. 有 MDK-ARM 或 .uvprojx、无Makefile → keil_only
  5. 子目录有 Makefile/.c、根目录无   → nested_project
  6. 否则                             → empty（有文件但无工程结构）

用法：
    state = SourceStateClassifier.classify(source_path, extraction_error=...)
    # state.is_machine_buildable / state.feedback_reason / state.feedback_fix
"""

from pathlib import Path
from dataclasses import dataclass
from typing import Optional

__all__ = ["SourceState", "SourceStateClassifier"]


# 源码状态枚举值
STATE_OK = "ok"
STATE_KEIL_ONLY = "keil_only"
STATE_EMPTY = "empty"
STATE_NOT_SUBMITTED = "not_submitted"
STATE_CORRUPTED = "corrupted"
STATE_NESTED_ARCHIVE = "nested_archive"
STATE_NESTED_PROJECT = "nested_project"


@dataclass
class SourceState:
    """源码工程状态及对应反馈。"""
    state: str                          # 上述 STATE_* 之一
    is_machine_buildable: bool          # 是否能走 GCC/make 机器编译
    feedback_reason: str                # 给学生的具体原因（已完整句子）
    feedback_fix: str                   # 给学生的具体改进方法（已完整句子）
    has_makefile: bool = False
    has_keil: bool = False              # 是否含 MDK-ARM/.uvprojx
    detail: str = ""                    # 诊断细节（供教师/日志，不进学生反馈）

    @property
    def is_format_problem(self) -> bool:
        """是否属于「格式问题」需要向学生反馈（ok 不需要）。"""
        return self.state != STATE_OK


class SourceStateClassifier:
    """学生源码工程状态分类器（无实例状态）。"""

    # 解压失败关键词 → 推断损坏/格式异常子类
    _CORRUPTED_KEYWORDS = ("not a zip file", "7z", "格式错误", "bad", "truncat")
    _NESTED_HINT = "压缩包内仍是压缩包"

    @classmethod
    def classify(
        cls,
        source_path: Optional[Path],
        extraction_error: Optional[str] = None,
    ) -> SourceState:
        """判定源码工程状态。

        Args:
            source_path: 学生源码目录（organizer 解压目标）。可能不存在（解压失败已清空）。
            extraction_error: organizer 记录的解压失败原因（可选）。
        """
        # 1) 有解压失败记录 → 按原因细分 corrupted / nested_archive
        if extraction_error:
            low = extraction_error.lower()
            if "压缩包内" in extraction_error or cls._NESTED_HINT in extraction_error:
                return cls._nested_archive(extraction_error)
            # 7z 改名 / 非有效 zip / 其它损坏
            return cls._corrupted(extraction_error)

        # 2) 目录不存在或为空
        if source_path is None or not source_path.exists() or not source_path.is_dir():
            return cls._not_submitted()
        try:
            entries = [p for p in source_path.iterdir()]
        except (PermissionError, OSError):
            return cls._not_submitted()
        if not entries:
            return cls._empty()

        # 3) 解压出来仍是压缩包（zip 套 7z 等）
        archives = [p for p in entries if p.is_file() and p.suffix.lower() in (".zip", ".7z", ".rar")]
        if archives and len(entries) == len(archives):
            return cls._nested_archive(f"源码目录里只有压缩包：{', '.join(p.name for p in archives[:3])}")

        # 4) 有 Makefile → 可机器编译
        if cls._has_makefile(source_path):
            return SourceState(
                state=STATE_OK,
                is_machine_buildable=True,
                feedback_reason="",
                feedback_fix="",
                has_makefile=True,
            )

        # 5) 有 MDK-ARM / .uvprojx 但无 Makefile → 纯 Keil 工程
        has_keil = cls._has_keil(source_path)
        if has_keil:
            return cls._keil_only()

        # 6) 根目录无 Makefile/Keil，但子目录里有 Makefile 或 .c → 嵌套/多工程打包
        #    （压缩包多套了一层文件夹，或多个工程混装；批阅工具按根目录找不到工程）
        nested = cls._nested_detail(source_path)
        if nested:
            return cls._nested_project(nested)

        # 7) 有文件但无任何工程结构 → 视为空/异常
        return cls._empty(detail=f"目录有 {len(entries)} 个条目但无工程结构")

    # ------------------------------------------------------------------
    # 各状态构造
    # ------------------------------------------------------------------
    @staticmethod
    def _has_makefile(d: Path) -> bool:
        # 顶层 Makefile 即可（flatten 后应在顶层）
        return (d / "Makefile").is_file()

    @classmethod
    def _has_keil(cls, d: Path) -> bool:
        if (d / "MDK-ARM").is_dir():
            return True
        return any(d.glob("*.uvprojx")) or any(d.glob("MDK-ARM/*.uvprojx"))

    @classmethod
    def _nested_detail(cls, d: Path) -> str:
        """根目录无工程结构，但子目录里有 Makefile 或 .c 源文件 → 返回诊断串；否则 ''。

        判定信号：Makefile 或 .c 出现在**子目录**（深度≥1）。根目录的 Makefile 已被
        ``_has_makefile`` 排除（命中即 STATE_OK，不会走到这里），故这里命中即代表工程
        被埋在子目录里——典型的"压缩包多套一层"或"多工程混装"。
        """
        sub_makefiles = []          # 子目录里的 Makefile 父目录
        c_top_dirs = set()           # 含 .c 的顶层子目录名
        c_count = 0
        for p in d.rglob("*"):
            if not p.is_file():
                continue
            parts = p.relative_to(d).parts
            if len(parts) < 2:
                continue            # 根目录文件不计
            top = parts[0]
            if p.name == "Makefile":
                sub_makefiles.append(p.parent)
                c_top_dirs.add(top)
            elif p.suffix.lower() == ".c":
                c_count += 1
                c_top_dirs.add(top)
            if c_count >= 300 and not sub_makefiles:
                break               # 防爆：足够判定即可
        if not sub_makefiles and c_count == 0:
            return ""
        sample = ", ".join(sorted(c_top_dirs)[:4])
        if sub_makefiles:
            mk = ", ".join(
                sorted({str(p.relative_to(d)).replace("\\", "/") for p in sub_makefiles[:4]})
            )
            return (f"根目录无 Makefile，但子目录({sample})内有 Makefile({mk})——"
                    "压缩包多套了一层文件夹，或多个工程混装在一起")
        return (f"根目录无 Makefile/工程结构，但子目录({sample})内有 {c_count} 个 .c 源文件——"
                "疑似压缩包多套了一层文件夹，或多个工程打包在一起")

    @staticmethod
    def _nested_project(detail: str) -> SourceState:
        return SourceState(
            state=STATE_NESTED_PROJECT,
            is_machine_buildable=False,
            feedback_reason=(
                "源码包解压后是嵌套/多工程结构：根目录没有 Makefile，工程文件散落在子目录里。"
                "批阅工具按根目录定位工程，找不到唯一的可编译工程，因此无法机器编译。"
            ),
            feedback_fix=(
                "改进方法：请只提交一个工程文件夹——让含 Makefile 的工程目录成为压缩包的根"
                "（解压后第一层就能直接看到 Makefile / Core / Drivers），不要在压缩包里再套一层"
                "或多层文件夹，也不要把多个工程打包在一起。重新打包后请自己解压验证：解压出来"
                "的第一层就有 Makefile。"
            ),
            detail=detail,
        )

    @staticmethod
    def _keil_only() -> SourceState:
        return SourceState(
            state=STATE_KEIL_ONLY,
            is_machine_buildable=False,
            has_keil=True,
            feedback_reason=(
                "源码是纯 Keil（MDK-ARM）工程，未包含 Makefile，"
                "无法用本课程的机器批阅工具链（arm-none-eabi-gcc + make）编译。"
            ),
            feedback_fix=(
                "改进方法：用 STM32CubeMX 重新生成工程时，在 Project Manager → Toolchain/IDE "
                "选择 \"Makefile\" 并重新生成；或在现有 MDK 工程基础上补一个 Makefile。"
                "生成后请确认工程根目录下存在 Makefile 文件再提交。"
            ),
            detail="含 MDK-ARM/.uvprojx，无 Makefile",
        )

    @staticmethod
    def _corrupted(error: str) -> SourceState:
        return SourceState(
            state=STATE_CORRUPTED,
            is_machine_buildable=False,
            feedback_reason=(
                "提交的源码压缩包无法解压（可能已损坏，或把 .7z 等格式改成了 .zip 后缀）。"
                f"系统提示：{error}"
            ),
            feedback_fix=(
                "改进方法：请重新打包源码，确保使用标准 zip 或 7z 格式，"
                "不要手动修改文件后缀；打包后建议自己先解压验证一次再提交。"
            ),
            detail=error,
        )

    @staticmethod
    def _nested_archive(hint: str) -> SourceState:
        return SourceState(
            state=STATE_NESTED_ARCHIVE,
            is_machine_buildable=False,
            feedback_reason=(
                "提交的源码包里又套了一层压缩包（如 zip 里装 .7z），"
                "批阅工具只解压了一层，真正的工程没被解开。"
            ),
            feedback_fix=(
                "改进方法：请只打包一层——直接把工程文件夹（含 Makefile/Core 等）压成一个 "
                "zip 或 7z，不要在压缩包里再放压缩包。"
            ),
            detail=hint,
        )

    @staticmethod
    def _empty(detail: str = "") -> SourceState:
        return SourceState(
            state=STATE_EMPTY,
            is_machine_buildable=False,
            feedback_reason="提交的源码包解压后没有内容（压缩包为空或解压后为空目录）。",
            feedback_fix="改进方法：请确认压缩包里确实包含了完整的工程文件夹，重新打包后再提交。",
            detail=detail,
        )

    @staticmethod
    def _not_submitted() -> SourceState:
        return SourceState(
            state=STATE_NOT_SUBMITTED,
            is_machine_buildable=False,
            feedback_reason="未找到源码工程（提交包里没有源码压缩包）。",
            feedback_fix="改进方法：请在提交包中附上源码工程压缩包（zip 或 7z，内含完整工程文件夹）。",
        )
