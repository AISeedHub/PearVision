import cv2
import requests 
import numpy as np
import time
import threading
from inference import Logger


RASPBERRY_IP = '192.168.0.43'
CAMERA_ORDER = 0 # which camera to request for image (from Raspberry Pi)



# class VideoStream:
#     def __init__(self, url):
#         self.url = url
#         self._run_flag = False
#         self.thread = None
#         self.frame = None
#         self.lock = threading.Lock()
#         self.last_frame_time = time.time()

#     def start(self):
#         if not self._run_flag:
#             self._run_flag = True
#             self.thread = threading.Thread(target=self._run, args=())
#             self.thread.start()

#     def _run(self):
#         try:
            # with requests.get(self.url, stream=True, timeout=10) as r:
            #     if r.status_code != 200:
            #         return

            #     bytes_buffer = bytes()
            #     for chunk in r.iter_content(chunk_size=1024):
            #         if not self._run_flag:
            #             break
            #         bytes_buffer += chunk
            #         a = bytes_buffer.find(b'\xff\xd8')
            #         b = bytes_buffer.find(b'\xff\xd9')
            #         if a != -1 and b != -1:
            #             jpg = bytes_buffer[a:b + 2]
            #             bytes_buffer = bytes_buffer[b + 2:]
            #             frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            #             if frame is not None:
            #                 with self.lock:
            #                     self.frame = frame
            #                     self.last_frame_time = time.time()
            #                 # logging.debug("Frame received and processed")
            #             else:
            #                 logging.warning("Received empty frame")
#         except requests.RequestException as e:
#             logging.error(f"Network error: {str(e)}")
#         except Exception as e:
#             logging.error(f"Error in video stream: {str(e)}")

#     def read(self):
#         print(self.frame)
#         with self.lock:
#             if self.frame is None:
#                 logging.warning("No frame available")
#                 return False, None
#             if time.time() - self.last_frame_time > 5:  # 5 seconds timeout
#                 logging.warning("Frame is stale (>5 seconds old)")
#                 return False, None
#             return True, self.frame.copy()

#     def stop(self):
#         self._run_flag = False
#         if self.thread:
#             self.thread.join()
#         logging.info("Video stream stopped")

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
                # while self._run_flag:  # Check flag in loop
                #     try:
                #         chunk = next(r.iter_content(chunk_size=1024))
                #         bytes_buffer += chunk
                #         a = bytes_buffer.find(b'\xff\xd8')
                #         b = bytes_buffer.find(b'\xff\xd9')
                #         if a != -1 and b != -1:
                #             jpg = bytes_buffer[a:b + 2]
                #             bytes_buffer = bytes_buffer[b + 2:]
                #             frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                #             if frame is not None:
                #                 with self.lock:
                #                     self.frame = frame
                #                     self.last_frame_time = time.time()
                #             else:
                #                 self.logger.log("Received empty frame", "WARNING")
                #     except StopIteration:
                #         if self._run_flag:  # Only log if not stopping intentionally
                #             self.logger.log("Stream ended unexpectedly", "ERROR")
                #         break
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

url = f"http://{RASPBERRY_IP}:5000/api/video_feed/{CAMERA_ORDER}"  # Replace with your server's URL
video_stream = VideoStream(url)
video_stream.start()



while True:
    ret, frame = video_stream.read()
    print("frame", frame)
    if not ret:
        continue

    cv2.imshow('Pear Detection', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break