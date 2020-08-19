""" Add files that are on tape only to the NLA system so that requests for them to be restored can be made.

    This is to be run via cron.

    For each file on disk in filesets marked for archive on tape only:

        - Check that big enough and is not a link.
        - Add to the system to be verified.

    This is designed to be used via the django-extentions runscript command:

    ``$ python manage.py runscript move_files_to_nla``
"""
#
# SJP 2016-02-09

from nla_control.models import TapeFile
import os, sys
import requests
from nla_control.settings import *
import subprocess

__author__ = 'sjp23'

def get_filesets():
    """Get a list of filesets marked as candidates for tape storage only from the service provided by the
       cedaarchiveapp.

       :param: None
       :return: A list of filesets that are marked as tape storage only.
       :rtype: List[string]
    """
    # open download config - list os storage pots with logical paths
    filesets = requests.get(ON_TAPE_URL)

    filesets = map(lambda x: x.split()[2].strip(), filesets)
    return filesets

def run():
    """Function picked up by django-extensions. Runs the scan for matching filesets.

       :param: None
       :return: None
    """

    # First of all check if the process is running - if it is then don't start running again
    try:
        lines = subprocess.check_output(["ps", "-f", "-u", "badc"]).split("\n")
        n_processes = 0
        for l in lines:
            if "move_files_to_nla" in l and not "/bin/sh" in l:
                print(l)
                print("Process already running, exiting")
                n_processes += 1
    except:
        n_processes = 1

    if n_processes == 1:   # this process counts as one move_files_to_nla process

        filesets = get_filesets()
        for fs in filesets:
            for directory, dirs, files in os.walk(fs):
                for f in files:
                    path = os.path.join(directory, f)
                    try:
                        if os.path.islink(path):
                            print("Ignore Link:", path)
                            continue
                        if os.path.getsize(path) < MIN_FILE_SIZE:
                            print("Ignore Small:", path)
                            continue

                        print("Adding ", path)
                        TapeFile.add(path, os.path.getsize(path))
                    except:
                        print("Could not add ", path)
