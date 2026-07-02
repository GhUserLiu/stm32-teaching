#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
处理实验报告zip文件并执行成绩评定
"""

import os
import sys
import json
import zipfile
import re
import shutil
from pathlib import Path

# 添加路径
SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent.parent.parent.parent
EXPERIMENT_DIR = SCRIPT_DIR.parent / "07-car-gear"
PROCESSED_DIR = EXPERIMENT_DIR / "processed"
SUBMISSIONS_DIR = EXPERIMENT_DIR / "submissions"

# 添加脚本路径
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent.parent / "common" / "scripts"))


def setup_directories():
    """Create necessary directories"""
    for dir_path in [PROCESSED_DIR, PROCESSED_DIR / "extracted"]:
        dir_path.mkdir(parents=True, exist_ok=True)
    print("[OK] Directory structure ready")


def parse_student_info(zip_filename):
    """Parse student ID from ZIP filename"""
    # Pattern: 23071140201-Name-Random.zip
    match = re.match(r'(\d+)-', zip_filename)
    if match:
        student_id = match.group(1)
        return student_id, None
    return None, None


def clean_filename(filename):
    """Clean filename to remove problematic characters"""
    # Replace zero-width spaces and other problematic characters
    return filename.replace('​', '').replace('﻿', '')


def extract_student_zips(zip_path):
    """Extract all student ZIP files"""
    print("Extracting student ZIP files...")

    students = []
    missing_students = []

    # Main extraction directory
    main_extract_dir = PROCESSED_DIR / "extracted_temp"
    if main_extract_dir.exists():
        shutil.rmtree(main_extract_dir, ignore_errors=True)
    main_extract_dir.mkdir()

    try:
        # First, extract the main zip to get nested zips
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Extract all files
            for name in zf.namelist():
                if name.endswith('.zip'):
                    # Clean the filename
                    clean_name = clean_filename(os.path.basename(name))
                    dest_path = main_extract_dir / clean_name
                    # Extract and save the nested zip
                    with open(dest_path, 'wb') as f:
                        f.write(zf.read(name))
                    print(f"  Extracted: {clean_name}")

        # Now find all nested zip files
        nested_zips = list(main_extract_dir.glob("*.zip"))
        print(f"  Found {len(nested_zips)} student zip files")

        for nested_zip_path in nested_zips:
            # Parse student ID from nested zip filename
            zip_basename = nested_zip_path.name
            student_id, _ = parse_student_info(zip_basename)

            if not student_id:
                print(f"  Skipping {zip_basename} (cannot parse ID)")
                continue

            # Create student extraction directory
            student_extract_dir = PROCESSED_DIR / student_id
            student_extract_dir.mkdir(exist_ok=True)

            try:
                # Extract the nested zip
                with zipfile.ZipFile(nested_zip_path, 'r') as nested_zf:
                    nested_zf.extractall(student_extract_dir)

                # Find the .docx file (may need to extract nested zip again)
                docx_files = list(student_extract_dir.rglob("*.docx"))

                # If no docx found, check for nested zip files and extract them
                if not docx_files:
                    nested_zips = list(student_extract_dir.glob("*.zip"))
                    for nz in nested_zips:
                        try:
                            with zipfile.ZipFile(nz, 'r') as nzf:
                                nzf.extractall(student_extract_dir)
                            # Remove the nested zip after extraction
                            nz.unlink()
                        except Exception:
                            pass
                    # Re-check for docx files
                    docx_files = list(student_extract_dir.rglob("*.docx"))

                if docx_files:
                    docx_name = docx_files[0].stem
                    students.append({
                        'id': student_id,
                        'name': docx_name,
                        'path': str(docx_files[0]),
                        'zip_name': zip_basename
                    })
                    print(f"  [OK] {student_id}: {docx_files[0].name}")
                else:
                    missing_students.append({
                        'id': student_id,
                        'name': '',
                        'path': '',
                        'zip_name': zip_basename,
                        'missing': True
                    })
                    print(f"  [X] {student_id}: No .docx found")

            except Exception as e:
                missing_students.append({
                    'id': student_id,
                    'name': '',
                    'path': '',
                    'zip_name': zip_basename,
                    'missing': True,
                    'error': str(e)
                })
                print(f"  [X] {student_id}: Error extracting - {e}")

    except Exception as e:
        print(f"Error opening main ZIP: {e}")
        import traceback
        traceback.print_exc()
        return []

    # Combine students and missing
    all_students = students + missing_students

    print(f"Extracted {len(students)} student reports")
    print(f"Missing {len(missing_students)} student reports")
    return all_students


def main():
    print("=" * 60)
    print("汽服2302B班 - 实验报告评价系统")
    print("实验: 汽车档位模拟器设计 (07_car_gear_experiment)")
    print("=" * 60)
    print()

    # Setup
    setup_directories()

    # Find the zip file
    zip_files = list(SUBMISSIONS_DIR.glob("*按人导出*.zip"))
    if not zip_files:
        print("Error: No submission zip file found")
        return

    zip_path = zip_files[0]
    print(f"Processing: {zip_path.name}")
    print()

    # Extract student reports
    students = extract_student_zips(zip_path)

    # Save student list
    student_list_path = PROCESSED_DIR / "students.json"
    with open(student_list_path, 'w', encoding='utf-8') as f:
        json.dump(students, f, ensure_ascii=False, indent=2, default=str)

    print()
    print(f"Student list saved to: {student_list_path}")
    print()
    print("Next steps:")
    print("1. Extract content from reports")
    print("2. Run quality assessment")
    print("3. Evaluate reports and generate scores")

    return students


if __name__ == "__main__":
    main()
