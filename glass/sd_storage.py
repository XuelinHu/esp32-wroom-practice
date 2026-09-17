"""MicroSD storage for the XIAO ESP32-S3 Sense expansion board."""

import os

try:
    from machine import SDCard as NativeSDCard, Pin, SPI
except ImportError:
    NativeSDCard = None
    Pin = None
    SPI = None

try:
    from sdcard_spi import SDCard as SPISDCard
except ImportError:
    SPISDCard = None


MOUNT_POINT = "/sd"
RECORDINGS_DIR = MOUNT_POINT + "/recordings"
SD_PINS = (7, 8, 9)
# Sense board revisions in official documentation use GPIO3 or GPIO21 for CS.
SD_OPTIONS = ((3, 3), (3, 21), (2, 3), (2, 21))


class SDStorage:
    def __init__(self):
        self.card = None
        self.mounted = False
        self.error = ""
        self.cs = None
        self.slot = None

    def mount(self):
        if self.mounted:
            return True
        self.error = ""
        if NativeSDCard is None:
            self.error = "sdcard_module_unavailable"
            return False
        if self._mount_spi_driver():
            return True
        spi_error = self.error
        for slot, cs in SD_OPTIONS:
            try:
                card = NativeSDCard(
                    slot=slot,
                    sck=SD_PINS[0],
                    miso=SD_PINS[1],
                    mosi=SD_PINS[2],
                    cs=cs,
                )
                os.mount(card, MOUNT_POINT)
                self.card = card
                self.mounted = True
                self.cs = cs
                self.slot = slot
                self._ensure_recordings_dir()
                print("SD_MOUNTED slot=%d cs=%d" % (slot, cs))
                return True
            except Exception as exc:
                self.error = str(exc)
        if spi_error:
            self.error = spi_error
        print("SD_NOT_AVAILABLE", self.error)
        return False

    def _mount_spi_driver(self):
        if SPISDCard is None or SPI is None:
            return False
        for spi_id in (1, 2):
            for cs in (3, 21):
                spi = None
                try:
                    spi = SPI(
                        spi_id,
                        baudrate=1320000,
                        polarity=0,
                        phase=0,
                        sck=Pin(SD_PINS[0]),
                        miso=Pin(SD_PINS[1]),
                        mosi=Pin(SD_PINS[2]),
                    )
                    card = SPISDCard(spi, Pin(cs, Pin.OUT))
                    os.mount(card, MOUNT_POINT)
                    self.card = card
                    self.mounted = True
                    self.cs = cs
                    self.slot = "spi%d" % spi_id
                    self._ensure_recordings_dir()
                    print("SD_MOUNTED spi=%d cs=%d" % (spi_id, cs))
                    return True
                except Exception as exc:
                    self.error = str(exc)
                    if spi is not None:
                        try:
                            spi.deinit()
                        except Exception:
                            pass
        return False

    def _ensure_recordings_dir(self):
        try:
            os.mkdir(RECORDINGS_DIR)
        except OSError:
            pass

    def recordings_dir(self):
        return RECORDINGS_DIR if self.mounted else "/recordings"

    def status(self):
        if not self.mounted:
            self.mount()
        result = {
            "mounted": self.mounted,
            "mount": MOUNT_POINT,
            "cs": self.cs,
            "slot": self.slot,
            "error": self.error,
        }
        if self.mounted:
            try:
                stat = os.statvfs(MOUNT_POINT)
                result["total"] = stat[0] * stat[2]
                result["free"] = stat[0] * stat[3]
            except OSError:
                pass
        return result

    def test(self):
        if not self.mount():
            return self.status()
        path = MOUNT_POINT + "/.glass_sd_test.txt"
        token = b"glass-sd-read-write-ok\n"
        try:
            with open(path, "wb") as target:
                target.write(token)
            with open(path, "rb") as source:
                valid = source.read() == token
            os.remove(path)
            result = self.status()
            result["test"] = "passed" if valid else "failed"
            return result
        except Exception as exc:
            self.error = str(exc)
            result = self.status()
            result["test"] = "failed"
            return result

    def files(self):
        if not self.mount():
            return []
        result = []
        try:
            for entry in os.ilistdir(MOUNT_POINT):
                name = entry[0]
                if name.startswith("."):
                    continue
                path = MOUNT_POINT + "/" + name
                try:
                    size = os.stat(path)[6]
                except OSError:
                    size = 0
                result.append({"name": name, "size": size, "directory": entry[1] == 0x4000})
        except OSError as exc:
            self.error = str(exc)
        result.sort(key=lambda item: item["name"])
        return result
