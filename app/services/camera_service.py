import pyrealsense2 as rs
import numpy as np
import cv2
import logging
from pathlib import Path
import json
from datetime import datetime
import asyncio

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
        self.rgb_writer = None

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
                # Initialize video writer for RGB stream
                self.rgb_writer = cv2.VideoWriter(
                    str(self.session_path / "rgb_stream.mp4"),
                    cv2.VideoWriter_fourcc(*'mp4v'),
                    30,  # FPS
                    (640, 480)  # Resolution
                )
                logger.info("RGB stream enabled")

            if enable_depth:
                # Enable both infrared streams and depth
                self.config.enable_stream(rs.stream.infrared, 1, 640, 480, rs.format.y8, 30)  # Left IR
                self.config.enable_stream(rs.stream.infrared, 2, 640, 480, rs.format.y8, 30)  # Right IR
                self.config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
                # Create depth directory
                (self.session_path / "depth").mkdir(exist_ok=True)
                logger.info("Depth stream enabled")

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

        # Create timestamp files
        if self.enabled_streams["rgb"]:
            with open(self.session_path / "rgb_timestamps.txt", "w") as f:
                f.write("frame_number,timestamp\n")
        if self.enabled_streams["depth"]:
            with open(self.session_path / "depth_timestamps.txt", "w") as f:
                f.write("frame_number,timestamp\n")
        
        while self.is_recording:
            try:
                frames = self.pipeline.wait_for_frames()
                timestamp = datetime.now()
                
                if self.enabled_streams["rgb"]:
                    color_frame = frames.get_color_frame()
                    if color_frame:
                        color_image = np.asanyarray(color_frame.get_data())
                        self.rgb_writer.write(color_image)
                        
                        # Save timestamp
                        with open(self.session_path / "rgb_timestamps.txt", "a") as f:
                            f.write(f"{self.frame_count},{timestamp.timestamp():.6f}\n")

                if self.enabled_streams["depth"]:
                    # Get both IR frames and depth frame
                    ir1_frame = frames.get_infrared_frame(1)  # Left IR
                    ir2_frame = frames.get_infrared_frame(2)  # Right IR
                    depth_frame = frames.get_depth_frame()

                    if depth_frame and ir1_frame and ir2_frame:
                        # Save depth data
                        depth_data = {
                            "depth": np.asanyarray(depth_frame.get_data()),
                            "ir_left": np.asanyarray(ir1_frame.get_data()),
                            "ir_right": np.asanyarray(ir2_frame.get_data())
                        }
                        np.savez_compressed(
                            str(self.session_path / "depth" / f"frame_{self.frame_count}_{timestamp.timestamp():.6f}.npz"),
                            **depth_data
                        )
                        
                        # Save timestamp
                        with open(self.session_path / "depth_timestamps.txt", "a") as f:
                            f.write(f"{self.frame_count},{timestamp.timestamp():.6f}\n")

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
        
        # Release video writer if it exists
        if self.rgb_writer:
            self.rgb_writer.release()
        
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
