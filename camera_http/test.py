"""
ESP32-Cam 组件测试脚本
测试WiFi、摄像头和HTTP服务器组件
"""

import time
import gc

def test_wifi():
    """测试WiFi热点功能"""
    print("=" * 30)
    print("测试WiFi热点功能")
    print("=" * 30)

    try:
        from wifi_ap import WiFiAP

        wifi = WiFiAP("Test-AP", "12345678")
        print("正在启动WiFi热点...")

        if wifi.start_ap():
            print("✅ WiFi热点启动成功")
            status = wifi.get_status()
            print(f"   SSID: {status.get('ssid', 'Unknown')}")
            print(f"   IP: {status.get('ip', 'Unknown')}")
            print(f"   信道: {status.get('channel', 'Unknown')}")

            time.sleep(3)  # 运行3秒

            wifi.stop_ap()
            print("✅ WiFi热点关闭成功")
            return True
        else:
            print("❌ WiFi热点启动失败")
            return False

    except Exception as e:
        print(f"❌ WiFi测试异常: {e}")
        return False

def test_camera():
    """测试摄像头功能"""
    print("\n" + "=" * 30)
    print("测试摄像头功能")
    print("=" * 30)

    try:
        from camera_setup import ESP32Camera

        camera = ESP32Camera()
        print("正在初始化摄像头...")

        if camera.init():
            print("✅ 摄像头初始化成功")
            status = camera.get_status()
            print(f"   初始化状态: {status.get('initialized', False)}")
            print(f"   像素格式: {status.get('format', 'Unknown')}")

            # 测试捕获图像
            print("正在测试图像捕获...")
            frame = camera.capture_frame()
            if frame:
                print(f"✅ 图像捕获成功，大小: {len(frame)} bytes")
            else:
                print("❌ 图像捕获失败")

            camera.deinit()
            print("✅ 摄像头关闭成功")
            return frame is not None
        else:
            print("❌ 摄像头初始化失败")
            return False

    except Exception as e:
        print(f"❌ 摄像头测试异常: {e}")
        return False

def test_memory():
    """测试内存状态"""
    print("\n" + "=" * 30)
    print("内存状态检查")
    print("=" * 30)

    try:
        gc.collect()
        free_mem = gc.mem_free()
        alloc_mem = gc.mem_alloc()

        print(f"可用内存: {free_mem} bytes ({free_mem//1024} KB)")
        print(f"已用内存: {alloc_mem} bytes ({alloc_mem//1024} KB)")
        print(f"总内存: {free_mem + alloc_mem} bytes ({(free_mem + alloc_mem)//1024} KB)")

        if free_mem < 50000:  # 少于50KB警告
            print("⚠️  可用内存较少，建议重启设备")
        else:
            print("✅ 内存状态正常")

        return free_mem > 50000

    except Exception as e:
        print(f"❌ 内存检查异常: {e}")
        return False

def test_system_info():
    """显示系统信息"""
    print("\n" + "=" * 30)
    print("系统信息")
    print("=" * 30)

    try:
        import machine
        import esp
        import uos

        # CPU信息
        freq = machine.freq()
        print(f"CPU频率: {freq//1000000} MHz")

        # Flash信息
        try:
            flash_size = esp.flash_size()
            print(f"Flash大小: {flash_size//1024} KB")
        except:
            print("Flash大小: 无法获取")

        # 系统信息
        uname = uos.uname()
        print(f"系统: {uname.sysname}")
        print(f"版本: {uname.version}")
        print(f"机器: {uname.machine}")

        return True

    except Exception as e:
        print(f"❌ 系统信息获取异常: {e}")
        return False

def run_all_tests():
    """运行所有测试"""
    print("ESP32-Cam 组件测试开始...")
    print("测试时间:", time.time())

    tests = [
        ("系统信息", test_system_info),
        ("内存状态", test_memory),
        ("WiFi热点", test_wifi),
        ("摄像头", test_camera)
    ]

    results = {}
    passed = 0

    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
            if result:
                passed += 1
        except Exception as e:
            print(f"❌ {test_name}测试异常: {e}")
            results[test_name] = False

    # 显示测试结果汇总
    print("\n" + "=" * 40)
    print("测试结果汇总")
    print("=" * 40)

    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")

    print(f"\n总计: {passed}/{len(tests)} 项测试通过")

    if passed == len(tests):
        print("🎉 所有测试通过，可以启动服务器!")
    else:
        print("⚠️  部分测试失败，请检查硬件连接")

    return passed == len(tests)

if __name__ == "__main__":
    run_all_tests()