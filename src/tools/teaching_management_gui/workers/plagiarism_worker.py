#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
查重工作线程（批量 + 跨班级）
Plagiarism Detection Worker Thread (multi-class, cross-class)

流程：
1. 逐班级整理 ZIP + 处理提交，收集所有班级的 submissions，记录 学号→班级 映射；
2. 把所有班级的 submissions 合并成一个字典喂 PlagiarismDetector.detect()，
   一次两两比对即天然包含跨班级相似对；
3. 结果带班级信息，落 plagiarism_results.json。
"""

from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

from PyQt6.QtCore import QThread, pyqtSignal

from tools.auto_grading import AutoGradingConfig  # noqa: E402
from tools.auto_grading.facade import AutoGradingFacade  # noqa: E402
from tools.plagiarism.core.detector import (  # noqa: E402
    PlagiarismDetector,
    SimilarityMethod,
    SimilarityResult,
)
from tools.teaching_management_gui.path_helper import (  # noqa: E402
    plagiarism_dir as resolve_plagiarism_dir,
    cross_class_dir as resolve_cross_class_dir,
)
from tools.common import atomic_write_json  # noqa: E402


# UI 方法下拉项 → SimilarityMethod 的映射
METHOD_MAP = {
    "结构相似度": SimilarityMethod.SEQUENCE,
    "文本相似度": SimilarityMethod.COSINE,
    "语义相似度": SimilarityMethod.SEMANTIC,
    "综合检测（推荐）": SimilarityMethod.HYBRID,
}


class PlagiarismWorker(QThread):
    """查重检测工作线程（多班级 + 跨班级）"""

    log_message = pyqtSignal(str)
    progress = pyqtSignal(int)
    detail = pyqtSignal(str)
    detection_completed = pyqtSignal(object)  # 结果载荷 dict
    detection_failed = pyqtSignal(str)
    detection_cancelled = pyqtSignal()  # 取消：不发结果，避免面板当成"完成"

    def __init__(
        self,
        entries,
        semester: str = "2026-春季",
        method: SimilarityMethod = SimilarityMethod.HYBRID,
        threshold: float = 60.0,
        check_code: bool = True,
        check_report: bool = True,
        config: Optional[AutoGradingConfig] = None,
    ):
        super().__init__()
        self.entries = list(entries)
        self.semester = semester
        self.method = method
        self.threshold = float(threshold)
        self.check_code = check_code
        self.check_report = check_report
        self.config = config or AutoGradingConfig()
        self.config.semester = semester
        self.is_cancelled = False

    def run(self):
        try:
            total = len(self.entries)
            self.log_message.emit(f"开始查重：共 {total} 个班级（含跨班级比对）")
            self.log_message.emit(f"方法: {self.method.value} | 阈值: {self.threshold}")

            facade = AutoGradingFacade(self.config)

            combined: Dict[str, Dict] = {}   # 学号 -> {name, text, class}
            class_map: Dict[str, str] = {}   # 学号 -> 班级

            # 阶段1：逐班级整理 + 处理，合并 submissions
            for i, entry in enumerate(self.entries):
                if self.is_cancelled:
                    self.detection_cancelled.emit()
                    return
                self.detail.emit(f"提取 {entry.class_name}（{i + 1}/{total}）")
                self.progress.emit(int(10 + 40 * (i / max(total, 1))))
                self.log_message.emit(f"({i + 1}/{total}) 处理班级 {entry.class_name}")

                zp = Path(entry.zip_path)
                if not zp.exists():
                    self.log_message.emit(f"警告: 压缩包不存在，跳过: {zp}")
                    continue
                # 整理（解压到实验树）
                try:
                    facade.organizer.process_class_submission(
                        zp, entry.class_name, entry.experiment_id
                    )
                except Exception as e:
                    self.log_message.emit(f"整理失败 {entry.class_name}: {e}")
                submissions = facade.processor.process_class_submissions(
                    entry.class_name, entry.experiment_id
                )
                for sub in submissions:
                    text_parts: List[str] = []
                    if self.check_report and getattr(sub, "report_text", ""):
                        text_parts.append(sub.report_text)
                    if self.check_code and getattr(sub, "code_blocks", None):
                        text_parts.append("\n".join(sub.code_blocks))
                    text = "\n\n".join(text_parts).strip()
                    if not text:
                        continue
                    combined[sub.student_id] = {
                        "name": sub.name,
                        "text": text,
                        "class": entry.class_name,
                    }
                    class_map[sub.student_id] = entry.class_name

            if len(combined) < 2:
                raise RuntimeError(f"可用于查重的提交不足 2 份（当前 {len(combined)}）")

            # 阶段2：一次检测全部（含跨班级对）
            self.detail.emit("两两相似度比对（含跨班级）…")
            self.progress.emit(60)
            self.log_message.emit(f"阶段2: 跨班级两两比对 {len(combined)} 份提交")

            detector = PlagiarismDetector(method=self.method, threshold=self.threshold)
            all_results, suspicious, adaptive_report = detector.detect(combined)

            # 阶段2 是阻塞调用；若期间请求了取消，检测完成后不再保存/发结果
            if self.is_cancelled:
                self.detection_cancelled.emit()
                return

            self.progress.emit(85)

            # 阶段3：整理结果
            self.detail.emit("整理结果…")
            payload = self._build_payload(
                all_results, suspicious, adaptive_report, combined, class_map
            )
            saved_path = self._save_results(payload)
            payload["saved_path"] = str(saved_path) if saved_path else None
            self.log_message.emit(f"结果已保存: {saved_path}")

            self.progress.emit(100)
            self.detail.emit("查重完成")
            cross = sum(1 for p in payload["pairs"] if p["cross_class"])
            self.log_message.emit(
                f"查重完成！相似对 {len(payload['pairs'])}（其中跨班级 {cross}），"
                f"可疑 {payload['suspicious_count']}"
            )
            self.detection_completed.emit(payload)

        except Exception as e:
            self.detection_failed.emit(str(e))

    def _build_payload(
        self,
        all_results: Dict[str, List[SimilarityResult]],
        suspicious: List[SimilarityResult],
        adaptive_report,
        combined: Dict[str, Dict],
        class_map: Dict[str, str],
    ) -> dict:
        suspicious_keys = {(r.student_id, r.similar_to) for r in suspicious}
        seen = set()
        pairs = []
        for s1, results in all_results.items():
            for r in results:
                key = frozenset((r.student_id, r.similar_to))
                if key in seen:
                    continue
                seen.add(key)
                ca = class_map.get(r.student_id, "")
                cb = class_map.get(r.similar_to, "")
                is_susp = (
                    (r.student_id, r.similar_to) in suspicious_keys
                    or (r.similar_to, r.student_id) in suspicious_keys
                )
                pairs.append({
                    "class_a": ca,
                    "student_a": r.student_id,
                    "name_a": combined.get(r.student_id, {}).get("name", ""),
                    "class_b": cb,
                    "student_b": r.similar_to,
                    "name_b": combined.get(r.similar_to, {}).get("name", ""),
                    "overall": round(r.overall_similarity, 1),
                    "text_sim": round(r.text_similarity, 1),
                    "code_sim": round(r.code_similarity, 1),
                    "structure_sim": round(r.structure_similarity, 1),
                    "suspicious": bool(is_susp),
                    "cross_class": bool(ca and cb and ca != cb),
                    "type": "改写" if getattr(r, "is_paraphrase", False) else "相似",
                })
        pairs.sort(key=lambda p: p["overall"], reverse=True)
        return {
            "classes": sorted({e.class_name for e in self.entries}),
            "method": self.method.value,
            "threshold": self.threshold,
            "total_students": len(combined),
            "pairs": pairs,
            "suspicious_count": len(suspicious),
            "adaptive_report": adaptive_report,
            "completed_at": datetime.now().isoformat(),
        }

    def _save_results(self, payload: dict) -> Optional[Path]:
        """保存查重结果。

        多班级（跨班级比对）时落学期根下 ``_跨班级比对/plagiarism/``（中立位置，
        各班归档都能找到，此前只落 entries[0] 目录、其余班无痕迹）；单班级仍落
        该班 ``results/plagiarism/``。
        """
        if not self.entries:
            return None
        if len(self.entries) > 1:
            out_dir = resolve_cross_class_dir(self.semester, "plagiarism")
        else:
            e = self.entries[0]
            out_dir = resolve_plagiarism_dir(e.class_name, e.experiment_id, self.semester)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "plagiarism_results.json"
        atomic_write_json(out_path, payload, ensure_ascii=False, indent=2, default=str)
        return out_path

    def cancel(self):
        self.is_cancelled = True
        self.log_message.emit("正在取消...")
