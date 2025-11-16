
<p align="center">
  <img src="https://img.shields.io/badge/ESP32--WROOM-Espressif-red?logo=espressif&logoColor=white" />
  <img src="https://img.shields.io/badge/PlatformIO-ready-brightgreen?logo=platformio&logoColor=white" />
  <img src="https://img.shields.io/badge/ESP--IDF-5.x-orange?logo=espressif&logoColor=white" />
  <img src="https://img.shields.io/badge/SSD1306-OLED-purple" />
  <img src="https://img.shields.io/badge/HC--SR04-Ultrasonic-informational" />
  <img src="https://img.shields.io/badge/License-MIT-green" />
</p>

# 开发环境
## 一、环境搭建（以ESP32-WROOM型号为例）
![usb_link.png](assets/usb_link.png)
MicroPython固件刷入链接

- 固件下载地址：https://micropython.org/download/
- ESP32通用固件：https://micropython.org/download/ESP32_GENERIC/
- 官方文档参考：https://docs.micropython.org/en/latest/esp32/quickref.html

```shell
conda create --name esp32 python=3.7
pip install esptool  # 自动安装最新兼容版本（4.x+）

esptool.py erase_flash
esptool.py --baud 460800 write_flash 0x1000 ESP32_BOARD_NAME-DATE-VERSION.bin


```

MicroPython 并不严格对应标准 Python 的某个具体版本（如 3.4），但它的语法和核心特性主要基于 Python 3.4 至 Python 3.6 的特性集，同时针对嵌入式设备的资源限制做了精简和优化。
具体说明：
1. 核心语法基础
MicroPython 遵循 Python 3 的语法规范（而非 Python 2），支持 print() 函数、类型注解、async/await 异步语法等 Python 3 的核心特性。这些特性主要对应 Python 3.4 到 3.6 之间的版本（例如，async/await 在 Python 3.5 中正式引入，MicroPython 也支持类似语法）。
2. 与标准 Python 的差异  
  ○ MicroPython 为了适配嵌入式设备（如 ESP32）的有限内存和计算资源，精简了标准库（例如，没有 tkinter、multiprocessing 等桌面级模块）。  
  ○ 增加了硬件控制专属模块（如 machine 模块用于 GPIO、PWM、ADC 等硬件操作）。  
  ○ 部分语法和函数实现略有简化（例如，字符串格式化、异常处理的细节）。
3. 版本兼容性
对于 ESP32 上的 MicroPython，你无需纠结它“对应”标准 Python 的哪个版本——只要你的代码符合 Python 3 的基本语法（避免使用 Python 3.7+ 才引入的新特性，如 walrus operator :=），基本都能在 MicroPython 上运行。例如：  
  ○ 支持 f-string（Python 3.6 引入），但早期 MicroPython 版本可能不支持；  
  ○ 不支持 Python 3.8+ 的 positional-only parameters 等较新特性。
总结：
MicroPython 基于 Python 3 的语法和特性，核心功能接近 Python 3.4~3.6，但并非严格等同于某个版本。开发时只需遵循 Python 3 的通用语法，并注意 MicroPython 对标准库的精简和硬件模块的扩展即可。
如果你是在 ESP32 上使用 MicroPython，无需关心本地 Conda 环境的 Python 版本（只要工具链如 esptool 能运行即可），因为 MicroPython 固件本身是独立的嵌入式解释器，与你的电脑 Python 版本无关。
## Thonny 下载与安装
- 方式一：直接下载安装（官网获取对应系统版本）
- 方式二：通过pip命令安装（终端执行pip install thonny）
## pycharm 开发ESP32
`2025前的版本，好像不支持通过plugin要搜索到 micropython-tools`

使用插件： [micropython-tools-jetbrains-pro-2025.3.1](https://plugins.jetbrains.com/plugin/26227-micropython-tools/versions/stable)

需要开启以下的配置


![pycharm.png](assets/pycharm.png)
## ESP32 datasheet
● 文档链接：https://documentation.espressif.com/esp32-s2_datasheet_en.pdf





# esp32-wroom-practice
ESP32-WROOM 实战练习：按键/旋钮编码器、HC-SR04 超声波、PIR（SR505）、干簧管、激光模块与 OLED 显示的示例与工具集。



## 目录说明
- `lib/`：第三方/驱动层（SSD1306、TM1637、LCD1602、SD 卡等）
- `base/`：项目基础模块（配置、日志、显示抽象、工具）
- `examples/`：功能示例（超声波、旋钮、激光、光敏、LCD1602、档位）
- `boot.py`：开机把 `/base`、`/examples` 加入 `sys.path`
- `main.py`：示例选择器或入口


## 常用的模块

| 模块名称               | 英文命名                               | 型号       |
|------------------------|----------------------------------------|------------|
| 干簧管传感器模块       | Reed Switch Sensor Module              | KY-021     |
| MPU6050模块            | MPU6050 Sensor Module (Gyro & Accelerometer) | MPU6050    |
| 光电传感器模块         | Photoelectric Sensor Module            | KY-010     |
| 旋转编码器模块         | Rotary Encoder Module                  | KY-040     |
| BMP280模块             | BMP280 Sensor Module (Pressure & Temperature) | BMP280     |
| 光敏传感器模块         | Light Dependent Resistor (LDR) Sensor Module | KY-018     |
| 热敏传感器模块         | Thermistor Sensor Module               | KY-013     |
| PS2摇杆模块            | PS2 Joystick Module                    | KY-023     |
| 蜂鸣器模块             | Buzzer Module                          | KY-012     |
| 火焰传感器模块         | Flame Sensor Module                    | KY-026     |
| 倾斜传感器模块         | Tilt Sensor Module                     | KY-020     |
| 声音传感器模块         | Sound Sensor Module                    | KY-038     |
| 触摸传感器模块         | Touch Sensor Module                    | KY-036     |
| 雨滴传感器模块         | Raindrop Sensor Module                 | KY-037     |
| 振动传感器模块         | Vibration Sensor Module                | KY-002     |
| 烟雾传感器模块（MQ-2） | Smoke Sensor Module (MQ-2)             | MQ-2       |
| 红外避障模块           | Infrared Obstacle Avoidance Sensor Module | KY-032     |
| 磁控开关模块           | Magnetic Switch Sensor Module          | KY-025     |
| 红外发射模块           | Infrared (IR) Transmitter Module       | KY-005     |
| 按键模块               | Push Button Module                     | KY-004     |
