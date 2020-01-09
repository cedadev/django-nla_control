"""
v0.3 of NLA introduced active requests, where requests can contain files not
currently in the NLA that will be restored as they become available.

Unfortunately a coding bug in the verify process meant that ``request_files``
fields for the VERIFY_PROCESS requests were not being filled in.

This had the side effect of those files being permanently stuck in the
ON_DISK state, so that they could not be "tidied" by the ``tidy_requests`` process
(which should set their state to be ON_TAPE) and so they could not  be restored
via the NLA system.

This script creates a new VERIFY_PROCESS *TapeRequest* to contain all the files
that have the ON_DISK state and adds those files to the request_files field in
of the new *TapeRequest*.  This ensures that the ``tidy_requests`` process can
convert the state of all of these files from ON_DISK to ON_TAPE.
"""

# import nla objects
from nla_control.models import *
from nla_site.settings import *
import datetime
import pytz

################################################################################

def run():
    """Entry point for the Django runscript."""
    # get the files with stage==ONDISK
    files = TapeFile.objects.filter(stage=TapeFile.ONDISK)

    # set the retention to be now so that process_requests and tidy_requests will pick it up now
    now = datetime.datetime.now(pytz.utc)

    # get the "_VERIFY" quota
    quota = Quota.objects.filter(user="_VERIFY")
    if len(quota) == 0:
        quota = Quota(user="_VERIFY", size=int(1e13), notes="System quota for requests from tidying.")
        quota.save()
    else:
        quota = quota[0]

    # create the tape_request
    tape_request = TapeRequest(quota=quota, retention=now, storaged_request_start=now, storaged_request_end=now,
                               first_files_on_disk=now, last_files_on_disk=now, label="FROM VERIFY PROCESS")

    num_verified_files = 0
    # loop over the files
    for f in files:
        # add the file to the TapeRequest
        tape_request.request_files += f.logical_path + "\n"
        num_verified_files += 1

    # if no files don't keep the tape request
    if num_verified_files == 0:
        tape_request.delete()
    else:
        tape_request.save()
