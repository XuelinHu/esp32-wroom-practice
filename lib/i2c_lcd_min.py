# i2c_lcd_min.py —— 1602 + PCF8574 (I2C) 调试友好版
# 默认映射：P0=RS, P1=RW, P2=E, P3=BL, P4=D4, P5=D5, P6=D6, P7=D7
from machine import I2C
import time

# LCD 指令
_LCD_CLR      = 0x01
_LCD_HOME     = 0x02
_LCD_ENTRY    = 0x04
_LCD_DISPLAY  = 0x08
_LCD_SHIFT    = 0x10
_LCD_FUNC     = 0x20
_LCD_CGRAM    = 0x40
_LCD_DDRAM    = 0x80
# 子位
_ENTRY_ID     = 0x02
_ENTRY_S      = 0x01
_DISPLAY_ON   = 0x04
_DISPLAY_C    = 0x02
_DISPLAY_B    = 0x01
_FUNC_8BIT    = 0x10
_FUNC_2LINE   = 0x08
_FUNC_5x10    = 0x04

class I2cLcd:
    def __init__(
        self, i2c: I2C, addr: int, rows=2, cols=16,
        backlight=True, bl_active_high=True,  # 有些背包背光位是“低有效”
        debug=False,
        # 允许修改位图（极少数背包映射不同）
        mask_rs=0x01, mask_rw=0x02, mask_en=0x04, mask_bl=0x08,
        d4=0x10, d5=0x20, d6=0x40, d7=0x80
    ):
        self.i2c, self.addr = i2c, addr
        self.rows, self.cols = rows, cols
        self.debug = debug

        # 位图
        self.MASK_RS = mask_rs
        self.MASK_RW = mask_rw
        self.MASK_EN = mask_en
        self.MASK_BL = mask_bl
        self.D4, self.D5, self.D6, self.D7 = d4, d5, d6, d7

        # 背光位有效极性
        self._bl_active_high = bl_active_high
        self._bl_state = bool(backlight)
        self._bl_mask = self.MASK_BL if (self._bl_state == self._bl_active_high) else 0

        self._log("init: addr=0x%02X rows=%d cols=%d backlight=%s bl_active_high=%s",
                  addr, rows, cols, backlight, bl_active_high)

        time.sleep_ms(50)  # 上电等待

        # 试探：直接切几次背光，确认 I2C 是否通
        self._probe_backlight()

        # 进入 4 位模式（HD44780 规定的“三次0x3 + 一次0x2”序列）
        self._write4(self._nibble(0x03)); time.sleep_ms(5)
        self._write4(self._nibble(0x03)); time.sleep_ms(5)
        self._write4(self._nibble(0x03)); time.sleep_ms(2)
        self._write4(self._nibble(0x02))

        # 基本设置
        self._cmd(_LCD_FUNC | _FUNC_2LINE)       # 4位,2行
        self._cmd(_LCD_DISPLAY | _DISPLAY_ON)    # 显示 ON, 光标/闪烁 OFF
        self.clear()
        self._cmd(_LCD_ENTRY | _ENTRY_ID)        # 写入地址自增

    # —— 调试输出 ——
    def _log(self, fmt, *args):
        if self.debug:
            try:
                print("[I2C_LCD]", fmt % args if args else fmt)
            except:
                print("[I2C_LCD]", fmt, args)

    # —— 工具：把高四位结构出来（依背包D4~D7位图）——
    def _nibble(self, val_4bit):
        # val_4bit: 0..15 (0000b..1111b) -> 映射到 D4..D7 的掩码组合
        res = 0
        if val_4bit & 0x01: res |= self.D4
        if val_4bit & 0x02: res |= self.D5
        if val_4bit & 0x04: res |= self.D6
        if val_4bit & 0x08: res |= self.D7
        return res

    def _bl_mask_now(self):
        # 当前背光位应该输出的掩码
        return (self.MASK_BL if (self._bl_state == self._bl_active_high) else 0)

    def _i2c_write_byte(self, b):
        # 低层 I2C 写（带日志）
        self.i2c.writeto(self.addr, bytes([b]))
        self._log("I2C wr: 0x%02X", b)

    def _pulse(self, data_mask):
        # 产生 EN 脉冲（EN↑ 写入，EN↓ 锁存）
        self._i2c_write_byte(data_mask | self.MASK_EN | self._bl_mask_now())
        self._i2c_write_byte(data_mask | self._bl_mask_now())

    def _write4(self, data4_masked, rs=False):
        # 写 4 位（已通过 _nibble() 换算），附带 RS/RW/BL
        base = data4_masked | (self.MASK_RS if rs else 0)  # RW 固定为写(0)
        self._pulse(base)

    def _send8(self, byte, rs):
        # 先高 4 位，再低 4 位
        hi = self._nibble((byte >> 4) & 0x0F)
        lo = self._nibble(byte & 0x0F)
        self._write4(hi, rs=rs)
        self._write4(lo, rs=rs)

    def _cmd(self, cmd):
        self._log("CMD: 0x%02X", cmd)
        self._send8(cmd, rs=False)
        if cmd in (_LCD_CLR, _LCD_HOME):
            time.sleep_ms(2)
        else:
            time.sleep_us(50)

    # —— 公共接口 ——
    def clear(self):
        self._cmd(_LCD_CLR)

    def home(self):
        self._cmd(_LCD_HOME)

    def backlight_on(self):
        self._bl_state = True
        self._i2c_write_byte(self._bl_mask_now())  # 立刻生效一次

    def backlight_off(self):
        self._bl_state = False
        self._i2c_write_byte(self._bl_mask_now())

    def move_to(self, col, row):
        row = max(0, min(self.rows-1, row))
        col = max(0, min(self.cols-1, col))
        addr = col + (0x40 * row)
        self._cmd(_LCD_DDRAM | addr)

    def putchar(self, ch):
        b = ch if isinstance(ch, int) else ord(ch)
        self._log("DAT: 0x%02X (%r)", b, chr(b) if 32 <= b < 127 else '.')
        self._send8(b, rs=True)

    def putstr(self, s):
        for ch in s:
            if ch == '\n':
                self.move_to(0, 1)
            else:
                self.putchar(ch)

    # —— 调试：开机探测背光是否受控（证明 I2C 通畅 & 找到对的地址/极性）——
    def _probe_backlight(self):
        self._log("probe: backlight toggle 3x")
        for i in range(3):
            self._bl_state = True
            self._i2c_write_byte(self._bl_mask_now())
            time.sleep_ms(120)
            self._bl_state = False
            self._i2c_write_byte(self._bl_mask_now())
            time.sleep_ms(120)
        # 还原到用户期望
        self._bl_state = True
        self._i2c_write_byte(self._bl_mask_now())
