"""
ESP32-Cam V2 视频流服务器
主程序 - WiFi Station模式，连接局域网提供视频流服务

功能:
1. 连接到指定WiFi网络 (STA模式)
2. 初始化摄像头
3. 启动HTTP服务器
4. 提供多种访问方式：
   - 网页界面: http://<设备IP>/
   - 实时视频流: http://<设备IP>/stream
   - 单张图片: http://<设备IP>/capture
   - 状态信息: http://<设备IP>/status
   - 参数控制: http://<设备IP>/control

WiFi配置:
   SSID: ChinaNet-E5y7
   密码: zadyx5cc
"""

import time
import gc
import machine
import sys

# WiFi配置
WIFI_SSID = "ChinaNet-E5y7"
WIFI_PASSWORD = "zadyx5cc"
HTTP_PORT = 80

# 导入模块
from wifi_sta import WiFiStation
from camera_setup import ESP32Camera
from http_server import CameraHTTPServer


class ESP32CamV2Server:
    def __init__(self, wifi_ssid, wifi_password, http_port=80):
        """
        初始化ESP32摄像头服务器V2

        Args:
            wifi_ssid: WiFi网络名称
            wifi_password: WiFi密码
            http_port: HTTP服务端口
        """
        print("\n" + "=" * 60)
        print("  ESP32-Cam V2 视频流服务器")
        print("  WiFi Station 模式")
        print("=" * 60)
        print(f"[MAIN] WiFi SSID: {wifi_ssid}")
        print(f"[MAIN] HTTP端口: {http_port}")
        print(f"[MAIN] 初始化时间: {time.ticks_ms()}")

        # 禁用调试输出以提高性能
        try:
            import esp
            esp.osdebug(None)
            print("[MAIN] 调试输出已禁用")
        except Exception as e:
            print(f"[MAIN] 禁用调试输出失败: {e}")

        # 初始化组件 (先不启动)
        self.wifi_ssid = wifi_ssid
        self.wifi_password = wifi_password
        self.http_port = http_port

        self.wifi_sta = None
        self.camera = None
        self.http_server = None

        # 运行状态
        self.running = False
        self.start_time = time.time()

    def setup_system(self):
        """系统设置"""
        print("\n" + "=" * 60)
        print("[MAIN] 系统设置")
        print("=" * 60)

        # 设置CPU频率为最高性能
        try:
            current_freq = machine.freq()
            print(f"[MAIN] 当前CPU频率: {current_freq//1000000} MHz")

            machine.freq(240000000)  # 240MHz
            print(f"[MAIN] CPU频率设置为: {machine.freq()//1000000} MHz")
        except Exception as e:
            print(f"[MAIN] 设置CPU频率失败: {e}")

        # 清理内存
        gc.collect()
        print(f"[MAIN] 可用内存: {gc.mem_free()} bytes")
        print(f"[MAIN] 已分配内存: {gc.mem_alloc()} bytes")

        # 打印系统信息
        try:
            import os
            print(f"[MAIN] 文件系统: {os.statvfs('/')}")
        except:
            pass

    def start(self):
        """启动所有服务"""
        print("\n" + "=" * 60)
        print("[MAIN] 开始启动服务...")
        print("=" * 60)

        try:
            # 1. 系统设置
            self.setup_system()

            # 2. 连接WiFi
            print("\n[MAIN] === 步骤1: 连接WiFi ===")
            self.wifi_sta = WiFiStation(
                self.wifi_ssid,
                self.wifi_password,
                timeout=30,
                retry_count=3
            )

            if not self.wifi_sta.connect():
                print("[MAIN] WiFi连接失败，程序退出")
                self.cleanup()
                return False

            ip_address = self.wifi_sta.get_ip()
            print(f"[MAIN] WiFi连接成功，IP地址: {ip_address}")

            # 3. 初始化摄像头
            print("\n[MAIN] === 步骤2: 初始化摄像头 ===")
            self.camera = ESP32Camera()

            if not self.camera.init():
                print("[MAIN] 摄像头初始化失败，程序退出")
                self.cleanup()
                return False

            print("[MAIN] 摄像头初始化成功")

            # 清理内存
            gc.collect()
            print(f"[MAIN] 摄像头初始化后可用内存: {gc.mem_free()} bytes")

            # 4. 启动HTTP服务器
            print("\n[MAIN] === 步骤3: 启动HTTP服务器 ===")
            try:
                # 尝试新版本(3参数)
                self.http_server = CameraHTTPServer(self.camera, self.http_port, self.wifi_sta)
            except TypeError:
                # 兼容旧版本(2参数)
                print("[MAIN] 使用旧版HTTP服务器接口")
                self.http_server = CameraHTTPServer(self.camera, self.http_port)
                self.http_server.wifi_sta = self.wifi_sta

            self.running = True

            # 显示访问信息
            self.show_access_info(ip_address)

            # 5. 运行HTTP服务器
            print("\n[MAIN] === 服务器已就绪 ===")
            print("[MAIN] 开始处理HTTP请求...\n")

            self.http_server.run()

            return True

        except Exception as e:
            print(f"[MAIN] 启动服务器失败: {e}")
            sys.print_exception(e)
            self.cleanup()
            return False

    def show_access_info(self, ip_address):
        """显示访问信息"""
        port = self.http_port

        print("\n" + "=" * 60)
        print("  服务器已启动，可以通过以下方式访问:")
        print("=" * 60)
        print(f"  WiFi网络: {self.wifi_ssid}")
        print(f"  设备IP: {ip_address}")
        print(f"  端口: {port}")
        print("")
        print("  访问地址:")
        print(f"  • 主页:     http://{ip_address}/")
        print(f"  • 视频流:   http://{ip_address}/stream")
        print(f"  • 单张图片: http://{ip_address}/capture")
        print(f"  • 状态信息: http://{ip_address}/status")
        print("")
        print("  控制参数:")
        print(f"  • 设置分辨率: http://{ip_address}/control?size=640x480")
        print(f"  • 设置质量:   http://{ip_address}/control?quality=10")
        print(f"  • 设置对比度: http://{ip_address}/control?contrast=1")
        print("=" * 60)
        print("")
        print("  请在同一局域网内的设备上访问上述地址")
        print("=" * 60)

    def cleanup(self):
        """清理资源"""
        print("\n" + "=" * 60)
        print("[MAIN] 清理资源...")
        print("=" * 60)

        self.running = False

        # 停止HTTP服务器
        if self.http_server:
            try:
                print("[MAIN] 停止HTTP服务器...")
                self.http_server.stop_server()
            except Exception as e:
                print(f"[MAIN] 停止HTTP服务器失败: {e}")

        # 关闭摄像头
        if self.camera:
            try:
                print("[MAIN] 关闭摄像头...")
                self.camera.deinit()
            except Exception as e:
                print(f"[MAIN] 关闭摄像头失败: {e}")

        # 断开WiFi
        if self.wifi_sta:
            try:
                print("[MAIN] 断开WiFi连接...")
                self.wifi_sta.disconnect()
            except Exception as e:
                print(f"[MAIN] 断开WiFi失败: {e}")

        # 清理内存
        gc.collect()
        print(f"[MAIN] 清理后可用内存: {gc.mem_free()} bytes")
        print("[MAIN] 资源清理完成")

    def stop(self):
        """停止服务器"""
        print("\n[MAIN] 正在停止服务器...")
        self.cleanup()

    def get_uptime(self):
        """获取运行时间"""
        return time.time() - self.start_time


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  ESP32-Cam V2 主程序启动")
    print("=" * 60)

    # 创建服务器实例
    server = ESP32CamV2Server(
        wifi_ssid=WIFI_SSID,
        wifi_password=WIFI_PASSWORD,
        http_port=HTTP_PORT
    )

    try:
        # 启动服务器
        server.start()

    except KeyboardInterrupt:
        print("\n[MAIN] 收到中断信号 (KeyboardInterrupt)...")
        server.stop()

    except Exception as e:
        print(f"\n[MAIN] 程序运行异常: {e}")
        sys.print_exception(e)
        server.stop()

    print("\n[MAIN] 程序结束")


def test_wifi_only():
    """仅测试WiFi连接"""
    print("\n" + "=" * 60)
    print("  WiFi连接测试")
    print("=" * 60)

    wifi = WiFiStation(WIFI_SSID, WIFI_PASSWORD, timeout=20, retry_count=2)

    if wifi.connect():
        print("\n[TEST] WiFi测试成功!")
        print(f"[TEST] IP地址: {wifi.get_ip()}")

        # 测试DNS
        print("\n[TEST] 测试DNS解析...")
        try:
            import socket
            addr = socket.getaddrinfo("www.baidu.com", 80)[0][-1]
            print(f"[TEST] DNS解析成功: www.baidu.com -> {addr[0]}")
        except Exception as e:
            print(f"[TEST] DNS解析失败: {e}")

        wifi.disconnect()
    else:
        print("\n[TEST] WiFi测试失败!")

    print("\n[TEST] 测试完成")


def test_camera_only():
    """仅测试摄像头"""
    print("\n" + "=" * 60)
    print("  摄像头测试")
    print("=" * 60)

    cam = ESP32Camera()

    if cam.init():
        print("\n[TEST] 摄像头初始化成功")

        # 捕获测试帧
        print("\n[TEST] 捕获测试帧...")
        for i in range(5):
            frame = cam.capture_frame()
            if frame:
                print(f"[TEST] 帧 {i+1}: {len(frame)} bytes")
            else:
                print(f"[TEST] 帧 {i+1}: 捕获失败")
            time.sleep(0.1)

        cam.print_status()
        cam.deinit()
    else:
        print("\n[TEST] 摄像头初始化失败")

    print("\n[TEST] 测试完成")


if __name__ == "__main__":
    # 运行主程序
    main()

    # 如果需要单独测试，取消下面的注释:
    # test_wifi_only()
    # test_camera_only()
