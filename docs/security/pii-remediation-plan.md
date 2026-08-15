# 学生隐私数据（PII）入史清理方案

> 状态：**待执行**（filter-repo 改写历史属不可逆操作，由维护者按本文步骤亲自执行）
> 创建：2026-08-15 · 依据：《项目诊断与重构方案》P0 项

## 1. 事实（已取证）

| 项 | 值 |
| --- | --- |
| 入库文件数 | **153**（results_pre_rerun_20260629 下 151：汽服2301B班 78 + 汽服2302B班 73；docs/ 下残余 2，见下行） |
| 路径 | `data/teaching/2026-春季/汽服230{1,2}B班/final-project/results_pre_rerun_20260629/` |
| 残余 PII | `汽服2302B班/docs/plagiarism_groups.txt`（11 行学号+姓名，GBK）；`汽服2302B班/docs/汽服2302B班_2026春季_实验成绩册_自动评分.xlsx`（35 名学生学号/成绩/抄袭标记）——2026-08-15 内容级二次扫描发现，旧 `data/teaching/*/*.xlsx` 一级目录模式未覆盖 docs/ 子目录 |
| 内容 | 学生反馈 md/docx、评分 JSON，**文件名与内容含真实学号 + 姓名** |
| 根因 | 旧 `.gitignore` 只匹配 `results/` 与 `results_backup*/`，不匹配 `results_pre_rerun_*` |
| 远端 | `origin = https://github.com/GhUserLiu/stm32-teaching.git` —— **GitHub 同样持有这些提交** |

## 2. 已完成的修复（2026-08-15，本次会话）

1. `.gitignore` 三处修复：
   - `results/` + `results_backup*/` → **`data/teaching/**/results*/`**（通配任意生成批次目录）；
   - 新增 `data/teaching/**/课程档案/`（成绩单 PDF 等含 PII）；
   - `outputs/` 由按扩展名枚举改为**整目录忽略**（曾漏掉 `.md`）；顺带新增 `database/*.sqlite`。
2. `git rm -r --cached` 已解除 **153** 个文件的跟踪（151 个 results_pre_rerun + 2 个 docs/ 残余；**磁盘文件保留**，仅不再入库）——变更已暂存，待提交。
3. 二次加固：`.gitignore` 新增任意深度 `data/teaching/**/*.xls(x)` 与 `data/teaching/**/plagiarism_groups*.txt` 规则。

## 3. 待执行：清历史（按顺序，逐步确认）

```bash
R="c:/Users/liuzh/Projects/Workspace/stm32-teaching"

# Step 1: commit this round (gitignore fix + untracked PII), filter-repo needs a clean repo
git -C "$R" add .gitignore
git -C "$R" commit -m "security: untrack PII results and close gitignore gaps"

# Step 2: full mirror backup -- the ONLY rollback path, verify it exists before continuing
# (path anchored to the repo's parent dir, independent of your current CWD)
git clone --mirror "$R" "$R/../stm32-teaching-backup-$(date +%Y%m%d).git"
ls "$R"/../stm32-teaching-backup-*.git/HEAD

# Step 3: rewrite history, dropping both PII directories (git-filter-repo already installed)
git -C "$R" filter-repo --force --invert-paths \
  --path "data/teaching/2026-春季/汽服2301B班/final-project/results_pre_rerun_20260629" \
  --path "data/teaching/2026-春季/汽服2302B班/final-project/results_pre_rerun_20260629" \
  --path "data/teaching/2026-春季/汽服2302B班/docs/plagiarism_groups.txt" \
  --path "data/teaching/2026-春季/汽服2302B班/docs/汽服2302B班_2026春季_实验成绩册_自动评分.xlsx"

# Step 4: verify -- ALL THREE commands must print 0
git -C "$R" rev-list --objects --all | grep -c results_pre_rerun
git -C "$R" log --all --oneline -- "*results_pre_rerun*" | wc -l
git -C "$R" rev-list --objects --all | grep -cE "plagiarism_groups|成绩册"

# Step 5: filter-repo removes remotes for safety -- re-add and force-push
git -C "$R" remote add origin https://github.com/GhUserLiu/stm32-teaching.git
git -C "$R" push origin --force --all
git -C "$R" push origin --force --tags
```

**注意**：filter-repo 会改写**全部提交哈希**——任何其他机器上的旧克隆必须重新 clone，不能 pull 合并。

## 4. 远端（GitHub）残余风险

- force-push 后，旧提交在 GitHub 侧**可能仍可通过哈希访问**（悬空对象保留一段时间；关联过 PR/Issue 的引用不会自动清除）。
- 彻底清除需联系 GitHub Support（提供仓库名与 commit 哈希，说明误提交 PII）。
- 私有仓库且无 fork 时实际暴露面有限；若为公开仓库，请立即执行本文并同步联系 Support。

## 5. 回滚（仅当 Step 3 之后发现误删）

```bash
# restore .git from the mirror backup taken in Step 2
# NOTE: replace YYYYMMDD with the real backup date; mirror clones are BARE,
# so core.bare must be flipped back before any working-tree command works.
rm -rf "$R/.git" && mkdir "$R/.git"
cp -r "$R/../stm32-teaching-backup-YYYYMMDD.git"/* "$R/.git/"
git -C "$R" config core.bare false   # mirror backup is bare; un-bare it
git -C "$R" reset --hard             # re-align working tree
```

## 6. 长效防再犯

- 目录通配规则已上线：任何 `results*` 命名的新批次目录自动忽略。
- 建议（列入 P2 顺手项）：pre-commit 钩子拦截 `data/teaching/` 下新增跟踪文件（`docs/` 与说明类 `.md` 白名单除外）。
