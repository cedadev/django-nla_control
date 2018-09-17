__author__ = 'sjp23'

# verify files on storage-D

from nla_control.models import TapeFile, TapeRequest, Quota
import glob
import pytz
import os
import datetime
import subprocess
import sys
from nla_control.settings import *

# load storage paths to do path translation to from logical to storage paths.
TapeFile.load_storage_paths()

def _run_test():
    files = TapeFile.objects.filter(stage=TapeFile.UNVERIFIED)
    for f in files:
        # v = storaged_verify(f.logical_path)
        # if v > f.logical_path  :
        #     f.stage=TapeFile.ONDISK
        #     f.save()
        pass
        # temporarily make just assume verified
        f.stage = TapeFile.ONDISK
        f.verified = datetime.datetime.now()
        f.save()

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
                      Make a table with entries so that logical paths  i.e
                      the file containing full paths that a user would reference, are
                      converted to spot name paths which are more easy to manipulate
                      under the current processing scheme.
                      A user would reference a file with the path ``/badc/faam`` for
                      instance which really points to the spot
                      ``/badc/faam -> /datacentre/archvol/pan23/archive/faam``. The latter
                      is the value we will use to reference any files.

                      Now check to see if the file in the list has a check sum in
                      the associated checksum files. Output and appropriate
                      message with each of the filenames.
        """


    files = TapeFile.objects.filter(stage=TapeFile.UNVERIFIED)
    print "Number of UNVERIFIED files: " + str(len(files))

    if "verify_now" in args:
        verify_now = True
    else:
        verify_now = False

    # HISTORY: Inception 20151103 BC

    # create CHKSUMDIR if not exist
    if not os.path.exists(CHKSUMSDIR):
        os.makedirs(CHKSUMSDIR)

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
    tape_request = TapeRequest(quota=quota, retention=retention, storaged_request_start=now, storaged_request_end=now,
                               first_files_on_disk=now, last_files_on_disk=now, label="FROM VERIFY PROCESS")
    tape_request.save()

    # Now check to see if the files exist in any of the associated
    # check sum listings held in directory CHKSUMSDIR
    #
    num_verified_files = 0

    for f in files:
        spot_logical_path, spot_name = f.spotname()
        file_path = f.logical_path
        if TEST_VERSION:
            to_find = file_path     # test version verification is just calculate insitu
        else:
            to_find = file_path.replace(spot_logical_path, "/datacentre/restorecache/archive/%s" % spot_name)

        # find all log files
        restore_log_files = glob.glob(CHKSUMSDIR + "/%s.chksums.*" % spot_name)

        # if there are no log files then go to next file
        if len(restore_log_files) == 0:
       	    print ("Restore log files not found: " + str(restore_log_files))
            continue

        # A problem here is that there may be more than one restore_log file for each file_set
        # due to the verify process restarting
        # To account for this we do the following:
        # 1. sort the restore log files that match the glob pattern on the date embedded in their filename
        # 2. step through the log files, most recent first
        # 3. If we find the file then we exit is already verified then we exit
        restore_log_files.sort()
        file_found = False

        for restore_log in restore_log_files:
            # look for file in restore checksums logs
            for line in open(restore_log):
                # get the checksum and filename
                strip_line = line.strip().split()
                if len(strip_line) < 2:
                    print ("Could not read line in restore log file correctly {} {}".format(line, restore_log))
                    continue
                checksum = strip_line[0]
                filename = strip_line[1]
                # if the filename matches the required filename
                if filename == to_find:
                    # set stage to ONDISK, set verification date
                    f.stage = TapeFile.ONDISK
                    f.verified = now
                    f.save()
                    # add the request files to the tape request
                    tape_request.request_files += f.logical_path + "\n"
                    # increment the number of verified files and indicate that the file is found
                    num_verified_files += 1
                    file_found = True
                if file_found:
                    break
            if file_found:
                break

    # if no files don't keep the tape request
    if num_verified_files == 0:
        tape_request.delete()
    else:
        tape_request.save()
