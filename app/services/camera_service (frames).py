import pyrealsense2 as rs
import numpy as np
import cv2
import asyncio
import logging
from pathlib import Path
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class CameraService:
    def __init__(self):
        self.pipeline = None
        self.config = None
        self.is_recording = False
        self.frame_count = 0
        self.start_time = None
        self.session_path = None
        self.enabled_streams = {"rgb": False, "depth": False}
        self.record_status_callback = None

    async def initialize(self, session_path: Path, enable_rgb: bool = False, enable_depth: bool = False):
        """Initialize camera with specified streams"""
        try:
            self.session_path = Path(session_path)
            self.enabled_streams = {"rgb": enable_rgb, "depth": enable_depth}
            
            if not (enable_rgb or enable_depth):
                logger.info("No streams enabled, camera initialization skipped")
                return True

            self.pipeline = rs.pipeline()
            self.config = rs.config()

            # Configure streams
            if enable_rgb:
                self.config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
                (self.session_path / "rgb").mkdir(exist_ok=True)
            if enable_depth:
                self.config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
                (self.session_path / "depth").mkdir(exist_ok=True)

            # Start streaming
            self.pipeline.start(self.config)
            logger.info(f"Camera initialized with RGB: {enable_rgb}, Depth: {enable_depth}")
            
            # Save camera configuration
            config_data = {
                "enabled_streams": self.enabled_streams,
                "resolution": "640x480",
                "fps": 30,
                "initialization_time": datetime.now().isoformat()
            }
            with open(self.session_path / "camera_config.json", "w") as f:
                json.dump(config_data, f, indent=4)
            
            return True

        except Exception as e:
            logger.error(f"Camera initialization error: {e}")
            return False

    async def start_recording(self):
        """Start recording enabled streams"""
        if not (self.enabled_streams["rgb"] or self.enabled_streams["depth"]):
            return False

        self.is_recording = True
        self.start_time = datetime.now()
        self.frame_count = 0
        
        while self.is_recording:
            try:
                frames = self.pipeline.wait_for_frames()
                timestamp = datetime.now()
                
                if self.enabled_streams["rgb"]:
                    color_frame = frames.get_color_frame()
                    if color_frame:
                        color_image = np.asanyarray(color_frame.get_data())
                        cv2.imwrite(
                            str(self.session_path / "rgb" / f"frame_{self.frame_count}_{timestamp.timestamp():.6f}.jpg"),
                            color_image
                        )

                if self.enabled_streams["depth"]:
                    depth_frame = frames.get_depth_frame()
                    if depth_frame:
                        depth_image = np.asanyarray(depth_frame.get_data())
                        np.save(
                            str(self.session_path / "depth" / f"frame_{self.frame_count}_{timestamp.timestamp():.6f}.npy"),
                            depth_image
                        )

                self.frame_count += 1
                
                # Send status update every 30 frames
                if self.frame_count % 30 == 0 and self.record_status_callback:
                    await self.record_status_callback({
                        "type": "camera_status",
                        "frame_count": self.frame_count,
                        "streams": self.enabled_streams,
                        "recording_time": (datetime.now() - self.start_time).total_seconds()
                    })

                await asyncio.sleep(0.001)  # Small delay to prevent CPU overload

            except Exception as e:
                logger.error(f"Error recording frame: {e}")
                if self.record_status_callback:
                    await self.record_status_callback({
                        "type": "camera_status",
                        "error": str(e)
                    })
                break

    async def stop_recording(self):
        """Stop recording and cleanup"""
        self.is_recording = False
        
        if self.pipeline:
            self.pipeline.stop()
            
        # Save recording summary
        if self.start_time:
            summary = {
                "total_frames": self.frame_count,
                "start_time": self.start_time.isoformat(),
                "end_time": datetime.now().isoformat(),
                "enabled_streams": self.enabled_streams
            }
            
            with open(self.session_path / "camera_recording_summary.json", "w") as f:
                json.dump(summary, f, indent=4)

        logger.info(f"Camera recording stopped. Total frames: {self.frame_count}")

    def set_status_callback(self, callback):
        """Set callback for status updates"""
        self.record_status_callback = callback
