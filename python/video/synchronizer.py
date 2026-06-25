import librosa
import os 
import shutil
import logging
import numpy as np 

from video.ffmpeg_wrapper import extract_audio

import math 
def format_seconds_to_hhmmss(seconds):
    #seconds is float number, it might have decimal part. 
    decimal_part, integer_part = math.modf(seconds)
    ms, seconds = int(decimal_part*1000), int(integer_part) 
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    ret =  f"{hours:02}:{minutes:02}:{seconds:02}"
    if decimal_part>0: 
        ret =f"{ret}.{ms:03}"
    return ret 



def find_offset_seconds(workspace_dir,v_a, v_b, sample_rate=16000):
    video_a_name, video_b_name=os.path.split(v_a)[-1], os.path.split(v_b)[-1]
    audio_a_temp_file=os.path.join(workspace_dir, f"{video_a_name}.mp3")
    audio_b_temp_file=os.path.join(workspace_dir, f"{video_b_name}.mp3")
    extract_audio(v_a, audio_a_temp_file)
    extract_audio(v_b, audio_b_temp_file)
    
    try: 
        audio_a, _ =librosa.load(audio_a_temp_file, sr=sample_rate, mono=True)
        audio_b, _ =librosa.load(audio_b_temp_file, sr=sample_rate, mono=True)

        logging.info(f"audio_a={audio_a.shape}, audio_b={audio_b.shape}")
        
        length=min(len(audio_a), len(audio_b))
        a=audio_a[:length]
        b=audio_b[:length]

        fa,fb=np.fft.rfft(a, n=2*length), np.fft.rfft(b, n=2*length)
        corr=np.fft.irfft(fa* np.conj(fb))
        corr=np.concatenate([corr[length:], corr[:length]])

        peak=int(np.argmax(np.abs(corr)))-length

        offset=peak/sample_rate
        if offset >0: 
            meaning=f"video A started {offset} earlier than video B."
        else: 
            meaning=f"video B started {offset*-1} earlier than video A."
        #if offset >0, then A Start Earlier ; 
        #elif offset <0, then B Start Earlier. 
        return offset , meaning
    
    finally:
        if os.path.exists(audio_a_temp_file):
            os.remove(audio_a_temp_file)
        if os.path.exists(audio_b_temp_file):
            os.remove(audio_b_temp_file)



def align_two_videos(v_a, v_b,  out_a, out_b,  sample_rate=16000):
    offset = find_offset_seconds(v_a, v_b, sample_rate)    
    
    if offset>0: 
        # B start later than , then we need trim A; 
        trim_video(v_a, out_a, offset)
            
            #simply copy b : 
        shutil.copyfile(v_b, out_b)
    elif offset <0: 
            # B start early than A, then trim B
        trim_video(v_b, out_b, -offset)
        shutil.copyfile(v_a, out_a)
    else: 
        shutil.copyfile(v_a, out_a)
        shutil.copyfile(v_b, out_b)
    

        


        
        
    