import os 
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
import shutil
from common_utils import call_command_line
from ml.detectors import detect_objects_on_multiple_images,analyze_result
from video.synchronizer import * 
import fnmatch
load_dotenv()

video_file_ext="MP4"
extract_fps=3
extract_img_fmt="jpg"
detection_chunk_size=60

class VideoGenerator(): 
    
    def __init__(self, left_video_file,right_video_file, output_video_file):
        self.left_video_file=left_video_file
        self.right_video_file=right_video_file
        self.output_video_file=output_video_file
        self.setup_workspace()
    
    def setup_workspace(self):
        pid=os.getpid()
        tmp_dir=os.getenv('tmp_dir')
        self.workspace_dir=os.path.join(tmp_dir, f"{pid}")
        os.mkdir(workspace_dir)
        
    def remove_workspace(self): 
        shutil.rmtree(self.workspace_dir)

    def create_frame_dir(self):
        self.left_frames_dir=os.path.join(self.workspace_dir, 'left')
        Path(self.left_frames_dir).mkdir(parents=True, exist_ok=True)

        self.right_frames_dir=os.path.join(self.workspace_dir, 'right')
        Path(self.right_frames_dir).mkdir(parents=True, exist_ok=True)

    def sample_frames_from_video(self): 
        file_name_pattern=f"%d.{extract_img_fmt}"
        output = f"{os.path.join(self.left_frames_dir, file_name_pattern)}"
        cmd=f"ffmpeg -i {self.left_video_file} -vf  scale=1280:720,fps={extract_fps} {output}"
        call_command_line(cmd)

        output = f"{os.path.join(self.right_frames_dir, file_name_pattern)}"
        cmd=f"ffmpeg -i {self.right_video_file} -vf  scale=1280:720,fps={extract_fps} {output}"
        call_command_line(cmd)

        def rename_frame_files(frame_dirs):
            for fd in frame_dirs: 
                frames = fnmatch.filter(os.listdir(fd), f"*.{extract_img_fmt}")
                for f in frames: 
                    parts=f.split(".")
                    file_index, ext=int(parts[0])-1, parts[1]
                    second, index_in_second=divmod(file_index,extract_fps)
                    new_file_name=f"{second}-{index_in_second}.{ext}"
                    shutil.move(os.path.join(fd,f), os.path.join(fd,new_file_name))
        rename_frame_files([self.left_frames_dir, self.right_frames_dir])
    
    def detect_basketball_and_players(self ):
        def detect(video_frame_dir): 
            files=fnmatch.filter(os.listdir(video_frame_dir), f"*.{extract_img_fmt}")
            df=pd.DataFrame(data=files, columns=["file_name"])
            df['chunk']=range(df.shape[0])
            df['chunk']=df.chunk//chunk_size
            def detect_chunk(gdf):
                files=[os.path.join(video_frame_dir,f) for f in gdf.file_name] 
                results=detect_objects_on_multiple_images(files)
                trios=[analyze_result(r) for r in results]
                num_of_basketballs, num_of_players , num_of_possessions= zip (*trios)
                
                gdf['has_baseketball']=num_of_basketballs
                gdf['has_baseketball']=gdf.has_baseketball>0
                
                gdf['has_possession']=num_of_possessions
                gdf['has_possession']=gdf.has_possession>0
                
                gdf['total_num_of_players']=num_of_players
                return gdf 
            ret= df.groupby('chunk').apply(detect_chunk)
            ret.sort_values(by="file_name", inplace=True)
            return ret
        df=detect(self.left_frames_dir)
        df['video_file']=self.left_video_file
        df.to_csv(os.path.join(self.left_frames_dir, "frame_information.csv"), index=False)
        left_df = df 
        
        df=detect(self.right_frames_dir)
        df['video_file']=self.right_video_file
        df.to_csv(os.path.join(self.right_frames_dir, "frame_information.csv"), index=False)
        right_df=df 

        return left_df, right_df
    def agg_prediction_df(df):
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
                    "has_possession":'any'   
                } 
        ).reset_index()
        adf['second_in_hhmmss']=adf.second.apply(format_seconds_to_hhmmss)
        adf['video_file']=df.video_file.iloc[0]
        #please sort me first !
        adf.sort_values(by='second', inplace=True)
        adf['global_index']=range(adf.shape[0])
        return adf 

if __name__ == "__main__":
    import argparse
    from common_utils import setup_logger
    setup_logger('INFO')

    workspace_dir= setup_workspace()
    print(workspace_dir)

    remove_workspace(workspace_dir)
