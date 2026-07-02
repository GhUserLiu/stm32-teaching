# 增强版实验报告查重与质量评估系统

> 版本: 2.6.0 (模块化重构)
> 作者: STM32F407 教学团队

## 🎯 模块化架构

本系统已重构为模块化架构，各功能模块独立维护：

```
tools/plagiarism/
├── core/              # 核心查重检测
│   ├── detector.py    # 检测器主逻辑
│   └── algorithms.py  # 相似度算法
├── grading/           # 评分系统
│   ├── grading.py     # 基础评分
│   └── enhanced_grading.py  # 增强评分
├── feedback/          # 反馈生成
│   ├── feedback.py    # 基础反馈
│   └── unified_feedback.py  # 统一反馈
├── quality/           # 质量评估
│   ├── quality.py     # 质量评估
│   └── technical_checks.py  # 技术检查
├── code/              # 代码分析
│   ├── code_analyzer.py  # 代码分析器
│   └── code_quality_analyzer.py  # 代码质量
├── image/             # 图像处理
│   ├── image_quality_checker.py  # 图像质量检查
│   └── image_counter.py  # 图像计数
├── report/            # 报告生成
│   └── report.py      # 报告生成器
└── utils/             # 工具函数
    ├── config.py      # 配置管理
    └── template.py    # 模板处理
```

## 📦 快速开始

### 基础使用

```python
from tools.plagiarism.core import PlagiarismDetector
from tools.plagiarism.report import PlagiarismReport

# 创建检测器
detector = PlagiarismDetector(
    method=SimilarityMethod.HYBRID,
    threshold=60.0
)

# 执行检测
results = detector.detect(submissions)

# 生成报告
report = PlagiarismReport(config)
report.generate_excel()
```

### 评分系统

```python
from tools.plagiarism.grading import EnhancedGradingSystem

grading = EnhancedGradingSystem(rubric_path='rubric.json')
results = grading.grade(submissions)
```

### 反馈生成

```python
from tools.plagiarism.feedback import UnifiedFeedbackGenerator

generator = UnifiedFeedbackGenerator(style='detailed')
feedback = generator.generate(student_result)
```

## 🔧 API 参考

### 核心检测 (core)

| 类/函数 | 说明 |
|--------|------|
| `PlagiarismDetector` | 查重检测器 |
| `SimilarityMethod` | 相似度计算方法枚举 |
| `SimilarityResult` | 相似度结果 |

### 评分系统 (grading)

| 类/函数 | 说明 |
|--------|------|
| `GradingSystem` | 基础评分系统 |
| `EnhancedGradingSystem` | 增强评分系统 |
| `GradingValidator` | 评分验证器 |

### 反馈生成 (feedback)

| 类/函数 | 说明 |
|--------|------|
| `FeedbackGenerator` | 基础反馈生成器 |
| `EnhancedFeedbackGenerator` | 增强反馈生成器 |
| `SmartFeedbackGenerator` | 智能反馈生成器 |

### 质量评估 (quality)

| 类/函数 | 说明 |
|--------|------|
| `QualityAssessment` | 质量评估器 |
| `AdaptiveThreshold` | 自适应阈值 |
| `TechnicalValidator` | 技术检查器 |

## 📝 迁移指南

如果你在使用旧版 API，请参考以下迁移指南：

### v2.5 → v2.6

```python
# 旧版
from tools.plagiarism import PlagiarismDetector

# 新版
from tools.plagiarism.core import PlagiarismDetector
```

```python
# 旧版
from tools.plagiarism import grading

# 新版
from tools.plagiarism.grading import EnhancedGradingSystem
```

## 🚀 新功能

- **模块化架构**: 各功能模块独立，便于维护
- **更好的导入**: 使用 `from tools.plagiarism.<module> import ...`
- **兼容性**: 保留旧版 API 的兼容导入

## 📚 更多文档

- [评分指南](GRADING.md)
- [配置说明](../security_config.json)
- [主项目文档](../../../README.md)

## 🔗 相关链接

- [教师端 GUI 应用](../teaching_management_gui/)
- [学生端 GUI 应用](../student_submission_gui/)
- [教学工具](../../../docs/teaching/)
