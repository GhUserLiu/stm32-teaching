# STM32F407 嵌入式教学平台

> 开发板: M144Z-M4 最小系统板 (STM32F407ZGTx)
>
> MCU: STM32F407ZGTx, 168MHz, 1MB Flash, 192KB RAM

---

## 快速开始

```bash
# 克隆或下载项目后，构建默认项目
make

# 构建指定项目
make PROJECT=01-turn-signal

# 查看帮助
make help
```

---

## 项目结构

```
stm32f407/
├── src/                          # 源代码
│   ├── common/                   # 共享代码库（模块化 HAL）
│   │   ├── core/                 # 核心 HAL 库（stm32f4xx_hal + error_handler）
│   │   ├── bsp/                  # 板级支持包（board.h 开发板引脚定义）⭐
│   │   ├── drivers/              # 外设驱动（UART、Timer）
│   │   ├── inc/                  # 公共头文件
│   │   └── startup/              # 启动文件（startup_stm32f407xx.s）
│   ├── projects/                 # 实验项目
│   │   ├── _template/            # 新项目模板
│   │   ├── 01-turn-signal/       # 转向灯系统（简单项目）
│   │   ├── 07-car-gear/          # 汽车档位模拟器（CubeMX）
│   │   └── Test6/                # 示例项目（CubeMX）
│   └── tools/                    # 教学管理工具（Python）
│       ├── auto_grading/         # 自动化批阅
│       ├── plagiarism/           # 查重检测
│       ├── teaching_management_gui/  # 教学管理 GUI（PyQt6）
│       ├── student_submission_gui/   # 学生端提交 GUI
│       ├── security/             # 安全工具（路径/ZIP/XML）
│       └── teaching_scripts/     # 教学处理脚本
├── data/                         # 配置 / 模板 / 教学业务数据
├── docs/                         # 文档（api / guides / security / teaching / archive）
├── scripts/                      # 构建 / 重跑辅助脚本
├── tests/                        # 单元 / 集成测试
├── outputs/                      # 运行时输出（不入库）
├── models/                       # 模型文件
├── Makefile                      # 构建脚本
├── STM32F407XX_FLASH.ld          # 链接脚本
├── build_student.spec            # 学生端 exe 构建配置
├── requirements.txt              # Python 依赖
├── PROJECT_STRUCTURE.md          # 结构说明
└── README.md
```

详细说明: [项目结构说明](PROJECT_STRUCTURE.md)

---

## 安全功能

本项目 v2.5.0+ 包含完整的安全防护措施：

| 功能 | 描述 | 模块 |
|------|------|------|
| **ZIP炸弹防护** | 文件大小/数量限制，路径遍历检查 | `tools/security/zip_validator.py` |
| **路径验证** | 限制目录访问范围，防御路径遍历 | `tools/security/path_validator.py` |
| **XXE防护** | 安全XML解析，防御外部实体注入 | `tools/security/xml_parser.py` |
| **数据脱敏** | 保护学生隐私，支持报告匿名化 | `tools/security/anonymizer.py` |
| **命令注入防护** | Makefile参数白名单验证 | `Makefile` |

详细说明: [安全指南](docs/security/SECURITY_GUIDE.md)

---

## 配置说明

### 硬件固定配置 (`common/bsp/board.h`)
开发板固定的引脚分配，**无需修改**：
- LED0/LED1 位置
- 按键位置
- 可用 GPIO 列表

### 项目特定配置 (`projects/XX/config.h`)
根据项目需求配置：
- 按键触发方式（高/低电平）
- 时序参数
- 项目特定功能开关

---

## 构建命令

```bash
# 构建默认项目
make

# 构建指定项目
make PROJECT=01-turn-signal

# 调试构建（默认）
make PROJECT=01-turn-signal debug

# 发布构建（优化）
make PROJECT=01-turn-signal release

# 显示内存使用
make PROJECT=01-turn-signal size

# 列出所有项目
make list

# 清理
make clean

# 查看帮助
make help
```

---

## 新建项目

### 方法一：使用脚本（推荐）

```bash
bash tools/scripts/new_project.sh 02 my-project
```

### 方法二：手动创建

```bash
# 1. 复制模板
cp -r projects/_template projects/02-your-project

# 2. 修改 projects/02-your-project/config.h

# 3. 编写 projects/02-your-project/main.c

# 4. 构建
make PROJECT=02-your-project
```

详细指南: [新建项目指南](docs/guides/NEW_PROJECT.md)

---

## 项目列表

| 编号 | 项目 | 说明 | 状态 | 文档 |
|------|------|------|------|------|
| 01 | [转向灯系统](projects/01-turn-signal/) | LED 转向灯控制 | ✅ 完成 | [硬件配置](projects/01-turn-signal/docs/HARDWARE_CONFIG.md) |
| 07 | [汽车档位](projects/07-car-gear/) | 档位显示模拟器 (CubeMX) | ✅ 完成 | - |
| - | [项目模板](projects/_template/) | 新项目模板 | - | - |

---

## 开发工具

### VSCode 任务

- `build` - 构建项目
- `flash` - 烧录到设备
- `build and flash` - 构建并烧录
- `clean` - 清理构建
- `make size` - 显示内存使用
- `new project` - 创建新项目
- `switch project` - 切换活动项目
- `check syntax` - 语法检查

### 辅助脚本

| 脚本 | 说明 |
|------|------|
| `tools/scripts/new_project.sh` | 快速创建新项目 |
| `tools/scripts/switch_project.sh` | 切换 EIDE 活动项目 |
| `tools/scripts/check_syntax.sh` | C 代码语法检查 |

---

## 文档

### 开发指南
- [新建项目指南](docs/guides/NEW_PROJECT.md)
- [构建系统说明](docs/guides/BUILD_SYSTEM.md)
- [代码风格指南](docs/guides/CODING_STYLE.md)

### API 文档
- [HAL 库 API](docs/api/HAL_API.md)
- [板级支持包 API](docs/api/BOARD_API.md)

### 其他文档
- [EIDE 使用指南](docs/EIDE_GUIDE.md)
- [故障排查日志](docs/TROUBLESHOOTING_LOG.md)

---

## 工具链要求

### STM32 开发工具链

- **编译器**: arm-none-eabi-gcc (建议 5.4+)
- **烧录工具**: ST-Link 或 J-Link
- **IDE**: VSCode + EIDE 插件（可选）

### Python 工具链（查重系统）

- **Python**: 3.8+
- **依赖安装**: `pip install -r requirements.txt`

#### 依赖项说明

| 依赖项 | 用途 | 必需性 |
|--------|------|--------|
| python-docx | Word文档处理 | ✅ 必需 |
| openpyxl | Excel报告生成 | ✅ 必需 |
| jieba | 中文精确分词 | ⭐ 强烈推荐 |
| sentence-transformers | 语义检测（改写） | ⚠️ 可选 |
| Pillow | 图片相似度 | ⚠️ 可选 |

#### 快速安装

```bash
# 安装所有依赖
pip install -r requirements.txt

# 仅安装核心依赖
pip install python-docx openpyxl jieba
```

详细说明: [安装指南](tools/INSTALL.md)

### 安装工具链

#### Windows
使用 EIDE 自动安装，或从 [ARM 官网](https://developer.arm.com/downloads/-/gnu-rm) 下载。

#### Linux
```bash
sudo apt install gcc-arm-none-eabi
```

#### macOS
```bash
brew install arm-none-eabi-gcc
```

---

## 许可证

本项目仅用于教学目的。

---

## 贡献

欢迎提交问题和改进建议！
