"""XIAO ESP32-S3 Sense camera support for OV2640/OV3660."""

import gc
import camera
import struct
from micropython import const

try:
    from camera import Camera as NativeCamera
    from camera import FrameSize, PixelFormat, GrabMode
    NEW_CAMERA_API = True
except ImportError:
    NativeCamera = None
    FrameSize = None
    PixelFormat = None
    GrabMode = None
    NEW_CAMERA_API = False

try:
    import _thread
except ImportError:
    _thread = None

PIN_PWDN = const(0)
PIN_RESET = const(1)
PIN_XCLK = const(2)
PIN_SIOD = const(3)
PIN_SIOC = const(4)
PIN_D7 = const(5)
PIN_D6 = const(6)
PIN_D5 = const(7)
PIN_D4 = const(8)
PIN_D3 = const(9)
PIN_D2 = const(10)
PIN_D1 = const(11)
PIN_D0 = const(12)
PIN_VSYNC = const(13)
PIN_HREF = const(14)
PIN_PCLK = const(15)

XCLK_MHZ = const(16)
PIXFORMAT = const(17)
FRAMESIZE = const(18)
JPEG_QUALITY = const(19)
FB_COUNT = const(20)

PIXFORMAT_JPEG = const(5)
FRAMESIZE_QQVGA = const(5)
FRAMESIZE_QVGA = const(6)
FRAMESIZE_VGA = const(9)
FRAMESIZE_SVGA = const(10)
FRAMESIZE_HD = const(12)
FRAMESIZE_QXGA = const(18)

FRAMESIZES = {
    "160x120": FRAMESIZE_QQVGA,
    "320x240": FRAMESIZE_QVGA,
    "640x480": FRAMESIZE_VGA,
    "800x600": FRAMESIZE_SVGA,
    "1280x720": FRAMESIZE_HD,
    "2048x1536": FRAMESIZE_QXGA,
}

FRAMESIZE_NAMES = {
    FRAMESIZE_QQVGA: "160x120",
    FRAMESIZE_QVGA: "320x240",
    FRAMESIZE_VGA: "640x480",
    FRAMESIZE_SVGA: "800x600",
    FRAMESIZE_HD: "1280x720",
    FRAMESIZE_QXGA: "2048x1536",
}

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
    FRAMESIZE: FRAMESIZE_QQVGA,
    JPEG_QUALITY: 12,
    FB_COUNT: 2,
}

FRAME_DIMENSIONS = {
    "160x120": (160, 120),
    "320x240": (320, 240),
    "640x480": (640, 480),
}

MAX_SENSOR_RESOLUTION = "2048x1536"


class Camera:
    def __init__(self, config=None):
        self.config = dict(config or XIAO_CONFIG)
        self.initialized = False
        self.native = None
        self.frames = 0
        self.errors = 0
        self.lock = _thread.allocate_lock() if _thread is not None else None

    def init(self):
        if self.initialized:
            return True
        if NEW_CAMERA_API:
            try:
                frame_size = {
                    "160x120": getattr(FrameSize, "QQVGA"),
                    "320x240": getattr(FrameSize, "QVGA"),
                    "640x480": getattr(FrameSize, "VGA"),
                    "800x600": getattr(FrameSize, "SVGA"),
                    "1280x720": getattr(FrameSize, "HD"),
                    "2048x1536": getattr(FrameSize, "QXGA"),
                }.get(self.framesize_name(), getattr(FrameSize, "VGA"))
                self.native = NativeCamera(
                    frame_size=frame_size,
                    pixel_format=PixelFormat.RGB565,
                    fb_count=1,
                    grab_mode=getattr(GrabMode, "WHEN_EMPTY"),
                    init=True,
                )
                self.initialized = True
                gc.collect()
                print("CAMERA_READY sensor=%s framesize=%s" % (
                    self.sensor_name(), self.framesize_name()
                ))
                return True
            except Exception as exc:
                self.native = None
                print("CAMERA_INIT_ERROR", exc)
                return False
        for key, value in self.config.items():
            camera.conf(key, value)
        if not camera.init():
            return False
        self.initialized = True
        gc.collect()
        print("CAMERA_READY sensor=auto framesize=%s" % self.framesize_name())
        return True

    def deinit(self):
        if self.initialized:
            if self.native is not None:
                self.native.deinit()
                self.native = None
            else:
                camera.deinit()
            self.initialized = False

    def capture(self):
        if not self.initialized:
            return None
        if self.lock is not None:
            self.lock.acquire()
        try:
            if self.native is not None:
                frame = self.native.capture()
                if frame:
                    frame = self._rgb565_to_bmp(bytes(frame))
                    self.native.free_buffer()
            else:
                frame = camera.capture()
            if frame:
                self.frames += 1
                return frame
            self.errors += 1
        except Exception:
            self.errors += 1
        finally:
            if self.lock is not None:
                self.lock.release()
        return None

    def capture_raw(self):
        if not self.initialized or self.native is None:
            return None
        if self.lock is not None:
            self.lock.acquire()
        try:
            frame = self.native.capture()
            if not frame:
                self.errors += 1
                return None
            data = bytes(frame)
            self.native.free_buffer()
            self.frames += 1
            return data
        except Exception:
            self.errors += 1
            return None
        finally:
            if self.lock is not None:
                self.lock.release()

    def _rgb565_to_bmp(self, raw):
        dimensions = FRAME_DIMENSIONS.get(self.framesize_name())
        if dimensions is None:
            return None
        width, height = dimensions
        if len(raw) != width * height * 2:
            return None
        row_size = width * 3
        total = 54 + row_size * height
        image = bytearray(total)
        struct.pack_into("<2sIHHI", image, 0, b"BM", total, 0, 0, 54)
        struct.pack_into(
            "<IiiHHIIiiII",
            image,
            14,
            40,
            width,
            -height,
            1,
            24,
            0,
            row_size * height,
            0,
            0,
            0,
            0,
        )
        source = 0
        target = 54
        for _ in range(width * height):
            pixel = (raw[source] << 8) | raw[source + 1]
            image[target] = (pixel & 0x1F) << 3
            image[target + 1] = ((pixel >> 5) & 0x3F) << 2
            image[target + 2] = ((pixel >> 11) & 0x1F) << 3
            source += 2
            target += 3
        return bytes(image)

    def set_framesize(self, name):
        value = FRAMESIZES.get(name)
        if value is None or not self.initialized:
            return False
        if self.native is not None and name not in FRAME_DIMENSIONS:
            return False
        if self.lock is not None:
            self.lock.acquire()
        try:
            if self.native is not None:
                frame_size = {
                    "160x120": getattr(FrameSize, "QQVGA"),
                    "320x240": getattr(FrameSize, "QVGA"),
                    "640x480": getattr(FrameSize, "VGA"),
                    "800x600": getattr(FrameSize, "SVGA"),
                    "1280x720": getattr(FrameSize, "HD"),
                    "2048x1536": getattr(FrameSize, "QXGA"),
                }[name]
                self.native.reconfigure(
                    pixel_format=PixelFormat.RGB565,
                    frame_size=frame_size,
                    grab_mode=getattr(GrabMode, "WHEN_EMPTY"),
                    fb_count=1,
                )
            else:
                camera.conf(FRAMESIZE, value)
            self.config[FRAMESIZE] = value
            return True
        finally:
            if self.lock is not None:
                self.lock.release()

    def framesize_name(self):
        return FRAMESIZE_NAMES.get(self.config.get(FRAMESIZE), "unknown")

    def sensor_name(self):
        if self.native is not None:
            try:
                return self.native.get_sensor_name()
            except Exception:
                pass
        return "OV2640/OV3660 auto-detect"

    def content_type(self):
        if self.native is not None:
            return "image/bmp"
        return "image/jpeg"

    def status(self):
        return {
            "ready": self.initialized,
            "sensor": self.sensor_name(),
            "framesize": self.framesize_name(),
            "jpeg_quality": self.config.get(JPEG_QUALITY),
            "format": self.content_type(),
            "max_resolution": MAX_SENSOR_RESOLUTION,
            "stream_limit": "320x240",
            "frames": self.frames,
            "errors": self.errors,
        }
