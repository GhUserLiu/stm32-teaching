# -*- coding: utf-8 -*-
"""Pydantic schemas for the teaching platform.

P1 scope: unified configuration (config.py). Task / grading / submission
schemas land in later phases as the services layer is extracted.
"""

from .config import (
    AppSettings,
    get_settings,
    load_settings,
    reload_settings,
)

__all__ = ["AppSettings", "get_settings", "load_settings", "reload_settings"]
