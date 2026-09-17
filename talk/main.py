# ESP32 audio test menu.
# 1: speaker tone, 2: looping ABC melody, 3: record and replay speech.

import math
import json
import os
import socket
import struct
import time
import network
from machine import I2S, Pin, SoftI2C

try:
    import ntptime
except ImportError:
    ntptime = None

try:
    import _thread
except ImportError:
    _thread = None

try:
    from ssd1306 import SSD1306_I2C
except ImportError:
    SSD1306_I2C = None


# Shared hardware pins.
MIC_BCLK = 26
MIC_WS = 25
MIC_SD = 33
AMP_BCLK = 18
AMP_LRC = 19
AMP_DIN = 23
AMP_SD = 27
OLED_SCL = 21
OLED_SDA = 22
OLED_ADDR = 0x3C
OLED_WIDTH = 128
OLED_HEIGHT = 32

# Voice audio settings.
VOICE_RATE = 8000
BUFFER_SAMPLES = 256
# MicroPython converts the INMP441 stream to signed 16-bit mono samples.
MIC_FRAME_BYTES = 2
VOICE_START_THRESHOLD = 2500
VOICE_SILENCE_THRESHOLD = 1200
MIN_RECORD_MS = 300
SILENCE_MS = 1000
MAX_RECORD_SECONDS = 30
NOISE_CALIBRATION_MS = 500
MIN_NOISE_GATE = 40
MAX_NOISE_GATE = 600
NOISE_GATE_MULTIPLIER = 3
RECORD_DIR = "/recordings"

# Default home Wi-Fi. Do not print the password to the console.
WIFI_SSID = "ChinaNet-E5y7"
WIFI_PASSWORD = "zadyx5cc"
WIFI_TIMEOUT_MS = 15000
WEB_PORT = 80
WEB_DIR = "/web"
WEB_RECORD_MAX_SECONDS = 60
TIMEZONE_OFFSET_SECONDS = 8 * 60 * 60

web_recording_active = False
web_record_stop_requested = False
web_record_path = ""
web_record_bytes = 0
web_record_error = ""
web_playing_active = False
web_play_stop_requested = False
web_play_path = ""
web_play_error = ""
web_abc_active = False
web_abc_stop_requested = False
web_abc_error = ""

# Tone and ABC song settings.
TONE_RATE = 8000
TONE_AMPLITUDE = 9000
PLAYBACK_GAIN_PERCENT = 220
TONE_HZ = 880
ABC_TEMPO_BPM = 100
ABC_BEAT_MS = 60000 // ABC_TEMPO_BPM

ABC_MELODY = (
    ("C4", 1), ("C4", 1), ("G4", 1), ("G4", 1),
    ("A4", 1), ("A4", 1), ("G4", 2),
    ("F4", 1), ("F4", 1), ("E4", 1), ("E4", 1),
    ("D4", 1), ("D4", 1), ("C4", 2),
    ("G4", 1), ("G4", 1), ("F4", 1), ("F4", 1),
    ("E4", 1), ("E4", 1), ("D4", 2),
    ("C4", 1), ("C4", 1), ("G4", 1), ("G4", 1),
    ("A4", 1), ("A4", 1), ("G4", 2),
    ("F4", 1), ("F4", 1), ("E4", 1), ("E4", 1),
    ("D4", 1), ("D4", 1), ("C4", 2),
)

NOTE_HZ = {
    "C4": 262,
    "D4": 294,
    "E4": 330,
    "F4": 349,
    "G4": 392,
    "A4": 440,
}


def init_oled():
    if SSD1306_I2C is None:
        print("OLED driver missing; serial menu remains available")
        return None
    try:
        # Skip a bus that is already held low. Audio must remain usable.
        scl_probe = Pin(OLED_SCL, Pin.IN, Pin.PULL_UP)
        sda_probe = Pin(OLED_SDA, Pin.IN, Pin.PULL_UP)
        time.sleep_ms(20)
        if scl_probe.value() == 0 or sda_probe.value() == 0:
            print("OLED bus low; display disabled for this boot")
            return None

        i2c = SoftI2C(
            scl=Pin(OLED_SCL),
            sda=Pin(OLED_SDA),
            freq=100000,
            timeout=50000,
        )
        devices = i2c.scan()
        print("I2C devices:", [hex(x) for x in devices])
        if OLED_ADDR not in devices:
            print("OLED 0x3C not found; serial menu remains available")
            return None
        return SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, addr=OLED_ADDR)
    except Exception as exc:
        print("OLED disabled:", exc)
        return None


def show_state(display, title, detail=""):
    if display is None:
        return
    display.fill(0)
    display.big_text(title, 0, 0, scale=2)
    if detail:
        display.text(detail, 0, 24)
    display.show()


def show_hello_world(display):
    if display is None:
        return
    display.fill(0)
    display.big_text("HELLO", 0, 0, scale=2)
    display.big_text("WORLD", 0, 16, scale=2)
    display.show()


def show_wifi(display, ip):
    if display is None:
        return
    display.fill(0)
    display.big_text("WIFI", 0, 0, scale=2)
    display.text(ip, 0, 24)
    display.show()


def show_idle(display, ip):
    if ip:
        show_wifi(display, ip)
    else:
        show_hello_world(display)


def sync_clock():
    if ntptime is None:
        print("NTP_SYNC_UNAVAILABLE")
        return False
    try:
        ntptime.settime()
        print("NTP_SYNC_OK")
        return True
    except Exception as exc:
        print("NTP_SYNC_FAILED", exc)
        return False


def wifi_connect(display):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("WIFI_CONNECTING ssid=%s" % WIFI_SSID)
        try:
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        except Exception as exc:
            print("WIFI_CONNECT_FAILED", exc)
            return None
        deadline = time.ticks_add(time.ticks_ms(), WIFI_TIMEOUT_MS)
        while not wlan.isconnected():
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                print("WIFI_CONNECT_FAILED timeout")
                return None
            time.sleep_ms(250)
    sync_clock()
    ip = wlan.ifconfig()[0]
    print("WIFI_CONNECTED")
    print("WIFI_IP", ip)
    show_wifi(display, ip)
    return ip


def recording_sort_key(name):
    stem = name.rsplit(".", 1)[0]
    if stem.startswith("record_"):
        return "1" + stem
    return "0" + stem


def recording_names():
    try:
        names = os.listdir(RECORD_DIR)
    except OSError:
        return []
    result = []
    for name in names:
        lower = name.lower()
        if lower.endswith(".wav") or lower.endswith(".mp3"):
            result.append(name)
    result.sort(key=recording_sort_key, reverse=True)
    return result


def send_all(client, data):
    view = memoryview(data)
    while len(view):
        sent = client.send(view)
        if not sent:
            break
        view = view[sent:]


def content_type(path):
    lower = path.lower()
    if lower.endswith(".html"):
        return "text/html; charset=utf-8"
    if lower.endswith(".json"):
        return "application/json; charset=utf-8"
    if lower.endswith(".mp3"):
        return "audio/mpeg"
    if lower.endswith(".wav"):
        return "audio/wav"
    return "application/octet-stream"


def send_file(client, path):
    try:
        size = os.stat(path)[6]
        file_obj = open(path, "rb")
    except OSError:
        send_all(client, b"HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n")
        return
    header = (
        "HTTP/1.1 200 OK\r\nContent-Type: %s\r\nContent-Length: %d\r\n"
        "Connection: close\r\n\r\n" % (content_type(path), size)
    )
    try:
        send_all(client, header.encode())
        while True:
            data = file_obj.read(1024)
            if not data:
                break
            send_all(client, data)
    finally:
        file_obj.close()


def http_error(client, status):
    body = ("%s\n" % status).encode()
    header = (
        "HTTP/1.1 %s\r\nContent-Type: text/plain\r\nContent-Length: %d\r\n"
        "Connection: close\r\n\r\n" % (status, len(body))
    ).encode()
    send_all(client, header + body)


def send_json(client, status, payload):
    body = json.dumps(payload).encode()
    header = (
        "HTTP/1.1 %s\r\nContent-Type: application/json; charset=utf-8\r\n"
        "Content-Length: %d\r\nConnection: close\r\n\r\n" %
        (status, len(body))
    ).encode()
    send_all(client, header + body)


def handle_http(client):
    request = client.recv(1024)
    if not request:
        return
    first_line = request.split(b"\r\n", 1)[0].split()
    if len(first_line) < 2:
        http_error(client, "400 Bad Request")
        return
    path = first_line[1].decode().split("?", 1)[0]
    if path == "/":
        send_file(client, WEB_DIR + "/index.html")
    elif path == "/api/list":
        send_json(client, "200 OK", recording_names())
    elif path == "/api/record/start":
        result = start_web_recording()
        if result.get("ok"):
            send_json(client, "200 OK", result)
        elif result.get("error") == "already_recording":
            send_json(client, "409 Conflict", result)
        else:
            send_json(client, "500 Internal Server Error", result)
    elif path == "/api/record/stop":
        result = stop_web_recording()
        send_json(client, "200 OK" if result.get("ok") else "409 Conflict", result)
    elif path == "/api/record/status":
        send_json(client, "200 OK", web_record_status())
    elif path.startswith("/api/play/start/"):
        name = path[len("/api/play/start/"):]
        if "/" in name or "\\" in name or ".." in name:
            http_error(client, "403 Forbidden")
            return
        result = start_web_playback(name)
        if result.get("ok"):
            send_json(client, "200 OK", result)
        elif result.get("error") == "already_playing":
            send_json(client, "409 Conflict", result)
        elif result.get("error") == "not_found":
            send_json(client, "404 Not Found", result)
        else:
            send_json(client, "500 Internal Server Error", result)
    elif path == "/api/play/stop":
        result = stop_web_playback()
        send_json(client, "200 OK" if result.get("ok") else "409 Conflict", result)
    elif path == "/api/play/status":
        send_json(client, "200 OK", web_play_status())
    elif path == "/api/abc/start":
        result = start_web_abc()
        if result.get("ok"):
            send_json(client, "200 OK", result)
        elif result.get("error") in ("already_playing", "recording_active"):
            send_json(client, "409 Conflict", result)
        else:
            send_json(client, "500 Internal Server Error", result)
    elif path == "/api/abc/stop":
        result = stop_web_abc()
        send_json(client, "200 OK" if result.get("ok") else "409 Conflict", result)
    elif path == "/api/abc/status":
        send_json(client, "200 OK", web_abc_status())
    elif path.startswith("/recordings/"):
        name = path[len("/recordings/"):]
        if "/" in name or "\\" in name or ".." in name:
            http_error(client, "403 Forbidden")
            return
        send_file(client, RECORD_DIR + "/" + name)
    else:
        http_error(client, "404 Not Found")


def web_server():
    server = socket.socket()
    try:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", WEB_PORT))
        server.listen(2)
        print("WEB_SERVER_STARTED port=%d" % WEB_PORT)
        while True:
            try:
                client, address = server.accept()
            except OSError:
                continue
            try:
                client.settimeout(5)
                handle_http(client)
            except Exception as exc:
                print("WEB_REQUEST_FAILED", exc)
            finally:
                client.close()
    except Exception as exc:
        print("WEB_SERVER_FAILED", exc)
    finally:
        server.close()


def start_web_server(ip):
    if _thread is None:
        print("WEB_SERVER_FAILED _thread unavailable")
        return
    try:
        _thread.start_new_thread(web_server, ())
        print("WEB_URL http://%s/" % ip)
    except Exception as exc:
        print("WEB_SERVER_FAILED", exc)


def oled_test(display):
    if display is None:
        print("OLED_TEST_FAIL")
        print("Check OLED VCC=3V3, GND, SCK=GPIO21, SDA=GPIO22")
        return
    display.fill(0)
    display.big_text("OLED", 0, 0, scale=2)
    display.text("DISPLAY OK", 0, 24)
    display.show()
    print("OLED_TEST_OK: DISPLAY OK")
    time.sleep_ms(5000)
    show_hello_world(display)


def signed_i16(buf, offset):
    value = buf[offset] | (buf[offset + 1] << 8)
    if value & 0x8000:
        value -= 0x10000
    return value


def convert_samples(rx_buf, tx_buf, dc_state=None, noise_gate=0):
    peak = 0
    magnitude_total = 0
    out = 0
    for frame_offset in range(0, len(rx_buf), MIC_FRAME_BYTES):
        sample = signed_i16(rx_buf, frame_offset)

        if dc_state is not None:
            dc = dc_state[0]
            dc += (sample - dc) >> 8
            dc_state[0] = dc
            sample -= dc

        magnitude = sample if sample >= 0 else -sample
        magnitude_total += magnitude
        if magnitude > peak:
            peak = magnitude
        if noise_gate and magnitude <= noise_gate:
            sample = 0
        elif noise_gate and magnitude < noise_gate * 2:
            reduced = (magnitude - noise_gate) * magnitude // noise_gate
            sample = reduced if sample >= 0 else -reduced
        if sample < 0:
            sample += 65536
        tx_buf[out] = sample & 0xFF
        tx_buf[out + 1] = (sample >> 8) & 0xFF
        out += 2
    return peak, magnitude_total // (len(rx_buf) // MIC_FRAME_BYTES)


def init_amp(rate=TONE_RATE):
    return I2S(
        1,
        sck=Pin(AMP_BCLK),
        ws=Pin(AMP_LRC),
        sd=Pin(AMP_DIN),
        mode=I2S.TX,
        bits=16,
        format=I2S.STEREO,
        rate=rate,
        ibuf=8000,
    )


def make_sine_buffer(freq, sample_count, phase=0.0):
    buf = bytearray(sample_count * 4)
    step = 2 * math.pi * freq / TONE_RATE
    for index in range(sample_count):
        value = int(math.sin(phase + step * index) * TONE_AMPLITUDE)
        if value < 0:
            value += 65536
        offset = index * 4
        low = value & 0xFF
        high = (value >> 8) & 0xFF
        buf[offset] = low
        buf[offset + 1] = high
        buf[offset + 2] = low
        buf[offset + 3] = high
    return buf


def mono_to_stereo(mono, stereo, size):
    out = 0
    for offset in range(0, size - 1, 2):
        sample = signed_i16(mono, offset)
        sample = sample * PLAYBACK_GAIN_PERCENT // 100
        if sample > 32767:
            sample = 32767
        elif sample < -32768:
            sample = -32768
        if sample < 0:
            sample += 65536
        low = sample & 0xFF
        high = (sample >> 8) & 0xFF
        stereo[out] = low
        stereo[out + 1] = high
        stereo[out + 2] = low
        stereo[out + 3] = high
        out += 4
    return out


def play_tone(display):
    show_state(display, "TONE", "880HZ 3 SEC")
    enable = Pin(AMP_SD, Pin.OUT, value=0)
    amp = None
    try:
        amp = init_amp()
        enable.value(1)
        print("TONE_START 880Hz 3sec")
        phase = 0.0
        total = TONE_RATE * 3
        sent = 0
        while sent < total:
            count = 256 if total - sent >= 256 else total - sent
            amp.write(make_sine_buffer(TONE_HZ, count, phase))
            phase += 2 * math.pi * TONE_HZ * count / TONE_RATE
            sent += count
        print("TONE_DONE")
    finally:
        enable.value(0)
        if amp is not None:
            amp.deinit()
        print("AMP_MUTED")
        show_state(display, "DONE", "AMP MUTED")


def play_note(amp, note, beats):
    total = TONE_RATE * ABC_BEAT_MS * beats // 1000
    sent = 0
    phase = 0.0
    freq = NOTE_HZ[note]
    while sent < total:
        count = 256 if total - sent >= 256 else total - sent
        amp.write(make_sine_buffer(freq, count, phase))
        phase += 2 * math.pi * freq * count / TONE_RATE
        sent += count


def play_abc(display):
    show_state(display, "ABC", "CTRL-C STOP")
    enable = Pin(AMP_SD, Pin.OUT, value=0)
    amp = None
    try:
        amp = init_amp()
        enable.value(1)
        print("ABC_START tempo=%d" % ABC_TEMPO_BPM)
        print("ABC_WIRING BCLK=18 LRC=19 DIN=23 SD_EN=27")
        loop = 0
        while True:
            loop += 1
            print("ABC_LOOP", loop)
            for note, beats in ABC_MELODY:
                print("NOTE", note, "BEATS", beats)
                play_note(amp, note, beats)
            time.sleep_ms(200)
    except KeyboardInterrupt:
        print("ABC_STOP")
    finally:
        enable.value(0)
        if amp is not None:
            amp.deinit()
        print("AMP_MUTED")
        show_hello_world(display)


def ensure_record_dir():
    try:
        os.mkdir(RECORD_DIR)
    except OSError:
        pass


def next_record_path():
    ensure_record_dir()
    now = time.localtime(time.time() + TIMEZONE_OFFSET_SECONDS)
    stamp = (
        "%04d%02d%02d_%02d%02d%02d_%03d" %
        (now[0], now[1], now[2], now[3], now[4], now[5],
         time.ticks_ms() % 1000)
    )
    return "%s/record_%s.wav" % (RECORD_DIR, stamp)


def wav_header(data_bytes):
    return (
        b"RIFF" + struct.pack("<I", 36 + data_bytes) + b"WAVE" +
        b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, VOICE_RATE,
                              VOICE_RATE * 2, 2, 16) +
        b"data" + struct.pack("<I", data_bytes)
    )


def web_record_status():
    return {
        "ok": web_record_error == "",
        "active": web_recording_active,
        "path": web_record_path,
        "bytes": web_record_bytes,
        "error": web_record_error,
    }


def web_record_worker():
    global web_recording_active
    global web_record_path, web_record_bytes, web_record_error

    rx_buf = bytearray(BUFFER_SAMPLES * MIC_FRAME_BYTES)
    tx_buf = bytearray(BUFFER_SAMPLES * 2)
    mic = None
    wav = None
    size = 0
    path = ""
    dc_state = [0]
    noise_peaks = []
    noise_gate = 0
    calibration_chunks = max(1, NOISE_CALIBRATION_MS //
                             (BUFFER_SAMPLES * 1000 // VOICE_RATE))
    try:
        mic = I2S(
            0,
            sck=Pin(MIC_BCLK),
            ws=Pin(MIC_WS),
            sd=Pin(MIC_SD),
            mode=I2S.RX,
            bits=16,
            format=I2S.MONO,
            rate=VOICE_RATE,
            ibuf=8000,
        )
        path = next_record_path()
        web_record_path = path
        wav = open(path, "wb")
        wav.write(b"\x00" * 44)
        max_bytes = VOICE_RATE * WEB_RECORD_MAX_SECONDS * 2
        print("WEB_RECORD_STARTED path=%s" % path)

        while size < max_bytes and not web_record_stop_requested:
            mic.readinto(rx_buf)
            peak, average = convert_samples(
                rx_buf, tx_buf, dc_state, noise_gate
            )
            if calibration_chunks > 0:
                noise_peaks.append(average)
                calibration_chunks -= 1
                if calibration_chunks == 0:
                    noise_floor = sum(noise_peaks) // len(noise_peaks)
                    noise_gate = noise_floor * NOISE_GATE_MULTIPLIER
                    if noise_gate < MIN_NOISE_GATE:
                        noise_gate = MIN_NOISE_GATE
                    elif noise_gate > MAX_NOISE_GATE:
                        noise_gate = MAX_NOISE_GATE
                    print("MIC_NOISE_CALIBRATION floor=%d gate=%d" %
                          (noise_floor, noise_gate))
            wav.write(tx_buf)
            size += len(tx_buf)
            web_record_bytes = size

        wav.seek(0)
        wav.write(wav_header(size))
        print("WEB_RECORD_SAVED path=%s bytes=%d" % (path, size))
    except Exception as exc:
        web_record_error = str(exc)
        print("WEB_RECORD_FAILED", exc)
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
        web_recording_active = False
        print("WEB_RECORD_RESOURCES_RELEASED")


def web_play_status():
    return {
        "ok": web_play_error == "",
        "active": web_playing_active,
        "path": web_play_path,
        "error": web_play_error,
    }


def web_play_worker(path):
    global web_playing_active, web_play_error

    amp = None
    enable = Pin(AMP_SD, Pin.OUT, value=0)
    wav = None
    try:
        wav = open(path, "rb")
        header = wav.read(44)
        if len(header) != 44 or header[0:4] != b"RIFF":
            raise ValueError("invalid WAV file")
        channels = header[22] | (header[23] << 8)
        sample_rate = (header[24] | (header[25] << 8) |
                       (header[26] << 16) | (header[27] << 24))
        sample_bits = header[34] | (header[35] << 8)
        if channels != 1 or sample_bits != 16:
            raise ValueError("only 16-bit mono WAV is supported")
        amp = init_amp(sample_rate)
        enable.value(1)
        print("WEB_PLAY_STARTED path=%s rate=%d gain=%d%%" %
              (path, sample_rate, PLAYBACK_GAIN_PERCENT))
        mono = bytearray(1024)
        stereo = bytearray(2048)
        while not web_play_stop_requested:
            size = wav.readinto(mono)
            if not size:
                break
            stereo_size = mono_to_stereo(mono, stereo, size)
            amp.write(memoryview(stereo)[:stereo_size])
        print("WEB_PLAY_DONE path=%s" % path)
    except Exception as exc:
        web_play_error = str(exc)
        print("WEB_PLAY_FAILED", exc)
    finally:
        enable.value(0)
        if wav is not None:
            wav.close()
        if amp is not None:
            amp.deinit()
        web_playing_active = False
        print("WEB_PLAY_RESOURCES_RELEASED")


def web_abc_status():
    return {
        "ok": web_abc_error == "",
        "active": web_abc_active,
        "error": web_abc_error,
    }


def web_abc_worker():
    global web_abc_active, web_abc_error

    amp = None
    enable = Pin(AMP_SD, Pin.OUT, value=0)
    try:
        amp = init_amp()
        enable.value(1)
        print("WEB_ABC_STARTED")
        loop = 0
        while not web_abc_stop_requested:
            loop += 1
            print("WEB_ABC_LOOP", loop)
            for note, beats in ABC_MELODY:
                if web_abc_stop_requested:
                    break
                play_note(amp, note, beats)
            time.sleep_ms(100)
        print("WEB_ABC_STOPPED")
    except Exception as exc:
        web_abc_error = str(exc)
        print("WEB_ABC_FAILED", exc)
    finally:
        enable.value(0)
        if amp is not None:
            amp.deinit()
        web_abc_active = False
        print("WEB_ABC_RESOURCES_RELEASED")


def start_web_abc():
    global web_abc_active, web_abc_stop_requested, web_abc_error

    if web_recording_active:
        return {"ok": False, "active": False, "error": "recording_active"}
    if web_playing_active or web_abc_active:
        return {"ok": False, "active": True, "error": "already_playing"}
    if _thread is None:
        return {"ok": False, "active": False, "error": "thread_unavailable"}

    web_abc_active = True
    web_abc_stop_requested = False
    web_abc_error = ""
    try:
        _thread.start_new_thread(web_abc_worker, ())
    except Exception as exc:
        web_abc_active = False
        web_abc_error = str(exc)
        return {"ok": False, "active": False, "error": web_abc_error}
    print("WEB_ABC_START_REQUEST")
    return web_abc_status()


def stop_web_abc():
    global web_abc_stop_requested
    if not web_abc_active:
        return {"ok": False, "active": False, "error": "not_playing"}
    web_abc_stop_requested = True
    print("WEB_ABC_STOP_REQUEST")
    return {"ok": True, "active": True, "stopping": True}


def start_web_playback(name):
    global web_playing_active, web_play_stop_requested
    global web_play_path, web_play_error

    if not name.lower().endswith(".wav"):
        return {"ok": False, "active": False, "error": "wav_only"}
    if web_recording_active:
        return {"ok": False, "active": False, "error": "recording_active"}
    if web_playing_active or web_abc_active:
        return {"ok": False, "active": True, "error": "already_playing"}

    path = RECORD_DIR + "/" + name
    try:
        os.stat(path)
    except OSError:
        return {"ok": False, "active": False, "error": "not_found"}
    if _thread is None:
        return {"ok": False, "active": False, "error": "thread_unavailable"}

    web_playing_active = True
    web_play_stop_requested = False
    web_play_path = path
    web_play_error = ""
    try:
        _thread.start_new_thread(web_play_worker, (path,))
    except Exception as exc:
        web_playing_active = False
        web_play_error = str(exc)
        return {"ok": False, "active": False, "error": web_play_error}
    print("WEB_PLAY_START_REQUEST path=%s" % path)
    return web_play_status()


def stop_web_playback():
    global web_play_stop_requested
    if not web_playing_active:
        return {"ok": False, "active": False, "error": "not_playing"}
    web_play_stop_requested = True
    print("WEB_PLAY_STOP_REQUEST")
    return {"ok": True, "active": True, "stopping": True}


def start_web_recording():
    global web_recording_active, web_record_stop_requested
    global web_record_path, web_record_bytes, web_record_error

    if web_recording_active:
        return {"ok": False, "active": True, "error": "already_recording"}
    if web_playing_active or web_abc_active:
        return {"ok": False, "active": False, "error": "playback_active"}
    if _thread is None:
        return {"ok": False, "active": False, "error": "thread_unavailable"}

    ensure_record_dir()
    web_recording_active = True
    web_record_stop_requested = False
    web_record_path = ""
    web_record_bytes = 0
    web_record_error = ""
    try:
        _thread.start_new_thread(web_record_worker, ())
    except Exception as exc:
        web_recording_active = False
        web_record_error = str(exc)
        return {"ok": False, "active": False, "error": web_record_error}
    print("WEB_RECORD_START_REQUEST")
    return web_record_status()


def stop_web_recording():
    global web_record_stop_requested
    if not web_recording_active:
        return {"ok": False, "active": False, "error": "not_recording"}
    web_record_stop_requested = True
    print("WEB_RECORD_STOP_REQUEST")
    return {"ok": True, "active": True, "stopping": True}


def record_phrase(mic, rx_buf, tx_buf, display):
    show_state(display, "READY", "SPEAK NOW")
    print("SPEAK NOW")
    dc_state = [0]
    deadline = time.ticks_add(time.ticks_ms(), 10000)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        mic.readinto(rx_buf)
        peak, _ = convert_samples(rx_buf, tx_buf, dc_state)
        if peak >= VOICE_START_THRESHOLD:
            break
    else:
        print("VOICE_TIMEOUT")
        return 0

    show_state(display, "RECORD", "SILENCE END")
    print("LISTENING")
    path = next_record_path()
    wav = open(path, "wb")
    wav.write(b"\x00" * 44)
    size = 0
    silence_ms = 0
    chunk_ms = BUFFER_SAMPLES * 1000 // VOICE_RATE
    min_bytes = VOICE_RATE * MIN_RECORD_MS // 1000 * 2
    max_bytes = VOICE_RATE * MAX_RECORD_SECONDS * 2

    try:
        while size < max_bytes:
            wav.write(tx_buf)
            size += len(tx_buf)
            if peak < VOICE_SILENCE_THRESHOLD:
                silence_ms += chunk_ms
            else:
                silence_ms = 0
            if size >= min_bytes and silence_ms >= SILENCE_MS:
                break
            mic.readinto(rx_buf)
        peak, _ = convert_samples(rx_buf, tx_buf, dc_state)
        wav.seek(0)
        wav.write(wav_header(size))
    finally:
        wav.close()
    print("RECORDED_BYTES", size)
    print("SAVED_WAV", path)
    return path, size


def replay_phrase(amp, enable, path, size, display):
    show_state(display, "REPLAY", "PLEASE WAIT")
    print("REPLAY_START bytes=%d" % size)
    enable.value(1)
    time.sleep_ms(30)
    wav = open(path, "rb")
    try:
        wav.seek(44)
        remaining = size
        while remaining > 0:
            data = wav.read(BUFFER_SAMPLES * 2)
            if not data:
                break
            amp.write(data)
            remaining -= len(data)
    finally:
        wav.close()
    enable.value(0)
    print("REPLAY_DONE")


def record_once(display):
    if web_recording_active:
        print("RECORD_BUSY web recording is active")
        return
    rx_buf = bytearray(BUFFER_SAMPLES * MIC_FRAME_BYTES)
    tx_buf = bytearray(BUFFER_SAMPLES * 2)
    mic = None
    try:
        mic = I2S(
            0,
            sck=Pin(MIC_BCLK),
            ws=Pin(MIC_WS),
            sd=Pin(MIC_SD),
            mode=I2S.RX,
            bits=16,
            format=I2S.MONO,
            rate=VOICE_RATE,
            ibuf=8000,
        )
        result = record_phrase(mic, rx_buf, tx_buf, display)
        if result:
            path, size = result
            show_state(display, "SAVED", "CHECK WEB")
            print("RECORD_ONLY_DONE path=%s bytes=%d" % (path, size))
        else:
            show_state(display, "MENU", "NO VOICE")
    finally:
        if mic is not None:
            mic.deinit()
        print("RECORD_RESOURCES_RELEASED")


def print_menu():
    print("\n================ ESP32 AUDIO MENU ================")
    print("1 - OLED display test")
    print("2 - Record one phrase (no speaker playback)")
    print("3 - Speaker tone test: 880 Hz, 3 seconds")
    print("4 - ABC song: loop until Ctrl-C")
    print("q - Quit menu and mute amplifier")
    print("===================================================")


def main():
    display = init_oled()
    ip = wifi_connect(display)
    if ip:
        start_web_server(ip)
    show_idle(display, ip)
    print("ESP32 AUDIO MENU READY")

    while True:
        print_menu()
        try:
            choice = input("Select 1/2/3/4/q: ").strip().lower()
        except KeyboardInterrupt:
            print("\nMENU_STOP")
            break

        if choice == "1":
            oled_test(display)
        elif choice == "2":
            record_once(display)
        elif choice == "3":
            play_tone(display)
        elif choice == "4":
            play_abc(display)
        elif choice == "q":
            print("MENU_EXIT")
            break
        else:
            print("Invalid choice; enter 1, 2, 3, 4, or q")

        show_idle(display, ip)

    Pin(AMP_SD, Pin.OUT, value=0)
    show_idle(display, ip)


if __name__ == "__main__":
    main()
