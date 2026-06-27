import os 
from video.synchronizer import * 
from video.ffmpeg_wrapper import * 
from multi_cam_switch.ffmpeg_cmd_string_gen import * 
from itertools import chain
import fnmatch
def gen_hhmmss(side, offset, second): 
    #if offset <0 , then right start early; otherwise left start early. 
    if offset<0: 
        if side =='right': 
            second =float(second) +offset*(-1)
    else: 
        if side=='left': 
            second =float(second) +offset
    return format_seconds_to_hhmmss(second)
 
def gen_cmds_from_ac_df(mdf, offset, left_video_file, right_video_file, output_fps=60, logo_file_path_name=None, pip=True ):
    def gen_cmd(start_r, last_r): 
        duration =last_r.second-start_r.second 
        if start_r.active_camera=='left':
            start_hhmmss=gen_hhmmss("left", offset, start_r.second)
            to_hhmmss=gen_hhmmss("left", offset, last_r.second)
            main_video_file_name=left_video_file
            pip_start_hhmmss=gen_hhmmss("right", offset, start_r.second)
            pip_video_file_name=right_video_file
        
        else:
            start_hhmmss=gen_hhmmss("right", offset, start_r.second)
            to_hhmmss=gen_hhmmss("right", offset, last_r.second)
            main_video_file_name=right_video_file
            pip_start_hhmmss=gen_hhmmss("left", offset, start_r.second)
            pip_video_file_name=left_video_file
        
        if pip : 
            if logo_file_path_name: 
                return cut_watermark_pip_encode_cmd( 
                        main_video_file_name, start_hhmmss, duration, 
                        pip_video_file_name, pip_start_hhmmss,
                        logo_file_path_name,
                        "part_to_be_replaced", output_fps=output_fps)
            else: 
                return  cut_pip_encode_cmd( main_video_file_name, start_hhmmss, duration, 
                        pip_video_file_name, pip_start_hhmmss,
                        "part_to_be_replaced", output_fps=output_fps)
        else: 
            if logo_file_path_name: 
                return cut_watermark_encode_cmd(main_video_file_name, logo_file_path_name, start_hhmmss, to_hhmmss, "part_to_be_replaced", output_fps=output_fps)
            else: 
                return cut_encode_cmd(main_video_file_name, start_hhmmss, to_hhmmss, "part_to_be_replaced", output_fps=output_fps)
    start_r, last_r=None, None  
    cmds=[]
    for r in mdf.itertuples():
        if start_r is None: 
            start_r, last_r=r, r 
            continue
        else: 
            if r.active_camera!=last_r.active_camera: 
                cmds.append(gen_cmd(start_r, last_r))
                start_r, last_r=r, r 
            else:
                last_r=r 

    if start_r and last_r: 
        cmds.append(gen_cmd(start_r,last_r))       
    return cmds 



def post_process_extract_cmds(extract_cmds, workspace_dir): 
    def rpl(index, cmd): 
        part=os.path.join(workspace_dir, f"part-{index}.MP4")
        return cmd.replace('part_to_be_replaced', part)
    extract_cmds= [rpl(i,c) for i, c in enumerate(extract_cmds) ]
    text="\n".join(extract_cmds)
    with open(os.path.join(workspace_dir,'extract_part.sh'), 'w') as h: 
        h.write(text)
    return extract_cmds

def part_sort_key(fn):
    return int(fn.split(".")[0].split("-")[-1])

def gen_concat_command(workspace_dir, part_file_name_pattern, output_file_name_path): 
        part_list=list(fnmatch.filter(os.listdir(workspace_dir), part_file_name_pattern))
        part_list.sort(key=part_sort_key)
        list_file_name=os.path.join(workspace_dir, 'part-list.txt')
        with open(list_file_name, 'w') as h: 
            for p in part_list:
                h.write(f"file '{p}' \n")
        return   f"ffmpeg -f concat -safe 0 -i {list_file_name} -c copy {output_file_name_path}"


