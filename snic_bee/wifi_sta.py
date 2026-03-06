"""
snic_bee.wifi_sta

Minimal WiFi Station (STA) helper for MicroPython/ESP32.
Kept intentionally small and dependency-free.
"""

import gc
import network
import time


class WiFiStation:
    def __init__(self, ssid, password, timeout_s=20, retry_count=3, log_prefix="[snic_bee.wifi]"):
        self.ssid = ssid
        self.password = password
        self.timeout_s = int(timeout_s)
        self.retry_count = int(retry_count)
        self.log_prefix = log_prefix

        self._sta = None
        self._ip = None

    def _log(self, msg):
        print("{} {}".format(self.log_prefix, msg))

    def connect(self):
        ap = network.WLAN(network.AP_IF)
        if ap.active():
            ap.active(False)

        self._sta = network.WLAN(network.STA_IF)
        self._sta.active(True)

        if self._sta.isconnected():
            self._ip = self._sta.ifconfig()[0]
            self._log("already connected, ip={}".format(self._ip))
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
            while not self._sta.isconnected():
                if time.time() - start >= self.timeout_s:
                    break
                time.sleep(0.2)

            if self._sta.isconnected():
                self._ip = self._sta.ifconfig()[0]
                self._log("connected, ip={}".format(self._ip))
                return True

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

    def reconnect(self):
        self.disconnect()
        time.sleep(0.5)
        return self.connect()

