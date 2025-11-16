# base/log.py
# 兼容 MicroPython 的简单日志工具

try:
    # MicroPython 和 CPython 都有的接口
    from time import ticks_ms, localtime
except ImportError:
    # 以防某些端口名字不同
    from utime import ticks_ms, localtime


def _now_str():
    """
    返回类似 '2025-01-01 12:34:56' 的字符串。
    在没有设置 RTC 的板子上，日期可能是默认值（比如 2000-01-01）。
    """
    try:
        y, m, d, hh, mm, ss, *_ = localtime()
        return "%04d-%02d-%02d %02d:%02d:%02d" % (y, m, d, hh, mm, ss)
    except Exception:
        # 退化：万一 localtime 不可用
        return "0000-00-00 00:00:00"


def debug(tag, *args):
    """
    Debug 日志：带时间 + ticks_ms
    """
    print("[{}][{:>7}ms][{}]".format(_now_str(), ticks_ms(), tag), *args)


def info(tag, *args):
    """
    Info 日志
    """
    print("[INFO][{}][{}]".format(_now_str(), tag), *args)


def warn(tag, *args):
    """
    Warn 日志
    """
    print("[WARN][{}][{}]".format(_now_str(), tag), *args)
