# -*- coding: utf-8 -*-
"""CODE-modality similarity adapters.

Importing this package registers the code checkers (import-time
registration, process-global -- see algorithms.factory).
"""

from .code_checkers import (  # noqa: F401
    CodeTokenChecker,
    TemplateCodeChecker,
)

__all__ = ["CodeTokenChecker", "TemplateCodeChecker"]
