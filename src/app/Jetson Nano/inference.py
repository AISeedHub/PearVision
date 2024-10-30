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


class Logger:
    """Custom logger for system status"""

    def __init__(self):
        self.start_time = time.time()

    def _get_timestamp(self):
        elapsed = time.time() - self.start_time
        return f"[{elapsed:.2f}s]"

    def info(self, message: str, emoji: str = "ℹ️"):
        print(f"{emoji} {self._get_timestamp()} {message}")
        sys.stdout.flush()

    def success(self, message: str):
        self.info(message, "✅")

    def warning(self, message: str):
        self.info(message, "⚠️")

    def error(self, message: str):
        self.info(message, "❌")

    def status(self, message: str):
        self.info(message, "🔄")


logger = Logger()


class PearDetectionModel:
    def __init__(self, config) -> None:
        logger.status("Initializing PearDetectionModel...")

        # Log CUDA availability
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            gpu_name = torch.cuda.get_device_name(0)
            logger.success(f"CUDA available: Using {gpu_name}")
        else:
            logger.warning("CUDA not available: Using CPU")

        self.device = torch.device("cuda" if cuda_available else "cpu")

        # Load model with timing
        load_start = time.time()
        logger.status(f"Loading YOLO model from {config['model_path']}...")
        self.model = YOLO(config["model_path"], task="detect")
        load_time = time.time() - load_start
        logger.success(f"Model loaded in {load_time:.2f}s")

        self.names = config["classes"]
        logger.info(f"Classes configured: {', '.join(self.names)}")

    def detect(self, img):
        results = self.model.predict(img)
        return results[0].boxes.cpu().numpy()

    def inference(self, img):
        pred = self.detect(img)
        labels = [self.names[int(cat)] for cat in pred.cls]
        if any([label != "normal_pear_box" for label in labels]):
            return 0, pred.xyxy
        else:
            return 1, pred.xyxy


def arduino_worker(arduino, command_queue):
    logger.status("Starting Arduino worker thread...")
    last_command_time = time.time()
    command_count = 0

    try:
        while True:
            try:
                command = command_queue.get(timeout=5)  # Wait for a command for up to 5 seconds
                if command is None:
                    logger.status("Received shutdown signal")
                    break

                current_time = time.time()
                if current_time - last_command_time >= 5:  # Check if 5 seconds have passed
                    on_count = 0
                    off_count = 0

                    # Collect all commands in the queue
                    while not command_queue.empty():
                        command = command_queue.get()
                        if command == 'ON\n':
                            on_count += 1
                        elif command == 'OFF\n':
                            off_count += 1

                    if on_count > off_count:
                        logger.info(f"Sending ON command to Arduino (ON:{on_count}, OFF:{off_count})", "🤖")
                        arduino.write(command.encode())
                        time.sleep(1)  # Wait for 1 second
                        logger.info("Sending OFF command to Arduino (Auto-OFF)", "🤖")
                        arduino.write(b'OFF\n')
                        last_command_time = current_time
                        command_count += 2  # Count both ON and OFF commands

            except queue.Empty:
                # Reset the queue if no command is received within 5 seconds
                logger.status("Command queue timeout - clearing queue")
                with command_queue.mutex:
                    command_queue.queue.clear()

    except KeyboardInterrupt:
        logger.status("Arduino worker interrupted")
    except serial.SerialException as e:
        logger.error(f"Serial communication error: {e}")
    finally:
        try:
            logger.status("Sending final OFF command to Arduino")
            arduino.write(b'OFF\n')
            arduino.close()
            logger.success(f"Arduino connection closed. Processed {command_count} commands")
        except:
            logger.error("Error during Arduino cleanup")


def main(config, command_queue):
    logger.status("Starting main worker...")

    # Load configuration
    try:
        with open(config) as f:
            config = yaml.safe_load(f)
            logger.success(f"Configuration loaded from {config}")
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return

    # Initialize model
    model = PearDetectionModel(config)

    # Initialize camera
    logger.status("Initializing camera...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Could not open camera")
        return
    logger.success("Camera initialized successfully")

    fps_start_time = time.time()
    frame_count = 0
    detection_count = {'normal': 0, 'abnormal': 0}

    try:
        logger.status("Starting main detection loop...")
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.error("Can't receive frame")
                break

            # Calculate and display FPS every 30 frames
            frame_count += 1
            if frame_count % 30 == 0:
                fps = frame_count / (time.time() - fps_start_time)
                logger.info(f"FPS: {fps:.1f}", "📊")

            # Run inference
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result, boxes = model.inference(img)

            # Update detection counts
            if result == 1:
                detection_count['abnormal'] += 1
                command_queue.put('ON\n')
            else:
                detection_count['normal'] += 1
                command_queue.put('OFF\n')

            # Draw boxes and results
            for box in boxes:
                x1, y1, x2, y2 = map(int, box[:4])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Add detection stats to frame
            cv2.putText(frame,
                        f"Result: {'Normal' if result == 0 else 'Abnormal'}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame,
                        f"Total: N:{detection_count['normal']} A:{detection_count['abnormal']}",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            cv2.imshow('Pear Detection', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                logger.status("Q pressed, stopping...")
                break

    except KeyboardInterrupt:
        logger.status("Main worker interrupted")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        logger.success(
            f"Detection statistics - Normal: {detection_count['normal']}, Abnormal: {detection_count['abnormal']}")


if __name__ == "__main__":
    logger.info("🚀 Starting Pear Detection System")

    import argparse

    args = argparse.ArgumentParser()
    args.add_argument("--config", type=str, default="yolo_config.yml")
    args = args.parse_args()

    logger.info(f"Configuration file: {args.config}")

    # Initialize Arduino connection
    arduino_port = '/dev/ttyACM0'
    logger.status(f"Connecting to Arduino on {arduino_port}...")
    try:
        arduino = serial.Serial(arduino_port, 9600)
        logger.success("Arduino connected successfully")
    except serial.SerialException as e:
        logger.error(f"Failed to connect to Arduino: {e}")
        sys.exit(1)

    # Create command queue
    command_queue = queue.Queue()
    logger.success("Command queue created")

    # Start Arduino thread
    logger.status("Starting Arduino worker thread...")
    arduino_thread = threading.Thread(
        target=arduino_worker,
        args=(arduino, command_queue)
    )
    arduino_thread.start()
    logger.success("Arduino worker thread started")

    try:
        main(args.config, command_queue)
    except Exception as e:
        logger.error(f"Main process error: {e}")
    finally:
        logger.status("Cleaning up...")
        command_queue.put(None)  # Signal Arduino thread to exit
        arduino_thread.join()
        logger.success("System shutdown complete")