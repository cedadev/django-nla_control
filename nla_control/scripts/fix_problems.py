""" Fix some problems that can occur with the NLA

 This is designed to be used via the django-extensions runscript command:

 ``$ python manage.py runscript fix_problems``

"""
#
# import nla objects
from nla_control.models import *
from nla_site.settings import *
import os
import re
import datetime
from pytz import utc

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
            print("Resetting file " + l_path + " to ONTAPE")
            f.stage = TapeFile.ONTAPE
            f.save()


def reset_stuck_taperequests():
    """Reset the taperequests that are stuck with a storageD request start and a no storageD request end
    """
    taperequests = TapeRequest.objects.filter(active_request=True, storaged_request_end=None).exclude(storaged_request_start=None)
    for tr in taperequests:
        print("Resetting request: " + tr.label)
        tr.storaged_request_start = None
        tr.active_request = False
        tr.save()


def deactivate_taperequests():
    taperequests = TapeRequest.objects.filter(active_request=True)
    for tr in taperequests:
        print("Deactivate request: " + tr.label)
        tr.active_request = False
        tr.save()


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
                        print(restored_archive_file_path, local_restored_path, fname)
                        # find the logical path
                        f = TapeFile.objects.filter(logical_path__contains=fname)[0]
                        # link file to final archive location
                        if not os.path.exists(f.logical_path) or os.path.islink(f.logical_path):
                            os.symlink(local_restored_path, f.logical_path)
                            f.stage = TapeFile.RESTORED
                            f.save()
                        # update the restore_disk
                        target_disk.update()
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
        for f in tr.files.filter(stage=TapeFile.RESTORED):
            if not os.path.exists(f.logical_path) and os.path.lexists(f.logical_path):
                # unlink
                print("Removing link to: " + f.logical_path)
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
    tape_files = TapeFile.objects.filter(stage=TapeFile.RESTORING)

    for tf in tape_files.all():
        if not os.path.exists(tf.logical_path) and tf.restore_disk:
            # build the restored spot path
            spot_logical_path, spot_name = tf.spotname()
            restore_path = tf.restore_disk.mountpoint+tf.logical_path.replace(spot_logical_path, "/archive/%s" % spot_name)
            # create the link if the restore path exists
            if os.path.exists(restore_path):
                print("LINKING: " + tf.logical_path + " & " + restore_path)
                os.symlink(restore_path, tf.logical_path)
                tf.stage = TapeFile.RESTORED
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
#        for tr in TapeRequest.objects.filter(retention__gte=now):
#            if tf in tr.files.all():
#                print "Other request has requested this file.", tf.logical_path
#                in_other_request = True
#                break
        qset = TapeRequest.objects.filter(files=tf)
        if len(qset) != 0:
            in_other_request = True
        if not in_other_request:
            print(tf.logical_path)
            tape_request.request_files += tf.logical_path + "\n"

    tape_request.save()


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
    """

    if len(args) == 0:
        print(run.__doc__)

    for a in args:
        if a == "-h" or a == "--help":
            print(run.__doc__)
        method = globals().get(a)
        try:
            method()
        except:
            print("Fix problem method: " + a + " does not exist as a function")
