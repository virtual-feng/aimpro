import datetime
import json
from common_utils import call_command_line
import logging
import os
import json
import shutil
import math 
from pathlib import Path

def extract_audio(vid_file, output_file):
    cmd_line=f'ffmpeg   -i {vid_file} -b:a 192K -vn  -ac 1 -y  {output_file}'
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

def extract_frames_from_video(vid_file, start, end, extract_fps, ouput_path_pattern, image_size="1280:720"): 
    cmd=f"ffmpeg -ss {start} -to {end} -i {vid_file} -vf scale={image_size},fps={extract_fps} {ouput_path_pattern}"
    stdout, stderr = call_command_line(cmd)
    logging.info(stdout[:2])

def extract_frames_from_synched_video(vid_file, extract_fps, ouput_path_pattern, image_size="1280:720"): 
    cmd=f"ffmpeg  -i {vid_file} -vf scale={image_size},fps={extract_fps} {ouput_path_pattern}"
    stdout, stderr = call_command_line(cmd)
    logging.info(stdout[:2])


def extract_video_infor(vid_file): 
    cmd=f"ffprobe -v error -select_streams v:0 -show_entries stream=duration,bit_rate,avg_frame_rate,r_frame_rate,codec_name,pix_fmt,width,height -of json {vid_file}"
    stdout, stderr= call_command_line(cmd)
    if stderr:
        return None 
    j=json.loads(stdout)
    return j.get('streams')[0]

def extract_audio_sample_rate(vid_file): 
    cmd=f"ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate -of json {vid_file}"
    stdout, stderr= call_command_line(cmd)
    if stderr:
        return None 
    j=json.loads(stdout)
    return j.get('streams')[0]

def normalize_video(vid_file,  output_file, start_hhmmss=None, end_hhmmss=None, fast=True):
    width=1280
    height=720
    pix_fmt="yuv420p" 
    codec='hevc'
    fps ="60/1"
    audio_sample_rate="48000"

    v_info=extract_video_infor(vid_file)
    logging.info(v_info)
    a_info= extract_audio_sample_rate(vid_file)
    logging.info(v_info)
    need_normalize= v_info.get('width')!=width or v_info.get('height')!=height or  v_info.get("codec_name")!=codec or   v_info.get("avg_frame_rate")!=fps or v_info.get("r_frame_rate")!=fps or v_info.get('pix_fmt')!=pix_fmt  or a_info.get("sample_rate")!=audio_sample_rate
    original_bit_rate = int(v_info.get('bit_rate'))//1000
    logging.info(f"original bit rate={original_bit_rate}k")

    output_dir= os.path.dirname(output_file)
    passlogfile=os.path.join(output_dir, "ffmpeg_passlog")

    if start_hhmmss and end_hhmmss: 
        cut_clause=f" -ss {start_hhmmss} -to {end_hhmmss}"
    else: 
        cut_clause="" 
    try: 
        if need_normalize:
            out_range=":out_range=tv" if v_info.get('pix_fmt')=='yuvj420p' else ""
            if fast :
                cmd = f'ffmpeg -y {cut_clause} -i "{vid_file}" -vf "scale={width}:{height}{out_range},format={pix_fmt}"  -c:v libx264 -crf 23 -r {fps} -vsync cfr -c:a copy "{output_file}"'
                call_command_line(cmd) 
                
            else: 
                #cmd = f'ffmpeg -i "{vid_file}" -vf "scale={width}:{height}{out_range},format={pix_fmt}" -c:v libx264 -r {fps} -vsync cfr -c:a aac -ar {audio_sample_rate} -b:a 192k "{output_file}"'
                cmd = f'ffmpeg -y {cut_clause} -i "{vid_file}" -vf "scale={width}:{height}{out_range},format={pix_fmt}" -c:v libx264 -b:v {original_bit_rate}k -pass 1 -passlogfile "{passlogfile}" -r {fps} -vsync cfr -c:a aac -ar {audio_sample_rate} -b:a 192k -f null /dev/null'
                call_command_line(cmd) 
                cmd = f'ffmpeg -y {cut_clause} -i "{vid_file}" -vf "scale={width}:{height}{out_range},format={pix_fmt}" -c:v libx264 -b:v {original_bit_rate}k -pass 2 -passlogfile "{passlogfile}" -r {fps} -vsync cfr -c:a aac -ar {audio_sample_rate} -b:a 192k "{output_file}"'
                call_command_line(cmd)        
    finally: 
        # Scan the current directory for the pattern and delete matches
        for file_path in Path(output_dir).glob("ffmpeg_passlog*"):
            file_path.unlink(missing_ok=True)

def normalize_video_fast(vid_file,  output_file, start_hhmmss=None, end_hhmmss=None):
    width=1280
    height=720
    pix_fmt="yuv420p" 
    fps ="60/1"
    
    v_info=extract_video_infor(vid_file)
    
    if start_hhmmss and end_hhmmss: 
        cut_clause=f" -ss {start_hhmmss} -to {end_hhmmss}"
    else: 
        cut_clause="" 
    out_range=":out_range=tv" if v_info.get('pix_fmt')=='yuvj420p' else ""
    cmd = f'ffmpeg -y {cut_clause} -i "{vid_file}" -vf "scale={width}:{height}{out_range},format={pix_fmt}"  -c:v libx264 -crf 23 -r {fps} -vsync cfr -c:a copy "{output_file}"'
    call_command_line(cmd) 
    

import argparse
def analyze_args():
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subparser for 'create'
    parser_info = subparsers.add_parser("info", help="get video infor")
    parser_info.add_argument("-i", "--input_file" , help="the vid file ")
    
    parser_normalize = subparsers.add_parser("normalize", help="normalize")
    parser_normalize.add_argument("-i", "--input_file" , help="the vid file ")
    
    return parser.parse_args()


if __name__ == "__main__":
    from common_utils import setup_logger
    log_dir=os.getenv('log_dir')
    setup_logger('INFO')

    args = analyze_args()
    if args.command == 'info': 
        v_info= extract_video_infor(args.input_file)
        a_info= extract_audio_sample_rate(args.input_file)

        print(f"video infor: {v_info}")
        print(f"audio infor: {a_info}")

    elif args.command =='normalize':
        file_dir, file_name=os.path.split(args.input_file)
        output_file_path_name=os.path.join(file_dir, f"norm_{file_name}") 
        normalize_video(args.input_file, output_file_path_name)

    else : 
        pass 

