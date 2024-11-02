import cv2
import numpy as np
import requests
from urllib.parse import urljoin
import threading
import time
import logging
import yaml
import queue

from inference import PearDetectionModel, Logger
from config import *

import serial

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


class VideoStream:
    def __init__(self, url):
        self.url = url
        self._run_flag = False
        self.thread = None
        self.frame = None
        self.lock = threading.Lock()
        self.last_frame_time = time.time()
        self.logger = Logger("VideoStream")

    def start(self):
        if not self._run_flag:
            self._run_flag = True
            self.thread = threading.Thread(target=self._run, args=())
            self.thread.daemon = True  # Make thread daemon
            self.thread.start()
            self.logger.log("Video stream thread started")

    def _run(self):
        try:
            self.logger.log(f"Connecting to stream URL: {self.url}")
            with requests.get(self.url, stream=True, timeout=10) as r:
                if r.status_code != 200:
                    self.logger.log(f"Failed to connect to stream. Status code: {r.status_code}", "ERROR")
                    return

                self.logger.log("Connected to stream successfully")
                bytes_buffer = bytes()

                for chunk in r.iter_content(chunk_size=1024):
                    if not self._run_flag:
                        break
                    bytes_buffer += chunk
                    a = bytes_buffer.find(b'\xff\xd8')
                    b = bytes_buffer.find(b'\xff\xd9')
                    if a != -1 and b != -1:
                        jpg = bytes_buffer[a:b + 2]
                        bytes_buffer = bytes_buffer[b + 2:]
                        frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                        if frame is not None:
                            with self.lock:
                                self.frame = frame
                                self.last_frame_time = time.time()
                            # logging.debug("Frame received and processed")
                        else:
                            self.logger.log("Received empty frame", "WARNING")
        except requests.RequestException as e:
            self.logger.log(f"Network error: {str(e)}", "ERROR")
        except Exception as e:
            self.logger.log(f"Error in video stream: {str(e)}", "ERROR")
        finally:
            self._run_flag = False

    def read(self):
        with self.lock:
            if self.frame is None:
                return False, None
            if time.time() - self.last_frame_time > 5:
                return False, None
            return True, self.frame.copy()

    def stop(self):
        self._run_flag = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)  # Add timeout
            if self.thread.is_alive():
                self.logger.log("Thread didn't stop gracefully", "WARNING")
        self.logger.log("Video stream stopped")


def load_model(config_file):
    with open(config_file) as f:
        config = yaml.safe_load(f)
        model = PearDetectionModel(config)
        print("Load model sucessfully!")
        print("-" * 10)
        return model
    return None


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
        self.status_interval = 60
        self.time_delay = 3  # delay time to send command to Arduino

    def connect(self) -> bool:
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
                    time.sleep(2)
        self.logger.log("Failed to connect to Arduino after all retries", "ERROR")
        return False

    def send_command(self, command: str) -> bool:
        try:
            self.arduino.write(command.encode())
            self.command_count[command.strip()] += 1
            return True
        except Exception as e:
            self.logger.log(f"Error sending command: {e}", "ERROR")
            return False

    def print_status(self):
        current_time = time.time()
        if current_time - self.last_status_time >= self.status_interval:
            self.logger.log(f"Status - ON commands: {self.command_count['ON']}, "
                            f"OFF commands: {self.command_count['OFF']}")
            self.last_status_time = current_time

    def process_commands(self, command_queue: queue.Queue):
        if not self.connect():
            return

        try:
            while self.running:
                try:
                    commands = []
                    update_queue_time = time.time()
                    while time.time() - update_queue_time < self.time_delay:
                        try:
                            cmd = command_queue.get_nowait()
                            if cmd is None:
                                self.running = False
                                break
                            commands.append(cmd)
                        except queue.Empty:
                            time.sleep(0.1)
                            continue

                    if not self.running:
                        break

                    if commands and (time.time() - self.last_command_time >= self.time_delay):
                        on_count = commands.count('ON\n')
                        off_count = commands.count('OFF\n')
                        if on_count > off_count:
                            if self.send_command('ON\n'):
                                time.sleep(1)
                                self.send_command('OFF\n')
                        self.last_command_time = time.time()

                except Exception as e:
                    self.logger.log(f"Command processing error: {e}", "ERROR")
                    time.sleep(1)
        finally:
            self.cleanup()

    def cleanup(self):
        try:
            if self.arduino:
                self.send_command('OFF\n')
                self.arduino.close()
                self.logger.log("Arduino connection closed")
                self.logger.log(f"Final stats - ON: {self.command_count['ON']}, "
                                f"OFF: {self.command_count['OFF']}")
        except Exception as e:
            self.logger.log(f"Error during cleanup: {e}", "ERROR")


def main():
    logger = Logger("Main")
    logger.log("Starting Pear Detection System")

    try:
        # load model and initialize components
        model = load_model(YOLO_CONFIG_FILE)
        url = f"http://{RASPBERRY_IP}:5000/api/video_feed/{CAMERA_ORDER}"  # Replace with your server's URL
        video_stream = VideoStream(url)
        video_stream.start()
        command_queue = queue.Queue()

        # Start Arduino thread
        arduino_controller = ArduinoController()
        arduino_thread = threading.Thread(
            target=arduino_controller.process_commands,
            args=(command_queue,)
        )
        arduino_thread.start()
        logger.log("Arduino thread started")
        while True:
            ret, frame = video_stream.read()
            if not ret:
                logging.error("Could not read frame.")
                time.sleep(1)  # Wait a bit before trying again
                continue

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
        logging.info("Keyboard interrupt received. Stopping.")
    except Exception as e:
        logger.log(f"Unexpected error: {e}", "ERROR")
    finally:
        # Cleanup
        logger.log("Cleaning up...")
        video_stream.stop()
        cv2.destroyAllWindows()
        command_queue.put(None)
        arduino_thread.join()
        logger.log("Cleanup complete")


if __name__ == "__main__":
    main()
