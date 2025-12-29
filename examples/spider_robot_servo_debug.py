# spider_robot_servo_debug.py
# ESP32 12舵机4足蜘蛛机器人调试代码

import time
from machine import Pin, PWM
from base.log import debug, info, warn

# ======================
# 蜘蛛机器人舵机配置
# ======================
FREQ = 50               # 舵机固定频率 50Hz
PWM_MAX = 1023         # ESP32 PWM 通道：duty范围 0~1023

# 180度舵机脉宽参数（根据实际舵机调试）
MIN_US = 1000          # 最小脉宽 1.0ms (0度)
MAX_US = 2000          # 最大脉宽 2.0ms (180度)
MID_US = 1500          # 中间脉宽 1.5ms (90度)

# 腿部配置 (FL:前左, FR:前右, BL:后左, BR:后右)
# 每条腿有3个关节：HIP(髋关节), THIGH(大腿关节), KNEE(膝关节)
LEGS_CONFIG = {
    'FL': {  # 前左腿
        'HIP': 13,    # 髋关节 - 控制腿的左右摆动
        'THIGH': 14,  # 大腿关节 - 控制腿的前后摆动
        'KNEE': 16    # 膝关节 - 控制腿的弯曲
    },
    'FR': {  # 前右腿
        'HIP': 17,
        'THIGH': 18,
        'KNEE': 19
    },
    'BL': {  # 后左腿
        'HIP': 21,    # GPIO21 - I2C默认脚，但可当PWM使用
        'THIGH': 22,  # GPIO22 - 同上
        'KNEE': 23
    },
    'BR': {  # 后右腿
        'HIP': 25,
        'THIGH': 26,
        'KNEE': 27
    }
}

# 舵机角度范围限制 (根据机械结构调整)
ANGLE_LIMITS = {
    'HIP': {'min': 30, 'max': 150},      # 髋关节角度限制
    'THIGH': {'min': 45, 'max': 135},    # 大腿关节角度限制
    'KNEE': {'min': 60, 'max': 120}      # 膝关节角度限制
}

# 初始化舵机对象
servos = {}

# 创建GPIO引脚到舵机标识的反向映射
GPIO_TO_SERVO = {}
for leg_name, leg_config in LEGS_CONFIG.items():
    for joint_name, pin in leg_config.items():
        GPIO_TO_SERVO[pin] = f"{leg_name}_{joint_name}"

# ======================
# 舵机初始化
# ======================
def init_servos():
    """初始化所有12个舵机"""
    info("INIT", "开始初始化12个舵机...")

    for leg_name, leg_config in LEGS_CONFIG.items():
        for joint_name, pin in leg_config.items():
            servo_key = f"{leg_name}_{joint_name}"
            try:
                servos[servo_key] = PWM(Pin(pin), freq=FREQ, duty=0)
                info("SERVO", "舵机已初始化: %s -> GPIO%d", servo_key, pin)
            except Exception as e:
                warn("SERVO", "舵机初始化失败: %s -> GPIO%d, 错误: %s", servo_key, pin, str(e))

    info("INIT", "舵机初始化完成，共%d个舵机", len(servos))
    return len(servos) == 12

# ======================
# 工具函数：角度转 duty
# ======================
def angle_to_duty(angle, joint_type):
    """
    角度转换为PWM duty
    angle: 0-180度
    joint_type: 关节类型 (HIP, THIGH, KNEE)
    """
    # 应用角度限制
    limits = ANGLE_LIMITS.get(joint_type, {'min': 0, 'max': 180})
    angle = max(limits['min'], min(limits['max'], angle))

    # 角度转换为脉宽
    us = MIN_US + (MAX_US - MIN_US) * angle / 180
    duty = int(PWM_MAX * us / 20000)  # 20ms = 20000us

    debug("CALC", "%s关节: 角度=%d° -> 脉宽=%.1fus -> duty=%d", joint_type, angle, us, duty)
    return duty

# ======================
# 单个舵机控制
# ======================
def get_servo_pin(leg, joint):
    """获取舵机对应的GPIO引脚"""
    try:
        return LEGS_CONFIG[leg][joint]
    except KeyError:
        return -1

def get_servo_info(leg, joint):
    """获取舵机详细信息字符串"""
    pin = get_servo_pin(leg, joint)
    servo_key = f"{leg}_{joint}"
    return f"{servo_key}(GPIO{pin})"

def format_servo_key_with_pin(servo_key):
    """格式化舵机标识，包含GPIO信息"""
    if '_' in servo_key:
        leg, joint = servo_key.split('_', 1)
        pin = get_servo_pin(leg, joint)
        return f"{servo_key}(GPIO{pin})"
    return servo_key

def set_servo_angle(leg, joint, angle, speed_ms=0):
    """
    设置单个舵机角度
    leg: 腿部标识 (FL, FR, BL, BR)
    joint: 关节标识 (HIP, THIGH, KNEE)
    angle: 目标角度
    speed_ms: 移动时间(毫秒)，0表示立即设置
    """
    servo_key = f"{leg}_{joint}"
    servo_info = get_servo_info(leg, joint)

    if servo_key not in servos:
        warn("SERVO", "舵机不存在: %s", servo_info)
        return False

    try:
        duty = angle_to_duty(angle, joint)

        if speed_ms > 0:
            # 平滑移动（简化版本，实际应用中需要更复杂的插值）
            servos[servo_key].duty(duty)
            time.sleep(speed_ms / 1000.0)
        else:
            servos[servo_key].duty(duty)

        debug("SERVO", "设置舵机: %s 角度=%d° duty=%d", servo_info, angle, duty)
        return True

    except Exception as e:
        warn("SERVO", "设置舵机失败: %s, 错误: %s", servo_info, str(e))
        return False

# ======================
# 腿部控制
# ======================
def set_leg_angles(leg, hip_angle=None, thigh_angle=None, knee_angle=None, speed_ms=0):
    """
    同时控制一条腿的三个关节
    leg: 腿部标识 (FL, FR, BL, BR)
    speed_ms: 移动时间(毫秒)
    """
    success_count = 0
    angle_parts = []

    if hip_angle is not None:
        if set_servo_angle(leg, 'HIP', hip_angle, speed_ms):
            success_count += 1
            angle_parts.append(f"HIP:{hip_angle}°")

    if thigh_angle is not None:
        if set_servo_angle(leg, 'THIGH', thigh_angle, speed_ms):
            success_count += 1
            angle_parts.append(f"THIGH:{thigh_angle}°")

    if knee_angle is not None:
        if set_servo_angle(leg, 'KNEE', knee_angle, speed_ms):
            success_count += 1
            angle_parts.append(f"KNEE:{knee_angle}°")

    if angle_parts:
        debug("LEG", "%s腿设置角度: %s (耗时%dms)", leg, ", ".join(angle_parts), speed_ms)

    return success_count

# ======================
# 姿势控制
# ======================
def stand_up_pose(speed_ms=1000):
    """站立姿势 - 所有关节回到中间位置"""
    info("POSE", "切换到站立姿势...")

    # 站立姿势角度
    stand_angles = {
        'FL': {'HIP': 90, 'THIGH': 90, 'KNEE': 90},
        'FR': {'HIP': 90, 'THIGH': 90, 'KNEE': 90},
        'BL': {'HIP': 90, 'THIGH': 90, 'KNEE': 90},
        'BR': {'HIP': 90, 'THIGH': 90, 'KNEE': 90}
    }

    for leg, angles in stand_angles.items():
        set_leg_angles(leg,
                      hip_angle=angles['HIP'],
                      thigh_angle=angles['THIGH'],
                      knee_angle=angles['KNEE'],
                      speed_ms=speed_ms)

    time.sleep(speed_ms / 1000.0)
    info("POSE", "站立姿势完成")

def sit_pose(speed_ms=1000):
    """坐下姿势 - 膝关节弯曲"""
    info("POSE", "切换到坐下姿势...")

    # 坐下姿势角度
    sit_angles = {
        'FL': {'HIP': 90, 'THIGH': 90, 'KNEE': 120},
        'FR': {'HIP': 90, 'THIGH': 90, 'KNEE': 120},
        'BL': {'HIP': 90, 'THIGH': 90, 'KNEE': 120},
        'BR': {'HIP': 90, 'THIGH': 90, 'KNEE': 120}
    }

    for leg, angles in sit_angles.items():
        set_leg_angles(leg,
                      hip_angle=angles['HIP'],
                      thigh_angle=angles['THIGH'],
                      knee_angle=angles['KNEE'],
                      speed_ms=speed_ms)

    time.sleep(speed_ms / 1000.0)
    info("POSE", "坐下姿势完成")

def crouch_pose(speed_ms=1000):
    """蹲下姿势 - 所有关节都收缩"""
    info("POSE", "切换到蹲下姿势...")

    crouch_angles = {
        'FL': {'HIP': 90, 'THIGH': 120, 'KNEE': 60},
        'FR': {'HIP': 90, 'THIGH': 120, 'KNEE': 60},
        'BL': {'HIP': 90, 'THIGH': 120, 'KNEE': 60},
        'BR': {'HIP': 90, 'THIGH': 120, 'KNEE': 60}
    }

    for leg, angles in crouch_angles.items():
        set_leg_angles(leg,
                      hip_angle=angles['HIP'],
                      thigh_angle=angles['THIGH'],
                      knee_angle=angles['KNEE'],
                      speed_ms=speed_ms)

    time.sleep(speed_ms / 1000.0)
    info("POSE", "蹲下姿势完成")

# ======================
# 步态模式
# ======================
def wave_gait(leg, step_count=4, speed_ms=500):
    """
    波浪步态 - 一次抬起一条腿
    leg: 开始的腿 ('FL', 'FR', 'BL', 'BR')
    """
    info("GAIT", "开始波浪步态，起始腿: %s", leg)

    # 步态序列：FL -> BR -> FR -> BL -> FL
    gait_sequence = ['FL', 'BR', 'FR', 'BL']
    start_index = gait_sequence.index(leg) if leg in gait_sequence else 0

    for step in range(step_count):
        current_leg = gait_sequence[(start_index + step) % 4]

        print(f"第{step + 1}步: 抬起{current_leg}腿")
        # 抬腿（膝关节伸直，大腿关节向前）
        set_leg_angles(current_leg, knee_angle=60, thigh_angle=45, speed_ms=speed_ms//2)
        time.sleep(speed_ms / 1000.0)

        # 放腿（回到站立位置）
        set_leg_angles(current_leg, knee_angle=90, thigh_angle=90, speed_ms=speed_ms//2)
        time.sleep(speed_ms / 1000.0)

    info("GAIT", "波浪步态完成")

def tripod_gait(step_count=4, speed_ms=800):
    """
    三脚步态 - 对角腿同时移动
    """
    info("GAIT", "开始三脚步态...")

    for step in range(step_count):
        if step % 2 == 0:
            # 第1组：FL和BR抬起
            print(f"第{step + 1}步: FL和BR腿抬起")
            set_leg_angles('FL', knee_angle=60, thigh_angle=45, speed_ms=speed_ms//2)
            set_leg_angles('BR', knee_angle=60, thigh_angle=45, speed_ms=speed_ms//2)
            time.sleep(speed_ms / 1000.0)

            set_leg_angles('FL', knee_angle=90, thigh_angle=90, speed_ms=speed_ms//2)
            set_leg_angles('BR', knee_angle=90, thigh_angle=90, speed_ms=speed_ms//2)
        else:
            # 第2组：FR和BL抬起
            print(f"第{step + 1}步: FR和BL腿抬起")
            set_leg_angles('FR', knee_angle=60, thigh_angle=45, speed_ms=speed_ms//2)
            set_leg_angles('BL', knee_angle=60, thigh_angle=45, speed_ms=speed_ms//2)
            time.sleep(speed_ms / 1000.0)

            set_leg_angles('FR', knee_angle=90, thigh_angle=90, speed_ms=speed_ms//2)
            set_leg_angles('BL', knee_angle=90, thigh_angle=90, speed_ms=speed_ms//2)

        time.sleep(speed_ms / 1000.0)

    info("GAIT", "三脚步态完成")

def turn_left(speed_ms=600):
    """左转"""
    info("GAIT", "开始左转...")

    # 左转时左侧腿向后，右侧腿向前
    turn_angles = {
        'FL': {'THIGH': 120, 'KNEE': 80},  # 左前腿向后
        'BL': {'THIGH': 120, 'KNEE': 80},  # 左后腿向后
        'FR': {'THIGH': 60, 'KNEE': 100},  # 右前腿向前
        'BR': {'THIGH': 60, 'KNEE': 100}   # 右后腿向前
    }

    for leg, angles in turn_angles.items():
        set_leg_angles(leg,
                      hip_angle=90,
                      thigh_angle=angles['THIGH'],
                      knee_angle=angles['KNEE'],
                      speed_ms=speed_ms)

    time.sleep(speed_ms / 1000.0)
    stand_up_pose(speed_ms)
    info("GAIT", "左转完成")

def turn_right(speed_ms=600):
    """右转"""
    info("GAIT", "开始右转...")

    # 右转时右侧腿向后，左侧腿向前
    turn_angles = {
        'FL': {'THIGH': 60, 'KNEE': 100},   # 左前腿向前
        'BL': {'THIGH': 60, 'KNEE': 100},   # 左后腿向前
        'FR': {'THIGH': 120, 'KNEE': 80},   # 右前腿向后
        'BR': {'THIGH': 120, 'KNEE': 80}    # 右后腿向后
    }

    for leg, angles in turn_angles.items():
        set_leg_angles(leg,
                      hip_angle=90,
                      thigh_angle=angles['THIGH'],
                      knee_angle=angles['KNEE'],
                      speed_ms=speed_ms)

    time.sleep(speed_ms / 1000.0)
    stand_up_pose(speed_ms)
    info("GAIT", "右转完成")

# ======================
# 测试函数
# ======================
def test_single_servo():
    """测试单个舵机"""
    print("\n=== 单舵机测试 ===")

    try:
        leg = input("请输入腿部标识 (FL, FR, BL, BR): ").upper().strip()
        joint = input("请输入关节标识 (HIP, THIGH, KNEE): ").upper().strip()
        angle = int(input("请输入角度 (0-180): "))

        if leg in LEGS_CONFIG and joint in LEGS_CONFIG[leg]:
            if set_servo_angle(leg, joint, angle):
                print(f"✅ {leg}_{joint} 舵机已设置到 {angle}°")
            else:
                print("❌ 舵机设置失败")
        else:
            print("❌ 无效的腿部或关节标识")

    except ValueError:
        print("❌ 请输入有效的角度数值")
    except Exception as e:
        print(f"❌ 测试失败: {e}")

def test_individual_leg():
    """测试单条腿"""
    print("\n=== 单腿测试 ===")

    try:
        leg = input("请输入腿部标识 (FL, FR, BL, BR): ").upper().strip()

        if leg not in LEGS_CONFIG:
            print("❌ 无效的腿部标识")
            return

        print(f"测试 {leg} 腿的三个关节...")

        # 测试序列
        test_sequence = [
            (90, 90, 90, "中间位置"),
            (60, 45, 60, "收缩状态"),
            (120, 135, 120, "伸展状态"),
            (90, 90, 90, "回到中间")
        ]

        for hip, thigh, knee, desc in test_sequence:
            print(f"  {desc}: HIP={hip}° THIGH={thigh}° KNEE={knee}°")
            set_leg_angles(leg, hip, thigh, knee, speed_ms=500)
            time.sleep(1)

        print("✅ 单腿测试完成")

    except Exception as e:
        print(f"❌ 单腿测试失败: {e}")

def test_all_servos():
    """测试所有舵机"""
    print("\n=== 全舵机测试 ===")
    info("TEST", "开始测试所有12个舵机...")

    # 测试所有舵机的中间位置
    info("TEST", "测试中间位置 90°...")
    for leg in LEGS_CONFIG.keys():
        for joint in ['HIP', 'THIGH', 'KNEE']:
            servo_key = f"{leg}_{joint}"
            if servo_key in servos:
                set_servo_angle(leg, joint, 90)
                servo_info = format_servo_key_with_pin(servo_key)
                print(f"  {servo_info} 设置到 90°")

    time.sleep(2)

    # 测试所有舵机的极限位置
    test_angles = [(60, "最小"), (120, "最大")]

    for angle, desc in test_angles:
        info("TEST", "测试%s位置 %d°...", desc, angle)
        for leg in LEGS_CONFIG.keys():
            for joint in ['HIP', 'THIGH', 'KNEE']:
                set_servo_angle(leg, joint, angle, speed_ms=200)
        time.sleep(2)

    # 回到中间位置
    stand_up_pose()
    info("TEST", "全舵机测试完成")

def calibration_mode():
    """校准模式 - 逐个调整每个舵机"""
    print("\n=== 舵机校准模式 ===")
    info("CAL", "开始逐个调整每个舵机的角度...")

    for leg in ['FL', 'FR', 'BL', 'BR']:
        for joint in ['HIP', 'THIGH', 'KNEE']:
            servo_info = get_servo_info(leg, joint)
            print(f"\n🔧 校准 {servo_info}")

            try:
                angle = int(input(f"请输入 {servo_info} 的角度 (0-180, 默认90): ") or "90")
                set_servo_angle(leg, joint, angle)
                print(f"✅ {servo_info} 设置为 {angle}°")

                cont = input("按回车继续，输入'skip'跳过后续舵机: ").strip().lower()
                if cont == 'skip':
                    break

            except ValueError:
                print("❌ 无效角度，使用默认值90°")
                set_servo_angle(leg, joint, 90)
            except KeyboardInterrupt:
                print("\n⚠️ 校准中断")
                return

    info("CAL", "校准模式完成")

# ======================
# 控制菜单
# ======================
def show_menu():
    """显示控制菜单"""
    print("\n" + "="*60)
    print("🕷️ ESP32 12舵机4足蜘蛛机器人调试工具")
    print("="*60)
    print("🔧 基础控制:")
    print("1. 站立姿势")
    print("2. 坐下姿势")
    print("3. 蹲下姿势")
    print("4. 单舵机测试")
    print("5. 单腿测试")
    print("6. 全舵机测试")
    print("7. 校准模式")

    print("\n🕷️ 腿部单独调试:")
    print("31. 前左腿 (FL) 调试 - GPIO 13,14,16")
    print("32. 前右腿 (FR) 调试 - GPIO 17,18,19")
    print("33. 后左腿 (BL) 调试 - GPIO 21,22,23")
    print("34. 后右腿 (BR) 调试 - GPIO 25,26,27")
    print("35. 所有腿顺序调试")
    print("36. 自定义GPIO调试")

    print("\n🚶 步态控制:")
    print("11. 波浪步态 (从FL开始)")
    print("12. 波浪步态 (从FR开始)")
    print("13. 波浪步态 (从BL开始)")
    print("14. 波浪步态 (从BR开始)")
    print("15. 三脚步态")
    print("16. 左转")
    print("17. 右转")

    print("\n🎯 快速动作:")
    print("21. 所有腿向前伸展")
    print("22. 所有腿向后伸展")
    print("23. 左侧腿抬起")
    print("24. 右侧腿抬起")
    print("25. 对角腿抬起 (FL+BR)")
    print("26. 对角腿抬起 (FR+BL)")

    print("\n0. 退出程序")
    print("="*60)

def get_user_input():
    """获取用户输入"""
    try:
        choice = input("\n请选择功能 (0-30): ").strip()
        return int(choice) if choice.isdigit() else -1
    except KeyboardInterrupt:
        return 0
    except:
        return -1

# ======================
# 腿部单独调试函数
# ======================
def debug_leg_by_gpio(hip_gpio, thigh_gpio, knee_gpio, speed_ms=500):
    """
    通用腿部调试函数 - 通过GPIO编号控制一条腿的三个关节
    hip_gpio: 髋关节GPIO编号
    thigh_gpio: 大腿关节GPIO编号
    knee_gpio: 膝关节GPIO编号
    speed_ms: 动作速度 (毫秒)
    """
    try:
        # 查找对应的舵机标识
        hip_servo = GPIO_TO_SERVO.get(hip_gpio)
        thigh_servo = GPIO_TO_SERVO.get(thigh_gpio)
        knee_servo = GPIO_TO_SERVO.get(knee_gpio)

        leg_name = "未知"
        for leg, config in LEGS_CONFIG.items():
            if config.get('HIP') == hip_gpio:
                leg_name = leg
                break

        print(f"\n🔧 开始调试 {leg_name} 腿 (GPIO: {hip_gpio}, {thigh_gpio}, {knee_gpio})")

        # 速度档位设置
        speeds = {
            'slow': 800,    # 慢速
            'fast': 300     # 快速
        }

        current_speed = speed_ms if speed_ms in speeds.values() else speeds['fast']
        speed_desc = '慢速' if current_speed >= 600 else '快速'

        print(f"🎯 角度控制在30度左右，速度: {speed_desc}")

        # 调试序列 - 30度左右的角度变化
        debug_sequence = [
            # (髋角度, 大腿角度, 膝盖角度, 描述)
            (90, 90, 90, "初始中间位置"),
            (75, 75, 75, "向内收缩约15度"),
            (105, 105, 105, "向外伸展约15度"),
            (90, 120, 60, "大腿后摆+膝盖弯曲"),
            (90, 60, 120, "大腿前摆+膝盖伸直"),
            (90, 90, 90, "回到中间位置")
        ]

        for hip_angle, thigh_angle, knee_angle, desc in debug_sequence:
            print(f"  📍 {desc}: HIP={hip_angle}° THIGH={thigh_angle}° KNEE={knee_angle}°")

            # 分别控制三个关节
            if hip_servo and hip_servo in servos:
                leg, joint = hip_servo.split('_', 1)
                set_servo_angle(leg, joint, hip_angle, current_speed)
                print(f"    ✅ {hip_servo}(GPIO{hip_gpio}) -> {hip_angle}°")

            if thigh_servo and thigh_servo in servos:
                leg, joint = thigh_servo.split('_', 1)
                set_servo_angle(leg, joint, thigh_angle, current_speed)
                print(f"    ✅ {thigh_servo}(GPIO{thigh_gpio}) -> {thigh_angle}°")

            if knee_servo and knee_servo in servos:
                leg, joint = knee_servo.split('_', 1)
                set_servo_angle(leg, joint, knee_angle, current_speed)
                print(f"    ✅ {knee_servo}(GPIO{knee_gpio}) -> {knee_angle}°")

            time.sleep(current_speed / 1000.0 + 0.5)  # 动作时间+暂停

        print(f"✅ {leg_name} 腿调试完成")
        return True

    except Exception as e:
        print(f"❌ 腿部调试失败: {e}")
        return False

def debug_leg_fl(speed='fast'):
    """调试前左腿 (FL) - GPIO 13, 14, 16"""
    speed_ms = 800 if speed == 'slow' else 300
    print("\n🕷️ 调试前左腿 (FL)")
    return debug_leg_by_gpio(13, 14, 16, speed_ms)

def debug_leg_fr(speed='fast'):
    """调试前右腿 (FR) - GPIO 17, 18, 19"""
    speed_ms = 800 if speed == 'slow' else 300
    print("\n🕷️ 调试前右腿 (FR)")
    return debug_leg_by_gpio(17, 18, 19, speed_ms)

def debug_leg_bl(speed='fast'):
    """调试后左腿 (BL) - GPIO 21, 22, 23"""
    speed_ms = 800 if speed == 'slow' else 300
    print("\n🕷️ 调试后左腿 (BL)")
    return debug_leg_by_gpio(21, 22, 23, speed_ms)

def debug_leg_br(speed='fast'):
    """调试后右腿 (BR) - GPIO 25, 26, 27"""
    speed_ms = 800 if speed == 'slow' else 300
    print("\n🕷️ 调试后右腿 (BR)")
    return debug_leg_by_gpio(25, 26, 27, speed_ms)

def debug_all_legs_sequentially(speed='fast'):
    """顺序调试所有四条腿"""
    print("\n🕷️ 顺序调试所有四条腿")
    legs = [
        ('前左腿 (FL)', debug_leg_fl),
        ('前右腿 (FR)', debug_leg_fr),
        ('后左腿 (BL)', debug_leg_bl),
        ('后右腿 (BR)', debug_leg_br)
    ]

    success_count = 0
    for leg_name, debug_func in legs:
        print(f"\n{'='*50}")
        try:
            if debug_func(speed):
                success_count += 1
                print(f"✅ {leg_name} 调试成功")
            else:
                print(f"❌ {leg_name} 调试失败")
        except Exception as e:
            print(f"❌ {leg_name} 调试异常: {e}")

        time.sleep(1)  # 腿之间的间隔

    print(f"\n🎯 所有腿调试完成，成功: {success_count}/4")
    return success_count == 4

def custom_gpio_debug():
    """自定义GPIO调试 - 用户输入三个GPIO编号"""
    print("\n🔧 自定义GPIO调试")
    try:
        hip_gpio = int(input("请输入髋关节GPIO编号: ").strip())
        thigh_gpio = int(input("请输入大腿关节GPIO编号: ").strip())
        knee_gpio = int(input("请输入膝关节GPIO编号: ").strip())

        speed_choice = input("选择速度 (1=慢速, 2=快速, 默认快速): ").strip()
        speed = 'slow' if speed_choice == '1' else 'fast'

        print(f"\n🎯 开始调试 GPIO组合: {hip_gpio}, {thigh_gpio}, {knee_gpio}")
        return debug_leg_by_gpio(hip_gpio, thigh_gpio, knee_gpio,
                               800 if speed == 'slow' else 300)

    except ValueError:
        print("❌ 请输入有效的GPIO编号")
        return False
    except Exception as e:
        print(f"❌ 自定义调试失败: {e}")
        return False

# ======================
# 快速动作函数
# ======================
def legs_forward():
    """所有腿向前伸展"""
    print("🦵 所有腿向前伸展...")
    forward_angles = {
        'FL': {'HIP': 90, 'THIGH': 60, 'KNEE': 100},
        'FR': {'HIP': 90, 'THIGH': 60, 'KNEE': 100},
        'BL': {'HIP': 90, 'THIGH': 60, 'KNEE': 100},
        'BR': {'HIP': 90, 'THIGH': 60, 'KNEE': 100}
    }

    for leg, angles in forward_angles.items():
        set_leg_angles(leg, angles['HIP'], angles['THIGH'], angles['KNEE'], speed_ms=800)

def legs_backward():
    """所有腿向后伸展"""
    print("🦵 所有腿向后伸展...")
    backward_angles = {
        'FL': {'HIP': 90, 'THIGH': 120, 'KNEE': 80},
        'FR': {'HIP': 90, 'THIGH': 120, 'KNEE': 80},
        'BL': {'HIP': 90, 'THIGH': 120, 'KNEE': 80},
        'BR': {'HIP': 90, 'THIGH': 120, 'KNEE': 80}
    }

    for leg, angles in backward_angles.items():
        set_leg_angles(leg, angles['HIP'], angles['THIGH'], angles['KNEE'], speed_ms=800)

def left_side_up():
    """左侧腿抬起"""
    print("🦵 左侧腿抬起...")
    set_leg_angles('FL', knee_angle=60, thigh_angle=45, speed_ms=600)
    set_leg_angles('BL', knee_angle=60, thigh_angle=45, speed_ms=600)

def right_side_up():
    """右侧腿抬起"""
    print("🦵 右侧腿抬起...")
    set_leg_angles('FR', knee_angle=60, thigh_angle=45, speed_ms=600)
    set_leg_angles('BR', knee_angle=60, thigh_angle=45, speed_ms=600)

def diagonal_up_fl_br():
    """对角腿抬起 (FL+BR)"""
    print("🦵 对角腿抬起 (FL+BR)...")
    set_leg_angles('FL', knee_angle=60, thigh_angle=45, speed_ms=600)
    set_leg_angles('BR', knee_angle=60, thigh_angle=45, speed_ms=600)

def diagonal_up_fr_bl():
    """对角腿抬起 (FR+BL)"""
    print("🦵 对角腿抬起 (FR+BL)...")
    set_leg_angles('FR', knee_angle=60, thigh_angle=45, speed_ms=600)
    set_leg_angles('BL', knee_angle=60, thigh_angle=45, speed_ms=600)

# ======================
# 主程序
# ======================
def run():
    """主运行函数"""
    try:
        print("\n" + "="*60)
        print("🕷️ ESP32 12舵机4足蜘蛛机器人调试工具启动!")
        print("="*60)

        # 初始化舵机
        if not init_servos():
            print("❌ 舵机初始化失败，程序退出")
            return

        print(f"✅ 成功初始化 {len(servos)} 个舵机")
        print("🎯 支持FL(前左)、FR(前右)、BL(后左)、BR(后右)四条腿")
        print("🦵 每条腿有HIP(髋)、THIGH(大腿)、KNEE(膝盖)三个关节")
        print("🔧 舵机频率: 50Hz, 角度范围: 0-180度")
        print("="*60 + "\n")

        # 初始姿势
        info("INIT", "设置初始站立姿势")
        stand_up_pose(speed_ms=1500)

        # 主循环
        info("MAIN", "进入控制台交互模式")
        while True:
            show_menu()
            choice = get_user_input()

            if choice == 0:
                print("👋 程序退出中...")
                break

            # 基础控制
            elif choice == 1:
                stand_up_pose()
            elif choice == 2:
                sit_pose()
            elif choice == 3:
                crouch_pose()
            elif choice == 4:
                test_single_servo()
            elif choice == 5:
                test_individual_leg()
            elif choice == 6:
                test_all_servos()
            elif choice == 7:
                calibration_mode()

            # 腿部单独调试
            elif choice == 31:
                debug_leg_fl()
            elif choice == 32:
                debug_leg_fr()
            elif choice == 33:
                debug_leg_bl()
            elif choice == 34:
                debug_leg_br()
            elif choice == 35:
                debug_all_legs_sequentially()
            elif choice == 36:
                custom_gpio_debug()

            # 步态控制
            elif choice == 11:
                wave_gait('FL')
            elif choice == 12:
                wave_gait('FR')
            elif choice == 13:
                wave_gait('BL')
            elif choice == 14:
                wave_gait('BR')
            elif choice == 15:
                tripod_gait()
            elif choice == 16:
                turn_left()
            elif choice == 17:
                turn_right()

            # 快速动作
            elif choice == 21:
                legs_forward()
            elif choice == 22:
                legs_backward()
            elif choice == 23:
                left_side_up()
            elif choice == 24:
                right_side_up()
            elif choice == 25:
                diagonal_up_fl_br()
            elif choice == 26:
                diagonal_up_fr_bl()

            else:
                print("❌ 无效选择，请输入有效数字")

            # 清理当前行，准备下次菜单显示
            print("\n按回车键继续...")
            try:
                input()
            except KeyboardInterrupt:
                break

    except KeyboardInterrupt:
        print("\n⚠️ 用户中断程序")
    except Exception as e:
        warn("MAIN", "主程序异常: %s", str(e))
    finally:
        # 清理资源 - 关闭所有舵机信号
        info("MAIN", "清理舵机资源...")
        for servo_key, servo in servos.items():
            try:
                servo.duty(0)
                servo_info = format_servo_key_with_pin(servo_key)
                debug("CLEAN", "关闭舵机信号: %s", servo_info)
            except:
                pass

        print("\n🔌 所有舵机信号已关闭")
        info("MAIN", "程序已退出")

# ======================
# 快速测试模式
# ======================
def quick_test():
    """快速测试模式 - 自动执行基本测试"""
    print("\n🚀 12舵机蜘蛛机器人快速测试启动!")

    try:
        # 初始化
        if not init_servos():
            print("❌ 初始化失败，测试终止")
            return

        print("✅ 舵机初始化成功")

        # 1. 站立测试
        print("\n1. 站立姿势测试...")
        stand_up_pose(speed_ms=1000)
        time.sleep(1)

        # 2. 单腿测试
        print("\n2. 单腿测试 (FL腿)...")
        set_leg_angles('FL', 60, 45, 60, speed_ms=500)
        time.sleep(1)
        set_leg_angles('FL', 90, 90, 90, speed_ms=500)
        time.sleep(1)

        # 3. 姿势切换测试
        print("\n3. 姿势切换测试...")
        sit_pose(speed_ms=800)
        time.sleep(1)
        stand_up_pose(speed_ms=800)
        time.sleep(1)

        # 4. 简单步态测试
        print("\n4. 简单步态测试...")
        wave_gait('FL', step_count=2, speed_ms=400)

        print("\n✅ 快速测试完成!")

    except Exception as e:
        print(f"❌ 快速测试失败: {e}")

# ======================
# 程序入口
# ======================
if __name__ == "__main__":
    import sys

    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        quick_test()
    else:
        run()