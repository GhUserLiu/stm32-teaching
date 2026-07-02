"""批处理模块（CLI 入口见 batch_class_processor.py）

注：batch_class_processor.py 为独立 CLI 脚本（含 sys.path 设置与 __main__ 守卫），
直接从 tools.plagiarism.* 取用能力，不暴露可导入的类。此处不强行 re-export，
以避免引用不存在的 BatchClassProcessor 导致 `import tools.batch` 失败。
"""
