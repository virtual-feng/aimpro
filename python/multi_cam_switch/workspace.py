import os 
from pathlib import Path
import shutil
import logging


installation_dir=Path(__file__).resolve().parent.parent.parent
resource_dir=os.path.join(installation_dir, 'resources')

class Workspace(): 
    def __init__(self, app_name):
        pid=os.getpid()
        appdir=os.path.join(os.getenv('tmp_dir'), app_name) 
        Path(appdir).mkdir(parents=True,exist_ok=True)
        previous_pids = os.listdir(appdir)
        if len(previous_pids)>0: 
            last_pid=previous_pids[0]
            logging.info(f"resume the last job {last_pid}")
            self.dir=os.path.join(appdir, f"{last_pid}")    
        else: 
            self.dir=os.path.join(appdir, f"{pid}")
        Path(self.dir).mkdir(parents=True,exist_ok=True)

        #finally , copy logo. 
        logo_file_path_name=os.path.join(resource_dir, "your-court-vision-light-blue.png")
        self.logo_file_path_name=os.path.join(self.dir, "your-court-vision.png")
        shutil.copy(logo_file_path_name, self.logo_file_path_name)
        logging.info(f"workspace {self.dir} created")

    def remove_workspace(self):
        shutil.rmtree(self.dir)
        logging.info(f"workspace {self.dir} deleted")
