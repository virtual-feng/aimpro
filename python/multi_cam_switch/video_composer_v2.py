import os 
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
import shutil
from common_utils import call_command_line
from ml.detectors_v2 import ObjectDetector
from video.synchronizer import * 
from video.ffmpeg_wrapper import * 
import pandas as pd 
import fnmatch
import logging
from multi_cam_switch.workspace import Workspace
from multi_cam_switch.ffmpeg_cmd_string_gen import * 
script_name = Path(__file__).name
installation_dir=Path(__file__).resolve().parent.parent.parent

load_dotenv(dotenv_path=os.path.join(installation_dir,'.env'))

video_fps=60


class VideoComposer(): 
    def __init__(self,workspace,ouput_video_file,  pip=True, watermark=True):
        self.workspace=workspace
        self.output_video_file=ouput_video_file
        self.pip=pip 
        self.watermark=watermark
    
    @staticmethod
    def gen_cmds_from_ac_df(mdf, output_fps=60, logo_file_path_name=None, pip=True ):
        def gen_cmd(start_row, end_row):
            start_row, end_row=start_row._asdict(), end_row._asdict()
            active_camera_index=start_row['active_camera_index']
            
            #if timeout or break, don't bother produce any command. 
            if active_camera_index==-1: 
                return None
            

            start_hhmmss=format_seconds_to_hhmmss(start_row["ms_rounded"]/1000) 
            end_hhmmss=format_seconds_to_hhmmss(end_row["ms_rounded"]/1000)
            main_video_file_name=start_row[f"video_file_{active_camera_index}"]
                
            if pip: 
                pip_start_hhmmss=format_seconds_to_hhmmss(start_row["ms_rounded"]/1000 )
                pip_camera_index=1 if active_camera_index==0 else 0
                pip_video_file_name=start_row[f"video_file_{pip_camera_index}"]
                duration = (end_row["ms_rounded"]-start_row["ms_rounded"])/1000.0
            
                if logo_file_path_name: 
                    cmd= cut_watermark_pip_encode_cmd( 
                            main_video_file_name, start_hhmmss, duration, 
                            pip_video_file_name, pip_start_hhmmss,
                            logo_file_path_name,
                            "part_to_be_replaced", output_fps=output_fps)
                else: 
                    cmd=  cut_pip_encode_cmd( main_video_file_name, start_hhmmss, duration, 
                            pip_video_file_name, pip_start_hhmmss,
                            "part_to_be_replaced", output_fps=output_fps)
            else: 
                if logo_file_path_name: 
                    cmd=cut_watermark_encode_cmd(main_video_file_name, logo_file_path_name, start_hhmmss, end_hhmmss, "part_to_be_replaced", output_fps=output_fps)
                else: 
                    cmd= cut_encode_cmd(main_video_file_name, start_hhmmss, end_hhmmss, "part_to_be_replaced", output_fps=output_fps)
            logging.info(f"{cmd}")
            return cmd 
        start_r, last_r=None, None  
        cmds=[]
        for r in mdf.itertuples():
            if start_r is None: 
                start_r, last_r=r, r 
                continue
            else: 
                if r.active_camera_index!=last_r.active_camera_index: 
                    cmds.append(gen_cmd(start_r, last_r))
                    start_r, last_r=r, r 
                else:
                    last_r=r 

        if start_r and last_r: 
            cmds.append(gen_cmd(start_r,last_r))       
        return [ c for c in cmds if c is not None]

    @staticmethod
    def post_process_extract_cmds(extract_cmds, workspace_dir): 
        def rpl(index, cmd): 
            part=os.path.join(workspace_dir, f"part-{index}.MP4")
            return cmd.replace('part_to_be_replaced', part)
        extract_cmds= [rpl(i,c) for i, c in enumerate(extract_cmds) ]
        text="\n".join(extract_cmds)
        with open(os.path.join(workspace_dir,'extract_part.sh'), 'w') as h: 
            h.write(text)
        return extract_cmds

    @staticmethod
    def gen_concat_command(workspace_dir, part_file_name_pattern, output_file_name_path): 
            part_list=list(fnmatch.filter(os.listdir(workspace_dir), part_file_name_pattern))
            part_list.sort(key=lambda fn: int(fn.split(".")[0].split("-")[-1]))
            list_file_name=os.path.join(workspace_dir, 'part-list.txt')
            with open(list_file_name, 'w') as h: 
                for p in part_list:
                    h.write(f"file '{p}' \n")
            return   f"ffmpeg -f concat -safe 0 -i {list_file_name} -c copy {output_file_name_path}"


    def process(self):
        if self.watermark: 
            logo_file_path_name=self.workspace.logo_file_path_name
        else: 
            logo_file_path_name=None 
        mdf=pd.read_parquet(os.path.join(self.workspace.dir, "merged_obj_dection_result.parquet"))
        
        effective_active_camera_indexes= [i for i in mdf.active_camera_index.unique() if i>=0]
        pip=self.pip and len(effective_active_camera_indexes)==2
        
        cmds = VideoComposer.gen_cmds_from_ac_df(mdf, 
                                   output_fps=video_fps, 
                                   logo_file_path_name=logo_file_path_name, 
                                   pip=pip )
        
        VideoComposer.post_process_extract_cmds(cmds, self.workspace.dir)
        cmd_line=f"bash {self.workspace.dir}/extract_part.sh"
        call_command_line(cmd_line)
        
        cmd =  VideoComposer.gen_concat_command(self.workspace.dir, "part*.MP4",self.output_video_file)
        call_command_line(cmd)
        

import argparse
def analyze_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--root_folder", type=str,   help="the root dir of all video files, optional.")
    parser.add_argument("-i", "--input_files", nargs="+" , type=str,   help="video files from 2 or more camerasl. If root_folder specified, we assume all video files are under the same root folder.")
    parser.add_argument("-o", "--output_file", type=str,   help="the output file name. If root_folder specified , the output file will be under the root folder.")
    parser.add_argument('-p', '--pip', choices=['Y', 'N'], default="Y")
    parser.add_argument('-w', '--watermark', choices=['Y', 'N'], default="Y")
    return parser.parse_args()
    
def display_duration(start,message): 
    end_time=datetime.now()
    delta = (end_time-start_time).total_seconds()
    delta_in_minutes, reminding_seconds = int(delta//60), int(delta%60) 
    print(f"it took {delta_in_minutes} minutes and {reminding_seconds} seconds to {message}.")

if __name__ == "__main__":
    from common_utils import setup_logger
    from datetime import datetime
    from multi_cam_switch.clip_picker import ClipPicker
    from multi_cam_switch.video_preprocessor import VideoPreprocessor

    import glob 
    log_dir=os.getenv('log_dir')
    setup_logger('INFO', log_file=os.path.join(log_dir, f"{script_name}.log"))
    args = analyze_args()
    try:
        workspace=Workspace(Path(__file__).name)
        video_files, output_file=args.input_files, args.output_file
        if args.root_folder: 
            video_files=[os.path.join(args.root_folder, v) for v in video_files]
            output_file=os.path.join(args.root_folder, output_file)
        
        start_time=datetime.now()
        process_start_time=start_time

        VideoPreprocessor(video_files, workspace).process()
        display_duration(start_time,"preprocess videos")


        start_time=datetime.now()
        video_files= glob.glob(f"{workspace.dir}/procesed_*", recursive=False)
        ClipPicker(video_files, workspace ).process()
        display_duration(start_time,"select footage")


        start_time=datetime.now()
        VideoComposer(workspace,output_file, args.pip.upper()=='Y', args.watermark.upper()=='Y').process()
        display_duration(start_time,"compose the final video.") 

        display_duration(process_start_time,"run full pipeline.") 

        # fix the iphone ffmpeg -i iphone.mp4 -vcodec libx264 -crf 18 -r 30 -pix_fmt yuv420p fixed_iphone.mp4
    finally:
        pass 

        #workspace.remove_workspace()


