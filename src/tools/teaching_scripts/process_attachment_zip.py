#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
处理附件格式的实验报告 ZIP 文件
新格式：外层 ZIP → 学生 ZIP → 单个 DOCX 文件
"""

import os
import sys
import json
import zipfile
import re
import shutil
from pathlib import Path

# 配置
BASE_DIR = Path(__file__).parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "teaching" / "2026-春季"


def clean_filename(filename):
    """Clean filename to remove problematic characters"""
    return filename.replace('​', '').replace('﻿', '')


def parse_student_info(zip_filename):
    """Parse student ID and name from ZIP filename"""
    # Pattern: 学号-姓名.zip
    # Try multiple patterns
    patterns = [
        r'^(\d+)-(.+?)\.zip$',  # 学号-姓名.zip
        r'^(\d+)(?:-(.+))?\.zip$',  # 学号-姓名.zip (name optional)
    ]

    for pattern in patterns:
        match = re.match(pattern, zip_filename)
        if match:
            student_id = match.group(1)
            name = match.group(2) if match.lastindex >= 2 else ''
            return student_id, name

    # Fallback: try to extract just the ID
    match = re.match(r'^(\d+)', zip_filename)
    if match:
        return match.group(1), ''

    return None, None


def process_attachment_zip(zip_path, experiment, class_name):
    """
    Process attachment format ZIP file

    Args:
        zip_path: Path to the attachment ZIP file
        experiment: Experiment name (e.g., "07-car-gear")
        class_name: Class name (e.g., "汽服2301B班")

    Returns:
        List of student info dictionaries
    """
    print("=" * 60)
    print(f"处理附件格式 ZIP: {Path(zip_path).name}")
    print(f"实验: {experiment}")
    print(f"班级: {class_name}")
    print("=" * 60)
    print()

    # Setup directories
    experiment_dir = DATA_DIR / class_name / experiment
    submissions_dir = experiment_dir / "submissions"
    extracted_dir = submissions_dir / "extracted"
    processed_dir = experiment_dir / "processed"

    # Clean and create directories
    if extracted_dir.exists():
        shutil.rmtree(extracted_dir)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    if processed_dir.exists():
        shutil.rmtree(processed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Temp directory for first extraction
    temp_dir = processed_dir / "temp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()

    students = []
    missing_students = []

    try:
        # First extraction: extract outer ZIP to get student ZIPs
        print("[1/3] 解压外层 ZIP 文件...")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for name in zf.namelist():
                if name.endswith('.zip'):
                    # Clean the filename
                    clean_name = clean_filename(os.path.basename(name))
                    dest_path = temp_dir / clean_name
                    # Extract and save the nested zip
                    with open(dest_path, 'wb') as f:
                        f.write(zf.read(name))

        # Find all student ZIP files
        student_zips = list(temp_dir.glob("*.zip"))
        print(f"  找到 {len(student_zips)} 个学生 ZIP 文件")
        print()

        # Second extraction: extract each student ZIP
        print("[2/3] 解压学生 ZIP 文件...")
        for student_zip in student_zips:
            zip_name = student_zip.name
            student_id, student_name = parse_student_info(zip_name)

            if not student_id:
                print(f"  [跳过] {zip_name} (无法解析学号)")
                missing_students.append({
                    'id': '',
                    'name': '',
                    'path': '',
                    'zip_name': zip_name,
                    'missing': True,
                    'error': 'Cannot parse student ID'
                })
                continue

            # Create student extraction directory
            student_extract_dir = processed_dir / student_id
            student_extract_dir.mkdir(exist_ok=True)

            try:
                # Extract the student ZIP
                with zipfile.ZipFile(student_zip, 'r') as zf:
                    zf.extractall(student_extract_dir)

                # Find the .docx file (should be only one)
                docx_files = list(student_extract_dir.rglob("*.docx"))

                if docx_files:
                    docx_file = docx_files[0]
                    # Try to extract name from docx filename if not already parsed
                    if not student_name:
                        docx_name = docx_file.stem
                        # Extract name from docx filename pattern
                        # Usually: 实验名称-班级-学号-姓名.docx
                        name_match = re.search(r'-(.+?)-\d+-\d+.*?\.docx$', docx_file.name)
                        if name_match:
                            student_name = name_match.group(1)
                        else:
                            student_name = docx_name

                    students.append({
                        'id': student_id,
                        'name': student_name,
                        'path': str(docx_file),
                        'zip_name': zip_name
                    })
                    print(f"  [OK] {student_id}: {docx_file.name}")
                else:
                    missing_students.append({
                        'id': student_id,
                        'name': student_name,
                        'path': '',
                        'zip_name': zip_name,
                        'missing': True
                    })
                    print(f"  [X] {student_id}: 未找到 .docx 文件")

            except Exception as e:
                missing_students.append({
                    'id': student_id,
                    'name': student_name,
                    'path': '',
                    'zip_name': zip_name,
                    'missing': True,
                    'error': str(e)
                })
                print(f"  [X] {student_id}: 解压错误 - {e}")

        print()

        # Copy DOCX files to extracted directory for easier access
        print("[3/3] 复制文件到 extracted 目录...")
        for student in students:
            if student['path']:
                src = Path(student['path'])
                # Use ID-name as filename
                dest_name = f"{student['id']}-{student['name']}.docx"
                dest = extracted_dir / dest_name
                shutil.copy(src, dest)
                print(f"  复制: {dest_name}")

        print()

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return []

    finally:
        # Clean up temp directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

    # Combine students and missing
    all_students = students + missing_students

    # Save student list
    student_list_path = processed_dir / "students.json"
    with open(student_list_path, 'w', encoding='utf-8') as f:
        json.dump(all_students, f, ensure_ascii=False, indent=2, default=str)

    print("=" * 60)
    print(f"处理完成!")
    print(f"  成功: {len(students)} 个学生报告")
    print(f"  缺失: {len(missing_students)} 个学生报告")
    print(f"  学生列表: {student_list_path}")
    print(f"  提取目录: {extracted_dir}")
    print("=" * 60)

    return all_students


def main():
    import argparse

    parser = argparse.ArgumentParser(description='处理附件格式的实验报告 ZIP 文件')
    parser.add_argument('zip_path', type=Path, help='附件格式 ZIP 文件路径')
    parser.add_argument('--experiment', default='07-car-gear', help='实验名称')
    parser.add_argument('--class', dest='class_name', required=True, help='班级名称')

    args = parser.parse_args()

    if not args.zip_path.exists():
        print(f"错误: 文件不存在: {args.zip_path}")
        sys.exit(1)

    process_attachment_zip(
        zip_path=args.zip_path,
        experiment=args.experiment,
        class_name=args.class_name
    )


if __name__ == "__main__":
    main()
