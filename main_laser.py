# laser_sensor_debug.py
# ESP32 + 激光传感模块 (数字DO) 非阻塞检测：GPIO22 + 中断去抖 + 分级调试日志
import time
from machine import Pin

# ============ 日志系统 ============
LOG_LEVEL = 2  # 0=ERROR, 1=INFO, 2=DEBUG, 3=TRACE
def _now_ms(): return time.ticks_ms()
def _fmt_ms(ms): return "{:>8d}ms".format(ms)
def log(level, msg, *args):
    if level <= LOG_LEVEL:
        try:
            print("[{}] {} | ".format(("ERR","INF","DBG","TRC")[level], _fmt_ms(_now_ms())) + (msg % args if args else msg))
        except Exception as e:
            print("[LOGFAIL]", msg, args, e)
ERR, INF, DBG, TRC = 0, 1, 2, 3

# ============ 可调参数 ============
SENSOR_PIN_NUM  = 22     # 你的要求：用 GPIO22
USE_PULL_UP     = True   # True=内部上拉（常见：DO为开漏或默认高），False=内部下拉
ACTIVE_HIGH     = True   # True=高电平=“检测到”（看你模块逻辑；不确定先看串口日志）
DEBOUNCE_MS     = 30     # 去抖时间
HEARTBEAT_MS    = 1000   # 心跳打印

# ============ 硬件初始化 ============
if USE_PULL_UP:
    sensor = Pin(SENSOR_PIN_NUM, Pin.IN, Pin.PULL_UP)
else:
    sensor = Pin(SENSOR_PIN_NUM, Pin.IN, Pin.PULL_DOWN)

# ============ 运行时状态 ============
_state = 0                 # 0=未检测到 / 1=检测到
_last_edge_ms = 0
_rise_count = 0
_fall_count = 0
_event_count = 0
_last_on_ms = None         # 最近一次“检测到”的时间
_last_off_ms = None        # 最近一次“未检测”的时间

def _logical_active():
    """把物理电平转换成逻辑态：1=检测到, 0=未检测到。"""
    v = sensor.value()
    return 1 if ((v == 1) if ACTIVE_HIGH else (v == 0)) else 0

def _irq_handler(pin):
    """中断：边沿到来 -> 去抖 -> 读逻辑态 -> 更新统计"""
    global _state, _last_edge_ms, _rise_count, _fall_count, _event_count, _last_on_ms, _last_off_ms
    now = _now_ms()
    if time.ticks_diff(now, _last_edge_ms) < DEBOUNCE_MS:
        return
    _last_edge_ms = now

    raw = pin.value()
    active = _logical_active()



    if active and _state == 0:
        _state = 1
        _event_count += 1
        _last_on_ms = now
        if raw == 1: _rise_count += 1
        else:        _fall_count += 1
        log(INF, "激光传感：触发 (event#%d, raw=%d)", _event_count, raw)
    elif (not active) and _state == 1:
        _state = 0
        _last_off_ms = now
        if raw == 1: _rise_count += 1
        else:        _fall_count += 1
        log(DBG, "激光传感：恢复 (raw=%d)", raw)
    else:
        log(TRC, "边沿但状态未变 (raw=%d, active=%d, state=%d)", raw, active, _state)

def _bind_irq():
    sensor.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=_irq_handler)
    log(INF, "IRQ 绑定：GPIO%d, 上拉=%s, ACTIVE_%s, 去抖=%dms",
        SENSOR_PIN_NUM, USE_PULL_UP, "HIGH" if ACTIVE_HIGH else "LOW", DEBOUNCE_MS)

def _init_state():
    global _state, _event_count, _last_on_ms, _last_off_ms, _rise_count, _fall_count, _last_edge_ms
    _state = _logical_active()
    _event_count = 1 if _state else 0
    _last_on_ms  = _now_ms() if _state else None
    _last_off_ms = _now_ms() if not _state else None
    _rise_count = 0
    _fall_count = 0
    _last_edge_ms = _now_ms()
    log(INF, "初始：state=%s (ACTIVE_%s)", "ON" if _state else "OFF", "HIGH" if ACTIVE_HIGH else "LOW")

def main():
    log(INF, "==== 激光传感(数字DO) 非阻塞监测 ====")
    _init_state()
    _bind_irq()

    last_hb = _now_ms()
    while True:
        now = _now_ms()
        if time.ticks_diff(now, last_hb) >= HEARTBEAT_MS:
            last_hb = now
            on_ago  = ("%.1fs" % (time.ticks_diff(now, _last_on_ms)/1000))  if _last_on_ms  else "--.-s"
            off_ago = ("%.1fs" % (time.ticks_diff(now, _last_off_ms)/1000)) if _last_off_ms else "--.-s"
            log(INF, "心跳：state=%s ev=%d rise/fall=%d/%d sinceON/sinceOFF=%s/%s",
                "ON" if _state else "OFF", _event_count, _rise_count, _fall_count, on_ago, off_ago)
        time.sleep_ms(2)

if __name__ == "__main__":
    main()
