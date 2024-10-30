import cv2
import torch
import yaml
from ultralytics import YOLO
import queue
import threading
import time
import serial
from datetime import datetime
import sys
from pathlib import Path
from typing import Optional, Tuple, List
import numpy as np


class Logger:
    def __init__(self, name: str):
        self.name = name
        self.start_time = time.time()

    def log(self, message: str, level: str = "INFO"):
        timestamp = time.time() - self.start_time
        print(f"[{timestamp:.2f}s] {level} - {self.name}: {message}")
        sys.stdout.flush()


class PearDetectionModel:
    def __init__(self, config) -> None:
        self.logger = Logger("Model")
        self.logger.log("Initializing model...")

        self.device = (
            torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
        )
        self.logger.log(f"Using device: {self.device}")

        try:
            self.model = YOLO(config["model_path"], task="detect")
            self.names = config["classes"]
            self.logger.log("Model loaded successfully")
            self.logger.log(f"Classes: {self.names}")
        except Exception as e:
            self.logger.log(f"Error loading model: {e}", "ERROR")
            raise

    def detect(self, img: np.ndarray) -> np.ndarray:
        """Run detection on image"""
        try:
            results = self.model.predict(img)
            return results[0].boxes.cpu().numpy()
        except Exception as e:
            self.logger.log(f"Detection error: {e}", "ERROR")
            return np.array([])

    def inference(self, img: np.ndarray) -> Tuple[int, np.ndarray]:
        """Run inference and return result and boxes"""
        pred = self.detect(img)
        pred = pred[pred.conf > 0.8]
        pred = (pred if any([label == "burn_bbox" for label in pred.cls]) else pred[pred.conf > 0.9])
        labels = [self.names[int(cat)] for cat in pred.cls]
        if any([label != "normal_pear_box" for label in labels]):
            return 1, pred.xyxy
        else:
            return 0, pred.xyxy


class ArduinoController:
    def __init__(self, port: str = '/dev/ttyACM0', baudrate: int = 9600):
        self.logger = Logger("Arduino")
        self.port = port
        self.baudrate = baudrate
        self.arduino = None
        self.last_command_time = time.time()
        self.running = True
        self.command_count = {'ON': 0, 'OFF': 0}
        self.last_status_time = time.time()
        self.status_interval = 60  # Print status every 60 seconds

    def connect(self) -> bool:
        """Establish connection with Arduino"""
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                self.arduino = serial.Serial(self.port, self.baudrate)
                self.logger.log(f"Connected to Arduino on {self.port}")
                return True
            except Exception as e:
                retry_count += 1
                self.logger.log(f"Connection attempt {retry_count} failed: {e}", "WARNING")
                if retry_count < max_retries:
                    time.sleep(2)  # Wait before retry

        self.logger.log("Failed to connect to Arduino after all retries", "ERROR")
        return False

    def send_command(self, command: str) -> bool:
        """Send command to Arduino with error handling"""
        try:
            self.arduino.write(command.encode())
            self.command_count[command.strip()] += 1
            return True
        except Exception as e:
            self.logger.log(f"Error sending command: {e}", "ERROR")
            return False

    def print_status(self):
        """Print periodic status updates"""
        current_time = time.time()
        if current_time - self.last_status_time >= self.status_interval:
            self.logger.log(f"Status - ON commands: {self.command_count['ON']}, "
                            f"OFF commands: {self.command_count['OFF']}")
            self.last_status_time = current_time

    def process_commands(self, command_queue: queue.Queue):
        """Main command processing loop"""
        if not self.connect():
            return

        try:
            while self.running:
                try:
                    # Collect commands for 5 seconds
                    commands = []

                    try:
                        while time.time() - self.last_command_time < 5:
                            cmd = command_queue.get_nowait()
                            if cmd is None:  # Exit signal
                                self.running = False
                                break
                            commands.append(cmd)
                    except queue.Empty:
                        time.sleep(0.1)  # Short sleep to prevent busy waiting
                        pass

                    if not self.running:
                        break

                    current_time = time.time()
                    if commands and (current_time - self.last_command_time >= 5):
                        # Count ON vs OFF commands
                        on_count = commands.count('ON\n')
                        off_count = commands.count('OFF\n')

                        if on_count > off_count:
                            if self.send_command('ON\n'):
                                time.sleep(1)
                                self.send_command('OFF\n')
                        self.last_command_time = current_time

                    self.print_status()

                except Exception as e:
                    self.logger.log(f"Command processing error: {e}", "ERROR")
                    time.sleep(1)

        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        try:
            if self.arduino:
                self.send_command('OFF\n')
                self.arduino.close()
                self.logger.log("Arduino connection closed")
                self.logger.log(f"Final stats - ON: {self.command_count['ON']}, "
                                f"OFF: {self.command_count['OFF']}")
        except Exception as e:
            self.logger.log(f"Error during cleanup: {e}", "ERROR")


class VideoCapture:
    def __init__(self, camera_id: int = 0):
        self.logger = Logger("Camera")
        self.cap = cv2.VideoCapture(camera_id)
        self.frame_count = 0
        self.start_time = time.time()

        if not self.cap.isOpened():
            self.logger.log("Failed to open camera", "ERROR")
            raise RuntimeError("Could not open camera")

        self.logger.log("Camera initialized successfully")

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read frame from camera with FPS logging"""
        ret, frame = self.cap.read()

        if ret:
            self.frame_count += 1
            if self.frame_count % 30 == 0:  # Log FPS every 30 frames
                elapsed = time.time() - self.start_time
                fps = self.frame_count / elapsed
                self.logger.log(f"FPS: {fps:.2f}")

        return ret, frame

    def release(self):
        """Release camera resources"""
        self.cap.release()
        self.logger.log("Camera released")


def main(config_path: str):
    logger = Logger("Main")
    logger.log("Starting Pear Detection System")

    try:
        # Load configuration
        with open(config_path) as f:
            config = yaml.safe_load(f)
            logger.log("Configuration loaded successfully")

        # Initialize components
        model = PearDetectionModel(config)
        camera = VideoCapture(0)
        command_queue = queue.Queue()

        # Start Arduino thread
        arduino_controller = ArduinoController()
        arduino_thread = threading.Thread(
            target=arduino_controller.process_commands,
            args=(command_queue,)
        )
        arduino_thread.start()
        logger.log("Arduino thread started")

        # Main processing loop
        while True:
            ret, frame = camera.read()
            if not ret:
                logger.log("Failed to read frame", "ERROR")
                break

            # Run inference
            result, boxes = model.inference(frame)

            # Send command
            command_queue.put('ON\n' if result == 1 else 'OFF\n')

            # Draw results
            for box in boxes:
                x1, y1, x2, y2 = map(int, box[:4])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            cv2.putText(frame,
                        f"Result: {'Normal' if result == 0 else 'Abnormal'}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            cv2.imshow('Pear Detection', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                logger.log("Quit signal received")
                break

    except KeyboardInterrupt:
        logger.log("Program interrupted by user")
    except Exception as e:
        logger.log(f"Unexpected error: {e}", "ERROR")
    finally:
        # Cleanup
        logger.log("Cleaning up...")
        camera.release()
        cv2.destroyAllWindows()
        command_queue.put(None)
        arduino_thread.join()
        logger.log("Cleanup complete")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="yolo_config.yml")
    args = parser.parse_args()

    main(args.config)
