# app/services/websocket_service.py
from fastapi import WebSocket
import json
import logging
from typing import Dict, Set
from .imu_service import IMUManager

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.imu_manager = IMUManager()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        
        # Register status callback for this connection
        self.imu_manager.register_status_callback(
            lambda status: self.send_status(websocket, status)
        )

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        # TODO: Cleanup if this was the last connection

    async def send_status(self, websocket: WebSocket, status: dict):
        """Send status update to specific client"""
        try:
            await websocket.send_json(status)
        except Exception as e:
            logger.error(f"Error sending status: {e}")
            await self.disconnect(websocket)

    async def broadcast(self, message: dict):
        """Broadcast message to all connections"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting: {e}")
                await self.disconnect(connection)

manager = ConnectionManager()

# Add to app/api/routes.py:

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            
            if data["action"] == "start_recording":
                success = await manager.imu_manager.start_recording(
                    data["selected_imus"],
                    data["imu_configs"],
                    data["session_path"]
                )
                await websocket.send_json({
                    "type": "recording_status",
                    "success": success,
                    "message": "Recording started" if success else "Failed to start recording"
                })
                
            elif data["action"] == "stop_recording":
                await manager.imu_manager.stop_recording()
                await websocket.send_json({
                    "type": "recording_status",
                    "success": True,
                    "message": "Recording stopped"
                })
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)
