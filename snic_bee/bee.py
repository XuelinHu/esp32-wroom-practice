# ====== CONFIG (edit here) ============================================
# Hardware / Pins
# - Ultrasonic sensor (HC-SR04): needs TRIG(OUT) + ECHO(IN)
# - Buzzer: PWM output pin
# - Water-drop sensor: digital input pin (typically "rain drop" / "water leak" board)
ULTRASONIC_TRIG_PIN = 25
ULTRASONIC_ECHO_PIN = 26
BUZZER_PWM_PIN = 13

# Frequency / Density knob
# - One parameter to make both ultrasonic sampling + HTTP upload denser.
# - 100 = baseline, bigger = denser (shorter intervals).
FREQUENCY_MULTIPLIER_PCT = 120

def _scaled_interval_ms(base_ms, min_ms=20):
    # Convert "frequency multiplier" to shorter time intervals.
    # Example: 120% => interval = base * 100 / 120 (~0.83x)
    try:
        scaled = (int(base_ms) * 100) // int(FREQUENCY_MULTIPLIER_PCT)
    except Exception:
        scaled = int(base_ms)
    if scaled < int(min_ms):
        return int(min_ms)
    return int(scaled)

# Ultrasonic / Buzzer behavior
# - Distances in cm: >= MAX means silent; < MIN will be clamped to MIN
ULTRASONIC_MIN_DISTANCE_CM = 5
ULTRASONIC_MAX_DISTANCE_CM = 200
ULTRASONIC_ECHO_TIMEOUT_US = 30000
ULTRASONIC_TIMEOUT_BACKOFF_BASE_MS = 260
ULTRASONIC_TIMEOUT_BACKOFF_MS = _scaled_interval_ms(ULTRASONIC_TIMEOUT_BACKOFF_BASE_MS, min_ms=50)

# - Buzzer mapping (nearer -> higher freq + faster beeps)
BUZZER_FREQ_MIN_HZ = 300
BUZZER_FREQ_MAX_HZ = 900
BUZZER_PERIOD_MAX_BASE_MS = 1400  # far end
BUZZER_PERIOD_MIN_BASE_MS = 700   # near end
BUZZER_PERIOD_MAX_MS = _scaled_interval_ms(BUZZER_PERIOD_MAX_BASE_MS, min_ms=200)
BUZZER_PERIOD_MIN_MS = _scaled_interval_ms(BUZZER_PERIOD_MIN_BASE_MS, min_ms=120)
BUZZER_ALARM_DUTY = 900      # PWM duty (0..1023)

# Water-drop sensor config
WATER_PIN = 27            # GPIO for water-drop detection
WATER_ACTIVE_LEVEL = 0    # 0: active-low (default pull-up), 1: active-high
WATER_DEBOUNCE_MS = 60    # debounce window for edge detection

# WiFi config (STA)
WIFI_SSID = "YOUR_WIFI_SSID_0"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD_0"

WIFI_SSID_1 = "YOUR_WIFI_SSID_1"
WIFI_PASSWORD_1 = "YOUR_WIFI_PASSWORD_1"

WIFI_SSID_2 = "YOUR_WIFI_SSID_2"
WIFI_PASSWORD_2 = "YOUR_WIFI_PASSWORD_2"

# Ordered list of WiFi candidates (will be used for rotation).
WIFI_NETWORKS = [
    (WIFI_SSID, WIFI_PASSWORD),
    (WIFI_SSID_1, WIFI_PASSWORD_1),
    (WIFI_SSID_2, WIFI_PASSWORD_2),
]

# WiFi connection strategy:
# - Connect in order: WIFI_SSID -> WIFI_SSID_1 -> WIFI_SSID_2
# - Each SSID: retry WIFI_CONNECT_RETRY_COUNT times with logs
# - All failed: wait WIFI_ROTATE_BACKOFF_S seconds and start from first again
WIFI_CONNECT_TIMEOUT_S = 20
WIFI_CONNECT_RETRY_COUNT = 3
WIFI_ROTATE_BACKOFF_S = 5

# Upload server config (fixed IP server)
SERVER_IP = "192.168.1.100"
SERVER_PORT = 8080
SERVER_PATH = "/upload"
UPLOAD_INTERVAL_BASE_MS = 1000
UPLOAD_INTERVAL_MS = _scaled_interval_ms(UPLOAD_INTERVAL_BASE_MS, min_ms=100)  # periodic telemetry interval (ms)

# Optional: device label shown in payload
DEVICE_NAME = "snic_bee"

# Optional local-only secrets override (recommended: keep credentials out of git).
# Create `snic_bee/secrets.py` to override any of:
# - WIFI_NETWORKS, SERVER_IP, SERVER_PORT, SERVER_PATH, DEVICE_NAME ...
_secrets = None
try:
    import snic_bee.secrets as _secrets  # type: ignore
except Exception:
    try:
        import secrets as _secrets  # type: ignore
    except Exception:
        _secrets = None

if _secrets is not None:
    if hasattr(_secrets, "WIFI_NETWORKS"):
        WIFI_NETWORKS = getattr(_secrets, "WIFI_NETWORKS")
    if hasattr(_secrets, "SERVER_IP"):
        SERVER_IP = getattr(_secrets, "SERVER_IP")
    if hasattr(_secrets, "SERVER_PORT"):
        SERVER_PORT = getattr(_secrets, "SERVER_PORT")
    if hasattr(_secrets, "SERVER_PATH"):
        SERVER_PATH = getattr(_secrets, "SERVER_PATH")
    if hasattr(_secrets, "DEVICE_NAME"):
        DEVICE_NAME = getattr(_secrets, "DEVICE_NAME")
# ======================================================================

from machine import Pin, PWM
import time

import machine

try:
    import ubinascii as binascii
except Exception:
    import binascii  # type: ignore

try:
    from snic_bee.uploader import HTTPUploader, utc_ms_fallback
    from snic_bee.wifi_sta import WiFiStation
except Exception:
    from uploader import HTTPUploader, utc_ms_fallback  # type: ignore
    from wifi_sta import WiFiStation  # type: ignore


class SonicBuzzerSystem:
    """Use ultrasonic distance to control buzzer speed/frequency."""

    def __init__(self, trig_pin=ULTRASONIC_TRIG_PIN, echo_pin=ULTRASONIC_ECHO_PIN, buzzer_pin=BUZZER_PWM_PIN):
        self.trig = Pin(trig_pin, Pin.OUT)
        self.echo = Pin(echo_pin, Pin.IN)
        self.buzzer = PWM(Pin(buzzer_pin, Pin.OUT), freq=1000, duty=0)

        # Range and timing config (cm / ms)
        self.min_distance = ULTRASONIC_MIN_DISTANCE_CM
        self.max_distance = ULTRASONIC_MAX_DISTANCE_CM  # Safety distance: 2 meters
        # Lower probe rate to improve stability on noisy setups.
        self.loop_delay_ms = 180
        self.timeout_backoff_ms = ULTRASONIC_TIMEOUT_BACKOFF_MS
        self.timeout_count = 0
        self.alarm_duty = BUZZER_ALARM_DUTY  # Louder alarm (0..1023)
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

        timeout_us = ULTRASONIC_ECHO_TIMEOUT_US

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
        freq_span = BUZZER_FREQ_MAX_HZ - BUZZER_FREQ_MIN_HZ
        period_span = BUZZER_PERIOD_MAX_MS - BUZZER_PERIOD_MIN_MS
        freq_hz = int(BUZZER_FREQ_MIN_HZ + ratio * freq_span)            # min..max Hz
        period_ms = int(BUZZER_PERIOD_MAX_MS - ratio * period_span)      # max..min ms
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
            return d

        freq_hz, period_ms, on_ms = mapped

        self.buzzer.freq(freq_hz)
        self.buzzer.duty(self.alarm_duty)
        time.sleep_ms(on_ms)
        self.buzzer.duty(0)

        off_ms = max(0, period_ms - on_ms)
        if off_ms:
            time.sleep_ms(off_ms)

        self.log("distance: {:.1f} cm, freq: {} Hz, period: {} ms".format(d, freq_hz, period_ms))
        return d

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


class WaterDropSensor:
    def __init__(self, pin, active_level=0, debounce_ms=60, pull=Pin.PULL_UP, log_prefix="[snic_bee.water]"):
        self.pin_no = int(pin)
        self.active_level = 1 if active_level else 0
        self.debounce_ms = int(debounce_ms)
        self.log_prefix = log_prefix

        self._pin = Pin(self.pin_no, Pin.IN, pull)
        self._last_raw = self._pin.value()
        self._stable = self._last_raw
        self._last_raw_change_ms = time.ticks_ms()
        self._active = self._stable == self.active_level

        self._log("init ok, GPIO{} active_level={}".format(self.pin_no, self.active_level))

    def _log(self, msg):
        print("{} {}".format(self.log_prefix, msg))

    def is_active(self):
        return self._stable == self.active_level

    def poll(self):
        """Return True only when a new 'active' edge is detected (debounced)."""
        now = time.ticks_ms()
        raw = self._pin.value()

        if raw != self._last_raw:
            self._last_raw = raw
            self._last_raw_change_ms = now

        if time.ticks_diff(now, self._last_raw_change_ms) < self.debounce_ms:
            return False

        if raw == self._stable:
            return False

        # Stable change confirmed
        self._stable = raw
        now_active = self._stable == self.active_level
        triggered = now_active and not self._active
        self._active = now_active
        if triggered:
            self._log("water drop detected (GPIO{}={})".format(self.pin_no, self._stable))
        return triggered


def _device_id_hex():
    try:
        raw = machine.unique_id()
        return binascii.hexlify(raw).decode()
    except Exception:
        return "unknown"


class SnicBeeTelemetryApp:
    def __init__(self):
        self.device_id = _device_id_hex()
        self.system = SonicBuzzerSystem()
        self.water = WaterDropSensor(
            pin=WATER_PIN,
            active_level=WATER_ACTIVE_LEVEL,
            debounce_ms=WATER_DEBOUNCE_MS,
        )

        # WiFiStation instance will be created when connecting (to support SSID rotation).
        first_ssid, first_password = ("", "")
        try:
            if WIFI_NETWORKS and WIFI_NETWORKS[0]:
                first_ssid, first_password = WIFI_NETWORKS[0]
        except Exception:
            pass

        self.wifi = WiFiStation(first_ssid, first_password, timeout_s=WIFI_CONNECT_TIMEOUT_S, retry_count=1)
        self.uploader = HTTPUploader(SERVER_IP, SERVER_PORT, path=SERVER_PATH, timeout_s=3)

        self._last_upload_ms = 0
        self._last_wifi_check_ms = 0

    def _payload_base(self):
        return {
            "device": DEVICE_NAME,
            "device_id": self.device_id,
            "ts_ms": utc_ms_fallback(),
            "uptime_ms": time.ticks_ms(),
        }

    def _ensure_wifi(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_wifi_check_ms) < 5000:
            return self.wifi.is_connected()
        self._last_wifi_check_ms = now

        if self.wifi.is_connected():
            return True

        self.system.log("wifi disconnected, reconnecting...")
        try:
            if self.wifi.reconnect():
                return True
        except Exception as e:
            self.system.log("wifi reconnect exception: {}".format(e))

        # If reconnect fails, rotate across the configured SSIDs in order.
        return self.connect_wifi_in_order()

    def _upload(self, payload):
        if not self._ensure_wifi():
            return False
        return self.uploader.post_json(payload)

    def connect_wifi_in_order(self):
        try:
            networks = list(WIFI_NETWORKS)
        except Exception:
            networks = []

        for idx, (ssid, password) in enumerate(networks, 1):
            if not ssid:
                continue

            self.system.log("wifi try {}/{} ssid={}".format(idx, len(networks), ssid))
            wifi = WiFiStation(
                ssid,
                password,
                timeout_s=WIFI_CONNECT_TIMEOUT_S,
                retry_count=WIFI_CONNECT_RETRY_COUNT,
            )
            ok = wifi.connect()
            if ok:
                self.wifi = wifi
                return True

        self.system.log("wifi all candidates failed")
        return False


def main():
    app = SnicBeeTelemetryApp()
    try:
        app.system.log("telemetry app start")

        # First WiFi connect (blocking) - upload only after WiFi is ready.
        app.system.log("wifi connecting...")
        while not app.connect_wifi_in_order():
            app.system.log("wifi connect failed, retry all in {}s".format(WIFI_ROTATE_BACKOFF_S))
            time.sleep(WIFI_ROTATE_BACKOFF_S)

        app.system.startup_self_test()

        while True:
            distance_cm = app.system.step()
            water_event = app.water.poll()
            now = time.ticks_ms()

            # Water event: upload immediately
            if water_event:
                payload = app._payload_base()
                payload.update(
                    {
                        "type": "event",
                        "event": "water_drop",
                        "water_active": 1 if app.water.is_active() else 0,
                        "distance_cm": None if distance_cm is None else round(distance_cm, 1),
                    }
                )
                app._upload(payload)

            # Periodic telemetry
            if time.ticks_diff(now, app._last_upload_ms) >= UPLOAD_INTERVAL_MS:
                app._last_upload_ms = now
                payload = app._payload_base()
                payload.update(
                    {
                        "type": "telemetry",
                        "distance_cm": None if distance_cm is None else round(distance_cm, 1),
                        "water_active": 1 if app.water.is_active() else 0,
                        "wifi_ip": app.wifi.get_ip(),
                    }
                )
                app._upload(payload)
    except KeyboardInterrupt:
        print("[snic_bee] stopped by user")


if __name__ == "__main__":
    main()
