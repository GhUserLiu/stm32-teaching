# -*- coding: utf-8 -*-
"""教师端打包预处理：生成 build_teacher_dir.spec（目录版 exe，含完整数据）。

与学生端区别：数据**不脱敏**（教师版需要 rubric 全文含参考答案）、无授权期限。
便携式布局：首启把 _internal 的 config/、data/ 种子拷到 exe 旁，成绩写 exe 旁。

用法（仓库根、stm32_teaching 环境）：
    python scripts/build_teacher_package.py
    python -m PyInstaller --noconfirm build_teacher_dir.spec
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "build" / "pkg_teacher"


def stage_datas():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    # data：学期模板 + 全局 rubrics + 教学配置（教师版完整数据，不脱敏）
    for sub in ("semesters", "rubrics"):
        src = ROOT / "data" / sub
        if src.exists():
            shutil.copytree(src, STAGE / "data" / sub)
    cfg = STAGE / "data" / "config" / "teaching"
    cfg.mkdir(parents=True)
    shutil.copy(ROOT / "data" / "config" / "teaching" / "config.yaml", cfg / "config.yaml")
    # config：统一配置层 base.yaml
    shutil.copytree(ROOT / "config", STAGE / "config",
                    ignore=shutil.ignore_patterns("__pycache__"))
    print(f"staged -> {STAGE}")


SPEC_TEMPLATE = """# -*- mode: python ; coding: utf-8 -*-
# 教师端目录版 spec —— 由 scripts/build_teacher_package.py 生成（数据完整不脱敏）
block_cipher = None

a = Analysis(
    ['src/tools/teaching_management_gui/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('build/pkg_teacher/data', 'data'),
        ('build/pkg_teacher/config', 'config'),
    ],
    hiddenimports=[
        'tools.plagiarism.grading.grading',
        'tools.plagiarism.image.image_counter',
        'tools.plagiarism.code_analysis.code_analyzer',
        'tools.security.seven_zip_validator',
        'py7zr',
        'tools.auto_grading.source_state',
        'tools.auto_grading.submission_normalizer',
        'tools.student_submission_gui.submission_packager',
        'core.services.grading_service',
        'core.services.similarity_service',
        'core.services.result_importer',
        'persistence.database',
        'parsers.keil_project_parser',
        'schemas.config',
        'defusedxml',
        'docx', 'openpyxl', 'xlrd', 'xlwt', 'xlutils',
        'PIL', 'numpy', 'yaml', 'pydantic', 'sqlalchemy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch', 'torchvision', 'torchaudio',
        'sentence_transformers', 'transformers', 'tokenizers',
        'pandas', 'sklearn', 'scipy', 'jieba',
        'matplotlib', 'IPython', 'jupyter', 'notebook',
        'pytest', '_pytest', 'tkinter',
        'reportlab', 'markdown',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='MCU_Teaching',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=False, upx_exclude=[],
    name='MCU_Teaching',
)
"""


def main():
    stage_datas()
    spec = ROOT / "build_teacher_dir.spec"
    spec.write_text(SPEC_TEMPLATE, encoding="utf-8")
    print(f"spec -> {spec}")
    print("下一步：python -m PyInstaller --noconfirm build_teacher_dir.spec")


if __name__ == "__main__":
    main()
