# 新建项目指南

## 复制模板

```bash
# 复制模板文件夹
cp -r projects/_template projects/02-your-project-name

# 或手动创建
mkdir -p projects/02-your-project-name
```

## 项目文件要求

每个项目目录需要包含：

```
projects/XX-your-project/
├── main.c              # 主程序 (必需)
├── config.h            # 项目配置 (必需)
└── docs/               # 项目文档 (可选)
    └── README.md       # 项目说明
```

## 构建

```bash
# Makefile 方式
make PROJECT=02-your-project-name

# 或修改 Makefile 中的默认项目
```

## 编译输出

```
build/
└── 02-your-project/
    ├── your-project.elf
    ├── your-project.hex
    └── your-project.bin
```

---

## 已有项目

| 编号 | 项目 | 说明 | 状态 | 文档 |
|------|------|------|------|------|
| 01 | [turn-signal](./01-turn-signal/) | 转向灯系统 | ✅ 完成 | [硬件配置](./01-turn-signal/docs/HARDWARE_CONFIG.md) |
| _template | [项目模板](./_template/) | 新项目模板 | - | - |

---

## 项目01：转向灯系统

### 功能说明
- 4种工作模式：关闭、左转、右转、双闪
- 按键控制：KEY0循环切换模式，KEY_UP双闪切换
- LED配置：PF9/PF10，共阳极，低电平点亮

### 硬件资源
| 资源 | 引脚 | 说明 |
|------|------|------|
| LED0 | PF9 | 左转向灯 |
| LED1 | PF10 | 右转向灯 |
| KEY0 | PE4 | 模式切换 |
| KEY_UP | PA0 | 双闪开关 |

### 文档
- [硬件配置详情](./01-turn-signal/docs/HARDWARE_CONFIG.md)
- [功能测试说明](./01-turn-signal/docs/TEST_KEY_LED.md)
- [硬件说明](./01-turn-signal/docs/HARDWARE.md)

### 编译输出
```
build/01-turn-signal/Debug/01-turn-signal.hex
build/01-turn-signal/Debug/01-turn-signal.bin
```

---

## 常见问题

详见 [故障排查日志](../docs/TROUBLESHOOTING_LOG.md)
