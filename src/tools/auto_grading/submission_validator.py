#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
提交完整性校验器
Submission Validator

在评分前/评分中对单个学生提交做"内容齐全 + 格式正确"校验，
产出结构化问题清单，供学生反馈置顶展示（advisory，不参与计分）。

规则：
1. 格式：报告应为 .docx（.doc/.pdf/纯图 → 警告）
2. 文件齐全：报告存在；若 rubric 含 build/code_analysis 类别，source/ 应存在
3. 章节完整：一~七 齐全（复用 SectionDetector）
4. 章节最小内容：每个在场章节正文 > N 字（过滤模板占位）
5. 图片证据：结果章节（三/五）≥1 张图（复用 ImageCounter）
6. 代码块：四、软件设计与实现 含 ≥1 段代码
7. 思考题：七、思考题 引用到 Q1~Q7；缺失题号点名
8. 文件名规范：匹配 {班级}-{学号}-{姓名}-实验报告.docx

设计原则：校验只读、绝不抛异常、不改变评分。
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


# 期望的七大章节：序号 → (用于匹配的关键词, 影响的 rubric 类别, 该类别分值)
EXPECTED_SECTIONS = [
    ("一", ["团队信息", "分工"], "team_collaboration", 5),
    ("二", ["实验目的", "原理"], "principle_understanding", 10),
    ("三", ["硬件设计", "连接", "硬件"], "completion", 20),
    ("四", ["软件设计", "实现", "软件"], "code_quality", 30),
    ("五", ["实验结果", "结果分析", "结果"], "completion", 20),
    ("六", ["问题", "讨论", "心得"], "report_quality", 10),
    ("七", ["思考题", "思考"], "report_quality", 10),
]

# 思考题题号检测模式
QUESTION_PATTERNS = [
    re.compile(r'Q\s*(\d)', re.IGNORECASE),
    re.compile(r'问题\s*(\d)'),
    re.compile(r'思考题\s*(\d)'),  # "思考题1/思考题2"等标题式编号
    re.compile(r'(?:^|\D)(\d)\s*[\.、）)]'),
]
# 散文式作答标记："答：/答:"。不少报告不写题号，改用"问…答：…"格式逐题作答
# （如"通用思考题/任务二专属思考题"标题下直接写题目+答：），靠它兜底补齐题号漏检。
ANSWER_MARKER_RE = re.compile(r'答\s*[:：]')


def detect_report_format(path) -> str:
    """按文件头嗅探报告真实格式（扩展名可能不准）。

    只读前 8 字节，开销极低。用于识破「旧版 .doc / RTF / PDF 被改名为 .docx」
    这类陷阱——它们不是真正的 zip-based .docx，python-docx 解析会静默返回空，
    进而让所有关键词类别 0 分。

    Returns:
        'docx'  — PK 头，至少是 zip（能否抽文本由后续解析决定）
        'doc'   — OLE2 复合文档（Word 97-2003 .doc）
        'pdf'   — PDF
        'rtf'   — RTF
        'unknown' — 其它/读取失败
    """
    try:
        with open(path, "rb") as f:
            head = f.read(8)
    except (OSError, TypeError):
        return "unknown"
    if head.startswith(b"PK\x03\x04"):
        return "docx"
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "doc"
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"{\\rtf"):
        return "rtf"
    return "unknown"


@dataclass
class ValidationIssue:
    """单条校验问题"""
    rule: str            # 规则名
    severity: str        # 'error' | 'warning' | 'info'
    section: str = ""    # 相关章节（可空）
    message: str = ""    # 问题描述
    fix: str = ""        # 修正建议


@dataclass
class ValidationReport:
    """提交校验报告"""
    passed: bool = True
    issues: List[ValidationIssue] = field(default_factory=list)
    sections: Dict[str, str] = field(default_factory=dict)   # 检测到的章节 {名称: 内容}
    missing_questions: List[str] = field(default_factory=list)  # 缺失的思考题号，如 ['Q3','Q5']

    def to_dict(self) -> Dict[str, Any]:
        return {
            'passed': self.passed,
            'issues': [
                {'rule': i.rule, 'severity': i.severity, 'section': i.section,
                 'message': i.message, 'fix': i.fix}
                for i in self.issues
            ],
            'missing_questions': self.missing_questions,
            'section_count': len(self.sections),
        }

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == 'error')

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == 'warning')


class SubmissionValidator:
    """提交校验器（advisory）"""

    # 章节最小正文字符数（去除空白后）
    MIN_SECTION_CHARS = 80
    # 结果章节最少图片数
    MIN_RESULT_IMAGES = 1

    def __init__(self, min_section_chars: int = None, min_result_images: int = None):
        self.min_section_chars = min_section_chars or self.MIN_SECTION_CHARS
        self.min_result_images = min_result_images or self.MIN_RESULT_IMAGES
        self._section_detector = None
        self._image_counter = None
        # rubric 驱动的校验配置（validate 时按 rubric 覆盖）
        self._rubric: Dict = {}
        self._expected_sections = EXPECTED_SECTIONS
        self._thinking_check = True

    # ---------- 复用既有实现（惰性导入，避免循环依赖）----------
    def _detect_sections(self, text: str) -> Dict[str, str]:
        if self._section_detector is None:
            try:
                from ..plagiarism.grading.grading import SectionDetector
                self._section_detector = SectionDetector
            except Exception:
                self._section_detector = False
        if not self._section_detector:
            return {}
        try:
            return self._section_detector.detect_sections(text)
        except Exception:
            return {}

    def _count_images(self, text: str, docx_path: Optional[Any]) -> int:
        if self._image_counter is None:
            try:
                from ..plagiarism.image.image_counter import ImageCounter
                self._image_counter = ImageCounter()
            except Exception:
                self._image_counter = False
        if not self._image_counter:
            # 退化：纯文本关键词代理
            return len(re.findall(r'图\s*\d|照片|截图|图片', text or ''))
        try:
            count = 0
            if docx_path is not None:
                try:
                    count = self._image_counter.count_from_docx(docx_path)
                except Exception:
                    count = 0
            text_count = self._image_counter.count_from_text(text or '')
            return max(count, text_count)
        except Exception:
            return 0

    # ---------- 主入口 ----------
    def validate(self, submission, rubric: Optional[Dict] = None) -> ValidationReport:
        """校验单个提交。绝不抛异常。"""
        report = ValidationReport()

        # 按 rubric 配置校验：期望章节、是否检查思考题（缺省回退汽车档位默认）
        self._rubric = rubric or {}
        self._expected_sections = self._rubric.get('expected_sections') or EXPECTED_SECTIONS
        self._thinking_check = bool(self._rubric.get('thinking_check', True))

        try:
            self._rule_format(submission, report)
            self._rule_files(submission, report, rubric)
            self._rule_filename(submission, report)

            text = getattr(submission, 'report_text', '') or ''
            sections = self._detect_sections(text)
            report.sections = sections

            self._rule_sections(sections, report)
            self._rule_section_content(sections, report)
            self._rule_code_block(submission, sections, report)
            self._rule_images(submission, sections, report)
            self._rule_thinking_questions(submission, sections, report)
        except Exception as e:  # 校验绝不能阻断评分
            report.issues.append(ValidationIssue(
                rule='validator_internal',
                severity='warning',
                message=f'校验过程出现异常（已忽略，不影响评分）：{e}',
                fix='可忽略；如反复出现请检查该提交文件是否损坏'
            ))

        report.passed = report.error_count == 0
        return report

    # ---------- 各规则 ----------
    def _rule_format(self, submission, report: ValidationReport):
        """规则1：报告格式（含「扩展名为 .docx 但实为旧版 .doc/RTF/PDF」的嗅探）"""
        path = getattr(submission, 'report_path', None)
        if path is None:
            report.issues.append(ValidationIssue(
                rule='format', severity='error',
                message='未找到实验报告文件',
                fix='补交 .docx 格式的实验报告'))
            return
        suffix = str(path).lower().rsplit('.', 1)[-1] if '.' in str(path) else ''
        # 即便扩展名是 .docx，也按文件头核验真实格式——防「旧版 .doc / RTF / PDF 改名 .docx」
        # 陷阱：它们不是真正的 zip-based .docx，python-docx 解析静默返回空 → 关键词类 0 分。
        true_fmt = detect_report_format(path)
        if suffix == 'docx':
            if true_fmt == 'docx':
                return
            label = {'doc': '旧版 Word .doc（97-2003）',
                     'pdf': 'PDF', 'rtf': 'RTF', 'unknown': '未知'}.get(true_fmt, '未知')
            report.issues.append(ValidationIssue(
                rule='format', severity='error', section='文件格式',
                message=f'扩展名是 .docx，但文件实为{label}，无法提取正文（关键词类将计 0 分）',
                fix='在 Word 中打开后「另存为 → Word 文档(.docx)」，再重新选择该新文件'))
            return
        if suffix == 'doc':
            report.issues.append(ValidationIssue(
                rule='format', severity='warning', section='文件格式',
                message='报告为旧版 .doc 格式，系统可能无法完整解析内容/图片',
                fix='另存为 .docx 后重新提交'))
        elif suffix == 'pdf':
            report.issues.append(ValidationIssue(
                rule='format', severity='warning', section='文件格式',
                message='报告为 PDF 格式，无法自动提取文本评分',
                fix='提交 .docx 源文件以便自动批阅'))
        else:
            report.issues.append(ValidationIssue(
                rule='format', severity='warning', section='文件格式',
                message=f'报告扩展名 .{suffix or "?"} 非 .docx',
                fix='提交 .docx 格式实验报告'))

    def _rule_files(self, submission, report: ValidationReport, rubric: Optional[Dict]):
        """规则2：文件齐全（含源码）"""
        text = getattr(submission, 'report_text', '') or ''
        if not text.strip():
            report.issues.append(ValidationIssue(
                rule='files', severity='error',
                message='报告内容为空或无法解析',
                fix='检查 .docx 是否损坏，或重新提交含完整正文的报告'))

        # 若 rubric 含 build/code_analysis 类别，源代码工程应存在
        needs_source = False
        if rubric:
            for c in rubric.get('categories', []):
                if c.get('grading_method') in ('build', 'code_analysis'):
                    needs_source = True
                    break
        if needs_source and not getattr(submission, 'source_path', None):
            lost = self._code_category_points(rubric)
            report.issues.append(ValidationIssue(
                rule='files', severity='warning', section='源代码',
                message=f'未提交源代码工程，"编译检查+代码质量"共 {lost} 分将无法获取',
                fix='提交完整源代码工程（含 main.c/Core 等）'))

    def _rule_filename(self, submission, report: ValidationReport):
        """规则8：文件名规范"""
        path = getattr(submission, 'report_path', None)
        if path is None:
            return
        stem = str(path).rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
        stem = stem.rsplit('.', 1)[0] if '.' in stem else stem
        pattern = re.compile(r'(.+)-(\d{11})-([一-龥]{2,4})-实验报告')
        if not pattern.search(stem):
            report.issues.append(ValidationIssue(
                rule='filename', severity='info',
                message=f'文件名不符合规范：{stem}',
                fix='命名为：班级-学号-姓名-实验报告.docx'))

    def _rule_sections(self, sections: Dict[str, str], report: ValidationReport):
        """规则3：章节完整"""
        if not sections:
            # 无法检测到任何章节（可能是格式问题）
            report.issues.append(ValidationIssue(
                rule='sections', severity='warning',
                message='未检测到章节结构（一、二…），可能影响自动评分准确性',
                fix='使用"一、团队信息与分工"等标准中文编号标题'))
            return
        section_names = list(sections.keys())
        for numeral, keywords, cat_id, cat_pts in self._expected_sections:
            found = any(any(kw in name for kw in keywords) for name in section_names)
            if not found:
                cat_name = self._category_name(cat_id)
                report.issues.append(ValidationIssue(
                    rule='sections', severity='warning',
                    section=f'{numeral}、',
                    message=f'缺少"{numeral}、"对应章节内容（{cat_name}，影响 {cat_pts} 分）',
                    fix=f'补写"{numeral}、"章节并展开说明'))

    def _rule_section_content(self, sections: Dict[str, str], report: ValidationReport):
        """规则4：章节最小内容"""
        for numeral, keywords, cat_id, cat_pts in self._expected_sections:
            for name, content in sections.items():
                if any(kw in name for kw in keywords):
                    body = re.sub(r'\s', '', content)
                    if 0 < len(body) < self.min_section_chars:
                        report.issues.append(ValidationIssue(
                            rule='section_content', severity='info',
                            section=f'{numeral}、{name}',
                            message=f'"{name}"内容过少（仅{len(body)}字），疑似模板占位',
                            fix=f'展开"{name}"，补充具体设计与数据'))
                    break

    def _rule_code_block(self, submission, sections: Dict[str, str], report: ValidationReport):
        """规则6：报告应含关键代码（在任意章节中检测，不限定「软件设计」）"""
        # 扫描所有章节正文找代码痕迹；不同实验报告结构不同（汽车档位在「软件设计」、综合项目在「核心代码说明」）
        all_content = "\n".join(sections.values())
        has_code_in_sec = bool(re.search(
            r'(int|void|static|HAL_|GPIO|switch|enum)\s*\w*\s*\(|[{};]\s*$', all_content, re.MULTILINE))
        code_blocks = getattr(submission, 'code_blocks', []) or []
        if not has_code_in_sec and not code_blocks:
            report.issues.append(ValidationIssue(
                rule='code_block', severity='warning', section='核心代码',
                message='报告未检测到关键代码，代码质量将主要依赖源码工程分析',
                fix='在核心代码章节粘贴关键代码（如状态机 switch、按键长/短按、非阻塞延时、EXTI 回调）'))

    def _rule_images(self, submission, sections: Dict[str, str], report: ValidationReport):
        """规则5：结果章节图片证据"""
        result_text = ''
        for name, content in sections.items():
            if any(kw in name for kw in ['实验结果', '结果分析', '结果']):
                result_text += content + '\n'
        if not result_text:
            return  # 章节缺失已在规则3提示
        docx_path = getattr(submission, 'report_path', None)
        img_count = self._count_images(result_text, docx_path)
        if img_count < self.min_result_images:
            report.issues.append(ValidationIssue(
                rule='images', severity='info', section='五、实验结果',
                message=f'结果章节图片证据不足（检测到 {img_count} 张，建议 ≥{self.min_result_images}）',
                fix='补充实验现象照片、LED 状态截图或示波器波形'))

    def _rule_thinking_questions(self, submission, sections: Dict[str, str], report: ValidationReport):
        """规则7：思考题题号齐全（rubric 声明 thinking_check=false 时跳过）。

        题号集由 rubric 驱动（``reference_answers.thinking_question_ids``，缺省 Q1~Q7），
        避免对期末项目（题数为 3）仍按汽车档位的 7 题判定与提示。
        """
        if not self._thinking_check:
            return
        ref = (self._rubric or {}).get('reference_answers', {}) or {}
        # 题号集须与 grading_engine._build_thinking_check 保持一致：优先显式
        # thinking_question_ids；否则取所有可能出现题目的键并集（通用 + 各任务专属）；
        # 都没有再回退 Q1~Q7。校验阶段尚不知所选任务，故用并集作为「全部可能题号」。
        tqs = ref.get('thinking_questions', {}) or {}
        by_task = ref.get('thinking_questions_by_task', {}) or {}
        key_union = set(tqs.keys())
        for task_map in by_task.values():
            if isinstance(task_map, dict):
                key_union |= set(task_map.keys())
        ids = ref.get('thinking_question_ids') or sorted(key_union) or [f'Q{i}' for i in range(1, 8)]
        id_label = '、'.join(ids)
        expected_nums = {n for n in (self._qid_num(q) for q in ids) if n > 0}

        q_text = ''
        for name, content in sections.items():
            if any(kw in name for kw in ['思考题', '思考']):
                q_text = content
                break
        if not q_text:
            # 报告无思考题章节：只记录 missing_questions 供反馈列出参考方向，不重复报 issue
            report.missing_questions = list(ids)
            return
        answered = set()
        for pat in QUESTION_PATTERNS:
            for m in pat.finditer(q_text):
                try:
                    n = int(m.group(1))
                    if n in expected_nums:
                        answered.add(n)
                except (ValueError, IndexError):
                    continue
        # 兜底：纯题号正则只认 Q1/问题1/1./思考题1 等显式编号，漏检"问…答：…"散文式作答
        # （报告按"通用思考题/任务二专属思考题"分组、题目下直接写"答：…"）。统计"答："作答
        # 标记数，按期望题数补齐已作答题号，避免把已答的报告误报为"未作答/0 个题号"。
        # 仅在题号正则未覆盖时启用，且不超出期望题数。
        if len(answered) < len(expected_nums):
            ans_markers = len(ANSWER_MARKER_RE.findall(q_text))
            fill = min(ans_markers, len(expected_nums)) - len(answered)
            for n in sorted(expected_nums):
                if fill <= 0:
                    break
                if n not in answered:
                    answered.add(n)
                    fill -= 1
        report.missing_questions = [qid for qid in ids if self._qid_num(qid) not in answered]

        body = re.sub(r'\s', '', q_text)
        if len(answered) == 0 and len(body) < 150:
            report.issues.append(ValidationIssue(
                rule='thinking_questions', severity='warning', section='七、思考题',
                message=f'思考题章节内容偏少（{len(body)}字）且未见题号，可能未逐题作答',
                fix=f'逐题作答 {id_label} 并显式标注题号，结合参考答案核对'))
        elif len(answered) < len(expected_nums):
            report.issues.append(ValidationIssue(
                rule='thinking_questions', severity='info', section='七、思考题',
                message=f'思考题仅检测到 {len(answered)} 个题号标注，建议逐题标注 {id_label} 以便核对',
                fix=f'按 {id_label} 显式标注题号作答'))
        # 检测到的题号数 >= 题号集：视为基本作答，不再提示

    @staticmethod
    def _qid_num(qid: str) -> int:
        """从题号标识（如 'Q3'）取数字部分，取不到返回 -1。"""
        m = re.search(r'(\d+)', qid or '')
        return int(m.group(1)) if m else -1

    # ---------- 辅助 ----------
    def _category_name(self, cat_id: str) -> str:
        """章节缺失提示里的类别名：优先取 rubric 中该类别的 name，回退到内置标签/id。"""
        for c in (self._rubric or {}).get('categories', []):
            if c.get('id') == cat_id:
                return c.get('name', cat_id)
        return self._category_label(cat_id)

    @staticmethod
    def _category_label(cat_id: str) -> str:
        return {
            'team_collaboration': '团队协作',
            'principle_understanding': '实验原理与认知',
            'completion': '实验完成度',
            'code_quality': '代码质量',
            'report_quality': '实验报告质量',
        }.get(cat_id, cat_id)

    @staticmethod
    def _code_category_points(rubric: Optional[Dict]) -> int:
        if not rubric:
            return 45
        return sum(c.get('points', 0) for c in rubric.get('categories', [])
                   if c.get('grading_method') in ('build', 'code_analysis'))
