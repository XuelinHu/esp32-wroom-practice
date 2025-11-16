# 统一的显示抽象：优先用 OLED，如没有可降级为串口输出
from machine import I2C, Pin
from base import log

try:
    from lib import ssd1306  # 明确从 lib 引入驱动
except ImportError:
    ssd1306 = None


class Screen:
    def __init__(self, screen_id=0, scl_pin=18, sda_pin=23, freq=400_000):
        self.ok = False
        if ssd1306:
            try:
                i2c = I2C(screen_id, scl=Pin(scl_pin), sda=Pin(sda_pin), freq=freq)
                self.oled = ssd1306.SSD1306_I2C(128, 64, i2c)
                self.ok = True
                log.info("display", "SSD1306 ready")
            except Exception as e:
                log.warn("display", "SSD1306 init failed:", e)

    def show_lines(self, *lines):
        if self.ok:
            self.oled.fill(0)
            for idx, s in enumerate(lines[:6]):
                self.oled.text(str(s), 0, idx * 10)
            self.oled.show()
        else:
            # 无 OLED 时退化为串口打印
            log.info("display", " | ".join(str(x) for x in lines))


screen = Screen(screen_id=0, scl_pin=18, sda_pin=23, freq=400_000)
