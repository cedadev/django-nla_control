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
from nla_control.settings import *
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

from ceda_elasticsearch_tools.index_tools import CedaFbi, CedaEo

def update_requests():
    """Update all of the *TapeRequests* in the NLA system and mark *TapeRequests* as active or inactive.

       *TapeRequests* are active if:
           - There are ``request_files`` in a *TapeRequest* which are present in the NLA system and have the
             stage of being ONTAPE
           - There are files in the NLA system which match ``request_patterns`` and have the stage of being
             ONTAPE

       This allows requests to be made for files that are not currently in the NLA system but may be made
       available in the future.  This in turn allows users to request files that they know will be appearing
       (for example Sentinel data) without having to submit further requests.

    """
    requests = TapeRequest.objects.all().order_by('request_date')

    for r in requests:
        new_files = []
        present_tape_files = []
        print("    Request ID " + str(r.id) + " user " + r.quota.user,)
        # check whether the number of files downloaded is the same number as requested and continue if it is
        nfiles = r.files.filter(Q(stage=TapeFile.ONDISK) | Q(stage=TapeFile.RESTORED))
        nreq_files = len(r.request_files.split())
        if nfiles == nreq_files:
            print("        deactivating as completed")
            r.active_request = False
            r.save()
            continue
        if r.quota.user == "_VERIFY":
            # Special case for verify to speed up process_requests
            request_files = r.request_files.split()
            present_tape_files = TapeFile.objects.filter(Q(stage=TapeFile.UNVERIFIED) & Q(logical_path__in=request_files))
            if len(present_tape_files) != 0:
                r.active_request = True
                r.files.set(present_tape_files.all())
                r.save()
                print("       making active with " + str(present_tape_files.count()) + " new files")
            else:
                print()
            continue

        elif r.request_files != "":
            # if the request is a file request
            # get the files in the request
            request_files = r.request_files.split()
            # get the TapeFile QuerySet for the files that are in the request and present on tape in the NLA system
            new_files = TapeFile.objects.filter((Q(stage=TapeFile.ONTAPE) | Q(stage=TapeFile.RESTORING)) & Q(logical_path__in=request_files))

        elif r.request_patterns != "":
            # if the request is a pattern request
            new_files = TapeFile.objects.filter((Q(stage=TapeFile.ONTAPE) | Q(stage=TapeFile.RESTORING)) & Q(logical_path__contains=r.request_patterns))

        if new_files.count() != 0:
            r.files.add(*(list(new_files.all())))
            r.active_request = True
            print("	  making active with " + str(new_files.count()) + " new files")
            r.save()
        else:
            print("	  making inactive as no new files")
            r.active_request = False
            r.save()


def adjust_slots():
    """Create or remove storage D slots if the current number of slots is different to the value of
    ``STORAGED_SLOTS`` in ``settings.py``.  If ``STORAGED_SLOTS`` is higher than the current number of slots
    then just append some slots.  If it is lower than the current number of slots then delete the last slots."""

    number_of_slots = len(StorageDSlot.objects.all())
    if number_of_slots < STORAGED_SLOTS:
        for i in range(STORAGED_SLOTS - number_of_slots):
            StorageDSlot().save()
    elif number_of_slots > STORAGED_SLOTS:
        slots = StorageDSlot.objects.filter(tape_request=None).order_by('-pk')
        for slot in slots[:number_of_slots - STORAGED_SLOTS]:
            slot.delete()


def load_slots():
    """Fill the slots with currently active requests.
    The algorithm runs until no slots or no requests are left, thereby maximising the utilisation of the slots.
    Users are only allowed to use a certain number of slots concurrently - this value is set in ``MAX_SLOTS_PER_USER``
    in ``settings.py``.
    """
    # first come first served
    requests = TapeRequest.objects.filter(active_request=True).order_by('request_date')
    irequest = 0

    # loop over all the slots, look for a request to add to it
    slots = StorageDSlot.objects.all()
    for s in range(0, slots.count()):
        # if the slot is not None, then it is occupied
        if slots[s].tape_request is not None:
            # if the slot continues a non-active (completed) request then reset the slot
            if not slots[s].tape_request.active_request:
                slot = slots[s]
                print("Removing request {} from slot {} as request is no longer active".format(
                          slot.tape_request.pk, slot.pk)
                     )
                slot.tape_request = None
                slot.save()
            else:
                continue

        # find the next request
        while irequest < requests.count():
            # check whether this request is already in a slot
            if StorageDSlot.objects.filter(tape_request=requests[irequest]).count() != 0:
                # on to the next one
                irequest += 1
                continue

            # get the user from the request
            quota_user = requests[irequest].quota.user

            # don't process requests from the "_VERIFY" user
            if quota_user == "_VERIFY":
                irequest += 1
                continue

            # get the number of requests the user already has in the slots
            user_slots = 0
            for ts in slots:
                if ts.tape_request != None:
                    if ts.tape_request.quota.user == quota_user:
                        user_slots += 1

            # don't allow the user to add another request if they have gone over their quota
            if user_slots + 1 > MAX_SLOTS_PER_USER:
                # need to go onto the next request
                irequest += 1
       	    else:
       	       	break

        # check if any requests left to add - end loop if not
        if irequest >= requests.count():
            break

        # assign the request to the slot
       	slot = slots[s]
        slot.tape_request = requests[irequest]
        print("Assigning request {} to slot {}".format(
                   slot.tape_request.pk, slot.pk)
             )
       	slot.save()
       	irequest += 1

def run():
    """ Entry point for the Django script run via ``./manage.py runscript``

        The algorithm / order to run the above functions is
          - ``update_requests``

          - ``adjust_slots``

          - ``load slots``

    """

    # First of all check if the process is running - if it is then don't start running again
    try:
        lines = subprocess.check_output(["ps", "-f", "-u", "badc"]).decode("utf-8").split("\n")
        n_processes = 0
        for l in lines:
            if "process_requests" in l and not "/bin/sh" in l:
                n_processes += 1
    except:
        n_processes = 1

    if n_processes > 1:   # this process counts as one process_requests processx
        print("Process already running exiting")
        sys.exit()

    # update the requests to active / not active
    print("Update requests")
    update_requests()

    # make right number of slots
    print("Adjust slots")
    adjust_slots()

    # fill queue slots with requests
    print("Load slots")
    load_slots()
