import machine
import time
import random
import neopixel
import math
import _thread
from machine import Pin, PWM
from tm1637 import TM1637

# ======================
# 硬件引脚配置（⚠️ 替换为支持上拉的 GPIO）
# ======================

# 按键（内部上拉：未按下=高电平1，按下=低电平0）
btn_led = Pin(25, Pin.IN, Pin.PULL_UP)
btn_buzzer = Pin(26, Pin.IN, Pin.PULL_UP)
btn_pwm = Pin(27, Pin.IN, Pin.PULL_UP)
btn_rgb = Pin(14, Pin.IN, Pin.PULL_UP)

# 输出设备
led_pin = Pin(15, Pin.OUT)
buzzer_pin = Pin(16, Pin.OUT)
pwm_led = PWM(Pin(4), freq=1000, duty=0)
np = neopixel.NeoPixel(Pin(17), 1)
tm = TM1637(clk=Pin(18), dio=Pin(19))

# ======================
# 功能函数（线程执行）
# ======================

def buzzer_3sec():
    print("[线程] 蜂鸣器开始响3秒")
    buzzer_pwm = PWM(buzzer_pin, freq=1000, duty=512)
    for duty in range(512, 0, -5):
        buzzer_pwm.duty(duty)
        time.sleep_ms(50)
    buzzer_pwm.deinit()
    print("[线程] 蜂鸣器结束")

def breathing_3sec():
    print("[线程] 呼吸灯开始3秒")
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < 3000:
        t = time.ticks_ms() / 1000
        duty = int(512 + 512 * math.sin(t * 2 * math.pi))
        pwm_led.duty(max(0, min(1023, duty)))
        time.sleep_ms(10)
    pwm_led.duty(0)
    print("[线程] 呼吸灯结束")

def rgb_random_3times():
    print("[线程] RGB开始变色3次")
    for _ in range(3):
        r, g, b = random.randint(0,255), random.randint(0,255), random.randint(0,255)
        np[0] = (r, g, b)
        np.write()
        time.sleep(0.5)
    np[0] = (0,0,0)
    np.write()
    print("[线程] RGB变色结束")

# ======================
# 中断回调函数（IRQ触发）
# ======================

# 为防止多次误触发，用忙碌标志位
flag_buzzer = False
flag_pwm = False
flag_rgb = False

def buzzer_irq(pin):
    global flag_buzzer
    if not flag_buzzer:
        flag_buzzer = True
        _thread.start_new_thread(run_buzzer, ())

def pwm_irq(pin):
    global flag_pwm
    if not flag_pwm:
        flag_pwm = True
        _thread.start_new_thread(run_pwm, ())

def rgb_irq(pin):
    global flag_rgb
    if not flag_rgb:
        flag_rgb = True
        _thread.start_new_thread(run_rgb, ())

# 包装线程函数（执行后自动清空标志）
def run_buzzer():
    try:
        buzzer_3sec()
    finally:
        global flag_buzzer
        flag_buzzer = False

def run_pwm():
    try:
        breathing_3sec()
    finally:
        global flag_pwm
        flag_pwm = False

def run_rgb():
    try:
        rgb_random_3times()
    finally:
        global flag_rgb
        flag_rgb = False

# ======================
# IRQ中断绑定
# ======================
btn_buzzer.irq(trigger=Pin.IRQ_FALLING, handler=buzzer_irq)
btn_pwm.irq(trigger=Pin.IRQ_FALLING, handler=pwm_irq)
btn_rgb.irq(trigger=Pin.IRQ_FALLING, handler=rgb_irq)

# LED（非中断，直接轮询即可）
# ======================
# 初始化状态
led_pin.off()
np[0] = (0,0,0)
np.write()
tm.number(0)

# ======================
# 主循环：持续刷新显示 + LED实时响应
# ======================
print("===== 系统启动（中断+线程版） =====")

n = 0
last_led_state = 1

while True:
    # LED按键轮询控制（实时点亮/熄灭）
    curr_led_state = btn_led.value()
    if curr_led_state == 0 and last_led_state == 1:
        led_pin.on()
        print("[主循环] LED点亮")
    elif curr_led_state == 1 and last_led_state == 0:
        led_pin.off()
        print("[主循环] LED熄灭")
    last_led_state = curr_led_state

    # 数码管递增显示（持续刷新，不受阻塞）
    tm.number(n)
    n = (n + 1) % 10000

    # 稍作延迟
    time.sleep_ms(100)
