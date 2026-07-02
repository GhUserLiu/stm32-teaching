# -*- coding: utf-8 -*-
"""
学生提交源码规整器单元测试
Submission Normalizer Unit Tests

覆盖 is_project_root / locate_project_root / flatten 的安全矩阵：
所有 ABORT 分支必须**原样保留目录树**，只有纯包装链才扁平化。
不依赖真实工具链，仅用 tmp_path 构造目录树。
"""

import os
import sys

import pytest

sys.path.insert(0, "src")

from tools.auto_grading.submission_normalizer import (
    SubmissionNormalizer as SN,
    NormalizeResult,
)


# ------------------------------------------------------------------
# 辅助
# ------------------------------------------------------------------
def _make_project_root(d):
    """在 d 处盖一个「工程根」：Makefile + Core/main.c + QIMO.ioc。"""
    d.mkdir(parents=True, exist_ok=True)
    (d / "Makefile").write_text("all:\n", encoding="utf-8")
    (d / "Core").mkdir()
    (d / "Core" / "main.c").write_text("int main(void){return 0;}", encoding="utf-8")
    (d / "QIMO.ioc").write_text("# ioc", encoding="utf-8")
    return d


# ==================================================================
# is_project_root
# ==================================================================
class TestIsProjectRoot:
    def test_makefile(self, tmp_path):
        (tmp_path / "Makefile").write_text("x", encoding="utf-8")
        assert SN.is_project_root(tmp_path) is True

    def test_mxproject(self, tmp_path):
        (tmp_path / ".mxproject").write_text("x", encoding="utf-8")
        assert SN.is_project_root(tmp_path) is True

    def test_core_dir_alone_is_not_root(self, tmp_path):
        # 仅凭 Core/ 目录不算工程根（需文件型构建标记）——否则只含同名包装目录的源码根会误判
        (tmp_path / "Core").mkdir()
        assert SN.is_project_root(tmp_path) is False

    def test_drivers_dir_alone_is_not_root(self, tmp_path):
        # 刘烊宏场景：源码根只套了一层 Drivers/ 包装，无 Makefile → 不是工程根
        (tmp_path / "Drivers").mkdir()
        assert SN.is_project_root(tmp_path) is False

    def test_bare_mdk_arm_dir_is_not_root(self, tmp_path):
        # 空 MDK-ARM/ 目录（无 .uvprojx）不算工程根
        (tmp_path / "MDK-ARM").mkdir()
        assert SN.is_project_root(tmp_path) is False

    def test_mdk_arm_uvprojx_is_root(self, tmp_path):
        # Keil 工程根：MDK-ARM/ 下有 .uvprojx
        (tmp_path / "MDK-ARM").mkdir()
        (tmp_path / "MDK-ARM" / "proj.uvprojx").write_text("x", encoding="utf-8")
        assert SN.is_project_root(tmp_path) is True

    def test_ioc_glob(self, tmp_path):
        (tmp_path / "proj.ioc").write_text("x", encoding="utf-8")
        assert SN.is_project_root(tmp_path) is True

    def test_uvprojx_glob(self, tmp_path):
        (tmp_path / "proj.uvprojx").write_text("x", encoding="utf-8")
        assert SN.is_project_root(tmp_path) is True

    def test_empty_dir(self, tmp_path):
        assert SN.is_project_root(tmp_path) is False

    def test_only_bare_c_file_is_not_root(self, tmp_path):
        # 刻意排除裸 .c：只有 main.c 不算工程根
        (tmp_path / "main.c").write_text("int main(void){}", encoding="utf-8")
        assert SN.is_project_root(tmp_path) is False

    def test_nonexistent(self, tmp_path):
        assert SN.is_project_root(tmp_path / "nope") is False


# ==================================================================
# locate_project_root
# ==================================================================
class TestLocateProjectRoot:
    def test_root_itself(self, tmp_path):
        _make_project_root(tmp_path)
        loc = SN.locate_project_root(tmp_path)
        assert loc == (tmp_path, 0)

    def test_one_level(self, tmp_path):
        _make_project_root(tmp_path / "wrap")
        assert SN.locate_project_root(tmp_path) == (tmp_path / "wrap", 1)

    def test_two_levels(self, tmp_path):
        _make_project_root(tmp_path / "QIMO" / "QIMO")
        assert SN.locate_project_root(tmp_path) == (tmp_path / "QIMO" / "QIMO", 2)

    def test_none(self, tmp_path):
        (tmp_path / "a").mkdir()
        assert SN.locate_project_root(tmp_path) is None

    def test_chain_ends_in_file(self, tmp_path):
        (tmp_path / "wrap").mkdir()
        (tmp_path / "wrap" / "notes.txt").write_text("x", encoding="utf-8")
        assert SN.locate_project_root(tmp_path) is None

    def test_shallowest_wins(self, tmp_path):
        # 顶层即是工程根，更深处还有一个 → 必须返回第 0 层
        _make_project_root(tmp_path)
        _make_project_root(tmp_path / "deeper")
        assert SN.locate_project_root(tmp_path) == (tmp_path, 0)


# ==================================================================
# flatten —— 行为矩阵
# ==================================================================
class TestFlatten:
    def test_pure_two_level_chain_flattens(self, tmp_path):
        """孔令林场景：QIMO/QIMO/{工程} → 工程内容上移到顶层。"""
        _make_project_root(tmp_path / "QIMO" / "QIMO")
        r = SN.flatten(tmp_path)
        assert r.flattened is True
        assert r.original_depth == 2
        assert r.skip_cause is None
        # 工程文件现已在顶层
        assert (tmp_path / "Makefile").is_file()
        assert (tmp_path / "Core").is_dir()
        assert (tmp_path / "QIMO.ioc").is_file()
        # 空壳已删
        assert not (tmp_path / "QIMO").exists()

    def test_one_level_chain_flattens(self, tmp_path):
        _make_project_root(tmp_path / "wrap")
        r = SN.flatten(tmp_path)
        assert r.flattened is True
        assert r.original_depth == 1
        assert (tmp_path / "Makefile").is_file()
        assert not (tmp_path / "wrap").exists()

    def test_drivers_named_wrapper_flattens(self, tmp_path):
        """刘烊宏场景：源码根只套一层 Drivers/（与 HAL 的 Drivers 同名）。
        旧实现把 Drivers/ 当 DIR_MARKER 误判 already_flat、不修；修复后应扁平化。"""
        _make_project_root(tmp_path / "Drivers")   # 包装层名为 Drivers
        r = SN.flatten(tmp_path)
        assert r.flattened is True
        assert r.original_depth == 1
        assert (tmp_path / "Makefile").is_file()    # 工程已提到顶层
        assert (tmp_path / "Core").is_dir()
        assert not (tmp_path / "Drivers").exists()  # 空壳包装层已删

    def test_already_flat(self, tmp_path):
        _make_project_root(tmp_path)
        r = SN.flatten(tmp_path)
        assert r.flattened is False
        assert r.skip_cause == NormalizeResult._CAUSE_ALREADY_FLAT
        assert r.original_depth == 0
        assert (tmp_path / "Makefile").is_file()  # 原样

    def test_wrapper_with_stray_file_aborts(self, tmp_path):
        """QIMO/ 里同时有 说明书.pdf 和 QIMO/{工程} → 放弃，原样保留。"""
        wrap = tmp_path / "QIMO"
        wrap.mkdir()
        (wrap / "说明书.pdf").write_text("x", encoding="utf-8")
        _make_project_root(wrap / "QIMO")
        r = SN.flatten(tmp_path)
        assert r.flattened is False
        assert r.skip_cause == NormalizeResult._CAUSE_AMBIGUOUS
        # 目录树原样未动
        assert (wrap / "说明书.pdf").exists()
        assert (wrap / "QIMO" / "Makefile").exists()
        assert not (tmp_path / "Makefile").exists()

    def test_multiple_siblings_at_top_aborts(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        r = SN.flatten(tmp_path)
        assert r.flattened is False
        assert r.skip_cause == NormalizeResult._CAUSE_AMBIGUOUS

    def test_stray_file_at_top_aborts_as_ambiguous(self, tmp_path):
        """顶层若有任何与包装层并列的散落文件（移动将造成不确定）→ 放弃，原样保留。

        注：这是「覆盖」场景在实践中的真正拦截点——STEP2 的纯单子链不变量保证，
        任何会在顶层造成同名覆盖的条目，早在 depth-1 就被判 ambiguous_siblings。
        故代码里的 _CAUSE_COLLISION 守卫属 defense-in-depth（几乎不可达），此处不单测。
        """
        (tmp_path / "README.txt").write_text("既存", encoding="utf-8")  # 非标记散落文件
        wrap = tmp_path / "wrap"
        _make_project_root(wrap)
        r = SN.flatten(tmp_path)
        assert r.flattened is False
        assert r.skip_cause == NormalizeResult._CAUSE_AMBIGUOUS
        # 既存文件未被移动/覆盖
        assert (tmp_path / "README.txt").read_text(encoding="utf-8") == "既存"
        assert (wrap / "Makefile").exists()               # 工程原样

    def test_no_project_root_aborts(self, tmp_path):
        (tmp_path / "wrap").mkdir()
        (tmp_path / "wrap" / "deep").mkdir()
        r = SN.flatten(tmp_path)
        assert r.flattened is False
        assert r.skip_cause == NormalizeResult._CAUSE_NO_PROJECT

    def test_chain_single_child_is_file_aborts(self, tmp_path):
        """唯一子是文件（如误把 notes.txt 当包装层）→ 放弃。"""
        (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
        r = SN.flatten(tmp_path)
        assert r.flattened is False
        assert r.skip_cause == NormalizeResult._CAUSE_EXTRA_FILES
        assert (tmp_path / "notes.txt").exists()

    def test_idempotent(self, tmp_path):
        """第二次运行 = already_flat。"""
        _make_project_root(tmp_path / "QIMO" / "QIMO")
        assert SN.flatten(tmp_path).flattened is True
        r2 = SN.flatten(tmp_path)
        assert r2.flattened is False
        assert r2.skip_cause == NormalizeResult._CAUSE_ALREADY_FLAT
        assert (tmp_path / "Makefile").is_file()

    def test_max_depth_cap_no_infinite_loop(self, tmp_path):
        """10 层链（无工程根）→ no_project_root，且不无限循环。"""
        d = tmp_path
        for _ in range(10):
            d = d / "d"
        d.mkdir(parents=True)
        (d / "Makefile").write_text("x", encoding="utf-8")  # 在第 10 层才有标记
        # MAX_DEPTH=8，第 10 层超出 → 视为未找到
        r = SN.flatten(tmp_path)
        assert r.flattened is False
        assert r.skip_cause == NormalizeResult._CAUSE_NO_PROJECT

    def test_nonexistent_dir(self, tmp_path):
        r = SN.flatten(tmp_path / "nope")
        assert r.flattened is False
        assert r.skip_cause == NormalizeResult._CAUSE_PERMISSION

    @pytest.mark.skipif(
        not hasattr(os, "symlink") or os.name == "nt",
        reason="符号链接测试在受限的 Windows 环境跳过",
    )
    def test_symlink_in_chain_aborts(self, tmp_path):
        """链中存在 symlink → 放弃。"""
        wrap = tmp_path / "wrap"
        wrap.mkdir()
        # 在包装层里放一个 symlink（指向任意处）
        try:
            os.symlink(tmp_path, wrap / "link")
        except (PermissionError, OSError):
            pytest.skip("无法创建符号链接（权限不足）")
        _make_project_root(wrap / "real" / "real")
        # wrap 现含 {link, real/} → 实际是 ambiguous，但若构造为单 symlink 子链也应被判 symlink
        r = SN.flatten(tmp_path)
        assert r.flattened is False
