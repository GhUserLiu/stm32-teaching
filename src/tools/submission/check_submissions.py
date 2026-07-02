#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
学生提交检查工具
功能：
1. 提取学生信息（姓名、学号、提交时间）
2. 根据提交时间判断原创和抄袭（相同提交时间=疑似抄袭）
3. 生成评分报告（没交和作弊都是0分）

使用方法：
1. 先解压主zip文件到extracted目录
2. 运行此脚本
"""

import os
import sys
import zipfile
import re
import io
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# Windows控制台编码修复
if sys.platform == 'win32':
    import io as io_module
    sys.stdout = io_module.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io_module.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


class SubmissionChecker:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.results = []
        self.students_missing_report = []
        self.students_missing_record = []

    def parse_student_id(self, filename):
        """从文件名中提取学号（11位数字）"""
        match = re.search(r'(\d{11})', filename)
        if match:
            return match.group(1)
        return None

    def extract_name_from_filename(self, filename):
        """从文件名提取姓名"""
        # 格式: 汽服2302B班-23071140201-董雨航-答题记录.doc
        match = re.match(r'.*-(\d{11})-(.+?)(?:-答题记录\.doc|\.docx)', filename)
        if match:
            return match.group(2)
        return None

    def extract_from_doc_xml(self, doc_data):
        """从doc文件的XML中提取答题人和提交时间"""
        doc_str = str(doc_data, errors='ignore')

        # 提取答题人
        pattern1 = r'<w:t>答题人：[^<]*</w:t>\s*.*?<w:t>([^<]+)</w:t>'
        name_match = re.search(pattern1, doc_str, re.DOTALL)
        name = name_match.group(1).strip() if name_match else None

        # 提取提交时间
        pattern2 = r'<w:t>提交时间：[^<]*</w:t>\s*.*?<w:t>(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})[^<]*</w:t>'
        time_match = re.search(pattern2, doc_str, re.DOTALL)
        time_str = time_match.group(1).strip() if time_match else None

        return name, time_str

    def process_student_submission(self, outer_zip_path):
        """处理单个学生的提交"""
        filename = os.path.basename(outer_zip_path)
        student_id = self.parse_student_id(filename)

        if not student_id:
            return None

        result = {
            'student_id': student_id,
            'name': None,
            'submission_time': None,
            'has_report': False,
            'has_record': False,
            'zip_file': filename
        }

        try:
            with zipfile.ZipFile(outer_zip_path, 'r') as outer_zip:
                files = outer_zip.namelist()

                if not files:
                    return result

                # 处理内层zip
                if files[0].endswith('.zip'):
                    inner_data = outer_zip.read(files[0])
                    with zipfile.ZipFile(io.BytesIO(inner_data), 'r') as inner_zip:
                        inner_files = inner_zip.namelist()

                        for f in inner_files:
                            # 从文件名提取姓名
                            name = self.extract_name_from_filename(f)
                            if name and not result['name']:
                                result['name'] = name

                            # 检查文件类型
                            if f.endswith('.docx') and '答题记录' not in f:
                                result['has_report'] = True

                            if '答题记录' in f and f.endswith('.doc'):
                                result['has_record'] = True
                                doc_data = inner_zip.read(f)
                                record_name, time_str = self.extract_from_doc_xml(doc_data)
                                if time_str:
                                    result['submission_time'] = time_str
                                if record_name and not result['name']:
                                    result['name'] = record_name
                else:
                    # 直接doc文件（少数情况）
                    for f in files:
                        if '答题记录' in f:
                            result['has_record'] = True
                            doc_data = outer_zip.read(f)
                            record_name, time_str = self.extract_from_doc_xml(doc_data)
                            if time_str:
                                result['submission_time'] = time_str

        except Exception as e:
            print(f"  Error processing {student_id}: {e}")

        return result

    def process_all(self):
        """处理所有学生提交"""
        zip_files = list(self.base_dir.glob('*.zip'))

        print(f"找到 {len(zip_files)} 个学生提交文件")
        print("=" * 60)

        for i, zip_file in enumerate(zip_files, 1):
            print(f"[{i}/{len(zip_files)}] 处理: {zip_file.name[:50]}...")

            result = self.process_student_submission(str(zip_file))
            if result:
                self.results.append(result)

        print("=" * 60)
        print(f"处理完成！共处理 {len(self.results)} 个学生提交\n")

    def check_plagiarism(self, results):
        """根据提交时间检查抄袭（相同提交时间=疑似抄袭）"""
        valid_results = [r for r in results if r.get('submission_time')]
        time_to_students = defaultdict(list)

        for r in valid_results:
            time_str = r['submission_time']
            time_to_students[time_str].append(r)

        # 找出相同时间提交的学生
        suspicious_groups = []
        for time_str, students in time_to_students.items():
            if len(students) > 1:
                suspicious_groups.append({
                    'time': time_str,
                    'students': students,
                    'count': len(students)
                })

        # 按人数排序
        suspicious_groups.sort(key=lambda x: x['count'], reverse=True)

        return suspicious_groups

    def generate_report(self):
        """生成评分报告"""
        suspicious_groups = self.check_plagiarism(self.results)

        # 统计
        students_with_time = [r for r in self.results if r.get('submission_time')]
        students_missing_report = [r for r in self.results if not r['has_report']]
        plagiarism_count = sum(len(g['students']) for g in suspicious_groups)

        print("=" * 80)
        print("汽服2302B班 - 作业提交检查报告")
        print("=" * 80)

        print(f"\n【统计】")
        print(f"  总人数: {len(self.results)}")
        print(f"  有提交时间: {len(students_with_time)}")
        print(f"  未提交实验报告: {len(students_missing_report)}")
        print(f"  疑似抄袭: {plagiarism_count}")

        # 按时间排序的学生列表
        print("\n" + "=" * 80)
        print("【一】按提交时间排序的学生列表")
        print("=" * 80)
        print(f"{'学号':<12} {'姓名':<12} {'提交时间':<20}")
        print("-" * 50)

        students_with_time.sort(key=lambda x: x['submission_time'])
        for r in students_with_time:
            print(f"{r['student_id']:<12} {r['name'] or '未知':<12} {r['submission_time']}")

        # 疑似抄袭
        print("\n" + "=" * 80)
        print("【二】相同提交时间统计（疑似抄袭，0分）")
        print("=" * 80)

        if suspicious_groups:
            for group in suspicious_groups:
                print(f"\n提交时间: {group['time']}  ({group['count']}人)")
                for student in group['students']:
                    print(f"  {student['student_id']}  {student['name']}")
        else:
            print("  无相同提交时间")

        # 未提交实验报告
        print("\n" + "=" * 80)
        print("【三】未提交实验报告（0分）")
        print("=" * 80)
        for r in students_missing_report:
            print(f"  {r['student_id']}  {r['name'] or '未知'}")

        # 评分建议
        print("\n" + "=" * 80)
        print("【评分建议】")
        print("=" * 80)
        print(f"  1. 未提交实验报告: {len(students_missing_report)}人 → 0分")
        print(f"  2. 疑似抄袭（相同提交时间）: {plagiarism_count}人 → 0分")
        print(f"  3. 正常提交: {len(students_with_time) - plagiarism_count}人 → 正常评分")
        print("=" * 80)

        # 保存到文件
        self.save_report(suspicious_groups, students_missing_report, plagiarism_count)

    def save_report(self, suspicious_groups, students_missing_report, plagiarism_count):
        """保存报告到文件"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = self.base_dir.parent / f'评分报告_{timestamp}.txt'

        students_with_time = [r for r in self.results if r.get('submission_time')]
        students_with_time.sort(key=lambda x: x['submission_time'])

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("汽服2302B班 - 作业提交检查报告\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"【统计】\n")
            f.write(f"  总人数: {len(self.results)}\n")
            f.write(f"  有提交时间: {len(students_with_time)}\n")
            f.write(f"  未提交实验报告: {len(students_missing_report)}\n")
            f.write(f"  疑似抄袭: {plagiarism_count}\n\n")

            f.write("=" * 80 + "\n")
            f.write("【一】按提交时间排序的学生列表\n")
            f.write("=" * 80 + "\n")
            f.write(f"{'学号':<12} {'姓名':<12} {'提交时间':<20}\n")
            f.write("-" * 50 + "\n")
            for r in students_with_time:
                f.write(f"{r['student_id']:<12} {r['name'] or '未知':<12} {r['submission_time']}\n")

            f.write("\n" + "=" * 80 + "\n")
            f.write("【二】相同提交时间统计（疑似抄袭，0分）\n")
            f.write("=" * 80 + "\n")
            if suspicious_groups:
                for group in suspicious_groups:
                    f.write(f"\n提交时间: {group['time']}  ({group['count']}人)\n")
                    for student in group['students']:
                        f.write(f"  {student['student_id']}  {student['name']}\n")
            else:
                f.write("  无相同提交时间\n")

            f.write("\n" + "=" * 80 + "\n")
            f.write("【三】未提交实验报告（0分）\n")
            f.write("=" * 80 + "\n")
            for r in students_missing_report:
                f.write(f"  {r['student_id']}  {r['name'] or '未知'}\n")

            f.write("\n" + "=" * 80 + "\n")
            f.write("【评分建议】\n")
            f.write("=" * 80 + "\n")
            f.write(f"  1. 未提交实验报告: {len(students_missing_report)}人 → 0分\n")
            f.write(f"  2. 疑似抄袭（相同提交时间）: {plagiarism_count}人 → 0分\n")
            f.write(f"  3. 正常提交: {len(students_with_time) - plagiarism_count}人 → 正常评分\n")
            f.write("=" * 80 + "\n")

        print(f"\n报告已保存到: {report_file}")


def main():
    # 默认路径
    script_dir = Path(__file__).parent.parent
    default_dir = script_dir / 'docs/teaching/2026-春季/汽服2302B班/07-car-gear/submissions/extracted'

    # 如果没有提供参数，使用默认路径
    if len(sys.argv) > 1:
        base_dir = Path(sys.argv[1])
    else:
        base_dir = default_dir

    if not base_dir.exists():
        print(f"错误：目录不存在: {base_dir}")
        print("\n请先解压文件到extracted目录，或提供正确路径:")
        print(f"  python {sys.argv[0]} <目录路径>")
        return

    print(f"工作目录: {base_dir}\n")

    checker = SubmissionChecker(str(base_dir))
    checker.process_all()
    checker.generate_report()


if __name__ == '__main__':
    main()
