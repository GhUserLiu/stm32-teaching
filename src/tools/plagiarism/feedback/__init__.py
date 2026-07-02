"""
反馈生成模块
Feedback Generation Module

生成个性化的学生反馈
"""

from .feedback import (
    FeedbackGenerator,
    save_student_feedback,
    HTMLFeedbackGenerator
)
from .enhanced_feedback import EnhancedFeedbackGenerator
from .smart_feedback import SmartFeedbackEngine
from .unified_feedback import UnifiedFeedbackGenerator

# 兼容性别名
SmartFeedbackGenerator = SmartFeedbackEngine

__all__ = [
    'FeedbackGenerator',
    'EnhancedFeedbackGenerator',
    'SmartFeedbackGenerator',
    'SmartFeedbackEngine',
    'UnifiedFeedbackGenerator',
    'save_student_feedback',
    'HTMLFeedbackGenerator',
]
