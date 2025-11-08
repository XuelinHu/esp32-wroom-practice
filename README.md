
<p align="center">
  <img src="https://img.shields.io/badge/ESP32--WROOM-Espressif-red?logo=espressif&logoColor=white" />
  <img src="https://img.shields.io/badge/PlatformIO-ready-brightgreen?logo=platformio&logoColor=white" />
  <img src="https://img.shields.io/badge/ESP--IDF-5.x-orange?logo=espressif&logoColor=white" />
  <img src="https://img.shields.io/badge/SSD1306-OLED-purple" />
  <img src="https://img.shields.io/badge/HC--SR04-Ultrasonic-informational" />
  <img src="https://img.shields.io/badge/License-MIT-green" />
</p>

# esp32-wroom-practice
ESP32-WROOM 实战练习：按键/旋钮编码器、HC-SR04 超声波、PIR（SR505）、干簧管、激光模块与 OLED 显示的示例与工具集。


| 文件名                  | 使用的硬件/ESP 外设                                | 主要作用/说明（要点）                                                                     |
| -------------------- | ------------------------------------------- | ------------------------------------------------------------------------------- |
| `lib/i2c_lcd_min.py` | **I²C 字符屏 LCD1602/2004（PCF8574 扩展板）**       | 最小驱动：初始化、清屏、写字符/光标控制；走 I²C 总线，供 `main_lcd1602.py` 调用。                           |
| `lib/ssd1306.py`     | **SSD1306 OLED（I²C/SPI 版常见 128×64/128×32）** | OLED 图形/文字驱动，提供绘图与文本 API；通常与测距/编码器示例联动显示。                                       |
| `lib/tm1637.py`      | **TM1637 4 位数码管**（CLK/DIO 两线）               | TM1637 数码管驱动，显示数字/档位/计数值；可能被 `main_gear.py` 等示例使用。                              |
| `lib/sdcard.py`      | **MicroSD 卡（SPI）**                          | SPI SD 卡块设备驱动，挂载到 VFS 进行读写日志/数据记录。                                              |
| `main_distance.py`   | **HC-SR04 超声波测距** +（常与 **SSD1306 OLED** 联动） | 非阻塞测距，实时显示距离/状态（通常在 OLED 上）。注意 Echo 需做 5V→3.3V 电平匹配或用 3.3V 兼容模块（如 SR04P）。       |
| `main_gear.py`       | **TM1637 数码管**（推断）/或“档位模式演示”                | 通过按键/旋钮切换“档位/模式”，在 TM1637 或 OLED 上显示数值（推断自文件名 *gear*）。                          |
| `main_laser.py`      | **激光发射/传感模块**（数模/数字输入）                      | 控制激光管开关，读取接收端/比较器输出并显示状态/计数；你先前提到“使用 GPIO22”可在此示例中配置。                           |
| `main_lcd1602.py`    | **LCD1602（I²C）** + `lib/i2c_lcd_min.py`     | 字符屏显示 Demo：初始化、打印多行文本/菜单。                                                       |
| `main_light.py`      | **光敏传感器（LDR/光照强度）→ ADC**                    | 采样模拟光照值（ADC），阈值判断/曲线显示（常配 OLED/串口日志）。                                           |
| `main_rotary.py`     | **旋钮编码器（KY-040 等）** +（常配 **SSD1306 OLED**）  | 读取旋转增量与**方向**、按钮按下；你之前给出接线：`SW=GPIO19, DT=GPIO21, CLK=GPIO22`，并在 OLED 上显示计数与方向。 |
