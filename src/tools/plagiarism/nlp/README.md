# NLP增强模块使用文档

## 概述

本模块提供了一系列NLP增强功能，用于改进查重和评分系统的检测能力，防止通过简单的字符修改绕过检测。

## 主要功能

### 1. 增强关键词匹配 (`enhanced_matcher.py`)

#### 功能
- **词边界匹配**: 防止通过字符分割绕过（如 `G P I O`）
- **模糊匹配**: 使用编辑距离和相似度算法
- **术语变体词典**: 自动识别技术术语的多种形式

#### 使用示例
```python
from tools.plagiarism.nlp import EnhancedKeywordMatcher, MatchMethod

matcher = EnhancedKeywordMatcher(
    use_fuzzy=True,
    use_variants=True,
    fuzzy_threshold=0.85
)

# 简单匹配
matched, ratio = matcher.match_keywords(
    text="使用GPIO配置LED灯...",
    keywords=["GPIO", "中断", "状态机"]
)

# 详细匹配
results, ratio = matcher.match_keywords(
    text="G P I O 配置...",
    keywords=["GPIO"],
    method=MatchMethod.HYBRID
)

for r in results:
    print(f"{r.keyword}: matched={r.matched}, confidence={r.confidence}")
```

#### 支持的术语变体
| 标准词 | 变体 |
|--------|------|
| GPIO | gpio, Gpio, G P I O, G-P-I-O, 通用IO |
| 中断 | 外部中断, EXTI, ISR, 中断服务 |
| DWT | dwt, Data Watchpoint, 数据断点 |
| 消抖 | 去抖, debounce, 防抖 |

---

### 2. 高级模板过滤 (`template_filter.py`)

#### 功能
- **N-gram匹配**: 使用字符级和词级N-gram
- **语义哈希**: 对字符顺序变化不敏感
- **结构化匹配**: 保留标点、空格等结构特征

#### 使用示例
```python
from tools.plagiarism.nlp import AdvancedTemplateFilter, FilterMethod

# 从模板创建过滤器
template = "实验目的：掌握STM32的GPIO配置..."
filter_obj = AdvancedTemplateFilter(
    template_content=template,
    ngram_sizes=[3, 4, 5],
    similarity_threshold=0.7
)

# 过滤文本
result = filter_obj.filter(
    text="实　验　目　的　：掌握STM32的GPIO配置...",
    method=FilterMethod.HYBRID
)

print(f"原始文本: {result.original_text[:50]}...")
print(f"过滤后: {result.filtered_text[:50]}...")
print(f"移除比例: {result.removal_ratio:.1%}")
```

#### 检测模板操纵
```python
# 检测学生是否操纵模板
manipulation = filter_obj.detect_template_manipulation(student_text)
if manipulation['detected']:
    print(f"检测到操纵: {manipulation['techniques']}")
    print(f"置信度: {manipulation['confidence']:.1%}")
```

---

### 3. 代码AST分析 (`code_analyzer_nlp.py`)

#### 功能
- **函数结构分析**: 提取函数名、参数、调用关系
- **变量重命名检测**: 识别变量名的系统性替换
- **控制流分析**: 检测if/for/while等结构的变化
- **代码规范化**: 移除注释和空白差异

#### 使用示例
```python
from tools.plagiarism.nlp import compare_code_blocks

code1 = """
void led_init(void) {
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_RESET);
}
"""

code2 = """
void灯初始化(void) {
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_RESET);
}
"""

result = compare_code_blocks(code1, code2)

print(f"整体相似度: {result.overall_similarity:.1f}%")
print(f"结构相似度: {result.structure_similarity:.1f}%")
print(f"逻辑相似度: {result.logic_similarity:.1f}%")

if result.obfuscation_detected:
    print(f"检测到混淆: {[t.value for t in result.obfuscation_detected]}")
```

---

### 4. 增强评分系统 (`enhanced_grading.py`)

#### 功能
- 集成NLP增强的评分器
- 提供详细的匹配信息
- 检测混淆行为

#### 使用示例
```python
from tools.plagiarism.nlp.enhanced_grading import enhance_grading_system
from tools.plagiarism.grading import RubricLoader

# 加载评分标准
rubric = RubricLoader.load(Path('rubric.json'))

# 创建增强评分器
grader = enhance_grading_system(rubric, fuzzy_threshold=0.85)

# 评分
result = grader.grade(
    student_id="23071140201",
    name="张三",
    text="学生报告内容...",
    return_details=True
)

# 查看详细匹配信息
print(f"总分: {result.total_score}")
print(f"NLP置信度: {result.nlp_confidence:.1%}")

for detail in result.match_details:
    print(f"{detail.keyword}: {detail.method} ({detail.confidence:.1%})")
```

---

### 5. NLP集成引擎 (`nlp_integration.py`)

#### 功能
统一的NLP增强接口，集成所有NLP功能

#### 使用示例
```python
from tools.plagiarism.nlp import create_nlp_enhanced_detector, get_preset

# 使用预设配置
config = get_preset('strict')  # 'default', 'strict', 'lenient', 'fast'
engine = create_nlp_enhanced_detector(
    template_content="模板内容...",
    fuzzy_threshold=0.85,
    strict_mode=True
)

# 增强相似度检查
result = engine.enhance_similarity_check(
    text1="报告1...",
    text2="报告2...",
    code1="代码1...",
    code2="代码2..."
)

print(f"检测到的混淆: {result.detected_obfuscations}")
print(f"建议: {result.recommendations}")
```

---

## 配置预设

| 预设 | 模糊匹配 | 模板过滤 | AST分析 | 适用场景 |
|------|----------|----------|---------|----------|
| `default` | 0.85 | 0.7 | ✓ | 日常使用 |
| `strict` | 0.90 | 0.9 | ✓ | 重要检测 |
| `lenient` | 0.75 | 0.5 | ✓ | 宽松检测 |
| `fast` | ✗ | 0.7 | ✗ | 快速批处理 |

---

## 集成到现有系统

### 方式1: 使用增强评分器
```python
from tools.plagiarism.nlp.enhanced_grading import EnhancedRubricGrader

grader = EnhancedRubricGrader(rubric, fuzzy_threshold=0.85)
result = grader.grade(student_id, name, text)
```

### 方式2: 使用NLP引擎
```python
from tools.plagiarism.nlp import NLPEngine, NLPEngineConfig

config = NLPEngineConfig(
    enable_fuzzy_matching=True,
    fuzzy_threshold=0.85
)
engine = NLPEngine(config)

matched, ratio, details = engine.enhance_keyword_matching(
    text, keywords, return_details=True
)
```

### 方式3: 打补丁
```python
from tools.plagiarism.nlp import patch_grading_system

EnhancedGrader = patch_grading_system()
grader = EnhancedGrader(rubric)
```

---

## 漏洞修复对照

| 原漏洞 | 修复方案 | 对应模块 |
|--------|----------|----------|
| 关键词匹配简单 | 词边界+模糊匹配 | `enhanced_matcher.py` |
| 模板过滤绕过 | N-gram+语义哈希 | `template_filter.py` |
| 代码检测阈值过高 | AST结构分析 | `code_analyzer_nlp.py` |
| 跨组检测漏洞 | 保守策略标记 | 需手动配置 |
| 结构相似度不准 | 章节级结构分析 | `template_filter.py` |

---

## 性能考虑

- **模糊匹配**: 略慢于精确匹配，但准确度提升显著
- **AST分析**: 对于大型代码块可能较慢，建议设置代码长度限制
- **N-gram过滤**: N越大越准确，但计算量越大（建议3-5）

---

## 依赖项

```
jieba (可选) - 中文分词
numpy (可选) - 数值计算
```

安装：
```bash
pip install jieba numpy
```
