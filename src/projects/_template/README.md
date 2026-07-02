# 项目模板使用指南

## 模板说明

这是 STM32F407 嵌入式教学平台的标准项目模板，遵循统一的代码规范（HAL库风格）。

**重要**: 所有新项目必须基于此模板创建，并遵循 `docs/guides/CODING_STYLE.md` 中的规范。

---

## 快速开始

### 方法一：使用脚本（推荐）

```bash
bash tools/scripts/new_project.sh 02 my-project-name
```

### 方法二：手动创建

1. **复制模板**
   ```bash
   cp -r projects/_template projects/02-your-project
   ```

2. **修改配置文件**
   - 编辑 `projects/02-your-project/config.h`
   - 添加项目特定的配置定义

3. **编写主程序**
   - 编辑 `projects/02-your-project/main.c`
   - 实现你的应用逻辑

4. **构建项目**
   ```bash
   make PROJECT=02-your-project
   ```

---

## 模板文件结构

```
_template/
├── main.c          # 主程序文件
├── config.h        # 项目配置文件
├── Makefile        # 项目构建文件（自动生成）
└── README.md       # 项目说明（可选）
```

---

## 代码规范要点

### 1. 统一使用 HAL 库

```c
// ✅ 正确：使用 HAL 库函数
HAL_GPIO_WritePin(GPIOF, GPIO_PIN_9, GPIO_PIN_SET);
if (HAL_GPIO_ReadPin(GPIOE, GPIO_PIN_4) == GPIO_PIN_RESET)

// ❌ 错误：直接寄存器操作（特殊情况除外）
GPIOF->ODR |= (1U << 9);
```

### 2. 检查返回值

```c
// ✅ 正确：检查 HAL 函数返回值
if (HAL_GPIO_Init(BOARD_LED0_PORT, &GPIO_InitStruct) != HAL_OK)
{
    Error_Handler();
}

// ❌ 错误：不检查返回值
HAL_GPIO_Init(BOARD_LED0_PORT, &GPIO_InitStruct);
```

### 3. 使用 volatile 关键字

```c
// ✅ 正确：中断中修改的变量使用 volatile
volatile uint32_t system_tick = 0;
volatile uint8_t data_ready = 0;

// ❌ 错误：中断变量未使用 volatile
uint32_t system_tick = 0;  // 错误！
```

### 4. 避免魔术数字

```c
// ✅ 正确：使用宏定义
#define LED_TOGGLE_INTERVAL  25
if (toggle_counter >= LED_TOGGLE_INTERVAL)

// ❌ 错误：使用魔术数字
if (toggle_counter >= 25)
```

---

## 常见任务示例

### LED 控制

```c
/* 初始化LED引脚 */
GPIO_InitTypeDef GPIO_InitStruct = {0};
GPIO_InitStruct.Pin = BOARD_LED0_PIN;
GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
GPIO_InitStruct.Pull = GPIO_NOPULL;
GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
HAL_GPIO_Init(BOARD_LED0_PORT, &GPIO_InitStruct);

/* 控制LED */
HAL_GPIO_WritePin(BOARD_LED0_PORT, BOARD_LED0_PIN, GPIO_PIN_RESET);  // 点亮
HAL_GPIO_WritePin(BOARD_LED0_PORT, BOARD_LED0_PIN, GPIO_PIN_SET);    // 熄灭
HAL_GPIO_TogglePin(BOARD_LED0_PORT, BOARD_LED0_PIN);                 // 翻转
```

### 按键读取

```c
/* 初始化按键引脚（输入模式，上拉） */
GPIO_InitTypeDef GPIO_InitStruct = {0};
GPIO_InitStruct.Pin = BOARD_KEY0_PIN;
GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
GPIO_InitStruct.Pull = GPIO_PULLUP;
HAL_GPIO_Init(BOARD_KEY0_PORT, &GPIO_InitStruct);

/* 读取按键状态 */
GPIO_PinState key_state = HAL_GPIO_ReadPin(BOARD_KEY0_PORT, BOARD_KEY0_PIN);
if (key_state == GPIO_PIN_RESET)
{
    /* 按键被按下（低电平） */
}
```

### 延时函数

```c
/* 毫秒级延时 */
HAL_Delay(500);  // 延时500ms

/* 微秒级延时（需使用DWT） */
// 见 07-car-gear 项目示例
```

---

## 错误处理

模板包含统一的错误处理函数：

```c
static void Error_Handler(void)
{
    /* 禁用中断 */
    __disable_irq();

    /* 点亮错误指示LED */
    HAL_GPIO_WritePin(ERROR_LED_PORT, ERROR_LED_PIN, GPIO_PIN_RESET);

    /* 进入死循环（LED闪烁） */
    while (1)
    {
        HAL_Delay(500);
        HAL_GPIO_TogglePin(ERROR_LED_PORT, ERROR_LED_PIN);
    }
}
```

当发生严重错误时，调用此函数：
```c
if (HAL_Init() != HAL_OK)
{
    Error_Handler();
}
```

---

## 调试技巧

### 1. 使用 LED 指示状态

```c
/* 在关键位置添加LED闪烁来指示程序执行 */
HAL_GPIO_TogglePin(BOARD_LED0_PORT, BOARD_LED0_PIN);
HAL_Delay(100);
HAL_GPIO_TogglePin(BOARD_LED0_PORT, BOARD_LED0_PIN);
```

### 2. 检查返回值

```c
/* 打印调试信息（需要配置UART） */
if (HAL_UART_Transmit(...) != HAL_OK)
{
    /* 传输失败处理 */
}
```

### 3. 使用断点

在IDE（如Keil、IAR）中设置断点，查看变量值。

---

## 下一步

- 阅读 [代码风格指南](../../docs/guides/CODING_STYLE.md)
- 查看 [01-turn-signal](../../projects/01-turn-signal/) 项目示例
- 参考 [07-car-gear](../../projects/07-car-gear/) 项目了解更多功能

---

## 注意事项

1. **不要混合编程方式**: 统一使用HAL库，特殊情况需文档说明
2. **检查所有返回值**: HAL函数可能失败，必须检查
3. **使用volatile**: 中断相关的变量必须声明为volatile
4. **避免魔术数字**: 使用宏定义提高代码可读性
5. **添加注释**: 关键代码必须添加注释说明

---

**如有问题，请参考项目文档或联系课程教师。**
