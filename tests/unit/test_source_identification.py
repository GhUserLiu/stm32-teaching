#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
回归测试：源码识别链（submission_organizer 的核心评分前置判定）

锁定 SubmissionOrganizer 三个脆点方法的【当前实际行为】，给后续
拆 grade_submission / 改阈值 / 改正则装安全网：

  ① _looks_like_source_project  —— zip 内容像不像源码工程（决定是否被
     _unwrap 当作包装层 unlink 掉，误判会毁掉真源码导致全源码类 0 分）
  ② _find_source_archive        —— 多归档时的 tie-break（不能只按体积）
  ③ _unwrap_nested_zips         —— 嵌套套娃 zip 能否解开让报告露出

这是 characterization / 回归测试：断言对齐【当前实际输出】，不是理想行为。
"""

import io
import zipfile
from pathlib import Path

import pytest

from tools.auto_grading.submission_organizer import SubmissionOrganizer


# ---------------------------------------------------------------------------
# 公共夹具：tmp_path 构造 organizer（base_dir 仅在 __init__ 存了路径，不被实际用到）
# ---------------------------------------------------------------------------
@pytest.fixture
def organizer(tmp_path):
    return SubmissionOrganizer(tmp_path)


def _make_zip(zip_path: Path, entries: dict):
    """用 zipfile 现造一个 zip。entries: {name_in_zip: bytes_or_str}。

    name 以 '/' 结尾表示目录条目（写空内容）。
    """
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            if name.endswith("/"):
                zf.writestr(name, "")
            elif isinstance(data, str):
                zf.writestr(name, data)
            else:
                zf.writestr(name, data)


# ===========================================================================
# ① _looks_like_source_project
# ===========================================================================
class TestLooksLikeSourceProject:
    """_looks_like_source_project(self, zip_path: Path) -> bool。

    规则（当前实现）：窥视 zip 内部条目——
      - 含报告（扩展名 .docx/.doc/.pdf/.wps 或文件名含「报告」）→ 返回 False（当作包装层）
      - 否则命中源码特征（.c/.h/.cpp/.hpp/.cxx/.s/.ioc/.uvprojx/.uvproj，
        或 Makefile / .mxproject / /core/ / /drivers/）→ 返回 True
      - 读不出 zip（非 zip / 损坏）→ 返回 False
    """

    SOURCE_MARKER_CASES = [
        (".c 文件", {"main.c": "int main(){}"}),
        (".h 文件", {"stm32f4xx.h": "#define X"}),
        (".cpp 文件", {"app.cpp": "void f(){}"}),
        (".hpp 文件", {"a.hpp": "x"}),
        (".cxx 文件", {"b.cxx": "x"}),
        (".s 汇编", {"startup.s": ".syntax unified"}),
        (".ioc 文件", {"proj.ioc": "Mcu.Name=STM32"}),
        (".uvprojx 文件", {"proj.uvprojx": "<Project>"}),
        (".uvproj 文件", {"proj.uvproj": "<Project>"}),
        ("Makefile", {"proj/Makefile": "all:\n\techo hi"}),
        (".mxproject", {"proj/.mxproject": "[PreviousGenFiles]"}),
        ("/core/ 路径", {"proj/Core/main.c": "x"}),
        ("/drivers/ 路径", {"proj/Drivers/STM32F4xx_HAL_Driver/stm32f4xx_hal.c": "x"}),
    ]

    @pytest.mark.parametrize("label,entries", SOURCE_MARKER_CASES)
    def test_source_markers_return_true(self, organizer, tmp_path, label, entries):
        """命中任一源码特征且【不含报告】→ True。"""
        zp = tmp_path / f"case_{label.replace('/', '_').replace(' ', '_')}.zip"
        _make_zip(zp, entries)
        assert organizer._looks_like_source_project(zp) is True

    WRAPPER_CASES = [
        ("报告.docx + .c", {"main.c": "x", "报告.docx": "y"}),
        ("纯 .docx", {"report.docx": "y"}),
        ("纯 .doc", {"report.doc": "y"}),
        ("纯 .pdf", {"report.pdf": "y"}),
        ("纯 .wps", {"report.wps": "y"}),
        ("文件名含「报告」无扩展名标记", {"实验报告.txt": "y"}),
        ("文件名含「报告」+ .c（含源码但有报告）", {"main.c": "x", "我的报告.txt": "y"}),
    ]

    @pytest.mark.parametrize("label,entries", WRAPPER_CASES)
    def test_report_present_returns_false(self, organizer, tmp_path, label, entries):
        """含报告（扩展名或文件名含「报告」）→ False（包装层）。"""
        zp = tmp_path / f"wrap_{hash(label) & 0xFFFFFF:x}.zip"
        _make_zip(zp, entries)
        assert organizer._looks_like_source_project(zp) is False

    def test_only_directory_entries_returns_false(self, organizer, tmp_path):
        """zip 里只有目录条目、无任何文件 → 既无报告也无源码标记 → False。"""
        zp = tmp_path / "dironly.zip"
        _make_zip(zp, {"Core/": "", "Drivers/": ""})
        assert organizer._looks_like_source_project(zp) is False

    def test_empty_zip_returns_false(self, organizer, tmp_path):
        """完全空 zip → False。"""
        zp = tmp_path / "empty.zip"
        with zipfile.ZipFile(zp, "w"):
            pass
        assert organizer._looks_like_source_project(zp) is False

    def test_non_zip_file_returns_false(self, organizer, tmp_path):
        """非 zip 文件（无法打开为 ZipFile）→ False。"""
        zp = tmp_path / "notazip.txt"
        zp.write_text("hello")
        assert organizer._looks_like_source_project(zp) is False

    def test_unrelated_files_returns_false(self, organizer, tmp_path):
        """无报告也无源码标记（如纯 txt）→ False。"""
        zp = tmp_path / "misc.zip"
        _make_zip(zp, {"readme.txt": "x", "data.csv": "1,2,3"})
        assert organizer._looks_like_source_project(zp) is False

    def test_report_extension_is_case_insensitive(self, organizer, tmp_path):
        """报告扩展名判断走 .lower() → 大写 .DOCX 仍判为报告 → False。"""
        zp = tmp_path / "upper.zip"
        _make_zip(zp, {"main.c": "x", "R.DOCX": "y"})
        assert organizer._looks_like_source_project(zp) is False

    def test_makefile_match_requires_suffix_only(self, organizer, tmp_path):
        """Makefile 判断是 endswith('makefile')（小写比较），
        裸名 Makefile 命中；锁此行为。"""
        zp = tmp_path / "mk.zip"
        _make_zip(zp, {"Makefile": "all:"})
        assert organizer._looks_like_source_project(zp) is True


# ===========================================================================
# ② _find_source_archive —— 多归档 tie-break
# ===========================================================================
class TestFindSourceArchive:
    """_find_source_archive(self, directory: Path) -> Optional[Tuple[Path, str, Dict]]。

    返回三元组 (path, kind, info)：
      - kind ∈ {'zip', '7z'}（仅按后缀判定，不读内容）
      - info = {'multiple_archives': bool, 'chosen': str(name), 'others': [name,...]}
      - 找不到返回 None

    tie-break 顺序（当前实现）：
      1) 命名优先（源代码/源码/code/project/工程 / 源代码*.7z 等命名模式）—— 一旦
         命中立即返回，不再窥视内容；
      2) 否则用 _looks_like_source_project 过滤出"像工程"的归档；都没有则全部作候选；
      3) 在候选里按 (非垃圾命名优先, 体积最大) 排序取首个。
         垃圾命名关键词：删除/delete/废弃/不要/旧/old/备份/backup。
    """

    def test_no_archive_returns_none(self, organizer, tmp_path):
        (tmp_path / "readme.txt").write_text("hi")
        assert organizer._find_source_archive(tmp_path) is None

    def test_single_archive_kind_and_info(self, organizer, tmp_path):
        """单个 zip：multiple_archives=False，others=[]。"""
        zp = tmp_path / "a.zip"
        _make_zip(zp, {"main.c": "int main(){}"})
        result = organizer._find_source_archive(tmp_path)
        assert result is not None
        path, kind, info = result
        assert path.name == "a.zip"
        assert kind == "zip"
        assert info == {
            "multiple_archives": False,
            "chosen": "a.zip",
            "others": [],
        }

    def test_multi_archive_picks_real_project_over_junk_big(
        self, organizer, tmp_path
    ):
        """审计点名：不能只按体积。

        构造「压缩后体积大、命名含「删除」、无源码标记」vs「较小但有 .c+Makefile（像工程）」。
        当前 tie-break：project_archives=[较小的]，垃圾归档不在候选 → 选较小的。
        （即使把垃圾算进候选，垃圾 key=0 也会排在 key=1 之后，结论一致。）
        """
        # 垃圾包用高熵随机字节撑大体积（避免 DEFLATE 把重复 "X" 压成更小），
        # 确保 junk 的【压缩后体积】确实大于 good，从而真正考验"不按体积取大"。
        import os as _os
        junk = tmp_path / "期末作业需要删除.zip"          # 命中「删除」垃圾词
        _make_zip(junk, {"pad.bin": _os.urandom(8000)})   # 体积大，但无源码标记

        good = tmp_path / "期末作业.zip"                   # 非垃圾命名 + 像工程
        _make_zip(good, {"main.c": "int main(){}", "Makefile": "all:"})

        result = organizer._find_source_archive(tmp_path)
        path, kind, info = result
        # 锁：选较小的「真工程」归档，不选大垃圾
        assert path.name == "期末作业.zip"
        assert kind == "zip"
        assert info["multiple_archives"] is True
        assert info["chosen"] == "期末作业.zip"
        assert "期末作业需要删除.zip" in info["others"]
        # 锁实际尺寸关系：good 比 junk 小（确保不是按体积取大）
        assert good.stat().st_size < junk.stat().st_size

    def test_multi_archive_both_like_project_non_junk_picks_largest(
        self, organizer, tmp_path
    ):
        """两个都像工程、都非垃圾 → tie-break 退化为体积最大。

        large(8000B) vs small(100B)，均含 .c。选 larger。
        """
        large = tmp_path / "projectA.zip"
        _make_zip(large, {"main.c": "Y" * 8000})
        small = tmp_path / "projectB.zip"
        _make_zip(small, {"main.c": "Z" * 100})
        result = organizer._find_source_archive(tmp_path)
        path, _kind, info = result
        assert path.name == "projectA.zip"
        assert info["multiple_archives"] is True
        assert "projectB.zip" in info["others"]

    def test_multi_archive_neither_like_project_junk_keyword_drops_to_smallest(
        self, organizer, tmp_path
    ):
        """都不像工程 → 全部作候选 → 非垃圾优先 + 体积。

        构造一个非垃圾(中)、一个垃圾(大) → 应选非垃圾(中)。
        """
        non_junk = tmp_path / "homework.zip"        # 非垃圾，无源码标记
        _make_zip(non_junk, {"readme.txt": "A" * 1500})
        junk = tmp_path / "homework_old_backup.zip"  # 命中 old+backup
        _make_zip(junk, {"readme.txt": "B" * 5000})
        result = organizer._find_source_archive(tmp_path)
        path, _kind, info = result
        # 非垃圾优先，即使体积更小
        assert path.name == "homework.zip"
        assert "homework_old_backup.zip" in info["others"]

    def test_multi_archive_both_like_project_junk_keyword_drops_to_smaller(
        self, organizer, tmp_path
    ):
        """两层闸门叠加：候选【都已通过内容判定(都像工程)】时，垃圾命名再筛一轮。

        构造「像工程且非垃圾且体积较小」vs「像工程且命中「删除」且体积更大」。
        当前 tie-break：project_archives=[两者]（都像工程），再按 _archive_score 的
        (非垃圾, 体积) 排序 → 非垃圾 key=1 > 垃圾 key=0 → 选【较小但非垃圾】的那一个。

        与 test_multi_archive_picks_real_project_over_junk_big 互补：那个用例靠内容判定
        把垃圾踢出候选；本用例两者都通过内容判定，纯粹靠垃圾词 tie-break 胜出——
        单独锁住这层交互，避免有人把 _archive_score 的 junk 维度删掉后只测内容过滤仍绿。
        """
        good = tmp_path / "proj_real.zip"          # 像工程 + 非垃圾 + 较小
        _make_zip(good, {"main.c": "x"})           # 真小体积
        # 命中「删除」垃圾词；用 urandom 撑大体积，确保【比 good 大】却仍落选
        import os as _os
        junk = tmp_path / ("proj_" + "删除" + ".zip")
        _make_zip(junk, {"main.c": "x", "pad.bin": _os.urandom(8000)})

        # 前置断言：两个都像工程、junk 确实更大（否则没考验到体积维度）
        assert organizer._looks_like_source_project(good) is True
        assert organizer._looks_like_source_project(junk) is True
        assert junk.stat().st_size > good.stat().st_size

        result = organizer._find_source_archive(tmp_path)
        path, _kind, info = result
        # 锁：选较小且非垃圾的工程，而非较大但命垃圾词的工程
        assert path.name == "proj_real.zip"
        assert info["multiple_archives"] is True
        assert "proj_删除.zip" in info["others"]

    def test_named_pattern_priority_overlooks_content(self, organizer, tmp_path):
        """命名优先级【高于】内容判定。

        「源代码.zip」只含 readme.txt（不像工程），而「big.zip」含 .c+Makefile（像工程）。
        当前实现：命名模式 '*源代码*.zip' 先命中 → 直接返回「源代码.zip」。
        这是 tie-break 的第一道闸门，锁此行为（见 notes：可能让"名实不符"的归档被选中）。
        """
        named = tmp_path / "23071140101-张三-源代码.zip"
        _make_zip(named, {"readme.txt": "no source here"})   # 不像工程
        real = tmp_path / "big.zip"
        _make_zip(real, {"main.c": "int main(){}", "Makefile": "all:"})
        result = organizer._find_source_archive(tmp_path)
        path, _kind, info = result
        assert path.name == "23071140101-张三-源代码.zip"
        assert info["chosen"] == "23071140101-张三-源代码.zip"
        assert "big.zip" in info["others"]

    def test_7z_kind_label_by_suffix(self, organizer, tmp_path):
        """kind 字段仅按后缀判定（'.7z' → '7z'），不验证内容是否真为 7z。"""
        seven = tmp_path / "src.7z"
        # 不写真 7z；rglob('*.7z') 仍能捡到，kind 按 suffix 判 '7z'
        seven.write_bytes(b"not a real 7z payload")
        result = organizer._find_source_archive(tmp_path)
        path, kind, info = result
        assert path.name == "src.7z"
        assert kind == "7z"
        assert info == {
            "multiple_archives": False,
            "chosen": "src.7z",
            "others": [],
        }

    def test_named_source_7z_pattern(self, organizer, tmp_path):
        """命名模式含 '*源代码*.7z' —— 该 .7z 即使是空壳也应被命名命中。"""
        named = tmp_path / "学号-姓名-源代码.7z"
        named.write_bytes(b"fake 7z")
        other = tmp_path / "其他.zip"
        _make_zip(other, {"main.c": "int main(){}", "Makefile": "all:"})
        result = organizer._find_source_archive(tmp_path)
        path, kind, info = result
        # 命名模式在 named 列表里顺序：*源代码*.7z 排在其它 zip 兜底之前 → 选 .7z
        assert path.name == "学号-姓名-源代码.7z"
        assert kind == "7z"

    def test_recursive_search_finds_nested_archive(self, organizer, tmp_path):
        """rglob 递归查找 —— 经 _unwrap 产生的 __unwrapped/ 子目录里的归档也能找到。"""
        nested_dir = tmp_path / "学号-姓名__unwrapped"
        nested_dir.mkdir()
        zp = nested_dir / "源码.zip"
        _make_zip(zp, {"main.c": "x", "Makefile": "all:"})
        result = organizer._find_source_archive(tmp_path)
        path, kind, info = result
        assert path.name == "源码.zip"
        assert kind == "zip"
        assert info["multiple_archives"] is False


# ===========================================================================
# ③ _unwrap_nested_zips
# ===========================================================================
class TestUnwrapNestedZips:
    """_unwrap_nested_zips(self, directory: Path, max_depth=5) -> None。

    行为：逐层解开"包装层" zip，直到目录里出现报告（_find_report_file 找到 .docx/.doc/.wps）。
      - 含报告 → 立即返回（不拆）；
      - 跳过命名像源码包的 zip（源代码/工程/code/project/source）和内容像工程的 zip
        （_looks_like_source_project）—— 绝不 unlink 真源码；
      - 每解一层把包装 zip 提取到 <stem>__unwrapped/ 并 wrapper.unlink()。
    """

    def test_wrapper_zip_with_report_is_unwrapped_and_deleted(
        self, organizer, tmp_path
    ):
        """包装层 zip（内含 report.docx，无源码标记）被解开并 unlink。"""
        wrapper = tmp_path / "学号-姓名-期末.zip"
        _make_zip(wrapper, {"班级姓名.docx": "REPORT"})

        organizer._unwrap_nested_zips(tmp_path)

        # 报告露出 → 原包装被删
        assert not wrapper.exists()
        uw = tmp_path / "学号-姓名-期末__unwrapped"
        assert uw.is_dir()
        assert (uw / "班级姓名.docx").exists()

    def test_report_already_present_means_no_unwrap(self, organizer, tmp_path):
        """目录里已有报告 → 立即返回，不去动任何 zip。"""
        # 先放报告
        (tmp_path / "report.docx").write_bytes(b"existing report")
        # 再放一个"会触发 unwrap 的包装 zip"（但因为有报告，不应被拆）
        wrapper = tmp_path / "outer.zip"
        _make_zip(wrapper, {"inner.docx": "x"})

        organizer._unwrap_nested_zips(tmp_path)

        assert wrapper.exists()  # 没被 unlink
        assert not (tmp_path / "outer__unwrapped").exists()

    def test_source_named_zip_not_unwrapped(self, organizer, tmp_path):
        """命名像源码包（含「源代码」）的 zip 即使无报告也不被当作包装层。"""
        src = tmp_path / "学号-姓名-源代码.zip"
        _make_zip(src, {"main.c": "x", "Makefile": "all:"})  # 像工程
        organizer._unwrap_nested_zips(tmp_path)
        # 源码包保留
        assert src.exists()
        assert not (tmp_path / "学号-姓名-源代码__unwrapped").exists()

    def test_source_named_zip_without_project_content_still_preserved(
        self, organizer, tmp_path
    ):
        """命名像源码包（含「源代码」）但内容【不像工程】（无 .c/Makefile）仍被保留。

        与 test_source_named_zip_not_unwrapped 互补：那个用例的 zip 同时含 .c+Makefile，
        故同时命中【命名】和【内容】两道闸门——删掉命名判定 (_looks_like_source_archive)
        测试仍会绿（内容判定兜住）。本用例让内容判定【失效】（仅 readme.txt），
        迫使保留行为只能依赖命名判定 _looks_like_source_archive，单独锁住这层闸门。
        """
        # 内容侧明确不像工程
        # 源代码命名 + 不含任何源码标记
        src = tmp_path / "23071140101-张三-源代码.zip"
        _make_zip(src, {"readme.txt": "just a readme, no .c/.h/Makefile"})
        # 前置断言：内容判定确为 False（确认本用例不被内容闸门兜住）
        assert organizer._looks_like_source_project(src) is False

        organizer._unwrap_nested_zips(tmp_path)

        # 仅靠命名判定被保留 → 没被当包装层 unlink
        assert src.exists()
        assert not (tmp_path / "23071140101-张三-源代码__unwrapped").exists()

    def test_source_project_content_zip_not_unwrapped(self, organizer, tmp_path):
        """虽未命中源码命名，但 zip 内容像工程（.c+Makefile）→ 不当包装层。"""
        proj = tmp_path / "anything.zip"  # 命名中性
        _make_zip(proj, {"main.c": "x", "Makefile": "all:"})
        organizer._unwrap_nested_zips(tmp_path)
        assert proj.exists()
        assert not (tmp_path / "anything__unwrapped").exists()

    def test_two_layer_wrapper_unwrapped(self, organizer, tmp_path):
        """两层包装 zip 套娃，最里层含报告 → 全部解开，报告落到磁盘。"""
        # 最内层：报告
        inner_buf = io.BytesIO()
        with zipfile.ZipFile(inner_buf, "w") as zf:
            zf.writestr("班级姓名.docx", "REPORT")
        # 中间层：包住最内层
        mid_buf = io.BytesIO()
        with zipfile.ZipFile(mid_buf, "w") as zf:
            zf.writestr("inner.zip", inner_buf.getvalue())
        # 外层（落在 tmp_path）
        outer = tmp_path / "学号-姓名-期末综合项目.zip"
        with zipfile.ZipFile(outer, "w") as zf:
            zf.writestr("mid.zip", mid_buf.getvalue())

        organizer._unwrap_nested_zips(tmp_path)

        # 应该能找到报告（递归解到底）
        reports = list(tmp_path.rglob("*.docx"))
        assert reports, "嵌套套娃解开后应能找到 .docx"
        # 外层包装已被 unlink
        assert not outer.exists()

    def test_unwrap_no_zips_is_noop(self, organizer, tmp_path):
        """目录无 zip 也无报告 → 安全无操作（不抛异常）。"""
        (tmp_path / "readme.txt").write_text("hi")
        organizer._unwrap_nested_zips(tmp_path)  # 不应抛
        assert (tmp_path / "readme.txt").exists()

    def test_unwrap_respects_max_depth_bound(self, organizer, tmp_path):
        """max_depth 闸门：超过 max_depth 层的套娃【不会】无限递归到底。

        构造 2 层包装链（outer.zip → inner.zip → 班级姓名.docx），传 max_depth=1。
        当前实现 for-loop 固定循环 max_depth 次 → max_depth=1 时只解 1 层：
        outer 被解成 outer__unwrapped/inner.zip 后循环即结束，inner.zip 未再被解
        → 报告仍埋在 inner.zip 里，rglob('*.docx') 找不到。
        锁此有界行为，防有人把 for 改成 while True（栈溢出/死循环）而无测试兜住。
        """
        # 2 层套娃：内层 inner.zip 含报告
        inner_buf = io.BytesIO()
        with zipfile.ZipFile(inner_buf, "w") as zf:
            zf.writestr("班级姓名.docx", "REPORT")
        outer = tmp_path / "outer.zip"
        with zipfile.ZipFile(outer, "w") as zf:
            zf.writestr("inner.zip", inner_buf.getvalue())

        organizer._unwrap_nested_zips(tmp_path, max_depth=1)  # 只允许解 1 层

        # max_depth=1：inner.zip 仍在，报告没露出
        reports = list(tmp_path.rglob("*.docx"))
        assert reports == [], "max_depth=1 时 2 层套娃的报告不应露出（锁有界递归）"
        # 关键：不抛异常（有界，不死循环/不栈溢出）

    def test_unwrap_max_depth_two_reaches_report(self, organizer, tmp_path):
        """与上一条互补：同样的 2 层套娃，max_depth=2 时应能解到底、报告露出。

        锁住 max_depth 维度的【正常可达】行为，避免上一条的'有界'断言被退化成
        '永远找不到报告'的恒真（确认只要给够深度就能解开）。
        """
        inner_buf = io.BytesIO()
        with zipfile.ZipFile(inner_buf, "w") as zf:
            zf.writestr("班级姓名.docx", "REPORT")
        outer = tmp_path / "outer.zip"
        with zipfile.ZipFile(outer, "w") as zf:
            zf.writestr("inner.zip", inner_buf.getvalue())

        organizer._unwrap_nested_zips(tmp_path, max_depth=2)

        reports = list(tmp_path.rglob("*.docx"))
        assert reports, "max_depth=2 时 2 层套娃应解开露出报告"
        assert not outer.exists(), "最外层包装应被 unlink"
