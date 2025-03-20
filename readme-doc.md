# Patient Recording System

A web-based system for synchronized recording of IMU sensors and RealSense D455 camera data.

## System Requirements
- Ubuntu 20.04 LTS
- NVIDIA Jetson (tested on Jetson AGX Xavier)
- Python 3.8
- Intel RealSense D455 Camera
- Xsens DOT IMU sensors

## Installation Guide

### 1. System Dependencies
```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y \
    cmake \
    build-essential \
    libssl-dev \
    libusb-1.0-0-dev \
    pkg-config \
    libgtk-3-dev \
    libglfw3-dev \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    python3-tk
```

### 2. Install Miniconda
```bash
# Download and install Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh
chmod +x Miniconda3-latest-Linux-aarch64.sh
./Miniconda3-latest-Linux-aarch64.sh
source ~/.bashrc
```

### 3. Create Conda Environment
```bash
# Create and activate environment
conda create -n patient_monitor python=3.8
conda activate patient_monitor

# Install basic packages
conda install -c conda-forge numpy pandas
```

### 4. Install RealSense SDK
```bash
# Clone and build librealsense
cd ~
git clone https://github.com/IntelRealSense/librealsense.git
cd librealsense
mkdir build && cd build

# Configure with required flags
cmake ../ -DFORCE_RSUSB_BACKEND=true \
    -DCMAKE_BUILD_TYPE=release \
    -DBUILD_PYTHON_BINDINGS=true \
    -DPYTHON_EXECUTABLE=$(which python)

# Build and install
make -j4
sudo make install
sudo ldconfig

# Install pyrealsense2
python -m pip install --no-cache-dir pyrealsense2 --user
```

### 5. Setup USB Rules for RealSense
```bash
sudo cp ~/librealsense/config/99-realsense-libusb.rules /etc/udev/rules.d/
echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="8086", ATTRS{idProduct}=="0b5c", MODE:="0666", GROUP:="plugdev"' | sudo tee /etc/udev/rules.d/99-realsense-d455.rules
sudo usermod -a -G plugdev $USER
sudo usermod -a -G video $USER
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### 6. Install Project Dependencies
```bash
# Install required packages
pip install fastapi==0.110.0
pip install "uvicorn[standard]"==0.27.1
pip install websockets==12.0
pip install bleak==0.22.3
pip install python-multipart==0.0.9
pip install pydantic==2.6.1
pip install asyncio==3.4.3
pip install aiofiles==23.2.1
pip install python-jose[cryptography]==3.3.0
pip install pytest==8.0.0
pip install pytest-asyncio==0.23.5
pip install opencv-python==4.6.0.66
```

### 7. Project Setup
```bash
# Create project directory
mkdir patient_monitoring
cd patient_monitoring

# Create required directories
mkdir -p app/{api,core,services,static}
mkdir -p data/sessions
```

### 8. System Verification
Test the installation by running the verification scripts:

```bash
# Test RealSense camera
python test_camera.py

# Test IMU connectivity
python test_imu.py
```

## Project Structure
```
patient_monitoring/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── models.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── imu_service.py
│   │   └── camera_service.py
│   └── static/
│       └── index.html
├── data/
│   └── sessions/
└── IMU_designate.json
```

## Running the Application

1. Start the server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

2. Access the web interface:
```
http://localhost:8000
```

## Data Collection

### Session Data Structure
Each recording session creates a directory with:
```
session_name_timestamp/
├── config.json
├── rgb_stream.mp4
├── rgb_timestamps.txt
├── depth/
│   ├── frame_X_timestamp.npz
│   └── ...
├── depth_timestamps.txt
├── camera_config.json
├── camera_recording_summary.json
└── imu/
    ├── IMU_ID_timestamp.csv
    └── ...
```

### Data Formats
- RGB: MP4 video file with separate timestamp file
- Depth: NPZ files containing depth and IR data
- IMU: CSV files with timestamps and sensor data

## Troubleshooting

### Common Issues

1. OpenMP TLS Error:
```bash
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1
```

2. USB Permission Issues:
```bash
sudo usermod -a -G plugdev $USER
sudo usermod -a -G video $USER
sudo udevadm control --reload-rules
sudo udevadm trigger
```

3. Camera Not Detected:
- Ensure USB 3.0/3.1 connection
- Check camera LED indicator
- Verify USB rules are properly set

4. IMU Connection Issues:
- Verify IMU addresses in IMU_designate.json
- Ensure IMUs are charged
- Check Bluetooth connectivity
