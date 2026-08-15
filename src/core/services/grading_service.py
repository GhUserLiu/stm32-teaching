#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Qt-free grading pipeline orchestration -- the P2 services-layer extraction.

Source of truth: extracted verbatim from
``tools/teaching_management_gui/workers/grading_worker.py``
(``GradingWorker.run`` + ``ObservableFacade.run_full_pipeline`` + ``_LogTee``),
so the pipeline orchestration lives in the services layer instead of the GUI
package. The GUI worker now only adapts Qt signals onto ``ProgressCallbacks``;
``ObservableFacade`` remains in the GUI module as a thin compatibility adapter
(existing tests inject stub facades via ``object.__new__``).

Behavior contract (must not drift):
  * identical call sequence into ``tools.auto_grading`` -- organizer ->
    processor (expand_team=True) -> per-experiment engine/rubric -> roster
    identity check -> dedupe_team_members -> reports;
  * identical log strings (they land in results/grading/batch_run.log);
  * identical checkpoint/resume semantics via ``tools.auto_grading.batch_checkpoint``;
  * identical cancellation semantics (poll between students, inject a
    ``threading.Event`` into the engine's build_checker, drop partial reports).

Also provides ``build_auto_grading_config``: the bridge from the unified
pydantic settings (P1 ``schemas`` / ``config/base.yaml``) onto the legacy
``AutoGradingConfig`` dataclass. Values are verified 1:1 against the legacy
defaults (P1 parity check), so this is wiring, not a behavior change.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Set, Tuple

from tools.auto_grading import (
    AutoGradingFacade,
    AutoGradingConfig,
    batch_checkpoint,
)
from tools.auto_grading.facade import PipelineResult


# ----------------------------------------------------------------- config bridge


def build_auto_grading_config(
    semester: Optional[str] = None,
    settings=None,
    project_root: Optional[Path] = None,
) -> AutoGradingConfig:
    """Bridge the unified pydantic settings onto the legacy dataclass config.

    ``project_root`` defaults to the repo root derived from the schemas
    package (instead of ``Path.cwd()``): same value in the normal
    launched-from-repo-root case, but robust when started elsewhere.
    """
    # Imported lazily so that tools-only consumers do not require pydantic.
    from schemas import get_settings
    from schemas.config import CONFIG_DIR
    from tools.auto_grading.config import (
        ProjectConfig,
        SecurityConfig,
        ToolchainConfig,
    )

    s = settings or get_settings()
    cfg = AutoGradingConfig(
        project_root=Path(project_root) if project_root else CONFIG_DIR.parent,
        semester=semester or s.teaching.semester,
    )

    t = s.grading.toolchain
    cfg.toolchain = ToolchainConfig(
        gcc_enabled=t.gcc_enabled,
        make_path=t.make_path,
        arm_none_eabi_prefix=t.arm_none_eabi_prefix,
        keil_enabled=t.keil_enabled,
        keil_uv4_path=t.keil_uv4_path,
        build_timeout=t.build_timeout,
    )
    p = s.grading.project
    cfg.project = ProjectConfig(
        allowed_projects=list(p.allowed_projects),
        project_types=dict(p.project_types),
    )
    sec = s.grading.security
    cfg.security = SecurityConfig(
        max_zip_size=sec.max_zip_size_mb * 1024 * 1024,   # MB -> bytes
        max_file_count=sec.max_file_count,
        allowed_extensions=list(sec.allowed_extensions),
        allow_absolute_paths=sec.allow_absolute_paths,
        allow_parent_references=sec.allow_parent_references,
    )
    return cfg


# -------------------------------------------------------------------- callbacks


@dataclass
class ProgressCallbacks:
    """Qt-free observation hooks.

    The GUI maps pyqtSignals onto these; tests inject plain lists/lambdas.
    All defaults are no-ops so a bare ``ProgressCallbacks()`` is valid.
    """

    stage_started: Callable[[str, str], None] = lambda stage_id, name: None
    stage_progress: Callable[[str, int, int], None] = (
        lambda stage_id, current, total: None)
    stage_completed: Callable[[str], None] = lambda stage_id: None
    log: Callable[[str], None] = lambda message: None
    is_cancelled: Callable[[], bool] = lambda: False
    cancel_event: Optional[threading.Event] = None


class _LogTee:
    """Tee the log stream into results/grading/batch_run.log (verbatim move).

    Wraps a signal-like object exposing ``.emit``; ``__call__`` is an alias
    so the service can treat it as a plain callable after rebinding.
    """

    def __init__(self, signal, log_path):
        self._signal = signal
        self._log_path = Path(log_path)

    def emit(self, message):
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {message}\n")
        except Exception:
            # 日志落盘失败绝不能影响批阅主流程
            pass
        self._signal.emit(message)

    __call__ = emit


class _LogSink:
    """Adapt a plain ``Callable[[str], None]`` onto the ``.emit`` interface."""

    def __init__(self, fn: Callable[[str], None]):
        self.emit = fn


# ----------------------------------------------------------------------- service


class GradingService:
    """Headless orchestrator for the 4-stage class grading pipeline.

    One instance per class run (mirrors the old per-class ``ObservableFacade``);
    ``run_batch`` creates a per-class instance internally, exactly like
    ``GradingWorker.run`` did.
    """

    def __init__(
        self,
        config: AutoGradingConfig,
        callbacks: Optional[ProgressCallbacks] = None,
        facade: Optional[AutoGradingFacade] = None,
    ):
        """
        Args:
            config: legacy dataclass config (bridge via build_auto_grading_config)
            callbacks: progress/log/cancel hooks; defaults are no-ops
            facade: injectable facade (tests pass stubs); None -> lazy creation
        """
        self.config = config
        self.cb = callbacks or ProgressCallbacks()
        self.facade = facade

    def _ensure_facade(self) -> AutoGradingFacade:
        if self.facade is None:
            self.facade = AutoGradingFacade(self.config)
        return self.facade

    # ------------------------------------------------------------- single class

    def run_class(
        self,
        class_zip: Path,
        class_name: str,
        experiment_id: str,
        skip_organization: bool = False,
        resume_completed_ids: Optional[Set[str]] = None,
    ) -> PipelineResult:
        """运行完整流水线（带进度回调）。

        Verbatim extraction of ObservableFacade.run_full_pipeline -- keep the
        step order, log strings and checkpoint writes byte-identical.
        """
        facade = self._ensure_facade()
        cb = self.cb
        log = cb.log   # rebound to a _LogTee below; always call as log(...)

        result = PipelineResult(
            class_name=class_name,
            experiment_id=experiment_id
        )

        log("=" * 70)
        log("自动化批阅系统")
        log("=" * 70)

        # 按实验 id 装载对应 rubric（与 facade.run_full_pipeline 一致）。
        # 否则 GUI 路径会一直用 AutoGradingFacade.__init__ 里默认的 rubric.json
        # （汽车档位标准），把综合项目等按错误标准评分。
        facade.engine = facade._make_engine(experiment_id)
        # 注入取消事件：让引擎内 build_checker 的 make 编译可被取消（命中即 kill 子进程）
        bc = getattr(facade.engine, "build_checker", None)
        if bc is not None and hasattr(bc, "set_cancel_event"):
            bc.set_cancel_event(cb.cancel_event)
        log(
            "rubric: " + str(
                getattr(facade.engine.rubric, 'get', lambda *a: None)(
                    'experiment_name', None)
                or facade.engine.rubric_path or '(默认)'))

        # 持久化日志：把本次运行的所有 log(...) 同时 tee 到
        # results/grading/batch_run.log（append，每行带时间戳；崩溃前已落盘，
        # 切走标签页/关窗都不丢）。失败不影响批阅。
        try:
            _log_path = facade.config.get_output_dir(class_name, experiment_id) / "batch_run.log"
            _log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(_log_path, "a", encoding="utf-8") as _hf:
                _hf.write(f"\n=== run started {datetime.now():%Y-%m-%d %H:%M:%S} "
                          f"| {class_name} / {experiment_id} ===\n")
            log = _LogTee(_LogSink(log), _log_path)
        except Exception:
            pass

        # 阶段1: 整理提交格式
        if not skip_organization:
            log("阶段1: 整理提交格式")
            cb.stage_started("organize", "整理提交")

            # 模拟进度（因为没有细粒度进度）
            cb.stage_progress("organize", 1, 10)
            org_result = facade.organizer.process_class_submission(
                class_zip,
                class_name,
                experiment_id
            )
            cb.stage_progress("organize", 10, 10)
            cb.stage_completed("organize")

            result.organization_result = org_result

            log(f"  成功: {org_result.successful}/{org_result.total_students}")

            if org_result.total_students == 0:
                log("警告: 没有找到学生提交")
                return result

            if cb.is_cancelled():
                return result
        else:
            log("阶段1: 跳过（已整理）")

        # 阶段2: 处理提交数据
        log("阶段2: 处理提交数据")
        cb.stage_started("process", "处理提交数据")
        cb.stage_progress("process", 1, 10)

        submissions = facade.processor.process_class_submissions(
            class_name,
            experiment_id,
            expand_team=True,   # 批阅按团队成员展开为每人一条；查重链路保持默认 False
        )

        cb.stage_progress("process", 10, 10)
        cb.stage_completed("process")

        result.total_submissions = len(submissions)
        log(f"  处理完成: {len(submissions)} 个提交")

        if not submissions:
            log("警告: 没有找到提交数据")
            return result

        # 阶段3: 批量评分（stage_id "analyze" 为 GUI 进度条约定，勿改名）
        log("阶段3: 批量评分")
        cb.stage_started("analyze", "评分中")

        grading_results = []
        failures = []  # per-student 评分异常收集（不再静默丢弃），供 GUI 展示
        total = len(submissions)

        # 断点续跑 checkpoint（Phase B）：每成功评一个学生就增量写缓存 + meta，
        # 崩溃/取消后下次「开始批阅」可检测到并跳过已完成者；批阅成功完成则清掉。
        _gdir = facade.config.get_output_dir(class_name, experiment_id)
        _resume_ids = set(resume_completed_ids or [])
        _meta = batch_checkpoint.new_meta(
            class_name, experiment_id, facade.config.semester, total)
        if _resume_ids:
            _meta["completed_ids"] = sorted(_resume_ids)
        else:
            batch_checkpoint.clear_checkpoint(_gdir)  # 全新开始：清掉上次残留
        batch_checkpoint.write_meta(_gdir, _meta)

        for i, submission in enumerate(submissions):
            if cb.is_cancelled():
                break

            log(f"评分 ({i+1}/{total}): {submission.student_id}-{submission.name}")
            cb.stage_progress("analyze", i + 1, total)

            # 续跑：该生已完成 → 复用缓存、不重评（缓存缺失/损坏则落到下方重评）
            if submission.student_id in _resume_ids:
                _cached = batch_checkpoint.load_result_cache(_gdir, submission.student_id)
                if _cached is not None:
                    log("  续跑：跳过（已完成，复用缓存）")
                    grading_results.append(_cached)
                    continue

            try:
                grading_result = facade.engine.grade_submission(submission)
            except Exception as e:
                # 单个提交异常不应中断整批：记录失败原因，其余继续（不再静默丢弃）
                log(f"  ⚠ 评分异常，已记入失败清单：{e}")
                failures.append({
                    'student_id': submission.student_id,
                    'name': submission.name,
                    'class_name': class_name,
                    'experiment_id': experiment_id,
                    'error': str(e),
                    'stage': 'analyze',
                })
                _meta["failed_ids"].append(submission.student_id)
                batch_checkpoint.write_meta(_gdir, _meta)
                continue
            grading_results.append(grading_result)
            # 增量写 checkpoint（崩溃前已落盘的部分下次可续跑）
            batch_checkpoint.write_result_cache(_gdir, grading_result)
            _meta["completed_ids"].append(submission.student_id)
            batch_checkpoint.write_meta(_gdir, _meta)

            log(f"  得分: {grading_result.total_score:.1f}/{grading_result.max_score:.1f} ({grading_result.grade})")

        cancelled = cb.is_cancelled()
        if not cancelled:
            cb.stage_progress("analyze", total, total)
            cb.stage_completed("analyze")

        # 小组按成员展开后，同一学生可能出现在多份上传报告中；按学号去重保留最高分。
        # 传 rubric：让 dedupe 按组真实人数校正组长加分（多组长平摊 / 无组长全员平摊）。
        # 花名册身份核验（re-key + 学号/姓名错误记0分）必须在去重之前：re-key 到真实学号后，
        # 撞号两人各落不同学号，不再被去重并掉（如 安晓童 210→211 不再撞 王倩倩 210）。
        # 函数内导入是有意为之：单测通过 monkeypatch 模块属性替换这两个函数，
        # 调用点导入才能取到补丁版本（勿提升到模块级）。
        from tools.auto_grading.grading_engine import dedupe_team_members
        try:
            from tools.auto_grading.roster_check import load_id_roster, validate_identities
            _cfg = facade.config
            _roster = load_id_roster(_cfg.teaching_dir / _cfg.semester)
            if _roster:
                grading_results = validate_identities(grading_results, _roster)
        except Exception as _e:
            log(f"  花名册核验跳过：{_e}")
        grading_results = dedupe_team_members(
            grading_results, rubric=getattr(facade.engine, 'rubric', None))

        result.grading_results = grading_results
        result.successful_graded = len(grading_results)
        result.failures = failures

        # 阶段4: 生成报告。取消则不落盘部分结果，避免与 grading_cancelled 信号不一致。
        if not cancelled:
            log("阶段4: 生成报告")
            cb.stage_started("report", "生成报告")
            cb.stage_progress("report", 1, 10)

            # completed_at 必须在 _save_reports 之前赋值，否则批阅汇总.json 里会是 null
            result.completed_at = datetime.now()
            class_report = None
            if grading_results:
                class_report = facade.engine.generate_class_report(grading_results)
                facade._save_reports(result, class_report)
                # 批阅成功完成 → 清除 checkpoint（保持 results/ 干净，下次全新开始）
                batch_checkpoint.clear_checkpoint(_gdir)
                log("  班级报告已生成")
                log("  个人报告已生成")
                cb.stage_progress("report", 10, 10)
            cb.stage_completed("report")

            log("=" * 70)
            log("批阅完成！")
            # 平均分/等级分布取自 generate_class_report（单一事实来源），避免与班级报告.json 不一致
            if class_report:
                log(f"平均分: {class_report['average_score']:.1f}")
                log(f"等级分布: {class_report['grade_distribution']}")
            log(f"完成时间: {result.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
            log(f"耗时: {(result.completed_at - result.started_at).total_seconds():.1f}秒")
        else:
            log("已取消，不生成报告")

        return result

    # ------------------------------------------------------------------- batch

    def run_batch(
        self,
        entries,
        resume: bool = False,
        facade_factory: Optional[Callable[[AutoGradingConfig], AutoGradingFacade]] = None,
    ) -> Tuple[list, list]:
        """遍历多个班级条目，合并所有 GradingResult 与失败清单。

        Verbatim extraction of GradingWorker.run's loop (Qt signal handling
        stays in the worker; cancelled/completed interpretation stays there).

        Args:
            entries: 具有 zip_path / class_name / experiment_id 属性的对象
                （GUI 的 data_source.ClassEntry 即满足）
            resume: True 时读取各班 checkpoint 的已完成学号集合并跳过
            facade_factory: 可注入的门面工厂（测试用桩）；默认每班新建
                AutoGradingFacade，与旧行为一致
        Returns:
            (all_results, all_failures)
        """
        factory = facade_factory or AutoGradingFacade
        cb = self.cb
        log = cb.log

        all_results = []
        all_failures = []   # per-student 评分失败（跨班级合并），供面板展示「⚠ N 人批阅失败」
        total = len(entries)
        log(f"开始批量批阅：共 {total} 个班级")

        for i, entry in enumerate(entries):
            if cb.is_cancelled():
                break
            zip_path = Path(entry.zip_path)
            log(f"({i + 1}/{total}) 班级 {entry.class_name} / 实验 {entry.experiment_id}")
            log(f"压缩包: {zip_path.name}")

            if not zip_path.exists():
                log(f"警告: 压缩包不存在，跳过: {zip_path}")
                cb.stage_progress("analyze", i + 1, total)
                continue

            # 每个班级一个 service 实例（per-class facade），复用 run_class
            service = GradingService(self.config, cb, facade=factory(self.config))
            # 续跑：读取该班级 checkpoint 的已完成学号集（Phase B）
            _resume_ids = None
            if resume:
                _gdir = self.config.get_output_dir(entry.class_name, entry.experiment_id)
                _meta = batch_checkpoint.load_meta(_gdir)
                if _meta and _meta.get("completed_ids"):
                    _resume_ids = set(_meta["completed_ids"])
                    log(f"  续跑：{entry.class_name} 跳过已完成 {len(_resume_ids)} 人")
            result = service.run_class(
                zip_path,
                entry.class_name,
                entry.experiment_id,
                False,
                resume_completed_ids=_resume_ids,
            )
            all_results.extend(result.grading_results)
            all_failures.extend(result.failures)
            cb.stage_progress("analyze", i + 1, total)

        return all_results, all_failures
