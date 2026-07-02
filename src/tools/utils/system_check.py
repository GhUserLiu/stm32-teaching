#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
系统兼容性检测
System Compatibility Check

检测当前系统是否支持各种增强功能
"""

import os
import sys
import platform
import multiprocessing
from pathlib import Path

# Windows控制台编码修复
if platform.system() == 'Windows':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def check_system_info():
    """检查系统信息"""
    print("=" * 60)
    print("系统信息")
    print("=" * 60)

    print(f"操作系统: {platform.system()} {platform.release()}")
    print(f"Python版本: {sys.version.split()[0]}")
    print(f"处理器: {platform.processor()}")

    # CPU核心数
    cpu_count = multiprocessing.cpu_count()
    print(f"CPU核心数: {cpu_count}")

    # 内存信息
    try:
        import psutil
        mem = psutil.virtual_memory()
        print(f"总内存: {mem.total / (1024**3):.1f} GB")
        print(f"可用内存: {mem.available / (1024**3):.1f} GB")
    except ImportError:
        print("内存信息: 需要安装 psulpip install psutil")

    print()


def check_multiprocessing_support():
    """检查多进程支持"""
    print("=" * 60)
    print("多进程支持检测")
    print("=" * 60)

    cpu_count = multiprocessing.cpu_count()

    if cpu_count >= 2:
        print(f"✅ 支持 {cpu_count} 进程并行")

        # 估算性能提升
        speedup = min(4, cpu_count)  # 最多4倍加速
        print(f"   预计性能提升: 最高 {speedup}x")

        # 并行评分建议
        if cpu_count >= 4:
            print(f"   建议工作进程数: {cpu_count - 1} (保留1核给系统)")
        else:
            print(f"   建议工作进程数: 2")
    else:
        print("⚠️ CPU核心数不足，建议使用单进程")

    # Windows特别说明
    if platform.system() == 'Windows':
        print("\n💡 Windows系统注意事项:")
        print("   - 多进程代码必须放在 if __name__ == '__main__': 块中")
        print("   - 或使用 spawn 方式启动进程")

    print()

    return cpu_count >= 2


def check_disk_space():
    """检查磁盘空间"""
    print("=" * 60)
    print("磁盘空间检测")
    print("=" * 60)

    # 检查项目目录
    project_dir = Path(__file__).parents[2]
    stats = os.statvfs(project_dir) if hasattr(os, 'statvfs') else None

    if stats:
        total = stats.f_frsize * stats.f_blocks / (1024**3)
        free = stats.f_frsize * stats.f_bavail / (1024**3)
        print(f"项目目录: {project_dir}")
        print(f"总空间: {total:.1f} GB")
        print(f"可用空间: {free:.1f} GB")

        if free < 1:
            print("⚠️ 可用空间不足1GB")
        elif free < 5:
            print("⚠️ 可用空间偏低")
        else:
            print("✅ 磁间空间充足")
    else:
        # Windows使用 shutil
        import shutil
        usage = shutil.disk_usage(project_dir)
        total = usage.total / (1024**3)
        free = usage.free / (1024**3)
        print(f"项目目录: {project_dir}")
        print(f"总空间: {total:.1f} GB")
        print(f"可用空间: {free:.1f} GB")

        if free < 1:
            print("⚠️ 可用空间不足1GB")
        elif free < 5:
            print("⚠️ 可用空间偏低")
        else:
            print("✅ 磁间空间充足")

    print()


def check_model_storage():
    """检查模型存储空间"""
    print("=" * 60)
    print("语义模型存储检测")
    print("=" * 60)

    model_dir = Path(__file__).parents[2] / 'models'
    model_dir.mkdir(exist_ok=True)

    # 检查现有模型
    existing_models = list(model_dir.glob('**/*'))
    existing_size = sum(f.stat().st_size for f in existing_models if f.is_file()) / (1024**2)

    print(f"模型目录: {model_dir}")
    print(f"现有模型大小: {existing_size:.1f} MB")

    # 预留空间
    required_space = 200  # MB
    import shutil
    usage = shutil.disk_usage(model_dir)
    free = usage.free / (1024**2)

    if free >= required_space:
        print(f"✅ 可用空间充足 ({free:.0f} MB)")
        print(f"   可存储约 {int(free / 100)} 个100MB模型")
    else:
        print(f"⚠️ 可用空间不足 ({free:.0f} MB < {required_space} MB)")

    print()


def check_dependencies():
    """检查依赖包"""
    print("=" * 60)
    print("依赖包检测")
    print("=" * 60)

    packages = {
        'numpy': '数值计算',
        'pandas': '数据处理',
        'openpyxl': 'Excel读写',
        'python-docx': 'Word文档处理',
        'sentence-transformers': '语义相似度(可选)',
        'psutil': '系统信息(可选)'
    }

    missing = []
    for package, description in packages.items():
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}: {description}")
        except ImportError:
            print(f"❌ {package}: {description} [缺失]")
            missing.append(package)

    if missing:
        print(f"\n需要安装: pip install {' '.join(missing)}")

    print()


def check_student_data_storage():
    """检查学生数据存储"""
    print("=" * 60)
    print("学生数据存储检测")
    print("=" * 60)

    data_dir = Path(__file__).parents[2] / 'student_profiles'
    data_dir.mkdir(exist_ok=True)

    print(f"数据目录: {data_dir}")
    print(f"✅ 数据目录已创建")

    # 估算存储需求
    students = 50  # 假设50人
    experiments = 7  # 7个实验
    per_student = 10  # KB 每学生每实验

    total_size = students * experiments * per_student / 1024  # MB
    print(f"预估存储需求: {total_size:.1f} MB")
    print(f"   ({students}人 × {experiments}实验 × {per_student}KB)")

    print()


def generate_recommendations():
    """生成优化建议"""
    print("=" * 60)
    print("优化建议")
    print("=" * 60)

    cpu_count = multiprocessing.cpu_count()
    platform_name = platform.system()

    recommendations = []

    # 多进程建议
    if cpu_count >= 4:
        recommendations.append("✅ 启用批量评分并行化（建议3-4个工作进程）")
    elif cpu_count >= 2:
        recommendations.append("✅ 可启用批量评分并行化（建议2个工作进程）")
    else:
        recommendations.append("⚠️ 建议使用单进程评分")

    # 模型建议
    try:
        __import__('sentence_transformers')
        recommendations.append("✅ 可启用语义相似度评分")
    except ImportError:
        recommendations.append("💡 安装 sentence-transformers 后可启用语义评分")

    # 系统特定建议
    if platform_name == 'Windows':
        recommendations.append("💡 Windows系统：多进程代码需要 if __name__ 保护")

    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")

    print()


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("评分系统兼容性检测 v2.6.0")
    print("=" * 60)
    print()

    # 执行各项检测
    check_system_info()
    mp_support = check_multiprocessing_support()
    check_disk_space()
    check_model_storage()
    check_student_data_storage()
    check_dependencies()
    generate_recommendations()

    print("=" * 60)
    print("检测完成")
    print("=" * 60)


if __name__ == '__main__':
    main()
