from machine import Pin, PWM
import time


class SonicBuzzerSystem:
    """Use ultrasonic distance to control buzzer speed/frequency."""

    def __init__(self, trig_pin=25, echo_pin=26, buzzer_pin=13):
        self.trig = Pin(trig_pin, Pin.OUT)
        self.echo = Pin(echo_pin, Pin.IN)
        self.buzzer = PWM(Pin(buzzer_pin, Pin.OUT), freq=1000, duty=0)

        # Range and timing config (cm / ms)
        self.min_distance = 5
        self.max_distance = 200  # Safety distance: 2 meters
        # Lower probe rate to improve stability on noisy setups.
        self.loop_delay_ms = 180
        self.timeout_backoff_ms = 260
        self.timeout_count = 0
        self.alarm_duty = 900  # Louder alarm (0..1023)
        self.timeout_log_every = 10

        self.log("init ok")
        self.log("pins: TRIG=GPIO{}, ECHO=GPIO{}, BUZZER=GPIO{}".format(trig_pin, echo_pin, buzzer_pin))
        self.log(
            "rules: alarm within {}cm, nearer -> faster, >= {}cm -> silent".format(
                self.max_distance, self.max_distance
            )
        )

    def log(self, msg):
        print("[snic_bee][{}] {}".format(time.ticks_ms(), msg))

    def close_buzzer(self):
        self.buzzer.duty(0)

    def startup_self_test(self):
        """Power-on self test: 3 short beeps when init is normal."""
        self.log("self-test start")
        try:
            self.buzzer.freq(1000)
            for i in range(3):
                self.buzzer.duty(self.alarm_duty)
                time.sleep_ms(120)
                self.buzzer.duty(0)
                time.sleep_ms(120)
                self.log("self-test beep {}/3".format(i + 1))
            self.log("self-test pass")
        except Exception as e:
            self.close_buzzer()
            self.log("self-test fail: {}".format(e))
            raise

    def measure_distance_cm(self):
        """Measure distance by HC-SR04. Return None when timeout."""
        self.trig.value(0)
        time.sleep_us(2)
        self.trig.value(1)
        time.sleep_us(10)
        self.trig.value(0)

        timeout_us = 30000

        start_wait = time.ticks_us()
        while self.echo.value() == 0:
            if time.ticks_diff(time.ticks_us(), start_wait) > timeout_us:
                self.timeout_count += 1
                if self.timeout_count % self.timeout_log_every == 0:
                    self.log("echo wait timeout #{}".format(self.timeout_count))
                return None
        pulse_start = time.ticks_us()

        while self.echo.value() == 1:
            if time.ticks_diff(time.ticks_us(), pulse_start) > timeout_us:
                self.timeout_count += 1
                if self.timeout_count % self.timeout_log_every == 0:
                    self.log("echo high timeout #{}".format(self.timeout_count))
                return None
        pulse_end = time.ticks_us()

        pulse_width = time.ticks_diff(pulse_end, pulse_start)
        distance = (pulse_width * 0.0343) / 2
        return distance

    def _map_distance(self, d):
        """Map distance to buzzer behavior.

        Nearer object -> higher tone + faster beep.
        Farther object -> lower tone + slower beep.
        Too far/invalid -> silent.
        """
        if d is None or d >= self.max_distance:
            return None

        if d < self.min_distance:
            d = self.min_distance

        span = self.max_distance - self.min_distance
        ratio = (self.max_distance - d) / span  # 0.0 far ... 1.0 near

        # Keep frequency/speed capped to avoid constant harsh beeping.
        freq_hz = int(300 + ratio * 600)      # 300..900 Hz
        period_ms = int(1400 - ratio * 700)   # 1400..700 ms
        on_ms = max(40, period_ms // 3)
        return freq_hz, period_ms, on_ms

    def step(self):
        d = self.measure_distance_cm()
        mapped = self._map_distance(d)

        if mapped is None:
            self.close_buzzer()
            if d is None:
                self.log("distance: timeout, buzzer: off")
            else:
                self.log("distance: {:.1f} cm, buzzer: off".format(d))
            time.sleep_ms(self.timeout_backoff_ms)
            return

        freq_hz, period_ms, on_ms = mapped

        self.buzzer.freq(freq_hz)
        self.buzzer.duty(self.alarm_duty)
        time.sleep_ms(on_ms)
        self.buzzer.duty(0)

        off_ms = max(0, period_ms - on_ms)
        if off_ms:
            time.sleep_ms(off_ms)

        self.log("distance: {:.1f} cm, freq: {} Hz, period: {} ms".format(d, freq_hz, period_ms))

    def run(self):
        self.log("run start, Ctrl+C to stop.")
        try:
            while True:
                self.step()
        except KeyboardInterrupt:
            self.log("stopped by user")
        finally:
            self.close_buzzer()
            self.log("buzzer off")


def main():
    system = SonicBuzzerSystem()
    system.startup_self_test()
    system.run()


if __name__ == "__main__":
    main()

