"""
ESP32-Cam WiFi热点摄像头服务器
主程序 - 启动摄像头和WiFi热点，提供HTTP访问

功能:
1. 启动WiFi热点
2. 初始化摄像头
3. 启动HTTP服务器
4. 提供多种访问方式：
   - 网页界面: http://192.168.4.1
   - 实时流: http://192.168.4.1/stream
   - 单张图片: http://192.168.4.1/capture
   - 状态信息: http://192.168.4.1/status
"""

import time
import gc
import machine
from wifi_ap import WiFiAP
from camera_setup import ESP32Camera
from http_server import CameraHTTPServer

class ESP32CamServer:
    def __init__(self,
                 wifi_ssid="ESP32-Cam",
                 wifi_password="12345678",
                 http_port=80):
        """
        初始化ESP32摄像头服务器

        Args:
            wifi_ssid: WiFi热点名称
            wifi_password: WiFi热点密码 (至少8位)
            http_port: HTTP服务端口
        """
        print("=" * 50)
        print("ESP32-Cam WiFi热点摄像头服务器")
        print("=" * 50)

        # 禁用调试输出以提高性能
        import esp
        esp.osdebug(None)

        # 初始化组件
        self.wifi_ap = WiFiAP(wifi_ssid, wifi_password)
        self.camera = ESP32Camera()
        self.http_server = CameraHTTPServer(self.camera, http_port)

        # 运行状态
        self.running = False

    def setup_system(self):
        """系统设置"""
        print("正在设置系统...")

        # 设置CPU频率为最高性能
        machine.freq(240000000)  # 240MHz
        print(f"CPU频率设置为: {machine.freq()//1000000} MHz")

        # 清理内存
        gc.collect()
        print(f"可用内存: {gc.mem_free()} bytes")

    def start(self):
        """启动所有服务"""
        try:
            # 系统设置
            self.setup_system()

            # 启动WiFi热点
            print("\n1. 启动WiFi热点...")
            if not self.wifi_ap.start_ap():
                print("WiFi热点启动失败，程序退出")
                return False

            # 初始化摄像头
            print("\n2. 初始化摄像头...")
            if not self.camera.init():
                print("摄像头初始化失败，程序退出")
                self.cleanup()
                return False

            # 启动HTTP服务器
            print("\n3. 启动HTTP服务器...")
            self.running = True
            print("\n服务器启动完成!")

            # 显示访问信息
            self.show_access_info()

            # 运行HTTP服务器
            print("\n开始处理HTTP请求...")
            self.http_server.run()

            return True

        except Exception as e:
            print(f"启动服务器失败: {e}")
            self.cleanup()
            return False

    def show_access_info(self):
        """显示访问信息"""
        ip = self.wifi_ap.get_ip()
        port = self.http_server.port

        print("\n" + "=" * 50)
        print("服务器已启动，可以通过以下方式访问:")
        print("=" * 50)
        print(f"WiFi热点名称: {self.wifi_ap.ssid}")
        print(f"WiFi密码: {self.wifi_ap.password}")
        print(f"服务器IP: {ip}")
        print(f"端口: {port}")
        print("\n访问地址:")
        print(f"• 主页: http://{ip}/")
        print(f"• 实时流: http://{ip}/stream")
        print(f"• 单张图片: http://{ip}/capture")
        print(f"• 状态信息: http://{ip}/status")
        print("\n控制参数:")
        print(f"• 设置分辨率: http://{ip}/control?size=640x480")
        print(f"• 设置质量: http://{ip}/control?quality=10")
        print(f"• 设置对比度: http://{ip}/control?contrast=1")
        print("=" * 50)
        print("请连接WiFi热点并在浏览器中打开上述地址")

    def cleanup(self):
        """清理资源"""
        print("\n正在清理资源...")
        self.running = False

        try:
            if self.http_server:
                self.http_server.stop_server()
        except:
            pass

        try:
            if self.camera:
                self.camera.deinit()
        except:
            pass

        try:
            if self.wifi_ap:
                self.wifi_ap.stop_ap()
        except:
            pass

        print("资源清理完成")

    def stop(self):
        """停止服务器"""
        print("\n正在停止服务器...")
        self.cleanup()

def main():
    """主函数"""
    # 创建服务器实例
    # 可以在这里修改WiFi名称和密码
    server = ESP32CamServer(
        wifi_ssid="ESP32-Cam-Hotspot",  # WiFi热点名称
        wifi_password="12345678",       # WiFi密码 (至少8位)
        http_port=80                    # HTTP端口
    )

    try:
        # 启动服务器
        server.start()

    except KeyboardInterrupt:
        print("\n收到中断信号...")
        server.stop()

    except Exception as e:
        print(f"程序运行异常: {e}")
        server.stop()

    print("程序结束")

def test_components():
    """测试各个组件"""
    print("测试ESP32摄像头组件...")

    # 测试WiFi热点
    print("\n1. 测试WiFi热点...")
    wifi = WiFiAP("Test-AP", "12345678")
    if wifi.start_ap():
        print("WiFi热点测试成功")
        wifi.stop_ap()
    else:
        print("WiFi热点测试失败")

    # 测试摄像头
    print("\n2. 测试摄像头...")
    cam = ESP32Camera()
    if cam.init():
        print("摄像头测试成功")
        frame = cam.capture_frame()
        if frame:
            print(f"图像捕获成功，大小: {len(frame)} bytes")
        cam.deinit()
    else:
        print("摄像头测试失败")

    print("\n组件测试完成")

if __name__ == "__main__":
    # 如果需要测试组件，取消下面的注释
    # test_components()

    # 运行主程序
    main()