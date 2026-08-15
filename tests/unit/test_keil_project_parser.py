#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""KeilProjectParser 单测（P4a：.uvprojx → 用户源码提取）。

覆盖：无命名空间/MSBuild 命名空间两种 uvprojx 变体、三层厂商过滤
（路径片段/系统文件前缀/扩展名）+ allowlist 覆盖、路径相对工程目录解析
（含 .. 与反斜杠）、USER CODE 区段提取（空块跳过/未闭合忽略）、
真实 07-car-gear 工程冒烟、畸形 XML 由 defusedxml 干净报错。
"""

from pathlib import Path

import pytest

from parsers.keil_project_parser import KeilProjectParser

REPO = Path(__file__).resolve().parents[2]
REAL_UVPROJX = (REPO / "src" / "projects" / "07-car-gear" / "cubemx"
                / "MDK-ARM" / "cubemx.uvprojx")

MAIN_C = """#include "main.h"
/* USER CODE BEGIN 0 */
int user_helper(void) { return 42; }
/* USER CODE END 0 */
int main(void)
{
  /* USER CODE BEGIN WHILE */
  while (1) { HAL_Delay(100); }
  /* USER CODE END WHILE */
}
"""

GPIO_C = """#include "main.h"
/* USER CODE BEGIN Includes */
#include <stdio.h>
/* USER CODE END Includes */
void MX_GPIO_Init(void) { }
"""

MSBUILD_NS = "http://schemas.microsoft.com/developer/msbuild/2003"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _minimal_project_xml(entries_xml: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<Project><Targets><Target><Groups><Group>"
        "<GroupName>G</GroupName><Files>"
        "%s"
        "</Files></Group></Groups></Target></Targets></Project>\n" % entries_xml
    )


def _synthetic_project(tmp_path: Path, namespace: str = "") -> Path:
    """Minimal but structurally faithful uvprojx + on-disk sources.

    namespace=""  -> bare tags (matches the repo's real 07-car-gear file)
    namespace=URL -> root tag declares a DEFAULT xmlns (descendant tags stay
        bare on disk but the parser reports them namespaced -- the other
        uvprojx flavor). NOTE: ElementTree's "{ns}tag" is a Python-side
        notation, never serial XML syntax.
    """
    def group(name: str, entries: str) -> str:
        return "<Group><GroupName>%s</GroupName><Files>%s</Files></Group>" % (
            name, entries)

    def entry(fname: str, fpath: str) -> str:
        return ("<File><FileName>%s</FileName><FileType>1</FileType>"
                "<FilePath>%s</FilePath></File>" % (fname, fpath))

    root_open = ('<Project xmlns="%s">' % namespace) if namespace else "<Project>"
    xml = "\n".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        root_open,
        "<Targets>",
        "<Target>",
        "<Groups>",
        group("Application/User/Core", "".join([
            entry("main.c", "../Core/Src/main.c"),
            entry("gpio.c", "..\\Core\\Src\\gpio.c"),
            entry("stm32f4xx_it.c", "../Core/Src/stm32f4xx_it.c"),
        ])),
        group("Drivers/CMSIS",
              entry("system_stm32f4xx.c",
                    "../Drivers/CMSIS/system_stm32f4xx.c")),
        group("Drivers/STM32F4xx_HAL_Driver",
              entry("stm32f4xx_hal_gpio.c",
                    "../Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_gpio.c")),
        group("Application/MDK-ARM",
              entry("startup_stm32f407xx.s", "startup_stm32f407xx.s")),
        "</Groups>",
        "</Target>",
        "</Targets>",
        "</Project>",
    ])

    proj = _write(tmp_path / "MDK-ARM" / "proj.uvprojx", xml)
    _write(tmp_path / "Core" / "Src" / "main.c", MAIN_C)
    _write(tmp_path / "Core" / "Src" / "gpio.c", GPIO_C)
    return proj


# ------------------------------------------------------------ classification

def test_bare_tags_classification(tmp_path):
    proj = _synthetic_project(tmp_path)
    by_name = {f.name: f for f in KeilProjectParser().parse(proj)}

    assert set(by_name) == {
        "main.c", "gpio.c", "stm32f4xx_it.c",
        "system_stm32f4xx.c", "stm32f4xx_hal_gpio.c", "startup_stm32f407xx.s"}
    # 用户文件：main.c / gpio.c（CubeMX 系统文件与厂商库全部剔除）
    assert not by_name["main.c"].is_vendor
    assert not by_name["gpio.c"].is_vendor
    assert by_name["stm32f4xx_it.c"].is_vendor          # 系统文件前缀
    assert by_name["system_stm32f4xx.c"].is_vendor      # CMSIS 路径 + 前缀
    assert by_name["stm32f4xx_hal_gpio.c"].is_vendor    # Drivers/ 路径
    assert by_name["startup_stm32f407xx.s"].is_vendor   # 扩展名过滤


def test_namespaced_tags_parse_identically(tmp_path):
    proj = _synthetic_project(tmp_path, namespace=MSBUILD_NS)
    files = KeilProjectParser().parse(proj)
    assert {f.name for f in files if not f.is_vendor} == {"main.c", "gpio.c"}


def test_path_resolution_relative_to_project_dir(tmp_path):
    proj = _synthetic_project(tmp_path)
    files = {f.name: f for f in KeilProjectParser().parse(proj)}
    assert files["main.c"].path == (tmp_path / "Core" / "Src" / "main.c").resolve()
    assert files["main.c"].path.is_file()
    # 反斜杠路径同样正确解析
    assert files["gpio.c"].path == (tmp_path / "Core" / "Src" / "gpio.c").resolve()


def test_group_recorded(tmp_path):
    proj = _synthetic_project(tmp_path)
    files = {f.name: f for f in KeilProjectParser().parse(proj)}
    assert files["main.c"].group == "Application/User/Core"
    assert files["stm32f4xx_hal_gpio.c"].group == "Drivers/STM32F4xx_HAL_Driver"


def test_allowlist_overrides_vendor_path(tmp_path):
    proj = _synthetic_project(tmp_path)
    parser = KeilProjectParser(allowlist=("hal_gpio",))
    files = {f.name: f for f in parser.parse(proj)}
    assert not files["stm32f4xx_hal_gpio.c"].is_vendor   # allowlist 胜出


# ---------------------------------------------------------- USER CODE blocks

def test_user_code_blocks_extracted(tmp_path):
    proj = _synthetic_project(tmp_path)
    files = {f.name: f for f in KeilProjectParser().parse(proj)}
    markers = {m for m, _ in files["main.c"].user_sections}
    assert markers == {"0", "WHILE"}
    body = dict(files["main.c"].user_sections)
    assert "user_helper" in body["0"]
    assert "HAL_Delay" in body["WHILE"]


def _single_file_project(proj_dir: Path, source: str) -> Path:
    _write(proj_dir / "a.c", source)
    return _write(proj_dir / "p.uvprojx", _minimal_project_xml(
        "<File><FileName>a.c</FileName><FileType>1</FileType>"
        "<FilePath>a.c</FilePath></File>"))


def test_empty_blocks_skipped(tmp_path):
    proj = _single_file_project(
        tmp_path / "MDK-ARM",
        "/* USER CODE BEGIN 1 */\n/* USER CODE END 1 */\nint x;")
    assert KeilProjectParser().parse(proj)[0].user_sections == []


def test_unclosed_block_ignored(tmp_path):
    proj = _single_file_project(
        tmp_path / "MDK-ARM",
        "/* USER CODE BEGIN 2 */\nint leaked = 1;\n")   # never closed
    assert KeilProjectParser().parse(proj)[0].user_sections == []


def test_user_code_text_default_blocks_only(tmp_path):
    proj = _synthetic_project(tmp_path)
    text = KeilProjectParser().user_code_text(proj)
    assert "user_helper" in text and "HAL_Delay" in text
    assert "#include <stdio.h>" in text          # gpio.c 的 Includes 块
    # 非区段内容不进入默认输出（main 函数体在标记之外）
    assert "int main(void)" not in text


def test_include_generated_appends_markerless_user_files(tmp_path):
    proj_dir = tmp_path / "MDK-ARM2"
    _write(proj_dir / "hand_written.c", "void my_uart_handler(void) { }")
    proj = _write(proj_dir / "p2.uvprojx", _minimal_project_xml(
        "<File><FileName>hand_written.c</FileName><FileType>1</FileType>"
        "<FilePath>hand_written.c</FilePath></File>"))

    parser = KeilProjectParser()
    assert parser.user_code_text(proj) == ""            # 无标记 → 默认空
    combined = parser.user_code_text(proj, include_generated=True)
    assert "my_uart_handler" in combined


def test_missing_project_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        KeilProjectParser().parse(tmp_path / "nope.uvprojx")


def test_malformed_xml_raises_cleanly(tmp_path):
    from xml.etree import ElementTree as ET
    bad = _write(tmp_path / "bad.uvprojx", "<Project><Unclosed>")
    with pytest.raises(ET.ParseError):
        KeilProjectParser().parse(bad)


# ------------------------------------------ adversarial-review regressions

def _project_with_files(tmp_path, entries):
    """One uvprojx whose single group lists the given (name, path) files."""
    xml_files = "".join(
        "<File><FileName>%s</FileName><FileType>1</FileType>"
        "<FilePath>%s</FilePath></File>" % (n, p) for n, p in entries)
    return _write(tmp_path / "MDK-ARM" / "p.uvprojx",
                  _minimal_project_xml(xml_files))


def test_automotive_user_files_survive_dir_matching(tmp_path):
    """D1 回归：文件名/学生目录含厂商词不得误杀（汽车学院 CAN 驱动场景）。"""
    proj = _project_with_files(tmp_path, [
        ("my_drivers.c", "../Core/Src/my_drivers.c"),
        ("can.c", "../MyDrivers/can.c"),
        ("rtos.c", "../Core/Src/rtos.c"),
        ("lwip_demo.c", "../Core/Src/lwip_demo.c"),
        ("middleware_notes.c", "../Core/Src/middleware_notes.c"),
        ("can_driver.c", "../Core/Src/can_driver.c"),
        ("readme.md", "../Drivers/readme.md"),          # 厂商目录 + 非代码
        ("hal_extra.c", "../STM32F4xx_HAL_Driver/Src/hal_extra.c"),
    ])
    files = {f.name: f for f in KeilProjectParser().parse(proj)}
    for name in ("my_drivers.c", "can.c", "rtos.c", "lwip_demo.c",
                 "middleware_notes.c", "can_driver.c"):
        assert not files[name].is_vendor, name
    assert files["readme.md"].is_vendor
    assert files["hal_extra.c"].is_vendor              # _HAL_Driver 目录


def test_vendor_dirs_still_match(tmp_path):
    proj = _project_with_files(tmp_path, [
        ("a.c", "../Drivers/x/a.c"),
        ("b.c", "../Middlewares/x/b.c"),
        ("c.c", "../FreeRTOS/Source/c.c"),
        ("d.c", "../MDK-ARM/sub/d.c"),
    ])
    files = KeilProjectParser().parse(proj)
    assert all(f.is_vendor for f in files)


def test_multi_target_project_dedupes(tmp_path):
    """D2 回归：Debug/Release 双 Target 引用同文件只计一次。"""
    def group(entries):
        return ("<Group><GroupName>G</GroupName><Files>%s</Files></Group>"
                % entries)
    file_xml = ("<File><FileName>main.c</FileName><FileType>1</FileType>"
                "<FilePath>../Core/Src/main.c</FilePath></File>")
    xml = ("<Project><Targets>"
           "<Target><Groups>%s</Groups></Target>"   # target 1
           "<Target><Groups>%s</Groups></Target>"   # target 2 (duplicate)
           "</Targets></Project>") % (group(file_xml), group(file_xml))
    proj = _write(tmp_path / "MDK-ARM" / "p.uvprojx", xml)
    _write(tmp_path / "Core" / "Src" / "main.c", MAIN_C)

    parser = KeilProjectParser()
    files = parser.parse(proj)
    assert len(files) == 1
    assert parser.user_code_text(proj).count("user_helper") == 1


def test_filepath_before_filename_order(tmp_path):
    """元素顺序无关：FileName 缺失时回退为路径 basename。"""
    xml = _minimal_project_xml(
        "<File><FileType>1</FileType><FilePath>../Core/Src/main.c</FilePath>"
        "<FileName>main.c</FileName></File>")
    proj = _write(tmp_path / "MDK-ARM" / "p.uvprojx", xml)
    files = KeilProjectParser().parse(proj)
    assert len(files) == 1 and files[0].name == "main.c"
    assert not files[0].is_vendor


def test_filepath_without_filename_uses_basename(tmp_path):
    proj = _write(tmp_path / "MDK-ARM" / "p.uvprojx", _minimal_project_xml(
        "<File><FileType>1</FileType><FilePath>../Core/Src/gpio.c</FilePath></File>"))
    files = KeilProjectParser().parse(proj)
    assert files[0].name == "gpio.c" and not files[0].is_vendor


def test_out_of_tree_filepath_flagged_never_read(tmp_path):
    """绝对路径/出树路径：标记 vendor、绝不读取、记录在案。

    树根 = MDK-ARM 的上级（CubeMX 布局：root/{MDK-ARM,Core,Drivers}），
    所以工程放 tmp_path/proj/MDK-ARM，机密文件放 tmp_path/outside（树外）。
    """
    outside = _write(tmp_path / "outside" / "secret.c",
                     "int teacher_answer_key = 1;")
    xml = _minimal_project_xml(
        "<File><FileName>evil.c</FileName><FileType>1</FileType>"
        "<FilePath>%s</FilePath></File>" % outside.as_posix())
    proj = _write(tmp_path / "proj" / "MDK-ARM" / "p.uvprojx", xml)

    parser = KeilProjectParser()
    files = parser.parse(proj)
    assert files[0].is_vendor
    assert outside.as_posix() in parser.last_flagged_paths
    assert "teacher_answer_key" not in parser.user_code_text(proj)

    # 合法的树内 ../ 路径不受影响
    legit = _write(tmp_path / "proj" / "Core" / "Src" / "main.c", MAIN_C)
    xml2 = _minimal_project_xml(
        "<File><FileName>main.c</FileName><FileType>1</FileType>"
        "<FilePath>../Core/Src/main.c</FilePath></File>")
    proj2 = _write(tmp_path / "proj" / "MDK-ARM" / "p2.uvprojx", xml2)
    files2 = KeilProjectParser().parse(proj2)
    assert not files2[0].is_vendor
    assert "user_helper" in KeilProjectParser().user_code_text(proj2)


def test_single_line_begin_end_blocks_isolated(tmp_path):
    """单行 BEGIN+END：两块各自完整，块间生成代码不泄漏进学生信号。"""
    src = ("/* USER CODE BEGIN 0 */ int a; /* USER CODE END 0 */\n"
           "int cube_generated_between;\n"
           "/* USER CODE BEGIN 1 */ int b; /* USER CODE END 1 */\n")
    proj = _single_file_project(tmp_path / "MDK-ARM", src)
    sections = dict(KeilProjectParser().parse(proj)[0].user_sections)
    assert sections == {"0": "int a;", "1": "int b;"}


def test_code_before_end_on_same_line_counts_as_block(tmp_path):
    src = ("/* USER CODE BEGIN 2 */\n"
           "int keep = 1; /* USER CODE END 2 */\n")
    proj = _single_file_project(tmp_path / "MDK-ARM", src)
    sections = dict(KeilProjectParser().parse(proj)[0].user_sections)
    assert sections == {"2": "int keep = 1;"}


def test_gbk_source_comments_survive(tmp_path):
    """GBK 编码源文件（中文 Windows Keil 常见）：中文注释不乱码。"""
    proj_dir = tmp_path / "MDK-ARM"
    (proj_dir / "a.c").parent.mkdir(parents=True, exist_ok=True)
    (proj_dir / "a.c").write_bytes(
        "/* USER CODE BEGIN 0 */\nint gbk_var = 1; // 中文注释\n"
        "/* USER CODE END 0 */\n".encode("gbk"))
    proj = _write(proj_dir / "p.uvprojx", _minimal_project_xml(
        "<File><FileName>a.c</FileName><FileType>1</FileType>"
        "<FilePath>a.c</FilePath></File>"))
    text = KeilProjectParser().user_code_text(proj)
    assert "中文注释" in text


def test_gbk_declared_uvprojx_parses(tmp_path):
    """pyexpat 拒绝多字节声明编码 → 预解码后解析。"""
    proj_dir = tmp_path / "MDK-ARM"
    proj_dir.mkdir(parents=True)
    xml = ('<?xml version="1.0" encoding="GBK"?>\n'
           "<Project><Targets><Target><Groups><Group>"
           "<GroupName>我的组</GroupName><Files>"
           "<File><FileName>a.c</FileName><FileType>1</FileType>"
           "<FilePath>a.c</FilePath></File>"
           "</Files></Group></Groups></Target></Targets></Project>\n")
    (proj_dir / "p.uvprojx").write_bytes(xml.encode("gbk"))
    files = KeilProjectParser().parse(proj_dir / "p.uvprojx")
    assert files[0].name == "a.c" and files[0].group == "我的组"


def test_scaffold_files_keep_user_sections(tmp_path):
    """stm32f4xx_it.c：整体 vendor（不入 user_sources），但学生写的
    USER CODE（ISR 逻辑）进入 user_code_text。"""
    src = ("void EXTI0_IRQHandler(void) { }\n"
           "/* USER CODE BEGIN 1 */\n"
           "HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_0);\n"
           "/* USER CODE END 1 */\n")
    proj = _single_file_project(tmp_path / "MDK-ARM", src)
    # 把文件名换成 scaffold 名
    proj.write_text(proj.read_text(encoding="utf-8").replace(
        "a.c", "stm32f4xx_it.c"), encoding="utf-8")
    (tmp_path / "MDK-ARM" / "stm32f4xx_it.c").write_text(
        src, encoding="utf-8")

    parser = KeilProjectParser()
    files = parser.parse(proj)
    it = files[0]
    assert it.is_vendor and it.scaffold
    assert parser.user_sources(proj) == []
    text = parser.user_code_text(proj)
    assert "HAL_GPIO_EXTI_IRQHandler" in text


# ------------------------------------------------------------- real project

@pytest.mark.skipif(not REAL_UVPROJX.is_file(), reason="real uvprojx absent")
def test_real_07_car_gear_project():
    parser = KeilProjectParser()
    files = parser.parse(REAL_UVPROJX)
    assert files, "real project should reference files"

    user = [f for f in files if not f.is_vendor]
    names = {f.name for f in user}
    assert {"main.c", "gpio.c"} <= names           # 用户核心文件
    # 厂商与系统文件绝不出现在用户集
    assert not any("hal" in f.name for f in user)
    assert not any(f.name.startswith(("startup", "system_")) for f in user)
    assert all(f.path.suffix in (".c", ".h") for f in user)

    text = parser.user_code_text(REAL_UVPROJX)
    assert text.strip()                            # 真工程确有 USER CODE 区段
