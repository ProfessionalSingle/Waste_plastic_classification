import socket
import math
from adafruit_pca9685 import PCA9685
from board import SCL, SDA
import busio
from sympy import symbols, cos, sin, pi, Matrix, atan2, sqrt, simplify
import time

# Servo settings
SG90_MIN = 150
SG90_MAX = 600
MG995_MIN = 150
MG995_MAX = 600

servo_channels = {
    'theta1': 0,
    'theta2': 1,
    'theta3': 2,
    'theta4': 3,
    'theta5': 4,
    'theta6': 5
}

# Link lengths in mm
L1 = 56
L2 = 50.485
L3 = 107.915
L4 = 96.374
L5 = 29.5
L6 = 77.17

# Initialize I2C and PCA9685
i2c = busio.I2C(SCL, SDA)
pca = PCA9685(i2c)
pca.frequency = 50

def angle_to_pwm(angle_deg, servo_type='MG995'):
    angle = max(0, min(180, angle_deg))
    if servo_type == 'SG90':
        pwm = SG90_MIN + (SG90_MAX - SG90_MIN) * angle / 180
    else:
        pwm = MG995_MIN + (MG995_MAX - MG995_MIN) * angle / 180
    return int(pwm)

def send_servo_angles(joint_angles_deg):
    for i, theta in enumerate(joint_angles_deg):
        channel = servo_channels[f'theta{i+1}']
        servo_type = 'MG995' if i < 3 else 'SG90'
        pulse = angle_to_pwm(theta, servo_type)
        pca.channels[channel].duty_cycle = int(pulse * 65535 / 4096)

def rpy_to_rotation_matrix(roll, pitch, yaw):
    r, p, y = map(lambda a: a * math.pi / 180, [roll, pitch, yaw])
    Rz = Matrix([
        [cos(y), -sin(y), 0],
        [sin(y),  cos(y), 0],
        [0,       0,      1]
    ])
    Ry = Matrix([
        [cos(p),  0, sin(p)],
        [0,       1, 0],
        [-sin(p), 0, cos(p)]
    ])
    Rx = Matrix([
        [1, 0,      0],
        [0, cos(r), -sin(r)],
        [0, sin(r),  cos(r)]
    ])
    return simplify(Rz * Ry * Rx)

def solve_inverse_kinematics(x, y, z, roll, pitch, yaw):
    try:
        R06 = rpy_to_rotation_matrix(roll, pitch, yaw)
        nx, ny, nz = R06[:, 2]
        xw = x - float(L6 * nx)
        yw = y - float(L6 * ny)
        zw = z - float(L6 * nz)

        theta1 = atan2(yw, xw)
        r = sqrt(xw**2 + yw**2)
        z_eff = zw - L1
        D = (r**2 + z_eff**2 - L3**2 - L4**2) / (2 * L3 * L4)
        theta3 = atan2(sqrt(1 - D**2), D)
        theta2 = atan2(z_eff, r) - atan2(L4 * sin(theta3), L3 + L4 * cos(theta3))

        def rot_z(theta): return Matrix([[cos(theta), -sin(theta), 0], [sin(theta), cos(theta), 0], [0, 0, 1]])
        def rot_x(alpha): return Matrix([[1, 0, 0], [0, cos(alpha), -sin(alpha)], [0, sin(alpha), cos(alpha)]])
        R01 = rot_z(theta1) * rot_x(-pi/2)
        R12 = rot_z(theta2) * rot_x(0)
        R23 = rot_z(theta3) * rot_x(0)
        R03 = simplify(R01 * R12 * R23)
        R36 = simplify(R03.T * R06)

        theta5 = atan2(sqrt(R36[0, 2]**2 + R36[1, 2]**2), R36[2, 2])
        theta4 = atan2(R36[1, 2], R36[0, 2])
        theta6 = atan2(R36[2, 1], -R36[2, 0])

        angles_deg = [
            float(theta1.evalf() * 180 / pi),
            float(theta2.evalf() * 180 / pi),
            float(theta3.evalf() * 180 / pi),
            float(theta4.evalf() * 180 / pi),
            float(theta5.evalf() * 180 / pi),
            float(theta6.evalf() * 180 / pi),
        ]
        return angles_deg
    except Exception as e:
        print("IK error:", e)
        return [90] * 6  # Fallback

# Socket server setup
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind(("0.0.0.0", 8000))
server_socket.listen(1)
print("Waiting for connection from laptop...")
conn, addr = server_socket.accept()
print(f"Connected to {addr}")

try:
    while True:
        data = conn.recv(1024).decode().strip()
        if not data:
            continue
        print("Raw data:", data)
        try:
            x_str, y_str, roll_str, pitch_str, yaw_str = data.split(",")
            x = float(x_str)
            y = float(y_str)
            z = 50  # static Z, update if needed
            roll = float(roll_str)
            pitch = float(pitch_str)
            yaw = float(yaw_str)

            print(f"Received: x={x}, y={y}, z={z}, roll={roll}, pitch={pitch}, yaw={yaw}")
            joint_angles = solve_inverse_kinematics(x, y, z, roll, pitch, yaw)
            print("Joint angles:", joint_angles)
            send_servo_angles(joint_angles)

        except ValueError:
            print("Invalid data format:", data)

except KeyboardInterrupt:
    print("Shutting down.")

finally:
    pca.deinit()
    conn.close()
    server_socket.close()
