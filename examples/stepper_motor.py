# stepper_keys_angles.py
# ESP32 + 28BYJ-48(ULN2003) + 4键非阻塞控制

import time
import micropython
from machine import Pin
from base.log import debug, info, warn   # 使用你的新日志函数

micropython.alloc_emergency_exception_buf(128)

# ========== 配置区域 ==========
MOTOR_PINS = (15, 2, 0, 4)  # ULN2003 IN1-IN4
KEY_PINS = (32, 33, 12, 13)

DEBOUNCE_MS = 40

STEPS_PER_REV = 4096
STEP_DELAY_US = 1200
RELEASE_WHEN_IDLE = True
DIR_INVERT = False

ANGLE_MAP = {1:+90, 2:+180, 3:-90, 4:+360}

HALFSTEP_SEQ = (
    (1,0,0,0),
    (1,1,0,0),
    (0,1,0,0),
    (0,1,1,0),
    (0,0,1,0),
    (0,0,1,1),
    (0,0,0,1),
    (1,0,0,1),
)

# ========== 硬件初始化 ==========
in_pins = [Pin(p, Pin.OUT, value=0) for p in MOTOR_PINS]
keys    = [Pin(p, Pin.IN, Pin.PULL_UP) for p in KEY_PINS]

# ========== 运行状态 ==========
seq_idx = 0
steps_remaining = 0
last_step_us = 0
_last_k_ms = [0,0,0,0]
_pending =   [0,0,0,0]

# ========== 步进电机基本操作 ==========
def _write(a,b,c,d):
    debug("COIL", "写线圈 = %s", (a,b,c,d))
    in_pins[0].value(a)
    in_pins[1].value(b)
    in_pins[2].value(c)
    in_pins[3].value(d)

def _release():
    debug("COIL", "释放全部线圈")
    _write(0,0,0,0)

def angle_to_steps(deg):
    s = int(deg * STEPS_PER_REV / 360)
    debug("CALC", "角度 %d° -> 计算步数=%d", deg, s)
    return -s if DIR_INVERT else s

def enqueue(steps):
    global steps_remaining
    steps_remaining += steps
    info("QUEUE", "加入任务 %+d 步 -> 当前剩余 %+d", steps, steps_remaining)
    debug("QUEUE", "steps_remaining=%d", steps_remaining)

def step_once(direction):
    global seq_idx
    seq_idx = (seq_idx + (1 if direction > 0 else -1)) & 7
    debug("STEP", "步进: direction=%+d seq_idx=%d", direction, seq_idx)
    _write(*HALFSTEP_SEQ[seq_idx])


# ========== Soft Handler（软件中断） ==========
def _process_soft(i):
    debug("SOFT", "进入 soft handler: K%d", i+1)

    _pending[i] = 0
    now = time.ticks_ms()

    if time.ticks_diff(now, _last_k_ms[i]) < DEBOUNCE_MS:
        debug("SOFT", "K%d soft 去抖丢弃", i+1)
        return

    _last_k_ms[i] = now

    key_val = keys[i].value()
    debug("SOFT", "K%d 软处理中读取 key value=%d", i+1, key_val)

    if key_val == 0:
        deg = ANGLE_MAP[i+1]
        debug("KEY", "K%d 按下 -> 目标角度 %+d°", i+1, deg)
        enqueue(angle_to_steps(deg))


# ========== IRQ Handler（硬件中断） ==========
def _mk_irq(i):
    def irq(pin):
        debug("IRQ", "IRQ 触发: K%d (pin value=%d)", i+1, pin.value())

        now = time.ticks_ms()
        # if time.ticks_diff(now, _last_k_ms[i]) < DEBOUNCE_MS:
        #     debug("IRQ", "K%d IRQ 去抖丢弃", i+1)
        #     return
        #
        # _last_k_ms[i] = now

        if not _pending[i]:
            _pending[i] = 1
            debug("IRQ", "K%d schedule soft handler", i+1)
            try:
                micropython.schedule(lambda _: _process_soft(i), 0)
            except Exception as e:
                warn("IRQ", "schedule 失败: %s，主循环将兜底", e)
    return irq

def bind_irqs():
    for i, kp in enumerate(keys):
        kp.irq(trigger=Pin.IRQ_FALLING, handler=_mk_irq(i))
    info("IRQ", "4 个按键 IRQ 已绑定: %s", KEY_PINS)


# ========== 步进电机自检 ==========
def self_test():
    info("TEST", "自检：正转 32 半步")
    for _ in range(320):
        step_once(1)
        time.sleep_us(max(STEP_DELAY_US, 800))

    _release()
    time.sleep_ms(200)

    info("TEST", "自检：反转 32 半步")
    for _ in range(320):
        step_once(-1)
        time.sleep_us(max(STEP_DELAY_US, 800))

    if RELEASE_WHEN_IDLE:
        _release()

    info("TEST", "自检完成")


# ========== 主运行循环 ==========
def run():
    global last_step_us, steps_remaining

    info("BOOT", "==== 程序启动 ====")
    info("CFG", "IN=%s KEY=%s HALF=%d DELAY=%dus DIR_INV=%s",
         MOTOR_PINS, KEY_PINS, STEPS_PER_REV, STEP_DELAY_US, DIR_INVERT)

    bind_irqs()
    self_test()
    _release()

    last_hb = time.ticks_ms()

    while True:
        # 如果 schedule 忙，兜底处理 pending
        for i2 in range(4):
            if _pending[i2]:
                debug("MAIN", "兜底处理 pending: K%d", i2+1)
                _process_soft(i2)

        # 步进任务调度
        if steps_remaining != 0:
            now_us = time.ticks_us()

            if time.ticks_diff(now_us, last_step_us) >= STEP_DELAY_US:
                last_step_us = now_us
                direction = 1 if steps_remaining > 0 else -1

                debug("MAIN", "开始步进: 剩余=%d direction=%+d",
                      steps_remaining, direction)

                step_once(direction)
                steps_remaining -= direction

                debug("MAIN", "步进后剩余=%d", steps_remaining)

                if steps_remaining == 0 and RELEASE_WHEN_IDLE:
                    _release()
                    debug("MOTOR", "到位 -> 断电线圈")
        else:
            time.sleep_ms(2)

        # 心跳日志
        if time.ticks_diff(time.ticks_ms(), last_hb) >= 1000:
            last_hb = time.ticks_ms()
            ks = "".join(str(k.value()) for k in keys)
            info("HB", "rem=%+d idx=%d keys=%s", steps_remaining, seq_idx, ks)


if __name__ == "__main__":
    run()
