#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
学生端「打包预处理」
Submission Packager

自检通过后，若提交**格式合规**，生成一个可直接上传学习通的规范 zip：
外层 ``{学号}-{姓名}.zip``，内含
- ``{班级}-{学号}-{姓名}-实验报告.docx``（改名副本）
- ``{班级}-{学号}-{姓名}-源代码.zip``（把源码树重新打成单层干净 zip，去掉嵌套/垃圾）

格式不合规时不生成 zip，由调用方（UI）把 ``assess_gate`` 返回的 blockers 展示给学生，
逐项修正后重检再打包——把以下根因挡在提交之前：
- 刘涛：交了多个源码 zip（学生端只产出一份干净源码 zip）
- 聂智聪：源码包嵌套（flatten 后重打）
- 杨凯辉：团队表学号写成 9 位（B7 拦截）
- 只交报告没交源码（B5/B6 拦截）

纯逻辑，无 Qt 依赖，便于单测与 headless 调用。
"""

import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from .id_card import StudentIdentity
from .self_check_report import _safe_dir_name
from .self_checker import SelfCheckResult


class PackagingError(RuntimeError):
    """打包闸门未过 / 源码缺失 / 拷贝失败等可向用户解释的错误。"""


# 团队表学号不规范的警告前缀（与 self_checker._check_team_member_ids 输出一致）
_TEAM_ID_WARN_PREFIX = "团队成员表里的学号位数不规范"


def assess_gate(
    result: SelfCheckResult,
    identity: StudentIdentity,
) -> Tuple[bool, List[str], List[str]]:
    """评估提交是否「格式合规」可打包。

    Returns:
        (ok, blockers, warnings)
        - ok=True iff blockers 为空（格式合规，可生成 zip）
        - blockers: 阻断打包的人类可读原因
        - warnings: 非阻断提示（如纯 Keil、报告原名不规范等）

    闸门口径 = **格式合规**（不卡分数）：
    - 身份完整、学号 11 位；报告为真 .docx 且存在；真实源码工程存在（ok/keil_only）；
      团队表学号规范。
    - 分数高低、纯 Keil 工程（编译会判 0）、报告章节不全/缺思考题等**质量**项**不阻断**，
      只进 warnings（validation 不阻断——按用户口径，质量由教师评，不由打包闸门卡）。
    """
    blockers: List[str] = []
    warnings: List[str] = []

    # B1/B2 身份
    if not identity.is_complete():
        blockers.append("学生信息不完整（班级/学号/姓名均需填写）。")
    elif len(identity.student_id) != 11:
        blockers.append(
            f"学号「{identity.student_id}」非 11 位，无法生成规范提交包；请核对学号。"
        )

    sub = result.submission
    report_path = sub.report_path if sub is not None else None

    # B4 报告路径存在性
    if report_path is None or not Path(report_path).exists():
        blockers.append("未找到实验报告文件，无法打包。")
    else:
        # B3 报告真实格式
        from tools.auto_grading.submission_validator import detect_report_format
        fmt = detect_report_format(Path(report_path))
        if fmt != "docx":
            blockers.append(
                f"报告非标准 .docx（检测为 {fmt}），无法被批阅工具解析；"
                f"请在 Word 中另存为 .docx 后重新选择并自检。"
            )
        # W3 报告原名不规范（信息性，因我们会改名）
        if not StudentIdentity.filename_is_canonical(Path(report_path).stem):
            warnings.append(
                f"报告原名「{Path(report_path).name}」不规范，打包时将自动改名为"
                f"「{identity.class_name}-{identity.student_id}-{identity.name}-实验报告.docx」。"
            )

    # B5 源码工程状态
    sstate = getattr(result, "source_state", "") or ""
    if sstate not in ("ok", "keil_only"):
        reason = getattr(result, "source_state_reason", "") or "未找到可编译的工程结构"
        blockers.append(f"源码工程不可用：{reason}")
    else:
        # W1 纯 Keil 工程（格式合规但教师端机器编译会判 0）
        if sstate == "keil_only":
            warnings.append(
                "检测到纯 Keil 工程（无 Makefile）：格式合规可打包，但教师端机器编译将计 0 分；"
                "建议用 STM32CubeMX → Toolchain/IDE 选「Makefile」重新生成后再提交。"
            )

    # B6 源码路径有效（tempdir 未被提前 cleanup）
    src_path = sub.source_path if sub is not None else None
    if src_path is None or not Path(src_path).exists():
        blockers.append("源码临时目录已失效，请重新自检后再打包。")

    # B7 团队表学号位数（_check_team_member_ids 的输出）
    for w in getattr(result, "warnings", []) or []:
        if _TEAM_ID_WARN_PREFIX in w:
            blockers.append(w)
            break  # 一条聚合提示即可

    # W2 validation 警告概要（仅提示，不阻断）
    v = getattr(result, "validation", None)
    if v is not None and getattr(v, "warning_count", 0) > 0:
        warnings.append(
            f"提交检测另有 {v.warning_count} 项警告（章节完整性/思考题等，不影响打包，"
            f"建议按「提交检测」面板提示改进）。"
        )

    return (len(blockers) == 0, blockers, warnings)


def _package_dir(project_root: Path, identity: StudentIdentity) -> Path:
    """打包输出目录：outputs/student_self_check/{学号}-{姓名}/{时间戳}/

    复用 self_check_report._safe_dir_name 与时间戳模式，与自检报告同目录。
    """
    root = Path(project_root) / "outputs" / "student_self_check"
    student_dir = root / _safe_dir_name(identity)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = student_dir / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def package_submission(
    result: SelfCheckResult,
    identity: StudentIdentity,
    project_root: Path,
    *,
    out_dir: Optional[Path] = None,
) -> Path:
    """生成规范提交 zip，返回其路径。

    步骤：复检闸门 → 拷贝源码到副本 → flatten → 打内层源码 zip → 装外层 zip。

    Args:
        result: 自检结果（``source_path`` 须仍有效——展示期间未 cleanup）
        identity: 学生身份（用于规范命名）
        project_root: 仓库根（定位 outputs/）
        out_dir: 可选输出目录（测试/用户指定路径）；默认与自检报告同目录

    Raises:
        PackagingError: 闸门未过 / 源码缺失 / 拷贝失败

    前置不变量：``result.submission.source_path`` 是 self_checker 已解压+单层 unwrap 的
    tempdir，但**可能仍有多层包装**（聂智聪场景），故 flatten 是必需的。flatten 原地改
    目录，故必须先 copytree 到副本。
    """
    ok, blockers, _ = assess_gate(result, identity)
    if not ok:
        raise PackagingError("；".join(blockers))

    sub = result.submission
    src_root = Path(sub.source_path)
    report_path = Path(sub.report_path)

    pkg_dir = Path(out_dir) if out_dir else _package_dir(project_root, identity)
    pkg_dir.mkdir(parents=True, exist_ok=True)

    inner_name = f"{identity.class_name}-{identity.student_id}-{identity.name}-源代码"
    report_canon = f"{identity.class_name}-{identity.student_id}-{identity.name}-实验报告.docx"
    outer_stem = f"{identity.student_id}-{identity.name}"  # 教师端期望的外层名

    work = Path(tempfile.mkdtemp(prefix="student_pkg_"))
    try:
        # 1. 拷贝源码树到副本（flatten 会原地改动）
        src_copy = work / "src"
        shutil.copytree(src_root, src_copy, symlinks=False, dirs_exist_ok=False)

        # 2. 扁平化多余包装层（zip 套目录套工程）；ABORT 路径不改目录，原样也合法
        from tools.auto_grading.submission_normalizer import SubmissionNormalizer
        SubmissionNormalizer.flatten(src_copy)

        # 3. 内层源码 zip：单层工程树
        shutil.make_archive(str(work / inner_name), "zip", root_dir=src_copy)

        # 3b. 源码树已打入内层 zip，从 work 移除，确保外层 zip 只含「报告 + 源码 zip」
        shutil.rmtree(src_copy, ignore_errors=True)

        # 4. 报告改名副本
        shutil.copy2(report_path, work / report_canon)

        # 5. 外层 zip：恰含「报告 + 源码 zip」两个文件
        outer_zip = shutil.make_archive(str(pkg_dir / outer_stem), "zip", root_dir=work)
        return Path(outer_zip)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def outer_zip_has_clean_structure(zip_path: Path) -> Tuple[bool, List[str]]:
    """校验生成的 zip 结构合规：外层恰含 1 个 .docx + 1 个 源代码.zip，均在根。

    供测试与自检断言用。
    """
    names = []
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
    at_root = [n for n in names if "/" not in n.rstrip("/")]
    has_docx = any(n.lower().endswith(".docx") for n in at_root)
    has_src = any("源代码" in n and n.lower().endswith(".zip") for n in at_root)
    issues = []
    if not has_docx:
        issues.append("缺少规范命名的实验报告 .docx")
    if not has_src:
        issues.append("缺少源代码 .zip")
    if len(at_root) != 2:
        issues.append(f"外层应恰含 2 个文件，实际 {len(at_root)} 个：{at_root}")
    return (len(issues) == 0, issues)
