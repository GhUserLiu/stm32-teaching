#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
整合评分引擎
Auto Grading Engine

以 rubric.json 为唯一事实来源，按每个 category 的 grading_method 派发：
- build         → BuildChecker（真实编译）
- code_analysis → EnhancedCodeAnalyzer（真实源码静态分析）
- keyword       → RubricGrader 逐准则关键词匹配
- manual        → 读 rubric default_points
- conditional   → 组长加分（基础分外）

每个 category 产出一个 CategoryScore；base 总分封顶 rubric.total_points(100)，
bonus（points_outside_base）单列；等级按 base/100 计算。

同时产出：
- validation_report：提交完整性校验（advisory，不改分）
- issues：结构化失分项（供直击式学生反馈）
- thinking_check：思考题 Q1~Q7 作答核对
"""

import math
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime

from .config import AutoGradingConfig
from .build_checker import BuildChecker, BuildResult, BuildStatus
from .submission_processor import ProcessedSubmission
from .submission_validator import SubmissionValidator, ValidationReport


# 编译"无法评估"的状态集合：这些情况下不应记为学生责任（不罚分、排除出总分），
# 仅 FAILED（真正编译出错）才计入失分。
_UNASSESSABLE_BUILD_STATES = frozenset({
    BuildStatus.SKIPPED,     # 工具链缺失 / 未提取到工程
    BuildStatus.NOT_FOUND,   # 工程无 Makefile / 无可编译目标（如纯 MDK-ARM 工程）
    BuildStatus.ERROR,       # 工具链执行错误
    BuildStatus.TIMEOUT,     # 编译超时
})


# 源码扫描防爆常量：_collect_source_text / _grade_source_check / _resolve_symbol_definers
# 等多处源码扫描共用同一口径。历史遗留：曾在每个函数里各自硬编码 80 与 512*1024，
# 一处分两处改就会出现"同一工程两次批阅结果不同"（受 MAX_FILES 截断 + rglob 顺序影响，
# 俗称"摇骰子"）。统一为单一事实源。
MAX_FILES = 80               # 单次扫描最多读取的源文件数
MAX_FILE_BYTES = 512 * 1024  # 单个源文件读取大小上限（512 KB）


# 厂商/第三方库目录标记：评分时只看学生自有代码，排除 ST HAL/CMSIS 等。
# HAL 库自身定义并使用 HAL_Delay（stm32f4xx_hal.c / _dsi.c / _eth.c …），若一并扫描，
# 任何包含 HAL 库的工程都会被判成"违反非阻塞"——这并非学生代码问题。任务检测与
# source_check 共用此清单，避免厂商代码污染学生侧评分。
_VENDOR_MARKERS = (
    '/STM32F4xx_HAL_Driver/', '/CMSIS/', '/Third_Party/',
    '/Libraries/', '/Middlewares/',
)


def _is_vendor_file(path) -> bool:
    """路径是否属于厂商/第三方库（按 POSIX 化后的全路径匹配目录标记）。"""
    fp = str(path).replace('\\', '/')
    return any(m in fp for m in _VENDOR_MARKERS)


@dataclass
class CategoryScore:
    """评分类别得分"""
    category_id: str           # 类别ID
    category_name: str         # 类别名称
    max_points: float          # 满分
    earned_points: float       # 得分
    details: List[Dict] = field(default_factory=list)  # 得分详情


@dataclass
class GradingResult:
    """评分结果"""
    student_id: str            # 学号
    name: str                  # 姓名
    class_name: str            # 班级

    # 评分
    total_score: float = 0.0   # 基础总分（封顶 max_score）
    max_score: float = 100.0   # 满分（rubric.total_points）
    bonus_total: float = 0.0   # 基础分外加分（如组长加分）
    is_team_leader: bool = False  # 报告是否声明作者为组长（驱动组长加分）
    leader_bonus_granted: float = 0.0  # 已发放的组长加分（grade_submission 先按唯一组长发全额；
                                       # dedupe_team_members 再按组真实人数校正：多组长平摊 / 无组长全员平摊）
    grade: str = "N/A"         # 等级（A/B/C/D/F）

    # 小组信息（同组共用同一份工程/报告；供反馈按组聚合）
    group_key: str = ""                     # 小组键（组长学号）；同组成员相同
    group_members: list = field(default_factory=list)  # [(学号, 姓名), ...]
    # 本组「各自提交了源码」的去重成员数（未单独提交者回退到组长源码，不计数）；≥2 时
    # 反馈层提示「同组只交一份」。0=未知/个人实验。全组同值，由 dedupe_team_members 盖章。
    group_submitter_count: int = 0
    # 本组「各自上传了报告」的去重人数（报告维度，= 组内结果数 ÷ 组员数）；≥2 时反馈提示
    # 「同组只交一份」。与 group_submitter_count(源码维度)互补——源码只交一份但报告各交各的
    # （如闫建铭/李全）也能被检出。全组同值，由 dedupe_team_members 盖章。
    group_reporter_count: int = 0

    # 任务感知（final-project：任选其一，难度系数缩放最终分）
    detected_task: str = ""                 # 任务键 task1/task2/task3（无任务 rubric 时为空）
    detected_task_name: str = ""            # 任务中文名
    detected_task_source: str = ""          # 检测来源 report/code/default
    detected_task_ambiguous: bool = False   # 任务判定不够权威（无显式声明且信号混杂/回退）→ 反馈提示核对
    evaluation_score: float = 0.0           # 评价分 /100（任务统一刻度）
    difficulty_ratio: float = 1.0           # 任务难度比（0.8/0.9/1.0）
    task_full_marks: float = 100.0          # 任务满分（80/90/100，= 难度比×100）

    # 各类别得分（每类一个，与 rubric 对齐）
    category_scores: List[CategoryScore] = field(default_factory=list)

    # 详细信息
    compilation_result: Optional[BuildResult] = None
    code_analysis: Optional[Dict] = None
    report_analysis: Optional[Dict] = None

    # 校验与反馈
    validation_report: Optional[ValidationReport] = None
    issues: List[Dict] = field(default_factory=list)        # 结构化失分项
    thinking_check: List[Dict] = field(default_factory=list)  # 思考题核对

    # 旧字段（兼容/汇总）
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    # 时间戳
    graded_at: datetime = field(default_factory=datetime.now)


# 视为"组长"的角色名（学生填表时可能用 主操作手 / 队长 等同义称呼）
_LEADER_TITLES = ("组长", "主操作手", "队长", "负责人", "项目负责")
# 预编译为正则 alternation，供 detect_team_leader 复用
_LEADER_TITLE_ALT = r'(?:' + '|'.join(re.escape(t) for t in _LEADER_TITLES) + r')'


# 自称为组长的句式（命中即判定作者为组长）
_LEADER_SELF_PATTERNS = [
    re.compile(r'担任组长'),
    re.compile(r'作为组长'),
    re.compile(r'我任组长'),
    re.compile(r'任组长'),
    re.compile(r'本人[^。\n]{0,6}组长'),
    re.compile(r'我[^。\n]{0,4}组长'),
    re.compile(r'我\s*[（(]\s*组长'),
    re.compile(r'组长[：:]\s*本人'),
    re.compile(r'组长[：:]\s*我(?!们)'),
]


def detect_team_leader(report_text: str, student_name: str) -> bool:
    """从实验报告文本判断"该学生"是否被声明为组长（含主操作手等同等角色）。

    小组报告会被多名成员共享（批阅时按团队展开），故必须按**姓名特异性**判定：
    - "组长：张三" / "主操作手：张三" 中的姓名 == 学生姓名 → True
    - "张三（组长）" / "张三（主操作手）" → True
    - 表式布局："<张三>\\n<学号>\\n<班级>\\n组长/主操作手" → True
    视为组长的角色见 _LEADER_TITLES（组长、主操作手、队长、负责人、项目负责）。
    文本级自称（"我担任组长"）无法归因到具体成员，仅在未提供姓名（单作者报告）
    时作退化判定；提供姓名时不使用，避免同组所有成员都被判为组长。
    只声明他人为组长，或完全未声明 → False。

    策略：实验报告模板已规定「组长」填写位，故姓名特异写法（组长：张三 / 张三（组长））
    是预期通道，无需再匹配散文自称。检测不到组长即视为该组选择将 +5 组长加分全员平分
    （见 _reconcile_leader_bonus：同组无人声明组长则全员平摊 ⌈leader_bonus/N⌉）。
    """
    if not report_text:
        return False
    if not student_name:
        # 无姓名（单作者报告）：退化为文本级自称
        return any(pat.search(report_text) for pat in _LEADER_SELF_PATTERNS)

    title_alt = _LEADER_TITLE_ALT  # (?:组长|主操作手|队长|负责人|项目负责)

    # 有姓名：仅按姓名特异性判定
    # 组长：张三 / 主操作手为张三 / 组长:张三
    for m in re.finditer(title_alt + r'[：:为是]\s*([^\s,，。、；;（(《<]{1,20})', report_text):
        tok = m.group(1)
        if student_name in tok or tok in student_name:
            return True
    # 张三（组长） / 张三（主操作手）
    for m in re.finditer(r'([一-龥A-Za-z·]{2,20})\s*[（(]\s*' + title_alt + r'\s*[）)]', report_text):
        if m.group(1) == student_name:
            return True
    # 表式布局兜底：docx 表格竖排，"<姓名>\n<学号>\n<班级>\n组长/主操作手"
    # （姓名后 1~4 行内出现作为独立单元格的角色名）
    if re.search(re.escape(student_name) + r'[^\n]*(?:\n[^\n]*){0,3}\n\s*' + title_alt + r'\b', report_text):
        return True
    return False


# ============================================================
# 任务检测（final-project：学生任选 task1/task2/task3 之一）
# ============================================================
def _collect_source_text(submission: "ProcessedSubmission", cache: Dict[Path, str]) -> str:
    """拼接工程内源/头文件文本（按 source_path 缓存），供任务检测/代码分析复用。
    遍历口径与 _grade_code_quality/_grade_source_check 一致，带文件数与单文件大小上限。"""
    sp = getattr(submission, 'source_path', None)
    pi = getattr(submission, 'project_info', None)
    if not sp or not pi:
        return ""
    sp = Path(sp)
    if sp in cache:
        return cache[sp]
    parts: List[str] = []
    files = list(getattr(pi, 'main_files', [])) \
            + list(getattr(pi, 'source_files', [])) \
            + list(getattr(pi, 'header_files', []))
    # 厂商/第三方库目录（HAL/CMSIS/...）含 HAL_RTC、ADC、BKP 等全部信号，会让"源码信号"
    # 兜底把任何 CubeMX 工程都误判成 task3/2。任务检测只看学生自己的 Core/User 代码。
    for f in files[:MAX_FILES]:
        try:
            if f.stat().st_size > MAX_FILE_BYTES:
                continue
            if _is_vendor_file(f):
                continue
            parts.append(f.read_text(encoding='utf-8', errors='ignore'))
        except Exception:
            continue
    text = "\n".join(parts)
    cache[sp] = text
    return text


# 任务显式声明：choose-动词 + 紧邻的"任务X"，权威判定学生所选任务。必须先于
# report_declare 关键字——后者会把"在任务一/二/三中选择了实验任务一"里的列举词
# "任务三"误判为 task3。负向 lookbehind 排除"没/不/未选择任务三"这类否定。
_DECLARE_RE = re.compile(
    r'(?<![没不未勿])'
    r'(?:选择|选定|选做|选用|选取|选了|确定|最终确定|决定|所选|所做|所取|做的是|题目是|题为|本任务[是为])'
    r'[^\n。；;,，]{0,18}?'
    r'(任务[一二三123])'
)


def _report_main_body(text: str) -> str:
    """砍掉「思考题」段，只留正文供任务检测。

    思考题（含扩展思考）里常顺带提及其他任务号（"如果做任务三…"），会让关键字
    误判。思考题一般在报告末尾，取首个"思考题"为切点；距开头太近（<200 字，疑似
    目录/前言）则不切。无思考题段则返回原文。
    """
    if not text:
        return ''
    m = re.search(r'思考题', text)
    if m and m.start() > 200:
        return text[:m.start()]
    return text


def detect_task(submission: "ProcessedSubmission",
                rubric: Dict,
                source_cache: Dict[Path, str]) -> Tuple[str, str]:
    """检测学生所选任务，返回 (task_key, source, ambiguous)。

    source ∈ {'report','code','default'}；ambiguous=True 表示判定不够权威（未见显式
    "选择任务X"声明、且多个任务特征信号并存，或回退到源码/默认），反馈层据此提示学生/教师核对。

    优先级：
    1. 显式声明（"选择了任务X"等 choose-动词 + 任务号；正文优先，已砍思考题）→ 'report', 不 ambiguous
    2. 关键字声明（report_declare 词命中正文，按 priority）→ 'report'；多于一个任务的关键字都命中
       → 信号混杂 → ambiguous=True（如聂智聪组：转向灯 与 RTC/任务三 并存）
    3. 源码信号（学生自有代码 HAL_RTC/闹钟→task3；HAL_ADC/温度→task2；已排除 HAL/CMSIS 厂商库）
       → 'code', ambiguous=True（无任何报告信号，不够权威）
    4. fallback（默认 task1）→ 'default', ambiguous=True

    显式声明先于关键字：避免"在任务一/二/三中选择了实验任务一"里的列举词"任务三"
    把实际做的 task1 误判成 task3。报告（作者意图）先于源码。
    """
    td = (rubric or {}).get('task_detection') or {}
    priority = td.get('priority', ['task3', 'task2', 'task1'])
    declare = td.get('report_declare') or {}
    signals = td.get('code_signals') or {}
    fallback = td.get('fallback', 'task1')

    text = getattr(submission, 'report_text', '') or ''
    main = _report_main_body(text)

    # 1) 显式声明优先（choose-动词 + 任务X）——作者意图，权威。必须先于关键字：
    #    关键字会把"在任务一/二/三中选择了实验任务一"里的列举词"任务三"误判为 task3。
    m = _DECLARE_RE.search(main) or _DECLARE_RE.search(text)
    if m:
        tn = m.group(1)
        tk = 'task1' if tn in ('任务一', '任务1') else 'task2' if tn in ('任务二', '任务2') else 'task3'
        return tk, 'report', False

    # 2) 关键字声明：只扫正文（已砍思考题段），按 priority 顺序。
    #    多于一个任务的关键字都命中 → 信号混杂，标记 ambiguous 供反馈提示核对。
    present = [tk for tk in priority
               if any(kw and kw in main for kw in declare.get(tk, []))]
    if present:
        return present[0], 'report', len(present) > 1

    # 3) 源码信号（_collect_source_text 已排除 HAL/CMSIS 等厂商库，避免样板误触）
    #    走到这说明报告里毫无任务信号，不够权威 → ambiguous
    code = _collect_source_text(submission, source_cache)
    if code:
        for tk in priority:
            for kw in signals.get(tk, []):
                if kw and kw in code:
                    return tk, 'code', True

    # 4) 默认
    return fallback, 'default', True


def _grade_from_scale(score: float, grading_scale: Dict) -> str:
    """按 grading_scale 定级：半开区间匹配（按 min 降序），消除 B.max=89.9/A.min=90 之类
    边界缝隙；与 RubricGrader._calculate_grade 语义一致。供 dedupe 校正后重定级复用。"""
    for grade, info in sorted(grading_scale.items(), key=lambda x: x[1]['min'], reverse=True):
        if score >= info['min']:
            return grade
    return 'F'


def _grade_default(score: float, max_score: float) -> str:
    """无 grading_scale 时的默认百分制定级。"""
    percentage = (score / max_score) * 100 if max_score > 0 else 0
    if percentage >= 90:
        return 'A'
    elif percentage >= 80:
        return 'B'
    elif percentage >= 70:
        return 'C'
    elif percentage >= 60:
        return 'D'
    else:
        return 'F'


def _adjust_leader_bonus(result: GradingResult, new_granted: float, grading_scale: Optional[Dict]) -> None:
    """把 result 的组长加分从临时全额(leader_bonus_granted)改为 new_granted，并重算评价分/总分/等级。

    评价分先扣回临时加分还原「加分前评价分」(已按可评基数折算)，再加 new_granted(封顶 100)；
    bonus_total 同步替换；total_score = 评价分 × 难度系数；等级按总分重定。
    """
    old_granted = float(result.leader_bonus_granted or 0.0)
    eval_pre = result.evaluation_score - old_granted        # 加分前评价分
    headroom = max(100.0 - eval_pre, 0.0)
    granted = round(min(float(new_granted), headroom), 1)
    new_eval = round(min(eval_pre + granted, 100.0), 1)
    result.evaluation_score = new_eval
    result.total_score = round(new_eval * result.difficulty_ratio, 1)
    result.bonus_total = round(result.bonus_total - old_granted + granted, 1)
    result.leader_bonus_granted = granted
    if grading_scale:
        result.grade = _grade_from_scale(result.total_score, grading_scale)
    else:
        result.grade = _grade_default(result.total_score, 100.0)


def _reconcile_leader_bonus(results, rubric: Dict) -> None:
    """按组校正组长加分（由 dedupe_team_members 在去重后调用）。

    - 同组多名组长(>=2)：每人加分 = ⌈leader_bonus / 组长人数⌉（2人→3、3人→2）；
    - 同组无人声明组长（含单人组）：视作全员组长，每人加分 = ⌈leader_bonus / 人数⌉
      （单人 = ⌈5/1⌉ = 5，封顶 100，评价分接近满分时实得可能 <5）；
    - 唯一组长：不动（grade_submission 的临时全额即正确）。
    校正后给每位受影响者追加说明性 issue（type=submission，machine/teacher 可读；不进学生必改区）。
    """
    try:
        leader_bonus = float(rubric.get('leader_bonus', 0) or 0)
    except (TypeError, ValueError):
        leader_bonus = 0.0
    if leader_bonus <= 0:
        return
    grading_scale = rubric.get('grading_scale')

    # 按 (班级, 组键) 聚合本组去重后的成员（含单人组：无人声明组长时也按规则平摊）
    groups: Dict[Tuple[str, str], List[GradingResult]] = {}
    for r in results:
        members = getattr(r, 'group_members', None) or []
        if getattr(r, 'group_key', '') and len(members) >= 1:
            groups.setdefault((r.class_name, r.group_key), []).append(r)

    for (cls, gk), members in groups.items():
        leaders = [m for m in members if m.is_team_leader]
        if leaders:
            if len(leaders) == 1:
                continue  # 唯一组长：临时全额加分即正确，无需校正
            recipients, scenario = leaders, 'multi'
        else:
            recipients, scenario = members, 'none'       # 无组长 → 全员平摊
        num = len(recipients)
        per_leader = math.ceil(leader_bonus / num)        # ⌈5/2⌉=3, ⌈5/3⌉=2
        names = ", ".join(f"{m.name}({m.student_id})" for m in recipients)
        for m in recipients:
            old_granted = float(m.leader_bonus_granted or 0.0)
            _adjust_leader_bonus(m, per_leader, grading_scale)
            new_granted = m.leader_bonus_granted
            if scenario == 'multi':
                msg = (f"同组({gk})检测到 {num} 名组长：{names}；按规则组长加分 = "
                       f"⌈{leader_bonus:g}/{num}⌉ = {per_leader}，已据此校正"
                       f"（原 +{old_granted:g} → +{new_granted:g}）。")
                fix = "每组宜仅一人任组长；已按人数平摊如实发放加分，无需额外操作。"
                criterion, expected = "同组组长加分平摊", "每组一名组长"
            else:  # none
                msg = (f"本组({gk})报告未声明组长；按规则视作全员({num}人)组长，组长加分 = "
                       f"⌈{leader_bonus:g}/{num}⌉ = {per_leader}，已据此发放（+{new_granted:g}）。")
                fix = "建议在报告「团队信息与分工」中明确组长，以免加分被平摊。"
                criterion, expected = "未声明组长·全员平摊", "明确组长归属"
            m.issues.append({
                "type": "submission",
                "category": "组长归属",
                "criterion": criterion,
                "points_lost": 0,
                "severity": "info",
                "message": msg,
                "fix": fix,
                "expected": expected,
            })


def _names_look_like_same_person(a: str, b: str) -> bool:
    """两个姓名是否像「同一人的不同写法」（同名异写）而非两个不同的人。

    判据：姓名汉字集合重合度高——共有的不同汉字数 ≥ 较长名长度 − 1。
    - 畅邵坤/畅绍坤、聂智聪/聂志聪 → True（同人，差异为同音/形近异写）
    - 安晓童/王倩倩、申凯丽/张丽娟 → False（不同人，无共同汉字）

    用于「学号重号」检测时过滤同名异写，避免对同一人误报。
    """
    ca, cb = set(a or ""), set(b or "")
    if not ca or not cb:
        return False
    return len(ca & cb) >= max(len(ca), len(cb)) - 1


def dedupe_team_members(results: List[GradingResult], rubric: Optional[Dict] = None) -> List[GradingResult]:
    """按学号去重评分结果。

    小组按成员展开后，同一学生可能出现在多份上传报告中（学习通「按人导出」，
    同组成员各自上传）。去重规则：

    1. **优先自评归因**：若该生有「自己提交的源码」对应的结果（学号命中源码目录名，
       即源码目录形如 ``{班级}-{学号}-{姓名}-源代码``），则保留自评那条——避免被
       判到队友的源码上、反馈与本人提交不符。仅当该生仅作为组员出现（无自己源码）
       时，才回退到最高分（共享组长源码）。
    2. **同组勿重复提交提醒**：若该生关联了 >1 个**不同**源码目录（多人各自上传了
       不同版本），在反馈 issues 中追加提醒，引导「同组由组长一人提交」。
    3. **组长加分按组人数校正**（传 rubric 且 leader_bonus>0 时生效）：grade_submission
       先按「唯一组长」给每人发了临时全额加分；此处按组真实情况校正——
       同组多名组长：加分 = ⌈leader_bonus / 组长人数⌉（如 2 人 → 3、3 人 → 2）；
       全组无人声明组长（含单人组）：视作全员组长，加分 = ⌈leader_bonus / 人数⌉（单人 = ⌈5/1⌉ = 5）；
       唯一组长：不校正。校正后重算评价分/总分/等级，并追加说明性 issue。

    对个人实验（无团队成员表、不展开）为空操作。自检/单提交路径不传 rubric → 不校正。
    """
    def _source_token(r: GradingResult) -> str:
        """该结果所用源码目录名（= 报告组长的源码包）；无源码返回 ''。"""
        pp = getattr(r.compilation_result, "project_path", None) if r.compilation_result else None
        try:
            return Path(pp).name if pp else ""
        except Exception:
            return ""

    def _is_self_sourced(r: GradingResult) -> bool:
        """该结果是否用的是「该生自己提交的源码」（学号在源码目录名中）。"""
        return bool(r.student_id) and r.student_id in _source_token(r)

    # 按学号分组
    by_id: Dict[str, List[GradingResult]] = {}
    for r in results:
        by_id.setdefault(r.student_id, []).append(r)

    best: Dict[str, GradingResult] = {}
    for sid, rs in by_id.items():
        if len(rs) == 1:
            best[sid] = rs[0]
            continue
        # 多份：优先自评；同为自评或同为非自评时再比最高分
        self_rs = [r for r in rs if _is_self_sourced(r)]
        pool = self_rs if self_rs else rs
        best[sid] = max(pool, key=lambda r: (r.total_score, r.bonus_total))

    # 同组勿重复提交：该生关联了 >1 个不同源码目录 → 追加提醒（advisory，不扣分）
    for sid, rs in by_id.items():
        tokens = {_source_token(r) for r in rs if _source_token(r)}
        if len(tokens) > 1 and sid in best:
            best[sid].issues.append({
                "type": "submission",
                "category": "提交规范",
                "criterion": "同组勿重复提交",
                "points_lost": 0,
                "severity": "info",
                "message": "检测到你的学号关联了多份不同的源码提交（同组多人各自上传了不同版本）。",
                "fix": "同组只需由组长提交一份报告 + 一份源码；组员不必各自重复上传，以免机器批阅归因混乱、反馈与本人提交不符。",
                "expected": "每组一份报告 + 一份源码",
            })

    # 学号重号检测：同一学号关联 ≥2 个不同姓名，且并非全是「同名异写(同一人)」
    # → 在**幸存**的 best[sid] 上盖告警（写在被并掉的那条上会随它一起丢失）。
    # 不改变去重行为（仍按学号取一份）；重号是上游数据错误，工具不擅自决定保留谁，
    # 只提示教师核定归属（与既有 type=submission advisory 一致，不进学生必改区）。
    for sid, rs in by_id.items():
        names: List[str] = []
        for r in rs:
            n = (r.name or "").strip()
            if n and n not in names:
                names.append(n)
        if len(names) < 2:
            continue
        # 所有姓名两两都像同一人 → 同名异写，不告警
        if all(_names_look_like_same_person(names[i], names[j])
               for i in range(len(names)) for j in range(i + 1, len(names))):
            continue
        if sid in best:
            best[sid].issues.append({
                "type": "submission",
                "category": "学号重号",
                "criterion": "疑似学号重号",
                "points_lost": 0,
                "severity": "warning",
                "message": (f"学号 {sid} 同时关联多个不同姓名（{' / '.join(names)}），"
                            f"疑为学号重号，**可能导致评分异常**（另一人评分被并掉）。请联系教师核对学号归属。"),
                "fix": "请教师核对该学号的真实归属；若为重号，更正其中一方学号后重评即可。",
                "expected": "一个学号对应一名学生",
            })

    # 组长加分按组人数校正（任务书约定）。grade_submission 已按「唯一组长」给每人发了临时
    # 全额加分(leader_bonus_granted)；这里按组真实人数回扣/补发：多组长平摊、无组长全员平摊。
    # 唯一组长/单人组不校正。仅在传入 rubric(含 leader_bonus)时生效。
    if rubric is not None:
        _reconcile_leader_bonus(best.values(), rubric)

    # 本组「各自提交了源码」的去重成员数：组内 best 结果里非空 _source_token 的去重数。
    # 未单独提交者会回退到组长源码（_is_self_sourced=False），不增加去重 token，故该值
    # 即"真正上传过源码的人数"；≥2 时反馈层据此提示"同组只交一份"。全组各成员同值。
    _group_tokens: Dict[str, set] = {}
    for r in best.values():
        if r.group_key:
            tok = _source_token(r)
            if tok:
                _group_tokens.setdefault(r.group_key, set()).add(tok)
    for r in best.values():
        if r.group_key:
            r.group_submitter_count = len(_group_tokens.get(r.group_key, ()))

    # 同组「各自上传了报告」的去重人数（报告维度）：每份报告按团队展开为(组员数)条结果，
    # 故 组内结果数 ÷ 组员数 ≈ 上传报告的人数。≥2 时反馈提示"同组只交一份"。与源码维度
    # (group_submitter_count)互补——源码只交一份但报告各交各的(如 闫建铭/李全)也能被检出。
    _group_entry_count: Dict[str, int] = {}
    _group_member_set: Dict[str, set] = {}
    for r in results:
        if r.group_key:
            _group_entry_count[r.group_key] = _group_entry_count.get(r.group_key, 0) + 1
            _group_member_set.setdefault(r.group_key, set()).add(r.student_id)
    for r in best.values():
        if r.group_key:
            mc = len(_group_member_set.get(r.group_key, ()))
            ec = _group_entry_count.get(r.group_key, 0)
            r.group_reporter_count = (ec // mc) if mc else 1

    # 按首次出现顺序输出
    seen = set()
    out = []
    for r in results:
        if r.student_id in seen:
            continue
        seen.add(r.student_id)
        out.append(best[r.student_id])
    return out


def _resolve_symbol_definers(symbols, source_files, source_path):
    """对每个未定义符号，在学生自有 .c 源码里找它的函数定义所在文件。

    返回 {symbol: [相对路径...]}。仅匹配**函数定义头**（行尾非分号、形如
    ``ret sym(...) {``），从而区分定义与调用/声明；排除厂商库。
    """
    definers = {}
    if not symbols or not source_files:
        return definers
    non_vendor = [f for f in source_files
                  if not _is_vendor_file(f) and f.suffix.lower() == '.c']
    for sym in symbols:
        if not sym:
            continue
        # 要求"返回类型 + sym(" 才算定义头（排除裸调用）；不锚定行尾以兼容单行定义
        # `void sym(...){ ... }`；行尾分号(声明/调用语句)跳过。
        rx = re.compile(rf'^[\w\s\*\[\]]*?\b\w+\s+\*?{re.escape(sym)}\s*\(')
        for f in non_vendor:
            try:
                if f.stat().st_size > MAX_FILE_BYTES:
                    continue
                text = f.read_text(encoding='utf-8', errors='ignore')
                disp = str(f.relative_to(source_path)).replace('\\', '/')
            except Exception:
                continue
            for line in text.splitlines():
                if line.rstrip().endswith(';'):
                    continue
                if rx.match(line):
                    definers.setdefault(sym, []).append(disp)
                    break
    return definers


def _makefile_c_sources(source_path) -> set:
    """读 Makefile 的 C_SOURCES 变量，返回归一化相对路径集合（如 Core/Src/key.c）。

    无 Makefile 或解析失败返回空集（调用方据此退化为"按文件名匹配"）。
    """
    mk = Path(source_path) / 'Makefile'
    if not mk.is_file():
        return set()
    try:
        if mk.stat().st_size > MAX_FILE_BYTES:
            return set()
        text = mk.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return set()
    out = set()
    in_block = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('C_SOURCES') and '=' in s:
            in_block = True
            s = s.split('=', 1)[-1].strip()
        if in_block:
            for tok in re.findall(r'\.?/?([^\s]+\.c)', s):
                out.add(tok.lstrip('./').lstrip('/'))
            if not line.rstrip().endswith('\\'):
                in_block = False
    return out


def _diagnose_missing_sources(undefined_symbols, submission) -> str:
    """链接失败时：把 undefined reference 符号定位到学生工程里定义它们的 .c，
    并指出这些文件未列入 Makefile 的 C_SOURCES。返回可直接拼进 fix 的句子（或 ''）。

    失败必返回 ''——反馈增强绝不影响批阅主流程。
    """
    try:
        pi = getattr(submission, 'project_info', None)
        sp = getattr(submission, 'source_path', None)
        source_files = list(getattr(pi, 'source_files', []) or [])
        if not undefined_symbols or not source_files or not sp:
            return ''
        sp = Path(sp)
        definers = _resolve_symbol_definers(undefined_symbols, source_files, sp)
        if not definers:
            return ''
        c_sources = _makefile_c_sources(sp)
        cs_basenames = {Path(c).name for c in c_sources}
        file_syms = {}                       # file_rel -> [symbols]
        for sym, files in definers.items():
            for fr in files:
                file_syms.setdefault(fr, []).append(sym)
        missing = []                         # 定义了符号、却未在 C_SOURCES 的文件
        for fr, syms in file_syms.items():
            in_cs = (not c_sources) or (fr in c_sources) or (Path(fr).name in cs_basenames)
            if not in_cs:
                missing.append((fr, syms))
        if not missing:
            pos = "; ".join(f"{fr} 定义了 {', '.join(syms)}" for fr, syms in sorted(file_syms.items())[:4])
            return f"（这些符号在你的源码里有定义：{pos}；请检查函数签名是否一致、工程是否需要重新生成。）"
        parts = [f"{fr}（定义 {', '.join(sorted(set(syms)))}）" for fr, syms in sorted(missing)[:4]]
        return ("（已定位：未定义的符号其实在你的源码里有定义，但对应文件未参与编译——"
                "请把以下 .c 加入 Makefile 的 C_SOURCES 后重新生成/编译：" + "；".join(parts) + "。）")
    except Exception:
        return ''


def _detect_blocking_wrappers(source_path, files):
    """检测"封装了 HAL_Delay 的阻塞延时函数"及其调用点。

    学生常把 HAL_Delay 包一层（如 ``HAL_Delay_ms()``）再在主循环调用，仅匹配字面
    ``HAL_Delay(`` 会漏掉这些间接调用。本函数：

    1. 逐文件按括号深度切出每个函数体，凡函数体内出现 ``HAL_Delay(`` 即记为封装函数；
    2. 再统计这些封装函数在全工程被调用的位置。

    返回 (wrappers, indirect_violations)：
    - wrappers: {func_name: 'file:line'}（封装函数定义处）
    - indirect_violations: [{file, line, wrapper}]（封装函数的调用点，不含其自身定义行）

    失败必返回 ({}, [])——绝不影响批阅主流程。
    """
    try:
        direct_re = re.compile(r'HAL_Delay\s*\(')
        # 函数定义头：[修饰] 返回类型 name(args) 可选 { ——要求"有返回类型前缀"，
        # 故裸调用/控制关键字不会命中；不锚定行尾，兼容单行定义 `void f(...){ ... }`。
        header_re = re.compile(
            r'^[ \t]*(?:static[ \t]+|extern[ \t]+|inline[ \t]+)*'
            r'[\w\*][\w\*\s\[\]]*?\s+\*?(\w+)\s*\([^;]*\)\s*\{?'
        )
        _CONTROL = {'if', 'for', 'while', 'switch', 'return', 'else', 'do', 'sizeof'}

        def _disp(f):
            try:
                return str(f.relative_to(source_path)).replace('\\', '/')
            except Exception:
                return f.name

        wrappers = {}            # name -> "disp:def_line"（候选：体内含 HAL_Delay；下方按"是否被调用"再筛）
        wrapper_ranges = {}      # name -> (disp, def_line, end_line)
        # 第一遍：找封装函数（函数体含 HAL_Delay）
        for f in files:
            try:
                if f.stat().st_size > MAX_FILE_BYTES:
                    continue
                text = f.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            disp = _disp(f)
            lines = text.splitlines()
            i = 0
            while i < len(lines):
                m = header_re.match(lines[i])
                if not m or m.group(1) in _CONTROL:
                    i += 1
                    continue
                name = m.group(1)
                # 前向声明（行尾分号）不是定义，跳过
                if lines[i].rstrip().endswith(';'):
                    i += 1
                    continue
                # 定位函数体起点 { ：同行(K&R) 或下一非空行(Allman)；都没有则放弃
                if '{' in lines[i]:
                    body_start = i
                else:
                    k = i + 1
                    while k < len(lines) and lines[k].strip() == '':
                        k += 1
                    if k < len(lines) and lines[k].lstrip().startswith('{'):
                        body_start = k
                    else:
                        i += 1
                        continue
                # 从 body_start 按括号深度取整个函数体
                depth = 0
                seen_open = False
                j = body_start
                while j < len(lines):
                    ln = lines[j]
                    opens, closes = ln.count('{'), ln.count('}')
                    if opens:
                        seen_open = True
                    depth += opens - closes
                    if seen_open and depth <= 0:
                        break
                    j += 1
                body = '\n'.join(lines[i:j + 1])
                if direct_re.search(body):
                    wrappers[name] = f"{disp}:{i + 1}"
                    wrapper_ranges[name] = (disp, i + 1, j + 1)   # 1-based 首尾行
                i = j + 1 if j > i else i + 1

        # 第二遍：统计封装函数的调用点（排除定义行、前向声明/原型、注释行）
        indirect = []
        if wrappers:
            call_res = {nm: re.compile(rf'\b{re.escape(nm)}\s*\(') for nm in wrappers}
            # 前向声明/原型行：有"返回类型 + name(args) + ;"（与第一遍同口径），
            # 不应被当成调用点（否则 .c/.h 里的原型会让 indirect 虚高）。
            decl_res = {nm: re.compile(
                rf'^\s*(?:static\s+|extern\s+|inline\s+)*[\w\*][\w\*\s\[\]]*?\s+\*?{re.escape(nm)}\s*\([^;]*\)\s*;'
            ) for nm in wrappers}
            defsites = set(wrappers.values())
            for f in files:
                try:
                    if f.stat().st_size > MAX_FILE_BYTES:
                        continue
                    text = f.read_text(encoding='utf-8', errors='ignore')
                except Exception:
                    continue
                disp = _disp(f)
                for ln, raw in enumerate(text.splitlines(), start=1):
                    if f"{disp}:{ln}" in defsites:
                        continue
                    line = re.sub(r'//.*$', '', raw)   # 去行尾注释，避免注释里提到 name() 被误计
                    for nm, rx in call_res.items():
                        if decl_res[nm].match(raw):
                            continue                   # 该行是 nm 的前向声明/原型，非调用
                        for _mm in rx.finditer(line):  # 同行多次调用逐个计
                            indirect.append({'file': disp, 'line': ln, 'wrapper': nm})

        # 只把"被调用过"的封装函数当成 wrapper：它的违例按调用点计、体内 HAL_Delay 不重复计。
        # 体内含 HAL_Delay 但**无人调用**的函数（如 main，或一次性业务函数）不算封装——
        # 其体内 HAL_Delay 直接计为违例（否则会被误排除而漏判）。
        called = {v['wrapper'] for v in indirect}
        wrappers = {nm: loc for nm, loc in wrappers.items() if nm in called}
        body_ranges = [wrapper_ranges[nm] for nm in wrappers]
        return wrappers, indirect, body_ranges
    except Exception:
        return {}, [], []


def _summarize_build_failure(br: BuildResult, submission: Optional["ProcessedSubmission"] = None) -> Tuple[str, str]:
    """把编译失败结果转成 (给学生看的反馈句, 改进建议句)。

    优先用 build_result.issues 里的真实诊断（编译错误 / 链接错误 / Makefile 语法错误），
    让学生看到具体错在哪；只有提取不到任何诊断时才回退到笼统提示。改进建议按主要错误
    类别给出可操作方向（链接失败→补 C_SOURCES/函数实现；Makefile 错误→重新生成/Tab 缩进；
    编译错误→补头文件/修拼写）。
    """
    # 真实 error 诊断，按描述去重，最多取 3 条，附定位（链接/Makefile 不带行号则只取描述）
    errs: List[str] = []
    seen: set = set()
    for it in (getattr(br, 'issues', None) or []):
        if getattr(it, 'severity', '') != 'error':
            continue
        desc = (getattr(it, 'message', '') or '').strip()
        if not desc:
            continue
        key = desc[:60]
        if key in seen:
            continue
        seen.add(key)
        has_loc = bool(getattr(it, 'line', 0)) and getattr(it, 'file', '') \
            and not str(it.file).lower().endswith('.exe') and it.file not in ('ld', 'Makefile')
        errs.append(f"{it.file}:{it.line}: {desc}" if has_loc else desc)

    joined = "；".join(errs[:3])
    more = f"（共 {br.error_count} 处）" if br.error_count > len(errs) and errs else ""
    if joined:
        feedback = f"编译失败：{joined}{more}"
    elif br.error_message:
        feedback = f"编译失败：{br.error_message}"
    else:
        feedback = "编译失败：未识别错误（未见 GCC/链接器诊断，可能为环境问题，请联系教师核对）"

    # 改进建议：按主要错误类别
    blob = (joined + "\n" + (getattr(br, 'output', '') or '')).lower()
    if 'undefined reference' in blob or 'ld returned' in blob or 'cannot find -l' in blob \
            or 'multiple definition' in blob:
        fix = ('链接失败：通常是 Makefile 的 C_SOURCES 漏加了某个 .c 源文件，或调用了未实现/'
               '未包含的函数。请把缺失的源文件加入 Makefile，或补全被引用函数的实现。')
        # 详细定位：把 undefined reference 符号对应到学生工程里定义它们的 .c，
        # 并指出这些文件未列入 Makefile 的 C_SOURCES（高雅梅：4 个自建模块漏列）。
        if submission is not None and 'undefined reference' in blob:
            syms = []
            for e in errs:
                mm = re.search(r"undefined reference to [`'\"]*(\w+)", e)
                if mm and mm.group(1) not in syms:
                    syms.append(mm.group(1))
            extra = _diagnose_missing_sources(syms, submission)
            if extra:
                fix = fix + ' ' + extra
    elif 'missing separator' in blob or re.search(r'\*\*\*.+?stop\.', blob):
        # Makefile 语法错误签名是 `*** ... Stop.`（missing separator / No rule to make target）。
        # 不能用裸 `*** ` 判：普通编译/链接失败结尾都有 `make: *** [target] Error N`，会误判。
        fix = ('Makefile 格式错误（配方行用了空格而非 Tab 等）。请用 STM32CubeMX 重新生成 '
               'Makefile，或检查 Makefile 配方行均以 Tab 缩进；勿用空格。')
    elif errs:
        fix = '请按上面的错误信息修正源码：常见为缺少头文件包含、符号拼写错误、类型/函数未定义。'
    else:
        fix = '请在本机用 arm-none-eabi-gcc + make 复现编译，按报错修正后重新提交。'
    return feedback, fix


class AutoGradingEngine:
    """自动评分引擎（rubric 驱动）"""

    def __init__(
        self,
        config: Optional[AutoGradingConfig] = None,
        rubric_path: Optional[Path] = None
    ):
        self.config = config or AutoGradingConfig()
        self.rubric_path = rubric_path

        # 初始化子模块
        self.build_checker = BuildChecker(self.config)
        self.validator = SubmissionValidator()
        # 编译结果缓存（按 source_path）：小组成员共享同一工程，避免重复编译
        self._build_cache: Dict[Path, BuildResult] = {}

        # 延迟导入（避免循环依赖）
        try:
            from ..plagiarism.code_analysis.code_analyzer import EnhancedCodeAnalyzer
            from ..plagiarism.grading.grading import RubricGrader

            self.code_analyzer = EnhancedCodeAnalyzer
            self.rubric_grader = RubricGrader
        except ImportError as e:
            print(f"警告: 无法导入评分模块: {e}")
            self.code_analyzer = None
            self.rubric_grader = None

        # 加载并自检评分标准
        self.rubric = None
        if rubric_path and rubric_path.exists():
            self.rubric = self._load_rubric(rubric_path)

    # --------------------------------------------------------------
    # rubric 加载与自检
    # --------------------------------------------------------------
    def _load_rubric(self, rubric_path: Path) -> Dict:
        import json
        with open(rubric_path, 'r', encoding='utf-8') as f:
            rubric = json.load(f)
        self._validate_rubric(rubric)
        return rubric

    def _validate_rubric(self, rubric: Dict):
        """加载期 rubric 自检：base 分值和 == total_points；id 唯一；keyword 准则有关键词。"""
        cats = rubric.get('categories', [])
        ids = [c.get('id') for c in cats]
        dup = [i for i in set(ids) if ids.count(i) > 1]
        if dup:
            raise ValueError(f"rubric 类别 id 重复: {dup}")

        if 'task_difficulty' in rubric:
            # 任务 rubric：统一 /100，校验 categories points 和 == 100
            total = sum(c.get('points', 0) for c in cats)
            if abs(total - 100) > 0.01:
                raise ValueError(
                    f"任务 rubric 类别分值和({total}) != 100；请检查 data/rubrics/final-project.json")
            # 校验难度系数
            for tk, ratio in (rubric.get('task_difficulty') or {}).items():
                if not (0 < float(ratio) <= 1.0):
                    raise ValueError(f"任务难度比非法 {tk}={ratio}，须在 (0,1]")
        else:
            total_points = rubric.get('total_points', 100)
            base_sum = sum(c.get('points', 0) for c in cats if not c.get('points_outside_base'))
            if abs(base_sum - total_points) > 0.01:
                raise ValueError(
                    f"rubric 基础分值和({base_sum}) != total_points({total_points})；"
                    f"请检查 data/rubrics/rubric.json"
                )

        for c in cats:
            if c.get('grading_method', 'keyword') == 'keyword':
                for crit in c.get('criteria', []):
                    # keywords 或 keywords_by_task 至少有一个
                    if not crit.get('keywords') and not crit.get('keywords_by_task'):
                        print(f"警告: 准则 '{crit.get('description')}' 未配置 keywords")

    # --------------------------------------------------------------
    # 主评分入口
    # --------------------------------------------------------------
    def _resolve_task_active_rubric(self, submission: ProcessedSubmission,
                                    result: GradingResult) -> Dict:
        """任务感知：按学生所选任务构造 active_rubric 并设置 result 的任务相关字段。

        - 任务 rubric（含 task_difficulty）：detect_task 定任务 → 建 active_rubric（统一 /100
          刻度，keyword 准则按任务取，避免跨任务误扣）→ 设 detected_*/difficulty_ratio/
          task_full_marks；报告声明与源码信号冲突时追加 advisory issue。
        - 非任务 rubric（07-car-gear 等）：active_rubric = self.rubric，行为零变化。
        """
        self._source_cache: Dict[Path, str] = getattr(self, '_source_cache', {})
        if 'task_difficulty' in self.rubric:
            task_key, task_src, task_ambiguous = detect_task(submission, self.rubric, self._source_cache)
            result.detected_task = task_key
            result.detected_task_source = task_src
            result.detected_task_ambiguous = task_ambiguous
            task_names = {'task1': '任务一·多功能灯光系统',
                          'task2': '任务二·温度报警系统',
                          'task3': '任务三·定时迎宾灯系统'}
            result.detected_task_name = (self.rubric.get('task_names') or {}).get(task_key) \
                                        or task_names.get(task_key, task_key)
            result.difficulty_ratio = float(self.rubric['task_difficulty'].get(task_key, 1.0))
            result.task_full_marks = round(result.difficulty_ratio * 100, 1)
            active_rubric = self._build_task_active_rubric(task_key)
            self._active_rubric = active_rubric
            # 声明与源码信号冲突（报告说任务A、代码像任务B）→ advisory 提示教师关注
            if task_src == 'report':
                code_task, _, _ = detect_task(
                    submission, {**self.rubric, 'task_detection': {
                        **(self.rubric.get('task_detection') or {}),
                        'report_declare': {}}}, self._source_cache)
                if code_task not in (task_key, self.rubric.get('task_detection', {}).get('fallback', 'task1')):
                    result.issues.append({
                        'type': 'submission', 'category': '任务识别',
                        'criterion': '报告声明与源码不一致', 'points_lost': 0,
                        'severity': 'info',
                        'message': f"报告声明为 {result.detected_task_name}，但源码更像 {code_task}；已按报告声明评分，请教师复核。",
                        'fix': '若实际做的是另一任务，请修正报告「所选任务」说明。', 'expected': '',
                    })
        else:
            self._active_rubric = self.rubric
            active_rubric = self.rubric
        return active_rubric

    def _finalize_scores(self, result: GradingResult, base_earned: float,
                         bonus_total: float, excluded_points: float,
                         is_leader: bool) -> None:
        """汇总与定级：base_earned/excluded_points/is_leader → result 的 total/max/grade/eval/leader_bonus/bonus。"""
        # 4. 汇总
        if 'task_difficulty' in self.rubric:
            # 任务 rubric：统一 /100 评价 + 难度系数缩放最终分。
            # 评价分 = Σ base_earned（categories 和=100，无 points_outside_base 除外项）。
            # 工具链缺失时编译被排除：评价分按可评基数折算回 /100（与下方同思路）。
            total_points = 100
            if excluded_points > 0:
                assessable_max = max(total_points - excluded_points, 0.01)
                eval_score = round((base_earned / assessable_max) * total_points, 1)
            else:
                eval_score = round(min(base_earned, total_points), 1)
            # 组长加分（任务书约定）：评价分 +leader_bonus，封顶 100；再按难度系数缩放。
            # 这里先按「唯一组长」发临时全额加分（leader_bonus_granted）；dedupe_team_members 会
            # 按组真实人数校正——同组多名组长时加分 = ⌈leader_bonus/组长人数⌉，全组无人声明组长
            # (member_count>=2) 时视作全员组长平摊。单提交/自检路径不经 dedupe，临时全额即最终值
            # （单人组 = 1 名组长 = ⌈5/1⌉ = 5，本就正确）。granted 为实际生效的临时加分（评价分已
            # 接近满分时不足 5），累入 bonus_total 供反馈展示。
            leader_bonus = float(self.rubric.get('leader_bonus', 0) or 0)
            granted = 0.0
            if leader_bonus > 0 and is_leader:
                granted = round(min(leader_bonus, max(total_points - eval_score, 0.0)), 1)
                eval_score = round(min(eval_score + granted, total_points), 1)
                bonus_total += granted
            result.leader_bonus_granted = granted
            result.evaluation_score = eval_score
            result.total_score = round(eval_score * result.difficulty_ratio, 1)  # 期末最终分
            result.max_score = 100.0
            if 'grading_scale' in self.rubric:
                result.grade = self._calculate_grade(result.total_score, self.rubric['grading_scale'])
            else:
                result.grade = self._calculate_grade_default(result.total_score, result.max_score)
        else:
            # 非任务 rubric：原逻辑（base 封顶 total_points，编译 skip 时按可评基数折算）
            total_points = self.rubric.get('total_points', 100)
            if excluded_points > 0:
                assessable_max = max(total_points - excluded_points, 0.01)
                result.max_score = round(assessable_max, 1)
                result.total_score = round(min(base_earned, assessable_max), 1)
                effective = (base_earned / assessable_max) * total_points
                if 'grading_scale' in self.rubric:
                    result.grade = self._calculate_grade(effective, self.rubric['grading_scale'])
                else:
                    result.grade = self._calculate_grade_default(result.total_score, result.max_score)
            else:
                result.total_score = round(min(base_earned, total_points), 1)
                result.max_score = total_points
                if 'grading_scale' in self.rubric:
                    result.grade = self._calculate_grade(result.total_score, self.rubric['grading_scale'])
                else:
                    result.grade = self._calculate_grade_default(result.total_score, result.max_score)
        result.bonus_total = round(bonus_total, 1)

    def grade_submission(self, submission: ProcessedSubmission) -> GradingResult:
        result = GradingResult(
            student_id=submission.student_id,
            name=submission.name,
            class_name=submission.class_name
        )

        # 透传小组信息（同组共用工程/报告；供反馈按组生成）
        result.group_key = getattr(submission, 'group_key', '') or submission.student_id
        result.group_members = list(
            getattr(submission, 'group_members', [])
            or [(submission.student_id, submission.name)]
        )

        # 1. 提交完整性校验（advisory，不参与计分）
        try:
            result.validation_report = self.validator.validate(submission, self.rubric)
        except Exception as e:
            print(f"警告: 提交校验异常: {e}")
            result.validation_report = None

        # 无 rubric 时降级（不应发生，facade 已强制接通）
        if not self.rubric:
            result.max_score = 100.0
            result.grade = self._calculate_grade_default(result.total_score, result.max_score)
            return result

        # 任务感知：抽出至 _resolve_task_active_rubric（设 result.detected_*/difficulty_ratio
        # /active_rubric；报告声明与源码冲突时追加 advisory issue）。
        active_rubric = self._resolve_task_active_rubric(submission, result)

        # 2. RubricGrader 跑一次 keyword/manual 类别（需要报告文本）；任务 rubric 用 active_rubric
        rg_result = None
        if self.rubric_grader and submission.report_text:
            try:
                grader = self.rubric_grader(active_rubric)
                rg_result = grader.grade(
                    submission.student_id,
                    submission.name,
                    submission.report_text,
                )
                result.report_analysis = {
                    'category_scores': {
                        cid: self._rg_category_to_dict(cs)
                        for cid, cs in rg_result.category_scores.items()
                    }
                }
            except Exception as e:
                print(f"警告: RubricGrader 执行失败: {e}")
                rg_result = None

        # 组长判定：从报告"团队信息与分工"等处提取；未声明则视为无组长
        is_leader = detect_team_leader(submission.report_text or "", submission.name or "")
        result.is_team_leader = is_leader

        # 3. 按 grading_method 派发，逐类产出 CategoryScore（任务 rubric 用 active_rubric）
        category_scores: List[CategoryScore] = []
        base_earned = 0.0
        bonus_total = 0.0
        excluded_points = 0.0   # 工具链缺失等「非学生责任」被排除的基数分
        rates_for_predict: Dict[str, float] = {}  # category_id -> 得分率（供功能预测）

        for cat in active_rubric.get('categories', []):
            method = cat.get('grading_method', 'keyword')

            cs = None
            if method == 'build':
                cs = self._grade_compilation(submission, cat)
            elif method == 'code_analysis':
                cs = self._grade_code_quality(submission, cat)
            elif method == 'source_check':
                cs = self._grade_source_check(submission, cat)
            elif method == 'conditional':
                cs = self._grade_conditional(cat, is_leader)
            elif method == 'manual':
                cs = self._grade_manual(cat)
            elif method == 'predicted':
                cs = self._grade_predicted(cat, rates_for_predict)
            else:  # keyword
                cs = self._category_from_rubric_grader(rg_result, cat, submission)

            if cs is None:
                cs = CategoryScore(
                    category_id=cat['id'],
                    category_name=cat.get('name', cat['id']),
                    max_points=cat.get('points', 0),
                    earned_points=0.0,
                    details=[{'feedback': '无法评分（缺少必要材料）'}]
                )

            # 记录编译/代码分析详情，供反馈与兼容字段使用
            if method == 'build' and cs.details:
                br = cs.details[0].get('build_result')
                result.compilation_result = br
                # 编译"无法评估"仅指本机工具链缺失/超时（非学生责任）：汇总时把该类分值
                # 排除出总分与等级基数，避免误判为编译失败拖低预测分。注意：学生提交层面的
                # 问题（未提交/损坏/嵌套/空/纯Keil）已在 _grade_compilation 判为 FAILED
                # （计入基数），不会走到这里。仅对基础分内类别生效（bonus 类本就单列）。
                if (br is not None
                        and getattr(br, 'status', None) in _UNASSESSABLE_BUILD_STATES
                        and not cat.get('points_outside_base')):
                    excluded_points += cat.get('points', 0)
            if method == 'code_analysis' and cs.details:
                result.code_analysis = cs.details[0].get('analysis')

            # 记录源码三项得分率，供 functionality(predicted) 复用
            if method in ('build', 'source_check', 'code_analysis') and cs.max_points > 0:
                rates_for_predict[cat['id']] = cs.earned_points / cs.max_points

            category_scores.append(cs)
            if cat.get('points_outside_base'):
                bonus_total += cs.earned_points
            else:
                base_earned += cs.earned_points

        result.category_scores = category_scores

        # 4-5. 汇总与定级（抽出至 _finalize_scores）
        self._finalize_scores(result, base_earned, bonus_total, excluded_points, is_leader)

        # 6. 生成结构化反馈（issues + thinking_check + 兼容 strengths/weaknesses）
        self._generate_feedback(result, submission)

        return result

    # --------------------------------------------------------------
    # 各 grading_method 打分
    # --------------------------------------------------------------
    def _grade_compilation(self, submission: ProcessedSubmission, cat: Dict) -> Optional[CategoryScore]:
        """build：真实编译检查。

        - 无源码/工程：按 source_state 分类，在学生反馈中给出**具体原因 + 改进方法**。
          * 所有不可机器编译的提交状态（纯Keil/损坏/嵌套/空/未提交）一律判真实编译失败
            （FAILED，0 分计入总分基数，不排除、不触发 rescale）——属学生提交责任。
          * 仅"有可编译工程但本机缺 make/gcc 工具链"（下方 check_build 返回 SKIPPED）
            才排除出总分（非学生责任）。
        - 同一 source_path 的编译结果缓存：小组多名成员共享同一工程，只编译一次。
        """
        from .source_state import STATE_OK
        max_points = cat.get('points', 10)
        name = f"{submission.student_id}-{submission.name}"

        ss = getattr(submission, 'source_state', None)
        # 无可机器编译的工程（含格式问题）：按状态分类给反馈
        if not submission.source_path or not submission.project_info \
                or (ss is not None and not getattr(ss, 'is_machine_buildable', True) and ss.state != STATE_OK):
            # 即便 source_path/project_info 在(如纯 Keil：有 project_info 但无 Makefile)，
            # 也由 source_state 统一出口，确保反馈带具体原因与改进方法。
            if ss is not None and not getattr(ss, 'is_machine_buildable', True):
                reason = ss.feedback_reason
                fix = ss.feedback_fix
                st = ss.state
                # 源码不可机器编译（纯Keil/损坏/嵌套/空/未提交）一律属学生提交责任：
                # 判真实编译失败 FAILED（0 分计入总分基数，不排除、不触发 rescale）。
                # 仅"有可编译工程但本机缺 make/gcc 工具链"（下方 check_build 返回 SKIPPED，
                # 非学生责任）才在汇总时排除出基数。这样未交源码者不再因 rescale 被白送约 5 分
                # （此前 not_submitted 等误入 SKIPPED 享受排除）。反馈仍用 source_state 的具体原因。
                status, feedback = BuildStatus.FAILED, f"{reason} {fix}"
                br = BuildResult(
                    status=status,
                    project_name=name,
                    project_path=Path(submission.source_path or ''),
                    success=False,
                    error_message=reason,
                )
                return CategoryScore(
                    category_id=cat['id'],
                    category_name=cat.get('name', '编译检查'),
                    max_points=max_points,
                    earned_points=0.0,
                    details=[{
                        'build_result': br,
                        'feedback': feedback,
                        'source_state': st,
                        'reason': reason,
                        'fix': fix,
                        'error_count': 0,
                        'warning_count': 0,
                        'error_message': '',
                    }]
                )
            # 无 source_state（兼容旧调用）：退化为原"无法评估"
            return CategoryScore(
                category_id=cat['id'],
                category_name=cat.get('name', '编译检查'),
                max_points=max_points,
                earned_points=0.0,
                details=[{
                    'build_result': BuildResult(
                        status=BuildStatus.SKIPPED,
                        project_name=name,
                        project_path=Path(submission.source_path or ''),
                        success=False,
                        error_message='未提取到可编译的源码工程（可能为 .7z 等未支持格式或学生未提交）',
                    ),
                    'feedback': '已跳过：未提取到源码工程（不代表代码无法编译）',
                    'error_count': 0,
                    'warning_count': 0,
                    'error_message': '',
                }]
            )

        cache_key = Path(submission.source_path)
        if cache_key in self._build_cache:
            build_result = self._build_cache[cache_key]
        else:
            build_result = self.build_checker.check_build(
                submission.source_path,
                f"{submission.student_id}-{submission.name}"
            )
            self._build_cache[cache_key] = build_result

        fix_hint = ''  # 仅 FAILED 分支会填充（真实错误的可操作改进建议）
        if build_result.status == BuildStatus.SUCCESS:
            earned_points = max_points
            feedback = "编译通过"
        elif build_result.status == BuildStatus.SKIPPED:
            # 工具链缺失（非学生责任）：本类记 0 分，但由 grade_submission 汇总时排除出
            # 总分与等级基数（按可评类别折算）。不用「无法编译」措辞以免误导。
            earned_points = 0
            feedback = "已跳过：本机未安装 make / arm-none-eabi-gcc（不代表代码无法编译）"
        elif build_result.status == BuildStatus.FAILED:
            # 编译失败一律 0 分。把 build_result.issues 里的真实诊断（编译/链接/Makefile 错误）
            # 摘要进反馈，让学生看到具体错在哪，而非笼统的「未识别错误」。fix_hint 同时供
            # _generate_feedback 作为可操作的改进建议。纯警告构建状态为 SUCCESS，已拿满分。
            earned_points = 0
            feedback, fix_hint = _summarize_build_failure(build_result, submission)
        else:
            earned_points = 0
            feedback = f"无法编译: {build_result.error_message}"

        return CategoryScore(
            category_id=cat['id'],
            category_name=cat.get('name', '编译检查'),
            max_points=max_points,
            earned_points=round(earned_points, 1),
            details=[{
                'build_result': build_result,
                'feedback': feedback,
                'fix_hint': fix_hint,
                'error_count': build_result.error_count,
                'warning_count': build_result.warning_count,
                'error_message': build_result.error_message or '',
            }]
        )

    def _grade_conditional(self, cat: Dict, is_leader: bool) -> CategoryScore:
        """conditional 类别（如组长加分）：满足条件得满分，否则 0。

        组长信息来自报告文本（detect_team_leader）；报告未声明组长则该组无组长、不加分。
        该类别通常为 points_outside_base，earned 会被计入 bonus_total，不影响百分制基数。
        """
        max_points = cat.get('points', 0)
        condition = cat.get('condition', '')
        if condition == 'is_team_leader':
            if is_leader:
                earned = float(max_points)
                feedback = f'报告声明担任组长，加 {max_points} 分'
            else:
                earned = 0.0
                feedback = '报告未声明为组长，不加分'
        else:
            earned = 0.0
            feedback = f'未知条件: {condition}'
        return CategoryScore(
            category_id=cat['id'],
            category_name=cat.get('name', cat['id']),
            max_points=max_points,
            earned_points=round(earned, 1),
            details=[{'feedback': feedback, 'is_leader': is_leader, 'condition': condition}]
        )

    def _grade_manual(self, cat: Dict) -> CategoryScore:
        """manual 类别（如实验态度）：取 rubric 的 default_points（教师可后续覆盖）。"""
        max_points = cat.get('points', 0)
        earned = float(cat.get('default_points', 0))
        return CategoryScore(
            category_id=cat['id'],
            category_name=cat.get('name', cat['id']),
            max_points=max_points,
            earned_points=round(earned, 1),
            details=[{'feedback': f'默认 {earned:g} 分（教师可调）', 'manual': True}]
        )

    def _grade_predicted(self, cat: Dict, rates: Dict[str, float]) -> CategoryScore:
        """predicted 类别（功能实现）：由指定类目（predict_from）的得分率均值预测。

        功能实现需硬件实测，机器无法直接评；用源码前三项（编译+非阻塞+代码质量）的得分率
        均值作侧面估计（代码质量高 → 功能更可能完成）。教师实测后可覆盖此预测值。
        """
        max_points = cat.get('points', 0)
        src_ids = cat.get('predict_from', []) or []
        rs = [rates.get(i) for i in src_ids if rates.get(i) is not None]
        rate = (sum(rs) / len(rs)) if rs else 0.0
        earned = round(rate * max_points, 1)
        comp = ', '.join(f'{i}={rates.get(i, 0)*100:.0f}%' for i in src_ids)
        return CategoryScore(
            category_id=cat['id'],
            category_name=cat.get('name', cat['id']),
            max_points=max_points,
            earned_points=earned,
            details=[{
                'feedback': f'机器预测（基于 {comp} 的均值 {rate*100:.0f}%）；教师实测可覆盖',
                'predicted': True, 'predict_rate': round(rate, 3),
                'predict_from': src_ids,
            }]
        )

    def _build_task_active_rubric(self, task_key: str) -> Dict:
        """构造任务感知 active_rubric：顶层 categories（/100 统一刻度），但 keyword 准则的
        keywords 解析为 keywords_by_task[task]（兜底 keywords），使 RubricGrader 只按所选
        任务的关键词评分，修复「单任务学生被跨任务关键词拖低」的失真。"""
        import copy
        rubric = self.rubric
        active = copy.deepcopy(rubric)
        cats = active.get('categories', [])

        def _resolve(criteria):
            for crit in criteria:
                kbt = crit.get('keywords_by_task')
                if kbt and task_key in kbt:
                    crit['keywords'] = list(kbt[task_key])
            return criteria

        for cat in cats:
            if cat.get('grading_method', 'keyword') == 'keyword' and cat.get('criteria'):
                _resolve(cat['criteria'])
        active['total_points'] = 100
        return active

    def _grade_code_quality(self, submission: ProcessedSubmission, cat: Dict) -> Optional[CategoryScore]:
        """code_analysis：真实源码静态分析（优先），否则报告代码块；都没有返回 None。"""
        # 是否存在真实源码文件（.c/.h）。无真实源码（源码包未解开/为空/损坏/未提交）时，
        # 不得回退到报告正文里抽取的代码片段去评代码质量——那会让"空源码"拿到满分（虚高），
        # 与 _grade_source_check 的空源码护栏一致。
        has_real_source = bool(
            submission.project_info
            and (getattr(submission.project_info, 'source_files', [])
                 or getattr(submission.project_info, 'header_files', []))
        )
        code_to_analyze = ""
        if submission.source_path and submission.project_info:
            for main_file in submission.project_info.main_files:
                try:
                    if main_file.stat().st_size > MAX_FILE_BYTES:
                        continue
                    code_to_analyze += main_file.read_text(encoding='utf-8', errors='ignore') + "\n\n"
                except Exception:
                    pass
        # 仅当存在真实源码（但 main 文件未识别到）时，才用报告代码块兜底分析；
        # 无真实源码时不再兜底，落到下方 source_unassessable 分支记 0 分。
        if not code_to_analyze and has_real_source and submission.code_blocks:
            code_to_analyze = "\n\n".join(submission.code_blocks)
        if not code_to_analyze.strip():
            if not has_real_source:
                # 无真实源码：记 0 分并标记（无 'analysis' 键 → _generate_feedback 不追加失分项）。
                return CategoryScore(
                    category_id=cat['id'],
                    category_name=cat.get('name', '代码质量'),
                    max_points=cat.get('points', 20),
                    earned_points=0.0,
                    details=[{
                        'source_unassessable': True,
                        'feedback': '无可评估的源代码（源码包未解开/为空/损坏/未提交），代码质量无法分析，记 0 分；具体原因与改进方法见「编译检查」项。',
                    }]
                )
            return None

        max_points = cat.get('points', 20)
        if not self.code_analyzer:
            return None

        try:
            analysis_result = self.code_analyzer.analyze(code_to_analyze)
            earned_points = (analysis_result.total_score / 100) * max_points

            # 结构化代码问题（带行号/严重度/建议），供直击式反馈
            issue_dicts = [
                {
                    'severity': i.severity.value,
                    'category': i.category,
                    'message': i.message,
                    'line': i.line_number,
                    'suggestion': i.suggestion,
                }
                for i in analysis_result.issues
            ]

            return CategoryScore(
                category_id=cat['id'],
                category_name=cat.get('name', '代码质量'),
                max_points=max_points,
                earned_points=round(earned_points, 1),
                details=[{
                    'analysis': {
                        'total_score': analysis_result.total_score,
                        'strengths': analysis_result.strengths,
                        'issues': issue_dicts,
                        'issue_count': len(analysis_result.issues),
                    },
                    'feedback': f"代码质量得分: {analysis_result.total_score}/100"
                }]
            )
        except Exception as e:
            print(f"警告: 代码分析失败: {e}")
            return None

    def _grade_source_check(self, submission: ProcessedSubmission, cat: Dict) -> Optional[CategoryScore]:
        """source_check：扫描源码命中禁止模式（如 HAL_Delay），按命中数扣分。

        任务书要求全部使用基于 HAL_GetTick() 的非阻塞实现，禁止 HAL_Delay()。
        遍历工程内所有源/头文件（ProjectInfo.source_files + header_files），
        按 forbid_patterns（正则）统计命中并计分。
        """
        if not submission.source_path or not submission.project_info:
            return None

        max_points = cat.get('points', 10)
        patterns = cat.get('forbid_patterns', [r'HAL_Delay\s*\('])
        penalty_per_hit = cat.get('penalty_per_hit', 5)

        compiled = []
        for p in patterns:
            try:
                compiled.append(re.compile(p))
            except re.error:
                continue
        if not compiled:
            return None

        violations = []  # [{file, line, match}]
        # 仅扫描学生自有代码：排除 ST HAL/CMSIS 等厂商库——HAL 库自身定义并使用 HAL_Delay
        # （stm32f4xx_hal.c 等），一并扫描会把任何含 HAL 库的工程都误判为"违反非阻塞"，
        # 且受 MAX_FILES 截断 + rglob 顺序影响变成"摇骰子"（同一工程两次批阅结果不同）。
        # 与任务检测同口径（_is_vendor_file）。
        files = [f for f in (list(getattr(submission.project_info, 'source_files', []))
                             + list(getattr(submission.project_info, 'header_files', [])))
                 if not _is_vendor_file(f)]
        if not files:
            # 无可评估的真实源码（源码包未解开/为空/损坏/未提交）：不得因"0 违规"给满分，
            # 否则会出现"没交源码的人 non_blocking 反而满分"的倒挂。记 0 分并标记；
            # 具体原因与改进方法已在「编译检查」项（source_state）给出，此处不重复。
            # hit_count=0 → _generate_feedback 的 source_check 分支不会再追加失分项。
            return CategoryScore(
                category_id=cat['id'],
                category_name=cat.get('name', cat['id']),
                max_points=max_points,
                earned_points=0.0,
                details=[{
                    'hit_count': 0,
                    'violations': [],
                    'source_unassessable': True,
                    'feedback': '无可评估的源代码（源码包未解开/为空/损坏/未提交），非阻塞检查无法进行，记 0 分；具体原因与改进方法见「编译检查」项。',
                }]
            )
        # 先检测"封装了 HAL_Delay 的阻塞延时函数"——其调用点同样是阻塞延时，按任务书
        # 「禁止阻塞延时」计入扣分（直接 HAL_Delay 与经封装函数间接调用同口径）；而封装
        # 函数体内那条 HAL_Delay 是"成因"，不与其调用点重复计分。
        wrappers, indirect, body_ranges = _detect_blocking_wrappers(submission.source_path, files)

        def _in_wrapper_body(file_disp, ln):
            for bf, b0, b1 in body_ranges:
                if bf == file_disp and b0 <= ln <= b1:
                    return True
            return False

        for f in files[:MAX_FILES]:
            try:
                if f.stat().st_size > MAX_FILE_BYTES:
                    continue
                text = f.read_text(encoding='utf-8', errors='ignore')
                # 工程内相对路径（Core/Src/main.c），比裸文件名更易定位
                file_disp = str(f.relative_to(submission.source_path)).replace('\\', '/')
            except Exception:
                continue
            for ln, line in enumerate(text.splitlines(), start=1):
                if _in_wrapper_body(file_disp, ln):
                    continue   # 封装函数体内的 HAL_Delay 是"成因"，不与调用点重复计
                for rx in compiled:
                    for m in rx.finditer(line):
                        violations.append({
                            'file': file_disp, 'line': ln, 'match': m.group(0),
                        })

        # 封装函数的调用点 = 间接阻塞调用，一并计入扣分
        for v in indirect:
            violations.append({
                'file': v['file'], 'line': v['line'],
                'match': f"{v['wrapper']}(...)", 'wrapper': v['wrapper'],
            })

        hit_count = len(violations)
        wnames = "、".join(wrappers.keys())
        if hit_count == 0:
            earned = float(max_points)
            feedback = "未发现阻塞延时调用（直接 HAL_Delay 或经封装函数间接调用），符合非阻塞要求"
        else:
            earned = max(0.0, max_points - hit_count * penalty_per_hit)
            sample = ", ".join(f"{v['file']}:{v['line']}" for v in violations[:6])
            more = "…" if hit_count > 6 else ""
            wnote = f"，含封装函数 {wnames}() 的间接调用" if wrappers else ""
            feedback = (f"发现 {hit_count} 处阻塞延时调用{wnote}（{sample}{more}），违反非阻塞要求。"
                        "任务书禁止阻塞延时：直接 HAL_Delay 与经封装函数（如 HAL_Delay_ms()）间接"
                        "调用 HAL_Delay 同样视为违反，需全部改为基于 HAL_GetTick() 差值判定的非阻塞写法。")

        return CategoryScore(
            category_id=cat['id'],
            category_name=cat.get('name', '源码检查'),
            max_points=max_points,
            earned_points=round(earned, 1),
            details=[{
                'violations': violations[:20],
                'hit_count': hit_count,
                'blocking_wrappers': wrappers,
                'indirect_hit_count': len(indirect),
                'feedback': feedback,
            }]
        )

    def _category_from_rubric_grader(self, rg_result, cat: Dict, submission: ProcessedSubmission) -> CategoryScore:
        """keyword/manual：从 RubricGrader 结果映射为引擎 CategoryScore。"""
        max_points = cat.get('points', 0)
        if rg_result is None or not submission.report_text:
            return CategoryScore(
                category_id=cat['id'],
                category_name=cat.get('name', cat['id']),
                max_points=max_points,
                earned_points=0.0,
                details=[{'feedback': '未提交报告或无正文，无法评分', 'criteria_scores': []}]
            )

        rg_cs = rg_result.category_scores.get(cat['id'])
        if rg_cs is None:
            return CategoryScore(
                category_id=cat['id'],
                category_name=cat.get('name', cat['id']),
                max_points=max_points,
                earned_points=0.0,
                details=[{'feedback': '该类别未被 RubricGrader 评分', 'criteria_scores': []}]
            )

        criteria_scores = [self._rg_criterion_to_dict(c) for c in rg_cs.criteria_scores]
        return CategoryScore(
            category_id=cat['id'],
            category_name=cat.get('name', rg_cs.name),
            max_points=max_points,
            earned_points=round(rg_cs.points_earned, 1),
            details=[{
                'feedback': '; '.join(rg_cs.feedback) if rg_cs.feedback else '',
                'criteria_scores': criteria_scores,
                'percentage': rg_cs.percentage,
            }]
        )

    # --------------------------------------------------------------
    # 反馈生成（结构化 issues + thinking_check）
    # --------------------------------------------------------------
    def _generate_feedback(self, result: GradingResult, submission: ProcessedSubmission):
        """构建结构化 issues 与 thinking_check，并填充兼容的 strengths/weaknesses。"""
        ref = (self.rubric or {}).get('reference_answers', {})
        issues: List[Dict] = []

        for cs in result.category_scores:
            cat = self._rubric_category(cs.category_id) or {}
            method = cat.get('grading_method', 'keyword')
            lost = round(cs.max_points - cs.earned_points, 1)

            if method == 'build':
                d = cs.details[0] if cs.details else {}
                br = d.get('build_result')
                src_state = d.get('source_state')
                # 格式问题（损坏/嵌套/空/未提交/纯Keil）：**必须**告知学生具体原因与改进方法，
                # 即便被归为「无法评估」(SKIPPED) 也反馈（用户要求：格式问题一定说清）。
                if src_state:
                    reason = d.get('reason') or d.get('feedback', '源码工程无法用于机器编译')
                    issues.append({
                        'type': 'build',
                        'category': cs.category_name,
                        'criterion': '编译/源码格式',
                        'points_lost': lost,
                        'severity': 'error',
                        'message': reason,
                        'detail': d.get('error_message', ''),
                        'expected': '提交标准 GCC 工程：根目录含 Makefile（CubeMX 导出时 Toolchain 选 Makefile）',
                        'fix': d.get('fix') or '请按反馈原因修正源码打包/工程类型后重新提交。',
                    })
                    continue
                if br is not None and getattr(br, 'status', None) in _UNASSESSABLE_BUILD_STATES:
                    # 编译"无法评估"（工具链缺失/超时等非学生责任，且无格式问题）：
                    # grade_submission 已把该类排除出总分；此处不再显示误导性"编译失败"。
                    continue
                if cs.earned_points < cs.max_points and cs.details:
                    issues.append({
                        'type': 'build',
                        'category': cs.category_name,
                        'criterion': '编译',
                        'points_lost': lost,
                        'severity': 'error' if cs.earned_points == 0 else 'warning',
                        'message': d.get('feedback', '编译未通过'),
                        'detail': d.get('error_message', ''),
                        'expected': '工程应能通过 arm-none-eabi-gcc / make 编译，0 error',
                        'fix': d.get('fix_hint') or '根据编译错误修正语法/链接；缺少源码工程则需补交。',
                    })
            elif method == 'code_analysis' and cs.details:
                d0 = cs.details[0]
                if d0.get('source_unassessable'):
                    # 无可评估源码：明确告知代码质量项为何 0 分（具体打包原因见编译项）。
                    issues.append({
                        'type': 'code',
                        'category': cs.category_name,
                        'criterion': '代码质量',
                        'points_lost': lost,
                        'severity': 'info',
                        'message': d0.get('feedback', '无可评估源码，代码质量无法分析'),
                        'expected': '提交可编译的源码工程',
                        'fix': '请提交完整的源码工程压缩包；具体原因与改进方法见「编译检查」项。',
                    })
                else:
                    analysis = d0.get('analysis', {}) or {}
                    for ci in (analysis.get('issues') or [])[:8]:
                        issues.append({
                            'type': 'code',
                            'category': cs.category_name,
                            'criterion': ci.get('category', '代码问题'),
                            'points_lost': 0,  # 单条 issue 不单独计分，整体已反映在得分率
                            'severity': ci.get('severity', 'info'),
                            'message': ci.get('message', ''),
                            'line': ci.get('line', 0),
                            'fix': ci.get('suggestion', ''),
                            'expected': '',
                        })
            elif method == 'source_check':
                d = cs.details[0] if cs.details else {}
                if d.get('source_unassessable'):
                    # 无可评估源码（未解开/为空/损坏/未提交）：明确告知本项失分原因，
                    # 不让学生对着 0 分一头雾水（具体打包原因见编译项）。
                    issues.append({
                        'type': 'source_check',
                        'category': cs.category_name,
                        'criterion': '非阻塞设计',
                        'points_lost': lost,
                        'severity': 'info',
                        'message': d.get('feedback', '无可评估源码，非阻塞检查无法进行'),
                        'detail': '',
                        'expected': '提交可编译的源码工程',
                        'fix': '请提交完整的源码工程压缩包；具体原因与改进方法见「编译检查」项。',
                    })
                elif d.get('hit_count', 0) > 0:
                    issues.append({
                        'type': 'source_check',
                        'category': cs.category_name,
                        'criterion': 'HAL_Delay 禁用',
                        'points_lost': lost,
                        'severity': 'error',
                        'message': d.get('feedback', '源码含 HAL_Delay 调用'),
                        'detail': '; '.join(
                            f"{v['file']}:{v['line']}" + (f"(间接·{v['wrapper']})" if v.get('wrapper') else "")
                            for v in d.get('violations', [])),
                        'expected': '全部使用基于 HAL_GetTick() 的非阻塞延时；直接 HAL_Delay 与经封装函数(如 HAL_Delay_ms)间接调用均禁止',
                        'fix': '将所有阻塞延时(含封装函数内部的 HAL_Delay 及其调用点)改为基于 HAL_GetTick() 差值判定的非阻塞写法',
                    })
            else:  # keyword/manual：逐准则失分
                criteria_scores = (cs.details[0].get('criteria_scores') if cs.details else []) or []
                for crit in criteria_scores:
                    p_lost = round(crit.get('points_possible', 0) - crit.get('points_earned', 0), 1)
                    if p_lost <= 0:
                        continue
                    issues.append({
                        'type': 'criterion',
                        'category': cs.category_name,
                        'category_id': cs.category_id,
                        'criterion': crit.get('description', ''),
                        'missing_keywords': crit.get('missing_keywords', []),
                        'points_lost': p_lost,
                        'severity': 'warning',
                        'message': f"未充分体现：{', '.join(crit.get('missing_keywords', [])) or '相关关键词缺失'}",
                        'expected': self._expected_answer(cs.category_id, crit.get('description', ''), ref),
                        'fix': (f"此处可回收 {p_lost:g} 分：围绕「{crit.get('description', '')}」"
                                "把原理/做法/数据写清写准即可拿回（缺失关键词见上）。"),
                    })

        # 源码提交冗余提示（学生交了多个源码归档）：advisory，不扣分，但明确告知，
        # 让学生知道"提交了多份源码、机器自动选用了一份"，避免下次重复上传。
        src_note = getattr(submission, 'source_note', '')
        if src_note:
            issues.append({
                'type': 'submission',
                'category': '提交规范',
                'criterion': '源码提交冗余',
                'points_lost': 0,
                'severity': 'warning',
                'message': src_note,
                'fix': '请下次只提交一份源码压缩包（内含完整工程文件夹）；勿同时上传多个版本或"待删除"文件，以免机器批阅选错工程。',
                'expected': '一份源码压缩包',
            })

        # 思考题核对：依据校验器在"七、思考题"章节内检测到的题号（避免正文其它编号误判）+ 参考答案
        result.thinking_check = self._build_thinking_check(
            result.validation_report, ref, result.detected_task or '')

        result.issues = issues

        # 兼容旧字段：strengths/weaknesses/suggestions（供尚未迁移的消费者）
        result.weaknesses = [
            f"{it.get('category', '')}：{it.get('message', '')}"
            for it in issues if it.get('severity') in ('error', 'warning')
        ][:10]
        result.suggestions = [it.get('fix', '') for it in issues if it.get('fix')][:10]
        result.strengths = [
            cs.category_name for cs in result.category_scores
            if cs.max_points > 0 and cs.earned_points >= cs.max_points
        ]

    def _build_thinking_check(self, validation_report, ref: Dict, detected_task: str = "") -> List[Dict]:
        """逐题核对：题号集与参考方向均由 rubric 驱动（不再写死 Q1~Q7）。

        - 题号集：``reference_answers.thinking_question_ids``；缺省回退参考方向键，
          再缺省回退 Q1~Q7（兼容汽车档位 rubric）。
        - 参考方向：``thinking_questions``（通用）叠加
          ``thinking_questions_by_task[任务]``（任务专属，如期项目 Q3）。
        - rubric 声明 ``thinking_check=false`` 时不生成该表。
        """
        # rubric 声明 thinking_check=false（如综合项目思考题为选做）时不生成该表
        if not (self.rubric or {}).get('thinking_check', True):
            return []
        answers = dict(ref.get('thinking_questions', {}) if isinstance(ref, dict) else {})
        by_task = ref.get('thinking_questions_by_task', {}) if isinstance(ref, dict) else {}
        if detected_task and isinstance(by_task, dict) and by_task.get(detected_task):
            answers.update(by_task[detected_task])
        # 题号集：显式优先 → 参考方向键 → 回退 Q1~Q7
        ids = ref.get('thinking_question_ids') if isinstance(ref, dict) else None
        if not ids:
            ids = sorted(answers.keys()) or [f'Q{i}' for i in range(1, 8)]
        missing = set()
        if validation_report is not None:
            missing = set(validation_report.missing_questions or [])
        return [
            {
                'id': qid,
                'answered': qid not in missing,
                'expected': answers.get(qid, ''),
            }
            for qid in ids
        ]

    def _expected_answer(self, category_id: str, criterion_desc: str, ref: Dict) -> str:
        """按类别/准则启发式回填参考答案（让反馈'正确应为'更具体）。"""
        if not isinstance(ref, dict):
            return ''
        desc = criterion_desc or ''
        try:
            if category_id == 'principle_understanding':
                if '原理' in desc:
                    parts = [f"消抖：{ref.get('debouncing','')}", f"中断：{ref.get('interrupt_config','')}"]
                    return '；'.join(p for p in parts if p)
            if category_id == 'completion':
                if '引脚' in desc or '硬件' in desc:
                    gp = ref.get('gpio_pins', {})
                    if gp:
                        return 'GPIO：' + '，'.join(f"{k}={v}" for k, v in gp.items())
                if '现象' in desc or '结果' in desc:
                    gs = ref.get('gear_states', {})
                    if gs:
                        return '档位 LED：' + '，'.join(f"{k}:{v}" for k, v in gs.items())
            if category_id == 'report_quality' and '思考题' in desc:
                tq = ref.get('thinking_questions', {})
                if tq:
                    return '应逐题作答 Q1~Q7，参考方向见评分反馈「思考题核对」'
        except Exception:
            return ''
        return ''

    # --------------------------------------------------------------
    # 工具
    # --------------------------------------------------------------
    def _rubric_category(self, cat_id: str) -> Optional[Dict]:
        # 任务 rubric 下从 active_rubric 取（keywords 已按任务解析）
        src = getattr(self, '_active_rubric', None) or self.rubric or {}
        for c in src.get('categories', []):
            if c.get('id') == cat_id:
                return c
        return None

    @staticmethod
    def _rg_category_to_dict(cs) -> Dict:
        return {
            'category_id': cs.category_id,
            'name': cs.name,
            'points_earned': cs.points_earned,
            'points_possible': cs.points_possible,
            'percentage': cs.percentage,
            'feedback': list(cs.feedback),
            'criteria_scores': [AutoGradingEngine._rg_criterion_to_dict(c) for c in cs.criteria_scores],
        }

    @staticmethod
    def _rg_criterion_to_dict(c) -> Dict:
        return {
            'criterion_id': c.criterion_id,
            'description': c.description,
            'points_earned': c.points_earned,
            'points_possible': c.points_possible,
            'matched_keywords': list(c.matched_keywords),
            'missing_keywords': list(getattr(c, 'missing_keywords', [])),
            'feedback': c.feedback,
        }

    def _calculate_grade(self, score: float, grading_scale: Dict) -> str:
        return _grade_from_scale(score, grading_scale)

    def _calculate_grade_default(self, score: float, max_score: float) -> str:
        return _grade_default(score, max_score)

    # --------------------------------------------------------------
    # 批量与班级报告
    # --------------------------------------------------------------
    def batch_grade(self, submissions: List[ProcessedSubmission]) -> List[GradingResult]:
        results = []
        for i, submission in enumerate(submissions):
            print(f"评分 ({i+1}/{len(submissions)}): {submission.student_id}-{submission.name}")
            result = self.grade_submission(submission)
            results.append(result)
            print(f"  得分: {result.total_score:.1f}/{result.max_score:.1f} (加分{result.bonus_total:.0f}) ({result.grade})")
        # 小组按成员展开后，同一学生可能出现在多份上传报告中（学习通「按人导出」，
        # 同组成员各自上传）；按学号去重，保留得分最高的一份（同组多版本取最优，
        # 对学生最有利且确定）。个人实验无团队成员表→不展开→去重为空操作。
        # 传 rubric：让 dedupe 按组真实人数校正组长加分（多组长平摊 / 无组长全员平摊）。
        # 花名册身份核验（re-key + 学号/姓名错误记0分）必须在去重之前——re-key 到真实学号
        # 后，撞号两人各落不同学号，不再被去重并掉。无花名册则跳过（向后兼容）。
        roster = None
        try:
            from .roster_check import load_id_roster, validate_identities
            semester_dir = self.config.teaching_dir / self.config.semester
            roster = load_id_roster(semester_dir)
            if roster:
                results = validate_identities(results, roster)
        except Exception:
            pass
        return dedupe_team_members(results, rubric=self.rubric)

    def generate_class_report(self, results: List[GradingResult]) -> Dict:
        if not results:
            return {}

        total = len(results)
        scores = [r.total_score for r in results]

        grade_distribution = {}
        for r in results:
            grade_distribution[r.grade] = grade_distribution.get(r.grade, 0) + 1

        category_stats = {}
        for result in results:
            for cat_score in result.category_scores:
                cat_id = cat_score.category_id
                if cat_id not in category_stats:
                    category_stats[cat_id] = {
                        'name': cat_score.category_name,
                        'total_points': 0,
                        'max_points': 0,
                        'count': 0
                    }
                category_stats[cat_id]['total_points'] += cat_score.earned_points
                category_stats[cat_id]['max_points'] += cat_score.max_points
                category_stats[cat_id]['count'] += 1

        for cat_id, stats in category_stats.items():
            if stats['count'] > 0:
                stats['average'] = stats['total_points'] / stats['count']
                stats['max_average'] = stats['max_points'] / stats['count']

        return {
            'total_students': total,
            'average_score': sum(scores) / total if total > 0 else 0,
            'max_score': results[0].max_score if results else 0,
            'grade_distribution': grade_distribution,
            'category_stats': category_stats,
            'individual_results': [
                {
                    'student_id': r.student_id,
                    'name': r.name,
                    'score': r.total_score,
                    'bonus': r.bonus_total,
                    'grade': r.grade
                }
                for r in results
            ]
        }


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description='整合评分引擎')
    parser.add_argument('class_name', type=str, help='班级名称')
    parser.add_argument('experiment_id', type=str, help='实验ID')
    parser.add_argument('--rubric', type=Path, help='评分标准文件路径')
    parser.add_argument('--base-dir', type=Path, default='data/teaching/2026-春季/', help='基础目录')

    args = parser.parse_args()

    from .submission_processor import SubmissionProcessor

    processor = SubmissionProcessor(args.base_dir)
    rubric_path = args.rubric
    if rubric_path is None:
        # 未显式指定 --rubric 时，按 experiment_id 解析（与 facade 路径一致），
        # 避免 CLI 误用默认/空 rubric 把综合项目按其它标准评。
        from .config import AutoGradingConfig
        rubric_path = AutoGradingConfig().get_rubric_path(args.experiment_id)
    if not rubric_path.exists():
        # rubric 缺失（常见于 cwd 不在仓库根）时直接报错退出，避免静默产出 0 分错误结果
        print(f"[错误] 评分标准文件不存在：{rubric_path}"
              f"（请检查 experiment_id / --rubric，或在仓库根目录运行）")
        return
    engine = AutoGradingEngine(rubric_path=rubric_path)

    submissions = processor.process_class_submissions(args.class_name, args.experiment_id)
    print(f"找到 {len(submissions)} 个提交")

    results = engine.batch_grade(submissions)
    class_report = engine.generate_class_report(results)

    print()
    print("=" * 60)
    print("班级报告")
    print("=" * 60)
    print(f"平均分: {class_report['average_score']:.1f}")
    print(f"等级分布: {class_report['grade_distribution']}")


if __name__ == '__main__':
    main()
