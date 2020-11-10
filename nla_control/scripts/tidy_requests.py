""" Tidy up files from requests where the retention time is in the past.

    Files are checked to see if they are part of another request, have been deleted or modified. If not then
    they are removed and flagged as back on tape.

    This is designed to be used via the django-extentions runscript command:

    ``$ python manage.py runscript tidy_requests``
"""

# SJP 2016-02-09

from nla_control.models import TapeFile, TapeRequest
import datetime
import sys
from pytz import utc
from nla_control.settings import *
from nla_control.scripts.process_requests import update_requests
from ceda_elasticsearch_tools.index_tools import CedaFbi, CedaEo
import subprocess

__author__ = 'sjp23'

def in_other_request(tr, f):
    # check that file is not in another request
    in_other_req = False
    now = datetime.datetime.now(utc)
    active_tape_requests = TapeRequest.objects.filter(retention__gte=now)
    file_in_requests = active_tape_requests.filter(files__id__exact = f.id)
    in_other_req = file_in_requests.count() > 0
    if (in_other_req > 0):
       	if (f.stage == TapeFile.RESTORED or f.stage == TapeFile.RESTORING):
            print("In other request {} {} {}".format(tr, f, file_in_requests))
    return in_other_req

def tidy_requests():
    """Run the tidying up of the TapeRequests.

    The algorithm is:

    - **for each** TapeRequest object whose retention time < currrent time (i.e. in the past):

      - **for each** file in the TapeRequest:

        - **if** the file does not exist on the disk but **and** a stage of RESTORED **then** delete the file
          (``move_files_to_nla.py`` will add the file back into the NLA if it is still archived on tape)

        - **if** the file has been modified **then** reset its stage to UNVERIFIED

        - **if** the file is in another request **then** move onto the next file **else**:

          - Unlink the file (delete)

          - Mark the stage of the file as ONTAPE

          - Update the restore disk to reflect that space has been freed

    """
    # Update the files portion of the tape request with those present in the NLA
    now = datetime.datetime.now(utc)
    print("Searching for expired tape requests")
    tape_requests = TapeRequest.objects.filter(retention__lt=now)
    print("Number of tape requests: ", tape_requests.count())
    print("Updating tape requests")
    for tr in tape_requests:
        print("Tape request: {}".format(tr))
        request_files = tr.request_files.split()
        n_rf = len(request_files)

        # split the request files up into batches of 1000
        n_per_batch = 100000
        tr.files.clear()
        for i in range(0, int(n_rf/n_per_batch+1)):
            batch_files = request_files[i*n_per_batch:(i+1)*n_per_batch]
            print("Processing {}/{}".format(i*len(batch_files), n_rf))
            present_tape_files = TapeFile.objects.filter(logical_path__in=batch_files)
            if len(present_tape_files) != 0:
                pf = list(present_tape_files.all())
                tr.files.add(*pf)
                tr.save()

    # list of restore disks used - cache them so that they only need to be updated once
    restore_disks = []
    print("Tidying tape requests: find tape requests...")
    for tr in tape_requests:
        # make list of files to tidy
        print(tr)
        to_remove = []

        for f in tr.files.all():
            # Check if the file does not exist on the disk anymore - but only remove it if it is still in a restored state
            if not os.path.exists(f.logical_path):
                if f.stage == TapeFile.RESTORED:
                    print("File requests exists, but file is not on the disk. Removing file from NLA:", f.logical_path)
                    #f.delete()
                continue
            file_mod = datetime.datetime.fromtimestamp(os.path.getmtime(f.logical_path), utc)
            if f.verified:
                tr_f_mod = f.verified.replace(tzinfo=file_mod.tzinfo)
                if not os.path.islink(f.logical_path) and file_mod > tr_f_mod:
                    print("File has been modified after the time it was verified. Leave it alone.")
                    print("Leaving file, but resetting as unverified %s" % f)
                    f.verified = None
                    f.stage = TapeFile.UNVERIFIED
                    f.restore_disk = None
                    f.save()
                    continue

            # check that file is not in another request
            if in_other_request(tr, f):
                continue

            # if we get here then the file exists, has not been modified since checked and is not in another request
            to_remove.append(f)

        print("Removing %s files from restored area:" % len(to_remove))
        # list of files to modify in elastic search
        removed_files = []
        for f in to_remove:
            print("     -  %s" % f)
            logical_dir = os.path.dirname(f.logical_path)
            sign_post = os.path.join(logical_dir, "00FILES_ON_TAPE")
            try:
                if not os.path.exists(sign_post):
                    if not TEST_VERSION:
                        os.symlink("/badc/ARCHIVE_INFO/FILES_ON_TAPE.txt", sign_post)
            except Exception as e:
                print("Could not create signpost: ", sign_post)
            # Commented out deletion of files for testing safety
            if f.stage == TapeFile.RESTORED:
                try:
                    f.stage = TapeFile.ONTAPE
                    # get the restore disk and update
                    if f.restore_disk and not f in restore_disks:
                        restore_disks.append(f.restore_disk)
                    # set no restore disk
                    f.restore_disk = None
                    f.save()
                    # remove link and datafile in restore cache
                    os.unlink(os.readlink(f.logical_path))
                    os.unlink(f.logical_path)
                except Exception as e:
                    print("Could not remove from restored area: ", f.logical_path)
            else:
                # removing for the first time or deleted or unverified
                try:
                    f.stage = TapeFile.ONTAPE
                    # get the restore disk and update
                    if f.restore_disk and not f in restore_disks:
                        restore_disks.append(f.restore_disk)
                    # set no restore disk
                    f.restore_disk = None
                    f.save()
                    os.unlink(f.logical_path)
                except Exception as e:
                    print("Could not remove from archive: ", f.logical_path)

            # add to list of files to be altered in Elastic Search
            removed_files.append(f.logical_path.encode("utf-8"))

        print("Setting status of files in Elastic Search to not on disk")
        try:
            # Open connection to index and update files
            if len(removed_files) > 0:
                fbi = CedaFbi(
                          headers = {
                              'x-api-key' : CEDA_FBI_API_KEY
                        }
                      )
                fbi.update_file_location(file_list=removed_files, on_disk=False)
            print("Updated Elastic Search index for files ",)
            for f in removed_files:
                print(" - " + str(f))
        except Exception as e:
            print("Failed updating Elastic Search Index ",)
            print(e, removed_files)

        print("Remove request %s" % tr)
        tr.delete()
    # update the restore disk used
    print("Updating restore disk")
    for rd in restore_disks:
        rd.update()


def run():
    """Entry point for the Django script run via ``./manage.py runscript``"""
    # First of all check if the process is running - if it is then don't start running again
    print("Starting tidy_requests")
    try:
        lines = subprocess.check_output(["ps", "-f", "-u", "badc"]).decode("utf-8").split("\n")
        n_processes = 0
        for l in lines:
            if "tidy_requests" in l and not "/bin/sh" in l:
                print(l)
                n_processes += 1
    except:
        n_processes = 1

    if n_processes > 1:
        print("Process already running, exiting")
        sys.exit()

    # otherwise run
    tidy_requests()
    print("Finished tidy_requests")
