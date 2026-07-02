# STM32F407 嵌入式教学平台 - 测试套件

## 快速开始

```bash
# 运行所有测试
pytest tests/ -v

# 运行单元测试
pytest tests/unit/ -v

# 运行集成测试
pytest tests/integration/ -v
```

## 测试结构

```
tests/
├── conftest.py          # pytest 配置和 fixtures
├── unit/                # 单元测试
│   └── test_core.py     # 核心模块测试
└── integration/         # 集成测试
    └── test_basic.py    # 基础导入测试
```
