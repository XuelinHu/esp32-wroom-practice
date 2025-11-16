# servo_easy.py
# ESP32 舵机控制（SG90/MG90S）+ 日志输出

import time
from machine import Pin, PWM
from base.log import debug, info, warn

# ======================
# 配置舵机参数
# ======================
SERVO_PIN = 27          # 舵机 PWM 引脚
FREQ = 50               # 舵机固定频率 50Hz
MIN_US = 500            # 0° 脉宽 0.5ms
MAX_US = 2500           # 180° 脉宽 2.5ms

# ESP32 PWM 通道：duty范围 0~1023
PWM_MAX = 1023

# ======================
# 舵机初始化
# ======================
servo = PWM(Pin(SERVO_PIN), freq=FREQ, duty=0)
info("SERVO", "舵机已初始化: pin=%d freq=%dHz", SERVO_PIN, FREQ)

# ======================
# 工具函数：角度转 duty
# ======================
def angle_to_duty(angle):
    angle = max(0, min(180, angle))
    us = MIN_US + (MAX_US - MIN_US) * angle / 180
    duty = int(PWM_MAX * us / 20000)  # 20ms = 20000us
    debug("CALC", "角度=%d° -> us=%d -> duty=%d", angle, us, duty)
    return duty

# ======================
# 设置舵机角度
# ======================
def servo_angle(angle):
    duty = angle_to_duty(angle)
    servo.duty(duty)
    info("SERVO", "设置角度=%d° duty=%d", angle, duty)
    time.sleep_ms(400)  # 舵机需要时间移动

# ======================
# 测试
# ======================
def run():
    info("TEST", "开始舵机自检")
    for a in (0, 90, 180, 90, 0):
        servo_angle(a)
        time.sleep(0.5)
    info("TEST", "自检完成")

if __name__ == "__main__":
    run()
