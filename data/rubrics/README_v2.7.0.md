# 评分系统 v2.7.0 功能总结

## 🎉 完成情况

### v2.6.0 基础功能
| 功能 | 状态 | 文件 |
|------|------|------|
| 抄袭自动扣分 | ✅ | `tools/plagiarism/grading.py` |
| 简化代码质量分析 | ✅ | `tools/plagiarism/simplified_code_checker.py` |
| 图片数量检测 | ✅ | `tools/plagiarism/image_counter.py` |

### v2.7.0 新增功能
| 功能 | 状态 | 文件 |
|------|------|------|
| **语义相似度评分** | ✅ | `tools/plagiarism/semantic_answer_grader.py` |
| **学生进步追踪** | ✅ | `tools/plagiarism/student_progress_tracker.py` |
| **批量评分并行化** | ✅ | `tools/plagiarism/parallel_grading.py` |
| **小组协作分析** | ✅ | `tools/plagiarism/team_collaboration_analyzer.py` |

---

## 📊 系统检测结果

```
操作系统: Windows 10
CPU核心数: 16核
可用内存: 15.9 GB
可用磁盘: 342.6 GB
```

**性能预估：**
| 学生数 | 单进程 | 并行(8进程) | 加速比 |
|--------|--------|-------------|--------|
| 20人 | 40秒 | 10秒 | 4.0x |
| 40人 | 80秒 | 15秒 | 5.3x |
| 60人 | 120秒 | 20秒 | 6.0x |
| 80人 | 160秒 | 25秒 | 6.4x |

---

## 🚀 功能详解

### 1. 语义相似度评分

**模型：** paraphrase-multilingual-MiniLM-L12-v2 (~100MB)

**测试结果：**
| 测试类型 | 相似度 | 得分 | 评价 |
|----------|--------|------|------|
| 完整答案 vs 简短答案 | 84.7% | 4.0/5.0 | ✅ 语义匹配良好 |
| 部分正确 vs 完整答案 | 76.5% | 4.0/5.0 | ✅ 核心意思识别 |
| 意思相近 vs 标准答案 | 82.8% | 4.0/5.0 | ✅ 同义词识别 |
| 完全错误 vs 正确答案 | 1.0% | 1.0/5.0 | ✅ 正确识别错误 |

**使用方法：**
```python
from tools.plagiarism.semantic_answer_grader import (
    SemanticAnswerGrader,
    grade_thinking_questions
)

# 评分思考题
results = grade_thinking_questions(report_text)
for result in results:
    print(f"相似度: {result.similarity}%")
    print(f"得分: {result.score}/{result.max_score}")
    print(f"需要复核: {result.needs_review}")
```

---

### 2. 学生进步追踪

**存储：** SQLite数据库，存储一学期数据 (~3.4MB for 50人×7实验)

**功能：**
- 跨实验成绩追踪
- 进步趋势分析 (improving/stable/declining)
- 薄弱环节识别
- 风险学生预警
- 个性化学习建议

**使用方法：**
```python
from tools.plagiarism.student_progress_tracker import (
    StudentProgressTracker,
    track_student_progress
)

# 记录实验成绩
track_student_progress(
    student_id='23071140201',
    name='张三',
    class_name='汽服2302B班',
    experiment_id='07_car_gear',
    experiment_name='汽车档位实验',
    grading_result=result_dict
)

# 获取学生档案
tracker = StudentProgressTracker()
profile = tracker.get_student_profile('23071140201')

print(f"平均分: {profile.average_score}")
print(f"趋势: {profile.score_trend}")
print(f"薄弱环节: {profile.weak_areas}")
print(f"学习建议: {profile.suggestions}")

# 导出学习报告
report_path = tracker.export_student_report('23071140201')
```

---

### 3. 批量评分并行化

**配置：** 自动使用 8 个工作进程 (16核CPU)

**性能提升：** 40人班级从 80秒 → 15秒 (5.3x加速)

**使用方法：**
```python
from tools.plagiarism.parallel_grading import parallel_grade

results = parallel_grade(
    submissions=submissions,
    rubric=rubric,
    enable_plagiarism_check=True,
    max_workers=8,  # 可选，默认自动
    verbose=True
)
```

---

### 4. 小组协作分析

**功能：**
- 组员报告相似度检测
- 疑似搭便车识别
- 疑似抄袭对子发现
- 协作质量评估

**测试结果：**
```
小组ID: test_team
成员数量: 3
协作质量: fair

建议:
  ⚠️ 小组协作存在一些问题，建议关注
  疑似抄袭对子: 23071140201-23071140203

相似度详情:
  张三 - 李四: 60.6%
  张三 - 王五: 100.0%
    ⚠️ 报告整体相似度过高 (100.0%)
    ⚠️ 心得体会几乎完全相同 (100.0%) - 疑似搭便车
```

**使用方法：**
```python
from tools.plagiarism.team_collaboration_analyzer import (
    TeamCollaborationAnalyzer,
    generate_team_report
)

analyzer = TeamCollaborationAnalyzer()
result = analyzer.analyze_team(team_members, team_id)

print(f"协作质量: {result.overall_collaboration_quality}")
print(f"疑似搭便车: {result.potential_free_riders}")
print(f"疑似抄袭: {result.potential_plagiarism_pairs}")

# 生成报告
report = generate_team_report(result)
```

---

## 📁 完整文件清单

### 新增文件 (v2.7.0)
```
tools/plagiarism/
├── semantic_answer_grader.py      # 语义相似度评分
├── student_progress_tracker.py     # 学生进步追踪
├── parallel_grading.py             # 批量评分并行化
└── team_collaboration_analyzer.py  # 小组协作分析

tools/utils/
└── system_check.py                 # 系统兼容性检测

models/
└── sentence_transformers/         # 语义模型缓存目录

student_profiles/
├── progress.db                     # 学生进步数据库
└── reports/                       # 学习报告输出目录
```

### 修改文件 (v2.6.0)
```
tools/plagiarism/grading.py         # 扩展GradingResult，添加抄袭扣分
docs/teaching/common/rubrics/
├── rubric_enhanced.json           # 增强版评分标准
└── README_v2.6.0.md               # v2.6.0文档
```

---

## 🔧 依赖包

### 已安装
- ✅ sentence-transformers (语义评分)
- ✅ torch (模型运行时)
- ✅ python-docx (Word文档处理)

### 使用前确认
```bash
python tools/utils/system_check.py
```

---

## 📈 使用场景示例

### 场景1：完整评分流程

```python
from tools.plagiarism.enhanced_grading_system import enhanced_batch_grade
from tools.plagiarism.parallel_grading import parallel_grade
from tools.plagiarism.student_progress_tracker import track_student_progress

# 1. 加载提交
submissions = load_submissions()

# 2. 并行评分（含抄袭检测）
results = parallel_grade(
    submissions=submissions,
    rubric=rubric,
    enable_plagiarism_check=True
)

# 3. 记录到进步追踪
for result in results:
    track_student_progress(
        student_id=result['student_id'],
        name=result['name'],
        class_name='汽服2302B班',
        experiment_id='07_car_gear',
        experiment_name='汽车档位实验',
        grading_result=result
    )
```

### 场景2：生成学生学习报告

```python
from tools.plagiarism.student_progress_tracker import StudentProgressTracker

tracker = StudentProgressTracker()
profile = tracker.get_student_profile('23071140201')

if profile.at_risk:
    print(f"⚠️ 风险学生: {profile.name}")
    for reason in profile.risk_reasons:
        print(f"  - {reason}")

# 导出报告
report_path = tracker.export_student_profile('23071140201')
print(f"报告已保存: {report_path}")
```

### 场景3：小组协作分析

```python
from tools.plagiarism.team_collaboration_analyzer import (
    TeamCollaborationAnalyzer
)

analyzer = TeamCollaborationAnalyzer()

# 分析所有小组
team_results = analyzer.analyze_all_teams(submissions, group_info)

for team_id, result in team_results.items():
    if result.overall_collaboration_quality == 'poor':
        print(f"🚨 小组 {team_id} 需要关注")
        print(f"  搭便车: {result.potential_free_riders}")
        print(f"  疑似抄袭: {result.potential_plagiarism_pairs}")
```

---

## 🎯 后续改进方向

### 可选扩展
1. **时间投入评估** - 根据提交时间计算加分
2. **批量报告生成** - 一键生成所有学生学习报告
3. **教师看板** - 班级整体数据可视化
4. **AI辅助反馈** - 基于学生问题生成针对性建议

### 已知限制
1. 语义模型需要首次下载 (~100MB)
2. 多进程在Windows需要特殊处理
3. 进步追踪数据需要定期备份

---

## 📞 技术支持

如遇问题，请运行系统检测：
```bash
python tools/utils/system_check.py
```

查看详细文档：
- v2.6.0: [README_v2.6.0.md](README_v2.6.0.md)
- 本文档: [README_v2.7.0.md](README_v2.7.0.md)
