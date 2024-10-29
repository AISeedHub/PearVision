import cv2
import torch
import yaml
from ultralytics import YOLO

import queue
import threading
import time
import serial

arduino_serial_port = '/dev/ttyACM0'  # serial port to communicate with Arduino


class PearDetectionModel:
    def __init__(self, config) -> None:
        self.device = (
            torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
        )
        self.model = YOLO(config["model_path"], task="detect")

        self.names = config["classes"]

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

    def _preporcess(self, img):
        pass


def arduino_worker(arduino, command_queue):
    last_command_time = time.time()
    try:
        while True:
            try:
                command = command_queue.get(timeout=5)  # Wait for a command for up to 5 seconds
                if command is None:
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
                        arduino.write(command.encode())
                        time.sleep(1)  # Wait for 1 second
                        arduino.write(b'OFF\n')
                        last_command_time = current_time
            except queue.Empty:
                # Reset the queue if no command is received within 5 seconds
                with command_queue.mutex:
                    command_queue.queue.clear()
    except KeyboardInterrupt:
        print("Program stopped")
    finally:
        arduino.write(b'OFF\n')
        arduino.close()


def main(config, command_queue):
    with open(config) as f:
        config = yaml.safe_load(f)
        print(config)

        model = PearDetectionModel(config)

        # Open the default camera (usually the built-in webcam)
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            print("Error: Could not open camera.")
            exit()

        while True:
            # Capture frame-by-frame
            ret, frame = cap.read()

            if not ret:
                print("Error: Can't receive frame (stream end?). Exiting ...")
                break

            # Convert the image from BGR to RGB
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Run inference
            result, boxes = model.inference(img)

            if result == 1:
                command_queue.put('ON\n')
            else:
                command_queue.put('OFF\n')

            # Draw bounding boxes on the frame
            for box in boxes:
                x1, y1, x2, y2 = map(int, box[:4])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Display the result
            cv2.putText(frame, f"Result: {'Normal' if result == 0 else 'Abnormal'}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            # Display the resulting frame
            cv2.imshow('Pear Detection', frame)

            # Break the loop on 'q' key press
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        # When everything done, release the capture
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    import argparse

    args = argparse.ArgumentParser()
    args.add_argument("--config", type=str, default="yolo_config.yml")
    args = args.parse_args()

    arduino = serial.Serial(arduino_serial_port, 9600)
    command_queue = queue.Queue()
    arduino_thread = threading.Thread(target=arduino_worker, args=(arduino, command_queue))
    arduino_thread.start()

    main(args.config, command_queue)
    command_queue.put(None)  # Signal the Arduino thread to exit
    arduino_thread.join()
