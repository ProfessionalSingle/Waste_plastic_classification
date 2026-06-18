from adafruit_pca9685 import PCA9685
from board import SCL, SDA
import busio
import time

# Setup I2C and PCA9685
i2c = busio.I2C(SCL, SDA)
pca = PCA9685(i2c)
pca.frequency = 50

# Enable or disable torque lock for positional servos after movement
TORQUE_LOCK_ENABLED = True

# Servo configuration: type 'positional' or 'continuous'
SERVOS = {
    1: {'name': 'Base',         'channel': 0, 'type': 'continuous'},
    2: {'name': 'Shoulder',     'channel': 1, 'type': 'continuous'},
    3: {'name': 'Elbow',        'channel': 2, 'type': 'continuous'},
    4: {'name': 'Wrist Roll',   'channel': 3, 'type': 'positional'},
    5: {'name': 'Wrist Pitch',  'channel': 4, 'type': 'positional'},
    6: {'name': 'Gripper',      'channel': 5, 'type': 'positional'},
}

# Constants for continuous servo control
STOP_PULSE_US = 1500
MAX_PULSE_US = 2500
MIN_PULSE_US = 500

# Calibrated timing lookup table for elbow servo (continuous)
TIMINGS = {
    'cw':   {90: 0.25, 180: 0.50, 270: 0.75, 360: 1.00},
    'ccw':  {90: 0.28, 180: 0.56, 270: 0.84, 360: 1.12}
}

def pulse_us_to_duty(pulse_us):
    return int(pulse_us * pca.frequency * 65536 / 1_000_000)

def set_servo_pulse(servo_id, pulse_us):
    ch = SERVOS[servo_id]['channel']
    pca.channels[ch].duty_cycle = pulse_us_to_duty(pulse_us)

def stop_servo(servo_id):
    if SERVOS[servo_id]['type'] == 'continuous':
        set_servo_pulse(servo_id, STOP_PULSE_US)

def get_duration_from_degrees(deg, direction):
    for d in sorted(TIMINGS[direction].keys()):
        if deg <= d:
            return TIMINGS[direction][d] * deg / d
    return TIMINGS[direction][360] * deg / 360

def move_continuous_servo(servo_id, direction, degrees):
    if servo_id not in SERVOS or SERVOS[servo_id]['type'] != 'continuous':
        print(f"[ERROR] Servo {servo_id} is not a continuous servo")
        return

    if direction not in ['cw', 'ccw']:
        print("[ERROR] Direction must be 'cw' or 'ccw'")
        return

    if degrees == 0:
        print(f"[INFO] No rotation needed for {SERVOS[servo_id]['name']} (0° input)")
        stop_servo(servo_id)
        return

    pulse = 1700 if direction == 'cw' else 1300
    duration = get_duration_from_degrees(degrees, direction)

    print(f"[INFO] Moving {SERVOS[servo_id]['name']} {direction} by {degrees}° for {duration:.2f}s")
    set_servo_pulse(servo_id, pulse)
    time.sleep(duration)
    stop_servo(servo_id)
    print(f"[INFO] {SERVOS[servo_id]['name']} stopped")

def move_positional_servo(servo_id, angle):
    if servo_id not in SERVOS or SERVOS[servo_id]['type'] != 'positional':
        print(f"[ERROR] Servo {servo_id} is not positional")
        return

    angle = max(0, min(180, angle))
    min_pulse = 600
    max_pulse = 2300
    pulse = min_pulse + (max_pulse - min_pulse) * (angle / 180)
    set_servo_pulse(servo_id, pulse)
    print(f"[INFO] Moved {SERVOS[servo_id]['name']} to {angle}°")
    time.sleep(0.5)

    if TORQUE_LOCK_ENABLED:
        pca.channels[SERVOS[servo_id]['channel']].duty_cycle = 0
        print(f"[INFO] {SERVOS[servo_id]['name']} torque locked (PWM off)")

def stop_all_servos():
    for sid, servo in SERVOS.items():
        if servo['type'] == 'continuous':
            stop_servo(sid)
        else:
            pca.channels[servo['channel']].duty_cycle = 0
    print("[INFO] All servos stopped.")

def demo_routine():
    # Home Position
    print("[INFO] Moving to Home position...")
    move_continuous_servo(2, 'ccw', 270*5)  # Shoulder up
    move_continuous_servo(3, 'ccw', 270*3)  # Elbow up
    move_positional_servo(4, 90)
    move_positional_servo(5, 45)
    move_positional_servo(6, 180)  # Gripper open

    # Pick Position
    print("[INFO] Moving to Pick position...")
    move_continuous_servo(2, 'cw', 270*4)   # Shoulder down
    move_continuous_servo(3, 'cw', 270*3)   # Elbow down
    move_positional_servo(6, 0)             # Gripper close

    # Back to Home (Gripper closed)
    print("[INFO] Returning to Home position with gripper closed...")
    move_continuous_servo(2, 'ccw', 270*4)  # Shoulder up
    move_continuous_servo(3, 'ccw', 270*3)  # Elbow up
    move_positional_servo(6, 0)

    # Place Position
    print("[INFO] Moving to Place position...")
    move_continuous_servo(1, 'cw', 180)     # Base rotate
    move_continuous_servo(2, 'cw', 270*3)   # Shoulder down
    move_continuous_servo(3, 'cw', 270*2)   # Elbow down
    move_positional_servo(6, 180)           # Gripper open

    # Back to Home (Final)
    print("[INFO] Returning to final Home position...")
    move_continuous_servo(1, 'ccw', 180)    # Base back
    move_continuous_servo(2, 'ccw', 270*3)  # Shoulder up
    move_continuous_servo(3, 'ccw', 270*3)  # Elbow up (3x)

def command_loop():
    print("Commands: move <id> <angle|cw|ccw> <degrees> | stop <id> | demo | exit")
    while True:
        try:
            cmd = input(">> ").strip().split()
            if not cmd:
                continue
            if cmd[0] == 'exit':
                break
            elif cmd[0] == 'move' and len(cmd) == 4:
                move_continuous_servo(int(cmd[1]), cmd[2], float(cmd[3]))
            elif cmd[0] == 'move' and len(cmd) == 3:
                move_positional_servo(int(cmd[1]), float(cmd[2]))
            elif cmd[0] == 'stop' and len(cmd) == 2:
                stop_servo(int(cmd[1]))
            elif cmd[0] == 'demo':
                demo_routine()
            else:
                print("[ERROR] Invalid command")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[ERROR] {e}")
    stop_all_servos()

if __name__ == '__main__':
    print("[INFO] Robot arm control ready.")
    stop_all_servos()
    command_loop()
