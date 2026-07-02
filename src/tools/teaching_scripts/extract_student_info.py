#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从学习通下载的zip文件中提取学生信息
- 从文件名中提取学生姓名
- 区分有实验报告和没有实验报告的学生
"""

import zipfile
import re
import json
import os
import sys

try:
    from docx import Document
except ImportError:
    print("Warning: python-docx not installed, cannot read docx files")
    print("Install: pip install python-docx")

def extract_student_info(zip_path):
    """
    从学习通下载的zip文件中提取学生信息

    返回: {学号: {'name': 姓名, 'has_report': 是否有实验报告}}
    """
    student_info = {}

    with zipfile.ZipFile(zip_path, 'r') as main_zip:
        # 获取所有学生zip文件
        student_zips = [f for f in main_zip.namelist() if f.endswith('.zip')]

        print(f"找到 {len(student_zips)} 个学生文件")

        for student_zip_name in student_zips:
            # 从文件名中提取学号和姓名
            # 格式: 学号-姓名-数字.zip
            match = re.match(r'(\d+)-(.+?)-(\d+)\.zip', student_zip_name)

            if not match:
                print(f"无法解析文件名: {student_zip_name}")
                continue

            student_id = match.group(1)
            name = match.group(2)

            # 解压内层zip
            try:
                with main_zip.open(student_zip_name) as student_zip_file:
                    with zipfile.ZipFile(student_zip_file) as inner_zip:
                        inner_files = inner_zip.namelist()

                        # 查找第二层zip（实验报告zip）
                        report_zip = None
                        for f in inner_files:
                            if f.endswith('.zip'):
                                report_zip = f
                                break

                        if not report_zip:
                            # 没有实验报告zip
                            student_info[student_id] = {
                                'name': name,
                                'has_report': False,
                                'has_answer_record': False
                            }
                            continue

                        # 解压最内层zip
                        with inner_zip.open(report_zip) as report_zip_file:
                            with zipfile.ZipFile(report_zip_file) as final_zip:
                                final_files = final_zip.namelist()

                                # 检查是否有答题记录和实验报告
                                has_answer = any('答题' in f for f in final_files)
                                has_report = any(f.endswith('.docx') and '答题' not in f for f in final_files)

                                student_info[student_id] = {
                                    'name': name,
                                    'has_report': has_report,
                                    'has_answer_record': has_answer,
                                    'files': final_files
                                }

            except Exception as e:
                print(f"处理学生 {student_id} 时出错: {e}")
                student_info[student_id] = {
                    'name': name,
                    'has_report': False,
                    'error': str(e)
                }

    return student_info

def read_answer_record(docx_path):
    """
    从答题记录doc文件中读取学生信息

    注意: 这是.doc格式，需要使用其他方法
    """
    # TODO: 实现.doc文件读取
    pass

def main():
    zip_path = '汽服2302B班-_实验报告（第七次实验 汽车档位模拟器设计）(按人导出)(word).zip'

    print("=" * 60)
    print("学习通文件信息提取")
    print("=" * 60)

    # 提取学生信息
    student_info = extract_student_info(zip_path)

    # 统计
    total = len(student_info)
    has_report = sum(1 for s in student_info.values() if s.get('has_report'))
    no_report = total - has_report

    print(f"\n统计结果:")
    print(f"  总人数: {total}")
    print(f"  有实验报告: {has_report}")
    print(f"  无实验报告: {no_report}")

    # 保存为JSON
    output_file = 'data/student_info_from_zip.json'
    os.makedirs('data', exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(student_info, f, ensure_ascii=False, indent=2)

    print(f"\n学生信息已保存到: {output_file}")

    # 显示前10个学生
    print(f"\n前10个学生信息:")
    for i, (sid, info) in enumerate(list(student_info.items())[:10]):
        status = "有报告" if info.get('has_report') else "无报告"
        print(f"  {sid}: {info['name']} ({status})")

if __name__ == '__main__':
    main()
