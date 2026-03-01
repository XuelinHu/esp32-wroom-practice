"""
Camera Setup Module for ESP32-Cam V2
摄像头初始化和配置模块

功能:
1. 摄像头硬件配置
2. 图像参数设置
3. 帧捕获功能
4. 详细日志输出
"""

import camera_http
from micropython import const
import time
import gc

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

# 帧尺寸名称映射
FRAMESIZE_NAMES = {
    FRAMESIZE_96X96: "96x96",
    FRAMESIZE_QQVGA: "160x120 (QQVGA)",
    FRAMESIZE_QCIF: "176x144 (QCIF)",
    FRAMESIZE_HQVGA: "240x176 (HQVGA)",
    FRAMESIZE_240X240: "240x240",
    FRAMESIZE_QVGA: "320x240 (QVGA)",
    FRAMESIZE_CIF: "400x296 (CIF)",
    FRAMESIZE_HVGA: "480x320 (HVGA)",
    FRAMESIZE_VGA: "640x480 (VGA)",
    FRAMESIZE_SVGA: "800x600 (SVGA)",
    FRAMESIZE_XGA: "1024x768 (XGA)",
    FRAMESIZE_HD: "1280x720 (HD)",
    FRAMESIZE_SXGA: "1280x1024 (SXGA)",
    FRAMESIZE_UXGA: "1600x1200 (UXGA)",
    FRAMESIZE_FHD: "1920x1080 (FHD)",
}

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
        初始化摄像头类

        Args:
            config: 摄像头配置字典，默认使用XIAO配置
        """
        self.config = config or XIAO_CONFIG
        self.initialized = False
        self.frame_count = 0
        self.error_count = 0

        print("[CAM] 摄像头模块初始化")
        print(f"[CAM] 配置信息:")
        print(f"[CAM]   帧尺寸: {FRAMESIZE_NAMES.get(self.config.get(FRAMESIZE), 'unknown')}")
        print(f"[CAM]   JPEG质量: {self.config.get(JPEG_QUALITY)}")
        print(f"[CAM]   帧缓冲数: {self.config.get(FB_COUNT)}")

    def configure(self):
        """配置摄像头参数"""
        print("[CAM] 开始配置摄像头参数...")

        try:
            for key, val in self.config.items():
                try:
                    camera_http.conf(key, val)
                    print(f"[CAM]   配置项 {key} = {val}")
                except Exception as e:
                    print(f"[CAM]   配置项 {key} = {val} 失败: {e}")

            print("[CAM] 摄像头参数配置完成")
            return True

        except Exception as e:
            print(f"[CAM] 摄像头配置失败: {e}")
            return False

    def init(self):
        """初始化摄像头"""
        print("\n" + "=" * 50)
        print("[CAM] 开始初始化摄像头...")
        print("=" * 50)

        # 先配置摄像头
        if not self.configure():
            print("[CAM] 配置失败，无法初始化")
            return False

        # 初始化摄像头
        print("[CAM] 调用 camera.init()...")
        try:
            result = camera_http.init()
            print(f"[CAM] camera.init() 返回值: {result}")

            if result:
                self.initialized = True
                print("[CAM] 摄像头初始化成功!")

                # 设置默认参数
                print("[CAM] 设置默认图像参数...")
                try:
                    camera_http.contrast(2)       # 增加对比度
                    print("[CAM]   对比度: 2")
                    camera_http.brightness(0)     # 亮度
                    print("[CAM]   亮度: 0")
                    camera_http.saturation(0)     # 饱和度
                    print("[CAM]   饱和度: 0")
                except Exception as e:
                    print(f"[CAM] 设置图像参数失败: {e}")

                # 清理内存
                gc.collect()
                print(f"[CAM] 可用内存: {gc.mem_free()} bytes")

                return True
            else:
                print("[CAM] 摄像头初始化失败 (返回False)")
                return False

        except Exception as e:
            print(f"[CAM] 摄像头初始化异常: {e}")
            import sys
            sys.print_exception(e)
            return False

    def deinit(self):
        """反初始化摄像头"""
        print("[CAM] 关闭摄像头...")

        try:
            camera_http.deinit()
            self.initialized = False
            print("[CAM] 摄像头已关闭")
        except Exception as e:
            print(f"[CAM] 关闭摄像头失败: {e}")

    def capture_frame(self):
        """捕获一帧图像"""
        if not self.initialized:
            print("[CAM] 错误: 摄像头未初始化")
            return None

        try:
            start_time = time.ticks_ms()
            frame = camera_http.capture()
            elapsed = time.ticks_diff(time.ticks_ms(), start_time)

            if frame:
                self.frame_count += 1
                frame_size = len(frame)
                # 每100帧打印一次状态
                if self.frame_count % 100 == 0:
                    print(f"[CAM] 已捕获 {self.frame_count} 帧, "
                          f"当前帧大小: {frame_size} bytes, "
                          f"耗时: {elapsed}ms, "
                          f"错误: {self.error_count}")
                return frame
            else:
                self.error_count += 1
                print(f"[CAM] 捕获图像失败 (空帧), 错误计数: {self.error_count}")
                return None

        except Exception as e:
            self.error_count += 1
            print(f"[CAM] 捕获图像异常: {e}, 错误计数: {self.error_count}")
            return None

    def set_framesize(self, size):
        """设置帧尺寸"""
        if not self.initialized:
            print("[CAM] 错误: 摄像头未初始化")
            return False

        try:
            camera_http.conf(FRAMESIZE, size)
            size_name = FRAMESIZE_NAMES.get(size, str(size))
            print(f"[CAM] 帧尺寸已设置为: {size_name}")
            return True
        except Exception as e:
            print(f"[CAM] 设置帧尺寸失败: {e}")
            return False

    def set_quality(self, quality):
        """设置JPEG质量 (1-31, 数值越小质量越高)"""
        if not self.initialized:
            print("[CAM] 错误: 摄像头未初始化")
            return False

        try:
            quality = max(1, min(31, quality))
            camera_http.conf(JPEG_QUALITY, quality)
            print(f"[CAM] JPEG质量已设置为: {quality}")
            return True
        except Exception as e:
            print(f"[CAM] 设置JPEG质量失败: {e}")
            return False

    def set_contrast(self, contrast):
        """设置对比度 (-2 到 +2)"""
        if not self.initialized:
            print("[CAM] 错误: 摄像头未初始化")
            return False

        try:
            camera_http.contrast(contrast)
            print(f"[CAM] 对比度已设置为: {contrast}")
            return True
        except Exception as e:
            print(f"[CAM] 设置对比度失败: {e}")
            return False

    def set_brightness(self, brightness):
        """设置亮度 (-2 到 +2)"""
        if not self.initialized:
            print("[CAM] 错误: 摄像头未初始化")
            return False

        try:
            camera_http.brightness(brightness)
            print(f"[CAM] 亮度已设置为: {brightness}")
            return True
        except Exception as e:
            print(f"[CAM] 设置亮度失败: {e}")
            return False

    def set_saturation(self, saturation):
        """设置饱和度 (-2 到 +2)"""
        if not self.initialized:
            print("[CAM] 错误: 摄像头未初始化")
            return False

        try:
            camera_http.saturation(saturation)
            print(f"[CAM] 饱和度已设置为: {saturation}")
            return True
        except Exception as e:
            print(f"[CAM] 设置饱和度失败: {e}")
            return False

    def get_status(self):
        """获取摄像头状态"""
        framesize = self.config.get(FRAMESIZE, 0)
        return {
            "initialized": self.initialized,
            "framesize": FRAMESIZE_NAMES.get(framesize, str(framesize)),
            "framesize_code": framesize,
            "quality": self.config.get(JPEG_QUALITY, "unknown"),
            "format": "JPEG",
            "frame_count": self.frame_count,
            "error_count": self.error_count
        }

    def print_status(self):
        """打印摄像头状态"""
        status = self.get_status()
        print("\n" + "=" * 50)
        print("[CAM] 摄像头状态")
        print("=" * 50)
        for key, value in status.items():
            print(f"[CAM]   {key}: {value}")
        print("=" * 50)


def test_camera():
    """测试摄像头"""
    print("\n" + "=" * 50)
    print("摄像头测试")
    print("=" * 50)

    cam = ESP32Camera()

    if cam.init():
        print("\n[CAM] 摄像头初始化成功")

        # 捕获测试帧
        print("\n[CAM] 捕获测试帧...")
        for i in range(5):
            frame = cam.capture_frame()
            if frame:
                print(f"[CAM] 帧 {i+1}: {len(frame)} bytes")
            else:
                print(f"[CAM] 帧 {i+1}: 捕获失败")
            time.sleep(0.1)

        cam.print_status()
        cam.deinit()
    else:
        print("\n[CAM] 摄像头初始化失败")

    print("\n[CAM] 测试完成")


if __name__ == "__main__":
    test_camera()
