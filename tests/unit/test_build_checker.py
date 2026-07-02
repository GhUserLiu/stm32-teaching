# -*- coding: utf-8 -*-
"""
编译检查器单元测试
Build Checker Unit Tests

由根目录诊断脚本 test_build_checker.py 重构为正式 pytest 用例。
不依赖真实 make/arm-none-eabi-gcc 工具链，仅测配置默认值与错误输出解析。
"""

import pytest

from tools.auto_grading.config import AutoGradingConfig
from tools.auto_grading.build_checker import (
    BuildChecker,
    BuildResult,
    BuildStatus,
)


class TestAutoGradingConfig:
    def test_defaults(self):
        cfg = AutoGradingConfig()
        assert cfg.toolchain.make_path == "make"
        assert cfg.toolchain.arm_none_eabi_prefix == "arm-none-eabi-"
        assert cfg.semester == "2026-春季"
        assert "07-car-gear" in cfg.project.allowed_projects

    def test_output_dir_uses_path_config(self, tmp_path):
        cfg = AutoGradingConfig(project_root=tmp_path)
        out = cfg.get_output_dir("汽服2302B班", "07-car-gear")
        assert out.parts[-1] == "grading"
        assert out == (
            tmp_path / "data" / "teaching" / "2026-春季"
            / "汽服2302B班" / "07-car-gear" / "results" / "grading"
        )


class TestBuildCheckerPatterns:
    """直接测类级正则，避免触发工具链探测。"""

    def test_gcc_error_pattern(self):
        line = "src/main.c:42:7: error: expected ';' before '}' token"
        m = BuildChecker.GCC_ERROR_PATTERN.search(line)
        assert m is not None
        assert m.group(1) == "src/main.c"
        assert m.group(2) == "42"
        assert m.group(4) == "error"
        assert "expected" in m.group(5)

    def test_gcc_warning_pattern(self):
        line = "drivers/timer.c:10:3: warning: unused variable 'x' [-Wunused-variable]"
        m = BuildChecker.GCC_ERROR_PATTERN.search(line)
        assert m is not None
        assert m.group(4) == "warning"

    def test_gcc_pattern_ignores_plain_text(self):
        assert BuildChecker.GCC_ERROR_PATTERN.search("just some log line") is None

    def test_keil_error_pattern(self):
        # Keil 模式：file(line): Error <num>: message
        line = 'main.c(57): Error 20: identifier "HAL_GPIO" is undefined'
        m = BuildChecker.KEIL_ERROR_PATTERN.search(line)
        assert m is not None
        assert m.group(1) == "main.c"
        assert m.group(2) == "57"
        assert m.group(3) == "Error"


class TestBuildResult:
    def test_success_result(self, tmp_path):
        r = BuildResult(
            status=BuildStatus.SUCCESS,
            project_name="01-turn-signal",
            project_path=tmp_path,
            success=True,
        )
        assert r.success is True
        assert r.error_count == 0
        assert r.status == BuildStatus.SUCCESS


class TestGccBuildCommand:
    """验证 _check_gcc_build 下发的 make 命令形态。

    回归：旧实现 ``make -C <dir>``，-C 收到的 Windows 反斜杠路径会被 MSYS make 解析坏。
    现仅 ``['make', 'all']``（clean 由 ``shutil.rmtree(build)`` 自行完成，不再依赖学生
    Makefile 里可能缺 rm 的 clean 配方，也不再用 -C），cwd 设为 makefile.parent。
    """

    def test_make_cmd_has_no_dash_c(self, tmp_path, monkeypatch):
        # 准备一个含 Makefile 的工程根
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "Makefile").write_text("all:\n", encoding="utf-8")

        captured = {}

        class _FakeCompleted:
            returncode = 0
            stdout = ""
            stderr = ""

        def fake_run(cmd, *args, **kwargs):
            captured["cmd"] = list(cmd)
            captured["cwd"] = kwargs.get("cwd")
            return _FakeCompleted()

        # 真实工具链是否在 PATH 不影响本测试：强制视为可用，跳过 SKIPPED 分支
        import tools.auto_grading.build_checker as bc
        monkeypatch.setattr(bc.subprocess, "run", fake_run)

        checker = BuildChecker()
        monkeypatch.setattr(checker, "make_available", True)
        monkeypatch.setattr(checker, "gcc_available", True)

        result = checker.check_build(proj, "test-proj")

        # 命令不得含 -C，也不得带路径参数；clean 由 shutil.rmtree 完成，故仅 make all
        assert captured["cmd"] == ["make", "all"]
        assert "-C" not in captured["cmd"]
        # cwd 仍指向 Makefile 所在目录（make 据此定位 Makefile）
        assert captured["cwd"] == str(proj)
        # returncode=0 且无 error → 编译成功
        assert result.status == BuildStatus.SUCCESS
        assert result.success is True

    def test_gcc_output_with_non_gbk_bytes_does_not_crash(self, tmp_path, monkeypatch):
        """回归：中文 Windows 下 text=True 按 GBK 解码 make 输出，若诊断含中文路径
        （学生源码目录命名固定带中文）会抛 UnicodeDecodeError，使读管道线程崩、
        stdout/stderr 变 None，``stdout + stderr`` 随之抛 TypeError，把真实编译错误
        吞成 "无法编译: can only concatenate str (not NoneType) to str"。

        修复后按字节捕获 + errors="replace" 解码：含非法字节（0xAD/0xFF 等）也不再
        崩溃，ASCII 诊断（GCC 的 file:line:col: error:）仍能被正则解析。
        （案例：汽服2302B班 王倩倩小组 undefined reference to HAL_EXTI_ConfigLine）
        """
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "Makefile").write_text("all:\n", encoding="utf-8")

        # 模拟真实 make 输出：GCC 错误行 + ld 报错 + 中文路径混入的非法字节
        stderr_bytes = (
            "Core/Src/main.c:190:5: error: implicit declaration of function 'HAL_EXTI_ConfigLine'\n"
            "collect2.exe: error: ld returned 1 exit status\n"
        ).encode("utf-8") + b"\xff\xad\xed from-\xe6\xb1\xbd\xe6\x9c\x8d-path"

        # SimpleNamespace 在函数作用域内构造，可直接引用上面的 stderr_bytes
        # （类体的裸名无法看到外层函数局部，故不用 class 形式）
        from types import SimpleNamespace
        fake_completed = SimpleNamespace(
            returncode=2,
            stdout=b"rm -fR build\narm-none-eabi-gcc -c Core/Src/main.c\n",
            stderr=stderr_bytes,
        )

        def fake_run(cmd, *args, **kwargs):
            return fake_completed

        import tools.auto_grading.build_checker as bc
        monkeypatch.setattr(bc.subprocess, "run", fake_run)

        checker = BuildChecker()
        monkeypatch.setattr(checker, "make_available", True)
        monkeypatch.setattr(checker, "gcc_available", True)

        result = checker.check_build(proj, "test-proj")

        # 不再因编码崩溃；真实诊断被解析；output 恒为 str 且保留 ld 错误。
        # error_count=2：GCC 格式错误行 + 链接错误行（GCC_LINKER_ERROR_PATTERN 把
        # "collect2.exe: error: ld returned 1 exit status" 也计入 error）。
        assert result.status == BuildStatus.FAILED
        assert result.success is False
        assert result.error_count == 2
        assert isinstance(result.output, str)
        assert "ld returned 1 exit status" in result.output
