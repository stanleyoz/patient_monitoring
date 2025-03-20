# /app/api/routes.py
from fastapi import APIRouter, HTTPException, WebSocket
from typing import List
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from app.core.models import SessionConfig
from app.services.imu_service import IMUManager
from app.services.camera_service import CameraService
from bleak import BleakScanner

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the router
router = APIRouter()

# Create service instances
imu_manager = IMUManager()
camera_service = CameraService()

@router.get("/imu-config")
async def get_imu_config():
    try:
        with open('IMU_designate.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="IMU configuration file not found")

@router.get("/scan-imus")
async def scan_imus():
    """Scan for available IMUs and return their status"""
    try:
        # Load IMU configurations
        with open('IMU_designate.json', 'r') as f:
            imu_configs = json.load(f)['imu_configs']
        
        # Get all configured addresses
        configured_addresses = {config['address']: imu_id 
                              for imu_id, config in imu_configs.items()}
        
        # Scan for devices
        devices = await BleakScanner.discover(timeout=5.0)
        found_addresses = {d.address: {
            "name": d.name,
            "rssi": d.rssi
        } for d in devices if d.name and "Xsens DOT" in d.name}
        
        # Prepare status response
        imu_status = {}
        for imu_id, config in imu_configs.items():
            address = config['address']
            imu_status[imu_id] = {
                "address": address,
                "location": config['location'],
                "description": config['description'],
                "active": address in found_addresses,
                "rssi": found_addresses.get(address, {}).get("rssi", None)
            }
            
        return imu_status
        
    except Exception as e:
        logger.error(f"Error scanning IMUs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/sessions")
async def create_session(config: SessionConfig):
    try:
        # Create session directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_path = Path(f"data/sessions/{config.session_name}_{timestamp}")
        session_path.mkdir(parents=True, exist_ok=True)
        
        # Save configuration
        with open(session_path / "config.json", "w") as f:
            json.dump(config.dict(), f, indent=4, default=str)
            
        return {"status": "success", "session_path": str(session_path)}
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# In routes.py, add more detailed logging
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection established")
    
    try:
        while True:
            data = await websocket.receive_json()
            logger.info(f"Received WebSocket message: {data}")  # This shows no camera_streams in the data
            
            if data["action"] == "start_recording":
                try:
                    session_path = data.get("session_path", "data/sessions/test")
                    selected_imus = data.get("selected_imus", [])
                    camera_streams = data.get("camera_streams", {})  # This is empty
                    
                    logger.info(f"Camera streams config: {camera_streams}")  # Add this log
                    
                    # Initialize camera if streams are enabled
                    if camera_streams["rgb"] or camera_streams["depth"]:
                        camera_success = await camera_service.initialize(
                            session_path=session_path,
                            enable_rgb=camera_streams["rgb"],
                            enable_depth=camera_streams["depth"]
                        )
                        if camera_success:
                            # Set up camera status callback
                            camera_service.set_status_callback(
                                lambda status: websocket.send_json(status)
                            )
                            # Start camera recording
                            asyncio.create_task(camera_service.start_recording())
                    
                    # Load IMU configurations and start IMU recording
                    with open('IMU_designate.json', 'r') as f:
                        imu_configs = json.load(f)['imu_configs']
                    
                    imu_success = await imu_manager.start_recording(
                        selected_imus,
                        imu_configs,
                        session_path
                    )
                    
                    await websocket.send_json({
                        "type": "recording_status",
                        "success": imu_success,
                        "message": "Recording started" if imu_success else "Failed to start recording"
                    })
                    
                except Exception as e:
                    logger.error(f"Error starting recording: {e}")
                    await websocket.send_json({
                        "type": "recording_status",
                        "success": False,
                        "message": f"Error: {str(e)}"
                    })
                    
            elif data["action"] == "stop_recording":
                logger.info("Stopping recording")
                # Stop IMU recording
                await imu_manager.stop_recording()
                # Stop camera recording if it was started
                if camera_service.is_recording:
                    await camera_service.stop_recording()
                
                await websocket.send_json({
                    "type": "recording_status",
                    "success": True,
                    "message": "Recording stopped"
                })
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        logger.info("WebSocket connection closed")
