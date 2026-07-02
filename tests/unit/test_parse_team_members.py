# -*- coding: utf-8 -*-
"""
parse_team_members 单测：团队表解析的两种现实排版

覆盖 2026-春季 期末实测的两组根因（闫建铭/李全同组被拆）：
- 角色词并入姓名单元格 → "李全\n组长\n23071140141"（姓名/角色/学号 各占一段）
- "团队成员基本信息" 表头落在任务说明之后 → 旧实现从更早的"团队信息与分工"起截、
  被"1.2"等子节号提前截断，漏掉真正的成员表。
"""

import sys

import pytest

sys.path.insert(0, "src")

from tools.auto_grading.submission_processor import parse_team_members


class TestParseTeamMembers:
    def test_role_between_name_and_id(self):
        """角色词夹在姓名与学号之间（李全式单元格：李全\\n组长\\n23071140141）→ 仍能配对。"""
        report = (
            "一、团队信息与分工\n"
            "团队成员基本信息\n"
            "姓名\n学号\n班级\n组内角色\n"
            "李全\n组长\n23071140141\n汽服2301B班\n硬件搭建、电路调试\n"
            "闫建铭\n组员\n23071140128\n汽服2301B班\n软件编程、中断逻辑编写\n"
            "个人分工说明\n各成员负责模块……"
        )
        members = parse_team_members(report, "23071140141", "李全")
        assert {sid for sid, _ in members} == {"23071140141", "23071140128"}

    def test_table_header_after_task_text(self):
        """表头"团队成员基本信息"落在任务说明之后（李全式：1实验任务选择→1.2 团队成员基本信息）。
        旧实现从"团队信息与分工"起截、被"1.2"截断 → 漏抓；修复后定位到表头、抓到全员。"""
        report = (
            "团队信息与分工（5 分）\n"
            "1实验任务选择说明\n"
            "本次实验所选项目为智能车双闪灯控制实验，选择该任务主要基于以下三点理由：\n"
            "1.专业贴合度：车身灯光控制是车载BCM核心功能……\n"
            "2.技术覆盖完整：覆盖GPIO、EXTI中断、状态机……\n"
            "1.2 团队成员基本信息\n"
            "李全\n23071140141\n汽服2301B班\n硬件搭建\n"
            "闫建铭\n23071140128\n汽服2301B班\n软件编程\n"
            "个人分工说明\n……"
        )
        members = parse_team_members(report, "23071140141", "李全")
        assert {sid for sid, _ in members} == {"23071140141", "23071140128"}

    def test_clean_inline_table_two_members(self):
        """干净表（姓名/学号同行，闫建铭式）→ 仍抓到两人。"""
        report = (
            "团队信息与分工\n"
            "1.1 团队成员基本信息\n"
            "李全 23071140141 汽服2301B班 硬件搭建\n"
            "闫建铭 23071140128 汽服2301B班 软件编程\n"
            "1.2 个人分工说明\n……"
        )
        members = parse_team_members(report, "23071140128", "闫建铭")
        assert {sid for sid, _ in members} == {"23071140141", "23071140128"}

    def test_no_team_section_returns_primary(self):
        """正文无团队表 → 回退为 primary 一人。"""
        assert parse_team_members("正文，没有团队信息表。", "23071140141", "李全") == [
            ("23071140141", "李全")
        ]

    def test_role_prefixed_name_still_parsed(self):
        """角色前缀（组长张三）兼容——既不被当独立姓名，也不漏掉真名。"""
        report = (
            "团队成员基本信息\n"
            "组长李全 23071140141 班 硬件\n"
            "组员闫建铭 23071140128 班 软件\n"
            "个人分工说明\n……"
        )
        members = parse_team_members(report, "23071140141", "李全")
        assert {sid for sid, _ in members} == {"23071140141", "23071140128"}
        names = {n for _, n in members}
        assert "李全" in names and "闫建铭" in names
