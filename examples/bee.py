# ESP32多传感器蜂鸣器联动控制系统（带定时打印）
# 集成雨滴、光敏、热敏、超声波、人体感应传感器

from machine import Pin, PWM, ADC
import time

class MultiSensorBuzzerSystem:
    def __init__(self):
        # 初始化蜂鸣器（GPIO13）
        self.buzzer_pin = Pin(13, Pin.OUT)
        self.pwm = PWM(self.buzzer_pin)
        self.pwm.freq(2000)  # 提高频率到2000Hz，声音更高
        self.pwm.duty(0)     # 初始关闭

        # 初始化传感器引脚
        self.rain_sensor = Pin(32, Pin.IN)      # 雨滴传感器 - 数字输入
        self.light_adc = ADC(Pin(33))           # 光敏传感器 - 模拟输入
        self.temp_adc = ADC(Pin(34))            # 热敏传感器 - 模拟输入
        self.trig_pin = Pin(25, Pin.OUT)        # 超声波传感器 - 触发引脚
        self.echo_pin = Pin(26, Pin.IN)         # 超声波传感器 - 回声引脚
        self.motion_sensor = Pin(27, Pin.IN)    # 人体感应传感器 - 数字输入

        # 设置ADC分辨率
        self.light_adc.atten(ADC.ATTN_11DB)     # 扩大测量范围
        self.temp_adc.atten(ADC.ATTN_11DB)

        # 状态跟踪变量
        self.last_rain_state = 1
        self.last_light_level = 0
        self.last_temp_level = 0
        self.last_distance = 0
        self.last_motion_state = 0

        # 定时打印变量
        self.last_print_time = time.time()
        self.print_interval = 5  # 每5秒打印一次传感器参数

        print("ESP32多传感器系统初始化完成")
        print("GPIO13 - 蜂鸣器")
        print("GPIO32 - 雨滴传感器")
        print("GPIO33 - 光敏传感器")
        print("GPIO34 - 热敏传感器")
        print("GPIO25 - 超声波TRIG")
        print("GPIO26 - 超声波ECHO")
        print("GPIO27 - 人体感应传感器")

    def buzzer_on(self, duty=512):
        """开启蜂鸣器"""
        self.pwm.duty(duty)

    def buzzer_off(self):
        """关闭蜂鸣器"""
        self.pwm.duty(0)

    def short_beep(self, duration_ms=200):
        """短蜂鸣声 - 雨滴传感器"""
        self.buzzer_on(700)  # 增强音量
        time.sleep_ms(duration_ms)
        self.buzzer_off()
        time.sleep_ms(100)

    def long_beep(self, duration_ms=800):
        """长蜂鸣声 - 光敏传感器"""
        self.buzzer_on(700)
        time.sleep_ms(duration_ms)
        self.buzzer_off()
        time.sleep_ms(200)

    def double_beep(self, duration_ms=300):
        """双短蜂鸣声 - 热敏传感器"""
        self.buzzer_on(700)
        time.sleep_ms(duration_ms)
        self.buzzer_off()
        time.sleep_ms(150)
        self.buzzer_on(700)
        time.sleep_ms(duration_ms)
        self.buzzer_off()
        time.sleep_ms(200)

    def triple_beep(self, duration_ms=250):
        """三短蜂鸣声 - 超声波传感器"""
        for i in range(3):
            self.buzzer_on(700)
            time.sleep_ms(duration_ms)
            self.buzzer_off()
            if i < 2:
                time.sleep_ms(100)
        time.sleep_ms(200)

    def continuous_beep(self, duration_ms=1500):
        """连续蜂鸣声 - 人体感应传感器"""
        self.buzzer_on(700)
        time.sleep_ms(duration_ms)
        self.buzzer_off()
        time.sleep_ms(300)

    def measure_distance(self):
        """测量超声波距离"""
        # 发送10微秒的触发信号
        self.trig_pin.value(0)
        time.sleep_us(2)
        self.trig_pin.value(1)
        time.sleep_us(10)
        self.trig_pin.value(0)

        # 等待回声信号
        timeout = time.ticks_add(time.ticks_ms(), 300)  # 300ms超时
        while self.echo_pin.value() == 0:
            if time.ticks_diff(time.ticks_ms(), timeout) >= 0:
                return 999  # 超时返回最大值
        pulse_start = time.ticks_us()

        timeout = time.ticks_add(time.ticks_ms(), 300)
        while self.echo_pin.value() == 1:
            if time.ticks_diff(time.ticks_ms(), timeout) >= 0:
                return 999
        pulse_end = time.ticks_us()

        # 计算距离 (厘米)
        pulse_duration = time.ticks_diff(pulse_end, pulse_start)
        distance = (pulse_duration * 0.034) / 2
        return round(distance, 2)

    def read_sensors(self):
        """读取所有传感器数据"""
        sensors_data = {}

        # 读取雨滴传感器
        sensors_data['rain'] = self.rain_sensor.value()

        # 读取光敏传感器 (0-4095)
        sensors_data['light'] = self.light_adc.read()

        # 读取热敏传感器 (0-4095)
        sensors_data['temp'] = self.temp_adc.read()

        # 读取超声波传感器
        sensors_data['distance'] = self.measure_distance()

        # 读取人体感应传感器
        sensors_data['motion'] = self.motion_sensor.value()

        return sensors_data

    def print_sensor_params(self):
        """定时打印传感器参数"""
        current_time = time.time()

        if current_time - self.last_print_time >= self.print_interval:
            data = self.read_sensors()

            print("="*50)
            print("传感器实时参数 (每{}秒打印一次)".format(self.print_interval))
            print("-"*50)
            print(f"光敏传感器数值: {data['light']} (0-4095)")
            print(f"热敏传感器数值: {data['temp']} (0-4095)")
            print(f"超声波距离: {data['distance']} cm")
            print(f"人体感应状态: {'有人' if data['motion'] == 1 else '无人'}")
            print(f"雨滴传感器状态: {'有雨' if data['rain'] == 0 else '无雨'}")
            print("="*50)

            self.last_print_time = current_time

    def process_sensors(self):
        """处理传感器数据并触发相应蜂鸣"""
        data = self.read_sensors()

        # 雨滴传感器：检测到雨水时播放短蜂鸣
        if data['rain'] == 0 and self.last_rain_state == 1:
            print(">>> 检测到雨水 - 播放短蜂鸣 <<<")
            self.short_beep()

        # 光敏传感器：光线变暗时播放长蜂鸣
        if data['light'] < 1000 and self.last_light_level >= 1000:  # 假设小于1000为光线较暗
            print(">>> 光线变暗 - 播放长蜂鸣 <<<")
            self.long_beep()

        # 热敏传感器：温度升高时播放双短蜂鸣
        if data['temp'] > 2000 and self.last_temp_level <= 2000:  # 假设大于2000为高温
            print(">>> 温度升高 - 播放双短蜂鸣 <<<")
            self.double_beep()

        # 超声波传感器：近距离物体播放三短蜂鸣
        if data['distance'] < 20 and data['distance'] != 999 and self.last_distance >= 20:  # 小于20cm
            print(f">>> 检测到近距离物体 ({data['distance']}cm) - 播放三短蜂鸣 <<<")
            self.triple_beep()

        # 人体感应传感器：检测到移动播放连续蜂鸣
        if data['motion'] == 1 and self.last_motion_state == 0:
            print(">>> 检测到人体移动 - 播放连续蜂鸣 <<<")
            self.continuous_beep()

        # 更新上次状态
        self.last_rain_state = data['rain']
        self.last_light_level = data['light']
        self.last_temp_level = data['temp']
        self.last_distance = data['distance']
        self.last_motion_state = data['motion']

        # 打印传感器数据
        print(f"传感器数据 - 雨滴:{'有雨' if data['rain']==0 else '无雨'}, "
              f"光照:{data['light']}, 温度:{data['temp']}, "
              f"距离:{data['distance']}cm, 人体:{'有人' if data['motion']==1 else '无人'}")

        # 定时打印详细参数
        self.print_sensor_params()

    def run_system(self):
        """运行多传感器监测系统"""
        print("="*60)
        print("ESP32多传感器蜂鸣器联动系统启动")
        print("传感器类型及蜂鸣模式:")
        print("- 雨滴传感器: 短蜂鸣 (GPIO32)")
        print("- 光敏传感器: 长蜂鸣 (GPIO33)")
        print("- 热敏传感器: 双短蜂鸣 (GPIO34)")
        print("- 超声波传感器: 三短蜂鸣 (GPIO25/26)")
        print("- 人体感应传感器: 连续蜂鸣 (GPIO27)")
        print("="*60)

        try:
            while True:
                self.process_sensors()
                time.sleep_ms(200)  # 每200ms检测一次
        except KeyboardInterrupt:
            print("\n系统被用户中断")
            self.buzzer_off()
            print("蜂鸣器已关闭")
        except Exception as e:
            print(f"发生错误: {e}")
            self.buzzer_off()

# 接线说明：
# ESP32-WROOM-32 板子完整接线：
# 1. 蜂鸣器 (GPIO13):
#    - 蜂鸣器正极 -> ESP32 GPIO13
#    - 蜂鸣器负极 -> ESP32 GND
#
# 2. 雨滴传感器 (GPIO32 - 数字输出):
#    - 传感器VCC -> ESP32 3.3V
#    - 传感器GND -> ESP32 GND
#    - 传感器DO -> ESP32 GPIO32
#
# 3. 光敏传感器 (GPIO33 - 模拟输入):
#    - 传感器VCC -> ESP32 3.3V
#    - 传感器GND -> ESP32 GND
#    - 传感器AO -> ESP32 GPIO33
#
# 4. 热敏传感器 (GPIO34 - 模拟输入):
#    - 传感器VCC -> ESP32 3.3V
#    - 传感器GND -> ESP32 GND
#    - 传感器AO -> ESP32 GPIO34
#
# 5. 超声波传感器 (GPIO25/26):
#    - VCC -> ESP32 5V (或3.3V，根据模块规格)
#    - GND -> ESP32 GND
#    - TRIG -> ESP32 GPIO25
#    - ECHO -> ESP32 GPIO26
#
# 6. 人体感应传感器 (GPIO27 - 数字输出):
#    - VCC -> ESP32 5V (PIR传感器通常需要5V)
#    - GND -> ESP32 GND
#    - OUT -> ESP32 GPIO27

def main():
    system = MultiSensorBuzzerSystem()
    system.run_system()

if __name__ == "__main__":
    main()