# EIDE 多项目构建指南

## 方法一：修改 eide.yml（推荐）

编辑 `.eide/eide.yml`，修改 `currentProject` 字段：

```yaml
# 切换到不同项目，修改这里
currentProject: 01-turn-signal    # 当前构建的项目

# 源码目录会自动更新
srcDirs:
  - projects/01-turn-signal
  - common/hal
```

### 切换项目步骤

1. 打开 `.eide/eide.yml`
2. 修改 `currentProject` 和 `srcDirs` 中的项目名
3. 保存后 EIDE 会自动重新加载

### 示例：切换到新项目

```yaml
# 从 01-turn-signal 切换到 02-new-project
currentProject: 02-new-project

srcDirs:
  - projects/02-new-project    # 修改这里
  - common/hal
```

---

## 方法二：为每个项目创建独立配置

为每个项目创建独立的 EIDE 配置文件：

```
.eide/
├── eide-01-turn-signal.yml
├── eide-02-new-project.yml
└── eide.yml -> eide-01-turn-signal.yml  # 符号链接指向当前项目
```

### 切换步骤

1. 复制当前配置：`cp .eide/eide.yml .eide/eide-XX-project.yml`
2. 修改新配置中的项目路径
3. 更新符号链接或重命名文件

---

## 当前 EIDE 配置 (01-turn-signal)

```yaml
srcDirs:
  - projects/01-turn-signal
  - common/hal

incList:
  - projects/01-turn-signal
  - common/inc
  - common/hal
```

---

## 注意事项

1. **修改后需重新加载**: 修改 eide.yml 后，VS Code 可能需要重新加载窗口
2. **构建输出**: 每个项目的输出在 `build/项目名/` 目录下
3. **排除模板**: `_template` 和 `Test6` 已在 excludeList 中排除
