"""
增强版实验报告查重与评分系统
Enhanced Plagiarism Detection and Grading System for Lab Reports

v2.6.0 - 模块化重构版本

模块结构：
- core: 核心查重检测
- grading: 评分系统
- feedback: 反馈生成
- quality: 质量评估
- code: 代码分析
- image: 图像处理
- report: 报告生成
- utils: 工具函数
"""

# ========== 核心检测模块 ==========
try:
    from .core import (
        PlagiarismDetector,
        SimilarityResult,
        SimilarityMethod
    )
except ImportError:
    pass

# ========== 评分模块 ==========
try:
    from .grading import (
        GradingSystem,
        EnhancedGradingSystem
    )
except ImportError:
    pass

# ========== 反馈模块 ==========
try:
    from .feedback import (
        FeedbackGenerator,
        EnhancedFeedbackGenerator,
        SmartFeedbackGenerator,
        UnifiedFeedbackGenerator
    )
except ImportError:
    pass

# ========== 质量评估模块 ==========
try:
    from .quality import (
        EnhancedQualityAssessor,
        AdaptiveThresholdEngine,
        TechnicalValidator
    )
except (ImportError, RuntimeError) as e:
    import sys
    print(f"[WARNING] Failed to import quality module in plagiarism __init__: {e}", file=sys.stderr)
    pass

# 代码分析模块的 re-export 已移除（线上经 code_analysis.code_analyzer 直接导入；
# 历史 `from .code import` 指向不存在的 code/ 包，恒静默失败）。

# ========== 图像处理模块 ==========
try:
    from .image import (
        ImageQualityChecker,
        ImageCounter
    )
except ImportError:
    pass

# ========== 报告生成模块 ==========
try:
    from .report import (
        PlagiarismReport,
        ReportConfig
    )
except ImportError:
    pass

# ========== 兼容旧版导入 ==========
# 保留一些旧模块的直接导入以保持兼容性
# 注: code_obfuscation / semantic / ai_detection 等死链 re-export 已移除
#     (包已删或从不存在, try/except 兜底恒静默失败, 详见死代码清理 commit)。
try:
    from .image_similarity import ImageDetector
except ImportError:
    pass

try:
    from .image_quality import ImageQualityAssessor
except ImportError:
    pass

__version__ = '2.4.0'

__all__ = [
    # 核心检测
    'PlagiarismDetector',
    'SimilarityResult',
    'SimilarityMethod',
    # 评分
    'GradingSystem',
    'EnhancedGradingSystem',
    # 反馈
    'FeedbackGenerator',
    'EnhancedFeedbackGenerator',
    'SmartFeedbackGenerator',
    'UnifiedFeedbackGenerator',
    # 质量评估
    'QualityAssessment',
    'AdaptiveThreshold',
    'TechnicalValidator',
    # 代码分析
    'CodeAnalyzer',
    'CodeQualityAnalyzer',
    # 图像处理
    'ImageQualityChecker',
    'ImageCounter',
    # 报告
    'PlagiarismReport',
    'ReportConfig',
]

# ========== 向后兼容性层 ==========
# 以下导入保持与旧版本的兼容性
# 警告: 这些可能在未来版本中弃用

try:
    # 从 quality 模块导入旧版技术检查
    from .quality import (
        TechnicalChecker,
        ExperimentType,
        CheckResult,
        ContentStructureChecker,
        CodeSnippetChecker,
        ThinkingQuestionsChecker
    )
except ImportError:
    pass

try:
    # 从 grading 模块导入旧版评分函数
    from .grading import (
        batch_grade,
        load_rubric_for_experiment,
        GradingResult
    )
except ImportError:
    pass

try:
    # 从 feedback 模块导入旧版反馈函数
    from .feedback import (
        save_student_feedback,
        HTMLFeedbackGenerator
    )
except ImportError:
    pass

# 历史 `from .code import (analyze_code_from_report, CodeAnalysisResult)` 已移除
# (.code 包不存在; 线上代码分析走 code_analysis.code_analyzer)。

# 将兼容性导出添加到 __all__
__all__.extend([
    # 旧版评分
    'batch_grade',
    'load_rubric_for_experiment',
    'GradingResult',
    # 旧版技术检查
    'TechnicalChecker',
    'ExperimentType',
    'CheckResult',
    'ContentStructureChecker',
    'CodeSnippetChecker',
    'ThinkingQuestionsChecker',
    # 旧版反馈
    'save_student_feedback',
    'HTMLFeedbackGenerator',
    # 代码分析
    'analyze_code_from_report',
    'CodeAnalysisResult',
])
