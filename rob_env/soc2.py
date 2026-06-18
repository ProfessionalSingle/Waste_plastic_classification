import socket
import time
from adafruit_pca9685 import PCA9685
from board import SCL, SDA
import busio

# === Servo control ===
i2c = busio.I2C(SCL, SDA)
pca = PCA9685(i2c)
pca.frequency = 50

# Define the servo channels for each joint (Base to Gripper)
servo_channels = [0, 2, 4, 6, 8, 10]  # Adjust channels as necessary

def angle_to_pwm(angle):
    """
    Convert the angle to PWM for the PCA9685.
    The angle should be between 0 and 180 degrees.
    """
    return int(4096 * ((0.5 + (angle / 180.0) * 2.0) / 20.0))

def move_servos(angles):
    """
    Move the servos based on the received angles.
    The angles should be a list of 6 values for each servo in the arm.
    """
    for ch, angle in zip(servo_channels, angles):
        pwm = angle_to_pwm(angle)
        pca.channels[ch].duty_cycle = pwm
        time.sleep(0.2)

# === Socket server ===
HOST = ""
PORT = 8000
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen(1)

print("?? Waiting for commands...")

try:
    while True:
        conn, addr = server_socket.accept()
        print(f"?? Connected: {addr}")
        data = conn.recv(1024).decode().strip()
        print("?? Received:", data)

        if data.startswith("ANGLES:"):
            angles_str = data[len("ANGLES:"):].strip()  # Extract angles part
            angles = list(map(int, angles_str.split(",")))  # Convert to a list of integers
            print(f"?? Angles received: {angles}")
            
            if len(angles) == 6:  # Ensure there are exactly 6 angles
                move_servos(angles)
            else:
                print("? Error: Received incorrect number of angles. Expected 6.")
        
        conn.close()

except KeyboardInterrupt:
    print("?? Shutting down")

finally:
    server_socket.close()
    # Ensure all servos stop after the server shuts down
    for ch in range(6):
        pca.channels[ch].duty_cycle = 0
    print("?? All servos stopped.")
