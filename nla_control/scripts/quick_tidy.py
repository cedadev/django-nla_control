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


def remove_expired_empty_requests():
    """Remove any expired requests that did not pull back on files - i.e. they are still all ONTAPE.
    """
    now = datetime.datetime.now(utc)
    print("Searching for expired tape requests")
    tape_requests = TapeRequest.objects.filter(retention__lt=now)
    print("Number of expired tape requests: ", tape_requests.count())

    # loop over all tape requests
    for tr in tape_requests:
        # number of completed files is this number of files - those files that are ONTAPE
        n_files = tr.files.count()
        n_files_on_tape = tr.files.filter(stage=TapeFile.ONTAPE).count()
        n_completed_files = n_files - n_files_on_tape
        if (n_completed_files == 0):
            print("Deleting request : {}, with {} files".format(tr.label, n_completed_files))
            tr.delete()

def update_expired_requests():
    """Update the expired tape requests."""
    now = datetime.datetime.now(utc)
    tape_requests = TapeRequest.objects.filter(retention__lt=now)
    print("Number of expired tape requests: ", tape_requests.count())
    print("Updating tape requests")
    for tr in tape_requests:
        print("Tape request: {}".format(tr))
        request_files = tr.request_files.split()
        n_rf = len(request_files)

        # split the request files up into batches of 10000
        n_per_batch = 10000
        tr.files.clear()
        for i in range(0, int(n_rf/n_per_batch+1)):
            batch_files = request_files[i*n_per_batch:(i+1)*n_per_batch]
            print("Processing {}/{}".format(i*len(batch_files), n_rf))
            present_tape_files = TapeFile.objects.filter(logical_path__in=batch_files)
            if len(present_tape_files) != 0:
                pf = list(present_tape_files.all())
                tr.files.add(*pf)
                tr.save()

def files_in_other_request():
    now = datetime.datetime.now(utc)
    tape_requests = TapeRequest.objects.filter(retention__lt=now)
    for tr in tape_requests:
        print("Processing: {}".format(tr))
        for f in tr.files.all():
            if in_other_request(tr, f):
                print("File in another request: ".format(f))

def run():
    """Entry point for the Django script run via ``./manage.py runscript``"""
    # First of all check if the process is running - if it is then don't start running again
    print("Starting quick_tidy")
    try:
        lines = subprocess.check_output(["ps", "-f", "-u", "badc"]).decode("utf-8").split("\n")
        n_processes = 0
        for l in lines:
            if "quick_tidy" in l and not "/bin/sh" in l:
                print(l)
                n_processes += 1
    except:
        n_processes = 1

    if n_processes > 1:
        print("Process already running, exiting")
        sys.exit()

    # otherwise run
#    remove_expired_empty_requests()
#    update_expired_requests()
    files_in_other_request()
    print("Finished quick_tidy")
