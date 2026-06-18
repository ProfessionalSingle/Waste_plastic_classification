from adafruit_pca9685 import PCA9685
from board import SCL, SDA
import busio
import time
import json
from datetime import datetime

# === Setup I2C and PCA9685 ===
i2c = busio.I2C(SCL, SDA)
pca = PCA9685(i2c)
pca.frequency = 50

# === Configuration ===
TORQUE_LOCK_ENABLED = True
LOG_FILE = "commands.log"
SEQUENCE_FILE = "sequences.json"

# Servo setup
SERVOS = {
    1: {'name': 'Base',         'channel': 0, 'type': 'continuous'},
    2: {'name': 'Shoulder',     'channel': 1, 'type': 'continuous'},
    3: {'name': 'Elbow',        'channel': 2, 'type': 'continuous'},
    4: {'name': 'Wrist Roll',   'channel': 3, 'type': 'positional'},
    5: {'name': 'Wrist Pitch',  'channel': 4, 'type': 'positional'},
    6: {'name': 'Gripper',      'channel': 5, 'type': 'positional'},
}

# Timing constants
STOP_PULSE_US = 1500
MAX_PULSE_US = 2500
MIN_PULSE_US = 500
TIMINGS = {
    'cw':   {90: 0.25, 180: 0.50, 270: 0.75, 360: 1.00},
    'ccw':  {90: 0.28, 180: 0.56, 270: 0.84, 360: 1.12}
}

# Teaching mode memory
current_routine_name = None
current_routine = []

# === Helpers ===
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

def log_command(cmd):
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.now().isoformat()} - {cmd}\n")

# === Movement Functions ===
def move_continuous_servo(servo_id, direction, degrees):
    if SERVOS[servo_id]['type'] != 'continuous':
        print(f"[ERROR] Servo {servo_id} is not continuous")
        return
    if direction not in ['cw', 'ccw']:
        print("[ERROR] Direction must be 'cw' or 'ccw'")
        return
    if degrees == 0:
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
    if SERVOS[servo_id]['type'] != 'positional':
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
        pca.channels[SERVOS[servo_id]['channel']].duty_cycle = pulse_us_to_duty(pulse)
        print(f"[INFO] {SERVOS[servo_id]['name']} torque locked")

def stop_all_servos():
    for sid, servo in SERVOS.items():
        if servo['type'] == 'continuous':
            stop_servo(sid)
        else:
            pca.channels[servo['channel']].duty_cycle = 0
    print("[INFO] All servos stopped.")

# === Sequence Management ===
def save_sequence_file():
    try:
        with open(SEQUENCE_FILE, "r") as f:
            all_sequences = json.load(f)
    except FileNotFoundError:
        all_sequences = {}

    all_sequences[current_routine_name] = current_routine

    with open(SEQUENCE_FILE, "w") as f:
        json.dump(all_sequences, f, indent=4)
    print(f"[INFO] Routine '{current_routine_name}' saved.")

def run_sequence(name):
    try:
        with open(SEQUENCE_FILE, "r") as f:
            sequences = json.load(f)
        sequence = sequences[name]
    except (FileNotFoundError, KeyError):
        print(f"[ERROR] Routine '{name}' not found.")
        return

    for step in sequence:
        sid = step['servo']
        if step['type'] == 'positional':
            move_positional_servo(sid, step['angle'])
        else:
            move_continuous_servo(sid, step['direction'], step['degrees'])

# === Command Loop ===
def command_loop():
    global current_routine, current_routine_name

    print("Commands: move <id> <angle|cw|ccw> <deg> | stop <id>")
    print("create_routine <name> | save_routine <name> | run <name> | exit")

    while True:
        try:
            cmd = input(">> ").strip().split()
            if not cmd:
                continue

            if cmd[0] == "exit":
                break

            elif cmd[0] == "create_routine" and len(cmd) == 2:
                current_routine_name = cmd[1]
                current_routine = []
                print(f"[INFO] Teaching mode started for routine '{current_routine_name}'.")

            elif cmd[0] == "save_routine" and len(cmd) == 2:
                if cmd[1] == current_routine_name:
                    save_sequence_file()
                else:
                    print("[ERROR] No active routine by that name.")

            elif cmd[0] == "run" and len(cmd) == 2:
                run_sequence(cmd[1])

            elif cmd[0] == "move" and len(cmd) == 4:
                sid = int(cmd[1])
                direction = cmd[2]
                degrees = float(cmd[3])
                move_continuous_servo(sid, direction, degrees)

                if current_routine_name:
                    save = input(f"Save this step to routine '{current_routine_name}'? (y/n): ").strip().lower()
                    if save == 'y':
                        current_routine.append({
                            'type': 'continuous',
                            'servo': sid,
                            'direction': direction,
                            'degrees': degrees
                        })

            elif cmd[0] == "move" and len(cmd) == 3:
                sid = int(cmd[1])
                angle = float(cmd[2])
                move_positional_servo(sid, angle)

                if current_routine_name:
                    save = input(f"Save this step to routine '{current_routine_name}'? (y/n): ").strip().lower()
                    if save == 'y':
                        current_routine.append({
                            'type': 'positional',
                            'servo': sid,
                            'angle': angle
                        })

            elif cmd[0] == "stop" and len(cmd) == 2:
                stop_servo(int(cmd[1]))

            else:
                print("[ERROR] Unknown command.")

            log_command(" ".join(cmd))

        except Exception as e:
            print(f"[ERROR] {e}")

    stop_all_servos()

# === Main ===
if __name__ == '__main__':
    print("[INFO] Robot arm controller ready.")
    stop_all_servos()
    command_loop()
