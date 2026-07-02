"""
报告生成模块
Report Generation Module

生成 Excel、HTML、JSON 格式的报告
"""

from .report import (
    PlagiarismReport,
    ReportConfig
)

__all__ = [
    'PlagiarismReport',
    'ReportConfig',
]
