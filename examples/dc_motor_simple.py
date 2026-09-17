# dc_motor_simple.py
# ESP32 使用 GPIO15 控制直流电机（单方向 + PWM 调速）

from machine import Pin, PWM
import time

# ========= 配置 =========
MOTOR_PIN = 15      # 通过 ULN2003 / MOSFET / L9110 输入 A1 控制
PWM_FREQ = 1000     # 直流电机常用 PWM = 500~2000 Hz
PWM_MAX = 1023      # ESP32 的 PWM 占空比范围

# ========= 初始化 =========
motor = PWM(Pin(MOTOR_PIN), freq=PWM_FREQ, duty=0)
print("MOTOR", "直流电机初始化完成 pin=%d freq=%dHz", MOTOR_PIN, PWM_FREQ)

# ========= 设置电机速度（0~100%） =========
def motor_speed(percent):
    percent = max(0, min(100, percent))
    duty = int(PWM_MAX * percent / 100)
    motor.duty(duty)
    print("MOTOR", "设置速度=%d%% duty=%d", percent, duty)

# ========= 关闭电机 =========
def motor_stop():
    motor.duty(0)
    print("MOTOR", "电机停止")

# ========= 测试程序 =========
def run():
    print("TEST", "直流电机测试开始")

    # 30% 转速
    motor_speed(30)
    time.sleep(2)

    # 60% 转速
    motor_speed(60)
    time.sleep(2)

    # 100% 转速
    motor_speed(100)
    time.sleep(2)

    # 停止
    motor_stop()
    print("TEST", "测试结束")

if __name__ == "__main__":
    run()
