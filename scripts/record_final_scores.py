# -*- coding: utf-8 -*-
"""把某实验的个人评分录入教务花名册 .xls 的指定成绩列。

典型用途：把 final-project 的期末分数录入两个教务导出 .xls 的「课堂期末成绩」列，
便于回传教务系统。

工作流（重要）：
  1. 先用 GUI 重跑批阅（含花名册身份核验）→ 生成最新的 个人报告/*.json（学号为核验后的
     权威学号，如 安晓童 211、王倩倩 210）。
  2. 再运行本脚本 → 读个人报告分数，按学号写入 .xls。
  若跳过第 1 步直接运行，撞号相关学生（安晓童/申凯丽/陈乐莹等）的分数会是旧的/缺失。

用法：
  python scripts/record_final_scores.py
  python scripts/record_final_scores.py --semester 2026-春季 --experiment final-project \\
      --score-col 课堂期末成绩 --out-suffix _含期末成绩

说明：
  - 用 xlutils.copy 在原 .xls 基础上改写，**保留原有格式/列结构**，输出到新文件
    （原名 + out-suffix），不破坏原件。
  - 学号列固定识别表头「学号」，成绩列由 --score-col 指定（默认「课堂期末成绩」）。
  - 花名册有、但个人报告无（未交/被并）的学生，该列留空并在日志列出。
"""

import argparse
import glob
import json
import sys
from pathlib import Path

from xlutils.copy import copy as xl_copy
import xlrd


def load_scores(semester_dir: Path, experiment_id: str):
    """读 个人报告/*.json → {student_id: total_score}（跨班级合并，学号全局唯一）。"""
    scores = {}
    pattern = str(semester_dir / "*" / experiment_id / "results" / "grading" / "个人报告" / "*-评分.json")
    for fp in glob.glob(pattern):
        try:
            with open(fp, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            continue
        sid = str(d.get("student_id", "")).strip()
        if sid:
            scores[sid] = float(d.get("total_score", 0.0) or 0.0)
    return scores


def find_cols(header_row):
    """在表头行定位「学号」与目标成绩列。返回 (sid_col, score_col) 或 raise。"""
    cells = [str(c).strip() for c in header_row]
    if "学号" not in cells:
        raise ValueError("表头未找到「学号」列，疑似非花名册文件")
    return cells.index("学号")


def record_one(xls_path: Path, scores, score_col_name: str, out_suffix: str):
    rb = xlrd.open_workbook(str(xls_path), formatting_info=True)
    sh = rb.sheet_by_index(0)
    header = [sh.cell_value(0, c) for c in range(sh.ncols)]
    sid_col = find_cols(header)
    try:
        score_col = [str(c).strip() for c in header].index(score_col_name)
    except ValueError:
        print(f"  ✗ 未找到成绩列「{score_col_name}」，跳过。表头：{header}")
        return 0, []

    wb = xl_copy(rb)
    ws = wb.get_sheet(0)
    filled, missing = 0, []
    for r in range(1, sh.nrows):
        sid = str(sh.cell_value(r, sid_col)).strip()
        if sid.endswith(".0"):
            sid = sid[:-2]
        if sid not in scores:
            missing.append((sid, str(sh.cell_value(r, sid_col + 1))))  # 姓名
            continue
        ws.write(r, score_col, round(scores[sid], 1))
        filled += 1
    out_path = xls_path.parent / f"{xls_path.stem}{out_suffix}.xls"
    wb.save(str(out_path))
    print(f"  ✓ {xls_path.name} → {out_path.name}：录入 {filled} 人"
          f"{('，花名册有但无个人报告 %d 人：%s' % (len(missing), '、'.join(f'{n}({s})' for s, n in missing))) if missing else ''}")
    return filled, missing


def main():
    ap = argparse.ArgumentParser(description="把实验分数录入教务花名册 .xls")
    ap.add_argument("--semester", default="2026-春季")
    ap.add_argument("--experiment", default="final-project")
    ap.add_argument("--score-col", default="课堂期末成绩", help="目标成绩列表头名")
    ap.add_argument("--out-suffix", default="_含期末成绩")
    args = ap.parse_args()

    semester_dir = Path("data/teaching") / args.semester
    scores = load_scores(semester_dir, args.experiment)
    print(f"载入 {args.experiment} 个人报告 {len(scores)} 份（{args.score_col} 录入）")
    if not scores:
        print("✗ 未找到任何个人报告，请先重跑批阅。", file=sys.stderr)
        sys.exit(1)

    xls_files = sorted(semester_dir.glob("*.xls"))
    xls_files = [f for f in xls_files if not f.name.endswith((f"{args.out_suffix}.xls",))]
    if not xls_files:
        print(f"✗ {semester_dir} 下未找到 .xls 花名册。", file=sys.stderr)
        sys.exit(1)

    total = 0
    for fp in xls_files:
        try:
            filled, _ = record_one(fp, scores, args.score_col, args.out_suffix)
            total += filled
        except Exception as e:
            print(f"  ✗ {fp.name} 处理失败：{e}")
    print(f"\n完成：共录入 {total} 人。输出文件已写到 {semester_dir}/（原文件保留）。")


if __name__ == "__main__":
    main()
