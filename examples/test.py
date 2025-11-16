from machine import Pin
import time

pins = [Pin(25, Pin.IN, Pin.PULL_UP),
        Pin(26, Pin.IN, Pin.PULL_UP),
        Pin(27, Pin.IN, Pin.PULL_UP),
        Pin(14, Pin.IN, Pin.PULL_UP)]

while True:
    print([p.value() for p in pins])
    time.sleep_ms(200)
