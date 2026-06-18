import json
import time
from adafruit_pca9685 import PCA9685
from board import SCL, SDA
import busio
import os

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

# Routine storage (in-memory)
routines = {}

# Teaching mode memory
current_routine_name = None
current_routine = []

# Load saved routines from file
def load_routines():
    try:
        with open('routines.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Save routines to file
def save_routines():
    with open('routines.json', 'w') as f:
        json.dump(routines, f, indent=4)

# Append command log with timestamp
def log_command(command_str):
    with open("commands.log", "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {command_str}\n")

# Convert pulse_us to duty cycle for PCA9685
def pulse_us_to_duty(pulse_us):
    return int(pulse_us * pca.frequency * 65536 / 1_000_000)

# Set servo pulse width
def set_servo_pulse(servo_id, pulse_us):
    ch = SERVOS[servo_id]['channel']
    pca.channels[ch].duty_cycle = pulse_us_to_duty(pulse_us)

# Stop servo
def stop_servo(servo_id):
    if SERVOS[servo_id]['type'] == 'continuous':
        set_servo_pulse(servo_id, STOP_PULSE_US)

# Calculate duration based on the degrees to move and direction
def get_duration_from_degrees(deg, direction):
    for d in sorted(TIMINGS[direction].keys()):
        if deg <= d:
            return TIMINGS[direction][d] * deg / d
    return TIMINGS[direction][360] * deg / 360

# Move continuous servo
def move_continuous_servo(servo_id, direction, degrees, speed_factor=1):
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
    duration = get_duration_from_degrees(degrees, direction) * speed_factor

    print(f"[INFO] Moving {SERVOS[servo_id]['name']} {direction} by {degrees}° for {duration:.2f}s")
    set_servo_pulse(servo_id, pulse)
    time.sleep(duration)
    stop_servo(servo_id)
    print(f"[INFO] {SERVOS[servo_id]['name']} stopped")

# Move positional servo (angle 0-180)
def move_positional_servo(servo_id, angle, speed_factor=1):
    if servo_id not in SERVOS or SERVOS[servo_id]['type'] != 'positional':
        print(f"[ERROR] Servo {servo_id} is not positional")
        return

    angle = max(0, min(180, angle))
    min_pulse = 600
    max_pulse = 2300
    pulse = min_pulse + (max_pulse - min_pulse) * (angle / 180)
    set_servo_pulse(servo_id, pulse)
    print(f"[INFO] Moved {SERVOS[servo_id]['name']} to {angle}°")
    time.sleep(0.5 * speed_factor)

    if TORQUE_LOCK_ENABLED:
        pca.channels[SERVOS[servo_id]['channel']].duty_cycle = 0
        print(f"[INFO] {SERVOS[servo_id]['name']} torque locked (PWM off)")

# Stop all servos
def stop_all_servos():
    for sid, servo in SERVOS.items():
        if servo['type'] == 'continuous':
            stop_servo(sid)
        else:
            pca.channels[servo['channel']].duty_cycle = 0
    print("[INFO] All servos stopped.")

# Teaching mode: Record commands into routine (updated with interactive prompts)
def create_routine(name):
    global current_routine_name, current_routine
    current_routine_name = name
    current_routine = []
    print(f"\n[TEACHING MODE] Started recording routine: '{name}'")
    print("After each movement command, you'll be asked if you want to save it to the routine")
    print("When finished, enter 'save_routine' to save")

# Execute saved routine
def run_routine(name):
    if name not in routines:
        print(f"[ERROR] Routine '{name}' not found")
        return

    print(f"[INFO] Running routine '{name}'")
    for step in routines[name]:
        if step['type'] == 'continuous':
            move_continuous_servo(step['servo'], step['direction'], step['degrees'])
        elif step['type'] == 'positional':
            move_positional_servo(step['servo'], step['angle'])

# List available routines
def list_routines():
    if not routines:
        print("[INFO] No routines available")
        return
        
    print("[INFO] Available routines:")
    for name in routines:
        print(f" - {name} ({len(routines[name])} steps)")

# Delete a routine
def delete_routine(name):
    if name in routines:
        del routines[name]
        save_routines()
        print(f"[INFO] Routine '{name}' deleted")
    else:
        print(f"[ERROR] Routine '{name}' not found")

# Rename a routine
def rename_routine(old_name, new_name):
    if old_name in routines:
        routines[new_name] = routines.pop(old_name)
        save_routines()
        print(f"[INFO] Routine '{old_name}' renamed to '{new_name}'")
    else:
        print(f"[ERROR] Routine '{old_name}' not found")

# Adjust speed multiplier
def adjust_speed(multiplier):
    multiplier = max(0.1, min(2.0, multiplier))  # Clamp between 0.1 and 2.0
    print(f"[INFO] Speed multiplier set to {multiplier:.1f}")
    return multiplier

# Command loop for interactive control (updated with interactive teaching prompts)
def command_loop():
    global current_routine, current_routine_name
    routines.update(load_routines())

    print("\nRobot Arm Control System")
    print("Available commands:")
    print("  move <servo_id> <cw|ccw> <degrees> - Move continuous servo")
    print("  move <servo_id> <angle> - Move positional servo (0-180)")
    print("  create_routine <name> - Start recording new routine")
    print("  save_routine - Save current routine")
    print("  run_routine <name> - Execute saved routine")
    print("  list_routines - List all saved routines")
    print("  delete_routine <name> - Delete a routine")
    print("  rename_routine <old> <new> - Rename a routine")
    print("  speed <multiplier> - Set speed (0.1-2.0)")
    print("  stop_all - Stop all servos immediately")
    print("  show_routine_path - Display the absolute path to routines.json")
    print("  exit - Quit program\n")

    speed_factor = 1.0

    while True:
        try:
            cmd = input(">> ").strip().split()
            if not cmd:
                continue

            if cmd[0] == 'exit':
                break

            elif cmd[0] == 'move' and len(cmd) == 4:  # Continuous servo
                servo_id = int(cmd[1])
                direction = cmd[2].lower()
                degrees = float(cmd[3])
                move_continuous_servo(servo_id, direction, degrees, speed_factor)
                
                if current_routine_name:
                    save = input(f"Save this movement to routine '{current_routine_name}'? (y/n): ").strip().lower()
                    if save == 'y':
                        current_routine.append({
                            'type': 'continuous',
                            'servo': servo_id,
                            'direction': direction,
                            'degrees': degrees
                        })
                        print(f"[INFO] Added step {len(current_routine)} to routine")

            elif cmd[0] == 'move' and len(cmd) == 3:  # Positional servo
                servo_id = int(cmd[1])
                angle = float(cmd[2])
                move_positional_servo(servo_id, angle, speed_factor)
                
                if current_routine_name:
                    save = input(f"Save this movement to routine '{current_routine_name}'? (y/n): ").strip().lower()
                    if save == 'y':
                        current_routine.append({
                            'type': 'positional',
                            'servo': servo_id,
                            'angle': angle
                        })
                        print(f"[INFO] Added step {len(current_routine)} to routine")

            elif cmd[0] == 'create_routine' and len(cmd) == 2:
                create_routine(cmd[1])

            elif cmd[0] == 'save_routine':
                if current_routine_name and current_routine:
                    routines[current_routine_name] = current_routine
                    save_routines()
                    print(f"[INFO] Saved routine '{current_routine_name}' with {len(current_routine)} steps")
                    current_routine_name = None
                    current_routine = []
                else:
                    print("[ERROR] No active routine to save or routine is empty")

            elif cmd[0] == 'run_routine' and len(cmd) == 2:
                run_routine(cmd[1])

            elif cmd[0] == 'list_routines':
                list_routines()

            elif cmd[0] == 'delete_routine' and len(cmd) == 2:
                delete_routine(cmd[1])

            elif cmd[0] == 'rename_routine' and len(cmd) == 3:
                rename_routine(cmd[1], cmd[2])

            elif cmd[0] == 'speed' and len(cmd) == 2:
                speed_factor = float(cmd[1])
                adjust_speed(speed_factor)

            elif cmd[0] == 'stop_all':
                stop_all_servos()

            elif cmd[0] == 'show_routine_path':
                json_path = os.path.abspath('routines.json')
                print(f"[INFO] Routine file is located at: {json_path}")

            else:
                print("[ERROR] Invalid command")

        except Exception as e:
            print(f"[ERROR] {e}")

if __name__ == '__main__':
    command_loop()
