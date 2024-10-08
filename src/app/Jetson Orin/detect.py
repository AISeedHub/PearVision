import cv2
import numpy as np
import requests
from urllib.parse import urljoin
import threading
import time
import logging
import yaml

from inference import PearDetectionModel
from config import *

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

    def start(self):
        if not self._run_flag:
            self._run_flag = True
            self.thread = threading.Thread(target=self._run, args=())
            self.thread.start()
            logging.info("Video stream thread started")

    def _run(self):
        try:
            logging.info(f"Connecting to stream URL: {self.url}")
            with requests.get(self.url, stream=True, timeout=10) as r:
                if r.status_code != 200:
                    logging.error(f"Failed to connect to stream. Status code: {r.status_code}")
                    return

                logging.info("Connected to stream successfully")
                bytes_buffer = bytes()
                for chunk in r.iter_content(chunk_size=1024):
                    if not self._run_flag:
                        break
                    bytes_buffer += chunk
                    a = bytes_buffer.find(b'\xff\xd8')
                    b = bytes_buffer.find(b'\xff\xd9')
                    if a != -1 and b != -1:
                        jpg = bytes_buffer[a:b+2]
                        bytes_buffer = bytes_buffer[b+2:]
                        frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                        if frame is not None:
                            with self.lock:
                                self.frame = frame
                                self.last_frame_time = time.time()
                            #logging.debug("Frame received and processed")
                        else:
                            logging.warning("Received empty frame")
        except requests.RequestException as e:
            logging.error(f"Network error: {str(e)}")
        except Exception as e:
            logging.error(f"Error in video stream: {str(e)}")

    def read(self):
        with self.lock:
            if self.frame is None:
                logging.warning("No frame available")
                return False, None
            if time.time() - self.last_frame_time > 5:  # 5 seconds timeout
                logging.warning("Frame is stale (>5 seconds old)")
                return False, None
            return True, self.frame.copy()

    def stop(self):
        self._run_flag = False
        if self.thread:
            self.thread.join()
        logging.info("Video stream stopped")

def load_model(config_file):
    with open(config_file) as f:
        config = yaml.safe_load(f)
        model = PearDetectionModel(config)
        print("Load model sucessfully!")
        print("-"*10)
        return model
    return None

def main():
    # load model
    model = load_model(YOLO_CONFIG_FILE)
    url = f"http://{RASPBERRY_IP}:5000/api/video_feed/{CAMERA_ORDER}"  # Replace with your server's URL
    video_stream = VideoStream(url)
    video_stream.start()

    try:
        while True:
            ret, frame = video_stream.read()
            if not ret:
                logging.error("Could not read frame.")
                time.sleep(1)  # Wait a bit before trying again
                continue

            # Process frame
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            #logging.debug(f"Frame processed. Size: {w}x{h}")

            cls, bboxes = model.inference(rgb_image)
            print(cls)

            # Display the frame
            for box in bboxes:
                cv2.rectangle(
                    frame,
                    (int(box[0]), int(box[1])),
                    (int(box[2]), int(box[3])),
                    (0, 255, 0),
                    2,
                )
            cv2.imshow('Camera Feed', frame)

            # Break the loop if 'q' is pressed
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received. Stopping.")
    finally:
        video_stream.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
