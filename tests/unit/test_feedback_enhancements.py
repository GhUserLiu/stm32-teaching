# -*- coding: utf-8 -*-
"""
反馈增强单测：
- _detect_blocking_wrappers：检测封装了 HAL_Delay 的阻塞延时函数及其调用点（次美业场景）
- _makefile_c_sources / _resolve_symbol_definers / _diagnose_missing_sources：
  链接失败时把 undefined reference 定位到漏列的 .c（高雅梅场景）
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, "src")

from tools.auto_grading.grading_engine import (
    _detect_blocking_wrappers,
    _makefile_c_sources,
    _resolve_symbol_definers,
    _diagnose_missing_sources,
)


# -----------------------------------------------------------------------
# 封装函数检测（非阻塞反馈）
# -----------------------------------------------------------------------
class TestDetectBlockingWrappers:
    def test_single_line_wrapper_and_calls(self, tmp_path):
        """单行封装 void HAL_Delay_ms(...){ HAL_Delay(...); } + 主循环调用 → 命中。"""
        src = tmp_path / "Core/Src/main.c"
        src.parent.mkdir(parents=True)
        src.write_text(
            '#include "main.h"\n'
            "void HAL_Delay_ms(uint32_t ms){ (void)HAL_Delay(ms); }\n"
            "int main(void){\n"
            "  while(1){ HAL_Delay_ms(20); HAL_Delay_ms(100); }\n"
            "}\n",
            encoding="utf-8",
        )
        wrappers, indirect, _body = _detect_blocking_wrappers(tmp_path, [src])
        assert "HAL_Delay_ms" in wrappers
        assert wrappers["HAL_Delay_ms"] == "Core/Src/main.c:2"
        assert len(indirect) == 2
        assert {v["line"] for v in indirect} == {4}

    def test_allman_style_wrapper(self, tmp_path):
        """Allman 风格（{ 在下一行）也能识别。"""
        src = tmp_path / "main.c"
        src.write_text(
            "static void my_delay(uint32_t ms)\n"
            "{\n"
            "    HAL_Delay(ms);\n"
            "}\n"
            "void f(void){ my_delay(5); my_delay(6); }\n",
            encoding="utf-8",
        )
        wrappers, indirect, _body = _detect_blocking_wrappers(tmp_path, [src])
        assert "my_delay" in wrappers
        assert len(indirect) == 2

    def test_forward_declaration_not_wrapper(self, tmp_path):
        """前向声明（行尾分号）不是封装定义，不应被当成封装函数。"""
        src = tmp_path / "main.c"
        src.write_text(
            "void HAL_Delay_ms(uint32_t ms);\n"      # 声明
            "void f(void){ HAL_Delay(10); }\n",       # 直接调用，但 f 不是封装
            encoding="utf-8",
        )
        wrappers, indirect, _body = _detect_blocking_wrappers(tmp_path, [src])
        assert "HAL_Delay_ms" not in wrappers
        assert indirect == []

    def test_no_hal_delay_wrapper(self, tmp_path):
        src = tmp_path / "main.c"
        src.write_text("void f(void){ uint32_t t = HAL_GetTick(); }\n", encoding="utf-8")
        wrappers, indirect, _body = _detect_blocking_wrappers(tmp_path, [src])
        assert wrappers == {}
        assert indirect == []

    def test_wrapper_definition_line_not_counted_as_call(self, tmp_path):
        """封装函数自身定义行不计入调用点。"""
        src = tmp_path / "main.c"
        src.write_text(
            "void d(uint32_t m){ HAL_Delay(m); }\n"
            "void g(void){ d(1); }\n",
            encoding="utf-8",
        )
        wrappers, indirect, _body = _detect_blocking_wrappers(tmp_path, [src])
        assert "d" in wrappers
        # 只有 g 里的 d(1) 算调用；d 的定义行(含 HAL_Delay)不算
        assert len(indirect) == 1
        assert indirect[0]["line"] == 2

    def test_forward_declaration_not_counted_as_call(self, tmp_path):
        """封装函数的 .c 前向声明（返回类型 + 分号）不是调用，不应计入 indirect。"""
        src = tmp_path / "main.c"
        src.write_text(
            "void dly(uint32_t m);\n"                       # 前向声明
            "void dly(uint32_t m){ HAL_Delay(m); }\n"       # 定义
            "void g(void){ dly(1); }\n",                    # 真调用
            encoding="utf-8",
        )
        wrappers, indirect, _body = _detect_blocking_wrappers(tmp_path, [src])
        assert wrappers.get("dly") == "main.c:2"
        assert len(indirect) == 1            # 只有 line 3 的真调用
        assert indirect[0]["line"] == 3

    def test_header_prototype_not_counted_as_call(self, tmp_path):
        """封装函数在 .h 里的原型声明不应被当成调用点。"""
        inc = tmp_path / "Core/Inc/dly.h"
        inc.parent.mkdir(parents=True)
        inc.write_text("void dly(uint32_t m);\n", encoding="utf-8")
        main_c = tmp_path / "Core/Src/main.c"
        main_c.parent.mkdir(parents=True)
        main_c.write_text(
            '#include "dly.h"\n'
            "void dly(uint32_t m){ HAL_Delay(m); }\n"
            "int main(void){ dly(5); }\n",
            encoding="utf-8",
        )
        wrappers, indirect, _body = _detect_blocking_wrappers(tmp_path, [inc, main_c])
        assert "dly" in wrappers
        # 只计 main.c:3 的真调用；dly.h:1 的原型不算
        assert len(indirect) == 1
        assert indirect[0]["file"] == "Core/Src/main.c"
        assert indirect[0]["line"] == 3

    def test_comment_mention_not_counted_as_call(self, tmp_path):
        """注释里提到封装函数不应计入调用点。"""
        src = tmp_path / "main.c"
        src.write_text(
            "void dly(uint32_t m){ HAL_Delay(m); }\n"
            "// 这里调用 dly() 做延时\n"
            "void g(void){ dly(1); }\n",
            encoding="utf-8",
        )
        wrappers, indirect, _body = _detect_blocking_wrappers(tmp_path, [src])
        assert len(indirect) == 1
        assert indirect[0]["line"] == 3


# -----------------------------------------------------------------------
# 链接失败缺失文件定位（高雅梅场景）
# -----------------------------------------------------------------------
class TestLinkFailureDiagnosis:
    def test_makefile_c_sources_parses_block(self, tmp_path):
        mk = tmp_path / "Makefile"
        mk.write_text(
            "C_SOURCES = \\\n"
            "Core/Src/main.c \\\n"
            "./Drivers/HAL/Src/stm32f4xx_hal.c \\\n"
            "foo.c\n"
            "CFLAGS = -O2\n",
            encoding="utf-8",
        )
        cs = _makefile_c_sources(tmp_path)
        assert "Core/Src/main.c" in cs
        assert "Drivers/HAL/Src/stm32f4xx_hal.c" in cs
        assert "foo.c" in cs
        assert "CFLAGS" not in cs   # 不越界抓到下一个变量

    def test_makefile_c_sources_no_makefile(self, tmp_path):
        assert _makefile_c_sources(tmp_path) == set()

    def test_resolve_symbol_definers(self, tmp_path):
        key = tmp_path / "Core/Src/key.c"
        key.parent.mkdir(parents=True)
        key.write_text(
            '#include "key.h"\n'
            "uint8_t key_scan(void){ return 0; }\n",
            encoding="utf-8",
        )
        d = _resolve_symbol_definers(["key_scan", "no_such_sym"], [key], tmp_path)
        assert d == {"key_scan": ["Core/Src/key.c"]}

    def test_diagnose_reports_missing_files(self, tmp_path):
        """定义了符号、但 .c 未在 C_SOURCES → 反馈点名该文件未参与编译。"""
        key = tmp_path / "Core/Src/key.c"
        key.parent.mkdir(parents=True)
        key.write_text(
            "void KEY_Init(void){}\n"
            "uint8_t key_scan(void){ return 0; }\n",
            encoding="utf-8",
        )
        (tmp_path / "Makefile").write_text(
            "C_SOURCES = \\\nCore/Src/main.c\n", encoding="utf-8"   # 不含 key.c
        )

        class PI:
            source_files = [key]

        class Sub:
            project_info = PI()
            source_path = str(tmp_path)

        msg = _diagnose_missing_sources(["KEY_Init", "key_scan"], Sub())
        assert "Core/Src/key.c" in msg
        assert "C_SOURCES" in msg
        assert "KEY_Init" in msg and "key_scan" in msg

    def test_diagnose_all_present_no_missing(self, tmp_path):
        """定义文件已在 C_SOURCES → 不报"未参与编译"，改提示签名/重新生成。"""
        key = tmp_path / "Core/Src/key.c"
        key.parent.mkdir(parents=True)
        key.write_text("void KEY_Init(void){}\n", encoding="utf-8")
        (tmp_path / "Makefile").write_text(
            "C_SOURCES = \\\nCore/Src/key.c\n", encoding="utf-8"   # 含 key.c
        )

        class PI:
            source_files = [key]

        class Sub:
            project_info = PI()
            source_path = str(tmp_path)

        msg = _diagnose_missing_sources(["KEY_Init"], Sub())
        assert "未参与编译" not in msg   # 没有漏列
        assert "KEY_Init" in msg         # 仍给出定义位置提示

    def test_diagnose_no_submission_returns_empty(self):
        assert _diagnose_missing_sources(["x"], None) == ""

    def test_diagnose_empty_symbols_returns_empty(self, tmp_path):
        class Sub:
            class project_info:
                source_files = []
            source_path = str(tmp_path)
        assert _diagnose_missing_sources([], Sub()) == ""


# -----------------------------------------------------------------------
# 非阻塞计分：封装调用计入扣分，封装体内 HAL_Delay 不重复计
# -----------------------------------------------------------------------
class TestNonBlockingScoring:
    """_grade_source_check 把封装函数的调用点计入扣分（任务书：禁止阻塞延时，
    直接/间接同口径）；封装函数体内那条 HAL_Delay 是"成因"，不与调用点重复计。"""

    def _submission(self, tmp_path, files_content):
        src_files = []
        for rel, text in files_content.items():
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
            src_files.append(p)

        class PI:
            source_files = src_files
            header_files = []

        class Sub:
            project_info = PI()
            source_path = str(tmp_path)

        return Sub()

    def _cat(self):
        return {'id': 'non_blocking', 'name': '非阻塞', 'points': 10,
                'penalty_per_hit': 5, 'forbid_patterns': [r'HAL_Delay\s*\(']}

    def test_wrapper_calls_count_toward_score(self, tmp_path):
        from tools.auto_grading.grading_engine import AutoGradingEngine
        engine = AutoGradingEngine()
        sub = self._submission(tmp_path, {
            'Core/Src/main.c':
                'void HAL_Delay_ms(uint32_t ms){ (void)HAL_Delay(ms); }\n'
                'int main(void){ while(1){ HAL_Delay_ms(20); HAL_Delay_ms(100); } }\n',
        })
        cs = engine._grade_source_check(sub, self._cat())
        # 封装体内 HAL_Delay 排除 + 2 个封装调用点 = 2 → max(0,10-10)=0
        assert cs.earned_points == 0.0
        assert cs.details[0]['hit_count'] == 2

    def test_wrapper_body_hal_delay_not_double_counted(self, tmp_path):
        """封装只被调用一次：体内 HAL_Delay 排除 + 1 调用点 = 1 → 5/10（非 0）。"""
        from tools.auto_grading.grading_engine import AutoGradingEngine
        engine = AutoGradingEngine()
        sub = self._submission(tmp_path, {
            'main.c':
                'void d(uint32_t m){ HAL_Delay(m); }\n'
                'void g(void){ d(1); }\n',
        })
        cs = engine._grade_source_check(sub, self._cat())
        assert cs.details[0]['hit_count'] == 1
        assert cs.earned_points == 5.0

    def test_direct_hal_delay_outside_wrapper_counts(self, tmp_path):
        from tools.auto_grading.grading_engine import AutoGradingEngine
        engine = AutoGradingEngine()
        sub = self._submission(tmp_path, {
            'main.c': 'int main(void){ HAL_Delay(50); HAL_Delay(60); }\n',
        })
        cs = engine._grade_source_check(sub, self._cat())
        assert cs.details[0]['hit_count'] == 2
        assert cs.earned_points == 0.0

    def test_no_violation_full_marks(self, tmp_path):
        from tools.auto_grading.grading_engine import AutoGradingEngine
        engine = AutoGradingEngine()
        sub = self._submission(tmp_path, {
            'main.c': 'int main(void){ while(1){ uint32_t t = HAL_GetTick(); } }\n',
        })
        cs = engine._grade_source_check(sub, self._cat())
        assert cs.earned_points == 10.0
        assert cs.details[0]['hit_count'] == 0
