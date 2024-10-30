import cv2
import torch
import yaml
from ultralytics import YOLO
import numpy as np
from typing import Tuple
import time
import sys


class Logger:
    def __init__(self, name: str):
        self.name = name
        self.start_time = time.time()

    def log(self, message: str, level: str = "INFO") -> None:
        timestamp = time.time() - self.start_time
        print(f"[{timestamp:.2f}s] {level} - {self.name}: {message}")
        sys.stdout.flush()


class PearDetectionModel:
    def __init__(self, config) -> None:
        self.logger = Logger("Model")
        self.logger.log("Initializing model...")

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
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
        try:
            results = self.model.predict(img)
            return results[0].boxes.cpu().numpy()
        except Exception as e:
            self.logger.log(f"Detection error: {e}", "ERROR")
            return np.array([])

    def inference(self, img: np.ndarray) -> Tuple[int, np.ndarray]:
        pred = self.detect(img)
        pred = pred[pred.conf > 0.8]
        pred = (pred if any([label == "burn_bbox" for label in pred.cls]) else pred[pred.conf > 0.9])
        labels = [self.names[int(cat)] for cat in pred.cls]
        if any([label != "normal_pear_box" for label in labels]):
            return 1, pred.xyxy
        else:
            return 0, pred.xyxy


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="yolo_config.yml")
    parser.add_argument("--img_path", type=str, default="Real_pear")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    model = PearDetectionModel(config)
    while True:
        img = cv2.imread(args.img_path)
        if img is None:
            print(f"Error: Could not read image from {args.img_path}")
            break
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        print(model.inference(img))
