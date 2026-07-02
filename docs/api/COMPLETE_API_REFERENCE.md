# STM32F407 嵌入式教学平台 - 完整 API 参考

## HAL 库 API

### 核心 HAL 函数

#### `HAL_Init()`
```c
HAL_StatusTypeDef HAL_Init(void);
```

### GPIO 操作

#### `HAL_GPIO_WritePin()`
```c
void HAL_GPIO_WritePin(GPIO_TypeDef *GPIOx, uint16_t GPIO_Pin, GPIO_PinState PinState);
```

#### `HAL_GPIO_ReadPin()`
```c
GPIO_PinState HAL_GPIO_ReadPin(GPIO_TypeDef *GPIOx, uint16_t GPIO_Pin);
```

## Python 工具 API

### 查重检测
```python
from tools.plagiarism.core import PlagiarismDetector
detector = PlagiarismDetector(method=SimilarityMethod.HYBRID)
```

### 评分系统
```python
from tools.plagiarism.grading import EnhancedGradingSystem
grading = EnhancedGradingSystem(rubric_path='rubric.json')
```

---

详细参考:
- [HAL API 详细文档](HAL_API.md)
- [板级支持包 API](BOARD_API.md)
