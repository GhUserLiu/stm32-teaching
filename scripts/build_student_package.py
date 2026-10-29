# -*- coding: utf-8 -*-
"""学生端打包预处理 + 目录版 spec 生成。

用法（在仓库根、stm32_teaching 环境）：
    python scripts/build_student_package.py --expiry 2026-11-15
    python -m PyInstaller --noconfirm build_student_dir.spec

做四件事：
1. 数据脱敏：rubric 剔除教师答案（reference_answers 只留题号 thinking_question_ids，
   删答案文本；common_issues 删除）——保留评分所需 keywords/criteria
2. 学期模板打包：data/semesters/** 一并入包（四级下拉数据源）
3. 生成 license_data.py：烧入到期日（EXPIRY_DATE）
4. 生成 build_student_dir.spec：PyInstaller 目录版（onedir，启动快/误报低）
"""
import argparse
import copy
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "build" / "pkg_stage"


def sanitize_rubric(data: dict) -> dict:
    """剔除教师答案字段；保留评分必需字段。"""
    out = copy.deepcopy(data)
    ref = out.get("reference_answers")
    if isinstance(ref, dict):
        # 只留题号列表（思考题"是否作答"检测需要），剔除一切答案文本
        ids = ref.get("thinking_question_ids")
        out["reference_answers"] = ({"thinking_question_ids": ids}
                                    if ids else {})
    elif "reference_answers" in out:
        out.pop("reference_answers")
    out.pop("common_issues", None)
    return out


def stage_datas():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    # 1) 全局 rubrics（旧布局回退用）
    gdir = STAGE / "data" / "rubrics"
    gdir.mkdir(parents=True)
    for name in ("rubric.json", "rubric_enhanced.json", "final-project.json"):
        src = ROOT / "data" / "rubrics" / name
        if src.exists():
            data = json.loads(src.read_text(encoding="utf-8"))
            (gdir / name).write_text(
                json.dumps(sanitize_rubric(data), ensure_ascii=False, indent=1),
                encoding="utf-8")

    # 2) 学期模板（yaml 原样 + rubrics 脱敏）
    sem_src = ROOT / "data" / "semesters"
    if sem_src.exists():
        for yaml_file in sem_src.glob("*/experiments.yaml"):
            sem = yaml_file.parent.name
            dst = STAGE / "data" / "semesters" / sem
            dst.mkdir(parents=True)
            shutil.copy(yaml_file, dst / "experiments.yaml")
            rdst = dst / "rubrics"
            rdst.mkdir()
            for rj in (yaml_file.parent / "rubrics").glob("*.json"):
                data = json.loads(rj.read_text(encoding="utf-8"))
                (rdst / rj.name).write_text(
                    json.dumps(sanitize_rubric(data), ensure_ascii=False, indent=1),
                    encoding="utf-8")

    # 3) 学生端全局配置
    cfg_dst = STAGE / "data" / "config" / "teaching"
    cfg_dst.mkdir(parents=True)
    shutil.copy(ROOT / "data" / "config" / "teaching" / "config.yaml",
                cfg_dst / "config.yaml")
    print(f"staged -> {STAGE}")


def write_license_data(expiry: str):
    p = (ROOT / "src" / "tools" / "student_submission_gui"
         / "license_data.py")
    p.write_text(
        f'# -*- coding: utf-8 -*-\n# 构建脚本自动生成（勿手改；改动会被下次构建覆盖）\n'
        f'EXPIRY_DATE = "{expiry}"\n',
        encoding="utf-8")
    print(f"license_data.py -> EXPIRY_DATE = {expiry}")


SPEC_TEMPLATE = """# -*- mode: python ; coding: utf-8 -*-
# 学生端目录版（onedir）spec —— 由 scripts/build_student_package.py 生成
# datas 来自 build/pkg_stage（已剔除教师答案），授权到期日已烧入 license_data
import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(
    ['src/tools/student_submission_gui/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('build/pkg_stage/data/rubrics', 'data/rubrics'),
        ('build/pkg_stage/data/semesters', 'data/semesters'),
        ('build/pkg_stage/data/config/teaching', 'data/config/teaching'),
    ],
    hiddenimports=[
        'tools.plagiarism.grading.grading',
        'tools.plagiarism.image.image_counter',
        'tools.plagiarism.code_analysis.code_analyzer',
        'tools.security.seven_zip_validator',
        'py7zr',
        'tools.auto_grading.source_state',
        'tools.student_submission_gui.submission_packager',
        'tools.auto_grading.submission_normalizer',
        'tools.student_submission_gui.license_data',
        'defusedxml',
        'docx',
        'openpyxl',
        'PIL',
        'PIL._tkinter_finder',
        'numpy',
        'yaml',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch', 'torchvision', 'torchaudio',
        'sentence_transformers', 'transformers', 'tokenizers',
        'pandas', 'sklearn', 'scipy',
        'jieba',
        'matplotlib', 'IPython', 'jupyter', 'notebook',
        'pytest', '_pytest',
        'tkinter',
        'reportlab', 'markdown',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MCU_SelfCheck',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_file=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MCU_SelfCheck',
)
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expiry", default="2026-11-15",
                    help="授权截止日 YYYY-MM-DD（默认 2026-11-15）")
    args = ap.parse_args()

    stage_datas()
    write_license_data(args.expiry)
    spec = ROOT / "build_student_dir.spec"
    spec.write_text(SPEC_TEMPLATE, encoding="utf-8")
    print(f"spec -> {spec}")
    print("\n下一步：python -m PyInstaller --noconfirm build_student_dir.spec")
    print(f"产物：dist/MCU_SelfCheck/MCU_SelfCheck.exe（有效期至 {args.expiry}）")


if __name__ == "__main__":
    main()
