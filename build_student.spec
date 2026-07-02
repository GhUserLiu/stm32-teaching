# -*- mode: python ; coding: utf-8 -*-
"""
学生端作业自检与自评系统 — PyInstaller 打包脚本（单一通用产物）
Student Self-Check & Self-Grade GUI — PyInstaller spec (universal build)

构建（须在 conda 环境 stm32f407-win7 下，或直接：scripts\\build_student_exe.bat）：
    conda run -n stm32f407-win7 python -m PyInstaller --noconfirm build_student.spec

产物：
    dist/StudentSelfCheck.exe          （单文件，windowed，覆盖 Win7/8.1/10/11）

为什么是 Python 3.8 + PyQt5（而非 3.13 + PyQt6）：
- Python 3.9+ 依赖 api-ms-win-core-path-l1-1-0.dll，Win7 无此 API Set，启动即崩。
- Qt6 运行时最低要求 Windows 10 1809+，不支持 Win7。
- 用 Py3.8 + PyQt5==5.15.2 后，单一 exe 覆盖 Win7-11（Qt5.15.2 是最后支持 Win7 的 Qt）。
- 学生端 GUI 经 qt_compat.py 双绑定 shim，本 spec 由 PyQt5 环境调用即打 PyQt5；
  代码在 PyQt6（开发机/教师端主线）下同样可运行。

说明：
- 单文件（onefile）、无控制台（windowed）。启动时 PyInstaller 会解压到临时目录。
- 只读资源（rubric.json / rubric_enhanced.json / final-project.json / config.yaml）
  随包打入，运行时由 runtime.bundle_root() 定位。
- 报告输出到用户主目录下的「STM32学生自检」（由 runtime.writable_root() 决定）。
- 显式排除学生端用不到的重型依赖（torch/sentence-transformers/pandas/sklearn/jieba 等），
  这些仅服务于教师端查重/语义检测，不在学生端运行时导入图中。
"""

block_cipher = None

a = Analysis(
    ['src/tools/student_submission_gui/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        # (源路径, 打包内目标目录，相对于 bundle_root)
        ('data/rubrics/rubric.json', 'data/rubrics'),
        ('data/rubrics/rubric_enhanced.json', 'data/rubrics'),
        ('data/rubrics/final-project.json', 'data/rubrics'),
        ('data/config/teaching/config.yaml', 'data/config/teaching'),
    ],
    hiddenimports=[
        # 学生端运行时按需（惰性导入）加载的模块，显式声明以免漏打包
        'tools.plagiarism.grading.grading',
        'tools.plagiarism.image.image_counter',
        'tools.plagiarism.code_analysis.code_analyzer',
        # .7z 源码包解压：seven_zip_validator 内 try-import py7zr，需显式声明两个
        # 否则 PyInstaller 静态分析漏抓，学生选 .7z 期末项目源码时会因 py7zr 缺失降级
        'tools.security.seven_zip_validator',
        'py7zr',
        # source_state：学生端 SelfChecker 顶层 import，正常可被静态分析抓到；
        # 但 grading_engine 内有函数级惰性 import，显式声明更稳（G3 源码状态分类）
        'tools.auto_grading.source_state',
        # 打包预处理（学生端新增）：PackageWorker 在后台线程惰性 import submission_packager，
        # 后者又惰性 import 教师端的 submission_normalizer(flatten)；显式声明以免漏打包，
        # 否则学生点「打包提交」时会因模块缺失报错。
        'tools.student_submission_gui.submission_packager',
        'tools.auto_grading.submission_normalizer',
        # 运行时依赖（多数可自动发现，显式声明更稳）
        'defusedxml',
        'docx',
        'openpyxl',
        'PIL',
        'PIL._tkinter_finder',
        'numpy',
        # path_helper.load_experiments 在 try 内惰性 import yaml 解析 config.yaml；
        # 漏装会导致实验下拉回退到内置默认清单（缺期末综合项目）
        'yaml',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 学生端不需要的重型/无关依赖（防止 PyInstaller 静态分析误打包）
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='StudentSelfCheck',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                 # 关闭 UPX：避免杀毒软件误报（代价是体积略大）
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,             # windowed GUI（无控制台窗口）
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
