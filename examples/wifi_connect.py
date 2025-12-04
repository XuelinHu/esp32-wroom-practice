# wifi_connect.py  或写在 main.py 里

import network
import time

AP = "ChinaNet-E5y7"
PWD = "zadyx5cc"

def connect_wifi(ssid=AP, password=PWD, timeout=15):
    wlan = network.WLAN(network.STA_IF)
    if not wlan.active():
        wlan.active(True)

    if not wlan.isconnected():
        print("正在连接 WiFi:", ssid)
        wlan.connect(ssid, password)

        start = time.time()
        while not wlan.isconnected():
            if time.time() - start > timeout:
                print("连接超时，检查 SSID/密码 或 路由器")
                return False
            print(".", end="")
            time.sleep(1)

    print("\n连接成功!")
    print("IP 信息:", wlan.ifconfig())
    return True

if __name__ == "__main__":
    ok = connect_wifi()
    if ok:
        # 这里可以写你后续的代码，比如 MQTT / HTTP 请求等
        pass
