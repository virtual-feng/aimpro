import logging
import fnmatch
import shutil
from pathlib import Path
import os 
from ml.detectors_v2 import ObjectDetector
from video.ffmpeg_wrapper import  extract_frames_from_synched_video
from multi_cam_switch.workspace import Workspace
import pandas as pd 
import numpy as np 
import glob
from common_utils import save_df

extract_fps=6
extract_img_fmt="jpg"
detection_chunk_size=64


def smooth_active_camera_index(ts, min_sequence_len=2): #2 means 1 second. 
    
    # Step 1: Compress array into explicit segments: [{'val': camera_id, 'len': frame_count}, ...]
    segments = []
    curr_val = ts[0]
    curr_len = 1
    
    for val in ts[1:]:
        if val == curr_val:
            curr_len += 1
        else:
            segments.append({'val': curr_val, 'len': curr_len})
            curr_val = val
            curr_len = 1
    segments.append({'val': curr_val, 'len': curr_len})
    
    # Step 2: Iteratively resolve segments shorter than the threshold
    changed = True
    while changed:
        changed = False
        for i in range(len(segments)):
            if segments[i]['len'] < min_sequence_len:
                has_left = i > 0
                has_right = i < len(segments) - 1
                
                if has_left and has_right:
                    left_valid = segments[i-1]['len'] >= min_sequence_len
                    right_valid = segments[i+1]['len'] >= min_sequence_len
                    
                    # Rule 1: Prioritise a valid neighbour over an invalid one
                    if left_valid and not right_valid:
                        target_idx = i - 1
                    elif right_valid and not left_valid:
                        target_idx = i + 1
                    else:
                        # Rule 2 & 3: Compare lengths. If equal, tie-break to the left (i-1)
                        if segments[i-1]['len'] >= segments[i+1]['len']:
                            target_idx = i - 1
                        else:
                            target_idx = i + 1
                elif has_left:
                    target_idx = i - 1
                elif has_right:
                    target_idx = i + 1
                else:
                    # Entire array is shorter than the threshold
                    break
                
                # Absorb the short segment's duration into the target neighbour
                segments[target_idx]['len'] += segments[i]['len']
                segments.pop(i)
                
                # Cleanup: Collapse adjacent segments that now share the same value
                j = 0
                while j < len(segments) - 1:
                    if segments[j]['val'] == segments[j+1]['val']:
                        segments[j]['len'] += segments[j+1]['len']
                        segments.pop(j+1)
                    else:
                        j += 1
                        
                changed = True
                break  # Restart scanning loop with updated segments
                
    # Step 3: Reconstruct the flat array from the smoothed segments
    smoothed_ac = []
    for seg in segments:
        smoothed_ac.extend([seg['val']] * seg['len'])
    return smoothed_ac

debug=False
class ClipPicker(): 
    def __init__(self, video_files,workspace):
        self.video_files=video_files
        self.workspace=workspace
        #model_path=os.path.join(os.getenv("ml_model_dir"),"yolo26-basketball-player-detection-model-small-test_v3_80_epochs.pt") 
        #model_path=os.path.join(os.getenv("ml_model_dir"),"yolo26-nano-basketball-player-808-imgsz-1280-epochs-120.pt")
        model_path=os.path.join(os.getenv("ml_model_dir"),"yolo26-nano-ball-player-imgsz-1280-epochs-120-bball-relabel.pt.pt")
        model_path=os.path.join(os.getenv("ml_model_dir"),"yolo26-p2-ball-player-imgsz-1280-epochs-150-ball-relabeled.pt")
        self.object_detector=ObjectDetector(model_path)
        logging.info(f"loaded ml model from  {model_path} ")
    
    def extract_frames(self): 
        file_name_pattern=f"%d.{extract_img_fmt}"
        for i, video_file  in enumerate(self.video_files): 
            ith_video_frame_dir=os.path.join(self.workspace.dir, f"frames_of_video_{i}")
            Path(ith_video_frame_dir).mkdir(parents=True, exist_ok=True)

            frames = list(fnmatch.filter(os.listdir(ith_video_frame_dir), f"*.{extract_img_fmt}") )    
            if not frames:
                ouput_path_pattern = os.path.join(ith_video_frame_dir, file_name_pattern)
                extract_frames_from_synched_video(video_file, extract_fps, ouput_path_pattern)
            else:
                logging.info(f"frames found, assume extraction has ever been done. ")
                return 
        
            def rename_img_file_to_s_ms(file_name):
                parts=file_name.split(".")
                file_index, ext=int(parts[0])-1, parts[1]
                s, index_in_second=divmod(file_index,extract_fps)
                ms=int(index_in_second*1000/extract_fps)
                new_file_name=f"{s}-{ms}.{ext}"
                shutil.move(os.path.join(ith_video_frame_dir, file_name), os.path.join(ith_video_frame_dir,new_file_name))
            
            frames = list(fnmatch.filter(os.listdir(ith_video_frame_dir), f"*.{extract_img_fmt}") )    
            [rename_img_file_to_s_ms(fn) for fn in frames]

    def detect_basketball_and_players(self):
        def detect(camera_index, video_file, video_frame_dir, csv_file_path_name,debug_image_dir=None): 
            files=fnmatch.filter(os.listdir(video_frame_dir), f"*.{extract_img_fmt}")
            df=pd.DataFrame(data=files, columns=["file_name"])
            df[f'video_file']=video_file
            df['chunk']=range(df.shape[0])
            df['chunk']=df.chunk//detection_chunk_size
            def detect_chunk(gdf):
                logging.info(f"object detection chunck : {gdf.name}")
                files=[os.path.join(video_frame_dir,f) for f in gdf.file_name] 
                results=self.object_detector.detect_objects_from_images(files, debug_output_dir=debug_image_dir)
                #raw_oput=[ObjectDetector.analyze_result(r) for r in results]
                raw_oput=[ObjectDetector.identify_ball_and_players_v2(r) for r in results]
                num_of_players, total_object_area, ball_bboxes= zip (*raw_oput)
                gdf['total_num_of_players']=num_of_players
                gdf['total_object_area']=total_object_area
                gdf['raw_ball_bboxes']=ball_bboxes
                return gdf 
            ret= df.groupby('chunk').apply(detect_chunk)
            ret.reset_index(inplace=True)

            # drop off bball false positives. 
            ret['ball_bboxes']=pd.Series(ObjectDetector.detect_and_remove_false_positive(ret.raw_ball_bboxes))
            ret['has_baseketball']=ret.ball_bboxes.apply(lambda blist: len(blist)>0)
            
            to_drop =[c for c in ret.columns if c.startswith("level_") or c=='chunk']
            ret.drop(columns=to_drop, inplace=True)

            cols_to_rename=[c for c  in ret.columns if c !='file_name']
            new_col_names =[f"{c}_{camera_index}" for c in cols_to_rename]
            ret.rename(columns = dict(zip(cols_to_rename, new_col_names)), inplace=True)

            def to_time_ms(s):
                parts = s.split(".")[0].split("-")
                s,ms = int(parts[0]), int(parts[1])
                return s*1000 +ms 
            ret.insert(loc=0, column=f"ms", value=df.file_name.apply(to_time_ms))

            ret = ret.sort_values(by='ms')
            save_df(ret, csv_file_path_name)
            #return ret
        frame_dirs =[f"frames_of_video_{i}" for i in range(len(self.video_files))]
        frame_dirs =[os.path.join(self.workspace.dir, fd) for fd in frame_dirs]
        trios = list(zip(self.video_files,  frame_dirs))
        
        for camera_index,(video_file,  frame_dir) in enumerate(trios): 
            debug_image_dir=None 
            if debug: 
                debug_image_dir=os.path.join(self.workspace.dir, "debug_images", os.path.split(frame_dir)[-1])
                Path(debug_image_dir).mkdir(parents=True, exist_ok=True)
            
            csv_file=os.path.join(self.workspace.dir,frame_dir, 'obj_dection_result.csv')

            if not os.path.exists(csv_file): 
                detect(camera_index, video_file,  frame_dir, csv_file,debug_image_dir)

    def detect_active_camera(self):
        def round_ms_to_half_second(ms):
            hs_2_ms=500
            s, only_ms= divmod(ms, hs_2_ms)
            only_ms=0 if only_ms<hs_2_ms else hs_2_ms 
            return s*hs_2_ms + only_ms
        
        def agg_to_half_seconds(df):
            df['ms_rounded']=df.ms.apply(round_ms_to_half_second)
            has_baseketball=[c for c in df.columns if c.startswith('has_baseketball')][0]
            total_num_of_players=[c for c in df.columns if c.startswith('total_num_of_players')][0]
            #has_possession=[c for c in df.columns if c.startswith('has_possession')][0]
            total_object_area=[c for c in df.columns if c.startswith('total_object_area')][0]
            video_file=[c for c in df.columns if c.startswith('video_file_')][0]
            file_name=[c for c in df.columns if c.startswith('file_name')][0]
            adf=df.groupby('ms_rounded').agg(
                {   
                    has_baseketball:'any',
                    total_num_of_players:'sum' ,
                    #has_possession:'any', 
                    total_object_area:'sum' , 
                    video_file:'first',
                    file_name:'first'
                 } 
            ).reset_index()
            df.sort_values(by='ms_rounded', inplace=True)
            return adf 
        result_files=glob.glob(f"{self.workspace.dir}/**/obj_dection_result.parquet", recursive=True)
        dfs =[]
        for f in result_files: 
            df=pd.read_parquet(f)
            df=agg_to_half_seconds(df)
            logging.info(f"aggregated df={df.shape}")
            dfs.append(df)
        mdf =pd.concat(dfs, axis=1)

        def active_camera_index(df): 
            # cols = [c for c in df.columns if c.startswith('has_baseketball_') ]
            # cols.sort(key=lambda x:x.split("_")[-1])
            # logging.info(f"cols={cols}")
            # h=df[cols].to_numpy()
            # logging.info(f"p={p.shape}")

            
            cols = [c for c in df.columns if c.startswith('total_num_of_players_') ]
            cols.sort(key=lambda x:x.split("_")[-1])
            logging.info(f"cols={cols}")
            p=df[cols].to_numpy()
            logging.info(f"p={p.shape}")

            cols = [c for c in df.columns if c.startswith('total_object_area_') ]
            cols.sort(key=lambda x:x.split("_")[-1])
            logging.info(f"cols={cols}")
            a=df[cols].to_numpy()
            logging.info(f"a={a.shape}")

            p_max = np.max(p, axis=1, keepdims=True)
            logging.info(f"p_max={p_max.shape}")

            is_p_max = (p == p_max)
            masked_a = np.where(is_p_max, a, -np.inf)
            logging.info(f"masked_a={masked_a.shape}")


            return pd.Series(np.argmax(masked_a, axis=1) )
        
        def active_camera_index_with_ball(df): 
            cols = [c for c in df.columns if c.startswith('has_baseketball_') ]
            cols.sort(key=lambda x:x.split("_")[-1])
            h=df[cols].to_numpy()
            
            cols = [c for c in df.columns if c.startswith('total_num_of_players_') ]
            cols.sort(key=lambda x:x.split("_")[-1])
            p=df[cols].to_numpy()
            
            cols = [c for c in df.columns if c.startswith('total_object_area_') ]
            cols.sort(key=lambda x:x.split("_")[-1])
            a=df[cols].to_numpy()
            
            only_one_has_ball = (h.sum(axis=1) == 1)
            r1_idx = np.argmax(h, axis=1)
    
            # Rule 2 & 3: Tie-breaking composite matrix
            a_min = a.min(axis=1, keepdims=True)
            a_max = a.max(axis=1, keepdims=True)
            a_range = a_max - a_min
            a_range[a_range == 0] = 1.0 
            a_normalized = (a - a_min) / a_range * 0.999999
            
            # Combined score ensures A2 dominates, and A3 breaks ties
            combined_score = p.astype(float) + a_normalized
            r23_idx = np.argmax(combined_score, axis=1)
            
            # Vectorized conditional merging based on the exact single True rule
            final_idx = np.where(only_one_has_ball, r1_idx, r23_idx)
            return pd.Series(final_idx.flatten() )
        
        def active_camera_index_with_ball_v2(df): 
            cols = [c for c in df.columns if c.startswith('total_num_of_players_') ]
            cols.sort(key=lambda x:x.split("_")[-1])
            p=df[cols].to_numpy()

            ols = [c for c in df.columns if c.startswith('has_baseketball_') ]
            cols.sort(key=lambda x:x.split("_")[-1])
            h=df[cols].to_numpy()
            
            cols = [c for c in df.columns if c.startswith('total_object_area_') ]
            cols.sort(key=lambda x:x.split("_")[-1])
            a=df[cols].to_numpy()
            
            
            # Rule 2 & 3: Tie-breaking composite matrix
            a_min = a.min(axis=1, keepdims=True)
            a_max = a.max(axis=1, keepdims=True)
            a_range = a_max - a_min
            a_range[a_range == 0] = 1.0 
            a_normalized = (a - a_min) / a_range * 0.999999
            # Combined score ensures A2 dominates, and A3 breaks ties
            combined_score = p.astype(float) + a_normalized
            
            true_counts = h.sum(axis=1)
            mask_exactly_one = (true_counts == 1)
            mask_multiple = (true_counts > 1)
            mask_zero = (true_counts == 0)
            
            final_idx = np.zeros(h.shape[0], dtype=int)
            
            # Tier 1: Exactly One True -> Get its index directly
            if np.any(mask_exactly_one):
                final_idx[mask_exactly_one] = np.argmax(h[mask_exactly_one], axis=1)
                
            # Tier 2: Multiple Trues -> Filter combined_score by A1's True positions, then take argmax
            if np.any(mask_multiple):
                # Mask out combined_score elements where A1 is False by setting them to negative infinity
                filtered_score = np.where(h, combined_score, -np.inf)
                final_idx[mask_multiple] = np.argmax(filtered_score[mask_multiple], axis=1)
                
            # Tier 3: Zero Trues -> Use global argmax of combined_score
            if np.any(mask_zero):
                final_idx[mask_zero] = np.argmax(combined_score[mask_zero], axis=1)

            #finally filter out timeout/break.
            no_player_mask=p<extract_fps/2 
            num_of_cameras_seeing_no_player=no_player_mask.sum(axis=1)
            total_num_of_cameras=p.shape[1]
            final_idx[num_of_cameras_seeing_no_player==total_num_of_cameras]=-1
            return pd.Series(final_idx.flatten() )
        

        mdf['raw_active_camera_index']=active_camera_index_with_ball_v2(mdf)
        
        #test timeout or quater break;
        # condition=True
        # cols = [c for c in df.columns if c.startswith('total_num_of_players_') ]
        # for c in cols: 
        #     #extract 2 frames/half second.  if all courts have less than 2 players , we believe it is timeout or break.
        #     condition=condition & (mdf[c]<extract_fps/2) 
        # mdf.loc[condition, 'raw_active_camera_index']=-1

        mdf['active_camera_index']=smooth_active_camera_index(mdf.raw_active_camera_index, min_sequence_len=4) #at leat 2 seconds. 
        
        # Keeps the first 'file_name' column and removes the rest
        mdf = mdf.loc[:, ~mdf.columns.duplicated()]
        
        #because we merge dfs with 'concat', not 'merge' or join. 
        #the left side and right might not have same shape. 
        mdf = mdf.loc[mdf.ms_rounded.notnull()]
        save_df(mdf, os.path.join(self.workspace.dir, "merged_obj_dection_result.csv"))
        

    def process(self): 
        self.extract_frames()       
        self.detect_basketball_and_players()
        self.detect_active_camera()
        #df = self.detect_active_camera(df)
         

if __name__ == "__main__":
    from dotenv import load_dotenv
    from common_utils import setup_logger
    import argparse
    def analyze_args():
        parser = argparse.ArgumentParser()
        parser.add_argument("-r", "--root_folder", type=str,   help="the root dir of all video files, optional.")
        parser.add_argument("-v", "--video_files", nargs="+" , type=str,   help="video files from 2 or more camerasl. If root_folder specified, we assume all video files are under the same root folder.")
        return parser.parse_args()
    
    script_name = Path(__file__).name
    installation_dir=Path(__file__).resolve().parent.parent.parent
    load_dotenv(dotenv_path=os.path.join(installation_dir,'.env'))
    setup_logger('INFO')
    args = analyze_args()
    wsp = Workspace(script_name)
    
    video_files = args.video_files
    if len(video_files)<2: 
        print (f"please provide at least two  video files.")
        exit(0)

    if args.root_folder: 
        video_files=[os.path.split(v)[-1] for v in video_files]
        video_files=[os.path.join(args.root_folder, v) for v in video_files]
    cp =ClipPicker(video_files, wsp )
    cp.process()
