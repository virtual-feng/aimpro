import os 
from dotenv import load_dotenv
from pathlib import Path
import shutil
from ml.detectors_v2 import ObjectDetector
import pandas as pd 
import fnmatch
import logging
from ml.detectors_v2 import ObjectDetector
import pandas as pd 
import yaml
    
script_name = Path(__file__).name
installation_dir=Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=os.path.join(installation_dir,'.env'))


def prelabel_with_ml(root_dir, model_file_path_name):
    #assume image files are under root_dir/images
    raw_frames=glob.glob(f"{root_dir}/images/*.jpg")
    raw_frames_with_bbox=os.path.join(root_dir, "images_with_bbox")
    Path(raw_frames_with_bbox).mkdir(parents=True, exist_ok=True)
    

    df=pd.DataFrame(data=raw_frames, columns=["frame_file"])
    df['page']=pd.Series(range(df.shape[0]))//60
    

    detector = ObjectDetector(model_file_path_name)
    def detect(gdf):
        gdf['label']=detector.detect_objects_from_images(gdf.frame_file, debug_output_dir=raw_frames_with_bbox)
        
        for l in gdf.label: 
            num_of_balls, num_of_players , _ = ObjectDetector.identify_ball_and_players(l)
            logging.info(f"found {num_of_balls} balls and {num_of_players} players ")    
        
        logging.info(gdf.shape)
        return gdf 
    df_with_label=df.groupby('page').apply(detect)
    df_with_label.reset_index(inplace=True)
    
    labels_dir=os.path.join(root_dir, "labels")
    shutil.rmtree(labels_dir)
    Path(labels_dir).mkdir(parents=True, exist_ok=True)
    
    def save(row): 
        frame_file_name=row['frame_file']
        label=row['label']
        file_name =Path(frame_file_name).stem
        label_file_name=os.path.join(root_dir, "labels", f"{file_name}.txt")
        label.save_txt(label_file_name)
    df_with_label.apply(save, axis=1)
    df_with_label.to_csv(os.path.join(root_dir,"prelabel_with_ml.csv"), index=False)

def save_lb_export(root_dir, label_csv, label_dir): 
    lb_exported_lables_dir=os.path.join(root_dir, 'labels_exported_from_lb_studio')
    Path(lb_exported_lables_dir).mkdir(parents=True, exist_ok=True)
    lbdf=pd.read_csv(label_csv)
    def related_image_file_name(image):
        return image.split("/")[-1].split('.')[0]
    lbdf['image_file_name']=lbdf.image.apply(related_image_file_name)
    labels_exported_from_studio=[f"{n}.txt" for n in lbdf.image_file_name]
    src_files=[os.path.join(label_dir,  f) for f in labels_exported_from_studio]
    tgt_files=[os.path.join(lb_exported_lables_dir, f) for f in labels_exported_from_studio]
    for s, t in dict(zip(src_files, tgt_files)).items(): 
        logging.info(f"copy {s} to {t}")
        shutil.copy(s,t)

def create_traning_set(root_dir,training_set_name): 
    lb_exported_lables_dir=os.path.join(root_dir, 'labels_exported_from_lb_studio')
    traning_dataset_folder=os.path.join(root_dir, training_set_name)
    Path(traning_dataset_folder).mkdir(parents=True, exist_ok=True)
    tr_images, tr_labels=os.path.join(traning_dataset_folder,'train', 'images'), os.path.join(traning_dataset_folder,'train', 'labels')
    te_images, te_labels=os.path.join(traning_dataset_folder,'test', 'images'), os.path.join(traning_dataset_folder,'test', 'labels')
    va_images, va_labels=os.path.join(traning_dataset_folder,'valid', 'images'), os.path.join(traning_dataset_folder,'valid', 'labels')
    Path(tr_images).mkdir(parents=True, exist_ok=True)
    Path(tr_labels).mkdir(parents=True, exist_ok=True)
    Path(te_images).mkdir(parents=True, exist_ok=True)
    Path(te_labels).mkdir(parents=True, exist_ok=True)
    Path(va_images).mkdir(parents=True, exist_ok=True)
    Path(va_labels).mkdir(parents=True, exist_ok=True)

    #get all labels. 
    labels=list(fnmatch.filter(os.listdir(lb_exported_lables_dir), "*.txt"))
    images=[l.replace(".txt", ".jpg") for l in labels]
    labels=[os.path.join(lb_exported_lables_dir, l) for l in labels]
    images=[os.path.join(root_dir, 'images' , i) for i in images]
    df=pd.DataFrame(data={
        "label":labels, 
        "image":images
    })

    #shuffle df first. 
    df=df.sample(frac=1, random_state=42)
    train_df = df.sample(frac=0.7, random_state=42)
    train_df['purpose']='train'
    logging.info(f"train_df: {train_df.shape}")
    
    rest_df = df.drop(train_df.index)
    test_df=rest_df.sample(frac=0.5, random_state=42)
    test_df['purpose']='test'
    logging.info(f"test_df: {test_df.shape}")
    

    val_df=rest_df.drop(test_df.index)
    val_df['purpose']='valid'
    logging.info(f"val_df: {val_df.shape}")
    
    
    def copy_row(row): 
        purpose, image, label=row['purpose'], row['image'], row['label']
        if purpose=="train": 
            shutil.copy(image, os.path.join(tr_images, os.path.split(image)[-1]))
            shutil.copy(label, os.path.join(tr_labels, os.path.split(label)[-1]))
        elif purpose=="test": 
            shutil.copy(image, os.path.join(te_images, os.path.split(image)[-1]))
            shutil.copy(label, os.path.join(te_labels, os.path.split(label)[-1]))
        else:
            shutil.copy(image, os.path.join(va_images, os.path.split(image)[-1]))
            shutil.copy(label, os.path.join(va_labels, os.path.split(label)[-1]))
    train_df.apply(copy_row, axis=1)
    test_df.apply(copy_row, axis=1)
    val_df.apply(copy_row, axis=1)
    
    data={
        "train":"/absolute_path_to/train/images",
        "val":"/absolute_path_to/valid/images",
        "test":"/absolute_path_to/test/images",
        "nc":2,
        "names":['ball', 'player']
    }
    with open(os.path.join(traning_dataset_folder, 'data.yaml'),  "w") as file:
        yaml.dump(data, file,   default_flow_style=False, sort_keys=False)
    
    print(f"cd to {root_dir} , then manually zip : zip -r {training_set_name}_dataset.zip {training_set_name}")



def prepare_data_set_for_lb_studio(root_dir):
    #assume image files are under root_dir/raw_mages
    #ML prelabels are under root_dir/labels
    
    #produce classes.txt 
    #hard code for now, will read from ml out later. 
    object_types=['ball','player']
    with open(os.path.join(root_dir, "classes.txt"), 'w') as h: 
        h.write('\n'.join(object_types))
    
    #create the sh script to run convert.
    script=f"""
cd {root_dir}
label-studio-converter import yolo -i {root_dir}  -o {root_dir}/labels_to_be_imported_to_studio.json --image-root-url "/data/local-files/?d=images"
""" 
    with open(os.path.join(root_dir, "convert_to_lb_studio_annotation.sh"), 'w') as h: 
        h.write(script) 

    script=f"""
cd {root_dir}
export DATA_UPLOAD_MAX_NUMBER_FILES=10000
export LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=$(pwd)
export LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true
label-studio
""" 
    with open(os.path.join(root_dir, "start_lb_studio.sh"), 'w') as h: 
        h.write(script) 



    print("please activate right conda env , and  manually run 'bash convert_to_lb_studio_annotation.sh' ")
    print("then manually run 'bash start_lb_studio.sh' ")
    

import argparse
def analyze_args():
    parser = argparse.ArgumentParser()
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    prelabel = subparsers.add_parser("prelabel", help="run ml models to pre-label data.")
    prelabel.add_argument("-r", "--root_dir" , help="the vid file ")
    prelabel.add_argument("-m", "--model_file" , help="the vid file ")

    convert = subparsers.add_parser("tostudio", help="convert ml output to label studio annotation.")
    convert.add_argument("-r", "--root_dir" , help="the vid file ")
    
    save_export = subparsers.add_parser("save_export", help=".")
    save_export.add_argument("-r", "--root_dir" , help="the vid file ")
    save_export.add_argument("-c", "--label_csv" , help=" ")
    save_export.add_argument("-d", "--label_dir" , help=" ")
    
    package_training_set = subparsers.add_parser("package", help=".")
    package_training_set .add_argument("-r", "--root_dir" , help="the vid file ")
    package_training_set .add_argument("-n", "--training_set_name" , help=" ")
    
    
    return parser.parse_args()
    
if __name__ == "__main__":
    from common_utils import setup_logger
    from datetime import datetime
    import glob 
    log_dir=os.getenv('log_dir')
    #setup_logger('INFO', log_file=os.path.join(log_dir, f"{script_name}.log"))
    setup_logger('INFO')
    args = analyze_args()

    if args.command == "prelabel": 
        model_path_file_name=os.path.join(os.getenv('ml_model_dir'), args.model_file)
        prelabel_with_ml(args.root_dir, model_path_file_name)

    elif args.command == "tostudio": 
         prepare_data_set_for_lb_studio(args.root_dir)

    elif args.command =='save_export': 
        save_lb_export(args.root_dir, args.label_csv, args.label_dir)

    elif args.command =='package': 
        create_traning_set(args.root_dir, args.training_set_name)




    