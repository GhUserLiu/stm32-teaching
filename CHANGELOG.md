# 更新日志

## [2.0.0] - 2026-06-26 - 教师端/学生端 GUI v2.0

### 教师端与学生端 GUI
- 两个 GUI 统一升级到 **v2.0**（窗口标题、侧栏版本号、关于对话框、`__version__`）。
- `启动教学管理系统.bat` 启动时打印版本横幅。

### 修复（关键）
- **编译检查吞错误**：`auto_grading/build_checker.py` 原用 `subprocess.run(text=True)`，
  在中文 Windows 上按 GBK 解码 make/gcc/ld 输出；学生源码目录名固定含中文，链接诊断里
  相应路径会出现 GBK 无法解码的字节，使读管道线程崩、`result.stderr` 变 `None`，
  `result.stdout + result.stderr` 抛 `TypeError: can only concatenate str (not "NoneType")
  to str`，被外层 `except` 记成 `status=error`，把真实编译/链接错误（如 `undefined reference`）
  吞成一段谁都看不懂的 Python 报错。
  - 改为按字节捕获 + `errors="replace"` 容错解码（新增 `_decode_subprocess_output`），
    `_check_gcc_build` / `_check_keil_build` 同步改造；真实诊断不再被掩盖，判决仍正确。
  - 案例：汽服2302B班 王倩倩小组 `undefined reference to HAL_EXTI_ConfigLine` 此前被吞。
  - 新增回归测试：`tests/unit/test_build_checker.py::test_gcc_output_with_non_gbk_bytes_does_not_crash`。

### 学生端新增
- **提交打包**：新增 `submission_packager`，学生可在本地把报告+源码规范打包成提交包；
  `self_check_report` / `self_checker` / `check_worker` / `files_panel` / `grade_panel` 同步更新。

## [2.5.0] - 2024-06-11 - 安全增强版

### 新增功能

#### 安全模块
- 新增 `tools/security/` 安全工具模块
  - **ZIP炸弹防护** (`zip_validator.py`): 防御Zip炸弹攻击
  - **路径验证** (`path_validator.py`): 防御路径遍历攻击
  - **XML安全解析** (`xml_parser.py`): 防御XXE注入攻击
  - **数据脱敏** (`anonymizer.py`): 保护学生隐私

#### 非阻塞消抖模块
- 新增 `debounce.h` 和 `debounce.c`
- 基于状态机的非阻塞按键消抖
- 提高系统响应性

#### 安全配置
- 新增 `tools/security_config.json`
- 集中管理安全配置
- 支持ZIP限制、路径验证、数据脱敏配置

### 修改内容

#### 核心修复
- **`tools/submission_utils.py`**
  - 集成ZIP验证器
  - 使用安全XML解析器
  - 改进异常处理和日志记录

- **`tools/plagiarism_detection_enhanced.py`**
  - 添加实验目录路径验证
  - 防御路径遍历攻击

- **`tools/plagiarism/report.py`**
  - 添加数据脱敏功能
  - 支持可选的学生信息保护

- **`projects/01-turn-signal/main.c`**
  - 使用非阻塞消抖替代`HAL_Delay`
  - 提高LED响应性

- **`Makefile`**
  - 添加PROJECT参数白名单验证
  - 防御命令注入攻击
  - 支持debounce.c编译

- **`requirements.txt`**
  - 固定所有依赖版本
  - 添加`defusedxml==0.7.1`安全依赖

### 安全漏洞修复

| 优先级 | 漏洞 | 状态 |
|--------|------|------|
| P0 | Zip炸弹风险 | ✅ 已修复 |
| P0 | 路径遍历漏洞 | ✅ 已修复 |
| P1 | XML注入(XXE) | ✅ 已修复 |
| P1 | 敏感信息泄露 | ✅ 已修复 |
| P2 | HAL_Delay阻塞 | ✅ 已修复 |
| P2 | 命令注入 | ✅ 已修复 |
| P3 | 依赖版本管理 | ✅ 已修复 |

### 文档更新

- 新增 `docs/security/SECURITY_GUIDE.md` 安全指南
- 更新 `README.md` 添加安全功能说明

### 依赖变更

#### 新增依赖
- `defusedxml==0.7.1` - 安全XML解析（必需）

#### 固定版本
- `python-docx==0.8.11`
- `openpyxl==3.0.10`
- `jieba==0.42.1`
- `numpy==1.24.0`
- `scikit-learn==1.3.0`

---

## [2.4.0] - 2024-05-30

### 功能更新
- 新增配置化权重系统
- 增强语义检测
- 增强AI生成检测

### 改进
- 优化相似度计算算法
- 改进报告生成格式

---

## [2.3.0] - 2024-05-15

### 功能更新
- 新增图片相似度检测
- 新增图片质量验证

### 改进
- 优化查重性能
- 改进用户界面

---

## [2.0.0] - 2024-04-20

### 重大更新
- 重构为模块化架构
- 新增多算法支持
- 新增模板过滤功能
- 新增质量评估模块
- 新增相似度矩阵可视化
- 新增抄袭团伙检测

### 新增项目
- 07-car-gear 汽车档位模拟器
