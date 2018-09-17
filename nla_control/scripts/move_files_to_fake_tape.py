""" Move files in the test system from the "archive" on a *Partition* to another area
 of disc that emulates a tape system - fake tape!
 """
__author__ = 'dhk63261' # NRM

from nla_control.models import TapeFile
from nla_control.settings import *
import shutil
import os

def move_files_to_fake_tape(tapefiles):
    """
    **For each** file do the following:

       - Move the file to the faketape directory
       - Create symbolic link between the file in the faketape directory and the original file location

    Note that ``tidy_requests.py`` will set the status of these files to ONTAPE.

    :param QuerySet[TapeFile] tapefiles: QuerySet of TapeFiles that are in the test NLA system, with stage == ONDISK
        which will be moved to fake tape.
    """

    for f in tapefiles:

        # get the physical (not logical) storage location
        spot_logicalpath, spotname = f.spotname()
        total_storage_path = f.logical_path.replace(spot_logicalpath, f.storage_path())
        fname = total_storage_path.split("/")[-1]

        # move the physical file to the faketape - if it doesn't already exist there
        if not os.path.exists(FAKE_TAPE_DIR+"/"+fname):
            shutil.move(total_storage_path, FAKE_TAPE_DIR)
            # link the file back to the logical path
            os.symlink(FAKE_TAPE_DIR+"/"+fname, f.logical_path)


def run():
    """Entry point for the Django runscript.  Move files to fake tape area of disk."""
    TapeFile.load_storage_paths()

    if not os.path.exists(FAKE_TAPE_DIR):
        os.makedirs(FAKE_TAPE_DIR)
    files = TapeFile.objects.filter(stage=TapeFile.ONDISK)
    move_files_to_fake_tape(files)