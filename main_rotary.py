# encoder_oled_debug.py
# ESP32 旋钮编码器：SW=GPIO19, DT=GPIO21, CLK=GPIO22
# 非阻塞：CLK 下降沿 IRQ 判方向 + SW IRQ 去抖；OLED 实时显示；带调试日志
import time
from machine import Pin, I2C

# ========== 日志 ==========
LOG_LEVEL = 2  # 0=ERROR, 1=INFO, 2=DEBUG, 3=TRACE
def _now_ms(): return time.ticks_ms()
def _now_us(): return time.ticks_us()
def _fmt_ms(ms): return "{:>8d}ms".format(ms)
def log(level, msg, *args):
    if level <= LOG_LEVEL:
        try:
            print("[{}] {} | ".format(("ERR","INF","DBG","TRC")[level], _fmt_ms(_now_ms())) + (msg % args if args else msg))
        except Exception as e:
            print("[LOGFAIL]", msg, args, e)
ERR, INF, DBG, TRC = 0, 1, 2, 3

# ========== 引脚参数 ==========
PIN_SW  = 19  # 按下接地
PIN_DT  = 21
PIN_CLK = 22

# OLED (SSD1306) I2C
I2C_ID   = 0
I2C_SDA  = 23
I2C_SCL  = 18
I2C_FREQ = 400_000
OLED_ADDR = 0x3C

# ========== 编码器/显示参数 ==========
STEP              = 1         # 每一“格”的步进
MIN_VAL           = -9999
MAX_VAL           =  9999
CLK_MIN_INTERVAL_US = 1500    # 边沿最小间隔(去抖/防抖动双触发) ~1.5ms
SW_DEBOUNCE_MS      = 80      # SW 按键去抖

OLED_REFRESH_MS   = 60
HEARTBEAT_MS      = 1000

# ========== 硬件对象 ==========
sw  = Pin(PIN_SW,  Pin.IN, Pin.PULL_UP)   # 按下=0
dt  = Pin(PIN_DT,  Pin.IN, Pin.PULL_UP)
clk = Pin(PIN_CLK, Pin.IN, Pin.PULL_UP)

i2c = I2C(I2C_ID, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=I2C_FREQ)
log(INF, "I2C(%d) OK SDA=%d SCL=%d %dkHz", I2C_ID, I2C_SDA, I2C_SCL, I2C_FREQ//1000)
devs = i2c.scan()
log(INF, "I2C 扫描: %s", [hex(a) for a in devs])
if (OLED_ADDR not in devs) and devs:
    OLED_ADDR = devs[0]
    log(INF, "未找到 0x3C，临时使用 %s", hex(OLED_ADDR))

try:
    import ssd1306
except ImportError:
    raise ImportError("未找到 ssd1306.py，请把驱动复制到板子上。")

oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=OLED_ADDR)
log(INF, "SSD1306 初始化：addr=%s", hex(OLED_ADDR))

# ========== 运行时状态 ==========
val = 0
last_clk_us = 0
rot_events = 0
cw_count = 0
ccw_count = 0

last_sw_ms = 0
sw_press_count = 0
sw_state = 1  # 1=未按, 0=按下

def _clamp(v):
    if v < MIN_VAL: return MIN_VAL
    if v > MAX_VAL: return MAX_VAL
    return v

# ========== IRQ ==========
def _clk_irq(pin):
    # 仅在 CLK 的“下降沿”处理（减少抖动和重复计数）
    # 方向由 DT 当下电平决定：常见规则是
    #   若 DT != CLK(此刻为0) 则一个方向，否则反方向
    # 实操更稳：直接读 DT；DT=1 表示 CW，DT=0 表示 CCW（某些编码器可能相反）
    global val, last_clk_us, rot_events, cw_count, ccw_count
    now = _now_us()
    if time.ticks_diff(now, last_clk_us) < CLK_MIN_INTERVAL_US:
        return
    last_clk_us = now

    d = dt.value()
    if d == 1:
        val = _clamp(val + STEP)
        cw_count += 1
        dir_str = "CW +"
    else:
        val = _clamp(val - STEP)
        ccw_count += 1
        dir_str = "CCW -"

    rot_events += 1
    log(TRC, "旋转: %s -> val=%d (dt=%d)", dir_str, val, d)

def _sw_irq(pin):
    # SW 按下接地：下降沿表示“按下”
    global last_sw_ms, sw_press_count, sw_state, val
    now = _now_ms()
    if time.ticks_diff(now, last_sw_ms) < SW_DEBOUNCE_MS:
        return
    last_sw_ms = now

    raw = pin.value()
    if raw == 0 and sw_state == 1:
        # 按下：清零（你也可以改为取反/加步长等）
        sw_state = 0
        sw_press_count += 1
        val = 0
        log(INF, "SW 按下：清零 -> val=0 (press#%d)", sw_press_count)
    elif raw == 1 and sw_state == 0:
        sw_state = 1
        log(DBG, "SW 释放")

# 绑定中断
clk.irq(trigger=Pin.IRQ_FALLING, handler=_clk_irq)
sw.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=_sw_irq)
log(INF, "IRQ 绑定：CLK=%d(下降沿), DT=%d(读电平判向), SW=%d(双沿+去抖)", PIN_CLK, PIN_DT, PIN_SW)

# ========== OLED 绘制 ==========
def draw():
    oled.fill(0)
    oled.text("Rotary Encoder", 0, 0)
    oled.text("VAL:", 0, 16)
    # 大字显示：拼接两行
    s = str(val)
    oled.text(s, 40, 16)
    oled.text("CW/CCW: %d/%d" % (cw_count, ccw_count), 0, 36)
    oled.text("Events: %d" % rot_events, 0, 48)
    oled.text("SW#: %d" % sw_press_count, 80, 48)
    oled.show()

# ========== 主程序 ==========
def main():
    global last_clk_us
    last_clk_us = _now_us()
    log(INF, "==== 旋钮 + OLED 启动 ====")
    draw()

    last_oled = _now_ms()
    last_hb   = _now_ms()

    while True:
        now = _now_ms()

        # 节流刷新 OLED
        if time.ticks_diff(now, last_oled) >= OLED_REFRESH_MS:
            draw()
            last_oled = now

        # 心跳日志
        if time.ticks_diff(now, last_hb) >= HEARTBEAT_MS:
            last_hb = now
            log(INF, "心跳: val=%d, cw/ccw=%d/%d, rot=%d, sw#=%d",
                val, cw_count, ccw_count, rot_events, sw_press_count)

        time.sleep_ms(2)

if __name__ == "__main__":
    main()
