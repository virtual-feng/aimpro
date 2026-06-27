import os 
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
import shutil
from common_utils import call_command_line, smooth
from ml.detectors_v2 import ObjectDetector
from video.synchronizer import * 
from video.ffmpeg_wrapper import * 
from multi_cam_switch.ffmpeg_command_generator import * 
import pandas as pd 
import fnmatch
import logging


script_name = Path(__file__).name
installation_dir=Path(__file__).resolve().parent.parent.parent
resource_dir=os.path.join(installation_dir, 'resources')
load_dotenv(dotenv_path=os.path.join(installation_dir,'.env'))

class Workspace(): 
    def __init__(self):
        pid=os.getpid()
        tmp_dir=os.getenv('tmp_dir')
        appdir=os.path.join(tmp_dir, script_name) 
        Path(appdir).mkdir(parents=True,exist_ok=True)
        previous_pids = os.listdir(appdir)
        if len(previous_pids)>0: 
            last_pid=previous_pids[0]
            logging.info(f"resume the last job {last_pid}")
            self.dir=os.path.join(tmp_dir, script_name, f"{last_pid}")    
        else: 
            self.dir=os.path.join(tmp_dir, script_name, f"{pid}")
        Path(self.dir).mkdir(parents=True,exist_ok=True)

        self.left_frames_dir=os.path.join(self.dir, 'left')
        Path(self.left_frames_dir).mkdir(parents=True, exist_ok=True)
        
        self.right_frames_dir=os.path.join(self.dir, 'right')
        Path(self.right_frames_dir).mkdir(parents=True, exist_ok=True)

        #finally , copy logo. 
        logo_file_path_name=os.path.join(resource_dir, "your-court-vision-light-blue.png")
        self.logo_file_path_name=os.path.join(self.dir, "your-court-vision.png")
        shutil.copy(logo_file_path_name, self.logo_file_path_name)
        logging.info(f"workspace {self.dir} created")

    def remove_workspace(self):
        shutil.rmtree(self.dir)
        logging.info(f"workspace {self.dir} deleted")

extract_fps=3
extract_img_fmt="jpg"
detection_chunk_size=60
class ClipPicker(): 
    def __init__(self, left_video_file,right_video_file,workspace):
        self.left_video_file=left_video_file
        self.right_video_file=right_video_file
        self.workspace=workspace
        model_path=os.path.join(os.getenv("ml_model_dir"),"yolo26-basketball-player-detection-model-small-test_v3_80_epochs.pt") 
        self.object_detector=ObjectDetector(model_path)
        logging.info(f"loaded ml model from  {model_path} ")
    
    def synch_left_right(self): 
        offset, meaning = find_offset_seconds(self.workspace.dir,
                                                  self.left_video_file, 
                                                  self.right_video_file)
        
        logging.info(f"video offset: {offset}, {meaning}")
        #offset=round(offset)

        left_video_duration= get_video_duration(self.left_video_file)
        right_video_duration= get_video_duration(self.right_video_file)
        logging.info(f"left video duration: {left_video_duration}, righ: {right_video_duration}")
        
        
        if offset <0: 
            # right start early
            right_start=-1*offset
            new_right_duration =  right_video_duration+offset 
            min_duration =min(left_video_duration, new_right_duration)
            ts=( 0, min_duration, right_start, right_start+min_duration) 
        elif offset>0: 
            left_start=offset 
            new_left_duration = left_video_duration-offset
            min_duration=min(new_left_duration, right_video_duration)
            ts=(left_start, left_start+ min_duration, 0, min_duration)
        return offset, tuple(format_seconds_to_hhmmss(t) for t in ts)
    
    def extract_frames(self, left_start, left_end, right_start, right_end): 
        file_name_pattern=f"%d.{extract_img_fmt}"
        
        left_imges = list(fnmatch.filter(os.listdir(self.workspace.left_frames_dir), f"*.{extract_img_fmt}"))
        right_imges = list(fnmatch.filter(os.listdir(self.workspace.right_frames_dir), f"*.{extract_img_fmt}"))
        if len(left_imges)>0 and len(right_imges)>0:
            logging.info(f"frames already extracted")
            return  
        
        ouput_path_pattern = os.path.join(self.workspace.left_frames_dir, file_name_pattern)
        extract_frames_from_video(self.left_video_file, left_start, left_end, extract_fps, ouput_path_pattern)
        ouput_path_pattern = os.path.join(self.workspace.right_frames_dir, file_name_pattern)
        extract_frames_from_video(self.right_video_file, right_start, right_end, extract_fps, ouput_path_pattern)

        #rename files. 
        def rename_img_file_to_seconds_index(fd):
            files = fnmatch.filter(os.listdir(fd), f"*.{extract_img_fmt}")
            for f in files: 
                parts=f.split(".")
                file_index, ext=int(parts[0])-1, parts[1]
                second, index_in_second=divmod(file_index,extract_fps)
                new_file_name=f"{second}-{index_in_second}.{ext}"
                shutil.move(os.path.join(fd,f), os.path.join(fd,new_file_name))
        rename_img_file_to_seconds_index(self.workspace.left_frames_dir)
        rename_img_file_to_seconds_index(self.workspace.right_frames_dir)

    def detect_basketball_and_players(self): 
        def detect(video_frame_dir, csv_file_path_name): 
            files=fnmatch.filter(os.listdir(video_frame_dir), f"*.{extract_img_fmt}")
            df=pd.DataFrame(data=files, columns=["file_name"])
            df['chunk']=range(df.shape[0])
            df['chunk']=df.chunk//detection_chunk_size
            def detect_chunk(gdf):
                logging.info(f"object detection chuck : {gdf.name}")
                files=[os.path.join(video_frame_dir,f) for f in gdf.file_name] 
                results=self.object_detector.detect_objects_from_images(files)
                raw_oput=[ObjectDetector.analyze_result(r) for r in results]
                num_of_basketballs, num_of_players , num_of_possessions, total_object_area= zip (*raw_oput)
                gdf['has_baseketball']=num_of_basketballs
                gdf['has_baseketball']=gdf.has_baseketball>0
                gdf['has_possession']=num_of_possessions
                gdf['has_possession']=gdf.has_possession>0
                gdf['total_num_of_players']=num_of_players
                gdf['total_object_area']=total_object_area
                return gdf 
            ret= df.groupby('chunk').apply(detect_chunk)
            ret.sort_values(by="file_name", inplace=True)
            #ret.to_csv(os.path.join(video_frame_dir, "frame_information.csv"), index=False)
            ret.to_csv(csv_file_path_name)
            return ret
        
        csv_file=os.path.join(self.workspace.dir,"left_frame_information.csv")
        if os.path.exists(csv_file): 
            left_frames_df = pd.read_csv(csv_file, index_col=None)  
        else: 
            left_frames_df = detect(self.workspace.left_frames_dir, csv_file)
        
        csv_file=os.path.join(self.workspace.dir, "right_frame_information.csv")
        if os.path.exists(csv_file): 
            right_frames_df = pd.read_csv(csv_file, index_col=None)  
        else: 
            right_frames_df = detect(self.workspace.right_frames_dir, csv_file)
        
 
        def agg_frame_information_df(df):
            def extract_second_and_index(fn):
                parts = fn.split(".")[0].split("-") 
                return parts[0], parts[1]
            pairs=df.file_name.apply(extract_second_and_index)
            df['second'], df["index_within_second"]=zip (*pairs)
            df['second'], df["index_within_second"]=df.second.astype(int), df.index_within_second.astype(int)
            adf=df.groupby('second').agg(
                {
                    "has_baseketball":'any',
                    "total_num_of_players":'sum' ,
                    "has_possession":'any', 
                    "total_object_area":'sum'   
                } 
            ).reset_index()
            adf.sort_values(by='second', inplace=True)
            return adf 

        return agg_frame_information_df(left_frames_df), agg_frame_information_df(right_frames_df)


    def choose_active_camera(self, left_frames_df, right_frames_df): 
        mdf=left_frames_df.merge(right_frames_df, how='inner', on='second', suffixes=("_l","_r"))

        def choose(r):
            if r['total_num_of_players_l']>r['total_num_of_players_r']:
                return 'left'
            elif r['total_num_of_players_l']<r['total_num_of_players_r']:
                return 'right'
            else:
                if r['total_object_area_l']>r['total_object_area_r']:
                    return 'left'
                elif r['total_object_area_l']<r['total_object_area_r']:
                    return 'right'
            return None
        mdf.sort_values(by='second', ascending=True, inplace=True)
        mdf['active_camera_raw']=mdf.apply(choose, axis=1)
        mdf.ffill(inplace=True)
        mdf['active_camera']=smooth(mdf.active_camera_raw)
        mdf.to_csv(os.path.join(self.workspace.dir,'active_camera.csv'), index=False)
        return mdf   
    
    def pick(self): 
        offset, (left_start, left_end, right_start, right_end) =self.synch_left_right()
        self.extract_frames(left_start, left_end, right_start, right_end)
        left_frames_df, right_frames_df=self.detect_basketball_and_players()
        logging.info(f"left_frames_df={left_frames_df.shape}, right_frames_df={right_frames_df.shape}")
        return self.choose_active_camera(left_frames_df, right_frames_df), offset 


video_fps=60
class VideoComposer(): 
    def __init__(self, left_video_file,right_video_file, output_video_file, workspace, pip=True, watermark=True):
        self.left_video_file=left_video_file
        self.right_video_file=right_video_file
        self.output_video_file=output_video_file
        self.pip=pip 
        self.watermark=watermark
        self.workspace=workspace
        model_path=os.path.join(os.getenv("ml_model_dir"),"yolo26-basketball-player-detection-model-small-test_v3_80_epochs.pt") 
        self.object_detector=ObjectDetector(model_path)
        logging.info(f"loaded ml model from  {model_path} ")
    
    def copy_source_to_workspace(self): 
        old_file_path_name=self.left_video_file
        _,file=os.path.split(self.left_video_file)
        self.left_video_file=os.path.join(self.workspace.dir, file)
        shutil.copy(old_file_path_name, self.left_video_file)
        
        old_file_path_name=self.right_video_file
        _,file=os.path.split(self.right_video_file)
        self.right_video_file=os.path.join(self.workspace.dir, file)
        shutil.copy(old_file_path_name, self.right_video_file)
    

    def cut_and_compose(self):
        if self.watermark: 
            logo_file_path_name=self.workspace.logo_file_path_name
        else: 
            logo_file_path_name=None 

        picker=ClipPicker(self.left_video_file,self.right_video_file, self.workspace)
        mdf , offset= picker.pick()
        
        cmds = gen_cmds_from_ac_df(mdf, 
                                   offset, 
                                   self.left_video_file, 
                                   self.right_video_file, 
                                   output_fps=video_fps, 
                                   logo_file_path_name=logo_file_path_name, 
                                   pip=self.pip )
        post_process_extract_cmds(cmds, self.workspace.dir)
        cmd_line=f"bash {self.workspace.dir}/extract_part.sh"
        call_command_line(cmd_line)
        
        tmp_output_vid_file=os.path.join(self.workspace.dir,"temp_output.MP4")
        cmd = gen_concat_command(self.workspace.dir, "part*.MP4",tmp_output_vid_file)
        call_command_line(cmd)
        
        return tmp_output_vid_file
    
    def process(self):
        # self.copy_source_to_workspace()
        tmp_output_vid_file=self.cut_and_compose()
        shutil.copy(tmp_output_vid_file, self.output_video_file)


import argparse
def analyze_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--left_video_file')
    parser.add_argument('-r', '--right_video_file')
    parser.add_argument('-o', '--output_video_file')
    parser.add_argument('-p', '--pip', choices=['Y', 'N'], default="Y")
    parser.add_argument('-w', '--watermark', choices=['Y', 'N'], default="Y")
    
    return parser.parse_args()

if __name__ == "__main__":
    from common_utils import setup_logger
    from datetime import datetime
    log_dir=os.getenv('log_dir')
    setup_logger('INFO', log_file=os.path.join(log_dir, f"{script_name}.log"))
    args = analyze_args()
    
    workspace=Workspace()
    try:
        start_time=datetime.now()
        gen=VideoComposer(args.left_video_file, args.right_video_file,args.output_video_file, workspace, pip=(args.pip.upper()=='Y'), watermark=(args.watermark.upper()=='Y'))
        gen.process()
        end_time=datetime.now()
        delta = (end_time-start_time).total_seconds()
        delta_in_minutes, reminding_seconds = int(delta//60), int(delta%60) 
        print(f"it took {delta_in_minutes} minutes and {reminding_seconds} seconds to produce {args.output_video_file}. ")

        # fix the iphone ffmpeg -i iphone.mp4 -vcodec libx264 -crf 18 -r 30 -pix_fmt yuv420p fixed_iphone.mp4
    finally:
        workspace.remove_workspace()


