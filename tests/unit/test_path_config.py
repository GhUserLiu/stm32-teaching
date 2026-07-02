# -*- coding: utf-8 -*-
"""
统一路径配置单元测试
Path Configuration Unit Tests

验证 ExperimentPaths 的目录约定，以及与 auto_grading 后端的一致性。
"""

from pathlib import Path

from tools.common.path_config import (
    ExperimentPaths,
    TeachingPaths,
    get_experiment_paths,
    get_teaching_paths,
)


class TestExperimentPaths:
    def test_subdirs_under_results(self, tmp_path):
        paths = ExperimentPaths(experiment_dir=tmp_path)
        assert paths.submissions_dir == tmp_path / "submissions"
        assert paths.processed_dir == tmp_path / "processed"
        assert paths.results_dir == tmp_path / "results"
        # 四类产物目录都在 results 下
        for d in (paths.reports_dir, paths.feedback_dir,
                  paths.grading_dir, paths.plagiarism_dir):
            assert d.parent == paths.results_dir

    def test_create_all(self, tmp_path):
        paths = ExperimentPaths(experiment_dir=tmp_path)
        paths.create_all()
        for d in (paths.submissions_dir, paths.processed_dir,
                  paths.results_dir, paths.grading_dir,
                  paths.plagiarism_dir, paths.feedback_dir,
                  paths.reports_dir):
            assert d.exists()

    def test_teaching_paths_hierarchy(self, tmp_path):
        tp = TeachingPaths(project_root=tmp_path)
        assert tp.teaching_data_dir == tmp_path / "data" / "teaching"
        exp = tp.get_experiment_paths("2026-春季", "汽服2302B班", "07-car-gear")
        assert exp.experiment_dir == (
            tmp_path / "data" / "teaching" / "2026-春季" / "汽服2302B班" / "07-car-gear"
        )


class TestAutoGradingPathUnification:
    """auto_grading 后端的输出路径必须落在 path_config 的 grading_dir。"""

    def test_get_output_dir_is_grading_dir(self, tmp_path):
        from tools.auto_grading.config import AutoGradingConfig

        cfg = AutoGradingConfig(project_root=tmp_path, semester="2026-春季")
        out = cfg.get_output_dir("汽服2302B班", "07-car-gear")

        expected = (
            tmp_path / "data" / "teaching" / "2026-春季"
            / "汽服2302B班" / "07-car-gear" / "results" / "grading"
        )
        assert out == expected

    def test_semester_field_default(self):
        from tools.auto_grading.config import AutoGradingConfig

        cfg = AutoGradingConfig()
        assert cfg.semester == "2026-春季"
