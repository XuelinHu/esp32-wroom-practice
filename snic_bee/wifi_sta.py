"""
snic_bee.wifi_sta

轻量级 Wi‑Fi STA 模式连接助手。
专门给 MicroPython / ESP32 使用，尽量保持简单、依赖少。
"""

import gc
import network
import time


class WiFiStation:
    def __init__(self, ssid, password, timeout_s=20, retry_count=3, log_prefix="[snic_bee.wifi]"):
        # 关键参数说明：
        # - timeout_s: 单次连接等待时长，过大时掉线恢复会更慢
        # - retry_count: 单个 SSID 的重试次数，过高会导致断线时持续高负载重试
        self.ssid = ssid
        self.password = password
        self.timeout_s = int(timeout_s)
        self.retry_count = int(retry_count)
        self.log_prefix = log_prefix

        self._sta = None
        self._ip = None

    def _log(self, msg):
        print("{} {}".format(self.log_prefix, msg))

    def _status_text(self, status):
        # MicroPython on ESP32 typically uses these constants (may vary by port/firmware).
        mapping = {}
        for name in (
            "STAT_IDLE",
            "STAT_CONNECTING",
            "STAT_WRONG_PASSWORD",
            "STAT_NO_AP_FOUND",
            "STAT_CONNECT_FAIL",
            "STAT_GOT_IP",
        ):
            try:
                code = getattr(network, name)
                mapping[int(code)] = name
            except Exception:
                pass
        try:
            return mapping.get(int(status), str(status))
        except Exception:
            return str(status)

    def _safe_status(self):
        try:
            if self._sta is None:
                return None
            return self._sta.status()
        except Exception:
            return None

    def _safe_rssi(self):
        try:
            if self._sta is None:
                return None
            return self._sta.status("rssi")
        except Exception:
            return None

    def _safe_mac(self):
        try:
            if self._sta is None:
                return None
            mac = self._sta.config("mac")
            try:
                return ":".join("{:02x}".format(b) for b in mac)
            except Exception:
                return str(mac)
        except Exception:
            return None

    def connect(self):
        # 关闭 AP 模式，避免 STA + AP 同时工作带来额外功耗和发热。
        ap = network.WLAN(network.AP_IF)
        if ap.active():
            ap.active(False)

        self._sta = network.WLAN(network.STA_IF)
        self._sta.active(True)
        mac = self._safe_mac()
        if mac:
            self._log("sta active=1 mac={}".format(mac))

        if self._sta.isconnected():
            self._ip = self._sta.ifconfig()[0]
            self._log("already connected, ip={} rssi={}".format(self._ip, self._safe_rssi()))
            return True

        for attempt in range(1, self.retry_count + 1):
            gc.collect()
            self._log("connect attempt {}/{} ssid={}".format(attempt, self.retry_count, self.ssid))
            try:
                self._sta.connect(self.ssid, self.password)
            except Exception as e:
                self._log("connect call failed: {}".format(e))
                time.sleep(1)
                continue

            start = time.time()
            last_status = None
            while not self._sta.isconnected():
                if time.time() - start >= self.timeout_s:
                    break

                st = self._safe_status()
                if st is not None and st != last_status:
                    last_status = st
                    self._log("status={} ({})".format(self._status_text(st), st))
                # 留出 CPU 时间片，避免连接等待期无意义空转。
                time.sleep(0.2)

            if self._sta.isconnected():
                self._ip = self._sta.ifconfig()[0]
                try:
                    ifcfg = self._sta.ifconfig()
                except Exception:
                    ifcfg = None
                self._log(
                    "connected, ip={} ifconfig={} rssi={}".format(
                        self._ip,
                        ifcfg,
                        self._safe_rssi(),
                    )
                )
                return True

            st = self._safe_status()
            if st is not None:
                self._log("connect timeout/fail, status={} ({})".format(self._status_text(st), st))

            try:
                self._sta.disconnect()
            except Exception:
                pass
            time.sleep(1)

        self._log("connect failed")
        return False

    def disconnect(self):
        if not self._sta:
            return
        try:
            self._sta.disconnect()
        finally:
            self._ip = None

    def is_connected(self):
        return bool(self._sta and self._sta.isconnected())

    def get_ip(self):
        if self.is_connected():
            self._ip = self._sta.ifconfig()[0]
        return self._ip

    def get_rssi(self):
        return self._safe_rssi()

    def reconnect(self):
        # 先断开再重连，避免某些路由器下的 STA 假连接状态。
        self.disconnect()
        time.sleep(0.5)
        return self.connect()
