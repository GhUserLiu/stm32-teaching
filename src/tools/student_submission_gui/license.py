# -*- coding: utf-8 -*-
"""学生端授权模块：网络时间校验 + 断网兜底 + 防时间回拨 + 到期退出。

策略（与课程组约定 2026-10-29）：
- 到期日常量烧入（构建脚本生成 license_data.py，Nuitka/PyInstaller 编译后不可见明文）
- 时间来源优先级：网络时间（HTTP Date 头，多端点容错）→ 本机时间 + 防回拨
- 防回拨：把"见过的最晚时间"持久化到用户目录；当前时间早于它 → 判定篡改 → 过期
- 过期/篡改：弹窗说明 + 拒绝启动
"""
import os
import sys
import time
import struct
import socket
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from .license_data import EXPIRY_DATE        # 构建时生成
except ImportError:
    EXPIRY_DATE = "2026-11-15"                   # 源码运行兜底（与构建默认一致）

# 网络时间端点：HTTP Date 头（校园网可达性优先）+ SNTP
_HTTP_TIME_ENDPOINTS = [
    "https://www.baidu.com",
    "https://www.qq.com",
]
_NTP_HOSTS = ["ntp.aliyun.com", "ntp.tencent.com", "pool.ntp.org"]
_CN_TZ = timezone(timedelta(hours=8))


def _writable_root() -> Path:
    """防回拨记录文件所在目录（用户主目录，随包运行时可写）。"""
    base = Path.home() / ".mcu_selfcheck"
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        base = Path(os.environ.get("TEMP", ".")) / ".mcu_selfcheck"
        base.mkdir(parents=True, exist_ok=True)
    return base


def _http_time() -> datetime or None:
    """HTTP HEAD 读 Date 头（首选，无需任何三方库）。"""
    import urllib.request
    for url in _HTTP_TIME_ENDPOINTS:
        try:
            req = urllib.request.Request(url, method="HEAD",
                                         headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                date_hdr = resp.headers.get("Date")
                if date_hdr:
                    # RFC 1123 → UTC datetime
                    from email.utils import parsedate_to_datetime
                    return parsedate_to_datetime(date_hdr).astimezone(_CN_TZ)
        except Exception:
            continue
    return None


def _sntp_time() -> datetime or None:
    """SNTP（UDP 123）读网络时间，作为 HTTP 全挂时的第二兜底。"""
    for host in _NTP_HOSTS:
        try:
            pkt = b"\x1b" + b"\x00" * 47
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.sendto(pkt, (host, 123))
            data, _ = s.recvfrom(256)
            s.close()
            if len(data) >= 48:
                secs = struct.unpack("!Q", data[40:48])[0] - 2208988800
                return datetime.fromtimestamp(secs, tz=timezone.utc).astimezone(_CN_TZ)
        except Exception:
            continue
    return None


def network_time() -> tuple:
    """取可信当前时间。返回 (datetime, 来源) ；全失败返回 (None, None)。"""
    t = _http_time()
    if t is not None:
        return t, "网络(HTTP)"
    t = _sntp_time()
    if t is not None:
        return t, "网络(NTP)"
    return None, None


def _load_last_seen() -> datetime:
    p = _writable_root() / ".ts"
    try:
        raw = p.read_text(encoding="utf-8").strip()
        return datetime.fromisoformat(raw)
    except Exception:
        # 哨兵用 2000 年而非 datetime.min：后续要做减法，min 会溢出
        return datetime(2000, 1, 1, tzinfo=_CN_TZ)


def _save_last_seen(now: datetime):
    try:
        p = _writable_root() / ".ts"
        p.write_text(now.isoformat(), encoding="utf-8")
    except Exception:
        pass


def check_license() -> tuple:
    """启动时调用。返回 (ok, message)。

    ok=False 时 message 为给用户看的原因；调用方弹窗并退出。
    """
    expiry = datetime.fromisoformat(EXPIRY_DATE).replace(
        hour=23, minute=59, second=59, tzinfo=_CN_TZ)

    net_t, src = network_time()
    if net_t is not None:
        now = net_t
    else:
        now = datetime.now(_CN_TZ)          # 断网兜底：本机时间 + 防回拨

    # 防回拨：本机时间若早于历史最晚记录 → 篡改
    last = _load_last_seen()
    if now < last - timedelta(minutes=5):   # 5 分钟容差（正常时钟微调）
        return False, ("检测到系统时间被回拨（当前时间早于上次运行时间）。\n"
                       "为公平起见本程序已停止运行；如属误判请联系任课教师。")
    _save_last_seen(max(now, last))

    if now > expiry:
        net_note = f"（时间来源：{src}）" if src else "（离线模式：本机时间）"
        return False, (f"本版本授权已于 {EXPIRY_DATE} 到期{net_note}。\n"
                       "如需继续使用，请联系汽车工程学院单片机课程组获取新版本。")
    return True, ""
