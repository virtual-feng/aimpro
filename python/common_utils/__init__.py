import logging
import sys
import datetime
import subprocess

def setup_logger(log_level, log_file=None):
    logger=logging.getLogger()

    for handler in logger.handlers:
        logger.removeHandler(handler)
    
    f=logging.Formatter('%(asctime)s\t%(name)s\t %(levelname)s\t%(module)s\t%(funcName)s\t%(message)s')
    
    h=logging.StreamHandler(sys.stdout)
    if log_file: 
        h=logging.FileHandler(log_file, encoding='utf-8')

    h.setFormatter(f)
    l=logging.getLogger()
    l.setLevel(log_level)
    l.addHandler(h)

def call_command_line(cmd_line):
    logging.info(f"start run : {cmd_line}")
    process=subprocess.Popen(cmd_line,
                         stdin=None,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         universal_newlines=True,
                         text=True, 
                         bufsize=0,
                         shell=True)
    stdout, stderr = process.communicate()
    if stderr:
        logging.error(stderr)
    logging.info(f"end run : {cmd_line}")
    return stdout, stderr

if __name__ == "__main__":
    import argparse
    setup_logger('INFO')
    stdout, stderror = call_command_line("ls -latr")
    print("----------------stdout------------------")
    print(stdout)
    print("----------------stderror------------------")
    if stderror: 
        print(stderror)
    else: 
        print("stderror is None ")
        
    stdout, stderror = call_command_line("Bla Bal")
    print("----------------stdout------------------")
    print(stdout)
    print("----------------stderror------------------")
    print(stderror)
    

