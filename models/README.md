# Models Directory

## 用途

此目录用于存放机器学习模型文件和缓存，支持以下功能：

- **语义分析**：文本相似度计算、语义匹配
- **AI检测**：AI生成内容检测
- **质量评估**：自动质量评分
- **特征提取**：文本和代码特征提取

## 支持的模型格式

- `.pkl` - Python pickle 格式（scikit-learn 模型）
- `.h5` - HDF5 格式（Keras/TensorFlow 模型）
- `.pt` - PyTorch 模型格式

## 当前使用的模型

### 语义分析模型
- **库**：sentence-transformers (v2.7.0)
- **模型**：paraphrase-multilingual-MiniLM-L12-v2
- **缓存位置**：`models/sentence_transformers/`
- **下载方式**：首次运行时自动从 Hugging Face 下载
- **使用位置**：
  - `src/tools/plagiarism/grading/semantic_answer_grader.py`
  - `src/tools/plagiarism/semantic/detector.py`

### 机器学习算法
- **库**：scikit-learn (v1.5.2)
- **用途**：余弦相似度计算

## 说明

1. **自动下载**：sentence-transformers 模型在首次使用时自动下载
2. **本地缓存**：下载后的模型缓存在 `models/sentence_transformers/` 目录
3. **Git忽略**：模型文件已在 `.gitignore` 中配置忽略，不提交到仓库
4. **网络要求**：首次运行语义分析功能需要网络连接下载模型

## 相关配置

- `.gitignore` 中已配置忽略模型文件
- 语义检测功能可通过 `data/config/teaching/config.yaml` 启用
- 依赖库：`requirements.txt` 中的 sentence-transformers 和 torch

## 目录结构（运行后）

```
models/
├── README.md                           # 本说明文档
└── sentence_transformers/              # 模型缓存（首次运行时创建）
    └── models/                        # 预训练模型文件
        └── paraphrase-multilingual-...  # 多语言语义模型
```

## 更新日期

2026-06-15
