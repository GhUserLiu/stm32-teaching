#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Keil 源码门控接线单测（P4b-1：_analyze_project 接 KeilProjectParser）。

钉死的行为：
- project_type=="keil"（根下无 Core/、有 uvprojx）→ 源码收集经解析器门控，
  Drivers/CMSIS 厂商树不再进入 source_files，main.c 仍在；
- 解析失败（畸形 uvprojx）→ 回退 legacy 盲扫（收集范围与旧代码一致）；
- cubemx/simple 类型 → 完全不受影响（仍为盲扫）。
"""

from pathlib import Path

from tools.auto_grading.submission_processor import SubmissionProcessor

PROCESSOR = SubmissionProcessor(Path("."))   # base_dir 不参与 _analyze_project

UVPROJX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Project><Targets><Target><Groups>
<Group><GroupName>Application/User/Core</GroupName><Files>
<File><FileName>main.c</FileName><FileType>1</FileType>
<FilePath>../Core/Src/main.c</FilePath></File>
<File><FileName>can_driver.c</FileName><FileType>1</FileType>
<FilePath>../Core/Src/can_driver.c</FilePath></File>
<File><FileName>app_cfg.h</FileName><FileType>5</FileType>
<FilePath>../Core/Inc/app_cfg.h</FilePath></File>
</Files></Group>
<Group><GroupName>Drivers/STM32F4xx_HAL_Driver</GroupName><Files>
<File><FileName>stm32f4xx_hal_gpio.c</FileName><FileType>1</FileType>
<FilePath>../Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_gpio.c</FilePath></File>
<File><FileName>stm32f4xx_hal_conf.h</FileName><FileType>5</FileType>
<FilePath>../Drivers/STM32F4xx_HAL_Driver/Inc/stm32f4xx_hal_conf.h</FilePath></File>
</Files></Group>
</Groups></Target></Targets></Project>
"""

MAIN_C = 'int main(void) { while (1) { } }\n'
CAN_C = 'void CAN_Filter_Config(void) { }\n'
HAL_C = 'HAL_StatusTypeDef HAL_GPIO_Init(void) { return 0; }\n'


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _keil_project(tmp_path: Path) -> Path:
    """keil 型提交：zip 多一层包裹目录 → Core/ 不在 project_path 根下，
    rglob 能找到 uvprojx → project_type=="keil"。"""
    root = tmp_path / "src_root"                     # ← project_path
    nest = root / "cubemx"
    _write(nest / "MDK-ARM" / "proj.uvprojx", UVPROJX_XML)
    _write(nest / "Core" / "Src" / "main.c", MAIN_C)
    _write(nest / "Core" / "Src" / "can_driver.c", CAN_C)
    _write(nest / "Core" / "Inc" / "app_cfg.h", "#pragma once\n")
    _write(nest / "Drivers" / "STM32F4xx_HAL_Driver" / "Src"
           / "stm32f4xx_hal_gpio.c", HAL_C)
    _write(nest / "Drivers" / "STM32F4xx_HAL_Driver" / "Inc"
           / "stm32f4xx_hal_conf.h", "#pragma once\n")
    return root


def _nest(tmp_path: Path) -> Path:
    """_keil_project 的工程内层目录（MDK-ARM 所在）。"""
    return _keil_project(tmp_path) / "cubemx"


# ------------------------------------------------------------------- gating

def test_keil_project_collects_user_sources_only(tmp_path):
    info = PROCESSOR._analyze_project(_keil_project(tmp_path))

    assert info.project_type == "keil"
    src_names = {p.name for p in info.source_files}
    assert src_names == {"main.c", "can_driver.c"}    # 厂商 .c 全部剔除
    assert {p.name for p in info.header_files} == {"app_cfg.h"}
    assert {p.name for p in info.main_files} == {"main.c"}
    # 用户文件真实存在（路径解析正确）
    assert all(p.is_file() for p in info.source_files)


def test_keil_gating_survives_automotive_driver_names(tmp_path):
    """D1 教训回归：用户驱动文件名不得被门控误杀。"""
    root = _keil_project(tmp_path)
    nest = _nest(tmp_path)
    _write(nest / "Core" / "Src" / "my_drivers.c", "int my_driver(void);\n")
    # 追加到 uvprojx 的用户组
    uv = nest / "MDK-ARM" / "proj.uvprojx"
    uv.write_text(
        uv.read_text(encoding="utf-8").replace(
            "<FilePath>../Core/Src/can_driver.c</FilePath></File>",
            "<FilePath>../Core/Src/can_driver.c</FilePath></File>"
            "<File><FileName>my_drivers.c</FileName><FileType>1</FileType>"
            "<FilePath>../Core/Src/my_drivers.c</FilePath></File>"),
        encoding="utf-8")

    info = PROCESSOR._analyze_project(root)
    assert "my_drivers.c" in {p.name for p in info.source_files}


def test_malformed_uvprojx_falls_back_to_blind_scan(tmp_path):
    root = _keil_project(tmp_path)
    (root / "cubemx" / "MDK-ARM" / "proj.uvprojx").write_text(
        "<Project><Unclosed>", encoding="utf-8")

    info = PROCESSOR._analyze_project(root)
    src_names = {p.name for p in info.source_files}
    # 回退 legacy 盲扫：厂商文件也在（与旧行为一致，绝不更糟）
    assert {"main.c", "can_driver.c", "stm32f4xx_hal_gpio.c"} <= src_names


def test_keil_without_user_entries_falls_back(tmp_path):
    """uvprojx 引用的用户文件全不在磁盘（残留条目）→ 回退盲扫而非幻影路径。"""
    root = tmp_path / "src_root"
    nest = root / "cubemx"
    _write(nest / "MDK-ARM" / "proj.uvprojx", UVPROJX_XML)   # 引用 main.c 等
    _write(nest / "Drivers" / "STM32F4xx_HAL_Driver" / "Src"
           / "stm32f4xx_hal_gpio.c", HAL_C)   # 只放厂商文件

    info = PROCESSOR._analyze_project(root)
    assert "stm32f4xx_hal_gpio.c" in {p.name for p in info.source_files}


# ------------------------------------------------------- other types intact

def test_cubemx_project_untouched(tmp_path):
    """cubemx 型（根下有 Core/）不走门控——主评分链路行为不变。"""
    proj = tmp_path / "src_root" / "cubemx"
    _write(proj / "Core" / "Src" / "main.c", MAIN_C)
    _write(proj / "Drivers" / "STM32F4xx_HAL_Driver" / "Src"
           / "stm32f4xx_hal_gpio.c", HAL_C)
    _write(proj / "MDK-ARM" / "proj.uvprojx", UVPROJX_XML)

    info = PROCESSOR._analyze_project(proj)
    assert info.project_type == "cubemx"
    # 盲扫：厂商文件照旧在列（legacy 行为钉死）
    assert {"main.c", "stm32f4xx_hal_gpio.c"} <= {
        p.name for p in info.source_files}


def test_simple_project_untouched(tmp_path):
    proj = tmp_path / "src_root" / "simple"
    _write(proj / "main.c", MAIN_C)

    info = PROCESSOR._analyze_project(proj)
    assert info.project_type == "simple"
    assert {p.name for p in info.source_files} == {"main.c"}


def test_relative_base_dir_is_resolved(tmp_path, monkeypatch):
    """分数反转回归：相对 base_dir 必须被 resolve，保证与门控返回的
    绝对路径同构（否则 relative_to 逐文件失败 → 违规学生拿满分）。"""
    monkeypatch.chdir(tmp_path)
    processor = SubmissionProcessor(Path("some/relative/base"))
    assert processor.base_dir.is_absolute()
    assert processor.base_dir == (tmp_path / "some" / "relative" / "base").resolve()
