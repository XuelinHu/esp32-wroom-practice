
# K1 长按 -> GPIO15 锁存，HC-SR04 非阻塞声波测距 + 统一 Screen 显示

import time
import micropython
from machine import Pin, Timer
from base.display import screen  # 使用你封装好的 Screen

micropython.alloc_emergency_exception_buf(128)

# 硬件参数
BTN_PINS       = (25, 26, 27, 14)  # 四键保留，K1 = 第一个
LATCH_OUT_PIN  = 15
TRIG_PIN       = 22
ECHO_PIN       = 21
MEAS_PERIOD_MS = 100
LONG_PRESS_MS  = 1200
DEBOUNCE_MS    = 30

# 按键及锁存
buttons   = [Pin(p, Pin.IN, Pin.PULL_UP) for p in BTN_PINS]
btn1      = buttons[0]
latch_out = Pin(LATCH_OUT_PIN, Pin.OUT, value=0)

# 超声波
trig  = Pin(TRIG_PIN, Pin.OUT, value=0)
echo  = Pin(ECHO_PIN, Pin.IN)
timer = Timer(0)

# K1 状态
_last_raw     = btn1.value()
_stable       = _last_raw
_change_time  = time.ticks_ms()
_press_start  = None
_latched      = False

# 测距状态
_t_start      = 0
_has_start    = False
_distance_cm  = None


def _timer_cb(_t):
    # 产生约 10us 脉冲
    trig.off()
    trig.on()
    for _ in range(40):
        pass
    trig.off()


def _echo_irq(pin):
    global _t_start, _has_start, _distance_cm
    if pin.value():  # 上升沿
        _t_start = time.ticks_us()
        _has_start = True
    elif _has_start:  # 下降沿
        dt = time.ticks_diff(time.ticks_us(), _t_start)  # us
        _distance_cm = dt * 0.01715  # 声速换算 cm
        _has_start = False


def _update_key1():
    global _last_raw, _stable, _change_time, _press_start, _latched

    raw = btn1.value()
    now = time.ticks_ms()

    # 去抖：检测原始跳变
    if raw != _last_raw:
        _last_raw = raw
        _change_time = now

    # 超过去抖时间后，更新稳态
    if time.ticks_diff(now, _change_time) > DEBOUNCE_MS and raw != _stable:
        _stable = raw
        if raw == 0:        # 按下
            _press_start = now
        else:               # 松开
            _press_start = None

    # 长按触发锁存
    if _stable == 0 and not _latched and _press_start is not None:
        if time.ticks_diff(now, _press_start) >= LONG_PRESS_MS:
            latch_out.on()
            _latched = True


def _update_screen():
    status = "LATCH ON" if _latched else "READY"
    if _distance_cm is None:
        screen.show_lines(status, "Measuring...")
    else:
        screen.show_lines(status, "Distance: %.2f cm" % _distance_cm)


def run():
    echo.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=_echo_irq)
    timer.init(mode=Timer.PERIODIC, period=MEAS_PERIOD_MS, callback=_timer_cb)

    while True:
        _update_key1()
        _update_screen()
        time.sleep_ms(60)


if __name__ == "__main__":
    run()
