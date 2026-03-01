"""
ESP32-Cam V2 Boot Script
启动脚本 - 在系统启动时执行

功能:
1. 禁用调试输出以提高性能
2. 设置基本系统参数
3. 自动运行主程序
"""

import gc
import machine

print("=" * 50)
print("ESP32-Cam V2 Boot Script")
print("=" * 50)

# 禁用调试输出以提高性能
try:
    import esp
    esp.osdebug(None)
    print("[BOOT] 调试输出已禁用")
except Exception as e:
    print(f"[BOOT] 禁用调试输出失败: {e}")

# 设置CPU频率为最高性能
try:
    machine.freq(240000000)  # 240MHz
    print(f"[BOOT] CPU频率设置为: {machine.freq()//1000000} MHz")
except Exception as e:
    print(f"[BOOT] 设置CPU频率失败: {e}")

# 清理内存
gc.collect()
print(f"[BOOT] 可用内存: {gc.mem_free()} bytes")

print("[BOOT] Boot script 完成，等待启动 main.py...")
print("=" * 50)
