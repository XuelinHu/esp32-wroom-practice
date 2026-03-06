"""
Camera Setup Module for ESP32-Cam V2
鎽勫儚澶村垵濮嬪寲鍜岄厤缃ā鍧?

鍔熻兘:
1. 鎽勫儚澶寸‖浠堕厤缃?
2. 鍥惧儚鍙傛暟璁剧疆
3. 甯ф崟鑾峰姛鑳?
4. 璇︾粏鏃ュ織杈撳嚭
"""

import camera
from micropython import const
import time
import gc

# 鎽勫儚澶撮厤缃父閲?
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

# 鍍忕礌鏍煎紡
PIXFORMAT_RGB565    = const(1)  # 2BPP/RGB565
PIXFORMAT_YUV422    = const(2)  # 2BPP/YUV422
PIXFORMAT_YUV420    = const(3)  # 1.5BPP/YUV420
PIXFORMAT_GRAYSCALE = const(4)  # 1BPP/GRAYSCALE
PIXFORMAT_JPEG      = const(5)  # JPEG/COMPRESSED
PIXFORMAT_RGB888    = const(6)  # 3BPP/RGB888
PIXFORMAT_RAW       = const(7)  # RAW

# 甯у昂瀵?
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

# 甯у昂瀵稿悕绉版槧灏?
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

# XIAO ESP32-S3 OV2640鎽勫儚澶撮厤缃?
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
        鍒濆鍖栨憚鍍忓ご绫?

        Args:
            config: 鎽勫儚澶撮厤缃瓧鍏革紝榛樿浣跨敤XIAO閰嶇疆
        """
        self.config = config or XIAO_CONFIG
        self.initialized = False
        self.frame_count = 0
        self.error_count = 0

        print("[CAM] 鎽勫儚澶存ā鍧楀垵濮嬪寲")
        print(f"[CAM] 閰嶇疆淇℃伅:")
        print(f"[CAM]   甯у昂瀵? {FRAMESIZE_NAMES.get(self.config.get(FRAMESIZE), 'unknown')}")
        print(f"[CAM]   JPEG璐ㄩ噺: {self.config.get(JPEG_QUALITY)}")
        print(f"[CAM]   甯х紦鍐叉暟: {self.config.get(FB_COUNT)}")

    def configure(self):
        """Configure camera parameters."""
        print("[CAM] 寮€濮嬮厤缃憚鍍忓ご鍙傛暟...")

        try:
            for key, val in self.config.items():
                try:
                    camera.conf(key, val)
                    print(f"[CAM]   閰嶇疆椤?{key} = {val}")
                except Exception as e:
                    print(f"[CAM]   閰嶇疆椤?{key} = {val} 澶辫触: {e}")

            print("[CAM] Camera parameter configuration complete")
            return True

        except Exception as e:
            print(f"[CAM] 鎽勫儚澶撮厤缃け璐? {e}")
            return False

    def init(self):
        """鍒濆鍖栨憚鍍忓ご"""
        print("\n" + "=" * 50)
        print("[CAM] 寮€濮嬪垵濮嬪寲鎽勫儚澶?..")
        print("=" * 50)

        # 鍏堥厤缃憚鍍忓ご
        if not self.configure():
            print("[CAM] 閰嶇疆澶辫触锛屾棤娉曞垵濮嬪寲")
            return False

        # 鍒濆鍖栨憚鍍忓ご
        print("[CAM] 璋冪敤 camera.init()...")
        try:
            result = camera.init()
            print(f"[CAM] camera.init() 杩斿洖鍊? {result}")

            if result:
                self.initialized = True
                print("[CAM] 鎽勫儚澶村垵濮嬪寲鎴愬姛!")

                # 璁剧疆榛樿鍙傛暟
                print("[CAM] 璁剧疆榛樿鍥惧儚鍙傛暟...")
                try:
                    camera.contrast(2)       # 澧炲姞瀵规瘮搴?
                    print("[CAM]   瀵规瘮搴? 2")
                    camera.brightness(0)     # 浜害
                    print("[CAM]   浜害: 0")
                    camera.saturation(0)     # 楗卞拰搴?
                    print("[CAM]   楗卞拰搴? 0")
                except Exception as e:
                    print(f"[CAM] 璁剧疆鍥惧儚鍙傛暟澶辫触: {e}")

                # 娓呯悊鍐呭瓨
                gc.collect()
                print(f"[CAM] 鍙敤鍐呭瓨: {gc.mem_free()} bytes")

                return True
            else:
                print("[CAM] 鎽勫儚澶村垵濮嬪寲澶辫触 (杩斿洖False)")
                return False

        except Exception as e:
            print(f"[CAM] 鎽勫儚澶村垵濮嬪寲寮傚父: {e}")
            import sys
            sys.print_exception(e)
            return False

    def deinit(self):
        """Deinitialize camera."""
        print("[CAM] 鍏抽棴鎽勫儚澶?..")

        try:
            camera.deinit()
            self.initialized = False
            print("[CAM] 鎽勫儚澶村凡鍏抽棴")
        except Exception as e:
            print(f"[CAM] 鍏抽棴鎽勫儚澶村け璐? {e}")

    def capture_frame(self):
        """Capture one frame."""
        if not self.initialized:
            print("[CAM] Error: camera not initialized")
            return None

        try:
            start_time = time.ticks_ms()
            frame = camera.capture()
            elapsed = time.ticks_diff(time.ticks_ms(), start_time)

            if frame:
                self.frame_count += 1
                frame_size = len(frame)
                # 姣?00甯ф墦鍗颁竴娆＄姸鎬?
                if self.frame_count % 100 == 0:
                    print(f"[CAM] 宸叉崟鑾?{self.frame_count} 甯? "
                          f"褰撳墠甯уぇ灏? {frame_size} bytes, "
                          f"鑰楁椂: {elapsed}ms, "
                          f"閿欒: {self.error_count}")
                return frame
            else:
                self.error_count += 1
                print(f"[CAM] 鎹曡幏鍥惧儚澶辫触 (绌哄抚), 閿欒璁℃暟: {self.error_count}")
                return None

        except Exception as e:
            self.error_count += 1
            print(f"[CAM] 鎹曡幏鍥惧儚寮傚父: {e}, 閿欒璁℃暟: {self.error_count}")
            return None

    def set_framesize(self, size):
        """Set frame size."""
        if not self.initialized:
            print("[CAM] Error: camera not initialized")
            return False

        try:
            camera.conf(FRAMESIZE, size)
            size_name = FRAMESIZE_NAMES.get(size, str(size))
            print(f"[CAM] 甯у昂瀵稿凡璁剧疆涓? {size_name}")
            return True
        except Exception as e:
            print(f"[CAM] 璁剧疆甯у昂瀵稿け璐? {e}")
            return False

    def set_quality(self, quality):
        """璁剧疆JPEG璐ㄩ噺 (1-31, 鏁板€艰秺灏忚川閲忚秺楂?"""
        if not self.initialized:
            print("[CAM] Error: camera not initialized")
            return False

        try:
            quality = max(1, min(31, quality))
            camera.conf(JPEG_QUALITY, quality)
            print(f"[CAM] JPEG璐ㄩ噺宸茶缃负: {quality}")
            return True
        except Exception as e:
            print(f"[CAM] 璁剧疆JPEG璐ㄩ噺澶辫触: {e}")
            return False

    def set_contrast(self, contrast):
        """璁剧疆瀵规瘮搴?(-2 鍒?+2)"""
        if not self.initialized:
            print("[CAM] Error: camera not initialized")
            return False

        try:
            camera.contrast(contrast)
            print(f"[CAM] 瀵规瘮搴﹀凡璁剧疆涓? {contrast}")
            return True
        except Exception as e:
            print(f"[CAM] 璁剧疆瀵规瘮搴﹀け璐? {e}")
            return False

    def set_brightness(self, brightness):
        """璁剧疆浜害 (-2 鍒?+2)"""
        if not self.initialized:
            print("[CAM] Error: camera not initialized")
            return False

        try:
            camera.brightness(brightness)
            print(f"[CAM] 浜害宸茶缃负: {brightness}")
            return True
        except Exception as e:
            print(f"[CAM] 璁剧疆浜害澶辫触: {e}")
            return False

    def set_saturation(self, saturation):
        """璁剧疆楗卞拰搴?(-2 鍒?+2)"""
        if not self.initialized:
            print("[CAM] Error: camera not initialized")
            return False

        try:
            camera.saturation(saturation)
            print(f"[CAM] 楗卞拰搴﹀凡璁剧疆涓? {saturation}")
            return True
        except Exception as e:
            print(f"[CAM] 璁剧疆楗卞拰搴﹀け璐? {e}")
            return False

    def get_status(self):
        """Get camera status."""
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
        """Print camera status."""
        status = self.get_status()
        print("\n" + "=" * 50)
        print("[CAM] Camera status")
        print("=" * 50)
        for key, value in status.items():
            print(f"[CAM]   {key}: {value}")
        print("=" * 50)


def test_camera():
    """Test camera."""
    print("\n" + "=" * 50)
    print("Camera test")
    print("=" * 50)

    cam = ESP32Camera()

    if cam.init():
        print("\n[CAM] 鎽勫儚澶村垵濮嬪寲鎴愬姛")

        # 鎹曡幏娴嬭瘯甯?
        print("\n[CAM] 鎹曡幏娴嬭瘯甯?..")
        for i in range(5):
            frame = cam.capture_frame()
            if frame:
                print(f"[CAM] 甯?{i+1}: {len(frame)} bytes")
            else:
                print(f"[CAM] 甯?{i+1}: 鎹曡幏澶辫触")
            time.sleep(0.1)

        cam.print_status()
        cam.deinit()
    else:
        print("\n[CAM] 鎽勫儚澶村垵濮嬪寲澶辫触")

    print("\n[CAM] 娴嬭瘯瀹屾垚")


if __name__ == "__main__":
    test_camera()
