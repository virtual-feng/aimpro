import datetime
import json
from common_utils import call_command_line
import logging
import os
import json
import shutil
import math 

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
    
def extract_video_infor(vid_file): 
    cmd=f"ffprobe -v error -select_streams v:0 -show_entries stream=avg_frame_rate,r_frame_rate,codec_name,pix_fmt,width,height -of json {vid_file}"
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

def normalize_video(vid_file, output_file):
    width=1920
    height=1080
    pix_fmt="yuv420p" 
    codec='hevc'
    fps ="60/1"
    audio_sample_rate="48000"

    v_info= extract_video_infor(vid_file)
    logging.info(v_info)
    a_info= extract_audio_sample_rate(vid_file)
    logging.info(v_info)
    need_normalize= v_info.get('width')!=width or v_info.get('height')!=height or  v_info.get("codec_name")!=codec or   v_info.get("avg_frame_rate")!=fps or v_info.get("r_frame_rate")!=fps or v_info.get('pix_fmt')!=pix_fmt  or a_info.get("sample_rate")!=audio_sample_rate
    
    if need_normalize: 
        out_range=":out_range=tv" if v_info.get('pix_fmt')=='yuvj420p' else ""
        cmd = f'ffmpeg -i "{vid_file}" -vf "scale={width}:{height}{out_range},format={pix_fmt}" -c:v libx265 -r 60 -vsync cfr -c:a aac -ar {audio_sample_rate} -b:a 192k "{output_file}"'
        call_command_line(cmd)        

def normalize_video_pair(v1, v2, v1_out, v2_out):
    d1=extract_video_infor(v1)
    d2=extract_video_infor(v2)

    d1['audio_sample_rate']=int(extract_audio_sample_rate(v1).get('sample_rate'))
    d2['audio_sample_rate']=int(extract_audio_sample_rate(v2).get('sample_rate'))
    
    d_o={
        'width':min(d1['width'],d2['width']) , 
        'height':min(d1['height'],d2['height']) ,
        'codec_name':'hevc', 
        'avg_frame_rate':"60/1", 
        'pix_fmt':'yuv420p',
        'audio_sample_rate':f"{min(d1['audio_sample_rate'],d2['audio_sample_rate'])}"
    }

    need_norm_v1, need_norm_v2 = d1!=d_o, d2!=d_o

    width=d_o.get('width')
    height=d_o.get('height')
    # pix_fmt="yuv420p" 
    # codec='hevc'
    # fps ="60/1"
    audio_sample_rate=f"{d_o.get('audio_sample_rate')}"

    file_produced =[]
    if need_norm_v1: 
        out_range=":out_range=tv" if d1.get('pix_fmt')=='yuvj420p' else ""
        cmd = f'ffmpeg -i "{v1}" -vf "scale={width}:{height}{out_range},format=yuv420p" -c:v libx265 -r 60 -vsync cfr -c:a aac -ar {audio_sample_rate} -b:a 192k "{v1_out}"'
        call_command_line(cmd)
        file_produced.append(v1_out)        
    
    if need_norm_v2: 
        out_range=":out_range=tv" if d2.get('pix_fmt')=='yuvj420p' else ""
        cmd = f'ffmpeg -i "{v2}" -vf "scale={width}:{height}{out_range},format=yuv420p" -c:v libx265 -r 60 -vsync cfr -c:a aac -ar {audio_sample_rate} -b:a 192k "{v2_out}"'
        call_command_line(cmd)        
        file_produced.append(v2_out)
    return file_produced

def add_subtitle(vid_file, start_seconds, end_seconds, text, workspace_dir):
    pass 
    # def format_seconds_to_hhmmss(seconds):
    #     #seconds is float number, it might have decimal part. 
    #     seconds =int(seconds)
    #     decimal_part, integer_part = math.modf(seconds)
    #     ms, seconds = int(decimal_part*1000), int(integer_part) 
    #     hours, remainder = divmod(seconds, 3600)
    #     minutes, seconds = divmod(remainder, 60)
    #     ret =  f"{hours:02}:{minutes:02}:{seconds:02}"
    #     if decimal_part>0: 
    #         ret =f"{ret},{ms:03}"
    #     return ret 


    # text="Stared by Venom U16-2 boys. <br/> Produced by @YourCourtVision. "
    # start_seconds, end_seconds = format_seconds_to_hhmmss(start_seconds), format_seconds_to_hhmmss(end_seconds)
    # #start_seconds, end_seconds = start_seconds.replace(".",","), end_seconds.replace(".",",")
    # srt_file = os.path.join(workspace_dir, "temp_srt.srt")
    # lines=f"""
    # text
    # 1
    # {start_seconds} --> {end_seconds}
    # {text}
    # """.splitlines()
    # lines=[l.strip() for l in lines]
    # lines=[l for l in lines if len(l)>0]
    # with open(srt_file, "w") as h: 
    #     h.write("\n".join(lines))    

    # temp_output_file= os.path.join(workspace_dir, "temp_video.MP4")
    # cmd=f'ffmpeg -i {vid_file} -vf "subtitles={srt_file}" {temp_output_file}'
    # call_command_line(cmd)

    # shutil.copy(temp_output_file, vid_file)
    # os.remove(srt_file)
    # os.remove(temp_output_file)



import argparse
def analyze_args():
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subparser for 'create'
    parser_info = subparsers.add_parser("info", help="get video infor")
    parser_info.add_argument("-i", "--input_file" , help="the vid file ")
    
    parser_normalize = subparsers.add_parser("normalize", help="normalize")
    parser_normalize.add_argument("-i", "--input_file" , help="the vid file ")
    
    parser_normalize_pair = subparsers.add_parser("norm_pair", help="normalize")
    parser_normalize_pair.add_argument("-l", "--left_file" , help="the vid file ")
    parser_normalize_pair.add_argument("-r", "--right_file" , help="the vid file ")

    subtitle_normalize = subparsers.add_parser("subtitle", help="normalize")
    subtitle_normalize.add_argument("-i", "--input_file" , help="the vid file ")
    subtitle_normalize.add_argument("-s", "--start_seconds" , help="the vid file ")
    subtitle_normalize.add_argument("-e", "--end_seconds" , help="the vid file ")
    #subtitle_normalize.add_argument("-t", "--text" , help="the vid file ")
    
    
    
    
    
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
        output_file_path_name=os.path.join(file_dir, f"normalized_{file_name}") 
        normalize_video(args.input_file, output_file_path_name)

    elif args.command =='norm_pair':
        file_dir, file_name=os.path.split(args.left_file)
        left_output_file_path_name=os.path.join(file_dir, f"normalized_{file_name}") 

        file_dir, file_name=os.path.split(args.right_file)
        right_output_file_path_name=os.path.join(file_dir, f"normalized_{file_name}") 
        
        file_produced = normalize_video_pair(args.left_file,args.right_file, left_output_file_path_name, right_output_file_path_name)

        if file_produced: 
            print(f"following video files have been created:")
            for f in file_produced: 
                print(f)
    elif args.command =='subtitle': 
        workspace_dir=os.getcwd()
        add_subtitle(args.input_file, args.start_seconds, args.end_seconds, 'bla', workspace_dir)

    else : 
        pass 

