#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批阅工作线程
Grading Worker Thread

在后台线程中执行批阅任务，避免阻塞GUI。
"""

import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Set

from PyQt6.QtCore import QThread, pyqtSignal

from tools.auto_grading import AutoGradingFacade, AutoGradingConfig
from tools.auto_grading import batch_checkpoint
from tools.auto_grading.facade import PipelineResult
from tools.teaching_management_gui.data_source import ClassEntry


class GradingWorker(QThread):
    """批阅工作线程（批量：遍历多个班级条目）"""

    # 定义信号
    stage_started = pyqtSignal(str, str)  # (stage_id, stage_name)
    stage_progress = pyqtSignal(str, int, int)  # (stage_id, current, total)
    stage_completed = pyqtSignal(str)  # (stage_id)
    log_message = pyqtSignal(str)  # (message)
    grading_completed = pyqtSignal(object, object)  # (list[GradingResult], list[失败dict])，跨班级合并
    grading_cancelled = pyqtSignal()  # 取消：不发部分结果，避免被面板当成"完成"
    grading_failed = pyqtSignal(str)  # (error_message)

    def __init__(
        self,
        entries,
        semester: str = "2026-春季",
        config: Optional[AutoGradingConfig] = None,
        resume: bool = False,
    ):
        """
        初始化批量批阅工作线程

        Args:
            entries: ClassEntry 列表（班级/实验/压缩包）
            semester: 学期（决定产物路径）
            config: 配置对象
        """
        super().__init__()
        self.entries = list(entries)
        self.semester = semester
        self.config = config or AutoGradingConfig()
        self.config.semester = semester
        self.resume = resume   # Phase B: True 时跳过各班 checkpoint 里已完成的学号
        self.is_cancelled = False
        # 取消事件：cancel() 置位后，引擎内 build_checker 正在跑的 make 编译会在
        # 下一次轮询（~0.2s）被 kill，而不必等它跑完或超时。
        self._cancel_event = threading.Event()

    def run(self):
        """对每个班级条目依次执行批阅，合并所有 GradingResult。"""
        try:
            all_results = []
            all_failures = []   # per-student 评分失败（跨班级合并），供面板展示「⚠ N 人批阅失败」
            total = len(self.entries)
            self.log_message.emit(f"开始批量批阅：共 {total} 个班级")

            for i, entry in enumerate(self.entries):
                if self.is_cancelled:
                    break
                zip_path = Path(entry.zip_path)
                self.log_message.emit(
                    f"({i + 1}/{total}) 班级 {entry.class_name} / 实验 {entry.experiment_id}"
                )
                self.log_message.emit(f"压缩包: {zip_path.name}")

                if not zip_path.exists():
                    self.log_message.emit(f"警告: 压缩包不存在，跳过: {zip_path}")
                    self.stage_progress.emit("analyze", i + 1, total)
                    continue

                # 每个班级一个可观察门面，复用其 run_full_pipeline
                facade = ObservableFacade(
                    self.config,
                    self.stage_started,
                    self.stage_progress,
                    self.stage_completed,
                    self.log_message,
                    lambda: self.is_cancelled,
                    self._cancel_event,
                )
                # 续跑：读取该班级 checkpoint 的已完成学号集（Phase B）
                _resume_ids = None
                if self.resume:
                    _gdir = self.config.get_output_dir(entry.class_name, entry.experiment_id)
                    _meta = batch_checkpoint.load_meta(_gdir)
                    if _meta and _meta.get("completed_ids"):
                        _resume_ids = set(_meta["completed_ids"])
                        self.log_message.emit(
                            f"  续跑：{entry.class_name} 跳过已完成 {len(_resume_ids)} 人")
                result = facade.run_full_pipeline(
                    zip_path,
                    entry.class_name,
                    entry.experiment_id,
                    False,
                    resume_completed_ids=_resume_ids,
                )
                all_results.extend(result.grading_results)
                all_failures.extend(result.failures)
                self.stage_progress.emit("analyze", i + 1, total)

            # 取消时不发 grading_completed（避免部分结果被当成"完成"），改发取消信号
            if self.is_cancelled:
                self.log_message.emit(f"批阅已取消（已丢弃 {len(all_results)} 条部分结果）")
                self.grading_cancelled.emit()
            else:
                self.grading_completed.emit(all_results, all_failures)

        except Exception as e:
            self.grading_failed.emit(str(e))

    def cancel(self):
        """取消批阅"""
        self.is_cancelled = True
        self._cancel_event.set()   # 通知引擎内 build_checker kill 当前 make 子进程
        self.log_message.emit("正在取消...")


class _LogTee:
    """把 log_message 信号同时 tee 到文件的包装器。

    ObservableFacade 在 run_full_pipeline 开头把 self.log_message 重新赋值为
    _LogTee(raw_signal, log_path)，之后现有 30+ 处 self.log_message.emit(...)
    调用无需改动，即同时把每行日志 append 到 results/grading/batch_run.log
    （每次 emit 独立 open/write/close + 即时落盘，崩溃前已写的内容不丢，
    也避免跨班级累积文件句柄）。"""

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


class ObservableFacade:
    """可观察的门面（用于向GUI发送信号）"""

    def __init__(
        self,
        config: AutoGradingConfig,
        stage_started_sig,
        stage_progress_sig,
        stage_completed_sig,
        log_message_sig,
        is_cancelled_func,
        cancel_event: Optional[threading.Event] = None,
    ):
        """
        初始化

        Args:
            config: 配置对象
            stage_started_sig: 阶段开始信号
            stage_progress_sig: 阶段进度信号
            stage_completed_sig: 阶段完成信号
            log_message_sig: 日志消息信号
            is_cancelled_func: 检查是否取消的函数
            cancel_event: 取消事件（注入引擎 build_checker，使 make 编译可被中断）
        """
        self.config = config
        self.stage_started = stage_started_sig
        self.stage_progress = stage_progress_sig
        self.stage_completed = stage_completed_sig
        self.log_message = log_message_sig
        self.is_cancelled = is_cancelled_func
        self._cancel_event = cancel_event

        # 创建实际的门面
        self.facade = AutoGradingFacade(config)

    def run_full_pipeline(
        self,
        class_zip: Path,
        class_name: str,
        experiment_id: str,
        skip_organization: bool = False,
        resume_completed_ids: Optional[Set[str]] = None,
    ) -> PipelineResult:
        """运行完整流水线（带信号通知）"""
        result = PipelineResult(
            class_name=class_name,
            experiment_id=experiment_id
        )

        self.log_message.emit("=" * 70)
        self.log_message.emit("自动化批阅系统")
        self.log_message.emit("=" * 70)

        # 按实验 id 装载对应 rubric（与 facade.run_full_pipeline 一致）。
        # 否则 GUI 路径会一直用 AutoGradingFacade.__init__ 里默认的 rubric.json
        # （汽车档位标准），把综合项目等按错误标准评分。
        self.facade.engine = self.facade._make_engine(experiment_id)
        # 注入取消事件：让引擎内 build_checker 的 make 编译可被取消（命中即 kill 子进程）
        bc = getattr(self.facade.engine, "build_checker", None)
        if bc is not None and hasattr(bc, "set_cancel_event"):
            bc.set_cancel_event(self._cancel_event)
        self.log_message.emit(
            "rubric: " + str(
                getattr(self.facade.engine.rubric, 'get', lambda *a: None)(
                    'experiment_name', None)
                or self.facade.engine.rubric_path or '(默认)'))

        # 持久化日志：把本类所有 self.log_message.emit(...) 同时 tee 到
        # results/grading/batch_run.log（append，每行带时间戳；崩溃前已落盘，
        # 切走标签页/关窗都不丢）。失败不影响批阅。
        try:
            _log_path = self.facade.config.get_output_dir(class_name, experiment_id) / "batch_run.log"
            _log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(_log_path, "a", encoding="utf-8") as _hf:
                _hf.write(f"\n=== run started {datetime.now():%Y-%m-%d %H:%M:%S} "
                          f"| {class_name} / {experiment_id} ===\n")
            self.log_message = _LogTee(self.log_message, _log_path)
        except Exception:
            pass

        # 阶段1: 整理提交格式
        if not skip_organization:
            self.log_message.emit("阶段1: 整理提交格式")
            self.stage_started.emit("organize", "整理提交")

            # 模拟进度（因为没有细粒度进度）
            self.stage_progress.emit("organize", 1, 10)
            org_result = self.facade.organizer.process_class_submission(
                class_zip,
                class_name,
                experiment_id
            )
            self.stage_progress.emit("organize", 10, 10)
            self.stage_completed.emit("organize")

            result.organization_result = org_result

            self.log_message.emit(f"  成功: {org_result.successful}/{org_result.total_students}")

            if org_result.total_students == 0:
                self.log_message.emit("警告: 没有找到学生提交")
                return result

            if self.is_cancelled():
                return result
        else:
            self.log_message.emit("阶段1: 跳过（已整理）")

        # 阶段2: 处理提交数据
        self.log_message.emit("阶段2: 处理提交数据")
        self.stage_started.emit("process", "处理提交数据")
        self.stage_progress.emit("process", 1, 10)

        submissions = self.facade.processor.process_class_submissions(
            class_name,
            experiment_id,
            expand_team=True,   # 批阅按团队成员展开为每人一条；查重链路保持默认 False
        )

        self.stage_progress.emit("process", 10, 10)
        self.stage_completed.emit("process")

        result.total_submissions = len(submissions)
        self.log_message.emit(f"  处理完成: {len(submissions)} 个提交")

        if not submissions:
            self.log_message.emit("警告: 没有找到提交数据")
            return result

        # 阶段3: 批量评分（stage_id "analyze" 为 GUI 进度条约定，勿改名）
        self.log_message.emit("阶段3: 批量评分")
        self.stage_started.emit("analyze", "评分中")

        grading_results = []
        failures = []  # per-student 评分异常收集（不再静默丢弃），供 GUI 展示
        total = len(submissions)

        # 断点续跑 checkpoint（Phase B）：每成功评一个学生就增量写缓存 + meta，
        # 崩溃/取消后下次「开始批阅」可检测到并跳过已完成者；批阅成功完成则清掉。
        _gdir = self.facade.config.get_output_dir(class_name, experiment_id)
        _resume_ids = set(resume_completed_ids or [])
        _meta = batch_checkpoint.new_meta(
            class_name, experiment_id, self.facade.config.semester, total)
        if _resume_ids:
            _meta["completed_ids"] = sorted(_resume_ids)
        else:
            batch_checkpoint.clear_checkpoint(_gdir)  # 全新开始：清掉上次残留
        batch_checkpoint.write_meta(_gdir, _meta)

        for i, submission in enumerate(submissions):
            if self.is_cancelled():
                break

            self.log_message.emit(f"评分 ({i+1}/{total}): {submission.student_id}-{submission.name}")
            self.stage_progress.emit("analyze", i + 1, total)

            # 续跑：该生已完成 → 复用缓存、不重评（缓存缺失/损坏则落到下方重评）
            if submission.student_id in _resume_ids:
                _cached = batch_checkpoint.load_result_cache(_gdir, submission.student_id)
                if _cached is not None:
                    self.log_message.emit("  续跑：跳过（已完成，复用缓存）")
                    grading_results.append(_cached)
                    continue

            try:
                grading_result = self.facade.engine.grade_submission(submission)
            except Exception as e:
                # 单个提交异常不应中断整批：记录失败原因，其余继续（不再静默丢弃）
                self.log_message.emit(f"  ⚠ 评分异常，已记入失败清单：{e}")
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

            self.log_message.emit(f"  得分: {grading_result.total_score:.1f}/{grading_result.max_score:.1f} ({grading_result.grade})")

        cancelled = self.is_cancelled()
        if not cancelled:
            self.stage_progress.emit("analyze", total, total)
            self.stage_completed.emit("analyze")

        # 小组按成员展开后，同一学生可能出现在多份上传报告中；按学号去重保留最高分。
        # 传 rubric：让 dedupe 按组真实人数校正组长加分（多组长平摊 / 无组长全员平摊）。
        # 花名册身份核验（re-key + 学号/姓名错误记0分）必须在去重之前：re-key 到真实学号后，
        # 撞号两人各落不同学号，不再被去重并掉（如 安晓童 210→211 不再撞 王倩倩 210）。
        from tools.auto_grading.grading_engine import dedupe_team_members
        try:
            from tools.auto_grading.roster_check import load_id_roster, validate_identities
            _cfg = self.facade.config
            _roster = load_id_roster(_cfg.teaching_dir / _cfg.semester)
            if _roster:
                grading_results = validate_identities(grading_results, _roster)
        except Exception as _e:
            self.log_message.emit(f"  花名册核验跳过：{_e}")
        grading_results = dedupe_team_members(
            grading_results, rubric=getattr(self.facade.engine, 'rubric', None))

        result.grading_results = grading_results
        result.successful_graded = len(grading_results)
        result.failures = failures

        # 阶段4: 生成报告。取消则不落盘部分结果，避免与 grading_cancelled 信号不一致。
        if not cancelled:
            self.log_message.emit("阶段4: 生成报告")
            self.stage_started.emit("report", "生成报告")
            self.stage_progress.emit("report", 1, 10)

            # completed_at 必须在 _save_reports 之前赋值，否则批阅汇总.json 里会是 null
            result.completed_at = datetime.now()
            class_report = None
            if grading_results:
                class_report = self.facade.engine.generate_class_report(grading_results)
                self.facade._save_reports(result, class_report)
                # 批阅成功完成 → 清除 checkpoint（保持 results/ 干净，下次全新开始）
                batch_checkpoint.clear_checkpoint(_gdir)
                self.log_message.emit("  班级报告已生成")
                self.log_message.emit("  个人报告已生成")
                self.stage_progress.emit("report", 10, 10)
            self.stage_completed.emit("report")

            self.log_message.emit("=" * 70)
            self.log_message.emit("批阅完成！")
            # 平均分/等级分布取自 generate_class_report（单一事实来源），避免与班级报告.json 不一致
            if class_report:
                self.log_message.emit(f"平均分: {class_report['average_score']:.1f}")
                self.log_message.emit(f"等级分布: {class_report['grade_distribution']}")
            self.log_message.emit(f"完成时间: {result.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
            self.log_message.emit(f"耗时: {(result.completed_at - result.started_at).total_seconds():.1f}秒")
        else:
            self.log_message.emit("已取消，不生成报告")

        return result

