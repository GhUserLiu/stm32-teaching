# -*- coding: utf-8 -*-
"""
GUI 模块导入冒烟测试
GUI Import Smoke Tests

确保教学管理 GUI 重构后各模块可正常导入（offscreen 模式，不弹窗）。
守护查重/反馈面板接线与 path_helper 不出现导入期错误。
"""

import os
import pytest

# 必须 offscreen，否则无显示环境会失败
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_path_helper_resolves():
    from tools.teaching_management_gui.path_helper import (
        grading_dir,
        plagiarism_dir,
        feedback_dir,
    )
    g = grading_dir("汽服2302B班", "07-car-gear")
    p = plagiarism_dir("汽服2302B班", "07-car-gear")
    f = feedback_dir("汽服2302B班", "07-car-gear")
    assert g.name == "grading"
    assert p.name == "plagiarism"
    assert f.name == "feedback"
    # 三者都在同一个 results 目录下
    assert g.parent == p.parent == f.parent


def test_import_panels():
    from tools.teaching_management_gui.ui.panels.data_source_panel import DataSourcePanel
    from tools.teaching_management_gui.ui.panels.plagiarism_panel import PlagiarismPanel
    from tools.teaching_management_gui.ui.panels.feedback_panel import FeedbackPanel
    from tools.teaching_management_gui.ui.panels.grading_panel import GradingPanel
    from tools.teaching_management_gui.ui.class_report_dialog import ClassReportDialog
    from tools.teaching_management_gui.ui.main_window import MainWindow
    assert DataSourcePanel is not None
    assert PlagiarismPanel is not None
    assert FeedbackPanel is not None
    assert GradingPanel is not None


def test_data_source_shared_and_parse():
    from tools.teaching_management_gui.data_source import shared, ClassEntry
    from tools.teaching_management_gui.path_helper import (
        parse_class_experiment_from_zip, match_experiment,
    )
    ds = shared()
    ds.clear()
    assert ds.entries() == []
    cn, exp = parse_class_experiment_from_zip(
        "汽服2301B班-_实验报告（第七次实验 汽车档位模拟器设计）(附件) (2)")
    assert cn == "汽服2301B班" and exp is None
    assert match_experiment("第七次实验 汽车档位模拟器设计") == "07-car-gear"
    ds.set_entries([ClassEntry("汽服2301B班", "07-car-gear", "/tmp/a.zip")])
    assert len(ds.entries()) == 1


def test_import_workers():
    from tools.teaching_management_gui.workers.grading_worker import GradingWorker
    from tools.teaching_management_gui.workers.plagiarism_worker import (
        PlagiarismWorker,
        METHOD_MAP,
    )
    from tools.plagiarism.core.detector import SimilarityMethod
    assert GradingWorker is not None
    assert PlagiarismWorker is not None
    # 方法映射覆盖四种 UI 选项
    assert len(METHOD_MAP) == 4
    assert METHOD_MAP["综合检测（推荐）"] == SimilarityMethod.HYBRID


def test_auto_grading_all_exports():
    """__all__ 修复后，被旧重复定义遮蔽的类应可正常导入。"""
    from tools.auto_grading import (
        AutoGradingFacade,
        SubmissionOrganizer,
        OrganizationResult,
        StudentInfo,
        CategoryScore,
    )
    for cls in (AutoGradingFacade, SubmissionOrganizer,
                OrganizationResult, StudentInfo, CategoryScore):
        assert cls is not None
