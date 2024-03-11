""" Fix some problems that can occur with the NLA

 This is designed to be used via the django-extensions runscript command:

 ``$ python manage.py runscript fix_problems``

"""
#
# import nla objects
from django.db.models import Count
from nla_control.models import *
from nla_control.settings import *
from nla_control.scripts.tidy_requests import in_other_request
import nla_control
import os
import re
import datetime
import glob
import sys
from pytz import utc
from django.db.models import Q
import requests
import subprocess
from sizefield.utils import filesizeformat

global pk
pk=None

def get_spot_contents(spot_name):
    """Get a list of the files in the spot `spot_name`"""

    sd_cmd = ["/usr/bin/python2.7", "/usr/bin/sd_ls", "-s", spot_name, "-L", "file"]
    try:
        output = subprocess.check_output(sd_cmd).decode("utf-8")
    except subprocess.CalledProcessError:
        return []

    out_lines = output.split("\n")
    spot_files = []
    for out_item in out_lines:
        out_file = out_item.split()
        if len(out_file) == 11:
            file_name = out_file[10]
            spot_files.append(os.path.basename(file_name))
    return spot_files

def clear_slots():
    """Remove all tasks from the slots directory"""
    for slot in StorageDSlot.objects.all():
        # reset slot if pid is None and no pk specified
        if pk is None and slot.pid is None:
            slot.pid = None
            slot.host_ip = None
            slot.tape_request = None
            slot.save()
        # if the slot matches the pk then force the removal
        if pk is not None and slot.pk == int(pk):
            print("Clear slot {}".format(slot.pk))
            slot.pid = None
            slot.host_ip = None
            slot.tape_request = None
            slot.save()


def set_restoring_files_to_ontape():
    """Set all files that are stuck in a "RESTORING" state to "ONTAPE"
    """
    if pk == None:
        files = TapeFile.objects.filter(stage=TapeFile.RESTORING)
    else:
        req = TapeRequest.objects.get(pk=pk)
        files = req.files.filter(stage=TapeFile.RESTORING)
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
                        print(local_restored_path, f.logical_path)
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


def fix_missing_links():
    """Due to errors, such as running the scripts as the wrong user(!), some links may be
       created to files that do not actually exist.
       This function removes the links and sets the file's status back to ONTAPE.  These files will
       then restore the files to the restore area if the files are part of a *TapeRequest*"""
    # get all the restored and restoring files
    DUMMY_RUN = False

    # loop over any files that are ONTAPE but have a link
    tape_files = TapeFile.objects.filter(Q(stage=TapeFile.ONTAPE))
    for f in tape_files:
        if os.path.lexists(f.logical_path):
            if os.path.exists(f.logical_path):
                if not DUMMY_RUN:
                    print("Restoring link to: " + f.logical_path)
                    # restore status to RESTORED
                    f.stage = TapeFile.RESTORED
                    f.save()
            else:
                if not DUMMY_RUN:
                    print("Removing link (1) to: " + f.logical_path)
                    os.unlink(f.logical_path)
                    f.stage = TapeFile.ONTAPE
                    f.restore_disk = None
                    f.save()

    tape_files = TapeFile.objects.filter(Q(stage=TapeFile.RESTORING) | Q(stage=TapeFile.RESTORED))
    for f in tape_files:
        if not os.path.exists(f.logical_path) and os.path.lexists(f.logical_path):
            # unlink
            print("Removing link (2) to: " + f.logical_path)
            if not DUMMY_RUN:
                os.unlink(f.logical_path)
                # set the stage to "ONTAPE"
                f.stage = TapeFile.ONTAPE
                f.restore_disk = None
                f.save()

    # loop over any files that are ONDISK but actually missing
    tape_files = TapeFile.objects.filter(Q(stage=TapeFile.ONDISK))
    for f in tape_files:
        if not os.path.exists(f.logical_path):
            print("File not found: " + f.logical_path)
            if not DUMMY_RUN:
                # set the stage to ONTAPE
                f.stage = TapeFile.ONTAPE
                f.restore_disk = None
                f.save()
    

def fix_restore_links():
    """Fix any files that are stuck in RESTORING mode where the file actually exists in the restore area
       but the symbolic link does not exist.  Fix by creating a symbolic link and setting the stage to RESTORED
    """
    # load the storage path mapping
    TapeFile.load_storage_paths()
    # get all the restoring files
    tape_files = TapeFile.objects.filter(Q(stage=TapeFile.RESTORING) | Q(stage=TapeFile.RESTORED))

    for tf in tape_files.all():
        if not os.path.exists(tf.logical_path):
            if tf.restore_disk:
                # build the restored spot path
                spot_logical_path, spot_name = tf.spotname()
                restore_path = tf.restore_disk.mountpoint+tf.logical_path.replace(spot_logical_path, "/archive/%s" % spot_name)
                # create the link if the restore path exists
                if os.path.exists(restore_path):
                    try:
                        os.symlink(restore_path, tf.logical_path)
                        tf.stage = TapeFile.RESTORED
                        tf.save()
                        print("LINKED: " + tf.logical_path + " & " + restore_path)
                    except:
                        print("FAILED TO LINK: " + tf.logical_path + " & " + restore_path)
                else:
                    print("RESTORE PATH DOES NOT EXIST: " + tf.logical_path + " & " + restore_path)
                    if os.path.exists(tf.logical_path):
                        os.unlink(tf.logical_path)
                    tf.stage = TapeFile.ONTAPE
                    tf.restore_disk = None
                    tf.save()
            else:
                print("LOGICAL PATH DOES NOT EXIST: " + tf.logical_path)
                if os.path.islink(tf.logical_path):
                    os.unlink(tf.logical_path)
                tf.stage = TapeFile.ONTAPE
                tf.restore_disk = None
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
    in_other_req = False
    for tf in tape_files:
        # check whether this file is in another request
        if in_other_request(tape_request, tf):
            in_other_req = True
            break
        qset = TapeRequest.objects.filter(files=tf)
        if len(qset) != 0:
            in_other_req = True
        if not in_other_req:
            print(tf.logical_path)
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
            try:
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
            except:
                continue


def clean_up_orphaned_files():
    """Find any files that have not been cleaned up properly from the restore disks and delete
    them if their status is ONTAPE."""
    # get a mapping of spot to logical paths
    spot_to_logical_path_mapping = get_spot_to_logical_path_mapping()
    # loop over the restore disks
    for rd in RestoreDisk.objects.all():
        # walk the directories looking for files
        archive_path = os.path.join(rd.mountpoint, 'archive')
        spot_dirs = glob.glob(os.path.join(archive_path, "spot*"))
        # loop over the spot dirs
        for spot_dir in spot_dirs:
            spot_name = os.path.basename(spot_dir)
            for root, dirs, files in os.walk(spot_dir):
                for fname in files:
                    # build the logical path - add the extra sub directory if present (will not contain "spot")
                    logical_root = spot_to_logical_path_mapping[spot_name]
                    if not "spot" in os.path.basename(root):
                        logical_root = os.path.join(logical_root, os.path.basename(root))
                    logical_path = os.path.join(logical_root, fname)
                    restored_path = os.path.join(root, fname)
                    # check whether it's in the db
                    try:
                        tape_file = TapeFile.objects.get(logical_path=logical_path)
                        if tape_file.stage == TapeFile.ONTAPE:
                            if os.path.exists(logical_path):
                                 print("Could not DELETE, link exists: " + str(logical_path))
                            else:
                                 print("DELETING: " + restored_path + " with logical path " + str(logical_path))
                                 os.unlink(restored_path)
                    except:
                        print("Could not find record for " + restored_path)
                        if os.path.exists(logical_path):
                            print("Link exists: " + str(logical_path))


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

def get_tape_stages():
    return ["ONTAPE", "RESTORING", "ONDISK", "UNVERIFIED", "", "RESTORED"]

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

    stages = get_tape_stages()

    # for each spot run sd_ls on the spot name to get the list of files in the spot back
    for spot_name in spot_files:
        print("Working on spot: ", spot_name, )
        # should be able to replace this with get_spot_contents
        sd_cmd = ["/usr/bin/python2.7", "/usr/bin/sd_ls", "-s", spot_name, "-L", "file"]
        print("... sd_ls completed")
        output = subprocess.check_output(sd_cmd).decode("utf-8")
        out_lines = output.split("\n")
        for out_item in out_lines:
            out_file = out_item.split()
            if len(out_file) == 11:
                file_name = os.path.basename(out_file[10])
                size = out_file[3]
                for f in spot_files[spot_name]:
                    if file_name in f:
                        # see if this record exists as a TapeFile
                        try:
                            tf = TapeFile.objects.filter(logical_path = f).order_by('pk')
                            if tf.count() > 1:
                                # more than one TapeFile with logical path due to earlier coding error
                                # delete the others
                                print("Removing duplicate file for: ", f)
                                for df in tf[1:]:
                                    df.delete()

                            tf = tf[0]
                            status = stages[tf.stage]
                        except Exception as e:
                            print(e)
                            status = "UNKNOWN"

                        # recreate the TapeFile record if its status is UNKNOWN
                        if status == "UNKNOWN":
                            tf = TapeFile(logical_path=f, size=int(size), stage=TapeFile.ONTAPE)
                            tf.save()
                            print("Re-added file: ", f)

    fh.close()


def get_spot_list(spot_name, spot_path, logical_path):
    print("Checking: ", spot_name)
    try:
        sd_cmd = ["/usr/bin/python2.7", "/usr/bin/sd_ls", "-s", spot_name, "-L", "file"]
        output = subprocess.check_output(sd_cmd).decode("utf-8")
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print ("Failed", str(e))
        output = ""
    out_lines = output.split("\n")
    file_list = []
    size_list = []
    for out_item in out_lines:
        out_file = out_item.split()
        if len(out_file) == 11:
            spot_file_name = out_file[10]
            spot_path_cmpts = spot_path.split("/")
            local_spot_path = "/" + spot_path_cmpts[-2] + "/" + spot_path_cmpts[-1]
            logical_file_name = spot_file_name.replace(local_spot_path, logical_path)
            size = int(out_file[3])
            if size > MIN_FILE_SIZE:
                file_list.append(logical_file_name)
                size_list.append(size)
    return file_list, size_list


def reset_all_removed_files():
    """Reset all the files that occur on the tape (via sd_ls) but have been removed from the NLA database"""
    response = requests.get(ON_TAPE_URL)
    if response.status_code != 200:
        raise Exception("Cannot find url: {}".format(ON_TAPE_URL))
    else:
        page = response.text.split("\n")

    print("Number of spots: {}".format(len(page)))
    stages = get_tape_stages()

    for line in page:
        line = line.strip()
        if line == '':
            continue
        spot_name, spot_path, logical_path = line.split()

        file_list, size_list = get_spot_list(spot_name, spot_path, logical_path)

	# get a list of files in the NLA that are also in the file_list
        tfs = TapeFile.objects.filter(logical_path__in = file_list)
        if tfs.count() < len(file_list):
            print ("Missing {} files".format(len(file_list) - tfs.count()))
            # list of files in the db
            db_file_list = [tf.logical_path for tf in tfs]
            for f in range(0, len(file_list)):
                fname = file_list[f]
                size = size_list[f]
                if not fname in db_file_list:
                    try:
                        tf = TapeFile(logical_path=fname, size=int(size), stage=TapeFile.ONTAPE)
                        tf.save()
                        print ("Re-adding file: {}".format(fname))
                    except KeyboardInterrupt:
                        raise
                    except Exception as e:
                        print("Exception: ", str(e))


def delete_broken_links():
    """Find any symbolic links relating to the NLA where the file it points to is no longer there."""
    tape_files = TapeFile.objects.filter(Q(stage=TapeFile.ONTAPE))
    for tf in tape_files.iterator():
        if os.path.lexists(tf.logical_path) and not os.path.exists(tf.logical_path):
            # unlink the symbolic link
            print("REMOVING broken symbolic link: {}".format(tf.logical_path))
            os.unlink(tf.logical_path)


def remove_empty_restore_directories():
    """Find any empty directories in the restore area and delete them."""
    for rd in RestoreDisk.objects.all():
        # walk the directories looking for files
        archive_path = os.path.join(rd.mountpoint, 'archive')
        spot_dirs = glob.glob(os.path.join(archive_path, "spot*"))
        # loop over the spot dirs
        for spot_dir in spot_dirs:
            for root, dirs, files in os.walk(spot_dir):
                if len(files) == 0 and len(dirs) == 0:
                    print("DELETING empty directory: " + root)
                    os.rmdir(root)


def recalculate_used_space():
    """Recalculate the space used on the restore disks."""
    for rd in RestoreDisk.objects.all():
        rd.update()


def delete_files_not_in_a_request():
    """Delete those files that have the status of RESTORED but are actually not in a request"""
    # build a list of RESTORED (or RESTORING) files from the requests
    restored_files_tapereq = []
    restored_file_size = 0
    error_file_size = 0
    for tr in TapeRequest.objects.iterator():
        # list of request files
        req_files = tr.request_files.split()
        for rf in req_files:
            try:
                tf = TapeFile.objects.get(logical_path = rf)
                if tf.stage == TapeFile.RESTORED or tf.stage == TapeFile.RESTORING:
                    restored_files_tapereq.append(tf)
                    restored_file_size += tf.size
            except:
                pass
        # pattern match files
        if tr.request_patterns != "":
            pattern_files = TapeFile.objects.filter(
                (Q(stage=TapeFile.RESTORED) |
                 Q(stage=TapeFile.RESTORING)) &
                Q(logical_path__contains=tr.request_patterns)
            )
            for pf in pattern_files.iterator():
                restored_files_tapereq.append(pf)
                restored_file_size += tf.size
    # get a list of files that the NLA thinks have been restored
    restored_files_nla = TapeFile.objects.filter(Q(stage=TapeFile.RESTORED) | Q(stage=TapeFile.RESTORING))
    total_size = 0
    for rf in restored_files_nla.iterator():
        total_size += rf.size

    print("Restored files in NLA             : {}".format(restored_files_nla.count()))
    print("Restored files in requests        : {}".format(len(restored_files_tapereq)))
    print("Size of restored files in NLA     : {}".format(filesizeformat(total_size)))
    print("Size of restored files in requests: {}".format(filesizeformat(restored_file_size)))

    # delete the files from the restore area and the symbolic link
    for rf in restored_files_nla.iterator():
        if rf not in restored_files_tapereq:
            # delete the file
            full_path = os.path.realpath(rf.logical_path)
            if os.path.exists(full_path):
                os.unlink(full_path)
                print("DELETING {}".format(full_path))
            # delete the link
            if os.path.exists(rf.logical_path):
                os.unlink(rf.logical_path)
                print("UNLINK   {}".format(rf.logical_path))
            # mark as on tape and save
            rf.stage = TapeFile.ONTAPE
            rf.save()
            # add up errorneous sizes
            error_file_size += rf.size

    print("Size of deleted files: {}".format(filesizeformat(error_file_size)))


def reset_deleted_files():
    TapeFile.load_storage_paths()
    del_files = TapeFile.objects.filter(stage=TapeFile.DELETED)
    spot_contents = {}
    for df in del_files:
        # 1. check file exists on Tape
        # 2. remove any symbolic link to the logical path
        # 3. set the status to ON_TAPE
        found = False
        file_path = df.logical_path
        while not found and len(file_path) > 0:
            # get the sub path
            try:
                spot_name = TapeFile.fileset_logical_path_map[file_path]
                found = True
            except:
                found = False
                file_path = os.path.dirname(file_path)
        if found:
            # use sd_ls to find the file on tape
            if not(spot_name in spot_contents):
                spot_contents[spot_name] = get_spot_contents(spot_name)
            # use just the basenames as identifiers
            fname = os.path.basename(df.logical_path)
            if fname in spot_contents[spot_name]:
                # check if a logical link exists
                if os.path.lexists(df.logical_path):
                    # if the link points to a valid file then change to RESTORED
                    if os.path.exists(df.logical_path):
                        print("Changing file: {} to RESTORED".format(df.logical_path))
                        df.stage = TapeFile.RESTORED
                    else:
                        print("Changing file: {} to ON_TAPE and removing symbolic link".format(df.logical_path))
                        df.stage = TapeFile.ONTAPE
                        os.unlink(df.logical_path)
                    df.save()
            else:
                print("File: {} not found on via sd_ls".format(df.logical_path))
        else:
            print("File: {} not found on tape".format(df.logical_path))


def reset_unverified_files():
    """Reset the status of unverified files to ONTAPE if they are not present
       on the disk.  We should also check that they are on the tape as well."""

    # we need the logical path to spot path mapping
    TapeFile.load_storage_paths()

    # find the unverified files that are not there
    unverified_files = TapeFile.objects.filter(stage=TapeFile.UNVERIFIED)
    count = 0
    spot_contents = {}
    for uf in unverified_files:
        if not os.path.exists(uf.logical_path):
            file_path = uf.logical_path
            found = False
            # os.path.dirname will return '/' as the last character
            while not found and len(file_path) > 1:
                # get the sub path
                try:
                    spot_name = TapeFile.fileset_logical_path_map[file_path]
                    found = True
                except:
                    found = False
                    file_path = os.path.dirname(file_path)
            if found:
                # use sd_ls to find the file on tape
                if not(spot_name in spot_contents):
                    spot_contents[spot_name] = get_spot_contents(spot_name)
                # use just the basenames as identifiers
                fname = os.path.basename(uf.logical_path)
                if fname in spot_contents[spot_name]:
                    print("Changing file: {} to ONTAPE".format(uf.logical_path))
                    uf.stage = TapeFile.ONTAPE
                    uf.save()
            else:
                print("File: {} not found on tape".format(uf.logical_path))
        else:
            print("File ONDISK: {}".format(uf.logical_path))


def remove_migrated_files():
    """When storage is decommissioned, the files will be removed from it.
    If these are files that are restored by the NLA, then they will have
    the status "RESTORED".  This function finds these files and restores
    them to "ON_TAPE".
    """
    # find all the files on a particular restore disk that have stage==RESTORED
    migrated_disk = "/datacentre/archvol2/pan74/nla_restore"
    migrated_files = TapeFile.objects.filter(
                         stage=TapeFile.RESTORED,
                         restore_disk__mountpoint=migrated_disk
                     )
    for mf in migrated_files:
        mf.stage=TapeFile.ONTAPE
        print("Resetting {} to ONTAPE".format(mf.logical_path))
        mf.save()
        try:
            os.unlink(mf.logical_path)
        except OSError:
            pass


def reset_ontape_to_unverified():
    """Reset any files that are	marked as ONTAPE but actually appear on	the disk to UNVERIFIED.
       This is only if the file	is not a link."""
    ontape_files = TapeFile.objects.filter(stage=TapeFile.ONTAPE)
    for	of in ontape_files:
       	if os.path.exists(of.logical_path) and not os.path.islink(of.logical_path):
       	    print("Reset {} to UNVERIFIED".format(of.logical_path))
            of.stage = TapeFile.UNVERIFIED
            of.save()


def remap_spotpath_to_logical_path():
    """There seems to be some entries in the database with the spotname named mapped into the logical
       path field.  Possibly due to an error at some point in the move_files_to_nla script.
       This has the knock on effect that those files are not verifyable.
       This function fixes those entries, mapping them back to the logical path."""
    # get the list of UNVERIFIED files
    pattern = "/datacentre/archvol"
    unver_files = TapeFile.objects.filter(Q(stage=TapeFile.UNVERIFIED) & Q(logical_path__contains=pattern))
    print("Number of erroneous files: {}".format(unver_files.count()))
    spot_to_logical_file_mapping = get_spot_to_logical_path_mapping()

    # dictionary to store spot contents to minimise calls to sd_ls
    spot_contents = {}

    # loop over every unverfied file that is in the wrong place!
    for f in unver_files:
        # split the filepath
        parts = f.logical_path.split("/")
        # find the spotname in the split parts
        for p in parts:
            if "spot" in p:
                spotname = p
                # get the remainder of the path
                i = parts.index(p)
                fname = "/".join(parts[i+1:]).strip("'")
                break
        # get the true logical path:
        try: 
            new_logical_path = spot_to_logical_file_mapping[spotname]
        except KeyError: 
            print("Could not find logical path for spotname {}".format(spotname))
            continue
        # join the filename onto the logical path
        new_logical_path = os.path.join(new_logical_path, fname.strip("'"))
        # check it exists before remapping it
        if os.path.exists(new_logical_path):
            print("Remap {} -> {}".format(f.logical_path, new_logical_path))
            f.logical_path = new_logical_path
            f.save()
        else:
            # look for the file on tape
            if not spotname in spot_contents:
                spot_contents[spotname] = get_spot_contents(spotname)
            if fname in spot_contents[spotname]:
                print("Remap on tape file: {} -> {}".format(f.logical_path, new_logical_path))
                f.logical_path = new_logical_path
                f.save()
            else:
                print("File does not exist {}, trying to remap {}".format(new_logical_path, f.logical_path))


def remove_files_with_spotpath():
    """Some files have /datacentre/archvol and are unverified.  Delete them from the NLA database"""
    # get the list of UNVERIFIED files
    pattern = "/datacentre/archvol"
    unver_files = TapeFile.objects.filter(Q(stage=TapeFile.UNVERIFIED) & Q(logical_path__contains=pattern))
    print("Number of erroneous files: {}".format(unver_files.count()))
    # loop over every unverfied file that is in the wrong place!
    for f in unver_files:
        print(f"Deleting file: {f} as it contains the pattern: {pattern}")
        f.delete()


def fix_logical_path_in_db():
    """Some logical paths in the db contain b''.  Remove these."""
    # get a query set of duplicates:
    tp = TapeFile.objects.filter(
	logical_path__contains="b'"
    )
    print("Number of byte encoded logical paths: {}".format(tp.count()))
    for t in tp:
        if(t.logical_path[:2] == "b'"):
            new_logical_path = t.logical_path[2:-1]
            t.logical_path = new_logical_path
            t.save()
            print(t.logical_path, new_logical_path)


def remove_duplicates():
    """Remove any duplicates of TapeFiles in the database."""
    # pk passed in as an arg sets the limit
    if pk != None:
        limit = int(pk)
    else:
        limit = TapeFile.objects.count()
    print("Limit processing of duplicates to {} files".format(limit))
    duplicates = TapeFile.objects.values(
        "logical_path"
    ).annotate(
        file_count=Count("logical_path")
    ).filter(
        file_count__gt=1
    )[:limit]
    print("Number of logical_paths with duplicates: {}".format(duplicates.count()))
    
    for fd in duplicates:
        files = TapeFile.objects.filter(logical_path=fd["logical_path"])
        # check if all instances of the TapeFiles have the same stage.  If they do
        # then we can just delete all but the first one
        file_stages = [files[x].stage for x in range(0, files.count())]
        if all(f == file_stages[0] for f in file_stages):
            for f in files[1:]:
                print("Deleting duplicate for : {} with stage : {}".format(
                          f.logical_path, TapeFile.STAGE_NAMES[f.stage])
                     )
                f.delete()
        else:
            file_stage_names = [TapeFile.STAGE_NAMES[f] for f in file_stages]

            # first case - UNVERIFIED and ON TAPE
            if "UNVERIFIED" in file_stage_names and "ON TAPE" in file_stage_names:
                # assume safely on tape
                for f in files[1:]:
                    print("Deleting duplicate for : {} with stage : {}".format(
                          f.logical_path, TapeFile.STAGE_NAMES[f.stage])
                    )
                    f.delete()
                print("Remapping : {} to stage : {}".format(
                      f.logical_path, TapeFile.STAGE_NAMES[TapeFile.ONTAPE]))
                files[0].stage = TapeFile.ONTAPE
                files[0].restore_disk = None
                files[0].save()

            # second case - all permutations of RESTORED
            elif "RESTORED" in file_stage_names:
       	       	for f in files[1:]:
                    print("Deleting duplicate for : {} with stage : {}".format(
                          f.logical_path, TapeFile.STAGE_NAMES[f.stage])
                    )
                    f.delete()
                # check if file is present - if it is then set to RESTORED, if not (or link is broken) 
                # then set to ONTAPE
                if os.path.exists(files[0].logical_path):
                    print("Remapping : {} to stage : {}".format(
                           f.logical_path, TapeFile.STAGE_NAMES[TapeFile.RESTORED]))
                    files[0].stage = TapeFile.RESTORED
                    if(files[0].restore_disk == None):
                        print("No restore disk!")
                    files[0].save()
                else:
                    print("Remapping : {} to stage : {}".format(
                          f.logical_path, TapeFile.STAGE_NAMES[TapeFile.ONTAPE]))
                    # remove the dead link
                    if os.path.lexists(files[0].logical_path):
                         os.remove(f.logical_path)
                    files[0].stage = TapeFile.ONTAPE
                    files[0].restore_disk = None
                    files[0].save()


def reset_restored_to_ontape():
    # reset files in a listfile to ontape from whatever state they are in
    if not pk:
        print("Pass in listfile filename as 2nd argument")
        return
    fh = open(pk)
    lines = fh.readlines()
    for l in lines:
        f = l.strip()
        file = TapeFile.objects.get(logical_path=f)
        if file.stage == TapeFile.RESTORED:
            file.stage = TapeFile.ONTAPE
            file.save()
            print("Reset {} to ONTAPE".format(f))


def run(*args):
    """Entry point for the Django script run via ``./manage.py runscript``
   Arguments (passed via --script-args) will run the corresponding function
   Available fixes:
       fix_restore_links
       clear_slots
       set_restoring_files_to_ontape
       reset_stuck_taperequests
       deactivate_taperequests
       fix_symbolic_links
       fix_missing_links
       create_request_for_on_disk_files
       clean_up_restore_disk
       clean_up_orphaned_files
       deactivate_all_taperequests
       reset_files_no_verify_date
       reset_removed_files
       reset_all_removed_files
       delete_broken_links
       remove_empty_restore_directories
       recalculate_used_space
       delete_files_not_in_a_request
       reset_unverified_files
       remove_migrated_files
       reset_ontape_to_unverified
       reset_restored_to_ontape
       remap_spotpath_to_logical_path
       remove_files_with_spotpath
       remove_duplicates
       fix_logical_path_in_db
       reset_deleted_files
    """

    global pk
    if len(args) == 0:
        print(run.__doc__)
        sys.exit()

    a1 = None
    a = args[0].split(",")
    a0 = a[0].strip()
    if(len(a) > 1):
        a1 = a[1].strip()

    if a0 == "-h" or a0 == "--help":
        print(run.__doc__)
    else:
        method = globals().get(a0)
        if a1 != None:
            pk = a1
        try:
            method()
        except Exception as e:
            print("Failed running fix problem method: " + a0 + " " + str(e))
