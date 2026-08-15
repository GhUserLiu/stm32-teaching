#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KeilProjectParser -- extract USER business-logic sources from a .uvprojx.

Why (2026-08 diagnosis, Keil-project pain point): students submit Keil
projects (.uvprojx); the toolchain only globs the file and hands it to
UV4.exe (disabled by default), while vendor boilerplate (CMSIS / HAL)
dominates any naive code comparison and drowns the signals that matter
(CAN/SPI driver logic, app state machines). This parser is the bridge:
.uvprojx -> user source files -> user-written code sections -> ready for
the CODE-modality similarity engines.

Security: student files are UNTRUSTED XML -- parsing goes through
defusedxml (project convention, CLAUDE.md 安全约定 #3; entity-expansion
attacks are blocked). FilePaths are also untrusted: a path that resolves
OUTSIDE the project tree (absolute paths, ..-escapes) is never read and
is recorded in ``last_flagged_paths`` for upstream reporting.

Robustness (each rule below fixed an adversarial-review finding):
  * both uvprojx flavors parse -- bare tags (noNamespaceSchemaLocation,
    the repo's real 07-car-gear file) and default-xmlns variants, via
    namespace-stripped local-name matching;
  * multi-target projects (Debug/Release) dedupe by resolved path, so no
    student's code is double-counted against single-target classmates;
  * element order inside <File> does not matter (FileName/FilePath in
    either order; a missing FileName falls back to the path basename);
  * GBK/GB2312: source files fall back from UTF-8 to GBK decoding
    (Keil on Chinese Windows writes GBK comments), and a multi-byte-
    declared uvprojx is decoded before parsing (pyexpat refuses such
    declarations).

Vendor classification (directory-anchored, NOT basename-substring --
"my_drivers.c" and "MyDrivers/can.c" are USER code at an automotive
college and must survive):
  1. directory-component match: a component equals a VENDOR_DIR name or
     ends with "_<name>" ("Drivers", "CMSIS", "STM32F4xx_HAL_Driver",
     "MDK-ARM", "Middlewares", "FreeRTOS", ...). The FILE NAME is never
     matched against path fragments;
  2. VENDOR_FILE_PREFIXES: CubeMX/vendor file names (stm32f4xx_hal_*,
     system_stm32*, startup_*, syscalls/sysmem);
  3. extension filter (.c/.h only -- drops .s/.o/lib entries);
  4. ``allowlist`` fragments always win (substring, site-specific).
Scaffold files (stm32f4xx_it.c / stm32f4xx_hal_msp.c) are vendor (their
unmarked bulk is CubeMX-generated and near-identical across students)
BUT their /* USER CODE */ sections still flow into user_code_text() --
that is where students write EXTI/UART ISR logic in this course.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from defusedxml import ElementTree as SafeET

# Vendor directory names: a path component matches when it EQUALS one of
# these (case-insensitive) or ends with "_<name>" (STM32F4xx_HAL_Driver).
VENDOR_DIR_NAMES = (
    "cmsis", "drivers", "stm32f4xx_hal_driver", "mdk-arm",
    "middleware", "middlewares", "freertos", "rtos", "rtthread", "lwip",
)
# Vendor/cube-generated file name prefixes (matched against the basename).
VENDOR_FILE_PREFIXES = (
    "stm32f4xx_hal_", "stm32f4xx_ll_", "system_stm32", "startup_",
    "syscalls", "sysmem",
)
# Scaffold files: vendor overall, but their USER CODE sections count.
VENDOR_SCAFFOLD_PREFIXES = ("stm32f4xx_it", "stm32f4xx_hal_msp")

USER_CODE_BEGIN = "/* USER CODE BEGIN"
USER_CODE_END = "/* USER CODE END"

# Multi-byte XML declarations pyexpat refuses; decoded before parsing.
_MULTIBYTE_DECL_RE = re.compile(
    rb'^<\?xml[^>]*encoding=["\'](gb2312|gbk|gb18030|big5)', re.IGNORECASE)


@dataclass
class KeilSourceFile:
    """One source file referenced by the Keil project."""

    name: str
    path: Path                 # resolved absolute path (may not exist)
    group: str                 # Keil <GroupName> it belongs to
    is_vendor: bool
    scaffold: bool = False     # vendor file whose USER CODE sections count
    user_sections: List[Tuple[str, str]] = field(default_factory=list)
    # (marker_name, code) pairs from /* USER CODE BEGIN x */ ... END blocks


def _local(tag: str) -> str:
    """Strip any XML namespace: '{ns}File' -> 'file'; bare tags unchanged."""
    return tag.rsplit("}", 1)[-1].lower()


def _read_text(path: Path) -> str:
    """UTF-8 first, GBK fallback (Keil on Chinese Windows writes GBK)."""
    data = path.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("gbk", errors="replace")


class KeilProjectParser:
    """Parse .uvprojx, classify vendor vs user sources, extract USER CODE.

    After each parse(), ``last_flagged_paths`` lists FilePaths that tried
    to escape the project tree (absolute paths / ..-escapes) -- they are
    marked vendor and never read.
    """

    def __init__(
        self,
        extra_excludes: Sequence[str] = (),
        allowlist: Sequence[str] = (),
    ) -> None:
        """
        Args:
            extra_excludes: additional vendor dir names (site-specific)
            allowlist: path fragments that ALWAYS count as user code
        """
        self._excludes = tuple(
            n.lower() for n in VENDOR_DIR_NAMES + tuple(extra_excludes))
        self._allow = tuple(f.lower() for f in allowlist)
        self.last_flagged_paths: List[str] = []

    # ------------------------------------------------------------------ API

    def parse(self, uvprojx_path: Path) -> List[KeilSourceFile]:
        """All .c/.h files referenced by the project (vendor + user)."""
        uvprojx_path = Path(uvprojx_path)
        root = self._parse_xml(uvprojx_path)
        project_dir = uvprojx_path.resolve().parent
        tree_root = project_dir.parent   # MDK-ARM/.. == the project tree

        self.last_flagged_paths = []
        files: List[KeilSourceFile] = []
        seen: set = set()               # dedupe across multiple <Target>s
        current_group = ""
        pending: Optional[dict] = None

        def _flush():
            nonlocal pending
            if pending is None:
                return
            entry = self._classify(pending, current_group,
                                   project_dir, tree_root)
            if entry is not None:
                key = str(entry.path).lower()
                if key not in seen:     # multi-target: referenced twice
                    seen.add(key)
                    files.append(entry)
            pending = None

        for elem in root.iter():
            tag = _local(elem.tag)
            text = (elem.text or "").strip()
            if tag == "groupname":
                _flush()
                current_group = text
            elif tag == "file":
                _flush()
                pending = {}
            elif pending is not None and tag in ("filename", "filepath"):
                pending[tag] = text
        _flush()
        return files

    def user_sources(self, uvprojx_path: Path) -> List[KeilSourceFile]:
        """Non-vendor sources only -- the comparison/grading input set."""
        return [f for f in self.parse(uvprojx_path) if not f.is_vendor]

    def user_code_text(
        self,
        uvprojx_path: Path,
        include_generated: bool = False,
    ) -> str:
        """Concatenated user-written code, ready for similarity engines.

        Sources: USER CODE blocks of user files AND of scaffold files
        (stm32f4xx_it.c et al. -- students write ISR bodies there).
        include_generated=True additionally appends the full text of
        non-vendor files carrying no markers at all (hand-written files
        outside CubeMX).
        """
        parts: List[str] = []
        for f in self.parse(uvprojx_path):
            if f.user_sections and (not f.is_vendor or f.scaffold):
                parts.extend("// %s [%s]\n%s" % (f.name, marker, code)
                             for marker, code in f.user_sections)
            elif (not f.is_vendor and not f.user_sections
                  and include_generated and f.path.is_file()):
                parts.append("// %s\n%s" % (f.name,
                                             _read_text(f.path)))
        return "\n".join(parts)

    # ------------------------------------------------------------ internals

    @staticmethod
    def _parse_xml(uvprojx_path: Path):
        """defusedxml parse; multi-byte-declared files are pre-decoded."""
        data = uvprojx_path.read_bytes()
        if _MULTIBYTE_DECL_RE.match(data):
            text = data.decode("gbk", errors="replace")
            text = re.sub(r'encoding=["\'][^"\']+["\']',
                          'encoding="utf-8"', text, count=1)
            return SafeET.fromstring(text)
        return SafeET.parse(str(uvprojx_path)).getroot()

    def _is_vendor_dir(self, low_rel: str) -> bool:
        """Directory-component match; the BASENAME is never consulted."""
        dir_part = low_rel.rsplit("/", 1)[0] if "/" in low_rel else ""
        for component in dir_part.split("/"):
            if not component:
                continue
            for name in self._excludes:
                if component == name or component.endswith("_" + name):
                    return True
        return False

    def _classify(
        self, pending: dict, group: str,
        project_dir: Path, tree_root: Path,
    ) -> Optional[KeilSourceFile]:
        raw = pending.get("filepath", "")
        if not raw:
            return None                     # entry without FilePath: skip
        name = pending.get("filename") or Path(raw).name
        resolved = (project_dir / raw).resolve()
        low_rel = raw.replace("\\", "/").lower()
        low_name = name.lower()

        scaffold = any(low_name.startswith(p)
                       for p in VENDOR_SCAFFOLD_PREFIXES)
        vendor = (
            scaffold
            or self._is_vendor_dir(low_rel)
            or any(low_name.startswith(p) for p in VENDOR_FILE_PREFIXES)
        )
        if any(a in low_rel for a in self._allow):   # allowlist wins
            vendor = scaffold        # scaffold files stay vendor regardless
        # Untrusted path: anything resolving outside the project tree is
        # never read (absolute FilePath / ..-escape) and gets flagged.
        in_tree = tree_root == resolved or tree_root in resolved.parents
        if not in_tree:
            vendor = True
            self.last_flagged_paths.append(raw)
        # Extension is the robust filter (FileType numbering varies across
        # Keil versions): only C sources/headers are comparable text.
        if not low_name.endswith((".c", ".h")):
            vendor = True

        sections = (self._extract_user_blocks(resolved)
                    if (not vendor or scaffold) else [])
        return KeilSourceFile(name, resolved, group, vendor, scaffold,
                              sections)

    @staticmethod
    def _extract_user_blocks(path: Path) -> List[Tuple[str, str]]:
        """Collect (marker, body) pairs between USER CODE BEGIN/END markers.

        Handles BEGIN+END on one line (common in student-edited files),
        code preceding an END on its line (counts as block content), files
        that do not exist (no sections), and unclosed blocks (ignored).
        """
        if not path.is_file():
            return []
        blocks: List[Tuple[str, str]] = []
        marker: Optional[str] = None
        buf: List[str] = []
        for line in _read_text(path).splitlines():
            if marker is None:
                if USER_CODE_BEGIN in line:
                    tail = line.split(USER_CODE_BEGIN, 1)[1]
                    head, sep, rest = tail.partition("*/")
                    marker = head.strip()
                    if not sep:
                        continue
                    if USER_CODE_END in rest:       # BEGIN+END on one line
                        body = rest.split(USER_CODE_END, 1)[0].strip()
                        if body:
                            blocks.append((marker, body))
                        marker = None
                    elif rest.strip():
                        buf.append(rest.strip())
            else:
                if USER_CODE_END in line:
                    head = line.split(USER_CODE_END, 1)[0]
                    if head.strip():
                        buf.append(head)            # code before END counts
                    body = "\n".join(buf).strip()
                    if body:
                        blocks.append((marker, body))
                    marker, buf = None, []
                else:
                    buf.append(line)
        return blocks
