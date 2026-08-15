# -*- coding: utf-8 -*-
"""Input parsers (read-only, stateless, independently testable).

KeilProjectParser extracts USER business-logic sources from student
.uvprojx projects so similarity/grading see student code, not vendor
boilerplate (CMSIS / HAL dominate file count and are near-identical
across students).
"""

from .keil_project_parser import KeilProjectParser, KeilSourceFile

__all__ = ["KeilProjectParser", "KeilSourceFile"]
