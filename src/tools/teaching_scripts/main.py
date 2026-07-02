"""
汽服2302B班实验报告评价系统
汽车档位模拟器设计实验 (07_car_gear_experiment)
"""

import os
import sys
import json
import zipfile
import re
from pathlib import Path
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration
BASE_DIR = Path(__file__).parent.parent.parent.parent
# 路径统一走 src/tools/common/path_config.py（与 auto_grading、GUI 保持一致）
sys.path.insert(0, str(BASE_DIR / "src"))
from tools.common.path_config import get_experiment_paths

# 默认使用最新的实验目录，可通过命令行参数覆盖
_default_paths = get_experiment_paths(
    "2026-春季", "汽服2302B班", "07-car-gear", project_root=BASE_DIR
)
EXPERIMENT_DIR = _default_paths.experiment_dir
EXTRACT_DIR = _default_paths.submissions_dir
PROCESSED_DIR = _default_paths.processed_dir
OUTPUT_DIR = _default_paths.results_dir
TEACHER_OUTPUT = _default_paths.reports_dir       # results/reports
STUDENT_OUTPUT = _default_paths.feedback_dir      # results/feedback

def setup_directories():
    """Create necessary directories"""
    for dir_path in [PROCESSED_DIR, TEACHER_OUTPUT, STUDENT_OUTPUT]:
        dir_path.mkdir(parents=True, exist_ok=True)
    print("[OK] Directory structure ready")

def parse_student_info(zip_filename):
    """Parse student ID from ZIP filename"""
    # Pattern: 23071140201-Name-Random.zip
    match = re.match(r'(\d+)-', zip_filename)
    if match:
        student_id = match.group(1)
        # Try to get name from docx file later instead of ZIP filename
        # due to encoding issues
        return student_id, None
    return None, None

def extract_student_zips():
    """Extract all student ZIP files and return student list"""
    print("Extracting student ZIP files...")

    students = []
    missing_students = []
    extract_dir = EXTRACT_DIR

    for zip_file in extract_dir.glob("*.zip"):
        student_id, student_name = parse_student_info(zip_file.name)
        if not student_id:
            print(f"  Skipping {zip_file.name} (cannot parse ID)")
            continue

        # Extract student ZIP
        student_extract_dir = PROCESSED_DIR / student_id
        student_extract_dir.mkdir(exist_ok=True)

        try:
            # First extraction level
            with zipfile.ZipFile(zip_file, 'r') as zf:
                zf.extractall(student_extract_dir)

            # Check for nested ZIP files and extract them
            nested_zips = list(student_extract_dir.glob("*.zip"))
            for nested_zip in nested_zips:
                try:
                    with zipfile.ZipFile(nested_zip, 'r') as zf:
                        zf.extractall(student_extract_dir)
                    # Optionally remove the nested ZIP after extraction
                    nested_zip.unlink()
                except Exception as e:
                    print(f"    Warning: Could not extract nested ZIP: {e}")

            # Find the .docx file
            docx_files = list(student_extract_dir.rglob("*.docx"))
            if docx_files:
                # Try to extract name from docx filename
                docx_name = docx_files[0].stem  # filename without extension
                students.append({
                    'id': student_id,
                    'name': docx_name,  # Use docx filename as name
                    'path': str(docx_files[0]),
                    'zip_name': zip_file.name
                })
                print(f"  [OK] {student_id}: {docx_files[0].name}")
            else:
                missing_students.append({
                    'id': student_id,
                    'name': '',
                    'path': '',
                    'zip_name': zip_file.name,
                    'missing': True
                })
                print(f"  [X] {student_id}: No .docx found (will record as 0)")

        except Exception as e:
            missing_students.append({
                'id': student_id,
                'name': student_name or '',
                'path': '',
                'zip_name': zip_file.name,
                'missing': True,
                'error': str(e)
            })
            print(f"  [X] {student_id}: Error extracting - {e}")

    # Combine students and missing
    all_students = students + missing_students

    print(f"Extracted {len(students)} student reports")
    print(f"Missing {len(missing_students)} student reports")
    return all_students

def install_dependencies():
    """Install required Python packages"""
    import subprocess
    packages = ['python-docx', 'openpyxl', 'pandas', 'chardet']

    print("Checking/installing required packages...")
    for pkg in packages:
        try:
            __import__(pkg.replace('-', '_'))
            print(f"  [OK] {pkg} already installed")
        except ImportError:
            print(f"  Installing {pkg}...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', pkg, '-q'],
                          check=True)
            print(f"  [OK] {pkg} installed")

def main():
    print("=" * 60)
    print("汽服2302B班 - 实验报告评价系统")
    print("实验: 汽车档位模拟器设计 (07_car_gear_experiment)")
    print("=" * 60)
    print()

    # Setup
    setup_directories()
    install_dependencies()

    # Extract student reports
    students = extract_student_zips()

    # Save student list
    student_list_path = PROCESSED_DIR / "students.json"
    with open(student_list_path, 'w', encoding='utf-8') as f:
        json.dump(students, f, ensure_ascii=False, indent=2, default=str)

    print()
    print(f"Student list saved to: {student_list_path}")
    print()
    print("Next steps:")
    print("1. Run extract_content.py - Extract content from reports")
    print("2. Run evaluate.py - Evaluate reports and generate scores")
    print("3. Run generate_output.py - Generate Excel and feedback documents")

if __name__ == "__main__":
    main()
