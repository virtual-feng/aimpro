import datetime
import json
from common_utils import call_command_line
import logging
import os

def extract_audio(vid_file, output_file):
    cmd_line=f'ffmpeg  -i {vid_file} -b:a 192K -vn  -ac 1 -y  {output_file}'
    stdout, stderr = call_command_line(cmd_line)
    logging.info(stdout[:2])
    if stderr:
        return None
    return output_file

def get_video_duration(vid_file): 
    cmd_line=f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {vid_file}"
    stdout, stderr = call_command_line(cmd_line)
    if stderr:
        return None 
    return float(stdout)

def extract_frames_from_video(vid_file, start, end, extract_fps, ouput_path_pattern): 
    cmd=f"ffmpeg -ss {start} -to {end} -i {vid_file} -vf scale=1280:720,fps={extract_fps} {ouput_path_pattern}"
    stdout, stderr = call_command_line(cmd)
    logging.info(stdout[:2])
    