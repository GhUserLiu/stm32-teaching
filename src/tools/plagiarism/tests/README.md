# STM32F407 嵌入式教学平台 - 查重测试套件

## 测试结构

```
tests/
├── unit/              # 单元测试
│   ├── test_core.py   # 核心查重测试
│   ├── test_grading.py # 评分系统测试
│   └── test_feedback.py # 反馈生成测试
├── integration/       # 集成测试
│   └── test_detection_workflow.py # 检测工作流测试
├── conftest.py        # Pytest 配置
└── README.md          # 本文件
```

## 运行测试

### 运行所有测试
```bash
pytest tests/
```

### 运行单元测试
```bash
pytest tests/unit/
```

### 运行集成测试
```bash
pytest tests/integration/
```

### 查看覆盖率
```bash
pytest tests/ --cov=tools --cov-report=html
```

### 详细输出
```bash
pytest tests/ -v
```

## 添加测试

### 单元测试示例
```python
# tests/unit/test_example.py
def test_function():
    result = function_to_test()
    assert result == expected
```

### 集成测试示例
```python
# tests/integration/test_workflow.py
def test_workflow():
    # 测试完整工作流
    result = run_workflow()
    assert result.is_valid
```

## Fixtures

可用的 fixtures（定义在 conftest.py）：

- `sample_submission`: 示例学生提交数据
- `sample_rubric`: 示例评分标准

## 测试指南

1. **命名规范**: 测试文件以 `test_` 开头，测试函数以 `test_` 开头
2. **独立性**: 每个测试应独立运行，不依赖其他测试
3. **清理**: 使用 fixtures 进行设置和清理
4. **断言**: 使用清晰的断言消息

## CI/CD 集成

测试会在 CI/CD 流程中自动运行。
