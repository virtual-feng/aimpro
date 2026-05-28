import os 
from ultralytics import YOLO
from PIL import Image
import supervision as sv
import logging

model_dir=os.getenv('ml_model_dir')
player_detection_model=YOLO(os.path.join(model_dir,"yolo26-basketball-player-detection-model-test_v2_40_epochs.pt"))

def detect_objects_on_multiple_images(files):
    images=[Image.open(f) for f in files]
    result =player_detection_model.predict(images, verbose=False)
    return result 

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

def analyze_result(res): 
    classes=res.boxes.cls
    return (classes==0).sum().item(), (classes==3).sum().item(), (classes==4).sum().item()