# 实验报告评分系统使用指南

> 版本: 2.1.0
> 功能: 查重检测 + 详细评分 + 技术检查 + 个性化反馈

## 功能概述

本系统提供全面的实验报告自动评分功能：

| 功能模块 | 说明 |
|---------|------|
| **查重检测** | 多算法相似度检测，跨组抄袭识别 |
| **Rubric评分** | 基于评分标准的自动打分 |
| **技术检查** | 专项技术要点验证（GPIO/中断/状态机等） |
| **代码检查** | 代码质量评估（注释/命名/结构） |
| **思考题检查** | 思考题回答验证 |
| **结构检查** | 报告章节完整性检查 |
| **个性化反馈** | 为每个学生生成详细反馈 |

## 快速开始

### 基础用法

```bash
# 完整分析（查重 + 评分 + 反馈）
python tools/plagiarism_detection_enhanced.py

# 指定实验目录
python tools/plagiarism_detection_enhanced.py \
    --experiment-dir "docs/teaching/2026-春季/汽服2302B班/07-car-gear"

# 仅查重
python tools/plagiarism_detection_enhanced.py --plagiarism-only

# 仅评分
python tools/plagiarism_detection_enhanced.py --quality-only
```

### 命令行参数

```
--experiment-dir     实验目录路径
--experiment-type    实验类型（档位实验/转向灯实验）
--class-name         班级名称
--threshold          查重阈值 (0-100，默认: 60)
--method             相似度算法 (sequence/cosine/jaccard/levenshtein/hybrid)
--template           模板文件（用于排除公共内容）
--plagiarism-only    仅执行查重
--quality-only       仅执行评分
--output-formats     报告格式（excel,json,html）
```

## 评分标准 (Rubric)

### 档位实验评分标准

| 类别 | 分值 | 评分要点 |
|------|------|----------|
| 团队协作 | 5分 | 成员信息、分工明确、协作记录 |
| 实验态度 | 10分 | 出勤情况（教师评定） |
| 实验原理与认知 | 10分 | 实验目的、原理阐述、应用场景 |
| 实验完成度 | 35分 | 硬件连接(15)、实验结果(20) |
| 代码质量 | 30分 | 流程图(6)、关键代码(8)、注释(8)、中断说明(4)、模块划分(4) |
| 实验报告质量 | 10分 | 问题记录(2)、协作解决(1)、个人心得(2)、思考题(5) |

### 技术要点检查（额外加分项）

| 检查项 | 分值 | 说明 |
|--------|------|------|
| LED0引脚配置 | 4分 | PF9，低电平有效 |
| LED1引脚配置 | 4分 | PF10，低电平有效 |
| 按键中断配置 | 7分 | PE4，下降沿触发，外部中断 |
| GPIO初始化 | 5分 | 模式、上拉、中断配置 |
| DWT消抖实现 | 8分 | DWT周期计数器使用 |
| 中断服务函数 | 5分 | HAL_GPIO_EXTI_Callback |
| 状态机逻辑 | 7分 | P→R→N→D循环切换 |
| 档位显示功能 | 8分 | 各档位LED显示正确 |
| 消抖效果验证 | 6分 | 消抖效果说明 |
| 功能完整性 | 6分 | 功能完整无缺陷 |

## 输出文件

```
实验目录/results/
├── 查重报告.xlsx           # Excel查重报告
├── 查重报告.json           # JSON查重数据
├── 查重报告.html           # HTML可视化报告
├── grading_results.json    # 详细评分结果
└── feedback/               # 学生反馈
    ├── 学号_姓名_反馈.md   # Markdown格式
    └── 学号_姓名_反馈.html # HTML格式
```

### grading_results.json 格式

```json
[
  {
    "student_id": "23071140201",
    "name": "张三",
    "total_score": 85.5,
    "total_possible": 100,
    "percentage": 85.5,
    "grade": "B",
    "category_scores": {
      "team_collaboration": {
        "name": "团队协作",
        "earned": 5.0,
        "possible": 5.0,
        "percentage": 100.0,
        "feedback": ["✓ 成员基本信息完整", "✓ 个人分工明确合理"]
      },
      ...
    },
    "technical_check": {
      "score": 52.0,
      "strengths": ["✓ 正确说明LED0连接到PF9"],
      "weaknesses": ["✗ 缺少或错误: DWT消抖实现"]
    },
    "strengths": ["团队协作: 正确", "硬件连接: 完整"],
    "weaknesses": ["软件设计: 代码注释不足"],
    "recommendations": ["【代码质量】需要增加注释说明"],
    "plagiarism_risk": 0.15,
    "auto_confidence": 0.85
  }
]
```

## 学生反馈示例

### Markdown 格式

```markdown
# 实验报告评分反馈

**学号**: 23071140201
**姓名**: 张三
**总分**: 85.5/100 (85.5%)
**等级**: B

---

## 各项得分详情

### ✅ 团队协作 (5/5)
- ✓ 成员基本信息完整
- ✓ 个人分工明确合理

### ⚠️ 代码质量 (18/30)
- ✓ 代码流程图清晰
- △ 关键代码完整规范 (部分)
- ✗ 代码注释详尽

...
```

### HTML 格式

生成的 HTML 反馈文件包含：
- 响应式设计，支持移动端查看
- 颜色编码（绿色=优秀，橙色=中等，红色=不足）
- 抄袭警告醒目显示
- 详细的改进建议列表

## API 使用

### 基础评分

```python
from tools.plagiarism import (
    RubricLoader,
    RubricGrader,
    batch_grade
)

# 加载评分标准
rubric = RubricLoader.load('docs/teaching/common/rubrics/rubric.json')

# 准备提交数据
submissions = {
    '2023001': {'name': '张三', 'text': '报告内容...'},
    '2023002': {'name': '李四', 'text': '报告内容...'}
}

# 批量评分
results = batch_grade(submissions, rubric)

for result in results:
    print(f"{result.name}: {result.total_score}/{result.total_possible} - {result.grade}")
```

### 技术检查

```python
from tools.plagiarism import TechnicalChecker, ExperimentType

# 执行技术检查
score, results, strengths, weaknesses = TechnicalChecker.check_all(
    text,
    ExperimentType.CAR_GEAR
)

print(f"技术要点得分: {score}")
print("亮点:", strengths)
print("需加强:", weaknesses)
```

### 生成学生反馈

```python
from tools.plagiarism import save_student_feedback
from pathlib import Path

# 保存反馈文件
feedback_path = save_student_feedback(
    student_id='2023001',
    name='张三',
    grading_result=grading_result,
    technical_results=(score, results, strengths, weaknesses),
    output_dir=Path('results/feedback'),
    plagiarism_risk=0.15,
    format='html'
)
```

## 自定义评分标准

编辑 `docs/teaching/common/rubrics/rubric.json`:

```json
{
  "experiment_name": "您的实验名称",
  "total_points": 100,
  "categories": [
    {
      "id": "custom_category",
      "name": "自定义类别",
      "points": 20,
      "criteria": [
        {
          "description": "具体要求",
          "points": 10,
          "keywords": ["关键词1", "关键词2"]
        }
      ]
    }
  ]
}
```

## 常见问题

### Q: 如何调整评分标准？
A: 编辑 `docs/teaching/common/rubrics/rubric.json` 文件，修改类别、分值和关键词。

### Q: 技术检查的得分如何计算？
A: 基于关键词匹配比例，完全匹配得满分，部分匹配得部分分数。

### Q: 如何禁用某些检查项？
A: 在 `rubric.json` 中将对应项的 `points` 设为 0，或删除该项。

### Q: 学生反馈可以自定义吗？
A: 可以编辑 `tools/plagiarism/feedback.py` 中的 `FeedbackGenerator` 类。

### Q: 如何处理未提交的学生？
A: 系统自动识别，记 0 分，等级为 F，并在反馈中提示尽快提交。

## 版本历史

### v2.1.0 (2024-06)
- 新增基于 Rubric 的详细评分
- 新增技术要点专项检查
- 新增学生个性化反馈生成
- 新增思考题自动检查
- 增强代码质量评估

### v2.0.0 (2024-05)
- 初始版本
- 基础查重功能
- 简单质量评估
