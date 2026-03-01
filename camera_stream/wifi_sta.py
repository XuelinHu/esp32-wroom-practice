"""
WiFi Station (STA) Module for ESP32-Cam V2
WiFi客户端模式 - 连接到现有WiFi网络

功能:
1. 连接到指定的WiFi网络
2. 自动重连机制
3. 连接状态监控
4. 详细日志输出
"""

import network
import time
import gc

class WiFiStation:
    def __init__(self, ssid, password, timeout=30, retry_count=3):
        """
        初始化WiFi Station

        Args:
            ssid: WiFi网络名称
            password: WiFi密码
            timeout: 连接超时时间(秒)
            retry_count: 重试次数
        """
        self.ssid = ssid
        self.password = password
        self.timeout = timeout
        self.retry_count = retry_count
        self.sta = None
        self.ip_address = None
        self.connected = False

        print(f"[WIFI] WiFi Station 模块初始化")
        print(f"[WIFI] 目标SSID: {ssid}")
        print(f"[WIFI] 连接超时: {timeout}秒")
        print(f"[WIFI] 重试次数: {retry_count}")

    def connect(self):
        """
        连接到WiFi网络

        Returns:
            bool: 连接是否成功
        """
        print("\n" + "=" * 50)
        print("[WIFI] 开始连接WiFi网络...")
        print("=" * 50)

        # 关闭AP模式
        try:
            ap = network.WLAN(network.AP_IF)
            if ap.active():
                ap.active(False)
                print("[WIFI] AP模式已关闭")
        except Exception as e:
            print(f"[WIFI] 关闭AP模式失败: {e}")

        # 创建STA接口
        try:
            self.sta = network.WLAN(network.STA_IF)
            print(f"[WIFI] STA接口状态: {'已激活' if self.sta.active() else '未激活'}")
        except Exception as e:
            print(f"[WIFI] 创建STA接口失败: {e}")
            return False

        # 如果已连接，先断开
        if self.sta.isconnected():
            print("[WIFI] 检测到已有连接，先断开...")
            self.sta.disconnect()
            time.sleep(1)

        # 激活STA接口
        print("[WIFI] 激活STA接口...")
        self.sta.active(True)
        time.sleep(0.5)

        # 扫描网络（可选，用于调试）
        print("[WIFI] 扫描可用网络...")
        try:
            networks = self.sta.scan()
            print(f"[WIFI] 发现 {len(networks)} 个网络:")
            for i, net in enumerate(networks[:10]):  # 只显示前10个
                ssid_bytes, bssid, channel, rssi, authmode, hidden = net
                ssid_str = ssid_bytes.decode('utf-8') if ssid_bytes else '<hidden>'
                print(f"[WIFI]   {i+1}. {ssid_str} (信道:{channel}, 信号:{rssi}dBm)")
        except Exception as e:
            print(f"[WIFI] 扫描网络失败: {e}")

        # 尝试连接
        for attempt in range(1, self.retry_count + 1):
            print(f"\n[WIFI] === 连接尝试 {attempt}/{self.retry_count} ===")

            try:
                # 清理内存
                gc.collect()

                # 开始连接
                print(f"[WIFI] 正在连接到: {self.ssid}")
                self.sta.connect(self.ssid, self.password)

                # 等待连接
                start_time = time.time()
                while time.time() - start_time < self.timeout:
                    if self.sta.isconnected():
                        # 连接成功
                        self.connected = True
                        self.ip_address = self.sta.ifconfig()[0]

                        print("\n" + "=" * 50)
                        print("[WIFI] WiFi 连接成功!")
                        print("=" * 50)
                        self._print_connection_info()

                        return True

                    # 显示等待状态
                    elapsed = time.time() - start_time
                    print(f"[WIFI] 等待连接中... ({elapsed:.1f}秒)")
                    time.sleep(1)

                # 连接超时
                print(f"[WIFI] 连接超时 ({self.timeout}秒)")

                # 显示失败原因
                status = self.sta.status()
                print(f"[WIFI] 连接状态码: {status}")
                self._print_status_meaning(status)

            except Exception as e:
                print(f"[WIFI] 连接过程异常: {e}")

            # 等待后重试
            if attempt < self.retry_count:
                wait_time = 2
                print(f"[WIFI] 等待 {wait_time}秒后重试...")
                time.sleep(wait_time)

        # 所有尝试都失败
        print("\n" + "=" * 50)
        print("[WIFI] WiFi 连接失败!")
        print(f"[WIFI] 已尝试 {self.retry_count} 次")
        print("=" * 50)

        self.connected = False
        return False

    def _print_connection_info(self):
        """打印连接详细信息"""
        if not self.sta or not self.sta.isconnected():
            return

        ifconfig = self.sta.ifconfig()
        print(f"[WIFI] IP地址: {ifconfig[0]}")
        print(f"[WIFI] 子网掩码: {ifconfig[1]}")
        print(f"[WIFI] 网关: {ifconfig[2]}")
        print(f"[WIFI] DNS服务器: {ifconfig[3]}")

        # 获取更多配置信息
        try:
            print(f"[WIFI] SSID: {self.sta.config('essid')}")
            print(f"[WIFI] 信道: {self.sta.config('channel')}")
        except:
            pass

    def _print_status_meaning(self, status):
        """打印状态码含义"""
        status_meanings = {
            0: "STAT_IDLE - 空闲状态",
            1: "STAT_NO_AP_FOUND - 未找到AP",
            2: "STAT_WRONG_PASSWORD - 密码错误",
            3: "STAT_NO_AP_FOUND_IN_RSSI - 信号太弱",
            4: "STAT_CONNECT_FAIL - 连接失败",
            5: "STAT_GOT_IP - 已获取IP (连接成功)",
            1000: "STAT_ASSOC - 正在关联",
            1001: "STAT_HANDSHAKE_TIMEOUT - 握手超时",
        }
        meaning = status_meanings.get(status, f"未知状态")
        print(f"[WIFI] 状态含义: {meaning}")

    def disconnect(self):
        """断开WiFi连接"""
        print("[WIFI] 断开WiFi连接...")
        if self.sta:
            try:
                self.sta.disconnect()
                self.connected = False
                self.ip_address = None
                print("[WIFI] WiFi已断开")
            except Exception as e:
                print(f"[WIFI] 断开连接失败: {e}")

    def is_connected(self):
        """检查是否已连接"""
        if self.sta:
            self.connected = self.sta.isconnected()
        return self.connected

    def get_ip(self):
        """获取IP地址"""
        if self.sta and self.sta.isconnected():
            self.ip_address = self.sta.ifconfig()[0]
        return self.ip_address

    def get_status(self):
        """获取连接状态"""
        if not self.sta:
            return {"connected": False, "error": "STA接口未初始化"}

        return {
            "connected": self.sta.isconnected(),
            "ip": self.get_ip(),
            "ssid": self.ssid,
            "ifconfig": self.sta.ifconfig() if self.sta.isconnected() else None
        }

    def reconnect(self):
        """重新连接WiFi"""
        print("[WIFI] 尝试重新连接...")
        self.disconnect()
        time.sleep(1)
        return self.connect()

    def monitor_connection(self, check_interval=5):
        """
        监控连接状态（非阻塞）

        Args:
            check_interval: 检查间隔(秒)

        Returns:
            bool: 当前是否连接
        """
        if not self.sta:
            return False

        if not self.sta.isconnected():
            print("[WIFI] 检测到连接断开!")
            self.connected = False
            return False

        return True


def test_wifi_connection():
    """测试WiFi连接"""
    # 测试用的WiFi配置
    test_ssid = "ChinaNet-E5y7"
    test_password = "zadyx5cc"

    print("\n" + "=" * 50)
    print("WiFi连接测试")
    print("=" * 50)

    wifi = WiFiStation(test_ssid, test_password, timeout=20, retry_count=2)

    if wifi.connect():
        print("\n测试成功!")

        # 测试网络连通性
        print("\n测试网络连通性...")
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(("8.8.8.8", 53))
            sock.close()

            if result == 0:
                print("网络连通性测试: 成功")
            else:
                print(f"网络连通性测试: 失败 (错误码: {result})")
        except Exception as e:
            print(f"网络连通性测试异常: {e}")

        wifi.disconnect()
    else:
        print("\n测试失败!")

    print("\n测试完成")


if __name__ == "__main__":
    test_wifi_connection()
