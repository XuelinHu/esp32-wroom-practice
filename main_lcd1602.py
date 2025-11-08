# main_lcd_debug.py —— ESP32 + LCD1602(I2C) 调试主程序（带 main）
from machine import I2C, Pin
import time
from i2c_lcd_min import I2cLcd

# -------- 可调参数 --------
I2C_ID_PRIMARY   = 0         # 先试 I2C(0)
I2C_ID_FALLBACK  = 1         # 再试 I2C(1) 作为备选
I2C_FREQ_HZ      = 100000    # 先用 100kHz 稳定跑，OK 后可改 400000
SCL_PIN          = 22
SDA_PIN          = 21
ROW_COUNT        = 2
COL_COUNT        = 16
DEBUG_DRIVER     = True      # 打开驱动内日志
TICK_INTERVAL_MS = 500

def make_i2c():
    """优先 I2C(0)，失败退到 I2C(1)。"""
    try:
        return I2C(I2C_ID_PRIMARY, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=I2C_FREQ_HZ)
    except Exception as e:
        print("[MAIN] I2C(%d) 失败，尝试 I2C(%d):" % (I2C_ID_PRIMARY, I2C_ID_FALLBACK), e)
        return I2C(I2C_ID_FALLBACK, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=I2C_FREQ_HZ)

def raw_backlight_probe(i2c, addr):
    """不依赖驱动，直接写 PCF8574，验证 I2C 通畅和背光极性是否生效。"""
    print("[MAIN] 原始背光探测：高->低->高")
    try:
        i2c.writeto(addr, b'\x08')  # 假设 BL 在 P3 且高有效
        time.sleep_ms(200)
        i2c.writeto(addr, b'\x00')
        time.sleep_ms(200)
        i2c.writeto(addr, b'\x08')
        time.sleep_ms(200)
    except Exception as e:
        print("[MAIN] 原始背光写入异常：", repr(e))

def try_init(i2c, addr, bl_active_high):
    """尝试一种背光极性初始化 LCD。返回 lcd 实例或抛异常。"""
    print("[MAIN] 尝试初始化：bl_active_high =", bl_active_high)
    lcd = I2cLcd(
        i2c, addr, ROW_COUNT, COL_COUNT,
        backlight=True, bl_active_high=bl_active_high, debug=DEBUG_DRIVER
    )
    lcd.clear()
    lcd.putstr("Hello ESP32!")
    lcd.move_to(0,1)
    lcd.putstr("I2C=" + hex(addr))
    return lcd

def main():
    print("[MAIN] ===== LCD1602 (I2C) 调试程序启动 =====")
    i2c = make_i2c()

    # 扫描地址
    addrs = i2c.scan()
    print("[MAIN] scan ->", [hex(a) for a in addrs])
    if not addrs:
        raise RuntimeError("没找到 I2C 设备；检查 VCC/GND/SDA(%d)/SCL(%d) 与上拉电阻电压/地址拨码"
                           % (SDA_PIN, SCL_PIN))
    addr = addrs[0]
    print("[MAIN] 使用地址:", hex(addr))

    # 原始背光探测
    raw_backlight_probe(i2c, addr)

    # 试两种背光极性
    lcd = None
    try:
        lcd = try_init(i2c, addr, bl_active_high=True)
    except Exception as e:
        print("[MAIN] 初始化失败(高有效)：", repr(e))

    if lcd is None:
        try:
            lcd = try_init(i2c, addr, bl_active_high=False)
        except Exception as e:
            print("[MAIN] 初始化失败(低有效)：", repr(e))

    if lcd is None:
        raise RuntimeError("初始化两种背光极性都失败；可能是位图映射不同或电气问题")

    print("[MAIN] 初始化完成，开始周期性写入测试")
    k = 0
    while True:
        try:
            lcd.move_to(0, 0)
            lcd.putstr("Tick:%04d   " % (k % 10000))
            lcd.move_to(0, 1)
            lcd.putstr("Stable test..")
            k += 1
        except Exception as e:
            print("[MAIN] 写入异常：", repr(e))
        time.sleep_ms(TICK_INTERVAL_MS)

if __name__ == "__main__":
    main()
