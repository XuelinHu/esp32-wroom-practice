# main.py
# 菜单选择器：读取examples文件夹中的示例，显示文件名、功能和针脚信息
# 选择项目后执行对应的run()方法，然后返回主菜单

import os
import sys

# 添加base和examples到系统路径
sys.path.append('base')
sys.path.append('examples')

def extract_file_info(filename):
    """从Python文件中提取功能描述和针脚信息"""
    examples_info = {
        'rotary.py': {
            'description': '旋钮编码器控制，通过中断检测旋转和按键',
            'pins': 'SW=GPIO19, DT=GPIO21, CLK=GPIO22'
        },
        'light_and_bee.py': {
            'description': '4按键控制：LED轮询、蜂鸣器、呼吸灯、RGB LED',
            'pins': '按键:25,26,27,14 | LED:15 | 蜂鸣器:16 | PWM:4 | RGB:17 | TM1637:18,19'
        },
        'stepper_motor.py': {
            'description': '28BYJ-48步进电机控制，4按键控制不同角度',
            'pins': '电机:15,2,0,4 | 按键:32,33,12,13'
        },
        'steering.py': {
            'description': 'SG90/MG90S舵机控制，测试不同角度',
            'pins': '舵机PWM:GPIO27'
        },
        'dc_motor_simple.py': {
            'description': '直流电机PWM调速控制',
            'pins': '电机控制:GPIO15'
        },
        'person_sensor.py': {
            'description': 'HC-SR501/SR602人体红外感应模块检测',
            'pins': 'PIR传感器:GPIO32'
        },
        'ir_obstacle.py': {
            'description': '红外避障检测模块',
            'pins': '红外传感器:GPIO32'
        },
        'phonotelemeter.py': {
            'description': 'HC-SR04超声波测距，K1长按锁存',
            'pins': '按键:25,26,27,14 | 锁存输出:15 | 超声波:TRIG-22, ECHO-21'
        },
        'rocker.py': {
            'description': 'PS2摇杆模拟输入检测',
            'pins': 'VRX:GPIO34, VRY:GPIO35, SW:GPIO32'
        },
        'wifi_simple_test.py': {
            'description': '简化WiFi连接测试，避免重启问题',
            'pins': 'WiFi网络连接，无特定GPIO'
        },
        'wifi_websocket.py': {
            'description': 'WiFi连接+WebSocket通信，发送helloworld',
            'pins': 'WiFi网络连接，无特定GPIO'
        },
        'ble_wifi_simple.py': {
            'description': 'BLE WiFi配网系统，手机配置WiFi',
            'pins': 'BLE广播，无特定GPIO'
        }
    }

    return examples_info.get(filename, {
        'description': '未知功能',
        'pins': '未定义'
    })

def get_examples():
    """获取examples文件夹中的所有Python文件"""
    examples = []
    try:
        files = os.listdir('examples')
        for file in sorted(files):
            if file.endswith('.py') and not file.startswith('__'):
                examples.append(file)
    except OSError:
        print("错误：无法读取examples文件夹")
        return []

    return examples

def display_menu(examples):
    """显示菜单选项"""
    print("\n" + "="*60)
    print("           ESP32 示例项目选择器")
    print("="*60)
    print(f"{'序号':<4} {'文件名':<20} {'功能描述':<25} {'针脚'}")
    print("-"*60)

    for i, filename in enumerate(examples, 1):
        info = extract_file_info(filename)
        # 截断过长的描述和针脚信息
        desc = info['description'][:24] if len(info['description']) > 24 else info['description']
        pins = info['pins'][:15] if len(info['pins']) > 15 else info['pins']
        print(f"{i:<4} {filename:<20} {desc:<25} {pins}")

    print("-"*60)
    print("0. 退出程序")
    print("="*60)

def get_user_choice(max_choice):
    """获取用户选择"""
    while True:
        try:
            choice = input("\n请输入选择的项目序号 (0-{}): ".format(max_choice))
            choice = int(choice)
            if 0 <= choice <= max_choice:
                return choice
            else:
                print("无效选择，请输入0到{}之间的数字".format(max_choice))
        except ValueError:
            print("无效输入，请输入数字")

def run_example(filename):
    """运行选中的示例"""
    print(f"\n正在运行: {filename}")
    print("="*40)

    try:
        # 动态导入模块
        module_name = filename.replace('.py', '')
        if module_name in sys.modules:
            # 如果模块已加载，先重新加载
            import importlib
            module = importlib.reload(sys.modules[module_name])
        else:
            module = __import__(module_name)

        # 检查是否有run函数
        if hasattr(module, 'run'):
            print("调用run()方法...")
            module.run()
        else:
            print(f"警告: {filename} 没有run()方法")
            print("该示例可能直接执行代码，请在手动运行时查看效果")

    except KeyboardInterrupt:
        print(f"\n\n用户中断，停止运行 {filename}")
    except Exception as e:
        print(f"\n运行 {filename} 时出错: {e}")

    print("\n按Enter键返回主菜单...")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        print("\n直接返回主菜单...")
        return

def main():
    """主程序循环"""
    print("ESP32示例项目选择器启动...")

    while True:
        examples = get_examples()

        if not examples:
            print("没有找到任何示例文件，程序退出")
            break

        display_menu(examples)
        choice = get_user_choice(len(examples))

        if choice == 0:
            print("程序退出")
            break
        else:
            filename = examples[choice - 1]
            run_example(filename)

    print("感谢使用ESP32示例项目选择器！")

if __name__ == "__main__":
    main()