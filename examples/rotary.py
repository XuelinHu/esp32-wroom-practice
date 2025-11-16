# encoder_oled_min.py
# ESP32 旋钮编码器：SW=GPIO19, DT=GPIO21, CLK=GPIO22
# CLK 下降沿 IRQ 判方向 + SW IRQ 去抖；通过 base.display 的 screen 显示

import time
import micropython
from machine import Pin
from base.display import screen  # 统一屏幕/串口输出

micropython.alloc_emergency_exception_buf(128)

# ========= 引脚参数 =========
PIN_SW  = 19  # 按下接地
PIN_DT  = 21
PIN_CLK = 22

# ========= 编码器参数 =========
STEP                = 1          # 每一“格”的步进
MIN_VAL             = -100       # 最小值
MAX_VAL             =  100       # 最大值
CLK_MIN_INTERVAL_US = 1500       # CLK 边沿最小间隔(去抖)
SW_DEBOUNCE_MS      = 80         # SW 按键去抖
SCREEN_REFRESH_MS   = 60         # 屏幕刷新节流

# ========= 硬件对象 =========
sw  = Pin(PIN_SW,  Pin.IN, Pin.PULL_UP)   # 按下=0
dt  = Pin(PIN_DT,  Pin.IN, Pin.PULL_UP)
clk = Pin(PIN_CLK, Pin.IN, Pin.PULL_UP)

# ========= 运行时状态 =========
val            = 0
cw_count       = 0
ccw_count      = 0
sw_press_count = 0

last_clk_us = 0
last_sw_ms  = 0
sw_state    = 1  # 1=未按, 0=按下


def _clamp(v):
    # 限制在 [-100, 100]
    if v < MIN_VAL:
        return MIN_VAL
    if v > MAX_VAL:
        return MAX_VAL
    return v


# ========= IRQ =========
def _clk_irq(pin):
    # 仅在 CLK 的下降沿处理，方向由 DT 电平决定
    global val, cw_count, ccw_count, last_clk_us
    now = time.ticks_us()
    if time.ticks_diff(now, last_clk_us) < CLK_MIN_INTERVAL_US:
        return
    last_clk_us = now

    if dt.value():          # DT=1 一个方向
        val = _clamp(val + STEP)
        cw_count += 1
    else:                   # DT=0 反方向
        val = _clamp(val - STEP)
        ccw_count += 1


def _sw_irq(pin):
    # SW 按下接地：下降沿表示“按下”
    global last_sw_ms, sw_press_count, sw_state, val
    now = time.ticks_ms()
    if time.ticks_diff(now, last_sw_ms) < SW_DEBOUNCE_MS:
        return
    last_sw_ms = now

    raw = pin.value()
    # 按下沿：清零计数
    if raw == 0 and sw_state == 1:
        sw_state = 0
        sw_press_count += 1
        val = 0
    # 松开沿：恢复状态
    elif raw == 1 and sw_state == 0:
        sw_state = 1


# 绑定中断
clk.irq(trigger=Pin.IRQ_FALLING, handler=_clk_irq)
sw.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=_sw_irq)


# ========= 显示 =========
def _update_screen():
    screen.show_lines(
        "Rotary Encoder",
        "VAL: %d" % val,
        "CW/CCW: %d/%d" % (cw_count, ccw_count),
        "SW#: %d" % sw_press_count,
    )


# ========= 主程序 =========
def run():
    global last_clk_us
    last_clk_us = time.ticks_us()

    last_screen = time.ticks_ms()
    _update_screen()

    while True:
        now = time.ticks_ms()
        if time.ticks_diff(now, last_screen) >= SCREEN_REFRESH_MS:
            _update_screen()
            last_screen = now

        time.sleep_ms(2)


if __name__ == "__main__":
    run()
