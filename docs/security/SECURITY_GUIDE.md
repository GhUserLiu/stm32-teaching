# 安全指南

## 概述

本项目包含多层安全防护措施，用于防御常见的Web和嵌入式系统安全漏洞。

---

## 安全功能

### 1. ZIP炸弹防护 (Zip Bomb Protection)

**位置**: `tools/security/zip_validator.py`

**防护内容**:
- 文件大小限制（外层100MB，内层50MB）
- 文件数量限制（最多1000个文件）
- 路径遍历检查（禁止`..`和绝对路径）
- 嵌套层级限制（最多2层）

**使用方法**:
```python
from tools.security import ZipLimits, validate_zip_size

limits = ZipLimits(max_outer_size=100*1024*1024)
with zipfile.ZipFile(zip_path, 'r') as zf:
    validate_zip_size(zf, limits)
```

---

### 2. 路径遍历防护 (Path Traversal Protection)

**位置**: `tools/security/path_validator.py`

**防护内容**:
- 实验目录路径限制在`docs/teaching`范围内
- 禁止绝对路径
- 禁止`..`父目录引用

**使用方法**:
```python
from tools.security import validate_experiment_dir, PathValidationError

try:
    validated_dir = validate_experiment_dir(user_path)
except PathValidationError as e:
    print(f"路径验证失败: {e}")
```

---

### 3. XXE注入防护 (XXE Injection Protection)

**位置**: `tools/security/xml_parser.py`

**防护内容**:
- 使用`defusedxml`库替代标准XML解析器
- 禁用XML实体处理
- 禁用外部DTD加载

**依赖安装**:
```bash
pip install defusedxml==0.7.1
```

**使用方法**:
```python
from tools.security import safe_parse_xml_string

root = safe_parse_xml_string(xml_content)
```

---

### 4. 数据脱敏 (Data Anonymization)

**位置**: `tools/security/anonymizer.py`

**功能**:
- 学号脱敏（保留后4位）
- 姓名脱敏（保留姓氏）
- 支持完全匿名模式

**使用方法**:
```python
from tools.security import StudentDataAnonymizer, AnonymizationConfig

config = AnonymizationConfig(preserve_last_digits=4)
anonymizer = StudentDataAnonymizer(config)

masked_id = anonymizer.anonymize_student_id("20230011234")
# 输出: "*******1234"
```

---

### 5. 命令注入防护 (Command Injection Protection)

**位置**: `Makefile`

**防护内容**:
- 项目名称白名单验证
- 危险字符过滤
- 参数清理

**允许的项目**:
```makefile
ALLOWED_PROJECTS := 01-turn-signal 07-car-gear _template Test6
```

---

## 配置文件

### 安全配置

**位置**: `tools/security_config.json`

```json
{
  "zip_limits": {
    "max_outer_size": 104857600,
    "max_inner_size": 52428800,
    "max_file_count": 1000
  },
  "anonymization": {
    "enabled": false,
    "preserve_last_digits": 4
  }
}
```

---

## 安全最佳实践

### 对于教师/管理员

1. **定期更新依赖**
   ```bash
   pip list --outdated
   ```

2. **启用数据脱敏**
   - 在公开分享报告时启用
   - 修改`security_config.json`中的`anonymization.enabled`

3. **限制文件访问**
   - 确保`results/`目录权限正确
   - 定期清理旧的敏感文件

### 对于学生

1. **提交文件前检查**
   - 确保ZIP文件大小合理（<50MB）
   - 文件名仅包含学号和必要信息

2. **保护个人信息**
   - 不要在报告中包含不必要的个人信息
   - 使用学号而非姓名标识

---

## 安全测试

### 测试ZIP炸弹防护

```bash
# 创建测试ZIP（正常大小）
python -c "
import zipfile
with zipfile.ZipFile('normal.zip', 'w') as z:
    z.writestr('test.txt', 'Hello World')
"

# 应该成功
python tools/plagiarism_detection_enhanced.py
```

### 测试路径遍历防护

```bash
# 应该被拒绝
python tools/plagiarism_detection_enhanced.py --experiment-dir /etc/passwd
# 输出: 错误: 路径验证失败
```

### 测试命令注入防护

```bash
# 应该被拒绝
make PROJECT="test; rm -rf /"
# 输出: 错误: 项目名称包含非法字符
```

---

## 安全事件响应

如果发现安全漏洞：

1. 立即停止使用受影响的功能
2. 记录漏洞详情
3. 联系项目维护者
4. 等待修复补丁

---

## 参考资源

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [Python安全最佳实践](https://python.readthedocs.io/)
