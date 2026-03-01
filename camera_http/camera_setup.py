"""
Camera Setup for ESP32-Cam
摄像头初始化和配置模块
"""

import camera_http
from micropython import const

# 摄像头配置常量
PIN_PWDN    = const(0)  # power-down
PIN_RESET   = const(1)  # reset
PIN_XCLK    = const(2)
PIN_SIOD    = const(3)  # SDA
PIN_SIOC    = const(4)  # SCL

PIN_D7      = const(5)
PIN_D6      = const(6)
PIN_D5      = const(7)
PIN_D4      = const(8)
PIN_D3      = const(9)
PIN_D2      = const(10)
PIN_D1      = const(11)
PIN_D0      = const(12)
PIN_VSYNC   = const(13)
PIN_HREF    = const(14)
PIN_PCLK    = const(15)

XCLK_MHZ    = const(16)  # camera machine clock
PIXFORMAT   = const(17)  # pixel format
FRAMESIZE   = const(18)  # framesize
JPEG_QUALITY= const(19)
FB_COUNT    = const(20)  # framebuffer count

# 像素格式
PIXFORMAT_RGB565    = const(1)  # 2BPP/RGB565
PIXFORMAT_YUV422    = const(2)  # 2BPP/YUV422
PIXFORMAT_YUV420    = const(3)  # 1.5BPP/YUV420
PIXFORMAT_GRAYSCALE = const(4)  # 1BPP/GRAYSCALE
PIXFORMAT_JPEG      = const(5)  # JPEG/COMPRESSED
PIXFORMAT_RGB888    = const(6)  # 3BPP/RGB888
PIXFORMAT_RAW       = const(7)  # RAW

# 帧尺寸
FRAMESIZE_96X96   = const(1)   # 96x96
FRAMESIZE_QQVGA   = const(2)   # 160x120
FRAMESIZE_QCIF    = const(3)   # 176x144
FRAMESIZE_HQVGA   = const(4)   # 240x176
FRAMESIZE_240X240 = const(5)   # 240x240
FRAMESIZE_QVGA    = const(6)   # 320x240
FRAMESIZE_CIF     = const(7)   # 400x296
FRAMESIZE_HVGA    = const(8)   # 480x320
FRAMESIZE_VGA     = const(9)   # 640x480
FRAMESIZE_SVGA    = const(10)  # 800x600
FRAMESIZE_XGA     = const(11)  # 1024x768
FRAMESIZE_HD      = const(12)  # 1280x720
FRAMESIZE_SXGA    = const(13)  # 1280x1024
FRAMESIZE_UXGA    = const(14)  # 1600x1200
FRAMESIZE_FHD     = const(15)  # 1920x1080
FRAMESIZE_P_HD    = const(16)  # 720x1280
FRAMESIZE_P_3MP   = const(17)  # 864x1536
FRAMESIZE_QXGA    = const(18)  # 2048x1536

# XIAO ESP32-S3 OV2640摄像头配置
XIAO_CONFIG = {
    PIN_PWDN: -1,
    PIN_RESET: -1,
    PIN_XCLK: 10,
    PIN_SIOD: 40,
    PIN_SIOC: 39,
    PIN_D7: 48,
    PIN_D6: 11,
    PIN_D5: 12,
    PIN_D4: 14,
    PIN_D3: 16,
    PIN_D2: 18,
    PIN_D1: 17,
    PIN_D0: 15,
    PIN_VSYNC: 38,
    PIN_HREF: 47,
    PIN_PCLK: 13,
    XCLK_MHZ: 14,
    PIXFORMAT: PIXFORMAT_JPEG,
    FRAMESIZE: FRAMESIZE_VGA,
    JPEG_QUALITY: 12,
    FB_COUNT: 2,
}

class ESP32Camera:
    def __init__(self, config=None):
        """
        初始化摄像头

        Args:
            config: 摄像头配置字典，默认使用XIAO配置
        """
        self.config = config or XIAO_CONFIG
        self.initialized = False

    def configure(self):
        """配置摄像头参数"""
        try:
            for key, val in self.config.items():
                camera_http.conf(key, val)
            print("摄像头配置完成")
            return True
        except Exception as e:
            print(f"摄像头配置失败: {e}")
            return False

    def init(self):
        """初始化摄像头"""
        try:
            # 先配置摄像头
            if not self.configure():
                return False

            # 初始化摄像头
            result = camera_http.init()
            if result:
                self.initialized = True
                print("摄像头初始化成功")

                # 设置默认参数
                camera_http.contrast(2)       # 增加对比度
                camera_http.brightness(0)     # 亮度
                camera_http.saturation(0)     # 饱和度

                return True
            else:
                print("摄像头初始化失败")
                return False

        except Exception as e:
            print(f"摄像头初始化异常: {e}")
            return False

    def deinit(self):
        """反初始化摄像头"""
        try:
            camera_http.deinit()
            self.initialized = False
            print("摄像头已关闭")
        except Exception as e:
            print(f"关闭摄像头失败: {e}")

    def capture_frame(self):
        """捕获一帧图像"""
        if not self.initialized:
            print("摄像头未初始化")
            return None

        try:
            return camera_http.capture()
        except Exception as e:
            print(f"捕获图像失败: {e}")
            return None

    def set_framesize(self, size):
        """设置帧尺寸"""
        if not self.initialized:
            return False

        try:
            camera_http.conf(FRAMESIZE, size)
            print(f"帧尺寸已设置为: {size}")
            return True
        except Exception as e:
            print(f"设置帧尺寸失败: {e}")
            return False

    def set_quality(self, quality):
        """设置JPEG质量 (1-31, 数值越小质量越高)"""
        if not self.initialized:
            return False

        try:
            camera_http.conf(JPEG_QUALITY, max(1, min(31, quality)))
            print(f"JPEG质量已设置为: {quality}")
            return True
        except Exception as e:
            print(f"设置JPEG质量失败: {e}")
            return False

    def set_contrast(self, contrast):
        """设置对比度 (-2 到 +2)"""
        if not self.initialized:
            return False

        try:
            camera_http.contrast(contrast)
            print(f"对比度已设置为: {contrast}")
            return True
        except Exception as e:
            print(f"设置对比度失败: {e}")
            return False

    def get_status(self):
        """获取摄像头状态"""
        return {
            "initialized": self.initialized,
            "framesize": self.config.get(FRAMESIZE, "unknown"),
            "quality": self.config.get(JPEG_QUALITY, "unknown"),
            "format": "JPEG"
        }

def configure_camera(cam, config):
    """配置摄像头的辅助函数"""
    for key, val in config.items():
        cam.conf(key, val)