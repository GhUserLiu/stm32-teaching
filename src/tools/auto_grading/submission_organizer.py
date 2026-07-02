#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
作业提交格式整理器
Submission Organizer

处理班级提交的压缩包，将其整理为标准格式：
- 提取实验报告到 reports/ 目录
- 提取源代码到 source/ 目录
- 自动重命名文件和文件夹

输入格式：
  班级压缩包
  └── 学生压缩包
      ├── 实验报告.docx
      └── 源代码.zip

输出格式：
  reports/
  └── 班级-学号-姓名-实验报告.docx
  source/
  └── 班级-学号-姓名-源代码/
"""

import os
import re
import shutil
import zipfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from ..security.zip_validator import safe_extract_zip, ZipLimits
from ..security.seven_zip_validator import safe_extract_7z
from .submission_normalizer import SubmissionNormalizer
# from ..security.path_validator import PathValidator  # Not needed


@dataclass
class StudentInfo:
    """学生信息"""
    student_id: str      # 学号
    name: str            # 姓名
    class_name: str      # 班级


@dataclass
class OrganizationResult:
    """整理结果"""
    total_students: int = 0
    successful: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)
    details: List[Dict] = field(default_factory=list)


class SubmissionOrganizer:
    """作业提交格式整理器"""

    # 文件扩展名模式
    REPORT_EXTENSIONS = {'.docx', '.doc', '.wps'}
    SOURCE_EXTENSIONS = {'.zip', '.7z'}

    # 班级压缩包解压限制：班级包内含每位学生的提交包（期末综合项目「按人导出」
    # 常达数百 MB），默认 ZipLimits 的 100MB 上限会误拦正常班级包。此处放宽
    # 外层/单文件上限；路径遍历、符号链接、高压缩比等其它安全检查仍由
    # safe_extract_zip 照常生效。
    CLASS_ZIP_LIMITS = ZipLimits(
        max_file_count=5000,
        max_outer_size=2 * 1024 * 1024 * 1024,   # 2GB（整班解压后总量）
        max_inner_size=500 * 1024 * 1024,        # 500MB（单个学生提交包）
    )

    # 学号模式（11位数字）
    STUDENT_ID_PATTERN = re.compile(r'(\d{11})')

    # 姓名模式（2-4个汉字）
    NAME_PATTERN = re.compile(r'([一-龥]{2,4})')

    def __init__(self, base_dir: Path):
        """
        初始化整理器

        Args:
            base_dir: 基础目录（例如：data/teaching/2026-春季/）
        """
        self.base_dir = Path(base_dir)

    def process_class_submission(
        self,
        class_zip: Path,
        class_name: str,
        experiment_id: str
    ) -> OrganizationResult:
        """
        处理班级提交压缩包

        Args:
            class_zip: 班级压缩包路径
            class_name: 班级名称（例如：汽服2302B班）
            experiment_id: 实验ID（例如：07-car-gear）

        Returns:
            整理结果
        """
        result = OrganizationResult()

        # 创建输出目录
        output_dir = self.base_dir / class_name / experiment_id
        reports_dir = output_dir / "reports"
        source_dir = output_dir / "source"

        # 每次整理前清空 reports/ 与 source/，避免上次运行的残留被复评。
        # reports/ 只覆盖同名文件；source/ 仅在"本次找到源码包"时按学生 rmtree 重建——
        # 故学生本次没交源码(改名/漏匹配/漏交)时，其旧 source 目录会被 processor 捡到
        # 复评（与 reports 残留同源的污染）。两目录一并清空，保证"输入即本次"。
        shutil.rmtree(reports_dir, ignore_errors=True)
        shutil.rmtree(source_dir, ignore_errors=True)
        reports_dir.mkdir(parents=True, exist_ok=True)
        source_dir.mkdir(parents=True, exist_ok=True)

        # 创建临时目录
        temp_dir = output_dir / ".temp"
        temp_dir.mkdir(exist_ok=True)

        try:
            # 1. 解压班级压缩包
            class_temp_dir = temp_dir / "class"
            class_temp_dir.mkdir(exist_ok=True)

            print(f"解压班级压缩包: {class_zip.name}")
            safe_extract_zip(class_zip, class_temp_dir, limits=self.CLASS_ZIP_LIMITS)

            # 2. 查找所有学生压缩包
            student_zips = self._find_student_zips(class_temp_dir)
            result.total_students = len(student_zips)
            print(f"找到 {len(student_zips)} 个学生提交")

            # 3. 处理每个学生提交
            for student_zip in student_zips:
                student_result = self._process_student_submission(
                    student_zip,
                    class_name,
                    reports_dir,
                    source_dir,
                    temp_dir
                )

                if student_result['success']:
                    result.successful += 1
                    result.details.append(student_result)
                else:
                    result.failed += 1
                    result.errors.append(f"{student_zip.name}: {student_result.get('error', 'Unknown error')}")

        except Exception as e:
            result.errors.append(f"处理班级压缩包时出错: {str(e)}")

        finally:
            # 清理临时目录
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

        return result

    def _find_student_zips(self, class_dir: Path) -> List[Path]:
        """查找所有学生压缩包"""
        zips = []
        for item in class_dir.rglob("*.zip"):
            # 排除嵌套的ZIP（可能是源代码压缩包）
            # 只处理直接位于班级目录下的ZIP
            if item.parent == class_dir or (
                item.parent.name.startswith("23") and  # 学号开头
                item.stat().st_size < 50 * 1024 * 1024  # 小于50MB（学生提交不会太大）
            ):
                zips.append(item)
        return zips

    def _process_student_submission(
        self,
        student_zip: Path,
        class_name: str,
        reports_dir: Path,
        source_dir: Path,
        temp_dir: Path
    ) -> Dict:
        """
        处理单个学生提交

        Args:
            student_zip: 学生压缩包路径
            class_name: 班级名称
            reports_dir: 报告输出目录
            source_dir: 源代码输出目录
            temp_dir: 临时目录

        Returns:
            处理结果字典
        """
        result = {
            'success': False,
            'student_id': None,
            'name': None,
            'report_path': None,
            'source_path': None,
            'error': None
        }

        try:
            # 1. 从文件名提取学生信息
            student_info = self._extract_student_info(student_zip, class_name)
            if not student_info:
                result['error'] = "无法从文件名提取学生信息"
                return result

            result['student_id'] = student_info.student_id
            result['name'] = student_info.name

            # 2. 创建学生临时目录
            student_temp = temp_dir / student_info.student_id
            student_temp.mkdir(exist_ok=True)

            # 3. 解压学生压缩包
            safe_extract_zip(student_zip, student_temp)

            # 3.5 递归解包"包装层"zip
            # 学习通「按人导出(附件)」的期末综合项目常有多层 zip 套娃：
            #   学号-姓名-ID.zip → 学号-姓名-期末综合项目.zip → 班级姓名.docx + 源码
            # 普通实验首层即含报告，此调用无副作用（找到报告立即返回）。
            self._unwrap_nested_zips(student_temp)

            # 4. 查找并处理报告文件
            report_file = self._find_report_file(student_temp)
            if report_file:
                # 重命名并移动到reports目录
                new_report_name = f"{class_name}-{student_info.student_id}-{student_info.name}-实验报告{report_file.suffix}"
                new_report_path = reports_dir / new_report_name
                shutil.move(str(report_file), str(new_report_path))
                result['report_path'] = str(new_report_path)
                print(f"  [OK] 处理报告: {new_report_name}")
            else:
                result['error'] = "未找到实验报告文件"
                return result

            # 5. 查找并处理源代码
            source_archive = self._find_source_archive(student_temp)
            if source_archive:
                source_file, src_kind, src_info = source_archive
                # 创建源代码目录
                source_name = f"{class_name}-{student_info.student_id}-{student_info.name}-源代码"
                source_path = source_dir / source_name
                # 重跑幂等：先清空旧目录（上一次扁平化留下的顶层 Makefile 会让本次
                # 新解压的嵌套工程被误判 already_flat）。注：这会清除教师对该目录的手改。
                shutil.rmtree(source_path, ignore_errors=True)
                source_path.mkdir(parents=True, exist_ok=True)

                # 解压源代码（增加限制以应对大型项目）
                source_limits = ZipLimits(
                    max_file_count=5000,      # 允许更多文件
                    max_outer_size=500*1024*1024,  # 500MB (学生可能包含大型库文件)
                    max_inner_size=200*1024*1024   # 200MB
                )
                try:
                    if src_kind == '7z':
                        safe_extract_7z(source_file, source_path, limits=source_limits)
                    else:
                        safe_extract_zip(source_file, source_path, limits=source_limits)
                    # 扁平化多余「包装层」目录嵌套（如 QIMO/QIMO/{工程}），
                    # 让真正的工程根落到 source_path 顶层，使 BuildChecker 能找到 Makefile。
                    # 仅在纯包装链时执行；不安全情形原样保留，绝不抛异常。
                    nres = SubmissionNormalizer.flatten(source_path)
                    if nres.flattened:
                        print(f"  [OK] 扁平化源码目录(原嵌套{nres.original_depth}层): {source_name}")
                    elif nres.skip_cause and nres.skip_cause != 'already_flat':
                        print(f"  [INFO] 未扁平化({nres.skip_cause}): {nres.reason}")
                    # 成功解压后清除可能残留的旧 .extraction_error 标记：否则 processor
                    # 读取该标记会让 SourceStateClassifier 优先判损坏/嵌套，连累本次
                    # 已成功解压的工程被误判（如上次失败留下的标记没清，重跑仍判 0）。
                    stale_err = source_dir / f"{source_name}.extraction_error"
                    if stale_err.exists():
                        try:
                            stale_err.unlink()
                        except Exception:
                            pass
                    # 源码提交冗余提示：交了多个归档时写标记，供 processor 带入学生反馈
                    # （明确告知"提交了多份源码，已选用 X，其余未采用"）；单归档时清掉上轮
                    # 残留标记，避免误报。
                    note_path = source_dir / f"{source_name}.source_note"
                    if src_info.get('multiple_archives'):
                        others = ", ".join(src_info.get('others', []))
                        try:
                            note_path.write_text(
                                f"提交包含多个源码压缩包，已自动选用「{src_info.get('chosen', '')}」；"
                                f"其余未采用：{others}。", encoding='utf-8')
                        except Exception:
                            pass
                    elif note_path.exists():
                        try:
                            note_path.unlink()
                        except Exception:
                            pass
                    result['source_path'] = str(source_path)
                    print(f"  [OK] 处理源代码({src_kind}): {source_name}")
                except Exception as e:
                    # 源码解压失败不阻断（报告已处理，可按报告评分；编译将按"无法评估"跳过）。
                    # 关键：清掉残留的空/半空 source_path，否则 processor 会把它当作"有源码但无 Makefile"，
                    # 让编译误判 not_found（实为解压失败）。清空后 processor 检测到无源码 → 编译判 SKIPPED，
                    # 归为「无法评估」并明确提示"未提取到源码工程"，不再误导。
                    shutil.rmtree(source_path, ignore_errors=True)
                    hint = ""
                    if src_kind == '7z' and ('py7zr' in str(e).lower() or '7z' in str(e).lower()):
                        hint = "（教师端请：pip install py7zr）"
                    msg = f"源代码解压失败({src_kind}) {source_file.name}: {e}{hint}"
                    print(f"  [WARN] {msg}")
                    result['source_error'] = msg   # 记录到结果，不再静默吞掉
                    # 写标记文件，供 SubmissionProcessor 读取并归类为 corrupted，
                    # 进而在学生反馈中告知「具体原因 + 改进方法」。
                    try:
                        (source_dir / f"{source_name}.extraction_error").write_text(msg, encoding='utf-8')
                    except Exception:
                        pass
            else:
                print(f"  [WARN] 未找到源代码压缩包: {student_zip.name}")

            result['success'] = True

        except Exception as e:
            result['error'] = str(e)

        return result

    def _extract_student_info(self, file_path: Path, class_name: str) -> Optional[StudentInfo]:
        """
        从文件名提取学生信息

        支持格式：
        - 23071140101-张三.zip
        - 学号-姓名.zip
        - 任意包含学号和姓名的格式

        Args:
            file_path: 文件路径
            class_name: 班级名称

        Returns:
            学生信息，如果提取失败则返回None
        """
        filename = file_path.stem  # 去除扩展名

        # 尝试提取学号
        student_id_match = self.STUDENT_ID_PATTERN.search(filename)
        if not student_id_match:
            return None

        student_id = student_id_match.group(1)

        # 尝试提取姓名
        name_match = self.NAME_PATTERN.search(filename)
        if not name_match:
            return None

        name = name_match.group(1)

        return StudentInfo(
            student_id=student_id,
            name=name,
            class_name=class_name
        )

    def _unwrap_nested_zips(self, directory: Path, max_depth: int = 5) -> None:
        """递归解包"包装层"zip，直到目录里出现真正的提交内容（实验报告）。

        背景：学习通「按人导出(附件)」导出常有多层 zip 套娃，期末综合项目
        尤为典型::

            学号-姓名-ID.zip
              └ 学号-姓名-期末综合项目.zip
                   └ 班级姓名.docx  +  源码.7z      ← 真正的提交内容

        本方法逐层解开这些"包装"zip，使报告落到磁盘上供 `_find_report_file`
        发现。普通实验（07-car-gear）学生包内首层即是「报告 + 源码.zip」，
        首层即可找到报告 → 立即返回，行为不变。

        - 仅在「当前层找不到报告」时才尝试解包；
        - 按命名约定属于源码包的 zip（源代码/工程/code/project/source）不视为
          包装层，避免误把真正的源码包解开（会破坏 source/ 的提取）。
        """
        for _ in range(max_depth):
            if self._find_report_file(directory) is not None:
                return  # 已到达含报告的内容层
            wrappers = [
                p for p in directory.rglob("*.zip")
                if not self._looks_like_source_archive(p)
                and not self._looks_like_source_project(p)
            ]
            if not wrappers:
                return
            progress = False
            for wrapper in wrappers:
                try:
                    dest = directory / f"{wrapper.stem}__unwrapped"
                    dest.mkdir(exist_ok=True)
                    safe_extract_zip(wrapper, dest)
                    wrapper.unlink()  # 删掉包装层，避免后续被当成源码包
                    progress = True
                except Exception:
                    continue
            if not progress:
                return

    def _looks_like_source_archive(self, path: Path) -> bool:
        """文件名是否符合"源代码压缩包"约定（不应被当作包装层解开）。"""
        name = path.name
        name_lower = name.lower()
        # 中文约定：源代码 / 工程；英文约定：code / project / source
        return any(kw in name for kw in ("源代码", "工程")) or \
            any(kw in name_lower for kw in ("code", "project", "source"))

    def _looks_like_source_project(self, zip_path: Path) -> bool:
        """zip 内容是否像一个源码工程（而非提交包装层），应保留给 source/ 提取。

        通过窥视内部条目判断：含工程源码特征（.c/.h/.ioc/.uvprojx/Core//Drivers/
        Makefile/.mxproject 等）且**不含报告**即视为源码工程——否则会把整棵
        CMSIS/HAL 树铺到临时目录。提交包装层（内含 报告.docx + 源码.7z）不含
        这些直接的源码文件，故不会被误判；即便包装层里同时散落了 .c，只要它还
        含报告，就仍按包装层解开以让报告露出。
        """
        try:
            import zipfile as _zf
            with _zf.ZipFile(zip_path) as zf:
                names = [n for n in zf.namelist() if not n.endswith("/")]
        except Exception:
            return False

        # 含报告 → 当作包装层（交给外层去解开让报告露出）
        has_report = any(
            n.lower().endswith((".docx", ".doc", ".pdf", ".wps")) or "报告" in n
            for n in names
        )
        if has_report:
            return False

        for n in names:
            low = n.lower()
            if low.endswith((".c", ".h", ".cpp", ".hpp", ".cxx", ".s",
                             ".ioc", ".uvprojx", ".uvproj")):
                return True
            if low.endswith("makefile") or ".mxproject" in low \
                    or "/core/" in low or "/drivers/" in low:
                return True
        return False

    def _find_report_file(self, directory: Path) -> Optional[Path]:
        """查找报告文件"""
        for ext in self.REPORT_EXTENSIONS:
            # 查找直接匹配的文件
            for file in directory.glob(f"*{ext}"):
                return file

            # 递归查找
            for file in directory.rglob(f"*{ext}"):
                # 确保不是源代码目录中的文件
                if 'source' not in str(file).lower() and 'code' not in str(file).lower():
                    return file

        return None

    def _find_source_archive(self, directory: Path) -> Optional[Tuple[Path, str, Dict]]:
        """查找源代码压缩包（.zip 或 .7z），含嵌套子目录（如 _unwrap 产生的 __unwrapped/）。

        学习通「按人导出(附件)」的综合项目源码常为 .7z，且经 _unwrap_nested_zips
        后位于 __unwrapped/ 子目录，故用 rglob 递归查找。

        Returns:
            (path, kind, info)；info = {multiple_archives, chosen, others}，供反馈告知
            "提交了多份源码"。找不到返回 None。kind ∈ {'zip', '7z'}。
        """
        def _kind(p: Path) -> str:
            return '7z' if p.suffix.lower() == '.7z' else 'zip'

        all_found = list(directory.rglob("*.zip")) + list(directory.rglob("*.7z"))

        def _info(chosen: Path) -> Dict:
            return {
                'multiple_archives': len(all_found) > 1,
                'chosen': chosen.name if chosen else '',
                'others': [p.name for p in all_found if p != chosen],
            }

        # 1) 按命名约定优先（明确为源码包的命名）
        named = ['*源代码*.zip', '*源码*.zip', '*code*.zip', '*project*.zip', '*工程*.zip',
                 '*源代码*.7z', '*源码*.7z']
        for pat in named:
            for f in directory.rglob(pat):
                return f, _kind(f), _info(f)

        # 2) 兜底：在所有归档里挑最可能是源码工程的那一个
        if not all_found:
            return None
        if len(all_found) == 1:
            return all_found[0], _kind(all_found[0]), _info(all_found[0])
        # 多个归档（学生交了多个 zip，如"期末作业.zip"+"期末作业需要删除.zip"）：
        # 旧逻辑直接 return None → 源码判 not_submitted（"未找到源码工程"），连累全源码类 0 分。
        # 改为：优先挑内容像源码工程的（_looks_like_source_project 窥视 .c/.h/Core/Makefile 等）；
        # 都不像则全部作为候选。再按「非垃圾命名 + 体积最大」排序取首个——垃圾命名
        # （删除/废弃/旧/备份…）优先级低于正常命名，避免取到学生自己标记要删的版本。
        project_archives = [f for f in all_found if self._looks_like_source_project(f)]
        candidates = project_archives if project_archives else all_found

        def _archive_score(p: Path) -> Tuple[int, int]:
            try:
                size = p.stat().st_size
            except OSError:
                size = 0
            junk = any(kw in p.name for kw in
                       ("删除", "delete", "废弃", "不要", "旧", "old", "备份", "backup"))
            return (0 if junk else 1, size)  # 非垃圾优先，再按体积

        best = sorted(candidates, key=_archive_score, reverse=True)[0]
        return best, _kind(best), _info(best)

    def generate_summary_report(self, result: OrganizationResult, output_path: Path):
        """生成整理报告"""
        lines = [
            "=" * 60,
            "作业提交格式整理报告",
            "=" * 60,
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "统计信息:",
            f"  总学生数: {result.total_students}",
            f"  成功处理: {result.successful}",
            f"  处理失败: {result.failed}",
            "",
        ]

        if result.details:
            lines.extend([
                "成功详情:",
            ])
            for detail in result.details:
                lines.append(
                    f"  {detail['student_id']}-{detail['name']}: "
                    f"报告={Path(detail['report_path']).name if detail['report_path'] else '无'}, "
                    f"源代码={Path(detail['source_path']).name if detail['source_path'] else '无'}"
                )

        if result.errors:
            lines.extend([
                "",
                "错误详情:",
            ])
            for error in result.errors:
                lines.append(f"  ❌ {error}")

        lines.append("=" * 60)

        report_text = "\n".join(lines)
        output_path.write_text(report_text, encoding='utf-8')

        # 同时生成JSON格式
        import json
        json_path = output_path.with_suffix('.json')
        json_data = {
            'timestamp': datetime.now().isoformat(),
            'statistics': {
                'total': result.total_students,
                'successful': result.successful,
                'failed': result.failed
            },
            'details': result.details,
            'errors': result.errors
        }
        json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description='作业提交格式整理器')
    parser.add_argument('class_zip', type=Path, help='班级压缩包路径')
    parser.add_argument('class_name', type=str, help='班级名称（例如：汽服2302B班）')
    parser.add_argument('experiment_id', type=str, help='实验ID（例如：07-car-gear）')
    parser.add_argument('--base-dir', type=Path, default='data/teaching/2026-春季/', help='基础目录')

    args = parser.parse_args()

    organizer = SubmissionOrganizer(args.base_dir)

    print(f"开始处理班级提交: {args.class_name}")
    print(f"实验: {args.experiment_id}")
    print(f"压缩包: {args.class_zip}")
    print()

    result = organizer.process_class_submission(
        args.class_zip,
        args.class_name,
        args.experiment_id
    )

    print()
    print("=" * 60)
    print("处理完成！")
    print(f"成功: {result.successful}/{result.total_students}")
    print(f"失败: {result.failed}/{result.total_students}")

    if result.errors:
        print()
        print("错误:")
        for error in result.errors:
            print(f"  {error}")

    # 生成报告
    output_dir = args.base_dir / args.class_name / args.experiment_id
    report_path = output_dir / "整理报告.txt"
    organizer.generate_summary_report(result, report_path)
    print(f"报告已生成: {report_path}")


if __name__ == '__main__':
    main()
