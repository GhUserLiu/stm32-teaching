"""
Pytest 配置文件
"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def sample_submission():
    """示例提交数据"""
    return {
        'student_id': '2023001',
        'name': '张三',
        'content': '''
# 实验报告

## 实验目的
学习STM32 GPIO控制

## 实验步骤
1. 配置GPIO
2. 编写控制代码
3. 测试运行

## 实验结果
LED正常闪烁
''',
        'code_blocks': [
            '''
int main(void) {
    HAL_Init();
    while(1) {
        HAL_GPIO_TogglePin(GPIOF, GPIO_PIN_9);
        HAL_Delay(500);
    }
}
'''
        ]
    }


@pytest.fixture
def sample_rubric():
    """示例评分标准"""
    return {
        'criteria': [
            {
                'id': 'purpose',
                'name': '实验目的',
                'max_points': 10,
                'description': '明确阐述实验目的'
            },
            {
                'id': 'procedure',
                'name': '实验步骤',
                'max_points': 30,
                'description': '步骤完整、逻辑清晰'
            },
            {
                'id': 'result',
                'name': '实验结果',
                'max_points': 30,
                'description': '结果真实、分析深入'
            },
            {
                'id': 'code_quality',
                'name': '代码质量',
                'max_points': 20,
                'description': '代码规范、注释完整'
            },
            {
                'id': 'format',
                'name': '格式规范',
                'max_points': 10,
                'description': '格式整齐、排版美观'
            }
        ]
    }
