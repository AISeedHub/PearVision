import cv2
import torch
import yaml
from ultralytics import YOLO


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


if __name__ == "__main__":
    import argparse

    args = argparse.ArgumentParser()
    args.add_argument("--config", type=str, default="yolo_config.yml")
    args.add_argument("--img_path", type=str, default="Real_pear")
    args = args.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)
        print(config)

        model = PearDetectionModel(config)
        while(True):
            img = cv2.imread(f"{args.img_path}")
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            print(model.inference(img))
