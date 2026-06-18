## Installation

### Clone the Repository

```bash
git clone https://github.com/ProfessionalSingle/waste_plastic_Classfifcation.git

cd rob_env
```

### Create a Virtual Environment

```bash
python3 -m venv rob_env

source rob_env/bin/activate
```

### Upgrade pip

```bash
pip install --upgrade pip
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Verify Installation

```bash
python -c "import cv2, numpy, ultralytics; print('Installation Successful')"
```

## Usage

### Activate the Environment

```bash
source rob_env/bin/activate
```

### Run the Vision System

```bash
python pi.py
```

### Run the Robotic Arm Control Module

```bash
python soc2.py
```

### Execute Pick-and-Place Routine

```bash
python t1.py
```

## Hardware Requirements

- Raspberry Pi 3 B+
- USB Camera / Pi Camera
- 6-DOF Robotic Arm
- PCA9685 Servo Driver
- Servo Motors
- External Power Supply

## Software Requirements

- Raspberry Pi OS
- Python 3.11+
- YOLOv8
- OpenCV
- Adafruit ServoKit
