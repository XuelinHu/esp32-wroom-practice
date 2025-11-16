# buttons_thread_demo.py
# 4 个按键：LED 轮询控制；蜂鸣器 / 呼吸灯 / RGB 通过中断 + 线程执行
# 数码管 TM1637 持续递增显示，并打印部分日志

import time
import random
import neopixel
import math
import _thread
from machine import Pin, PWM
from tm1637 import TM1637
from base.log import debug, info, warn   # 使用 base/log.py 的 d/i/w

# ======================
# 硬件引脚配置
# ======================

# 按键（内部上拉：未按下=1，按下=0）
BTN_LED_PIN    = 25
BTN_BUZZER_PIN = 26
BTN_PWM_PIN    = 27
BTN_RGB_PIN    = 14

btn_led    = Pin(BTN_LED_PIN,    Pin.IN, Pin.PULL_UP)
btn_buzzer = Pin(BTN_BUZZER_PIN, Pin.IN, Pin.PULL_UP)
btn_pwm    = Pin(BTN_PWM_PIN,    Pin.IN, Pin.PULL_UP)
btn_rgb    = Pin(BTN_RGB_PIN,    Pin.IN, Pin.PULL_UP)

# 输出设备
led_pin    = Pin(15, Pin.OUT)
buzzer_pin = Pin(16, Pin.OUT)
pwm_led    = PWM(Pin(4), freq=1000, duty=0)
np         = neopixel.NeoPixel(Pin(17), 1)
tm         = TM1637(clk=Pin(18), dio=Pin(19))

# 按键去抖（仅对中断按键）
BTN_DEBOUNCE_MS = 150
_last_buzzer_ms = 0
_last_pwm_ms    = 0
_last_rgb_ms    = 0

# ======================
# 功能函数（在线程中执行）
# ======================

def buzzer_3sec():
    info("BUZZ", "蜂鸣器开始响 3 秒")
    try:
        buzzer_pwm = PWM(buzzer_pin, freq=1000, duty=512)
        for duty in range(512, 0, -5):
            buzzer_pwm.duty(duty)
            time.sleep_ms(50)
        buzzer_pwm.deinit()
    except Exception as e:
        warn("BUZZ", "执行异常: %r" % e)
    finally:
        buzzer_pin.off()
        info("BUZZ", "蜂鸣器结束")

def breathing_3sec():
    info("PWM", "呼吸灯开始 3 秒")
    start = time.ticks_ms()
    try:
        while time.ticks_diff(time.ticks_ms(), start) < 3000:
            t = time.ticks_ms() / 1000
            duty = int(512 + 512 * math.sin(t * 2 * math.pi))
            pwm_led.duty(max(0, min(1023, duty)))
            time.sleep_ms(10)
    except Exception as e:
        warn("PWM", "执行异常: %r" % e)
    finally:
        pwm_led.duty(0)
        info("PWM", "呼吸灯结束")

def rgb_random_3times():
    info("RGB", "RGB 开始变色 3 次")
    try:
        for _ in range(3):
            r = random.randint(0, 255)
            g = random.randint(0, 255)
            b = random.randint(0, 255)
            np[0] = (r, g, b)
            np.write()
            time.sleep(0.5)
    except Exception as e:
        warn("RGB", "执行异常: %r" % e)
    finally:
        np[0] = (0, 0, 0)
        np.write()
        info("RGB", "RGB 变色结束")

# ======================
# 中断回调（IRQ -> 起线程）
# ======================

# 忙碌标志，防止重复起线程
_flag_buzzer = False
_flag_pwm    = False
_flag_rgb    = False

def _start_thread_safe(flag_name, target):
    """根据标志位安全启动新线程"""
    global _flag_buzzer, _flag_pwm, _flag_rgb

    if flag_name == "buzzer":
        if _flag_buzzer:
            return
        _flag_buzzer = True
    elif flag_name == "pwm":
        if _flag_pwm:
            return
        _flag_pwm = True
    elif flag_name == "rgb":
        if _flag_rgb:
            return
        _flag_rgb = True

    def wrapper():
        try:
            target()
        finally:
            global _flag_buzzer, _flag_pwm, _flag_rgb
            if flag_name == "buzzer":
                _flag_buzzer = False
            elif flag_name == "pwm":
                _flag_pwm = False
            elif flag_name == "rgb":
                _flag_rgb = False
            debug("THREAD", "%s 线程结束，标志位已清零" % flag_name)

    try:
        _thread.start_new_thread(wrapper, ())
        debug("THREAD", "启动 %s 线程" % flag_name)
    except Exception as e:
        warn("THREAD", "启动 %s 线程失败: %r" % (flag_name, e))
        if flag_name == "buzzer":
            _flag_buzzer = False
        elif flag_name == "pwm":
            _flag_pwm = False
        elif flag_name == "rgb":
            _flag_rgb = False

def buzzer_irq(pin):
    global _last_buzzer_ms
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_buzzer_ms) < BTN_DEBOUNCE_MS:
        return
    _last_buzzer_ms = now
    debug("IRQ", "蜂鸣器按键触发")
    _start_thread_safe("buzzer", buzzer_3sec)

def pwm_irq(pin):
    global _last_pwm_ms
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_pwm_ms) < BTN_DEBOUNCE_MS:
        return
    _last_pwm_ms = now
    debug("IRQ", "呼吸灯按键触发")
    _start_thread_safe("pwm", breathing_3sec)

def rgb_irq(pin):
    global _last_rgb_ms
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_rgb_ms) < BTN_DEBOUNCE_MS:
        return
    _last_rgb_ms = now
    debug("IRQ", "RGB 按键触发")
    _start_thread_safe("rgb", rgb_random_3times)

# 绑定中断
btn_buzzer.irq(trigger=Pin.IRQ_FALLING, handler=buzzer_irq)
btn_pwm.irq(trigger=Pin.IRQ_FALLING, handler=pwm_irq)
btn_rgb.irq(trigger=Pin.IRQ_FALLING, handler=rgb_irq)

# ======================
# 初始化状态
# ======================

led_pin.off()
np[0] = (0, 0, 0)
np.write()
tm.number(0)

info("MAIN", "系统启动（中断 + 线程版）")
info("MAIN", "按键：LED=%d, BUZZER=%d, PWM=%d, RGB=%d" %
     (BTN_LED_PIN, BTN_BUZZER_PIN, BTN_PWM_PIN, BTN_RGB_PIN))

# ======================
# 主循环：LED 轮询 + 数码管递增 + 心跳日志
# ======================

def run():
    n = 0
    last_led_state = btn_led.value()
    last_hb = time.ticks_ms()

    while True:
        # LED 按键轮询控制（按下点亮，松开熄灭）
        curr_led_state = btn_led.value()
        if curr_led_state != last_led_state:
            if curr_led_state == 0:
                led_pin.on()
                debug("MAIN", "LED 点亮")
            else:
                led_pin.off()
                debug("MAIN", "LED 熄灭")
            last_led_state = curr_led_state

        # 数码管递增显示（0~9999）
        tm.number(n)
        n = (n + 1) % 10000

        # 每秒打印一次心跳
        now = time.ticks_ms()
        if time.ticks_diff(now, last_hb) >= 1000:
            last_hb = now
            msg = "n=%d buzzer_busy=%d pwm_busy=%d rgb_busy=%d led_btn=%d" % (
                n, _flag_buzzer, _flag_pwm, _flag_rgb, curr_led_state
            )
            info("HB", msg)

        time.sleep_ms(100)


if __name__ == "__main__":
    run()
