# pir_sensor.py
# ESP32 + HC-SR501 / SR602 人体红外感应模块
# 输出高电平 = 检测到人体移动

from machine import Pin
import time
from base.log import debug, info, warn

# ======================
# 配置模块
# ======================
PIR_PIN = 32        # 人体感应输出引脚
DEBOUNCE_MS = 200   # 去抖，人体模块本身慢，一般 200ms 足够

# ======================
# 初始化硬件
# ======================
pir = Pin(PIR_PIN, Pin.IN)
_last_ms = 0
_last_state = pir.value()

info("PIR", "人体感应模块已初始化 pin=%d 当前状态=%d", PIR_PIN, _last_state)

# ======================
# 状态变化回调
# ======================
def pir_changed(new_state):
    if new_state == 1:
        info("PIR", "检测到人体移动 (HIGH)")
    else:
        info("PIR", "人体离开，恢复静止 (LOW)")

# ======================
# 主循环：监控 PIR 状态
# ======================
def run():
    global _last_ms, _last_state

    info("PIR", "开始监控人体感应数据...")

    while True:
        now = time.ticks_ms()
        state = pir.value()

        # 状态变化才处理
        if state != _last_state:
            # 去抖判断
            if time.ticks_diff(now, _last_ms) > DEBOUNCE_MS:
                debug("PIR", "状态变化: %d -> %d", _last_state, state)
                _last_state = state
                pir_changed(state)

            _last_ms = now

        time.sleep_ms(50)

# ======================
# 运行本文件时自动启动
# ======================
if __name__ == "__main__":
    run()
