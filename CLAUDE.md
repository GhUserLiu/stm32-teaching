# STM32F407 嵌入式教学平台 - Claude AI 指南

> 本文档为 Claude AI 提供项目上下文和开发指南，确保 AI 能够准确理解和协助开发。

---

## 项目概述

本项目是一个 **STM32F407 嵌入式教学平台**，包含：
1. **STM32 嵌入式开发框架** - 模块化 HAL 库和项目模板
2. **教学管理系统** - 查重检测、自动评分、反馈生成
3. **GUI 管理应用** - 基于 PyQt6 的桌面应用
4. **安全工具集** - 路径验证、ZIP 解压、XML 解析等

---

## 硬件平台

| 参数 | 规格 |
|------|------|
| **开发板** | M144Z-M4 最小系统板 |
| **MCU** | STM32F407ZGTx |
| **主频** | 168 MHz |
| **Flash** | 1 MB |
| **RAM** | 192 KB |
| **核心** | ARM Cortex-M4 + FPU |

---

## 目录结构速查

```
stm32f407/
├── src/                          # 源代码目录
│   ├── common/                   # 共享代码库（模块化 HAL）
│   │   ├── core/                # 核心 HAL 库（GPIO/SysTick/RCC/EXTI + 错误处理）
│   │   ├── bsp/                 # 板级支持包（board.h 引脚定义）
│   │   ├── drivers/             # 外设驱动（UART、Timer）
│   │   ├── inc/                 # 公共头文件
│   │   └── startup/             # 启动文件（startup_stm32f407xx.s）
│   │
│   ├── projects/                 # STM32 实验项目
│   │   ├── _template/           # 项目模板（新建项目参考）
│   │   ├── 01-turn-signal/      # 转向灯系统（简单项目示例）
│   │   ├── 07-car-gear/         # 汽车档位模拟器（CubeMX 项目）
│   │   └── Test6/               # 示例项目（CubeMX）
│   │
│   └── tools/                    # 教学管理工具（Python，legacy 算法/引擎层）
│       ├── plagiarism/           # 查重检测系统（核心）
│       ├── auto_grading/         # 自动化批阅（核心逻辑，无 GUI）
│       ├── teaching_management_gui/  # 教学管理桌面应用（PyQt6）
│       ├── student_submission_gui/   # 学生端提交应用
│       ├── security/            # 安全工具（路径/ZIP/XML/脱敏）
│       ├── teaching_scripts/    # 教学处理脚本（legacy，P5 淘汰对象）
│       └── scripts/             # 通用辅助脚本
│
│   # ---- 2026-08 重构新增的分层（绞杀者模式：旧 tools/ 保持可用）----
│   ├── core/                    # 服务层（Qt-free 业务编排，可独立单测）
│   │   └── services/            #   grading_service / similarity_service / result_importer
│   ├── algorithms/              # 查重引擎族（base 契约 + factory 注册表 + text/ + code/）
│   ├── parsers/                 # 输入解析（KeilProjectParser：.uvprojx → 用户源码）
│   ├── schemas/                 # Pydantic 严格校验（统一配置层入口）
│   └── persistence/             # SQLAlchemy 八表 ER + engine/session
│
├── config/                       # 统一配置（base.yaml 唯一真源，<env>.yaml 覆盖）
├── database/                     # 运行时 SQLite（不入库；含 -wal/-journal 边车）
├── data/                         # 数据目录
│   ├── config/                   # 配置文件
│   │   ├── teaching/            # 教学系统配置
│   │   ├── plagiarism/          # 查重工具配置
│   │   └── security/            # 安全配置
│   ├── rubrics/                  # 评分标准
│   ├── templates/                # 模板文件（实验报告模板等）
│   └── teaching/                 # 教学业务数据
│       └── 2026-春季/           # 按学期组织的数据
│
├── docs/                         # 文档中心
│   ├── api/                      # API 文档
│   ├── guides/                   # 开发指南
│   ├── security/                 # 安全文档
│   ├── teaching/                 # 教学资料
│   └── archive/                  # 归档资料
│
├── scripts/                      # 构建 / 重跑辅助脚本
├── tests/                        # 单元 / 集成测试
├── outputs/                      # 运行时输出（不入库）
├── models/                       # 模型文件
├── Makefile                      # 构建系统
├── STM32F407XX_FLASH.ld          # 链接脚本
├── build_student.spec            # 学生端 exe 构建配置
├── requirements.txt              # Python 依赖
├── CLAUDE.md / README.md / PROJECT_STRUCTURE.md / CHANGELOG.md
└── 启动教学管理系统.bat           # 教学管理系统启动器
```

---

## 开发指南

### STM32 项目开发

#### 新建项目
```bash
# 方法1：使用模板
cp -r src/projects/_template src/projects/02-your-project

# 方法2：使用脚本（如果存在）
bash src/tools/scripts/new_project.sh 02 your-project
```

#### 构建命令
```bash
make                              # 构建默认项目
make PROJECT=01-turn-signal       # 构建指定项目
make PROJECT=01-turn-signal debug    # 调试构建
make PROJECT=01-turn-signal release  # 发布构建
make clean                        # 清理
make list                         # 列出所有项目
```

#### 项目类型
- **简单项目**：单文件 `main.c`，使用 common/ 库
- **CubeMX 项目**：包含 `cubemx/` 子目录，使用 CubeMX 生成的构建系统

### C 代码规范

#### 文件结构
```c
/* 头文件包含顺序 */
#include "stm32f4xx_hal.h"      // HAL 库
#include "board.h"              // 板级定义
#include "config.h"             // 项目配置

// 主函数结构
int main(void)
{
    // 1. HAL 初始化
    HAL_Init();

    // 2. 系统时钟配置
    SystemClock_Config();

    // 3. 外设初始化
    MX_GPIO_Init();

    // 4. 主循环
    while (1)
    {
        // 应用逻辑
    }
}
```

#### 错误处理
```c
// 使用统一错误处理
#include "error_handler.h"

if (some_function() != HAL_OK) {
    ERROR_HANDLER(ERR_GPIO_INIT);  // 自动记录文件和行号
}

// 或使用带消息的错误处理
Error_Handler_WithCode(ERR_UART_INIT);
```

#### 非阻塞延时（推荐）
```c
// debounce.h 为 01-turn-signal 的项目本地实现（src/common 暂无共享版）
#include "debounce.h"

// 使用状态机替代 HAL_Delay
while (1) {
    if (Debounce_Update(&key_state, HAL_GetTick())) {
        // 按键处理
    }
    // 其他任务...
}
```

### Python 工具开发

#### 查重系统
```python
from tools.plagiarism.core import PlagiarismDetector

detector = PlagiarismDetector(
    method=SimilarityMethod.HYBRID,
    threshold=60.0
)
results = detector.detect(submissions)
```

#### 教学管理 GUI（教师端）

```bash
# Windows：双击 启动教学管理系统.bat（自动设 PYTHONPATH=src 并 cd 到仓库根）
conda run -n stm32_teaching python src/tools/teaching_management_gui/main.py
```

#### 统一配置层与服务层（2026-08 重构新增）

- **配置唯一真源**是 `config/base.yaml`，由 `src/schemas/`（pydantic，
  `extra=forbid`）加载校验；覆盖链 `base.yaml <- <env>.yaml <-
  APP_<SECTION>__<FIELD>` 环境变量。**拼错字段会在启动时报错**（不允许
  静默死配置）；阈值等运行值改这里，不要再改 dataclass 默认值。
- **服务层** `src/core/services/`（Qt-free）：`grading_service`（批阅
  管线编排，GUI worker 只做 Qt 胶水）、`similarity_service`（分引擎
  查重——GUI 方法下拉"分引擎检测（beta）"）、`result_importer`
  （JSON 产物回填数据库）。
- **查重引擎** `src/algorithms/`：工厂注册（`@register_checker`），
  代码/文字分模态分阈值；新引擎实现 `BaseSimilarityChecker` 契约
  （0-100 刻度、空输入 0、矩阵对角显式置 100）。
- **Keil 解析** `src/parsers/`：`.uvprojx` → 用户源码（厂商目录/
  CubeMX 系统文件剔除，GBK 兼容，出树路径防读）；keil 型提交的源码
  收集已接入门控（`submission_processor._collect_user_sources_via_keil`，
  解析失败自动回退盲扫）。
- **持久化** `src/persistence/`（SQLite 默认 `database/teaching.sqlite`）；
  历史结果回填：`conda run -n stm32_teaching python scripts/backfill_from_results.py --dry-run`
  预览，去掉 `--dry-run` 落库（幂等可重跑）。

---

## 重要约定

### 命名约定
| 类型 | 约定 | 示例 |
|------|------|------|
| 项目目录 | `编号-名称` | `01-turn-signal` |
| C 函数 | `模块_动作` | `HAL_GPIO_Init` |
| Python 文件 | `snake_case.py` | `plagiarism_detector.py` |
| 配置文件 | `config.json/yaml` | `rubric.json` |

### 安全约定
1. **路径验证**：始终使用 `src/tools/security/path_validator.py` 验证路径
2. **ZIP 解压**：使用 `src/tools/security/zip_validator.py` 解压 ZIP 文件
3. **XML 解析**：使用 `src/tools/security/xml_parser.py` 解析 XML
4. **数据脱敏**：使用 `src/tools/security/anonymizer.py` 处理敏感信息

### 文档约定
1. **C 头文件**：使用 Doxygen 风格注释
2. **Python 模块**：使用 docstring 说明
3. **配置文件**：添加 JSON Schema 或 YAML 注释

---

## 常见任务

### 修复编译错误
1. 检查 `Makefile` 中的项目白名单（第 25 行）
2. 确认启动文件路径：`src/common/startup/startup_stm32f407xx.s`
3. 检查包含路径：`-I$(COMMON_DIR)/inc -I$(COMMON_DIR)/core`

### 添加新驱动
1. 在 `src/common/drivers/` 创建对应目录
2. 实现驱动接口（参考 `src/common/drivers/uart/` 和 `src/common/drivers/timer/`）
3. 更新 `src/common/drivers/README.md`

### 修改评分标准
1. 编辑 `data/rubrics/rubric.json`
2. 或使用 GUI 应用的设置页面

### 调试查重结果
1. 检查 `data/teaching/.../results/` 目录
2. 查看 Excel 报告的"详细结果"工作表
3. 调整 `data/config/security/security_config.json` 中的阈值

---

## 依赖管理

### 运行环境（2026-10-07 钉扎）

> 专用 conda 环境 `stm32_teaching`（Python 3.11）。本机裸 `python`/`pip` 在 PATH
> 解析到 conda base（3.13.9）=违规，一切执行点钉
> `conda run -n stm32_teaching python …` 形态（装包用 `python -m pip`）。
> 2026-10-07 增量补装（已 pin 进 requirements.txt）：
> `xlrd==2.0.2`、`xlwt==1.3.0`、`xlutils==2.0.0`（教务 .xls 花名册读写）。
> 家用机重建：`conda create -n stm32_teaching python=3.11` 后
> `conda run -n stm32_teaching python -m pip install -r requirements.txt`。

### STM32 工具链
- **编译器**: `arm-none-eabi-gcc`
- **烧录**: ST-Link 或 J-Link

### Python 依赖
```bash
# 核心依赖（必需；含统一配置层 pydantic/PyYAML 与持久化 SQLAlchemy）
conda run -n stm32_teaching python -m pip install python-docx openpyxl defusedxml pydantic PyYAML SQLAlchemy

# 推荐依赖（中文分词）
conda run -n stm32_teaching python -m pip install jieba

# 可选依赖（语义检测、图像处理）
conda run -n stm32_teaching python -m pip install sentence-transformers Pillow
```

---

## 故障排查

### 编译问题
- **错误: 未定义的引用**: 检查是否链接了所有源文件
- **错误: 启动文件找不到**: 检查 Makefile 第 184 行的文件名
- **Flash 大小超限**: 使用 `make size` 查看内存使用

### 运行时问题
- **程序不运行**: 检查时钟配置和 GPIO 初始化
- **按键无响应**: 检查消抖实现，避免使用 HAL_Delay

### Python 工具问题
- **导入错误**: 确保在项目根目录运行
- **路径错误**: 检查 `security_config.json` 中的路径配置
- **ZIP 解压失败**: 检查是否使用了安全的 ZIP 验证器

---

## Repository context via redcon（2026-09-29 接入）

> **本机（办公室机）回退：本机 VSCode 扩展的 redcon MCP 通道 tools/call 挂死**（initialize/tools-list 正常但调用 60s 超时，2026-09-29 定论）——本机勿调 `mcp__redcon__*` 工具，一律用 CLI，且必须 `PYTHONUTF8=1` 前缀（否则 GBK 解码崩溃）。CLI 可用子命令 plan/pack/repo-map（**无 search 子命令**，正则检索退回 Grep）。`.mcp.json` 随仓库走，供家用机（或本机通道修复后）MCP 使用。

- 用法（仓库根）：`PYTHONUTF8=1 redcon plan "任务描述" --repo .`（pack / repo-map "任务" 同理；PATH 里的 redcon 为 base env，与 `.mcp.json` 钉的 `teaching_workbench` env 同为 1.18.0）
- 索引已剪枝（`redcon.toml [scan]`；redcon 不读 .gitignore，须显式排除）：`data/teaching/**`（**学生 PII，坚决不入索引**——2026-08 曾有 151 个含学号姓名文件入库教训）、`cubemx` 厂商树（不可用 Drivers，会撞 src/common/drivers 自有驱动）、`__pycache__`/`.pytest_cache`/`outputs`/`database`/`Downloads`/`课程档案`；PDF/xlsx/xls/zip/log 二进制不入索引
- 教学平台代码优先查 `src/tools` 与 `src/core`；`.redcon/` 为本地索引目录（已 gitignore）
- 新增大目录/敏感目录须同步补 `redcon.toml`：目录用 `ignore_dirs`（按名剪枝、唯一省扫描的开关，且会整体替换默认剪枝集——保留 `.git`/`.redcon` 条目），文件模式用 `ignore_globs`

---

## 版本历史

- **v3.0.0** (2026-08-15): 架构重构——统一配置层（schemas）、服务层（core/services）、
  查重引擎族（algorithms 工厂）、Keil 解析（parsers）、持久化与 JSON 回填（persistence）；
  PII 治理（153 文件出库 + filter-repo 方案）
- **v2.5.0** (2024-06-11): 安全增强版，添加完整安全防护
- **v2.4.0** (2024-05-30): 配置化权重、增强语义检测
- **v2.0.0** (2024-04-20): 模块化架构重构

---

## 联系方式

- **项目维护**: STM32F407 教学团队
- **问题反馈**: 通过项目 Issue 跟踪

---

**最后更新**: 2026-08-15
