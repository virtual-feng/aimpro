
def encode_cmd_options(output_fps, output_video_file_name):
    return f"-r {output_fps} -vsync cfr -c:v libx264 -crf 23 -pix_fmt yuv420p -c:a aac {output_video_file_name}"

def cut_encode_cmd(source_video_file_name, start_hhmmss, to_hhmmss, output_video_file_name,output_fps=60): 
     encode = encode_cmd_options(output_fps, output_video_file_name)
     return f'ffmpeg -ss {start_hhmmss} -to {to_hhmmss} -i {source_video_file_name} {encode}'

def to_one_line(s):
    lines = s.splitlines()
    lines = [l.strip() for l in lines ]
    lines =[l for l in lines if len(l)>0]
    return " ".join(lines)

def cut_watermark_encode_cmd(source_video_file_name, logo_file_path_name, start_hhmmss, to_hhmmss, output_video_file_name,output_fps=60): 
    overlay_directive="overlay=10:main_h-overlay_h-10" 
    encode = encode_cmd_options(output_fps, output_video_file_name)
    ret= f"""
        ffmpeg -ss {start_hhmmss} -to {to_hhmmss} -i {source_video_file_name} 
        -i {logo_file_path_name}  
        -filter_complex "[1:v]scale=iw*0.2:-1[watermark];[0:v][watermark]{overlay_directive}" 
        {encode} 
    """
    return to_one_line(ret)
def cut_pip_encode_cmd( main_video_file, start_hhmmss, duration, 
                        pip_video_file, pip_start_hhmms,
                        output_video_file_name,output_fps=60):
    overlay_directive="overlay=W-w-10:H-h-10:shortest=1"
    encode = encode_cmd_options(output_fps, output_video_file_name)
    ret =  f"""
        ffmpeg 
        -ss {start_hhmmss} -t {duration} -vsync 1 -i {main_video_file} 
        -ss {pip_start_hhmms} -t {duration} -vsync 1 -i {pip_video_file} 
        -filter_complex "[1:v]scale=iw/4:-1,pad=iw+5:ih+5:2:2:color=greenyellow [pip];[0:v][pip]{overlay_directive}"  
        {encode}
    """
    return to_one_line(ret)
def cut_watermark_pip_encode_cmd( 
                        main_video_file, start_hhmmss, duration, 
                        pip_video_file, pip_start_hhmms,
                        logo_file_path_name,
                        output_video_file_name,output_fps=60):
    pip_overylay_directive="overlay=W-w-10:H-h-10:shortest=1"
    wm_overylay_directive="overlay=10:main_h-overlay_h-10"
    encode = encode_cmd_options(output_fps, output_video_file_name)
    ret= f"""
        ffmpeg 
        -ss {start_hhmmss} -t {duration} -vsync 1 -i {main_video_file} 
        -ss {pip_start_hhmms} -t {duration} -vsync 1 -i {pip_video_file}  
        -i {logo_file_path_name} 
        -filter_complex 
        "[1:v]scale=iw/4:-1,pad=iw+5:ih+5:2:2:color=greenyellow [pip_scaled]; 
        [2:v]scale=iw*0.2:-1[wm_scaled]; 
        [0:v][pip_scaled]{pip_overylay_directive}[base_with_pip]; 
        [base_with_pip][wm_scaled]{wm_overylay_directive}" 
        {encode}
    """
    return to_one_line(ret)

def h265_encoding_cmd(input_vid, output_vid):
    return f"ffmpeg -i {input_vid} -c:v libx265 -vtag hvc1 -c:a copy -c:s copy {output_vid}"
