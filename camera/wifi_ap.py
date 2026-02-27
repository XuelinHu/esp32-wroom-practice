"""
WiFi Access Point Configuration for ESP32-Cam
创建WiFi热点供设备连接
"""

import network
import time
import socket

class WiFiAP:
    def __init__(self, ssid="ESP32-Cam", password="12345678", channel=11):
        """
        初始化WiFi热点

        Args:
            ssid: 热点名称
            password: 密码 (至少8位)
            channel: WiFi信道 (1-14)
        """
        self.ssid = ssid
        self.password = password
        self.channel = channel
        self.ap = None
        self.ip_address = None

    def start_ap(self):
        """启动WiFi热点"""
        try:
            # 关闭STA模式
            sta = network.WLAN(network.STA_IF)
            if sta.active():
                sta.active(False)

            # 创建AP热点
            self.ap = network.WLAN(network.AP_IF)
            self.ap.active(True)

            # 配置热点
            self.ap.config(essid=self.ssid, password=self.password, channel=self.channel)

            # 等待热点启动
            time.sleep(2)

            # 获取IP地址
            self.ip_address = self.ap.ifconfig()[0]

            print(f"WiFi热点已启动")
            print(f"SSID: {self.ssid}")
            print(f"密码: {self.password}")
            print(f"IP地址: {self.ip_address}")
            print(f"信道: {self.channel}")

            return True

        except Exception as e:
            print(f"启动WiFi热点失败: {e}")
            return False

    def stop_ap(self):
        """关闭WiFi热点"""
        if self.ap:
            self.ap.active(False)
            print("WiFi热点已关闭")

    def get_status(self):
        """获取热点状态"""
        if not self.ap or not self.ap.active():
            return {"active": False}

        connected_stations = len(self.ap.status('stations'))
        return {
            "active": True,
            "ssid": self.ssid,
            "ip": self.ip_address,
            "channel": self.channel,
            "connected_devices": connected_stations
        }

    def is_connected(self):
        """检查热点是否活跃"""
        return self.ap and self.ap.active()

    def get_ip(self):
        """获取热点IP地址"""
        return self.ip_address if self.ip_address else "192.168.4.1"