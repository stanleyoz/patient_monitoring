# app/services/imu_service.py
import asyncio
import logging
import struct
from datetime import datetime
from pathlib import Path
from bleak import BleakClient, BleakScanner
import csv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# IMU UUIDs
MEASUREMENT_UUID = "15172004-4947-11e9-8646-d663bd873d93"
CONTROL_UUID = "15172001-4947-11e9-8646-d663bd873d93"

class IMUDevice:
    def __init__(self, imu_id: str, address: str, output_dir: Path, status_callback=None):
        self.imu_id = imu_id
        self.address = address
        self.output_dir = Path(output_dir)
        self.client = None
        self.csv_writer = None
        self.current_file = None
        self.sample_count = 0
        self.is_recording = False
        self.status_callback = status_callback

    async def connect(self):
        try:
            logger.info(f"Scanning for IMU {self.imu_id} at {self.address}...")
            
            # Send initial scanning status
            if self.status_callback:
                await self.status_callback({
                    "imu_id": self.imu_id,
                    "status": "scanning",
                    "message": "Scanning for device..."
                })
            
            device = await BleakScanner.find_device_by_address(
                self.address, timeout=20.0
            )
            
            if not device:
                if self.status_callback:
                    await self.status_callback({
                        "imu_id": self.imu_id,
                        "status": "error",
                        "message": "Device not found"
                    })
                raise Exception(f"Could not find IMU {self.imu_id}")

            self.client = BleakClient(device)
            await self.client.connect()
            logger.info(f"Connected to {self.imu_id}")

            if self.status_callback:
                await self.status_callback({
                    "imu_id": self.imu_id,
                    "status": "connected",
                    "message": "Connected"
                })

            # Create output file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = self.output_dir / f"{self.imu_id}_{timestamp}.csv"
            self.current_file = open(filename, 'w', newline='')
            self.csv_writer = csv.writer(self.current_file)
            self.csv_writer.writerow([
                'timestamp', 
                'quaternion_w', 'quaternion_x', 'quaternion_y', 'quaternion_z',
                'accel_x', 'accel_y', 'accel_z'
            ])

            # Enable notifications
            await self.client.start_notify(
                MEASUREMENT_UUID,
                self._notification_handler
            )

            # Enable measurements
            control_data = bytearray([0x01, 0x01, 0x06])
            await self.client.write_gatt_char(CONTROL_UUID, control_data)
            
            self.is_recording = True
            
            if self.status_callback:
                await self.status_callback({
                    "imu_id": self.imu_id,
                    "status": "recording",
                    "samples": 0,
                    "message": "Started recording"
                })
                
            return True

        except Exception as e:
            logger.error(f"Error connecting to {self.imu_id}: {e}")
            if self.status_callback:
                await self.status_callback({
                    "imu_id": self.imu_id,
                    "status": "error",
                    "message": f"Connection error: {str(e)}"
                })
            return False

    def _notification_handler(self, sender, data):
        try:
            w, x, y, z = struct.unpack('<ffff', data[4:20])
            self.csv_writer.writerow([
                datetime.now().isoformat(),
                w, x, y, z,
                0, 0, 0  # placeholder for acceleration
            ])
            self.sample_count += 1
            
            # Send status update every 100 samples
            if self.sample_count % 100 == 0:
                logger.info(f"{self.imu_id}: Collected {self.sample_count} samples")
                self.current_file.flush()
                
                # Send status through callback if available
                if self.status_callback:
                    asyncio.create_task(self.status_callback({
                        "imu_id": self.imu_id,
                        "status": "recording",
                        "samples": self.sample_count,
                        "message": f"Recording: {self.sample_count} samples"
                    }))

        except Exception as e:
            logger.error(f"Error handling data for {self.imu_id}: {e}")
            if self.status_callback:
                asyncio.create_task(self.status_callback({
                    "imu_id": self.imu_id,
                    "status": "error",
                    "message": f"Data error: {str(e)}"
                }))

    async def disconnect(self):
        try:
            if self.client and self.client.is_connected:
                await self.client.disconnect()
            if self.current_file:
                self.current_file.close()
            self.is_recording = False
            
            if self.status_callback:
                await self.status_callback({
                    "imu_id": self.imu_id,
                    "status": "disconnected",
                    "samples": self.sample_count,
                    "message": f"Disconnected. Total samples: {self.sample_count}"
                })
                
            logger.info(f"Disconnected {self.imu_id}")
        except Exception as e:
            logger.error(f"Error disconnecting {self.imu_id}: {e}")
            if self.status_callback:
                await self.status_callback({
                    "imu_id": self.imu_id,
                    "status": "error",
                    "message": f"Disconnect error: {str(e)}"
                })

class IMUManager:
    def __init__(self, status_callback=None):
        self.devices = {}
        self.is_recording = False
        self.status_callback = status_callback

    async def start_recording(self, selected_imus, imu_configs, session_path):
        """Start recording data from selected IMUs"""
        logger.info("Starting IMU connections...")
        self.devices.clear()
        
        # Create session directory
        session_dir = Path(session_path)
        session_dir.mkdir(parents=True, exist_ok=True)

        for imu_id in selected_imus:
            if imu_id not in imu_configs:
                continue

            device = IMUDevice(
                imu_id=imu_id,
                address=imu_configs[imu_id]['address'],
                output_dir=session_dir,
                status_callback=self.status_callback
            )

            success = await device.connect()
            if success:
                self.devices[imu_id] = device
                await asyncio.sleep(2)  # Delay between device setups

        self.is_recording = len(self.devices) > 0
        return self.is_recording

    async def stop_recording(self):
        """Stop recording and disconnect all devices"""
        logger.info("Stopping all recordings...")
        for device in self.devices.values():
            await device.disconnect()
        self.devices.clear()
        self.is_recording = False
