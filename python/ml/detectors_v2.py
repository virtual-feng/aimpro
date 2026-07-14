import os 
from ultralytics import YOLO
from PIL import Image
import supervision as sv
import logging
from pathlib import Path
from sklearn.cluster import DBSCAN
import itertools
import numpy as np

import torch 



class ObjectDetector(): 
    default_imgsz=1280

    def __init__(self, model_file_path_name):

        self.model = YOLO(model_file_path_name)

    def detect_objects_from_images(self, imge_files, debug_output_dir=None): 
        images=[Image.open(f) for f in imge_files]

        if torch.backends.mps.is_available(): 
            result =self.model.predict(images,  device='mps',imgsz = ObjectDetector.default_imgsz, verbose=False) #might need tweak conf=0.25,  iou=0.45,
        else: 
            result =self.model.predict(images,imgsz = ObjectDetector.default_imgsz, verbose=False) #might need tweak conf=0.25,  iou=0.45,
        
        if debug_output_dir:
            images=[ObjectDetector.annotate(image, res) for image, res in zip(images, result)]
            for image, f in zip(images, imge_files):
                file_name=Path(f).name
                output_image_file_path_name=os.path.join(debug_output_dir, file_name)
                logging.info(f"annotated image saved to {output_image_file_path_name}")
                image.save(output_image_file_path_name)
        return result
    
    
    @staticmethod
    def analyze_result(res): 
        classes=res.boxes.cls
        def area(xyxy): 
            c=xyxy.cpu().numpy()[0]
            return abs((c[2]-c[0]) * (c[3]-c[1]))
        xyxys=[box.xyxy for box in res.boxes if box.cls in [0,3,4]]
        areas=[area(xyxy) for xyxy in xyxys]    
        return (classes==0).sum().item(), (classes==3).sum().item(), (classes==4).sum().item(), sum(areas)
    
    @staticmethod
    def identify_ball_and_players(res): 
        classes=res.boxes.cls
        def area(xyxy): 
            c=xyxy.cpu().numpy()[0]
            return abs((c[2]-c[0]) * (c[3]-c[1]))
        xyxys=[box.xyxy for box in res.boxes if box.cls in [0,1]]
        areas=[area(xyxy) for xyxy in xyxys]    
        #return num of balls, num of players, and total object area. 
        return  (classes==0).sum().item(),(classes==1).sum().item(),sum(areas)
    
    @staticmethod
    def identify_ball_and_players_v2(res): 
        classes=res.boxes.cls
        def area(xyxy): 
            c=xyxy
            return abs((c[2]-c[0]) * (c[3]-c[1]))
        ball_bboxs =[box.xyxy.cpu().numpy()[0] for box in res.boxes if box.cls==0]
        player_bboxes=[box.xyxy.cpu().numpy()[0] for box in res.boxes if box.cls==1]
        areas=[area(xyxy) for xyxy in player_bboxes]    
        #return num of balls, num of players, and total object area. 
        return  (classes==1).sum().item(),sum(areas), ball_bboxs
    
    @staticmethod
    def detect_and_remove_false_positive(bbox_series, eps_pixels=5, min_samples=15):
        bboxes = list(itertools.chain.from_iterable(bbox_series))
        logging.info(f"total {len(bboxes)} to be checked.")
        X = np.array(bboxes)
        db= DBSCAN(eps=eps_pixels,min_samples=min_samples).fit(X)
        logging.info(f"clusters found: {set(db.labels_)}")
        for l in set(db.labels_): 
            logging.info(f"numbers of elements in cluster {l} is {len(X[db.labels_==l])}")
        
        fpboxes=X[db.labels_==0]
        ret=bbox_series.tolist()
        def remove_false_positive(bboxes):
            return [b for b in bboxes if not ((b == fpboxes).all(axis=1).any())]
        return [ remove_false_positive(bbs) for bbs in ret]    


    # @staticmethod
    # def analyze_result_advanced(res): 
        
    #     def area(xyxy): 
    #         c=xyxy.cpu().numpy()[0]
    #         return abs((c[2]-c[0]) * (c[3]-c[1]))
    #     areas=[area(box.xyxy)*box.conf.item() for box in res.boxes if box.cls in [0,3,4]]
    #     total_conf_0 = sum([box.conf.item() for box in res.boxes if box.cls ==0]) #ball
    #     total_conf_3 = sum([box.conf.item() for box in res.boxes if box.cls ==3]) #player 
    #     total_conf_4 = sum([box.conf.item() for box in res.boxes if box.cls ==4]) #player-in-possision. 
    #     return total_conf_0, total_conf_3, total_conf_4, sum(areas)


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
        #out.thumbnail((1000, 1000))
        return out 
    
    @staticmethod
    def annotate_image_file(image_file, result, output_file):
        image=Image.open(image_file)
        out=ObjectDetector.annotate(image, result)
        out.save(output_file)
        
if __name__ == "__main__":
    import argparse
    from common_utils import setup_logger
    setup_logger('INFO')

    imgs = [
        "/mnt/ramdisk/clip_picker.py/54185/frames_of_video_1/99-333.jpg",
        "/mnt/ramdisk/clip_picker.py/54185/frames_of_video_1/98-500.jpg"
    ]
    od =ObjectDetector(f"/home/fnz/workspace/vid/model/yolo26-basketball-player-detection-model-small-test_v3_80_epochs.pt")
    results = od.detect_objects_from_images(imgs)
    for r in results:
        print(r)
        for b in r.boxes: 
            print(b)
            #print(analyze_result(r))
        ra = ObjectDetector.analyze_result_advanced(r)
        print(ra)