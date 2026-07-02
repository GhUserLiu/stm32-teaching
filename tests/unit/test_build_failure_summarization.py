# -*- coding: utf-8 -*-
"""回归 / characterization 测试：锁定 _summarize_build_failure 及其助手当前的实际行为。

被测模块: src/tools/auto_grading/grading_engine.py

锁定脆点（对应 focus 要求）：
  ① 三流分类——链接失败 / Makefile 错误 / 其余编译错误，各喂典型输出断言分流正确；
  ② 防误判——`make: *** [target] Error N` 不应被当成 Makefile stop 错误；
  ③ undefined reference 文本经 _resolve_symbol_definers + _makefile_c_sources 定位到 .c；
  ④ 空 / 无识别错误的兜底分支。

断言用的字符串/数值均为实际跑出来的当前输出，目的是给后续重构装安全网——
任何静默漂移都会让本文件红。这是 characterization 测试：锁当前行为，不论是否理想。
"""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.auto_grading.build_checker import BuildIssue, BuildResult, BuildStatus
from tools.auto_grading.grading_engine import (
    _diagnose_missing_sources,
    _makefile_c_sources,
    _resolve_symbol_definers,
    _summarize_build_failure,
)


# ---------------------------------------------------------------------------
# 夹具构造助手
# ---------------------------------------------------------------------------

def make_build_result(
    *,
    issues=None,
    output="",
    error_message="",
    error_count=None,
) -> BuildResult:
    """构造一个最小可用的 BuildResult（status=FAILED，project_name 占位）。"""
    issues = issues or []
    if error_count is None:
        error_count = sum(1 for i in issues if i.severity == "error")
    return BuildResult(
        status=BuildStatus.FAILED,
        project_name="proj",
        project_path=Path("/tmp/proj"),
        success=False,
        duration=0.0,
        error_count=error_count,
        warning_count=0,
        issues=issues,
        output=output,
        error_message=error_message,
    )


def make_submission(source_path, source_files):
    """构造一个只含 _summarize_build_failure 路径用得到的字段的 submission。

    用 SimpleNamespace 而非真 dataclass，因为源码里走的是 getattr，鸭子类型即可。
    """
    pi = SimpleNamespace(source_files=list(source_files))
    return SimpleNamespace(source_path=Path(source_path), project_info=pi)


# ===========================================================================
# 脆点 ① 三流分类
# ===========================================================================

class TestThreeWayClassification:
    """锁定 _summarize_build_failure 的反馈句 + 改进建议按错误类别分三流。"""

    def test_linker_error_undefined_reference_branch(self):
        """链接失败流：issue message 含 undefined reference → fix 走链接失败建议。"""
        br = make_build_result(
            issues=[
                BuildIssue(severity="error", file="ld", line=0, column=0,
                           message="undefined reference to `key_init`"),
            ],
            error_count=1,
        )
        feedback, fix = _summarize_build_failure(br)

        # 反馈句含具体描述（ld 不带行号 → 只取描述）
        assert feedback == "编译失败：undefined reference to `key_init`"
        # 改进建议命中链接失败流
        assert fix.startswith("链接失败：")
        assert "C_SOURCES" in fix

    def test_linker_error_ld_returned_branch(self):
        """链接失败流：ld returned 1 exit status（仅出现在 output，不在 issues）。"""
        br = make_build_result(
            issues=[
                BuildIssue(severity="error", file="main.c", line=42, column=3,
                           message="dummy"),
            ],
            output="collect2.ld: error: ld returned 1 exit status",
            error_count=1,
        )
        feedback, fix = _summarize_build_failure(br)

        assert feedback == "编译失败：main.c:42: dummy"
        # output 里含 'ld returned' → 命中链接失败流
        assert fix.startswith("链接失败：")

    def test_linker_error_cannot_find_library_branch(self):
        """链接失败流：cannot find -l<lib>。"""
        br = make_build_result(
            issues=[
                BuildIssue(severity="error", file="ld", line=0, column=0,
                           message="cannot find -lmylib"),
            ],
            error_count=1,
        )
        feedback, fix = _summarize_build_failure(br)

        assert feedback == "编译失败：cannot find -lmylib"
        assert fix.startswith("链接失败：")

    def test_linker_error_multiple_definition_branch(self):
        """链接失败流：multiple definition of。"""
        br = make_build_result(
            issues=[
                BuildIssue(severity="error", file="ld", line=0, column=0,
                           message="multiple definition of `foo`"),
            ],
            error_count=1,
        )
        feedback, fix = _summarize_build_failure(br)

        assert feedback == "编译失败：multiple definition of `foo`"
        assert fix.startswith("链接失败：")

    def test_makefile_syntax_error_branch(self):
        """Makefile 错误流：blob 命中 `*** ... stop.` 正则。"""
        br = make_build_result(
            issues=[
                BuildIssue(severity="error", file="Makefile", line=0, column=0,
                           message="Makefile:12: *** missing separator.  Stop."),
            ],
            output="Makefile:12: *** missing separator.  Stop.",
            error_count=1,
        )
        feedback, fix = _summarize_build_failure(br)

        # Makefile 不带行号 → 只取描述
        assert feedback == "编译失败：Makefile:12: *** missing separator.  Stop."
        assert fix.startswith("Makefile 格式错误")
        assert "Tab" in fix

    def test_plain_compile_error_branch(self):
        """其余编译错误流：普通 file:line:col: error，走第三条 fix。"""
        br = make_build_result(
            issues=[
                BuildIssue(severity="error", file="main.c", line=10, column=2,
                           message="'GPIOA' undeclared"),
            ],
            error_count=1,
        )
        feedback, fix = _summarize_build_failure(br)

        assert feedback == "编译失败：main.c:10: 'GPIOA' undeclared"
        assert fix.startswith("请按上面的错误信息修正源码")
        assert "头文件" in fix


# ===========================================================================
# 脆点 ② 防误判：make: *** [target] Error N 不应被当成 Makefile stop 错误
# ===========================================================================

class TestMakeErrorNotFalsePositive:
    """锁定注释里明确警告的防误判行为。

    普通编译/链接失败结尾都有 `make: *** [target] Error N`，
    绝不能被 re.search(r'\\*\\*\\*.+?stop\\.', blob) 误判为 Makefile 语法错误。
    """

    def test_make_error_N_with_undefined_reference_goes_linker(self):
        """undefined reference 末尾跟 `make: *** [build/foo.o] Error 1` → 仍走链接失败流。"""
        br = make_build_result(
            issues=[
                BuildIssue(severity="error", file="ld", line=0, column=0,
                           message="undefined reference to `key_init`"),
            ],
            output="make: *** [build/foo.o] Error 1",
            error_count=1,
        )
        feedback, fix = _summarize_build_failure(br)

        # 关键防误判：必须命中链接失败流，不能落到 Makefile 格式错误流
        assert fix.startswith("链接失败："), (
            f"被误判为 Makefile 错误！fix={fix!r}"
        )
        # blob 里确实含 `*** ` 但不含 `Stop.`，正则 \*\*\*.+?stop\. 不应命中
        assert not re.search(r"\*\*\*.+?stop\.", "make: *** [build/foo.o] Error 1".lower())

    def test_make_error_N_with_plain_compile_error_goes_compile(self):
        """普通编译错误末尾跟 `make: *** ... Error 2` → 走编译错误流，不进 Makefile 流。"""
        br = make_build_result(
            issues=[
                BuildIssue(severity="error", file="main.c", line=5, column=1,
                           message="expected ';' before '}' token"),
            ],
            output="make: *** [build/main.o] Error 2",
            error_count=1,
        )
        feedback, fix = _summarize_build_failure(br)

        # 不能进 Makefile 格式错误流
        assert not fix.startswith("Makefile 格式错误"), f"被误判！fix={fix!r}"
        # 应走普通编译错误流（errs 非空）
        assert fix.startswith("请按上面的错误信息修正源码")

    def test_make_error_N_alone_is_not_makefile_syntax_error(self):
        """output 只含裸 `make: *** [target] Error N`、issues 为空 → 不进 Makefile 流。

        锁定两层：
        1. 源码正则 `*** ... stop.` 对该文本不命中（纯文本镜像，独立验证正则本身）；
        2. 实跑 _summarize_build_failure：blob 虽含 `*** ` 但 fix 绝不能以
           "Makefile 格式错误" 起头（否则即回归——本测试直接断言被测函数输出，
           与上层 re.search 断言双重锁定，任一被破坏都会红）。
        """
        blob = "make: *** [build/stm32f4xx_it.o] Error 2".lower()
        # 这是源码正则的纯文本镜像断言，独立验证防误判逻辑
        assert re.search(r"\*\*\*.+?stop\.", blob) is None

        # 关键：再实跑被测函数断言真实输出——只镜像正则而不喂给函数是脆弱的
        # （正则若被改成 r'\*\*\*.+?error'，纯文本断言仍绿但生产已回归）。
        br = make_build_result(
            issues=[],
            output="make: *** [build/stm32f4xx_it.o] Error 2",
            error_count=0,
        )
        feedback, fix = _summarize_build_failure(br)
        # 无 error issue + 无链接/Makefile 关键字 → 走最终兜底，绝不进 Makefile 格式错误流
        assert not fix.startswith("Makefile 格式错误"), f"裸 Error N 被误判！fix={fix!r}"
        assert fix.startswith("请在本机用 arm-none-eabi-gcc + make 复现编译")


# ===========================================================================
# 脆点 ③ undefined reference → 定位到具体 .c 源文件
# ===========================================================================

class TestSymbolResolution:
    """锁定 _resolve_symbol_definers / _makefile_c_sources / _diagnose_missing_sources。"""

    def test_makefile_c_sources_parses_block(self, tmp_path):
        """_makefile_c_sources 解析 C_SOURCES 续行块，返回归一化相对路径集合。"""
        (tmp_path / "Makefile").write_text(
            "C_SOURCES = \\\n"
            "Core/Src/main.c \\\n"
            "Core/Src/stm32f4xx_it.c \\\n"
            "./Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal.c\n"
            "\n"
            "CFLAGS = -O2\n",
            encoding="utf-8",
        )
        result = _makefile_c_sources(tmp_path)

        # 归一化：去前导 ./ /，正则 \.?/?([^\s]+\.c) 抓的是去掉首个 ./或/ 后的部分
        # 构造：Core/Src/main.c、Core/Src/stm32f4xx_it.c、Drivers/.../stm32f4xx_hal.c
        assert "Core/Src/main.c" in result
        assert "Core/Src/stm32f4xx_it.c" in result
        assert "Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal.c" in result

    def test_makefile_c_sources_missing_makefile_returns_empty(self, tmp_path):
        """无 Makefile → 空集合。"""
        assert _makefile_c_sources(tmp_path) == set()

    def test_resolve_symbol_definers_finds_definition_file(self, tmp_path):
        """_resolve_symbol_definers：匹配函数定义头（行尾非分号），返回相对路径。"""
        # 学生自有源码 key.c：定义了 key_init
        key_c = tmp_path / "Core" / "Src" / "key.c"
        key_c.parent.mkdir(parents=True)
        key_c.write_text(
            "#include \"key.h\"\n"
            "void key_init(void)\n"          # 函数定义头（行尾无分号）
            "{\n"
            "    // init\n"
            "}\n"
            "void key_init(void);            // 前向声明（行尾分号，应被跳过）\n",
            encoding="utf-8",
        )
        source_files = [key_c]

        definers = _resolve_symbol_definers(["key_init"], source_files, tmp_path)

        assert "key_init" in definers
        # 相对路径用 / 分隔
        assert definers["key_init"] == ["Core/Src/key.c"]

    def test_resolve_symbol_definers_skips_call_and_declaration(self, tmp_path):
        """调用语句 / 行尾分号声明 不应被当成定义。无定义 → 返回空 dict。"""
        main_c = tmp_path / "main.c"
        main_c.write_text(
            "key_init();\n"                  # 调用（行尾分号）
            "void key_init(void);\n"         # 声明（行尾分号）
            "    foo(key_init);\n",          # 另一种调用形式（行尾分号）
            encoding="utf-8",
        )
        definers = _resolve_symbol_definers(["key_init"], [main_c], tmp_path)
        # 这些行全部以分号结尾 → 没有匹配到定义头 → 不应出现该符号
        assert definers == {}

    def test_resolve_symbol_definers_excludes_vendor(self, tmp_path):
        """厂商库目录下的 .c 被排除。"""
        vendor_c = tmp_path / "Drivers" / "STM32F4xx_HAL_Driver" / "Src" / "stm32f4xx_hal.c"
        vendor_c.parent.mkdir(parents=True)
        vendor_c.write_text("void foo(void)\n{\n}\n", encoding="utf-8")
        definers = _resolve_symbol_definers(["foo"], [vendor_c], tmp_path)
        assert definers == {}

    def test_diagnose_missing_sources_reports_missing_files(self, tmp_path):
        """端到端：符号在源码有定义、但未列入 C_SOURCES → 反馈指出文件未参与编译。"""
        # 学生源码定义了 key_init，但 Makefile 没列它
        key_c = tmp_path / "Core" / "Src" / "key.c"
        key_c.parent.mkdir(parents=True)
        key_c.write_text(
            "void key_init(void)\n{\n}\n",
            encoding="utf-8",
        )
        (tmp_path / "Makefile").write_text(
            "C_SOURCES = Core/Src/main.c\n",
            encoding="utf-8",
        )
        sub = make_submission(tmp_path, [key_c])

        msg = _diagnose_missing_sources(["key_init"], sub)

        # 命中 missing 分支：应含「未参与编译」和文件相对路径 + 符号
        assert "未参与编译" in msg
        assert "Core/Src/key.c" in msg
        assert "key_init" in msg

    def test_diagnose_missing_sources_all_listed_reports_definition_only(self, tmp_path):
        """符号有定义且已在 C_SOURCES → 不报 missing，但提示「源码里有定义」需核对签名。"""
        key_c = tmp_path / "Core" / "Src" / "key.c"
        key_c.parent.mkdir(parents=True)
        key_c.write_text("void key_init(void)\n{\n}\n", encoding="utf-8")
        (tmp_path / "Makefile").write_text(
            "C_SOURCES = Core/Src/key.c\n", encoding="utf-8")
        sub = make_submission(tmp_path, [key_c])

        msg = _diagnose_missing_sources(["key_init"], sub)

        # 文件已在 C_SOURCES → missing 为空 → 走 fallback 提示
        assert "源码里有定义" in msg
        assert "Core/Src/key.c" in msg

    def test_diagnose_missing_sources_no_definition_returns_empty(self, tmp_path):
        """符号在源码无定义 → 返回空串（绝不抛异常）。"""
        (tmp_path / "Makefile").write_text("C_SOURCES = main.c\n", encoding="utf-8")
        sub = make_submission(tmp_path, [])
        assert _diagnose_missing_sources(["does_not_exist"], sub) == ""

    def test_summarize_appends_diagnosis_to_linker_fix(self, tmp_path):
        """_summarize_build_failure 在链接失败流里把诊断拼进 fix（submission 传入时）。"""
        key_c = tmp_path / "Core" / "Src" / "key.c"
        key_c.parent.mkdir(parents=True)
        key_c.write_text("void key_init(void)\n{\n}\n", encoding="utf-8")
        (tmp_path / "Makefile").write_text(
            "C_SOURCES = Core/Src/main.c\n", encoding="utf-8")
        sub = make_submission(tmp_path, [key_c])

        br = make_build_result(
            issues=[
                BuildIssue(severity="error", file="ld", line=0, column=0,
                           message="undefined reference to `key_init`"),
            ],
            error_count=1,
        )
        feedback, fix = _summarize_build_failure(br, sub)

        assert feedback == "编译失败：undefined reference to `key_init`"
        assert fix.startswith("链接失败：")
        # 诊断被拼进 fix
        assert "Core/Src/key.c" in fix
        assert "key_init" in fix

    def test_summarize_without_submission_skips_diagnosis(self):
        """submission=None → 链接失败 fix 不带诊断（仍是基础建议句）。"""
        br = make_build_result(
            issues=[
                BuildIssue(severity="error", file="ld", line=0, column=0,
                           message="undefined reference to `key_init`"),
            ],
            error_count=1,
        )
        feedback, fix = _summarize_build_failure(br, None)

        assert fix.startswith("链接失败：")
        # 无 submission → 不会有诊断拼接
        assert "未参与编译" not in fix


# ===========================================================================
# 脆点 ④ 空 / 无识别错误的兜底分支
# ===========================================================================

class TestFallbackBranches:
    """锁定 issues 为空 / 无识别诊断时的兜底文案。"""

    def test_no_issues_no_output_uses_unrecognized_fallback(self):
        """无 issues、无 output、无 error_message → 「未识别错误」兜底句。

        锁定：blob 全空时三流都不命中，fix 走最终兜底。
        """
        br = make_build_result(issues=[], output="", error_message="", error_count=0)
        feedback, fix = _summarize_build_failure(br)

        assert feedback == (
            "编译失败：未识别错误（未见 GCC/链接器诊断，可能为环境问题，请联系教师核对）"
        )
        assert fix.startswith("请在本机用 arm-none-eabi-gcc + make 复现编译")

    def test_no_issues_but_error_message_uses_error_message(self):
        """无 issues 但有 error_message → 反馈用 error_message（如「未安装 make」）。"""
        br = make_build_result(
            issues=[], output="", error_message="未安装 make / arm-none-eabi-gcc",
            error_count=0)
        feedback, fix = _summarize_build_failure(br)

        assert feedback == "编译失败：未安装 make / arm-none-eabi-gcc"
        # blob 不含任何流的关键字 → 走最终兜底 fix
        assert fix.startswith("请在本机用 arm-none-eabi-gcc + make 复现编译")

    def test_warning_only_issues_not_in_feedback(self):
        """severity='warning' 的 issue 不进 feedback（feedback 只收 error）。"""
        br = make_build_result(
            issues=[
                BuildIssue(severity="warning", file="x.c", line=1, column=1,
                           message="unused variable"),
            ],
            error_count=0,
        )
        feedback, fix = _summarize_build_failure(br)

        # 无 error issue → joined 为空 → 走兜底
        assert "未识别错误" in feedback
        assert "unused variable" not in feedback

    def test_more_count_suffix(self):
        """error_count > 去重后 error 总数 → 反馈句尾追加「（共 N 处）」。

        锁定逻辑：`more = f"（共 {error_count} 处）" if error_count > len(errs) and errs`。
        len(errs) 是去重后的 error 数（不是展示数 3），故 error_count 必须超过去重后总数
        才会追加。同时锁定 has_loc：bool(line) 为真才带 file:line，line=0 视为无定位。
        """
        issues = [
            BuildIssue(severity="error", file=f"f{i}.c", line=i, column=1,
                       message=f"err{i}")
            for i in range(5)
        ]
        # error_count=9 > len(errs)=5（去重后 5 条，前缀各异）→ 追加后缀
        br = make_build_result(issues=issues, error_count=9)
        feedback, fix = _summarize_build_failure(br)

        # joined 取 errs[:3]：f0.c 行号 0 → 无定位只取描述；f1.c:1 / f2.c:2 带定位
        assert feedback == "编译失败：err0；f1.c:1: err1；f2.c:2: err2（共 9 处）"

    def test_more_count_suffix_not_appended_when_count_le_dedup_total(self):
        """error_count <= 去重后 error 总数 → 不追加「（共 N 处）」。

        锁定：more 条件是 error_count > len(errs)（去重后总数），不是 > 展示数 3。
        即便 error_count(5) > 展示数(3)，只要不超过去重后总数(5) 就不追加。
        """
        issues = [
            BuildIssue(severity="error", file=f"f{i}.c", line=i, column=1,
                       message=f"err{i}")
            for i in range(5)
        ]
        br = make_build_result(issues=issues, error_count=5)
        feedback, fix = _summarize_build_failure(br)
        assert feedback == "编译失败：err0；f1.c:1: err1；f2.c:2: err2"

    def test_exe_file_location_suppressed(self):
        """file 以 .exe 结尾时不带行号定位（防 Windows 工具链误带行号）。"""
        br = make_build_result(
            issues=[
                BuildIssue(severity="error", file="arm-none-eabi-gcc.exe", line=1,
                           column=1, message="boom"),
            ],
            error_count=1,
        )
        feedback, fix = _summarize_build_failure(br)
        # .exe 文件 has_loc=False → 只取描述，不带 file:line
        assert feedback == "编译失败：boom"

    def test_dedup_by_description_prefix(self):
        """描述前 60 字符相同视为重复，去重。

        锁定 has_loc：第一条 f0.c 行号 0 → 无定位，故不带 file:line。
        """
        same_prefix = "this is a long error message that repeats the same prefix many times"
        issues = [
            BuildIssue(severity="error", file=f"f{i}.c", line=i, column=1,
                       message=same_prefix + f" tail{i}")
            for i in range(3)
        ]
        br = make_build_result(issues=issues, error_count=3)
        feedback, fix = _summarize_build_failure(br)
        # 三条 desc[:60] 相同 → 只保留第一条
        # 第一条 line=0 → 无定位 → 不带 file:line，只取描述
        assert feedback == f"编译失败：{same_prefix} tail0（共 3 处）"
