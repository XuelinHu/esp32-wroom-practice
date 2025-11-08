import time
import gc
from machine import Pin, PWM
try:
    import network
except:
    network = None

# ======================
# 日志系统
# ======================
# 0=ERROR, 1=INFO, 2=DEBUG, 3=TRACE
LOG_LEVEL = 2

def _now_ms():
    return time.ticks_ms()

def _fmt_ms(ms):
    return "{:>8d}ms".format(ms)

def log(level, msg, *args):
    if level <= LOG_LEVEL:
        try:
            print("[{}] {} | ".format(
                ("ERR","INF","DBG","TRC")[level],
                _fmt_ms(_now_ms())
            ) + (msg % args if args else msg))
        except Exception as e:
            # 打印格式化失败也不能影响主逻辑
            print("[LOG-FAIL]", msg, args, e)

ERR, INF, DBG, TRC = 0, 1, 2, 3

# ======================
# 硬件引脚
# ======================
btn1 = Pin(25, Pin.IN, Pin.PULL_UP)  # 长按触发锁存
btn2 = Pin(26, Pin.IN, Pin.PULL_UP)
btn3 = Pin(27, Pin.IN, Pin.PULL_UP)
btn4 = Pin(14, Pin.IN, Pin.PULL_UP)

led_pin = Pin(15, Pin.OUT)

# ======================
# 参数
# ======================
LONG_PRESS_MS = 1200  # 长按阈值
DEBOUNCE_MS   = 30    # 去抖时间
MAIN_LOOP_DELAY_MS = 5
HEARTBEAT_MS = 1000   # 心跳打印间隔（状态速览）

# ======================
# 运行时状态
# ======================
_last_raw_1 = 1
_stable_1 = 1
_last_debounce_time_1 = 0
_press_start_time_1 = None
_latched_on = False
_bounce_count = 0
_last_heartbeat = 0


def clear_esp32_state():
    log(INF, "清理 ESP32 可能残留状态...")
    # 1) 网络
    if network is not None:
        try:
            sta = network.WLAN(network.STA_IF)
            ap  = network.WLAN(network.AP_IF)
            if sta.active():
                log(DBG, "关闭 STA")
                sta.active(False)
            if ap.active():
                log(DBG, "关闭 AP")
                ap.active(False)
        except Exception as e:
            log(DBG, "关闭网络忽略异常: %s", repr(e))

    # 2) 清理可能残留的中断
    try:
        btn1.irq(handler=None); btn2.irq(handler=None)
        btn3.irq(handler=None); btn4.irq(handler=None)
        log(DBG, "已清除按键 IRQ 回调")
    except Exception as e:
        log(DBG, "清 IRQ 忽略异常: %s", repr(e))

    # 3) 15 脚恢复为普通输出并拉低
    try:
        led_pin.init(mode=Pin.OUT, pull=None)
        led_pin.off()
        log(DBG, "15脚已设为GPIO输出并拉低")
    except Exception as e:
        log(DBG, "配置 15脚 忽略异常: %s", repr(e))

    # 4) 若 15 脚遗留 PWM，尝试解除
    try:
        _tmp_pwm = PWM(led_pin)
        _tmp_pwm.deinit()
        led_pin.off()
        log(DBG, "尝试解除 15脚 PWM 绑定（若存在）")
    except Exception as e:
        log(TRC, "解除 PWM 忽略异常(多为正常): %s", repr(e))

    # 5) GC
    try:
        gc.collect()
        log(DBG, "GC 完成，剩余内存未显示（Micropython不同固件接口不一）")
    except Exception as e:
        log(DBG, "GC 忽略异常: %s", repr(e))


def clear_state():
    global _last_raw_1, _stable_1, _last_debounce_time_1, _press_start_time_1, _latched_on, _bounce_count
    led_pin.off()
    _last_debounce_time_1 = _now_ms()
    _press_start_time_1 = None
    _latched_on = False
    _bounce_count = 0

    raw = btn1.value()
    _last_raw_1 = raw
    _stable_1 = raw

    # 同步其他按键的电平一次（仅日志）
    r2, r3, r4 = btn2.value(), btn3.value(), btn4.value()
    log(INF, "清程序状态：key1=%d, key2=%d, key3=%d, key4=%d, 15脚=%d",
        raw, r2, r3, r4, led_pin.value())


def _trace_edges_and_debounce():
    """处理 key1 的去抖与稳定态转换，输出细粒度日志。"""
    global _last_raw_1, _stable_1, _last_debounce_time_1, _bounce_count, _press_start_time_1
    raw = btn1.value()

    if raw != _last_raw_1:
        # 原始读数变化（可能是抖动）
        _last_raw_1 = raw
        _last_debounce_time_1 = _now_ms()
        _bounce_count += 1
        log(TRC, "原始变化 raw=%d（累计抖动=%d）", raw, _bounce_count)

    # 稳定判定
    if time.ticks_diff(_now_ms(), _last_debounce_time_1) > DEBOUNCE_MS:
        if raw != _stable_1:
            prev = _stable_1
            _stable_1 = raw
            log(DBG, "稳定态切换 %d -> %d (去抖=%dms)",
                prev, _stable_1, DEBOUNCE_MS)
            if _stable_1 == 0:  # 按下
                _press_start_time_1 = _now_ms()
                log(DBG, "按下稳定，开始计时 t0=%s", _fmt_ms(_press_start_time_1))
            else:
                # 松开
                if _press_start_time_1 is not None:
                    held = time.ticks_diff(_now_ms(), _press_start_time_1)
                    log(DBG, "松开稳定，按住时长=%dms", held)
                _press_start_time_1 = None

    return raw, _stable_1


def _check_long_press_and_latch():
    global _latched_on
    if (_stable_1 == 0) and (not _latched_on) and (_press_start_time_1 is not None):
        held = time.ticks_diff(_now_ms(), _press_start_time_1)
        if held >= LONG_PRESS_MS:
            led_pin.on()
            _latched_on = True
            log(INF, "【长按达阈值】held=%dms -> 15脚置1并锁存", held)


def _heartbeat():
    global _last_heartbeat
    now = _now_ms()
    if time.ticks_diff(now, _last_heartbeat) >= HEARTBEAT_MS:
        _last_heartbeat = now
        # 输出一眼可见的关键状态
        log(INF, "心跳: raw=%d stable=%d latched=%s led15=%d %s",
            _last_raw_1, _stable_1, _latched_on, led_pin.value(),
            "(按下计时中)" if _press_start_time_1 is not None else "")


def main():
    log(INF, "==== 启动 ====")
    clear_esp32_state()
    clear_state()

    log(INF, "参数：LONG_PRESS_MS=%d, DEBOUNCE_MS=%d, LOG_LEVEL=%d", LONG_PRESS_MS, DEBOUNCE_MS, LOG_LEVEL)
    log(INF, "提示：LOG_LEVEL=3 可打开 TRACE 逐读日志（更详细）")

    while True:
        _trace_edges_and_debounce()
        _check_long_press_and_latch()
        _heartbeat()
        time.sleep_ms(MAIN_LOOP_DELAY_MS)


if __name__ == "__main__":
    main()
