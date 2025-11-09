# esp32_buttons_oled_hcsr04.py
# 四键保留（key1 长按 -> GPIO15 上锁存为 1），非阻塞式 HC-SR04 测距 + OLED 实时显示（带详细日志）
import time
import gc
from machine import Pin, I2C, Timer
import micropython

# 允许中断抛异常/缓冲
micropython.alloc_emergency_exception_buf(128)

# ======================
# 日志系统（0=ERROR, 1=INFO, 2=DEBUG, 3=TRACE）
# ======================
LOG_LEVEL = 2
def _now_ms(): return time.ticks_ms()
def _fmt(ms):   return "{:>8d}ms".format(ms)
def log(level, msg, *args):
    if level <= LOG_LEVEL:
        try:
            print("[{}] {} | ".format(("ERR","INF","DBG","TRC")[level], _fmt(_now_ms())) + (msg % args if args else msg))
        except:
            pass
ERR, INF, DBG, TRC = 0, 1, 2, 3

# ======================
# 可调硬件参数
# ======================
# 4 个按键：内部上拉（未按=1，按下=0）
BTN1_PIN = 25  # 长按 -> 15 脚置 1 并锁存
BTN2_PIN = 26
BTN3_PIN = 27
BTN4_PIN = 14

# 锁存输出引脚（要求：长按 key1 后置 1 保持）
LATCH_OUT_PIN = 15

# OLED I2C
I2C_SDA = 23
I2C_SCL = 18
I2C_FREQ = 400_000
OLED_ADDR = 0x3C  # 常见 SSD1306 地址

# 超声测距 HC-SR04
TRIG_PIN = 22   # 输出，10us 脉冲
ECHO_PIN = 21   # 输入，上升沿记录开始，下降沿记录结束
MEAS_PERIOD_MS = 100  # 测量周期（越小刷新越快，但注意回波时间与串扰）

# 长按 & 去抖
LONG_PRESS_MS = 1200
DEBOUNCE_MS = 30

# ======================
# 硬件对象
# ======================
btn1 = Pin(BTN1_PIN, Pin.IN, Pin.PULL_UP)
btn2 = Pin(BTN2_PIN, Pin.IN, Pin.PULL_UP)
btn3 = Pin(BTN3_PIN, Pin.IN, Pin.PULL_UP)
btn4 = Pin(BTN4_PIN, Pin.IN, Pin.PULL_UP)

latch_out = Pin(LATCH_OUT_PIN, Pin.OUT)

trig = Pin(TRIG_PIN, Pin.OUT, value=0)
echo = Pin(ECHO_PIN, Pin.IN)

# I2C & OLED
i2c = I2C(0, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=I2C_FREQ)
log(INF, "I2C(0) init: SDA=%d SCL=%d %dkHz", I2C_SDA, I2C_SCL, I2C_FREQ//1000)
try:
    devs = i2c.scan()
    log(INF, "I2C scan: %s", [hex(a) for a in devs])
except Exception as e:
    log(ERR, "I2C 扫描失败：%r", e)
    devs = []

# SSD1306 驱动
try:
    import ssd1306
except ImportError:
    raise ImportError("未找到 ssd1306 驱动模块，请将 ssd1306.py 拷到板子上，或告知我你的屏幕型号/驱动名。")

oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=OLED_ADDR)
log(INF, "SSD1306 初始化: addr=%s", hex(OLED_ADDR))

# ======================
# 运行时状态（按键1）
# ======================
_last_raw_1 = 1
_stable_1 = 1
_last_debounce_time_1 = 0
_press_start_time_1 = None
_latched_on = False

# ======================
# 运行时状态（测距）
# ======================
# echo 时序
_t_start = 0       # us
_t_end = 0         # us
_has_start = False
_distance_cm = None
_measure_ok = False

# 统计用
_timer_tick_count = 0
_irq_rising = 0
_irq_falling = 0
_last_dt_us = None
_bad_range = 0

# 定时器（非阻塞触发测距）
_timer = Timer(0)

# ======================
# 清状态
# ======================
def clear_state():
    global _last_raw_1, _stable_1, _last_debounce_time_1, _press_start_time_1, _latched_on
    global _t_start, _t_end, _has_start, _distance_cm, _measure_ok
    global _timer_tick_count, _irq_rising, _irq_falling, _last_dt_us, _bad_range

    # 输出默认拉低（未锁存）
    latch_out.off()
    _latched_on = False

    # 按键状态同步
    raw = btn1.value()
    _last_raw_1 = raw
    _stable_1 = raw
    _last_debounce_time_1 = time.ticks_ms()
    _press_start_time_1 = None

    # 测距状态
    _t_start = 0
    _t_end = 0
    _has_start = False
    _distance_cm = None
    _measure_ok = False

    # 统计
    _timer_tick_count = 0
    _irq_rising = 0
    _irq_falling = 0
    _last_dt_us = None
    _bad_range = 0

    # OLED 清屏
    oled.fill(0)
    oled.text("HC-SR04 + OLED", 0, 0)
    oled.text("Init...", 0, 16)
    oled.show()

    gc.collect()
    log(INF, "状态已清空：latch=0, key1=%d", _stable_1)

# ======================
# 按键1：去抖 + 长按锁存
# ======================
def process_key1():
    global _last_raw_1, _stable_1, _last_debounce_time_1, _press_start_time_1, _latched_on

    raw = btn1.value()
    if raw != _last_raw_1:
        _last_raw_1 = raw
        _last_debounce_time_1 = time.ticks_ms()
        log(TRC, "K1 原始跳变: %d", raw)

    if time.ticks_diff(time.ticks_ms(), _last_debounce_time_1) > DEBOUNCE_MS:
        # 稳态切换
        if raw != _stable_1:
            prev = _stable_1
            _stable_1 = raw
            log(DBG, "K1 稳态 %d -> %d", prev, _stable_1)
            if _stable_1 == 0:   # 按下
                _press_start_time_1 = time.ticks_ms()
                log(DBG, "K1 按下：开始长按计时")
            else:                # 松开
                if _press_start_time_1 is not None:
                    held = time.ticks_diff(time.ticks_ms(), _press_start_time_1)
                    log(DBG, "K1 松开：本次按住 %d ms", held)
                _press_start_time_1 = None

        # 长按判定（仅在未锁存时）
        if (_stable_1 == 0) and (not _latched_on) and (_press_start_time_1 is not None):
            held = time.ticks_diff(time.ticks_ms(), _press_start_time_1)
            if held >= LONG_PRESS_MS:
                latch_out.on()
                _latched_on = True
                draw_status_line("LATCH ON")
                log(INF, "K1 长按触发：GPIO%d=1 已锁存", LATCH_OUT_PIN)

# ======================
# HC-SR04 非阻塞测距
#  - Timer 每 MEAS_PERIOD_MS 触发一次：发 ~10us TRIG 脉冲
#  - ECHO 上升沿记录开始时间；下降沿记录结束并计算距离
# ======================
def _timer_cb(_t):
    global _timer_tick_count
    _timer_tick_count += 1
    # 产生 >=10us 上升脉冲；尽量短小，避免在中断里 sleep
    trig.off()
    trig.on()
    # 简短忙等 ~10us（Timer 回调处不可用 sleep_us；简短循环即可）
    for _ in range(40):  # 约 10us 左右（依据主频，大致即可）
        pass
    trig.off()

def _echo_irq(pin):
    # 使用 ticks_us 捕捉（IRQ 中不打印日志，避免分配内存）
    global _t_start, _t_end, _has_start, _distance_cm, _measure_ok
    global _irq_rising, _irq_falling, _last_dt_us, _bad_range
    if pin.value() == 1:
        _t_start = time.ticks_us()
        _has_start = True
        _irq_rising += 1
    else:
        if _has_start:
            _t_end = time.ticks_us()
            dt = time.ticks_diff(_t_end, _t_start)  # us
            _last_dt_us = dt
            _distance_cm = dt * 0.01715
            _measure_ok = True
            _has_start = False
            _irq_falling += 1
            if not (2.0 <= _distance_cm <= 400.0):
                _bad_range += 1

# ======================
# OLED 显示
# ======================
def draw_status_line(msg):
    # 顶部状态行（反白）
    oled.fill_rect(0, 0, 128, 12, 1)
    oled.fill_rect(0, 12, 128, 52, 0)  # 清内容区，避免覆盖
    oled.text(msg[:20], 2, 2, 0)       # 反白区用 0 颜色写字

def draw_distance():
    # 在内容区显示距离与状态
    y = 18
    if _measure_ok and _distance_cm is not None:
        d = _distance_cm
        if 2.0 <= d <= 400.0:
            oled.text("Distance:", 0, y); y += 16
            oled.text("{:6.2f} cm".format(d), 0, y); y += 16
        else:
            oled.text("Distance:", 0, y); y += 16
            oled.text("Out of range", 0, y); y += 16
    else:
        oled.text("Measuring...", 0, y); y += 16

    # 简要显示 latch 状态与按键读数（调试友好）
    oled.text("Latch:{} K1:{}".format(1 if _latched_on else 0, _stable_1), 0, y)

# ======================
# 主程序
# ======================
def main():
    log(INF, "===== 程序启动 =====")
    log(INF, "注意：HC-SR04 ECHO 可能为 5V，请做好分压/电平转换（ECHO→GPIO21）。")

    clear_state()

    # 绑定 ECHO 中断（上升/下降沿）
    echo.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=_echo_irq)
    log(INF, "ECHO IRQ 绑定：GPIO%d", ECHO_PIN)

    # 启动周期触发测距的定时器（非阻塞）
    _timer.init(mode=Timer.PERIODIC, period=MEAS_PERIOD_MS, callback=_timer_cb)
    log(INF, "TRIG 周期启动：%d ms/次", MEAS_PERIOD_MS)

    # 首屏状态
    draw_status_line("READY")
    draw_distance()
    oled.show()

    # 主循环：处理按键 + 刷新 OLED（非阻塞）
    last_oled_update = time.ticks_ms()
    last_hb = time.ticks_ms()
    OLED_REFRESH_MS = 60   # 屏幕刷新节流
    HEARTBEAT_MS    = 1000 # 日志心跳

    while True:
        # 处理按键1长按锁存（其余 3 个按键保留为输入，不触发动作）
        process_key1()

        # 周期性刷新 OLED
        now = time.ticks_ms()
        if time.ticks_diff(now, last_oled_update) >= OLED_REFRESH_MS:
            draw_status_line("READY" if not _latched_on else "LATCH ON")
            draw_distance()
            oled.show()
            last_oled_update = now

        # 心跳日志（把 IRQ/测距统计集中打印）
        if time.ticks_diff(now, last_hb) >= HEARTBEAT_MS:
            last_hb = now
            ks = (btn1.value(), btn2.value(), btn3.value(), btn4.value())
            dist = ("%.2fcm" % _distance_cm) if _distance_cm is not None else "None"
            log(INF, "心跳：ticks=%d rise/fall=%d/%d last_dt=%s us dist=%s bad=%d latch=%d keys=%s",
                _timer_tick_count, _irq_rising, _irq_falling,
                str(_last_dt_us) if _last_dt_us is not None else "None",
                dist, _bad_range, 1 if _latched_on else 0, ks)

        # 不阻塞，让出 CPU
        time.sleep_ms(2)

if __name__ == "__main__":
    main()
