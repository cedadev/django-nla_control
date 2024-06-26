""" Process requests from users into a storage-D tape requests.

 This script makes sure all the storage-D queue slots are loaded with requests.

 Then starts a single storage-D request. Other instances of this script make this run in parallel.

 The storage-D retrieve log is monitored to note when files are moved onto disk.

 This is designed to be used via the django-extensions runscript command:

 ``$ python manage.py runscript queue_requests``

"""
#
# SJP 2016-02-09
# NRM 2017-01-25

# import nla objects
from nla_control.models import *
from nla_site.settings import *
import nla_control

from django.core.mail import send_mail
from django.db.models import Q

import subprocess
import datetime

import time
import re
import socket
from pytz import utc
import sys, os

from fbi_core import update_file_location


def get_restore_disk(slot):
    """Get the next restore disk with enough free space to store all the files in the request.

       :param integer slot: slot number
       :return: the mountpoint of the first restore disk with enough space to store the request
       :rtype: string
       """

    restore_disks = RestoreDisk.objects.all()

    # get the size of the files in the request
    files = slot.tape_request.files.filter(stage=TapeFile.ONTAPE)
    # if no files then just return
    if len(files) == 0:
        return restore_disks[0]
    # add up the filesize
    total_request_size = 0
    for f in files:
        # have to go via the TapeFile
        total_request_size += TapeFile.objects.filter(logical_path=f.logical_path)[0].size

    # loop over the restore_disks
    target_disk = None
    for td in restore_disks:
        # find a disk with enough free space
        if td.allocated_bytes - td.used_bytes > total_request_size:
            target_disk = td
            break

    # if a disk not found then print an error and return None
    if type(target_disk) == type(None):
        return None

    # create the directory if it doesn't exist
    if not os.path.exists(target_disk.mountpoint):
        os.makedirs(target_disk.mountpoint)

    return target_disk


def send_start_email(slot):
    """Send an email to the user to notify that the request has started.  The email address is stored in
       ``notify_on_first_file`` in the *TapeRequest*.

       :param integer slot: slot number
    """
    if not slot.tape_request.notify_on_first_file:
        return

    # to address is notify_on_first
    toaddrs = [slot.tape_request.notify_on_first_file]
    # from address is just a dummy address
    fromaddr = "support@ceda.ac.uk"

    # subject
    subject = "[NLA] - Tape request %i has started" % slot.tape_request.id
    msg = "Request contains files: "
    for f in slot.tape_request.files.all():
        msg += "\n" + f.logical_path

    send_mail(subject, msg, fromaddr, toaddrs, fail_silently=False)


def send_end_email(slot):
    """Send an email to the user to notify that the request has finished. The email address is stored in
       ``notify_on_last_file`` in the *TapeRequest*.

       :param integer slot: slot number
    """
    if not slot.tape_request.notify_on_last_file:
        return

    # to address is notify_on_last
    toaddrs = [slot.tape_request.notify_on_last_file]
    # from address is just a dummy address
    fromaddr = "support@ceda.ac.uk"

    # subject
    subject = "[NLA] - Tape request %i has finished" % slot.tape_request.id
    msg = "Request contains files: "
    for f in slot.tape_request.files.all():
        msg += "\n" + f.logical_path

    send_mail(subject, msg, fromaddr, toaddrs, fail_silently=False)


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
            size = out_file[1]
            status = out_file[2]
            spot_files.append({os.path.basename(file_name) : (file_name, size, status,)})
    return spot_files


def create_retrieve_listing(slot, target_disk):
    """Create a text file (``file_listing_filename``) containing the names of the files to retrieve from StorageD.
    This text file is saved to the mountpoint of the restore disk that has been allocated for this retrieval by
    ``get_restore_disk``. The function also builds a mapping (``retrieved_to_file_map``) between a files spot name
    (physical location) and TapeFile, which includes a files logical path (symbolic link to the file from the archive
    filespace).

    :param integer slot: slot number
    :param RestoreDisk target_disk: *RestoreDisk* object containing the mountpoint where files will be written to
    :return: file_listing_filename, retrieved_to_file_map
    :rtype: Tuple(string, Dictionary[string:TapeFile])
    """

    # files to retrieve
    files = slot.tape_request.files.filter(stage=TapeFile.ONTAPE)

    # make files to retrieve in a listing file and mark files as restoring.
    file_listing_filename = os.path.join(target_disk.mountpoint, "retrieve_listing_%s.txt" % slot.tape_request.id)
    file_listing = open(file_listing_filename, "w")

    retrieved_to_file_map = {}
    spot_list = {}

    for f in files:
        try:
            spot_logical_path, spot_name = f.spotname()
        except:
            print("Spotname name not found for file: {}".format(f))
            continue
        # get a list of files in the spot if not already got
        if spot_name not in spot_list:
            spot_list[spot_name] = get_spot_contents(spot_name)
        if TEST_VERSION:
            to_retrieve = f.logical_path
        else:
            to_retrieve = f.logical_path.replace(spot_logical_path, "/archive/%s" % spot_name)

        to_check = os.path.basename(to_retrieve)
        # check it's in the spot on sd
        # spot list is now a list of dictionaries with the file name to check as the key
        spot_list_keys = [list(s.keys())[0] for s in spot_list[spot_name]]
        if to_check in spot_list_keys:
            retrieved_to_file_map[to_retrieve] = f
            file_listing.write(to_retrieve + "\n")
            f.stage = TapeFile.RESTORING
            f.restore_disk = target_disk
            f.save()
    file_listing.close()
    return file_listing_filename, retrieved_to_file_map


def start_sd_get(slot, file_listing_filename, target_disk):
    """
    Start the process of retrieving files from StorageD by calling (the command line program) sd_get, with the
    list of files created by ``create_retrieve_listing`` as input, for a single slot.  The process id of the instance
    of sd_get running for the slot is returned.  A logfile is also created, with output from sd_get being appended to
    the logfile.

    :param integer slot: slot number
    :param string file_listing_filename: the name of the text file containing the names of the files to retrieve from
        StorageD.  This file listing is created by ``create_retrieve_listing``.
    :param RestoreDisk target_disk: *RestoreDisk* object containing the mountpoint where files will be written to
    :return: process id of the instance of ``sd_get``, the name of the output log file
    :rtype: Tuple(integer, string)
    """

    # start an sd_get to retrieval cache
    log_file_name = os.path.join(target_disk.mountpoint, "retrieve_log_%s.txt" % slot.tape_request.id)
    if os.path.exists(log_file_name):  # make sure old log is removed as this may get picked up by current request
        os.unlink(log_file_name)

    # build the arg string for sd_get
    sd_get_args = ["-v", "-l", log_file_name, "-h", SD_HOST, "-r", target_disk.mountpoint, "-f", file_listing_filename]

    if TEST_VERSION:
        # get the current python running via sys.executable and the sd_get_emulator command from
        # the current PROJECT_DIR / BASE_DIR
        pth = os.path.dirname(nla_control.__file__)
        sd_get_cmd = [sys.executable, pth, "/bin/sd_get_emulator"]
        sd_get_cmd.extend(sd_get_args)
    else:
        # this is a bit hacky but sd_get uses the system python2.7, rather than the venv one
        sd_get_cmd = ["/usr/bin/python2.7", "/usr/bin/sd_get"]
        sd_get_cmd.extend(sd_get_args)

    # mark request as started
    slot.tape_request.storaged_request_start = datetime.datetime.utcnow()
    slot.tape_request.save()

    # start storage-D process and record pid and host
    p = subprocess.Popen(sd_get_cmd)
    print("Starting retrieval of file listing : {}".format(
        file_listing_filename)
    )
    slot.host_ip = socket.gethostbyname(socket.gethostname())
    slot.pid = p.pid
    slot.save()
    return p, log_file_name


def wait_sd_get(p, slot, log_file_name, target_disk, retrieved_to_file_map):
    """
    Wait for the ``sd_get`` process for a slot to finish.  The function monitors the log file (``log_file_name``)
    for reports of file restores from StorageD (carried out by ``sd_get``.  When a restored file is found, a symbolic
    link is created from its place in the restore area (*RestoreDisk* ``target_disk``) to the original logical_file_path
    location in the archive.

    :param integer p: process id of the instance of ``sd_get``
    :param integer slot: slot number
    :param string log_file_name: name of log file to append to
    :param RestoreDisk target_disk: *RestoreDisk* object containing the mountpoint where files will be written to
    :param retrieved_to_file_map: Mapping of spot filepaths to logical file paths, created by ``create_retrieve_listing``
    """
    """ """
    # setup log file to read
    files_retrieved = 0
    log_file = None
    ended = False

    while True:
        # sleep first, to allow process to start
        time.sleep(10)
        # see if process has ended
        if p.poll() is not None:
            ended = True

        # see is logfile is available yet. if not then wait a second and try again.
        if log_file is None:
            if os.path.exists(log_file_name):
                log_file = open(log_file_name)
            else:
                if ended:
                    break
                time.sleep(1)
                continue

        # check the log file for reports of file restores...
        lines = log_file.readlines()
        # keep a list of restored filenames
        restored_files = []

        for line in lines:
            # look for line with right pattern to know its finished
            if TEST_VERSION:
                m = re.search('Copying file: (.*) to (.*)', line)
            else:
                m = re.search('Saving (.*) into local file (.*)', line)
            if m:
                restored_archive_file_path = m.groups()[0]
                local_restored_path = m.groups()[1]
                files_retrieved += 1
                # move the retrieved file back to archive area.
                f = retrieved_to_file_map[restored_archive_file_path]
                # link file to final archive location
                try:
                    if os.path.exists(f.logical_path):
                        if os.path.islink(f.logical_path):
                            os.unlink(f.logical_path)
                            os.symlink(local_restored_path, f.logical_path)
                        else:
                            raise Exception("File exists and is not a link".format(f.logical_path))
                    else:
                        os.symlink(local_restored_path, f.logical_path)
                except:
                    print("Could not create symlink from {} to {}".format(f.logical_path, local_restored_path))
                else:
                    # set the first files on disk if not already set
                    if slot.tape_request.first_files_on_disk is None:
                        slot.tape_request.first_files_on_disk = datetime.datetime.utcnow()
                    f.stage = TapeFile.RESTORED
                    f.save()
                # update the restore_disk
                target_disk.update()
                # add the filename to the restored filenames
                restored_files.append(f.logical_path)
        # modify the restored files in elastic search
        try:
            if len(restored_files) > 0:
                update_file_location(path_list=restored_files, location="on_disk")
        except Exception as e:
            print("Failed updating Elastic Search Index ",)
            print(e, restored_files)
        log_file.close()
        log_file = None

        # checking to see if the process ended before we searched the log file
        if ended:
            break

def complete_request(slot):
    """Tidy up slot after a completed request.  This involves setting dates for the storaged_request_end
    and last_files_on_disk members, setting the active_request to False and clearing the slot.

       :param integer slot: slot number
    """
    print("Completing request {} on slot {}".format(
        slot.tape_request, slot.pk)
    )
    # request ended - mark request as finished
    slot.tape_request.storaged_request_end = datetime.datetime.utcnow()
    slot.tape_request.last_files_on_disk = datetime.datetime.utcnow()
    slot.tape_request.save()
    # reset slot
    slot.pid = None
    slot.host_ip = None
    slot.tape_request = None
    slot.save()


def start_retrieval(slot):
    """Function to run the storage-D retrieve for a tape request.
    This function takes a slot with an attached tape request, creates a working directory for the retrival listing,
    log file and retrieved data. It starts an sd_get command as a subprocess and monitors its progress by monitoring
    the log file and polling to see if the process is completed.

    :param integer slot: slot number to strat the request in
    """

    # don't call this if slot not filled or already started.
    assert slot.tape_request is not None, "ERROR: Can only call watch_sd_get with a full slot"

    # files to retrieve
    files = slot.tape_request.files.filter(stage=TapeFile.ONTAPE)

    # if no files need retrieving then just mark up as if finished
    if len(files) == 0:
        slot.tape_request.storaged_request_start = datetime.datetime.utcnow()
        complete_request(slot)
        return False

    # get the next free restore disk
    target_disk = get_restore_disk(slot)
    # error check - no room on the disk returns None
    if target_disk is None:
        print("ERROR: No RestoreDisks exist with enough space to hold the request")
        return False

    # create the retrieve listing file and get the mapping between the retrieve listing and the spot filename
    file_listing_filename, retrieved_to_file_map = create_retrieve_listing(slot, target_disk)

    # check whether any files actually need to be downloaded
    if len(retrieved_to_file_map) != 0:

        print("  Start request for %s on slot %s" % (slot.tape_request, slot.pk))
        # send start notification email if no files retrieved
        if slot.tape_request.files.filter(stage=TapeFile.RESTORED).count() == 0:
            send_start_email(slot)

        # start the sd_get_process
        p, log_file_name = start_sd_get(slot, file_listing_filename, target_disk)

        wait_sd_get(p, slot, log_file_name, target_disk, retrieved_to_file_map)

        # request ended - send ended email if there are no files in the request left ONTAPE or RESTORING
        if slot.tape_request.files.filter(Q(stage=TapeFile.ONTAPE) | Q(stage=TapeFile.RESTORING)).count() == 0:
            send_end_email(slot)

        # if got all the files then mark slot as empty
        if slot.tape_request.files.filter(stage=TapeFile.RESTORING).count() == 0:
            complete_request(slot)
        else:
            print("Request finished on StorageD, but all files in request not retrieved yet")
            redo_request(slot)          # mark the request to reattempt later
        return True
    else:
        # Deactivate request and make slot available to others
        slot.tape_request.save()
        slot.tape_request = None
        slot.save()
        return False


def redo_request(slot):
    """Reset a tape request so that it will be restarted.  This is used for requests with files that are stuck
       in the RESTORING stage.

       - Mark all files with stage RESTORING as ONTAPE (i.e. reset them to previous state)
       - Reset all the information in the request so that it is marked as not started

       :param integer slot: slot number to redo the request for
    """
    print("Redoing request {} on slot {}".format(
        slot.tape_request, slot.pk)
    )
    # mark unrestored files as on tape
    for f in slot.tape_request.files.filter(stage=TapeFile.RESTORING):
        f.stage = TapeFile.ONTAPE
        f.save()
    # mark tape request as not started
    slot.tape_request.storaged_request_start = None
    slot.tape_request.storaged_request_end = None
    slot.tape_request.save()
    # reset slot
    slot.pid = None
    slot.host_ip = None
    slot.tape_request = None
    slot.save()


def check_happy(slot):
    """Check the progress of the requests in each slot.  Several scenarios are accounted for:

       - The request hasn't started yet (do nothing)
       - The request is stuck in the RESTORING phase (restart the request via ``redo_requests``)
       - This script has been run from a different host (do nothing)
       - The ``sd_get`` process is still running (do nothing)
       - The ``sd_get`` process is not running but the request has started (restart the request via ``redo_requests``)

       :param integer slot: slot number to check
       """
    print("Checking slot %s" % slot)
    if slot.tape_request.storaged_request_start is None:
        # no need to tidy up an unstarted process
        print("No need to correct: not started yet.")
        return

    # look for files stuck in RESTORING state
    if slot.pid is None or slot.host_ip is None:
        start_time = slot.tape_request.storaged_request_start.replace(tzinfo=utc)
        if start_time < datetime.datetime.now(utc) + datetime.timedelta(seconds=120):
            # no port or host ip and not started
            print("Reset request: pid or host not set and not started for 120s.")
            redo_request(slot)
            return
        else:
            # wait for rest after 20 seconds
            print("No need to correct: pid or host not sec, but less than 20s old.")
            return

    if slot.host_ip != socket.gethostbyname(socket.gethostname()):
        # can't reset from different machine
        print("No need to correct: Not on right host.")
        return

    # need to test pid on this machine
    if os.path.exists("/proc/{}".format(slot.pid)):
        print("No need to correct: pid still running.")
        return
    else:
        print("Reset request: pid not running.")
        redo_request(slot)
        return

def run():
    """ Entry point for the Django script run via ``./manage.py retrieve_files``

        The algorithm / order to run the above functions is
          - **for each** slot:

            - **if** no request in the slot **then** continue to next slot

            - **if** request already active in the slot **then** check the progress of the request (``check_happy``)

            - **if** there is a new request in the slot **then**

              - load the storage paths (``TapeFile.load_storage_paths``)

              - start the retrieval of the file(s) in the request and create an active request in this slot (``start_retrieval``)

    """

    # First of all check if the process is running - if it is then don't start running again
    try:
        lines = subprocess.check_output(["ps", "-f", "-u", "badc"]).decode("utf-8").split("\n")
        n_processes = 0
        for l in lines:
            if "retrieve_files" in l and not "/bin/sh" in l:
                n_processes += 1
    except:
        n_processes = 1

    if n_processes > MAX_RETRIEVALS+1:   # this process counts as one process_requests processx
        print("Process already running {} transfers, exiting".format(MAX_RETRIEVALS))
        sys.exit()

    # flag whether storage paths are loaded
    spaths_loaded = False

    print("Start retrieval runs for a slot")

    for slot in StorageDSlot.objects.all():
        if slot.tape_request is None:
            print("  No request for slot %s" % slot.pk)
            continue
        elif slot.pid is not None:
            print("  Request for %s already active on slot %s" % (slot.tape_request, slot.pk))
            check_happy(slot)
            continue
        else:
            # load storage paths to do path translation to from logical to storage paths.
            print("  Process slot %s" % slot.pk)
            if not spaths_loaded:
                print("Load storage paths")
                TapeFile.load_storage_paths()
                spaths_loaded = True

            if start_retrieval(slot):
               break

    print("End retrieval run.")
