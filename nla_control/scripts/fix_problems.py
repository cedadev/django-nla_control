""" Fix some problems that can occur with the NLA

 This is designed to be used via the django-extensions runscript command:

 ``$ python manage.py runscript fix_problems``

"""
#
# import nla objects
from nla_control.models import *
from nla_control.settings import *
import nla_control
import os
import re
import datetime
import glob
from pytz import utc
from django.db.models import Q
import requests
import subprocess

def clear_slots():
    """Remove all tasks from the slots directory"""
    for slot in StorageDSlot.objects.all():
        # reset slot
        slot.pid = None
        slot.host_ip = None
        slot.tape_request = None
        slot.save()

def set_restoring_files_to_ontape():
    """Set all files that are stuck in a "RESTORING" state to "ONTAPE"
    """
    files = TapeFile.objects.filter(stage=TapeFile.RESTORING)
    for f in files:
        l_path = f.logical_path
        if not(os.path.exists(l_path)):
            print "Resetting file " + l_path + " to ONTAPE"
            f.stage = TapeFile.ONTAPE
            f.save()


def reset_stuck_taperequests():
    """Reset the taperequests that are stuck with a storageD request start and a no storageD request end
    """
    taperequests = TapeRequest.objects.filter(active_request=True, storaged_request_end=None).exclude(storaged_request_start=None)
    for tr in taperequests:
        print "Resetting request: " + tr.label
        tr.storaged_request_start = None
        tr.active_request = False
        tr.save()


def deactivate_taperequests():
    taperequests = TapeRequest.objects.filter(active_request=True)
    for tr in taperequests:
        print "Deactivate request: " + tr.label
        tr.active_request = False
        tr.save()


def get_spot_to_logical_path_mapping():
    # get the URL and download the mapping
    response = requests.get(CEDA_DOWNLOAD_CONF)
    if response.status_code != 200:
        raise Exception("Cannot find url: {}".format(CEDA_DOWNLOAD_CONF))
    else:
        page = response.text.split("\n")
    spot_to_logical_path_map = {}

    # make a dictionary that maps logical paths to spot names
    for line in page:
        line = line.strip()
        if line == '':
            continue
        spot_name, logical_path = line.split()
        spot_to_logical_path_map[spot_name] = logical_path
    return spot_to_logical_path_map


def fix_symbolic_links():
    # loop over all the target disks looking for log files
    for td in RestoreDisk.objects.all():
        files = os.listdir(td.mountpoint)
        for f in files:
            if "retrieve_log" in f:
                log_file_name = os.path.join(td.mountpoint + "/" + f)
                log_file = open(log_file_name)
                lines = log_file.readlines()
                for line in lines:
                    # look for line with right pattern to know its finished
                    m = re.search('Saving (.*) into local file (.*)', line)
                    if m:
                        restored_archive_file_path = m.groups()[0]
                        local_restored_path = m.groups()[1]
                        fname = restored_archive_file_path.split("/")[-1]
                        # find the logical path
                        f = TapeFile.objects.filter(logical_path__contains=fname)
                        if len(f) == 0:
                            continue
                        else:
                            f = f[0]
                        # link file to final archive location
                        print local_restored_path, f.logical_path
                        if not os.path.exists(f.logical_path):
                            # os.path.exists returns false for broken links so delete the link
                            if os.path.islink(f.logical_path):
                               os.unlink(f.logical_path)
                            os.symlink(local_restored_path, f.logical_path)
                            f.stage = TapeFile.RESTORED
                            f.save()
                        # update the restore_disk
                        if f.restore_disk:
                            f.restore_disk.update()
        log_file.close()


def fix_missing_files():
    """Due to errors, such as running the scripts as the wrong user(!), some links may be
       created to files that do not actually exist.
       This function removes the links and sets the file's status back to ONTAPE.  These files will
       then restore the files to the restore area if the files are part of a *TapeRequest*"""
    # get all the tape requests and loop over them
    tape_requests = TapeRequest.objects.all()
    for tr in tape_requests:
        # loop over the files which have been restored in the tape request
        for f in tr.files.filter(Q(stage=TapeFile.RESTORED) | Q(stage=TapeFile.RESTORING)):
            if not os.path.exists(f.logical_path):# and os.path.lexists(f.logical_path):
                print (f.logical_path, os.path.lexists(f.logical_path))
                continue
                # unlink
                print "Removing link to: " + f.logical_path
                os.remove(f.logical_path)
                # set the stage to "ONTAPE"
                f.stage = TapeFile.ONTAPE
                f.restore_disk = None
                f.save()
        # loop over any files that are ONDISK but actually missing
        for f in tr.files.filter(stage=TapeFile.ONDISK):
            if not os.path.exists(f.logical_path):
                # set the stage to unverified
                f.stage = TapeFile.UNVERIFIED
                f.restore_disk = None
                f.save()


def fix_links():
    """Fix any files that are stuck in RESTORING mode where the file actually exists in the restore area
       but the symbolic link does not exist.  Fix by creating a symbolic link and setting the stage to RESTORED
    """
    # load the storage path mapping
    TapeFile.load_storage_paths()
    # get all the restoring files
    tape_files = TapeFile.objects.filter(Q(stage=TapeFile.RESTORING) | Q(stage=TapeFile.RESTORED))

    for tf in tape_files.all():
        if not os.path.exists(tf.logical_path) and tf.restore_disk:
            # build the restored spot path
            spot_logical_path, spot_name = tf.spotname()
            restore_path = tf.restore_disk.mountpoint+tf.logical_path.replace(spot_logical_path, "/archive/%s" % spot_name)
            # create the link if the restore path exists
            if os.path.exists(restore_path):
                try:
                    os.symlink(restore_path, tf.logical_path)
                    tf.stage = TapeFile.RESTORED
                    tf.save()
                    print "LINKED: " + tf.logical_path + " & " + restore_path
                except:
                    print "FAILED TO LINK: " + tf.logical_path + " & " + restore_path
            else:
                print "RESTORE PATH DOES NOT EXIST: " + tf.logical_path + " & " + restore_path
                if os.path.exists(tf.logical_path):
                    os.unlink(tf.logical_path)
                tf.stage = TapeFile.ONTAPE
                tf.save()


def create_request_for_on_disk_files():
    """Create a TapeRequest containing all the files that are currently listed as being ONDISK, but are not part of
       a _VERIFY process request.  This enables files that are stuck in the ONDISK stage to be moved to tape"""

    # make a tape file request so all fixed files belong to a request. This request
    # belongs to the _VERIFY quota.
    quota = Quota.objects.filter(user="_VERIFY")
    quota = quota[0]

    now = datetime.datetime.now(utc)
    retention = now + datetime.timedelta(days=1)
    tape_request = TapeRequest(quota=quota, retention=retention, storaged_request_start=now, storaged_request_end=now,
                               first_files_on_disk=now, last_files_on_disk=now, label="FROM FIX PROBLEMS")
    tape_request.save()

    # get a list of files that are ONDISK
    tape_files = TapeFile.objects.filter(stage=TapeFile.ONDISK)
    for tf in tape_files:
        # check whether this file is in another request
        in_other_request = False
        now = datetime.datetime.now(utc)
        for tr in TapeRequest.objects.filter(retention__gte=now):
            if tf in tr.files.all():
                print "Other request has requested this file.", tf.logical_path
                in_other_request = True
                break
        qset = TapeRequest.objects.filter(files=tf)
        if len(qset) != 0:
            in_other_request = True
        if not in_other_request:
            print tf.logical_path
            tape_request.request_files += tf.logical_path + "\n"

    tape_request.save()


def clean_up_restore_disk():
    """Clean up the restore disk by removing files from requests that have been expired."""
    # get a mapping of spot to logical paths
    spot_to_logical_path_mapping = get_spot_to_logical_path_mapping()
    # get the time to check for expired requests
    now = datetime.datetime.now()

    # loop over the restore disks
    for rd in RestoreDisk.objects.all():
        # get a list of the retrieve files
        retrieve_files = glob.glob(os.path.join(rd.mountpoint, "retr*ve_listing_*"))
        # loop over the files
        for rf in retrieve_files:
            # get the request_id
            req_id = int(rf.split("_")[-1][:-4])
            # flag to keep track of whether to delete or not
            delete = False
            # get the tape request
            try:
                tape_req = TapeRequest.objects.get(pk=req_id)
            except:
                # tape_req does not exist so set delete to true
                delete = True
            # if we are to delete, open the retrieval file
            if delete:
                fh = open(rf)
                # get the file names
                fnames = fh.readlines()
                for fn in fnames:
                    fname = fn.strip()
                    # build the filepath and see if it exists
                    if len(fname) > 0:
                        fp = str(os.path.join(rd.mountpoint, fname[1:]))
                        try:
                            logical_path = ""
                            if os.path.exists(fp):
                                # get the spot name
                                file_name_cmpts = fp.split("/")
                                for i in range(0, len(file_name_cmpts)):
                                    fnc = file_name_cmpts[i]
                                    # get the logical path name
                                    if "spot" in fnc:
                                        logical_path = spot_to_logical_path_mapping[fnc]
                                        for j in range(i+1, len(file_name_cmpts)):
                                            logical_path += "/" + file_name_cmpts[j]
                                        break
                            if logical_path != "":
                                # get the tapefile object
                                tape_file = TapeFile.objects.get(logical_path=logical_path)
                                # unlink the archived file if it exists and tape file stage is ONTAPE
                                if tape_file.stage == TapeFile.ONTAPE:
                                    print ("Deleting " + str(fp))
                                    os.unlink(fp)
                                
                        except:
                            pass
                fh.close()

def deactivate_all_taperequests():
    """Set active in all taperequests to false"""
    # get all the tape requests and loop over them
    tape_requests = TapeRequest.objects.all()
    for tr in tape_requests:
        tr.active_request = False
        tr.save()

def reset_files_no_verify_date():
    """Find all the files that have no verification date, but have a stage other than UNVERIFIED,
    and reset their stage to UNVERIFIED"""
    tape_files = TapeFile.objects.filter(Q(verified=None) & ~Q(stage=TapeFile.UNVERIFIED))
    print ("{} files have no verification date".format(tape_files.count()))
    for t in tape_files:
        if t.stage == TapeFile.ONTAPE:
            t.stage = TapeFile.UNVERIFIED
            t.save()

def reset_removed_files():
    """From a list of logical paths in the file /home/badc/missing_files.txt, find the
       files that do not exist in the NLA but do on the tape and restore the status of those
       on the tape."""
    # we need the logical path to spot path mapping
    TapeFile.load_storage_paths()
    fpath = "/home/badc/missing_files.txt"
    fh = open(fpath, 'r')
    files = fh.read().split("\n")
    # a dictionary of spotnames and files
    spot_files = {}
    for f in files:
        if len(f) == 0:
            continue
        # get the spot from the filepath
        # find the longest logical path that matches
        found = False
        file_path = f
        while not found and len(file_path) > 0:
            # get the sub path
            try:
                spot_name = TapeFile.fileset_logical_path_map[file_path]
                found = True
            except:
                found = False
                file_path = os.path.dirname(file_path)
        
        if found:
            if spot_name in spot_files:
                spot_files[spot_name].append(f)
            else:
                spot_files[spot_name] = [f]

    print(spot_files)
    stages = ["ONTAPE", "RESTORING", "ONDISK", "UNVERIFIED", "RESTORED"]

    # for each spot run sd_ls on the spot name to get the list of files in the spot back
    for spot_name in spot_files:
        sd_cmd = ["/usr/bin/python2.7", "/usr/bin/sd_ls", "-s", spot_name, "-L", "file"]
        output = subprocess.check_output(sd_cmd)
        out_lines = output.split("\n")
        for out_item in out_lines:
            out_file = out_item.split()
            if len(out_file) == 11:
                file_name = os.path.basename(out_file[10])
                size = out_file[1]
                for f in spot_files[spot_name]:
                    if file_name in f:
                        # see if this record exists as a TapeFile
                        try:
                            tf = TapeFile.objects.get(logical_path = f)
                            status = stages[tf.stage]
                        except:
                            status = "UNKNOWN"

                        # recreate the TapeFile record if its status is UNKNOWN
                        if status == "UNKNOWN":
                            tf = TapeFile(logical_path=f, size=int(size), stage=TapeFile.ONTAPE)
                            tf.save()
                            print("Re-added file: ", f)

    fh.close()
        

def run(*args):
    """Entry point for the Django script run via ``./manage.py runscript``
   Arguments (passed via --script-args) will run the corresponding function
   Available fixes:
       fix_links
       clear_slots
       set_restoring_files_to_ontape
       reset_stuck_taperequests
       deactivate_taperequests
       fix_symbolic_links
       create_request_for_on_disk_files
       clean_up_restore_disk
       deactivate_all_taperequests
       reset_files_no_verify_date
       reset_removed_files
    """

    if len(args) == 0:
        print run.__doc__

    for a in args:
        if a == "-h" or a == "--help":
            print run.__doc__
        method = globals().get(a)
        try:
            method()
        except Exception as e:
            print "Failed running fix problem method: " + a + " " + str(e)
