# -*- coding: utf-8 -*-
"""
安全工具单元测试
Security Tools Unit Tests

覆盖：路径穿越防护、ZIP 安全、XML XXE 防护、数据脱敏。
"""

import zipfile
import pytest
from pathlib import Path

from tools.security.path_validator import (
    PathValidationError,
    validate_path_allowed,
    safe_path_join,
)
from tools.security.zip_validator import (
    ZipValidationError,
    validate_path_traversal,
    validate_zip_size,
    ZipLimits,
    safe_extract_zip,
)
from tools.security.xml_parser import safe_parse_xml_string, XMLError
from tools.security.anonymizer import (
    create_anonymized_mapping,
    apply_id_mapping,
)


# ============================================================
# 路径校验
# ============================================================
class TestPathValidator:
    def test_allowed_path_inside_base(self, tmp_path):
        base = tmp_path
        target = tmp_path / "sub" / "file.txt"
        target.parent.mkdir(parents=True)
        target.write_text("x")
        resolved = validate_path_allowed(target, [base])
        assert resolved.resolve() == target.resolve()

    def test_traversal_rejected(self, tmp_path):
        base = tmp_path
        # 构造 ../../etc/passwd 风格的逃逸路径
        evil = tmp_path / "sub" / ".." / ".." / ".." / "etc" / "passwd"
        with pytest.raises(PathValidationError):
            validate_path_allowed(evil, [base])

    def test_safe_path_join_rejects_parent_ref(self, tmp_path):
        with pytest.raises(PathValidationError):
            safe_path_join(tmp_path, "../../etc/passwd")

    def test_safe_path_join_rejects_absolute(self, tmp_path):
        with pytest.raises(PathValidationError):
            safe_path_join(tmp_path, "/etc/passwd")

    def test_safe_path_join_ok(self, tmp_path):
        joined = safe_path_join(tmp_path, "a", "b.txt")
        assert joined == tmp_path / "a" / "b.txt"


# ============================================================
# ZIP 校验
# ============================================================
class TestZipValidator:
    def test_path_traversal_rejects_dotdot(self):
        with pytest.raises(ZipValidationError):
            validate_path_traversal("../../etc/passwd")

    def test_path_traversal_rejects_absolute(self):
        with pytest.raises(ZipValidationError):
            validate_path_traversal("/etc/passwd")

    def test_path_traversal_accepts_normal(self):
        # 正常文件名不应抛异常
        validate_path_traversal("student/report.docx")

    def test_zip_size_limit(self, tmp_path):
        zip_path = tmp_path / "big.zip"
        # 写一个解压后总大小超过 1 字节限制的 zip，验证 size 校验
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("a.txt", "x" * 100)
        limits = ZipLimits(max_outer_size=1)
        with zipfile.ZipFile(zip_path, "r") as zf:
            with pytest.raises(ZipValidationError):
                validate_zip_size(zf, limits)

    def test_safe_extract_rejects_zip_slip(self, tmp_path):
        """构造 zip-slip（条目名含 ..）的恶意 zip，解压必须拒绝。"""
        evil_zip = tmp_path / "evil.zip"
        with zipfile.ZipFile(evil_zip, "w") as zf:
            zf.writestr("../../escaped.txt", "pwned")
        target = tmp_path / "out"
        with pytest.raises(ZipValidationError):
            safe_extract_zip(evil_zip, target)

    def test_safe_extract_normal(self, tmp_path):
        zip_path = tmp_path / "ok.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("inside/a.txt", "hello")
        target = tmp_path / "out"
        safe_extract_zip(zip_path, target)
        assert (target / "inside" / "a.txt").read_text() == "hello"


# ============================================================
# XML XXE 防护
# ============================================================
class TestXmlParser:
    def test_parse_normal_xml(self):
        root = safe_parse_xml_string("<root><a>1</a></root>")
        assert root.tag == "root"
        assert root.find("a").text == "1"

    def test_parse_invalid_xml_raises(self):
        with pytest.raises(XMLError):
            safe_parse_xml_string("<not-closed>")

    def test_xxe_entity_rejected(self):
        """含实体声明的 XML 应被安全解析器拒绝（defusedxml 禁止实体，即 XXE 防护）。"""
        xxe = (
            '<?xml version="1.0"?>'
            '<!DOCTYPE root [<!ENTITY xxe "ENTITY_VALUE">]>'
            '<root>&xxe;</root>'
        )
        # defusedxml 遇到实体声明会抛 EntitiesForbidden —— 这正是防护生效
        with pytest.raises(Exception):
            safe_parse_xml_string(xxe)


# ============================================================
# 数据脱敏
# ============================================================
class TestAnonymizer:
    def test_create_mapping_format(self):
        mapping = create_anonymized_mapping(["23071140101", "23071140102"])
        assert mapping["23071140101"] == "S001"
        assert mapping["23071140102"] == "S002"

    def test_apply_id_mapping_replaces_student_id(self):
        mapping = {"23071140101": "S001"}
        data = {"student_id": "23071140101", "name": "张三"}
        out = apply_id_mapping(data, mapping)
        assert out["student_id"] == "S001"
        assert out["name"] == "张三"

    def test_apply_id_mapping_nested(self):
        mapping = {"23071140101": "S001", "23071140102": "S002"}
        data = {
            "student_id": "23071140101",
            "pairs": [
                {"student_id": "23071140102", "similar_to": "23071140101"},
            ],
        }
        out = apply_id_mapping(data, mapping)
        assert out["student_id"] == "S001"
        assert out["pairs"][0]["student_id"] == "S002"
        assert out["pairs"][0]["similar_to"] == "S001"
