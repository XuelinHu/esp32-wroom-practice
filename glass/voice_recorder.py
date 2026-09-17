"""Onboard PDM microphone recorder for XIAO ESP32-S3 Sense.

The pdm_mic module is compiled into the project-specific firmware. It uses the
Sense expansion board microphone on GPIO42 (clock) and GPIO41 (data).
"""

import os
import struct
import time
import pdm_mic

try:
    import _thread
except ImportError:
    _thread = None


VOICE_RATE = 16000
BUFFER_SAMPLES = 256
MAX_SECONDS = 60
CALIBRATION_MS = 500
NOISE_GATE_MIN = 40
NOISE_GATE_MAX = 600
NOISE_GATE_MULTIPLIER = 3
RECORD_DIR = "/recordings"


def signed_i16(buffer, offset):
    value = buffer[offset] | (buffer[offset + 1] << 8)
    return value - 65536 if value & 0x8000 else value


def wav_header(data_bytes):
    return (
        b"RIFF" + struct.pack("<I", 36 + data_bytes) + b"WAVE" +
        b"fmt " + struct.pack(
            "<IHHIIHH", 16, 1, 1, VOICE_RATE,
            VOICE_RATE * 2, 2, 16
        ) +
        b"data" + struct.pack("<I", data_bytes)
    )


class VoiceRecorder:
    def __init__(self, record_dir=RECORD_DIR):
        self.record_dir = record_dir
        self.active = False
        self.stop_requested = False
        self.path = ""
        self.bytes = 0
        self.error = ""

    def _ensure_dir(self):
        try:
            os.mkdir(self.record_dir)
        except OSError:
            pass

    def set_record_dir(self, record_dir):
        if not self.active:
            self.record_dir = record_dir

    def _next_path(self):
        self._ensure_dir()
        now = time.localtime()
        stamp = "%04d%02d%02d_%02d%02d%02d_%03d" % (
            now[0], now[1], now[2], now[3], now[4], now[5],
            time.ticks_ms() % 1000,
        )
        return "%s/record_%s.wav" % (self.record_dir, stamp)

    def status(self):
        return {
            "active": self.active,
            "path": self.path,
            "bytes": self.bytes,
            "error": self.error,
            "rate": VOICE_RATE,
            "format": "16-bit mono WAV",
            "source": "XIAO Sense onboard PDM microphone",
            "storage": self.record_dir,
        }

    def start(self):
        if self.active:
            return self.status()
        if _thread is None:
            self.error = "thread_unavailable"
            return self.status()
        self.active = True
        self.stop_requested = False
        self.path = ""
        self.bytes = 0
        self.error = ""
        try:
            _thread.start_new_thread(self._worker, ())
        except Exception as exc:
            self.active = False
            self.error = str(exc)
        return self.status()

    def stop(self):
        if not self.active:
            return self.status()
        self.stop_requested = True
        return self.status()

    def _process(self, source, target, dc_state, gate):
        peak = 0
        average = 0
        for offset in range(0, len(source), 2):
            sample = signed_i16(source, offset)
            dc = dc_state[0] + ((sample - dc_state[0]) >> 8)
            dc_state[0] = dc
            sample -= dc
            magnitude = sample if sample >= 0 else -sample
            average += magnitude
            peak = max(peak, magnitude)
            if gate and magnitude <= gate:
                sample = 0
            elif gate and magnitude < gate * 2:
                value = (magnitude - gate) * magnitude // gate
                sample = value if sample >= 0 else -value
            if sample < 0:
                sample += 65536
            target[offset] = sample & 0xff
            target[offset + 1] = (sample >> 8) & 0xff
        return peak, average // max(1, len(source) // 2)

    def _worker(self):
        mic = None
        wav = None
        path = ""
        size = 0
        dc_state = [0]
        gate = 0
        calibration = max(1, CALIBRATION_MS // (BUFFER_SAMPLES * 1000 // VOICE_RATE))
        noise = []
        rx = bytearray(BUFFER_SAMPLES * 2)
        processed = bytearray(BUFFER_SAMPLES * 2)
        try:
            mic = pdm_mic.Microphone(sample_rate=VOICE_RATE)
            path = self._next_path()
            self.path = path
            wav = open(path, "wb")
            wav.write(b"\x00" * 44)
            max_bytes = VOICE_RATE * MAX_SECONDS * 2
            print("VOICE_RECORD_STARTED path=%s" % path)
            while size < max_bytes and not self.stop_requested:
                read = mic.readinto(rx)
                if read < len(rx):
                    for index in range(read, len(rx)):
                        rx[index] = 0
                _, average = self._process(rx, processed, dc_state, gate)
                if calibration:
                    noise.append(average)
                    calibration -= 1
                    if not calibration:
                        gate = sum(noise) // len(noise) * NOISE_GATE_MULTIPLIER
                        gate = max(NOISE_GATE_MIN, min(NOISE_GATE_MAX, gate))
                        print("VOICE_GATE %d" % gate)
                wav.write(processed)
                size += len(processed)
                self.bytes = size
            wav.seek(0)
            wav.write(wav_header(size))
            print("VOICE_RECORD_SAVED path=%s bytes=%d" % (path, size))
        except Exception as exc:
            self.error = str(exc)
            print("VOICE_RECORD_FAILED", exc)
            if path:
                try:
                    os.remove(path)
                except OSError:
                    pass
        finally:
            if wav is not None:
                wav.close()
            if mic is not None:
                mic.deinit()
            self.active = False
            print("VOICE_RECORD_RELEASED")

    def recordings(self):
        self._ensure_dir()
        result = []
        for name in os.listdir(self.record_dir):
            if name.lower().endswith(".wav"):
                result.append(name)
        result.sort(reverse=True)
        return result

    def recording_path(self, name):
        return self.record_dir + "/" + name
