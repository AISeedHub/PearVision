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

    def detect(self, img: np.ndarray, conf: float) -> np.ndarray:
        """Run detection on image"""
        try:
            results = self.model.predict(img)
            # Extract bounding boxes, classes, and scores
            bboxes = results[0].boxes.xyxy.cpu().numpy()
            classes = results[0].boxes.cls.cpu().numpy()
            scores = results[0].boxes.conf.cpu().numpy()
            # Filter results based on confidence threshold
            mask = scores >= conf
            bboxes = bboxes[mask]
            classes = classes[mask]

            return np.hstack((bboxes, classes[:, None]))
        except Exception as e:
            self.logger.log(f"Detection error: {e}", "ERROR")
            return np.array([])
        
    def postprocess(self, pred: np.ndarray) -> np.ndarray:
        """Post-process the predictions"""
        # ensure that defect boxes are inside the fruit boxes
        # extract the defect boxes and fruit boxes
        defect_boxes = pred[pred[:, 4] == 1][:, :4]
        fruit_boxes = pred[pred[:, 4] == 0][:, :4]
        # check if defect boxes are inside fruit boxes
        # if the defect box is not inside any fruit box, remove it
        for defect_box in defect_boxes:
            x1, y1, x2, y2 = defect_box
            inside = False
            for fruit_box in fruit_boxes:
                fx1, fy1, fx2, fy2 = fruit_box
                if (x1 >= fx1 and y1 >= fy1 and x2 <= fx2 and y2 <= fy2):
                    inside = True
                    break
            if not inside:
                pred = pred[pred[:, :4] != defect_box].reshape(-1, 5)
        return pred

    def inference(self, img: np.ndarray) -> Tuple[int, np.ndarray, np.ndarray]:
        """Run inference and return result and boxes"""
        pred = self.detect(img, conf=0.7)
        # pred = self.postprocess(pred)
        labels = [self.names[int(cat)] for cat in pred[:, 4]]

        # if any classes rather than "normal_pear_box" is detected, return 0 else return 1
        if any([label == "defect" for label in labels]):
            return 1, pred[:, 0:4], pred[:, 4]
        else:
            return 0, pred[:, 0:4], pred[:, 4]


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
        self.time_delay = 3  # Delay time to send command to Arduino

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
                        update_queue_time = time.time()
                        while time.time() - update_queue_time < self.time_delay:
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

                    if commands and (time.time() - self.last_command_time >= self.time_delay):
                        # Count ON vs OFF commands
                        on_count = commands.count('ON\n')
                        off_count = commands.count('OFF\n')

                        if on_count > off_count:
                            if self.send_command('ON\n'):
                                time.sleep(1)
                                self.send_command('OFF\n')
                        self.last_command_time = time.time()

                    update_queue_time = time.time()

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
        # Set the resolution to 640x480
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
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
            result, boxes, cls = model.inference(frame)
            # Send command
            command_queue.put('ON\n' if result == 1 else 'OFF\n')

            # Draw results
            for box, cl in zip(boxes, cls):
                x1, y1, x2, y2 = map(int, box[:4])
                if cl == 0:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                else:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

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
