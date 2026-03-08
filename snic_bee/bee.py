# ====== 配置区（主要改这里） ============================================
# 硬件引脚
# - 超声波传感器 HC-SR04：需要 TRIG(输出) 和 ECHO(输入)
# - 蜂鸣器：PWM 输出引脚
# - 水滴/漏水传感器：数字输入引脚
ULTRASONIC_TRIG_PIN = 25
ULTRASONIC_ECHO_PIN = 26
BUZZER_PWM_PIN = 13

# 功能开关
# - 关闭不需要的功能，可以直接减少传感器轮询、蜂鸣器驱动和事件处理带来的 CPU 占用
ENABLE_DISTANCE_SENSOR = True
ENABLE_WATER_SENSOR = False

# WiFi/HTTP 上传开关（默认不上传）
# - 默认不会连接 WiFi / 不会 HTTP 上传
# - 如需上传：设 `ENABLE_UPLOAD_WIFI=True` 或在启动时确认
ENABLE_UPLOAD_WIFI = False
UPLOAD_CONFIRM_ON_BOOT = True
UPLOAD_CONFIRM_TIMEOUT_S = 8

# WiFi auto-connect on boot (upload can still stay disabled).
# This is for quickly verifying "联网成功" via WiFi logs (IP/RSSI/status).
ENABLE_WIFI_ON_BOOT = True

# 开机蜂鸣（默认三声）
ENABLE_BOOT_BEEP = True
BOOT_BEEP_COUNT = 3
BOOT_BEEP_FREQ_HZ = 1000
BOOT_BEEP_ON_MS = 120
BOOT_BEEP_OFF_MS = 120

# 运行频率倍率
# - 同时影响超声波测距节奏和 HTTP 上传节奏
# - 100 = 基准频率；越大越密集、CPU/Wi‑Fi 更忙、发热更高
# - 为了长期运行更稳，默认改为 70，整体降载
FREQUENCY_MULTIPLIER_PCT = 70

def _scaled_interval_ms(base_ms, min_ms=20):
    # 将“频率倍率”换算成实际时间间隔。
    # 例如 120% => 间隔变短；70% => 间隔变长。
    try:
        scaled = (int(base_ms) * 100) // int(FREQUENCY_MULTIPLIER_PCT)
    except Exception:
        scaled = int(base_ms)
    if scaled < int(min_ms):
        return int(min_ms)
    return int(scaled)

# 超声波 / 蜂鸣器参数
# - 单位 cm：距离 >= MAX 时静音；距离 < MIN 时按 MIN 计算
ULTRASONIC_MIN_DISTANCE_CM = 5
ULTRASONIC_MAX_DISTANCE_CM = 200
ULTRASONIC_ECHO_TIMEOUT_US = 30000
ULTRASONIC_TIMEOUT_BACKOFF_BASE_MS = 260
ULTRASONIC_TIMEOUT_BACKOFF_MS = _scaled_interval_ms(ULTRASONIC_TIMEOUT_BACKOFF_BASE_MS, min_ms=120)

# - 蜂鸣器映射：越近 -> 频率越高、鸣叫越快
# - 为降低发热，限制最高频率和占空比，避免长时间高功率驱动
BUZZER_FREQ_MIN_HZ = 280
BUZZER_FREQ_MAX_HZ = 700
BUZZER_PERIOD_MAX_BASE_MS = 1800  # 远距离时更稀疏
BUZZER_PERIOD_MIN_BASE_MS = 900   # 近距离时也不要过快
BUZZER_PERIOD_MAX_MS = _scaled_interval_ms(BUZZER_PERIOD_MAX_BASE_MS, min_ms=350)
BUZZER_PERIOD_MIN_MS = _scaled_interval_ms(BUZZER_PERIOD_MIN_BASE_MS, min_ms=220)
BUZZER_ALARM_DUTY = 420      # PWM 占空比 (0..1023)，越大越响也越热

# 水滴传感器参数
WATER_PIN = 27            # 水滴检测 GPIO
WATER_ACTIVE_LEVEL = 0    # 0: 低电平触发（默认上拉）；1: 高电平触发
WATER_DEBOUNCE_MS = 80    # 去抖时间，避免抖动误报

# Wi‑Fi 配置（STA 模式）
WIFI_SSID = "YOUR_WIFI_SSID_0"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD_0"

WIFI_SSID_1 = "YOUR_WIFI_SSID_1"
WIFI_PASSWORD_1 = "YOUR_WIFI_PASSWORD_1"

WIFI_SSID_2 = "YOUR_WIFI_SSID_2"
WIFI_PASSWORD_2 = "YOUR_WIFI_PASSWORD_2"

# Wi‑Fi 候选列表，按顺序轮询连接
WIFI_NETWORKS = [
    (WIFI_SSID, WIFI_PASSWORD),
    (WIFI_SSID_1, WIFI_PASSWORD_1),
    (WIFI_SSID_2, WIFI_PASSWORD_2),
]

# Wi‑Fi 连接策略
# - 按列表顺序依次连接
# - 每个 SSID 重试若干次
# - 全部失败后等待一段时间再从头开始
WIFI_CONNECT_TIMEOUT_S = 20
WIFI_CONNECT_RETRY_COUNT = 3
WIFI_ROTATE_BACKOFF_S = 8

# 上传服务器参数（固定 IP）
SERVER_IP = "192.168.1.100"
SERVER_PORT = 8080
SERVER_PATH = "/upload"
UPLOAD_INTERVAL_BASE_MS = 3000
UPLOAD_INTERVAL_MS = _scaled_interval_ms(UPLOAD_INTERVAL_BASE_MS, min_ms=800)  # 周期遥测上传间隔（ms）

# 设备名：会上报到服务端
DEVICE_NAME = "snic_bee"

# 可选的本地私有配置覆盖（建议把账号密码放在 secrets.py）
# 可覆盖：WIFI_NETWORKS、SERVER_IP、SERVER_PORT、SERVER_PATH、DEVICE_NAME 等
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
    """使用超声波距离控制蜂鸣器频率和节奏。"""

    def __init__(self, trig_pin=ULTRASONIC_TRIG_PIN, echo_pin=ULTRASONIC_ECHO_PIN, buzzer_pin=BUZZER_PWM_PIN):
        self.trig = Pin(trig_pin, Pin.OUT)
        self.echo = Pin(echo_pin, Pin.IN)
        self.buzzer = PWM(Pin(buzzer_pin, Pin.OUT), freq=1000, duty=0)

        # 核心运行参数
        self.min_distance = ULTRASONIC_MIN_DISTANCE_CM
        self.max_distance = ULTRASONIC_MAX_DISTANCE_CM  # 安全检测上限，单位 cm
        self.loop_delay_ms = 250  # 预留给空闲节流，数值越大越省电
        self.timeout_backoff_ms = ULTRASONIC_TIMEOUT_BACKOFF_MS
        self.timeout_count = 0
        self.alarm_duty = BUZZER_ALARM_DUTY  # 蜂鸣器驱动强度，长期运行不宜过高
        self.timeout_log_every = 20          # 减少超时日志，避免串口刷屏占用 CPU
        self._last_off_log_ms = 0

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
        """通过 HC-SR04 测距，超时返回 None。"""
        self.trig.value(0)
        time.sleep_us(2)
        self.trig.value(1)
        time.sleep_us(10)
        self.trig.value(0)

        timeout_us = ULTRASONIC_ECHO_TIMEOUT_US

        start_wait = time.ticks_us()
        while self.echo.value() == 0:
            machine.idle()
            if time.ticks_diff(time.ticks_us(), start_wait) > timeout_us:
                self.timeout_count += 1
                if self.timeout_count % self.timeout_log_every == 0:
                    self.log("echo wait timeout #{}".format(self.timeout_count))
                return None
        pulse_start = time.ticks_us()

        while self.echo.value() == 1:
            machine.idle()
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
        """将距离映射为蜂鸣器行为。

        越近：音调更高、节奏更快
        越远：音调更低、节奏更慢
        太远或测距失败：静音
        """
        if d is None or d >= self.max_distance:
            return None

        if d < self.min_distance:
            d = self.min_distance

        span = self.max_distance - self.min_distance
        ratio = (self.max_distance - d) / span  # 0.0 far ... 1.0 near

        # 限制最高频率和最短周期，降低持续高负载和刺耳鸣叫。
        freq_span = BUZZER_FREQ_MAX_HZ - BUZZER_FREQ_MIN_HZ
        period_span = BUZZER_PERIOD_MAX_MS - BUZZER_PERIOD_MIN_MS
        freq_hz = int(BUZZER_FREQ_MIN_HZ + ratio * freq_span)
        period_ms = int(BUZZER_PERIOD_MAX_MS - ratio * period_span)
        on_ms = max(30, period_ms // 4)
        return freq_hz, period_ms, on_ms

    def step(self):
        d = self.measure_distance_cm()
        mapped = self._map_distance(d)

        if mapped is None:
            self.close_buzzer()
            now = time.ticks_ms()
            # 静音状态下只做限频日志，避免一直刷串口导致额外负载。
            if time.ticks_diff(now, self._last_off_log_ms) >= 3000:
                if d is None:
                    self.log("distance: timeout, buzzer: off")
                else:
                    self.log("distance: {:.1f} cm, buzzer: off".format(d))
                self._last_off_log_ms = now
            time.sleep_ms(max(self.timeout_backoff_ms, self.loop_delay_ms))
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
    """水滴/漏水数字传感器，带简单去抖。"""

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

        # 已确认状态稳定变化
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
        self.system = SonicBuzzerSystem() if ENABLE_DISTANCE_SENSOR else None
        self.water = (
            WaterDropSensor(
                pin=WATER_PIN,
                active_level=WATER_ACTIVE_LEVEL,
                debounce_ms=WATER_DEBOUNCE_MS,
            )
            if ENABLE_WATER_SENSOR
            else None
        )

        # Wi‑Fi 实例会在真正连接时创建，便于多 SSID 轮询切换。
        first_ssid, first_password = ("", "")
        try:
            if WIFI_NETWORKS and WIFI_NETWORKS[0]:
                first_ssid, first_password = WIFI_NETWORKS[0]
        except Exception:
            pass

        self.wifi = WiFiStation(first_ssid, first_password, timeout_s=WIFI_CONNECT_TIMEOUT_S, retry_count=1)
        self.uploader = HTTPUploader(SERVER_IP, SERVER_PORT, path=SERVER_PATH, timeout_s=3)
        self.upload_enabled = bool(ENABLE_UPLOAD_WIFI)

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
        # 不要每次上传都检查 Wi‑Fi，降低网络栈抖动和额外功耗。
        if time.ticks_diff(now, self._last_wifi_check_ms) < 15000:
            return self.wifi.is_connected()
        self._last_wifi_check_ms = now

        if self.wifi.is_connected():
            return True

        self.log("wifi disconnected, reconnecting...")
        try:
            if self.wifi.reconnect():
                return True
        except Exception as e:
            self.log("wifi reconnect exception: {}".format(e))

        # If reconnect fails, rotate across the configured SSIDs in order.
        return self.connect_wifi_in_order()

    def _upload(self, payload):
        if not getattr(self, "upload_enabled", False):
            return False
        if not self._ensure_wifi():
            try:
                self.log(
                    "upload skip: wifi not ready type={} distance_cm={}".format(
                        payload.get("type", "unknown"),
                        payload.get("distance_cm", None),
                    )
                )
            except Exception:
                pass
            return False
        ok = self.uploader.post_json(payload)
        try:
            self.log(
                "upload {}: type={} distance_cm={} water_active={} wifi_ip={}".format(
                    "ok" if ok else "failed",
                    payload.get("type", "unknown"),
                    payload.get("distance_cm", None),
                    payload.get("water_active", None),
                    self.wifi.get_ip(),
                )
            )
        except Exception:
            pass
        return ok

    def connect_wifi_in_order(self):
        try:
            networks = list(WIFI_NETWORKS)
        except Exception:
            networks = []

        for idx, (ssid, password) in enumerate(networks, 1):
            if not ssid:
                continue

            self.log("wifi try {}/{} ssid={}".format(idx, len(networks), ssid))
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

        self.log("wifi all candidates failed")
        return False

    def log(self, msg):
        if self.system is not None:
            self.system.log(msg)
        else:
            print("[snic_bee][{}] {}".format(time.ticks_ms(), msg))


def _confirm_enable_upload(timeout_s=8):
    """Wait for user confirmation on REPL; default is disabled."""
    try:
        import sys

        try:
            import uselect  # type: ignore
        except Exception:
            uselect = None  # type: ignore

        if uselect is not None:
            poller = uselect.poll()
            poller.register(sys.stdin, uselect.POLLIN)
            print(
                "[snic_bee] upload disabled by default; type 'y' + Enter within {}s to enable.".format(
                    int(timeout_s)
                )
            )
            start = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), start) < int(timeout_s) * 1000:
                ready = poller.poll(200)
                if ready:
                    line = sys.stdin.readline()
                    if not line:
                        return False
                    return line.strip().lower() in ("y", "yes", "1", "true", "on")
            return False

        ans = input("Enable upload? [y/N] ")
        return ans.strip().lower() in ("y", "yes", "1", "true", "on")
    except Exception:
        return False


def _boot_beep(system=None):
    pwm = None
    temp_pwm = False
    try:
        if system is not None and hasattr(system, "buzzer"):
            pwm = system.buzzer
        else:
            pwm = PWM(Pin(BUZZER_PWM_PIN, Pin.OUT), freq=int(BOOT_BEEP_FREQ_HZ), duty=0)
            temp_pwm = True

        try:
            pwm.freq(int(BOOT_BEEP_FREQ_HZ))
        except Exception:
            pass

        for _ in range(int(BOOT_BEEP_COUNT)):
            pwm.duty(int(BUZZER_ALARM_DUTY))
            time.sleep_ms(int(BOOT_BEEP_ON_MS))
            pwm.duty(0)
            time.sleep_ms(int(BOOT_BEEP_OFF_MS))
    except Exception:
        try:
            if pwm is not None:
                pwm.duty(0)
        except Exception:
            pass
    finally:
        if temp_pwm and pwm is not None:
            try:
                pwm.deinit()
            except Exception:
                pass


def main():
    app = SnicBeeTelemetryApp()
    try:
        # 降低 CPU 频率，优先保证长期运行温升可控。
        # ESP32 常见可选值：80MHz / 160MHz / 240MHz。
        try:
            machine.freq(160000000)
            app.log("cpu freq set to 160MHz for thermal control")
        except Exception as e:
            app.log("cpu freq keep default: {}".format(e))

        if ENABLE_BOOT_BEEP:
            _boot_beep(system=app.system)

        app.log("telemetry app start")
        app.log(
            "feature switch: distance={}, water={}".format(
                1 if ENABLE_DISTANCE_SENSOR else 0,
                1 if ENABLE_WATER_SENSOR else 0,
            )
        )

        if UPLOAD_CONFIRM_ON_BOOT:
            app.upload_enabled = _confirm_enable_upload(UPLOAD_CONFIRM_TIMEOUT_S)
        else:
            app.upload_enabled = bool(ENABLE_UPLOAD_WIFI)

        if app.upload_enabled:
            # First WiFi connect (blocking) - upload only after WiFi is ready.
            app.log("wifi connecting...")
            while not app.connect_wifi_in_order():
                app.log("wifi connect failed, retry all in {}s".format(WIFI_ROTATE_BACKOFF_S))
                time.sleep(WIFI_ROTATE_BACKOFF_S)
        else:
            app.log("upload disabled; http upload off")
            if ENABLE_WIFI_ON_BOOT:
                app.log("wifi auto-connect enabled; try connect once at boot")
                try:
                    app.connect_wifi_in_order()
                except Exception as e:
                    app.log("wifi connect exception: {}".format(e))

        if app.system is not None:
            app.system.startup_self_test()

        while True:
            distance_cm = app.system.step() if app.system is not None else None
            water_event = app.water.poll() if app.water is not None else False
            now = time.ticks_ms()

            # Keep WiFi alive even when upload is disabled (throttled inside _ensure_wifi()).
            if ENABLE_WIFI_ON_BOOT and not app.upload_enabled:
                try:
                    app._ensure_wifi()
                except Exception as e:
                    app.log("wifi ensure exception: {}".format(e))

            # Water event: upload immediately
            if water_event and app.upload_enabled:
                payload = app._payload_base()
                payload.update(
                    {
                        "type": "event",
                        "event": "water_drop",
                        "water_active": 1 if (app.water is not None and app.water.is_active()) else 0,
                        "distance_cm": None if distance_cm is None else round(distance_cm, 1),
                    }
                )
                app._upload(payload)

            # Periodic telemetry
            if app.upload_enabled and time.ticks_diff(now, app._last_upload_ms) >= UPLOAD_INTERVAL_MS:
                app._last_upload_ms = now
                payload = app._payload_base()
                payload.update(
                    {
                        "type": "telemetry",
                        "distance_cm": None if distance_cm is None else round(distance_cm, 1),
                        "water_active": 1 if (app.water is not None and app.water.is_active()) else 0,
                        "distance_enabled": 1 if app.system is not None else 0,
                        "water_enabled": 1 if app.water is not None else 0,
                        "wifi_ip": app.wifi.get_ip(),
                    }
                )
                app._upload(payload)
    except KeyboardInterrupt:
        print("[snic_bee] stopped by user")


if __name__ == "__main__":
    main()
