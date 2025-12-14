# base/log.py
# 兼容 MicroPython 的简单日志工具

try:
    # MicroPython 和 CPython 都有的接口
    from time import ticks_ms, localtime, ticks_diff
except ImportError:
    # 以防某些端口名字不同
    from utime import ticks_ms, localtime, ticks_diff

# 记录程序开始时间
_start_ticks = ticks_ms()

def _uptime_str():
    """
    返回程序运行时间，格式为 HH:MM:SS
    """
    try:
        uptime_ms = ticks_diff(ticks_ms(), _start_ticks)
        total_seconds = uptime_ms // 1000
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return "%02d:%02d:%02d" % (hours, minutes, seconds)
    except Exception:
        return "??:??:??"

def _rtc_str():
    """
    返回RTC时间，如果没有设置则显示运行时间
    """
    try:
        y, m, d, hh, mm, ss, *_ = localtime()
        # 如果是2000年，说明RTC未设置，使用运行时间
        if y == 2000:
            return "UPTIME " + _uptime_str()
        return "%04d-%02d-%02d %02d:%02d:%02d" % (y, m, d, hh, mm, ss)
    except Exception:
        return _uptime_str()

def _format_ticks(ms):
    """
    格式化ticks显示，右对齐6位
    """
    return "{:>6}ms".format(ms)

def _log_with_args(level, tag, format_str, *args):
    """
    统一的日志格式化函数
    level: 日志级别
    tag: 标签
    format_str: 格式字符串
    args: 参数列表
    """
    try:
        if args and isinstance(format_str, str):
            # 如果有格式字符串和参数，进行格式化
            message = format_str % args
        else:
            # 否则直接拼接所有参数
            message = " ".join(str(arg) for arg in (format_str,) + args)
    except (TypeError, ValueError):
        # 格式化失败，直接拼接
        message = " ".join(str(arg) for arg in (format_str,) + args)

    print("[{}][{}][{}] {}".format(level, _rtc_str(), tag, message))

def debug(tag, *args):
    """
    Debug 日志：带时间 + ticks_ms
    """
    if args and isinstance(args[0], str) and '%' in args[0]:
        # 如果第一个参数是格式字符串
        format_str = args[0]
        format_args = args[1:]
        _log_with_args("DEBUG", tag, format_str, *format_args)
    else:
        # 否则直接拼接
        _log_with_args("DEBUG", tag, *args)


def info(tag, *args):
    """
    Info 日志
    """
    if args and isinstance(args[0], str) and '%' in args[0]:
        format_str = args[0]
        format_args = args[1:]
        _log_with_args("INFO", tag, format_str, *format_args)
    else:
        _log_with_args("INFO", tag, *args)


def warn(tag, *args):
    """
    Warn 日志
    """
    if args and isinstance(args[0], str) and '%' in args[0]:
        format_str = args[0]
        format_args = args[1:]
        _log_with_args("WARN", tag, format_str, *format_args)
    else:
        _log_with_args("WARN", tag, *args)


def error(tag, *args):
    """
    Error 日志
    """
    if args and isinstance(args[0], str) and '%' in args[0]:
        format_str = args[0]
        format_args = args[1:]
        _log_with_args("ERROR", tag, format_str, *format_args)
    else:
        _log_with_args("ERROR", tag, *args)
