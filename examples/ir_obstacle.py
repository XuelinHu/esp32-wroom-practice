# ir_obstacle.py
# 红外避障模块（TCRT5000 / KY-032） + 日志输出

from machine import Pin
import time
from base.log import debug, info, warn

# ======================
# 配置参数
# ======================
IR_PIN = 32          # 红外避障输出引脚
DEBOUNCE_MS = 50     # 去抖时间（红外模块很快，但反射会抖）

# ======================
# 初始化引脚
# ======================
ir = Pin(IR_PIN, Pin.IN)
_last_state = ir.value()
_last_ms = time.ticks_ms()

info("IR", "红外避障模块初始化完成 pin=%d 当前值=%d", IR_PIN, _last_state)

# ======================
# 状态变化回调
# ======================
def obstacle_changed(state):
    if state == 0:
        info("IR", "检测到障碍物！（LOW）")
    else:
        info("IR", "前方无障碍（HIGH）")

# ======================
# 主循环逻辑
# ======================
def run():
    global _last_state, _last_ms

    info("IR", "开始监控红外避障状态...")

    while True:
        now = time.ticks_ms()
        state = ir.value()

        # 只有状态变化才处理
        if state != _last_state:
            # 做去抖
            if time.ticks_diff(now, _last_ms) > DEBOUNCE_MS:
                debug("IR", "状态变化: %d -> %d", _last_state, state)
                _last_state = state
                obstacle_changed(state)

            _last_ms = now

        time.sleep_ms(20)


# ======================
# 单独运行本文件时自动启动
# ======================
if __name__ == "__main__":
    run()
