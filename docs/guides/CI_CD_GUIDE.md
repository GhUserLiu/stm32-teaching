# CI/CD 指南

## 概述

本项目使用 GitHub Actions 进行持续集成和持续部署。

## 工作流

### CI 工作流 (`.github/workflows/ci.yml`)

在以下情况触发：
- 推送到 `main` 或 `develop` 分支
- 创建 Pull Request

包含以下任务：
1. **STM32 构建** - 编译所有 STM32 项目
2. **Python 代码检查** - flake8, black, isort
3. **Python 测试** - pytest 单元测试
4. **安全扫描** - safety, bandit
5. **文档构建** - 检查文档完整性

### Release 工作流 (`.github/workflows/release.yml`)

在以下情况触发：
- 推送版本标签 (v*)

包含以下任务：
1. **创建发布** - 在 GitHub 上创建 Release
2. **构建发布包** - 打包项目文件
3. **上传发布包** - 上传到 GitHub Releases

## 本地测试

### 运行 STM32 构建
```bash
make list
make PROJECT=01-turn-signal
```

### 运行 Python 检查
```bash
pip install flake8 black isort
flake8 tools/
black --check tools/
isort --check-only tools/
```

### 运行测试
```bash
pip install pytest pytest-cov
pytest tests/ -v
pytest tests/ --cov=tools --cov-report=html
```

## 故障排查

### 构建失败
- 检查 ARM 工具链版本
- 验证 Makefile 语法
- 检查启动文件路径

### 测试失败
- 本地运行测试重现问题
- 检查 Python 版本兼容性
- 验证所有依赖已安装

### 安全扫描警告
- 更新依赖到安全版本
- 检查代码安全问题
- 修复配置文件中的敏感信息
