import os 
from ultralytics import YOLO
from PIL import Image
import supervision as sv
import logging

class ObjectDetector(): 
    #default_imgsz=1280

    def __init__(self, model_file_path_name):
        self.model = YOLO(model_file_path_name)

    def detect_objects_from_images(self, imge_files): 
        images=[Image.open(f) for f in imge_files]
        # increase the image size doesn't seem to help to increase the accurycy. Good footage is still the key. 
        #result =self.model.predict(images, imgsz = ObjectDetector.default_imgsz, verbose=False)
        result =self.model.predict(images, verbose=False)
        return result 
    @staticmethod
    def analyze_result(res): 
        classes=res.boxes.cls
        def area(xyxy): 
            c=xyxy.numpy()[0]
            return abs((c[2]-c[0]) * (c[3]-c[1]))
        xyxys=[box.xyxy for box in res.boxes if box.cls in [0,3,4]]
        areas=[area(xyxy) for xyxy in xyxys]    
        return (classes==0).sum().item(), (classes==3).sum().item(), (classes==4).sum().item(), sum(areas)

    @staticmethod
    def annotate(image: Image.Image, result ) -> Image.Image:
        detections = sv.Detections.from_ultralytics(result)
        text_scale = sv.calculate_optimal_text_scale(resolution_wh=image.size)

        box_annotator = sv.BoxAnnotator()
        label_annotator = sv.LabelAnnotator(
            text_color=sv.Color.BLACK,
            text_scale=text_scale,
            smart_position=True
        )

        out = image.copy()
        out = box_annotator.annotate(out, detections)
        out = label_annotator.annotate(out, detections)
        out.thumbnail((1000, 1000))
        return out

