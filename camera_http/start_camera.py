"""
ESP32-Cam 快速启动脚本
简化的摄像头服务器启动程序

使用方法:
1. 将此文件上传到ESP32
2. 运行: exec(open('start_camera.py').read())
"""

# 配置参数
WIFI_SSID = "ESP32-Cam"      # WiFi热点名称
WIFI_PASSWORD = "12345678"   # WiFi密码 (至少8位)
HTTP_PORT = 80               # HTTP端口

# 快速启动函数
def quick_start():
    """快速启动摄像头服务器"""
    try:
        import main

        print("正在启动ESP32摄像头服务器...")
        server = main.ESP32CamServer(WIFI_SSID, WIFI_PASSWORD, HTTP_PORT)
        server.start()

    except Exception as e:
        print(f"启动失败: {e}")
        print("请检查硬件连接和配置")

# 直接启动
if __name__ == "__main__":
    quick_start()