"""
Camera Setup for ESP32-Cam
鎽勫儚澶村垵濮嬪寲鍜岄厤缃ā鍧?"""

import camera
from micropython import const

# 鎽勫儚澶撮厤缃父閲?PIN_PWDN    = const(0)  # power-down
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

# 鍍忕礌鏍煎紡
PIXFORMAT_RGB565    = const(1)  # 2BPP/RGB565
PIXFORMAT_YUV422    = const(2)  # 2BPP/YUV422
PIXFORMAT_YUV420    = const(3)  # 1.5BPP/YUV420
PIXFORMAT_GRAYSCALE = const(4)  # 1BPP/GRAYSCALE
PIXFORMAT_JPEG      = const(5)  # JPEG/COMPRESSED
PIXFORMAT_RGB888    = const(6)  # 3BPP/RGB888
PIXFORMAT_RAW       = const(7)  # RAW

# 甯у昂瀵?FRAMESIZE_96X96   = const(1)   # 96x96
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

# XIAO ESP32-S3 OV2640鎽勫儚澶撮厤缃?XIAO_CONFIG = {
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
        鍒濆鍖栨憚鍍忓ご

        Args:
            config: 鎽勫儚澶撮厤缃瓧鍏革紝榛樿浣跨敤XIAO閰嶇疆
        """
        self.config = config or XIAO_CONFIG
        self.initialized = False

    def configure(self):
        """Configure camera parameters."""
        try:
            for key, val in self.config.items():
                camera.conf(key, val)
            print("Camera configuration complete")
            return True
        except Exception as e:
            print(f"鎽勫儚澶撮厤缃け璐? {e}")
            return False

    def init(self):
        """鍒濆鍖栨憚鍍忓ご"""
        try:
            # 鍏堥厤缃憚鍍忓ご
            if not self.configure():
                return False

            # 鍒濆鍖栨憚鍍忓ご
            result = camera.init()
            if result:
                self.initialized = True
                print("鎽勫儚澶村垵濮嬪寲鎴愬姛")

                # 璁剧疆榛樿鍙傛暟
                camera.contrast(2)       # 澧炲姞瀵规瘮搴?                camera.brightness(0)     # 浜害
                camera.saturation(0)     # 楗卞拰搴?
                return True
            else:
                print("鎽勫儚澶村垵濮嬪寲澶辫触")
                return False

        except Exception as e:
            print(f"鎽勫儚澶村垵濮嬪寲寮傚父: {e}")
            return False

    def deinit(self):
        """Deinitialize camera."""
        try:
            camera.deinit()
            self.initialized = False
            print("鎽勫儚澶村凡鍏抽棴")
        except Exception as e:
            print(f"鍏抽棴鎽勫儚澶村け璐? {e}")

    def capture_frame(self):
        """Capture one frame."""
        if not self.initialized:
            print("Camera not initialized")
            return None

        try:
            return camera.capture()
        except Exception as e:
            print(f"鎹曡幏鍥惧儚澶辫触: {e}")
            return None

    def set_framesize(self, size):
        """Set frame size."""
        if not self.initialized:
            return False

        try:
            camera.conf(FRAMESIZE, size)
            print(f"甯у昂瀵稿凡璁剧疆涓? {size}")
            return True
        except Exception as e:
            print(f"璁剧疆甯у昂瀵稿け璐? {e}")
            return False

    def set_quality(self, quality):
        """璁剧疆JPEG璐ㄩ噺 (1-31, 鏁板€艰秺灏忚川閲忚秺楂?"""
        if not self.initialized:
            return False

        try:
            camera.conf(JPEG_QUALITY, max(1, min(31, quality)))
            print(f"JPEG璐ㄩ噺宸茶缃负: {quality}")
            return True
        except Exception as e:
            print(f"璁剧疆JPEG璐ㄩ噺澶辫触: {e}")
            return False

    def set_contrast(self, contrast):
        """璁剧疆瀵规瘮搴?(-2 鍒?+2)"""
        if not self.initialized:
            return False

        try:
            camera.contrast(contrast)
            print(f"瀵规瘮搴﹀凡璁剧疆涓? {contrast}")
            return True
        except Exception as e:
            print(f"璁剧疆瀵规瘮搴﹀け璐? {e}")
            return False

    def get_status(self):
        """Get camera status."""
        return {
            "initialized": self.initialized,
            "framesize": self.config.get(FRAMESIZE, "unknown"),
            "quality": self.config.get(JPEG_QUALITY, "unknown"),
            "format": "JPEG"
        }

def configure_camera(cam, config):
    """閰嶇疆鎽勫儚澶寸殑杈呭姪鍑芥暟"""
    for key, val in config.items():
        cam.conf(key, val)
