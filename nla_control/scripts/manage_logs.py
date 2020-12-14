# manage the logs in the directory /var/log/nla/

from pathlib import Path
import os
import subprocess
from datetime import datetime

# minimum size = 500 bytes
MIN_SIZE = 500

# time before logs get zipped
ZIP_TIME = 1

# maximum length of time persistant = 7 days
MAX_PERSISTANCE = 7

# log directory
LOG_DIR = "/var/log/nla"

def run(*args):    
    if "dry_run" in args:
        DRY_RUN = True
    else:
        DRY_RUN = False

    # list the log directory
    log_path = Path(LOG_DIR)

    # delete small
    for f in log_path.glob("*.log"):
        # get the file info
        finfo = f.stat()
        # delete the small logs
        if (finfo.st_size < MIN_SIZE):
            print("Deleting log file {} due to small size {}".format(f, finfo.st_size))
            if not DRY_RUN:
                os.unlink(f)

    # gzip
    for f in log_path.glob("*.log"):
        # check the mtime
        finfo = f.stat()
        now = datetime.now()
        file_time = datetime.fromtimestamp(finfo.st_mtime)
        days_old = (now - file_time).days
        if days_old >= ZIP_TIME:
            print("Gzipping log file {} due to age {} days".format(f, days_old))
            if not DRY_RUN:
                subprocess.run(["gzip", f])

    # delete gzipped
    for f in log_path.glob("*.log.gz"):
        # check the mtime
        finfo = f.stat()
        now = datetime.now()
        file_time = datetime.fromtimestamp(finfo.st_mtime)
        days_old = (now - file_time).days
        if days_old >= MAX_PERSISTANCE:
            print("Deleting log file {} due to age {} days".format(f, days_old))
            if not DRY_RUN:
                os.unlink(f)
