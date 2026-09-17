"""XIAO ESP32-S3 Sense combined voice and camera application."""

import time
import network

from camera_setup import Camera
from http_server import GlassHTTPServer
from sd_storage import SDStorage
from voice_recorder import VoiceRecorder


WIFI_SSID = "ChinaNet-E5y7"
WIFI_PASSWORD = "zadyx5cc"
WIFI_TIMEOUT_MS = 15000
HTTP_PORT = 80


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print("WIFI_CONNECTED")
        print("WIFI_IP %s" % ip)
        return ip
    print("WIFI_CONNECTING ssid=%s" % WIFI_SSID)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    deadline = time.ticks_add(time.ticks_ms(), WIFI_TIMEOUT_MS)
    while not wlan.isconnected() and time.ticks_diff(deadline, time.ticks_ms()) > 0:
        time.sleep_ms(250)
    if not wlan.isconnected():
        print("WIFI_CONNECT_FAILED")
        return None
    ip = wlan.ifconfig()[0]
    print("WIFI_CONNECTED")
    print("WIFI_IP %s" % ip)
    return ip


def main():
    print("GLASS_START")
    print("VOICE_MODE onboard PDM microphone GPIO42/41")
    print("CAMERA_MODE OV2640/OV3660 auto-detect")
    ip = connect_wifi()
    camera = Camera()
    if not camera.init():
        print("CAMERA_INIT_FAILED_CONTINUE_AUDIO")
    storage = SDStorage()
    recorder = VoiceRecorder()
    server = GlassHTTPServer(camera, recorder, storage, HTTP_PORT)
    if ip:
        print("WEB_URL http://%s/" % ip)
    server.run()


main()
