#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
编译检查器
Build Checker

提供批量编译检查功能：
- 支持STM32CubeMX项目（使用项目内Makefile）
- 支持Keil项目（使用UV4命令行，可选）
- 解析编译输出，提取错误和警告
- 生成编译检查报告
"""

import re
import sys
import time
import threading
import subprocess
import shutil
from pathlib import Path
from types import SimpleNamespace
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum

from .config import AutoGradingConfig


class BuildStatus(Enum):
    """编译状态"""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"  # 工具链错误
    NOT_FOUND = "not_found"  # 项目文件未找到
    SKIPPED = "skipped"  # 跳过（例如：不支持的类型）


@dataclass
class BuildIssue:
    """编译问题"""
    severity: str  # error, warning, note
    file: str     # 文件路径
    line: int     # 行号
    column: int   # 列号
    message: str  # 问题信息


@dataclass
class BuildResult:
    """编译结果"""
    status: BuildStatus
    project_name: str
    project_path: Path
    success: bool
    duration: float = 0.0  # 编译耗时（秒）
    error_count: int = 0
    warning_count: int = 0
    issues: List[BuildIssue] = field(default_factory=list)
    output: str = ""  # 完整输出
    error_message: str = ""  # 错误信息（如果失败）


class BuildChecker:
    """编译检查器"""

    # GCC编译输出模式
    GCC_ERROR_PATTERN = re.compile(
        r'([^:]+):(\d+):(\d+):\s+(error|warning|note):\s+(.+)'
    )

    # 链接器错误：undefined reference / cannot find -lxxx / multiple definition / ld returned。
    # 这些不符合 file:line:col: error: 格式，GCC_ERROR_PATTERN 匹配不到 → error_count=0，
    # 旧逻辑把链接失败当成"未识别错误"。补上后链接失败也能计入 error_count、并写进反馈。
    GCC_LINKER_ERROR_PATTERN = re.compile(
        r"(undefined reference to `[^']*'"
        r"|cannot find -l\S+"
        r"|multiple definition of `[^']*'"
        r"|relocation truncated to fit"
        r"|collect2\.\w*:\s*error:\s*ld returned \d+ exit status)"
    )

    # Makefile 语法错误：Makefile:NN: *** ... Stop.（配方行用了空格而非 Tab 等）
    MAKEFILE_ERROR_PATTERN = re.compile(
        r'(Makefile\S*:\s*\d+:.+?\*\*\*.+?Stop\.|Makefile\S*:\s*.+?\*\*\*.+?Stop\.)'
    )

    # Keil编译输出模式
    KEIL_ERROR_PATTERN = re.compile(
        r'(.+)\((\d+)\):\s+(Error|Warning)\s+(\d+):\s+(.+)'
    )

    def __init__(self, config: Optional[AutoGradingConfig] = None):
        """
        初始化编译检查器

        Args:
            config: 配置对象，如果为None则使用默认配置
        """
        self.config = config or AutoGradingConfig()

        # 检查工具链
        self._check_toolchain()

    def _check_toolchain(self):
        """检查工具链是否可用（静默）。

        仅把可用性记录为属性，不打印、不在构造期抛异常——GUI 与库的启动
        不应被"可选的工具链"阻断。真正编译时由 check_build 执行；工具链缺失
        会优雅返回 BuildResult(ERROR)，不会崩溃。UI 中每名学生的"编译"列
        会以 ✓/✗ 反映编译情况，用户可据此判断是否需要安装 make/MinGW。
        """
        self.make_available = bool(shutil.which(self.config.toolchain.make_path))
        self.gcc_available = bool(
            shutil.which(f"{self.config.toolchain.arm_none_eabi_prefix}gcc")
        )
        self.keil_available = False
        if self.config.toolchain.keil_enabled and self.config.toolchain.keil_uv4_path:
            self.keil_available = Path(self.config.toolchain.keil_uv4_path).exists()

        # 取消事件（可选，由 GUI 批阅 worker 注入）。默认 None：check_build 走
        # subprocess.run 原路径，CLI/自检/单测行为完全不变；设置后改用可取消的
        # Popen 轮询，命中取消即 kill make/gcc 子进程（批阅取消时不必等编译跑完）。
        self._cancel_event: Optional[threading.Event] = None

    def set_cancel_event(self, event: Optional[threading.Event]) -> None:
        """注入取消事件（详见 self._cancel_event 注释）。"""
        self._cancel_event = event

    def check_build(
        self,
        project_path: Path,
        project_name: Optional[str] = None,
        toolchain: str = 'auto'
    ) -> BuildResult:
        """
        检查单个项目的编译状态

        Args:
            project_path: 项目路径
            project_name: 项目名称（可选）
            toolchain: 工具链类型（auto, gcc, keil）

        Returns:
            编译结果
        """
        if not project_path.exists():
            return BuildResult(
                status=BuildStatus.NOT_FOUND,
                project_name=project_name or project_path.name,
                project_path=project_path,
                success=False,
                error_message="项目路径不存在"
            )

        start_time = time.time()

        # 自动检测项目类型
        if toolchain == 'auto':
            toolchain = self._detect_project_type(project_path)

        # 工具链不可用时优雅跳过（给出清晰原因，而非抛 FileNotFoundError）。
        # make_available / gcc_available 等属性在 _check_toolchain 中静默记录。
        # 任一缺失即视为工具链不完整：make 在但 arm-none-eabi-gcc 不在时，make 必然失败，
        # 应判 SKIPPED（不计入总分）而非误导性的 FAILED。
        if toolchain == 'gcc' and not (
            getattr(self, 'make_available', True) and getattr(self, 'gcc_available', True)
        ):
            return BuildResult(
                status=BuildStatus.SKIPPED,
                project_name=project_name or project_path.name,
                project_path=project_path,
                success=False,
                error_message="未安装 make / arm-none-eabi-gcc，编译检查已跳过"
            )

        try:
            if toolchain == 'gcc':
                result = self._check_gcc_build(project_path, project_name)
            elif toolchain == 'keil':
                result = self._check_keil_build(project_path, project_name)
            else:
                result = BuildResult(
                    status=BuildStatus.SKIPPED,
                    project_name=project_name or project_path.name,
                    project_path=project_path,
                    success=False,
                    error_message=f"不支持的工具链: {toolchain}"
                )
        except subprocess.TimeoutExpired:
            result = BuildResult(
                status=BuildStatus.TIMEOUT,
                project_name=project_name or project_path.name,
                project_path=project_path,
                success=False,
                error_message="编译超时"
            )
        except Exception as e:
            result = BuildResult(
                status=BuildStatus.ERROR,
                project_name=project_name or project_path.name,
                project_path=project_path,
                success=False,
                error_message=str(e)
            )

        result.duration = time.time() - start_time
        return result

    def batch_check(
        self,
        projects: List[Tuple[Path, str]],
        toolchain: str = 'auto'
    ) -> Dict[str, BuildResult]:
        """
        批量检查多个项目

        Args:
            projects: (项目路径, 项目名称)列表
            toolchain: 工具链类型

        Returns:
            项目名称 -> 编译结果的字典
        """
        results = {}

        for project_path, project_name in projects:
            result = self.check_build(project_path, project_name, toolchain)
            results[project_name] = result

            # 打印进度
            status_icon = "✓" if result.success else "✗"
            print(f"  {status_icon} {project_name}: {result.status.value}")

        return results

    def _detect_project_type(self, project_path: Path) -> str:
        """
        检测项目类型

        Returns:
            'gcc' 或 'keil'
        """
        # 检查是否有Makefile（CubeMX项目）
        if (project_path / "Makefile").exists():
            return 'gcc'

        # 检查是否有MDK-ARM目录（CubeMX生成的Keil项目）
        if (project_path / "MDK-ARM").exists():
            # 检查是否有.uvprojx文件
            uvprojx_files = list((project_path / "MDK-ARM").glob("*.uvprojx"))
            if uvprojx_files:
                return 'gcc'  # CubeMX的Keil项目也可以用GCC

        # 检查是否有.uvprojx文件（纯Keil项目）
        uvprojx_files = list(project_path.glob("*.uvprojx"))
        if uvprojx_files:
            if self.config.toolchain.keil_enabled:
                return 'keil'
            else:
                return 'gcc'  # 尝试用GCC

        # 默认使用GCC
        return 'gcc'

    def _execute_build(self, cmd: List[str], cwd: Optional[str]):
        """运行编译命令，返回 ``(completed, cancelled)``。

        - 无 ``_cancel_event``：用 ``subprocess.run``，与历史行为/单测 mock 完全一致。
        - 有 ``_cancel_event``：用 ``Popen`` + ``communicate(timeout)`` 轮询，每 ~0.2s
          检查一次取消事件：命中则 kill 子进程并返回 cancelled=True；到 build_timeout
          仍 kill 并抛 TimeoutExpired（与原超时语义一致）。stderr 合并入 stdout（单管道，
          轮询期间持续排空，避免管道缓冲写满导致子进程阻塞）。

        ``completed`` 为类 CompletedProcess 对象（有 returncode/stdout/stderr），
        交由 ``_decode_subprocess_output`` 统一解码。
        """
        timeout = self.config.toolchain.build_timeout
        if self._cancel_event is None:
            return subprocess.run(
                cmd, capture_output=True, timeout=timeout, cwd=cwd
            ), False

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd,
            **(dict(creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
               if sys.platform == "win32" else {}),
        )
        deadline = time.monotonic() + timeout
        try:
            while True:
                poll_t = max(0.05, min(0.2, deadline - time.monotonic()))
                try:
                    out, _ = proc.communicate(timeout=poll_t)
                    return (
                        SimpleNamespace(returncode=proc.returncode, stdout=out, stderr=None),
                        False,
                    )
                except subprocess.TimeoutExpired:
                    # communicate 超时后可安全重试（官方文档保证不丢输出）
                    if self._cancel_event.is_set():
                        self._kill(proc)
                        return (
                            SimpleNamespace(returncode=-1, stdout=b"", stderr=None),
                            True,
                        )
                    if time.monotonic() >= deadline:
                        self._kill(proc)
                        raise
        except BaseException:
            # 任何异常/取消都确保进程被回收，避免孤儿 make/gcc
            self._kill(proc)
            raise

    @staticmethod
    def _kill(proc):
        """终止并排空子进程管道，并尽力终结整棵进程树（幂等，失败静默）。

        Popen.kill()/TerminateProcess 只终结「直接子进程」(make)；而 make all 会派生
        arm-none-eabi-gcc / collect2 / ld 孙进程，且它们继承 make 的 stdout 管道。若只杀
        make：①孙进程成孤儿继续跑、持有 build/ 下 .o/.elf/.map 文件句柄，导致下一名学生
        ``shutil.rmtree(build_dir, ignore_errors=True)`` 静默漏删、make 增量编译复用过期
        .o → 污染计分；②孙进程仍持有管道，communicate 会一直阻塞到超时。

        故 Windows 下必须**先** ``taskkill /T /F /PID``（在父进程仍存活时按 PID 亲子链
        递归终结全部后代，并关闭其继承的管道），再 proc.kill() 兜底、communicate 排空。
        顺序不能反：父进程先死则其子被孤儿化、taskkill /T /PID 找不到树。
        """
        pid = proc.pid
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(pid)],
                    capture_output=True, timeout=5,
                )
            except Exception:
                pass
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.communicate(timeout=5)
        except Exception:
            pass

    def _check_gcc_build(
        self,
        project_path: Path,
        project_name: Optional[str] = None
    ) -> BuildResult:
        """
        使用GCC工具链检查编译

        Args:
            project_path: 项目路径
            project_name: 项目名称

        Returns:
            编译结果
        """
        name = project_name or project_path.name

        # 检查是否有Makefile
        makefile = project_path / "Makefile"
        if not makefile.exists():
            # 尝试查找CubeMX的MDK-ARM目录
            mdk_dir = project_path / "MDK-ARM"
            if mdk_dir.exists():
                makefile = mdk_dir / "Makefile"
            else:
                return BuildResult(
                    status=BuildStatus.NOT_FOUND,
                    project_name=name,
                    project_path=project_path,
                    success=False,
                    error_message="未找到Makefile"
                )

        # 清理 build/ 后只跑 `make all`（不再 `make clean all`）。
        # 学生 CubeMX Makefile 的 clean 配方用 Unix `rm -rf/-fR build`；批阅启动环境
        # （.bat 启动，非 git-bash）PATH 里常没有 rm.exe，于是 `make clean all` 死在 clean
        # 步骤、根本编不到学生代码，把真实编译错误掩盖成「未识别错误」。CubeMX 的 clean
        # 等价于删除 build/ 目录，故改用 shutil 自行清理：不依赖外部 rm，clean 失败也不再
        # 阻断真正要评分的 make all。不传 -C：cwd 已设为 makefile.parent，-C 本就冗余；
        # 且 Windows + MSYS make 下 -C 收到的反斜杠路径会被解析坏。
        build_dir = makefile.parent / "build"
        if build_dir.exists():
            shutil.rmtree(build_dir, ignore_errors=True)

        cmd = [
            self.config.toolchain.make_path,
            'all'
        ]

        try:
            result, cancelled = self._execute_build(cmd, str(makefile.parent))
        except subprocess.TimeoutExpired:
            raise

        if cancelled:
            return BuildResult(
                status=BuildStatus.SKIPPED,
                project_name=name,
                project_path=project_path,
                success=False,
                error_message="编译已取消"
            )

        # 解析输出（按字节捕获 + 容错解码，详见 _decode_subprocess_output）
        output = self._decode_subprocess_output(result)
        issues = self._parse_gcc_output(output)

        # 统计错误和警告
        error_count = sum(1 for i in issues if i.severity == 'error')
        warning_count = sum(1 for i in issues if i.severity == 'warning')

        # 判断是否成功
        success = result.returncode == 0 and error_count == 0

        return BuildResult(
            status=BuildStatus.SUCCESS if success else BuildStatus.FAILED,
            project_name=name,
            project_path=project_path,
            success=success,
            error_count=error_count,
            warning_count=warning_count,
            issues=issues,
            output=output
        )

    def _check_keil_build(
        self,
        project_path: Path,
        project_name: Optional[str] = None
    ) -> BuildResult:
        """
        使用Keil UV4检查编译

        Args:
            project_path: 项目路径
            project_name: 项目名称

        Returns:
            编译结果
        """
        name = project_name or project_path.name

        if not self.config.toolchain.keil_enabled:
            return BuildResult(
                status=BuildStatus.ERROR,
                project_name=name,
                project_path=project_path,
                success=False,
                error_message="Keil工具链未启用"
            )

        # 查找.uvprojx文件
        uvprojx_files = list(project_path.glob("*.uvprojx"))
        if not uvprojx_files:
            mdk_dir = project_path / "MDK-ARM"
            if mdk_dir.exists():
                uvprojx_files = list(mdk_dir.glob("*.uvprojx"))

        if not uvprojx_files:
            return BuildResult(
                status=BuildStatus.NOT_FOUND,
                project_name=name,
                project_path=project_path,
                success=False,
                error_message="未找到.uvprojx文件"
            )

        uvprojx_file = uvprojx_files[0]

        # 调用Keil UV4命令
        cmd = [
            self.config.toolchain.keil_uv4_path,
            '-r',  # 重建
            '-j0',  # 并行编译
            '-b',  # 批处理模式
            str(uvprojx_file)
        ]

        try:
            result, cancelled = self._execute_build(cmd, None)
        except subprocess.TimeoutExpired:
            raise

        if cancelled:
            return BuildResult(
                status=BuildStatus.SKIPPED,
                project_name=name,
                project_path=project_path,
                success=False,
                error_message="编译已取消"
            )

        # 解析输出（按字节捕获 + 容错解码，详见 _decode_subprocess_output）
        output = self._decode_subprocess_output(result)
        issues = self._parse_keil_output(output)

        # 统计错误和警告
        error_count = sum(1 for i in issues if i.severity == 'error')
        warning_count = sum(1 for i in issues if i.severity == 'warning')

        # 判断是否成功（Keil返回0表示成功）
        success = result.returncode == 0 and error_count == 0

        return BuildResult(
            status=BuildStatus.SUCCESS if success else BuildStatus.FAILED,
            project_name=name,
            project_path=project_path,
            success=success,
            error_count=error_count,
            warning_count=warning_count,
            issues=issues,
            output=output
        )

    @staticmethod
    def _decode_subprocess_output(result) -> str:
        """合并并解码子进程 stdout/stderr，恒返回 str。

        不用 subprocess 的 text 模式：中文 Windows 下 text 模式按 GBK(CP936) 解码，
        而 make / arm-none-eabi-gcc / ld 的诊断里若含中文路径（学生源码目录命名
        固定带中文），经 MSYS-make → 原生 ld.exe 传递后会混入 GBK 无法解码的字节，
        导致读管道线程抛 UnicodeDecodeError、stdout/stderr 变 None，`stdout + stderr`
        随之抛 TypeError，把真实的链接错误吞成 "无法编译: can only concatenate..."。
        改为按字节捕获、errors="replace" 容错解码：永不因编码崩溃，ASCII 诊断
        （GCC 的 file:line:col: error:）完整保留供正则解析，中文路径即便变成替换
        字符也不影响错误计数与成败判定。
        """
        parts = []
        for stream in (result.stdout, result.stderr):
            if not stream:
                continue
            if isinstance(stream, bytes):
                parts.append(stream.decode("utf-8", errors="replace"))
            else:
                parts.append(stream)
        return "".join(parts)

    def _parse_gcc_output(self, output: str) -> List[BuildIssue]:
        """解析 GCC/make 输出：编译错误（file:line:col: error:）+ 链接错误 + Makefile 语法错误。

        编译错误走 GCC_ERROR_PATTERN；链接错误（undefined reference 等）与 Makefile 语法
        错误（*** ... Stop.）单列，统一记 severity='error'，使 error_count 反映真实失败、
        且反馈能展示具体缺失符号/语法问题，而非笼统的「未识别错误」。
        """
        issues = []

        for line in output.split('\n'):
            match = self.GCC_ERROR_PATTERN.search(line)
            if match:
                file, line_no, col, severity, message = match.groups()
                issues.append(BuildIssue(
                    severity=severity,
                    file=file,
                    line=int(line_no),
                    column=int(col),
                    message=message.strip()
                ))
                continue
            # 链接错误（不符合 file:line:col: error: 格式，上面的正则抓不到）
            ml = self.GCC_LINKER_ERROR_PATTERN.search(line)
            if ml:
                issues.append(BuildIssue(
                    severity='error', file='ld', line=0, column=0,
                    message=ml.group(1).strip()
                ))
                continue
            # Makefile 语法错误
            mm = self.MAKEFILE_ERROR_PATTERN.search(line)
            if mm:
                issues.append(BuildIssue(
                    severity='error', file='Makefile', line=0, column=0,
                    message=mm.group(1).strip()
                ))

        return issues

    def _parse_keil_output(self, output: str) -> List[BuildIssue]:
        """解析Keil编译输出"""
        issues = []

        for line in output.split('\n'):
            match = self.KEIL_ERROR_PATTERN.search(line)
            if match:
                file, line_no, severity, code, message = match.groups()
                issues.append(BuildIssue(
                    severity=severity.lower(),
                    file=file,
                    line=int(line_no),
                    column=0,
                    message=f"{code}: {message}".strip()
                ))

        return issues

    def generate_report(self, results: Dict[str, BuildResult]) -> str:
        """
        生成编译检查报告

        Args:
            results: 编译结果字典

        Returns:
            报告文本
        """
        lines = [
            "=" * 70,
            "编译检查报告",
            "=" * 70,
            "",
            f"总项目数: {len(results)}",
            f"编译成功: {sum(1 for r in results.values() if r.success)}",
            f"编译失败: {sum(1 for r in results.values() if not r.success and r.status == BuildStatus.FAILED)}",
            f"跳过/错误: {sum(1 for r in results.values() if r.status in [BuildStatus.ERROR, BuildStatus.NOT_FOUND, BuildStatus.SKIPPED])}",
            "",
        ]

        # 详细结果
        lines.extend([
            "详细结果:",
            "-" * 70,
        ])

        for name, result in results.items():
            status_icon = "✓" if result.success else "✗"
            lines.append(f"{status_icon} {name}: {result.status.value}")

            if result.error_count > 0:
                lines.append(f"    错误: {result.error_count}")
            if result.warning_count > 0:
                lines.append(f"    警告: {result.warning_count}")
            if result.error_message:
                lines.append(f"    错误信息: {result.error_message}")

            # 显示前3个错误
            errors = [i for i in result.issues if i.severity == 'error'][:3]
            for error in errors:
                lines.append(f"      {error.file}:{error.line}: {error.message}")

        lines.append("=" * 70)

        return "\n".join(lines)


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description='编译检查器')
    parser.add_argument('project', type=Path, help='项目路径')
    parser.add_argument('--name', type=str, help='项目名称')
    parser.add_argument('--toolchain', choices=['auto', 'gcc', 'keil'], default='auto', help='工具链类型')

    args = parser.parse_args()

    checker = BuildChecker()

    result = checker.check_build(args.project, args.name, args.toolchain)

    print(f"项目: {result.project_name}")
    print(f"状态: {result.status.value}")
    print(f"成功: {'是' if result.success else '否'}")

    if result.error_count > 0:
        print(f"错误数: {result.error_count}")
    if result.warning_count > 0:
        print(f"警告数: {result.warning_count}")

    if result.issues:
        print("\n问题详情:")
        for issue in result.issues[:10]:  # 只显示前10个
            print(f"  [{issue.severity}] {issue.file}:{issue.line}: {issue.message}")


if __name__ == '__main__':
    main()
