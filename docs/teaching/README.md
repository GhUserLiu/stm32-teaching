# 作业管理文件夹

本目录用于管理所有课程的作业、实验报告和评估数据。

## 目录结构

```
assignments/
├── common/                    # 通用评估脚本和模板
│   ├── scripts/               # 评估脚本
│   ├── templates/            # 报告模板
│   ├── rubrics/              # 评分标准
│   └── README.md             # 使用说明
│
├── 2026-春季/                # 2026年春季学期
│   ├── 汽服2302B班/
│   │   ├── 07-car-gear/      # 实验07：汽车档位模拟器
│   │   │   ├── submissions/ # 原始作业
│   │   │   ├── processed/   # 评估数据
│   │   │   ├── feedback/    # 反馈文档
│   │   │   └── results/     # 评分结果
│   │   │   ├── task.md      # 任务书
│   │   │   ├── task.docx    # 任务书DOCX
│   │   │   ├── task.pdf     # 任务书PDF
│   │   │   └── README.md    # 实验说明
│   │   └── [其他实验]/
│   └── [其他班级]/
│
└── archive/                  # 归档过去学期
```

## 使用说明

### 新增实验

1. 在对应学期/班级下创建实验文件夹
2. 添加任务书文件 (task.md, task.docx, task.pdf)
3. 创建子文件夹：submissions/, processed/, feedback/, results/
4. 编写 README.md 说明实验内容

### 评估作业

1. 将学生作业放入 `submissions/` 文件夹
2. 运行 `assignments/common/scripts/main.py` 提取内容
3. 运行评估脚本生成评分和反馈

详见 `assignments/common/README.md`

## 命名规范

- 学期：`YYYY-季节` (如 2026-春季)
- 班级：使用课程全名 (如 汽服2302B班)
- 实验：`序号-简短英文名` (如 07-car-gear)
- 文件：
  - 任务书：task.{md,docx,pdf}
  - 模板：template.{md,docx}
  - 评分标准：rubric.json
