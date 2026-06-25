import os 
from video.synchronizer import * 
from video.ffmpeg_wrapper import * 
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

def gen_ffmpeg_extract_commands(mdf, offset, left_video_file, right_video_file, fps=60, logo_file_path_name=None ):
    def gen_cmd(start_r,last_r): 
        if start_r.active_camera=='left':
            start_hhmmss=gen_hhmmss("left", offset, start_r.second)
            to_hhmmss=gen_hhmmss("left", offset, last_r.second)
            video_file_name=left_video_file
        else:
            start_hhmmss=gen_hhmmss("right", offset, start_r.second)
            to_hhmmss=gen_hhmmss("right", offset, last_r.second)
            video_file_name=right_video_file
        #cmd1 = f"ffmpeg -ss {start_hhmmss} -to {to_hhmmss} -i {video_file_name}  -c copy part_to_be_replaced"
        watermark=""
        if logo_file_path_name: 
            watermark=f' -i {logo_file_path_name} -filter_complex "[1:v]scale=iw*0.25:-1[watermark];[0:v][watermark]overlay=10:main_h-overlay_h-10" '

        cmd1 =f"ffmpeg -ss {start_hhmmss} -to {to_hhmmss} -i {video_file_name}  {watermark} -r {fps} -vsync cfr -c:v libx264 -crf 23 -pix_fmt yuv420p -c:a aac part_to_be_replaced"

        return cmd1
    
    start_r, last_r=None, None  
    cmds=[]
    for r in mdf.itertuples():
        if start_r is None: 
            start_r, last_r=r, r 
            continue
        else: 
            if r.active_camera!=last_r.active_camera: 
                #need swtich. 
                cmds.append(gen_cmd(start_r, last_r))
                start_r, last_r=r, r 
            else:
                last_r=r 

    if start_r and last_r: 
        cmds.append(gen_cmd(start_r,last_r))       
    return cmds 

def gen_ffmpeg_extract_commands_with_pip(mdf,offset,left_video_file, right_video_file, fps=60, logo_file_path_name=None):
    def gen_cmd(start_r,last_r): 
        
        if start_r.active_camera=='left':
            start_hhmmss=gen_hhmmss("left", offset, start_r.second)
            to_hhmmss=gen_hhmmss("left", offset, last_r.second)
            video_file_name=left_video_file

            pip_start_hhmmss=gen_hhmmss("right", offset, start_r.second)
            pip_to_hhmmss=gen_hhmmss("right", offset, last_r.second)
            pip_video_file_name=right_video_file
        else:
            start_hhmmss=gen_hhmmss("right", offset, start_r.second)
            to_hhmmss=gen_hhmmss("right", offset, last_r.second)
            video_file_name=right_video_file
            
            pip_start_hhmmss=gen_hhmmss("left", offset, start_r.second)
            pip_to_hhmmss=gen_hhmmss("left", offset, last_r.second)
            pip_video_file_name=left_video_file
            
        # cmd1 = f"ffmpeg -ss {start_hhmmss} -to {to_hhmmss} -i {video_file_name}  -c copy part_to_be_replaced"
        # cmd2 = f"ffmpeg -ss {pip_start_hhmmss} -to {pip_to_hhmmss} -i {pip_video_file_name}  -c copy {start_r.active_camera}-part_to_be_replaced" 
        watermark=""
        if logo_file_path_name: 
            watermark=f' -i {logo_file_path_name} -filter_complex "[1:v]scale=iw*0.25:-1[watermark];[0:v][watermark]overlay=10:main_h-overlay_h-10" '
        #ffmpeg -ss 00:01:30 -to 00:02:45 -i input.mp4 -i watermark.png -filter_complex "[1:v]scale=main_w*0.15:-1[watermark];[0:v][watermark]overlay=main_w-overlay_w-10:10" -c:v libx264 -crf 23 -c:a aac output.mp4


        cmd1 = f"ffmpeg -ss {start_hhmmss} -to {to_hhmmss} -i {video_file_name}  {watermark} -r {fps} -vsync cfr -c:v libx264 -crf 23 -pix_fmt yuv420p -c:a aac part_to_be_replaced"
        cmd2 = f"ffmpeg -ss {pip_start_hhmmss} -to {pip_to_hhmmss} -i {pip_video_file_name} {watermark} -r {fps} -vsync cfr -c:v libx264 -crf 23 -pix_fmt yuv420p -c:a aac {start_r.active_camera}-part_to_be_replaced" 
        return (cmd1,cmd2)
    
    start_r, last_r=None, None  
    cmds=[]
    for r in mdf.itertuples():
        if start_r is None: 
            start_r, last_r=r, r 
            continue
        else: 
            if r.active_camera!=last_r.active_camera: 
                #need swtich. 
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

def post_process_extract_cmds_pip(extract_cmds, workspace_dir): 
    def rpl(index, cmd_pair): 
        c,c_pip=cmd_pair
        part=os.path.join(workspace_dir, f"part-{index}.MP4")
        c = c.replace('part_to_be_replaced', part)

        #for pip a bit tricky. 
        active_camera_and_place_holder=c_pip.split(" ")[-1]
        active_camera=active_camera_and_place_holder.split("-")[0]
        part=os.path.join(workspace_dir, f"pip-{active_camera}-part-{index}.MP4")
        c_pip = c_pip.replace(active_camera_and_place_holder, part)
        return c, c_pip
    extract_cmds= [rpl(i,c) for i, c in enumerate(extract_cmds) ]
    extract_cmds = list(chain.from_iterable(extract_cmds))
    text="\n".join(extract_cmds)
    with open(os.path.join(workspace_dir,'extract_part.sh'), 'w') as h: 
        h.write(text)
    
    return extract_cmds

def part_sort_key(fn):
            return int(fn.split(".")[0].split("-")[-1])


def gen_pip_command(part, pip_part, workspace_dir): 
    #get active camera first. 
    # pip-right-part-8.MP4
    active_camera=pip_part.split("-")[1]
    output_part = f"with_pip_{part}"
    
    # Top-Left Corneroverlay=10:10
    # Top-Right Corneroverlay=W-w-10:10
    # Bottom-Left Corneroverlay=10:H-h-10
    # Bottom-Right Corneroverlay=W-w-10:H-h-10
    
    #place the overlay on the top left, if active camera is right. 
    #position_directive="overlay=20:20"
    position_directive="overlay=W-w-10:H-h-10"
    # if active_camera=='left': 
    #     #then place the pip at the right top corner. 
    #     position_directive="overlay=W-w-20:20"

    part =os.path.join(workspace_dir, part)
    pip_part=os.path.join(workspace_dir, pip_part)
    output_file=os.path.join(workspace_dir,output_part)

    #get the active camera first.                            "[1:v]scale=iw/4:-1, pad=iw+20:ih+20:10:10:color=white[pip];[0:v][pip]overlay=20:20:ts_sync_mode=vfr" 
    #return  f'ffmpeg -i {part} -i {pip_part} -filter_complex "[1:v]scale=iw/4:-1[pip];[0:v][pip]{position_directive}:shortest=1" -c:a copy {output_file}'
    return  f'ffmpeg -i {part} -i {pip_part} -filter_complex "[1:v]scale=iw/4:-1,pad=iw+5:ih+5:2:2:color=greenyellow [pip];[0:v][pip]{position_directive}:shortest=1" -c:v libx264 -c:a copy {output_file}'
    


def gen_concat_command(workspace_dir, part_file_name_pattern, output_file_name_path): 
        part_list=list(fnmatch.filter(os.listdir(workspace_dir), part_file_name_pattern))
        part_list.sort(key=part_sort_key)
        list_file_name=os.path.join(workspace_dir, 'part-list.txt')
        with open(list_file_name, 'w') as h: 
            for p in part_list:
                h.write(f"file '{p}' \n")
        return   f"ffmpeg -f concat -safe 0 -i {list_file_name} -c copy {output_file_name_path}"

def gen_h265_encoding_cmd(input_vid, output_vid):
    return f"ffmpeg -i {input_vid} -c:v libx265 -vtag hvc1 -c:a copy -c:s copy {output_vid}"
