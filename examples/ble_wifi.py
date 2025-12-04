import network
import time
import bluetooth
from bluetooth import BLE

# ========== WiFi 相关，做了“重置 + 更安全的等待” ==========
def connect_wifi(ssid, password, timeout=15):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # 先尽量把之前的连接状态清掉，避免 "sta is connecting" 错误
    try:
        wlan.disconnect()
    except OSError:
        pass

    # 等一小会儿
    time.sleep(0.5)

    print("开始连接 WiFi:", ssid)

    # 注意：这里包一层 try，避免直接抛 OSError: Wifi Internal Error
    try:
        wlan.connect(ssid, password)
    except OSError as e:
        print("调用 wlan.connect 出错:", e)
        return False, None

    # 更安全的等待方式：看 status() 而不光是 isconnected()
    start = time.ticks_ms()
    while True:
        s = wlan.status()
        # print("调试：status =", s)  # 需要的话可以打开

        if s == network.STAT_GOT_IP:
            # 连接成功
            print("\n✅ WiFi 连接成功:", wlan.ifconfig())
            return True, wlan.ifconfig()

        # 这些是各种失败状态
        if s in (network.STAT_WRONG_PASSWORD,
                 network.STAT_NO_AP_FOUND,
                 network.STAT_CONNECT_FAIL):
            print("⛔ 连接失败，status =", s)
            return False, None

        # 超时处理
        if time.ticks_diff(time.ticks_ms(), start) > timeout * 1000:
            print("⏰ WiFi 连接超时，status =", s)
            return False, None

        print(".", end="")
        time.sleep(0.5)


# ========== BLE UART-like 服务 ==========
UART_SERVICE_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
UART_RX_UUID      = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")
UART_TX_UUID      = bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")

UART_RX = (UART_RX_UUID, bluetooth.FLAG_WRITE)
UART_TX = (UART_TX_UUID, bluetooth.FLAG_NOTIFY)
UART_SERVICE = (UART_SERVICE_UUID, (UART_RX, UART_TX))

ble = BLE()
ble.active(True)

# 你的板子这里返回类似：((rx_handle, tx_handle),)
services = ble.gatts_register_services((UART_SERVICE,))
RX_HANDLE, TX_HANDLE = services[0]
print("Handles => RX:", RX_HANDLE, "TX:", TX_HANDLE)

current_conn_handle = None

# 缓存 WiFi 配置
wifi_cached = {"ssid": None, "pwd": None}
pending_wifi_config = {"ssid": None, "pwd": None}


def send_ble_message(msg):
    """向手机发送 BLE 通知"""
    global current_conn_handle
    if current_conn_handle is None:
        print("【BLE】未连接，无法发送：", msg)
        return
    try:
        ble.gatts_notify(current_conn_handle, TX_HANDLE, msg)
    except Exception as e:
        print("BLE notify 出错：", e)


def advertise():
    name = "ESP32-SETUP"
    payload = bytearray(b"\x02\x01\x06") + bytearray((len(name) + 1, 0x09)) + name.encode()
    ble.gap_advertise(100_000, payload)
    print("📡 BLE 广播中：名称 =", name)


def bt_irq(event, data):
    global current_conn_handle, wifi_cached, pending_wifi_config

    if event == 1:
        # 手机连接
        conn_handle, _, _ = data
        current_conn_handle = conn_handle
        print("💙 手机已连接 conn =", conn_handle)
        send_ble_message("CONNECTED")

    elif event == 2:
        # 手机断开
        conn_handle, _, _ = data
        print("💔 手机断开 conn =", conn_handle)
        current_conn_handle = None
        advertise()

    elif event == 3:
        # 手机写数据
        conn_handle, value_handle = data
        if value_handle == RX_HANDLE:
            raw = ble.gatts_read(RX_HANDLE)
            try:
                text = raw.decode().strip()
            except:
                text = ""
            print("📥 收到:", text)

            # S:SSID
            if text.startswith("S:"):
                ssid = text[2:].strip()
                wifi_cached["ssid"] = ssid
                send_ble_message("SSID_OK")
                print("➡ SSID 设置为:", ssid)

            # P:PASSWORD
            elif text.startswith("P:"):
                pwd = text[2:].strip()
                wifi_cached["pwd"] = pwd
                send_ble_message("PWD_OK")
                print("➡ PWD 设置为:", pwd)

                # 如果 SSID+PWD 均已收到，则触发配网
                if wifi_cached["ssid"]:
                    pending_wifi_config["ssid"] = wifi_cached["ssid"]
                    pending_wifi_config["pwd"]  = wifi_cached["pwd"]
                    send_ble_message("CFG_OK")
                    print("➡ WiFi 配置收齐，准备连接")

            else:
                send_ble_message("ERR_FORMAT")


# ========== 初始化 BLE ==========
ble.irq(bt_irq)
advertise()
print("系统启动完毕：BLE 配网模式")


# ========== 主循环：处理 WiFi 连接 ==========
while True:
    if pending_wifi_config["ssid"] and pending_wifi_config["pwd"]:
        ssid = pending_wifi_config["ssid"]
        pwd  = pending_wifi_config["pwd"]

        pending_wifi_config["ssid"] = None
        pending_wifi_config["pwd"]  = None

        send_ble_message("WIFI_CONNECTING")
        ok, info = connect_wifi(ssid, pwd)

        if ok:
            ip, mask, gw, dns = info
            send_ble_message("WIFI_OK," + ip)
        else:
            send_ble_message("WIFI_FAIL")

    time.sleep(0.1)
