import time


def on_boot():
    print("[snic_bee.boot][{}] module init".format(time.ticks_ms()))
    print("[snic_bee.boot][{}] ultrasonic+buzzer profile".format(time.ticks_ms()))
