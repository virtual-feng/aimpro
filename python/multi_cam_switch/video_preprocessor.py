import logging
import fnmatch
import shutil
from pathlib import Path
import os 
from ml.detectors_v2 import ObjectDetector
from video.synchronizer import find_offset_seconds, format_seconds_to_hhmmss
from video.ffmpeg_wrapper import get_video_duration, extract_frames_from_video, normalize_video
from multi_cam_switch.workspace import Workspace

class VideoPreprocessor():
    
    def __init__(self, video_files,workspace):
        self.video_files=video_files
        self.workspace=workspace
        
    def synch_videos(self): 
        #use video 0 as reference, all offset of video 1, 2... are referencing video 0. 
        ref_video_file=self.video_files[0]
        def calc_offset(video): 
            if ref_video_file==video: 
                return 0 
            else: 
                offset, meaning = find_offset_seconds(self.workspace.dir,ref_video_file,video)
                logging.info(f"{video} offset related to ref_video: {offset}, {meaning}")
                # if offset >0: 
                #     meaning=f"video started later than reference video "
                # else: 
                #     meaning=f"video started earlier than reference video."
                return offset
        
        offsets=[calc_offset(f) for f in self.video_files]
        the_latest_start_time   =max(offsets)
        
        #if we assume ref video started at time 0, thenn ref video finished at 0+ref_duration. 
        #similarly, a video with offset to ref video, then video started at offset, and complete at offset +duration. 
        video_durations =[get_video_duration(f) for f in self.video_files]
        video_finish_time =[o+d for o,d in zip(offsets, video_durations)]
        the_earliest_finish_time=min(video_finish_time)
        usable_duration = the_earliest_finish_time-the_latest_start_time
        
        return list(zip (
            self.video_files, 
            [ (the_latest_start_time-o, the_latest_start_time-o+usable_duration) for o in offsets]
        ))

    
    def gen_output_file_path_name(self,f): 
        file_name_only =os.path.split(f)[-1]
        return os.path.join(self.workspace.dir,f'procesed_{file_name_only}')
            
    def process(self):
        for f in self.video_files: 
            if os.path.exists(self.gen_output_file_path_name(f)):
                logging.info(f"file {f} already preprocesed.skip")
                return 
            
        for file, (start_time, end_time) in self.synch_videos(): 
            output_file=self.gen_output_file_path_name(file)
            start_hhmmss= format_seconds_to_hhmmss(start_time) 
            end_hhmmss=format_seconds_to_hhmmss(end_time) 
            normalize_video(file,output_file, start_hhmmss, end_hhmmss)


    