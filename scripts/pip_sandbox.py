# -*- coding: utf-8 -*-
"""沙盒内安装包装器：patch tempfile.mkdtemp 为普通 mkdir（绕过临时目录写限制）后调 pip。"""
import os, sys, itertools

_c = itertools.count()
def _mkdtemp(prefix=None, dir=None, suffix=''):
    base = dir or os.environ.get('TMP') or '.'
    d = os.path.join(base, f"{(prefix or 'tmp')}{next(_c)}{suffix}")
    os.makedirs(d, exist_ok=True)
    return d

import tempfile
tempfile.mkdtemp = _mkdtemp
# TemporaryDirectory 依赖 mkdtemp（已被 patch）

from pip._internal.cli.main import main
args = sys.argv[1:]
sys.exit(main(args))
