#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CLI wrapper: 把现有 JSON 批阅/查重产物回填进数据库。

用法（仓库根目录）:
    python scripts/backfill_from_results.py                    # 默认学期/默认库
    python scripts/backfill_from_results.py --semester 2026-春季
    python scripts/backfill_from_results.py --db-url sqlite:///database/teaching.sqlite
    python scripts/backfill_from_results.py --dry-run          # 只打印将要做什么

幂等：按自然键 get-or-create，重跑更新分数（最新值胜出），不产生重复行。
"""

import argparse
import sys
from pathlib import Path

# 允许从仓库根直接运行：把 src/ 加进 sys.path（与 GUI 启动器同约定）
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="回填现有 JSON 批阅/查重结果到 teaching 数据库")
    parser.add_argument("--semester", default=None,
                        help="学期（默认取统一配置 teaching.semester）")
    parser.add_argument("--db-url", default=None,
                        help="SQLAlchemy URL（默认 database/teaching.sqlite）")
    parser.add_argument("--teaching-dir", default=None,
                        help="教学数据根目录（默认 data/teaching）")
    parser.add_argument("--course-code", default="STM32F407")
    parser.add_argument("--course-name", default="单片机原理及应用")
    parser.add_argument("--dry-run", action="store_true",
                        help="只统计与打印，不提交（结尾回滚）")
    args = parser.parse_args(argv)

    from core.services.result_importer import ResultImporter
    from persistence import get_engine

    engine = get_engine(args.db_url)
    importer = ResultImporter(
        engine=engine,
        teaching_dir=Path(args.teaching_dir) if args.teaching_dir else None,
        semester=args.semester,
        course_code=args.course_code,
        course_name=args.course_name,
        log=print,
        dry_run=args.dry_run,
    )
    try:
        stats = importer.import_all()
    except Exception:
        # 失败也已整体回滚；把已累计的统计打印出来再抛（不丢上下文）
        if importer.last_stats is not None:
            print("回填失败（已整体回滚），失败前统计：",
                  importer.last_stats.summary_line(), file=sys.stderr)
        raise
    print(stats.summary_line())
    for note in stats.notes:
        print("  note:", note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
