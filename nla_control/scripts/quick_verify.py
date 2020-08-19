__author__ = 'sjp23'

# verify files on storage-D

import glob
import pytz
import os
import datetime
import subprocess
import sys
import json

from django.db.models import Q

from nla_control.models import TapeFile, TapeRequest, Quota
from nla_control.settings import *

# load storage paths to do path translation to from logical to storage paths.
print("Loading storage paths...")
TapeFile.load_storage_paths()
print("...done")

def run(*args):

    """Entry point for the Django script run via ./manage.py in the Django project directory

       :param \*args: additional arguments to the script, see below
       :return: None

       :Script arguments:
           * *verify_now* -- set the retention time to be now

       **Purpose**:
                    Script to check from a list of files which files have associated check
                    sums that have been calculated via the normal backup validation process.

       **Algorithm**:
                    This checks the UNVERIFIED files to find those that belong
                    to sentinel1 or sentinel2, and they are verified quickly by
                    just checking to see if the file exists on the tape
        """
    # First of all check if the process is running - if it is then don't start running again
    try:
        lines = subprocess.check_output(["ps", "-f", "-u", "badc"]).split("\n")
        n_processes = 0
        for l in lines:
            if "quick_verify" in l and "manage.py" in l:
                print(l)
                n_processes += 1
    except:
        n_processes = 1

    if n_processes > 1:
        print("Process already running, exiting")
        sys.exit()

    # open the JSON file containing the directories to match against
    with open("/usr/local/nla_server/NLA/nla_control/scripts/quick_verify_files.json") as fh:
        lpath_json = json.load(fh)

    # build a Q query with each logical path mapping
    query = Q(stage=TapeFile.UNVERIFIED)
    # add the lpaths
    for lpath in lpath_json["match_logical_path"]:
        query = query | Q(logical_path__contains=lpath)

    # limit each batch to 100,000 files to remove
    files = TapeFile.objects.filter(query)[:100000]
    print("Number of UNVERIFIED files that can be quick verified: " +
          str(len(files)))

    if "verify_now" in args:
        verify_now = True
    else:
        verify_now = False

    # make a tape file request so all verified files belong to a request. This request
    # belongs to the _VERIFY quota.
    quota = Quota.objects.filter(user="_VERIFY")
    if len(quota) == 0:
        quota = Quota(user="_VERIFY", size=10000000000000, notes="System quota for requests from tidying.")
        quota.save()
    else:
        quota = quota[0]

    now = datetime.datetime.now(pytz.utc)
    if verify_now:
        retention = now
    else:
        retention = now + datetime.timedelta(days=20)

    tape_request = TapeRequest(quota=quota, retention=retention,
                               storaged_request_start=now,
                               storaged_request_end=now,
                               first_files_on_disk=now, last_files_on_disk=now,
                               label="FROM QUICK_VERIFY PROCESS")
    tape_request.save()

    # Now check to see if the files exist on the tape, using sd_ls
    num_verified_files = 0
    # spot lists
    spot_lists = {}

    for f in files:
        spot_logical_path, spot_name = f.spotname()
        # if the spot_name is not in the spot_lists then do a sd_ls
        if not spot_name in spot_lists:
            print("Building spot name list for " + spot_name)
            spot_lists[spot_name] = []
            sd_cmd = ["/usr/bin/python2.7", "/usr/bin/sd_ls", "-s", spot_name, "-L", "file"]
            try:
                output = subprocess.check_output(sd_cmd)
       	    except subprocess.CalledProcessError:
       	       	print("Spot name: {} not found by sd_ls".format(spot_name))
       	       	continue
            out_lines = output.split("\n")
            for out_item in out_lines:
                out_file = out_item.split()
                if len(out_file) == 11:
                    file_name = out_file[10]
                    size = out_file[1]
                    status = out_file[2]
                    if status == "TAPED" and size != 0:
                        spot_lists[spot_name].append(file_name)
                    
        file_path = f.logical_path
        if TEST_VERSION:
            to_find = file_path     # test version verification is just
                                    # calculate insitu
        else:
            to_find = file_path.replace(
                spot_logical_path, "/archive/%s" % spot_name
            )

        if to_find in spot_lists[spot_name]:
            tape_request.request_files += file_path + "\n"
            num_verified_files += 1


    # if no files don't keep the tape request
    if num_verified_files == 0:
        tape_request.delete()
    else:
        tape_request.save()
