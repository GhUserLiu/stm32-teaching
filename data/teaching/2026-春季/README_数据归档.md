# 2026-春季 学生数据归档说明

> 建立时间：2026-09-22

## 已移出本目录的大体量数据

以下目录已于 2026-09-22 移出工作区，存放到本机 D 盘归档区
（同盘移动，原路径结构完整保留）：

**归档根目录：`D:\教学归档\stm32-teaching\data\teaching\2026-春季\`**

| 原位置（本目录下） | 内容 | 体量 |
|---|---|---|
| `汽服2301B班/07-car-gear/` | 实验课学生提交（submissions/source）及批量产出（reports/results） | 约 20,000 文件 |
| `汽服2302B班/07-car-gear/` | 同上 | 约 12,000 文件 |
| `汽服2301B班/final-project/source/` | 课设学生源代码（每人一份完整 CubeMX 工程） | 合计约 52,000 文件 |
| `汽服2302B班/final-project/source/` | 同上 | ↑ |
| `汽服*/final-project/{processed, reports, results*}/` | 课设评分/查重/报告批量产出 | 约 500 文件 |

## 本目录保留的内容

- 成绩单 xls（根目录）
- `课程档案/`、`Downloads/`
- 班级 docs（任务书、实验成绩册、README）

## 移出原因

学生提交自带完整 STM32 HAL/CMSIS 库，一个班的课设+实验数据共约
85,000 个文件，拖慢 VSCode/Pylance 索引与文件监视（"large number of
source files" 警告的来源）。数据本身未做任何修改，仅改变存放位置。

## 如需恢复

在 Git Bash 中执行（同盘移动，瞬时完成）：

```bash
mv "/d/教学归档/stm32-teaching/data/teaching/2026-春季/汽服2301B班/07-car-gear" \
   "/d/4-Workspace/stm32-teaching/data/teaching/2026-春季/汽服2301B班/"
# 其余目录同理，把归档路径换回工作区路径即可
```

## 注意

- 归档区 `D:\教学归档` **不在任何 git 仓库内**，无版本控制和异地备份，
  与工作区同盘（D:）。重要原始数据请自行另行备份。
- 相关工具（auto_grading、plagiarism 等）的路径事实源仍是
  `data/config/teaching/config.yaml` 的 `teaching_dir: "data/teaching"`；
  如需对 2026-春季 重跑分析，先按上文恢复数据。
