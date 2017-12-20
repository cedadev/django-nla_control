""" Tidy up files from requests where the retention time is in the past.

    Files are checked to see if they are part of another request, have been deleted or modified. If not then
    they are removed and flagged as back on tape.

    This is designed to be used via the django-extentions runscript command:

    ``$ python manage.py runscript tidy_requests``
"""

# SJP 2016-02-09

from nla_control.models import TapeFile, TapeRequest
import datetime
from pytz import utc
from nla_site.settings import *
from nla_control.scripts.process_requests import update_requests
from ceda_elasticsearch_tools.core.updater import ElasticsearchQuery, ElasticsearchUpdater
from nla_control.scripts.logging import setup_logging
import logging

__author__ = 'sjp23'

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
    tape_requests = TapeRequest.objects.filter(retention__lt=now)

    logging.info("Updating tape requests")
    for tr in tape_requests:
        logging.info(tr)
        request_files = tr.request_files.split()
        present_tape_files = TapeFile.objects.filter(logical_path__in=request_files)
        if len(present_tape_files) != 0:
            tr.files = present_tape_files.all()
            tr.save()

    logging.info("Tidying tape requests: find tape requests...")
    for tr in tape_requests:
        # make list of files to tidy
        logging.info(tr)
        to_remove = []

        for f in tr.files.all():
            # Check if the file does not exist on the disk anymore - but only remove it if it is still in a restored state
            if not os.path.exists(f.logical_path):
                if f.stage == TapeFile.RESTORED:
                    logging.info("    File requests exists, but file is not on the disk. Removing file from NLA:", f.logical_path)
                    f.delete()
                continue
            file_mod = datetime.datetime.fromtimestamp(os.path.getmtime(f.logical_path), utc)
            if f.verified:
                tr_f_mod = f.verified.replace(tzinfo=file_mod.tzinfo)
                if not os.path.islink(f.logical_path) and file_mod > tr_f_mod:
                    logging.info("    File has been modified after the time it was verified. Leave it alone.")
                    logging.info("    Leaving file, but resetting as unverified %s" % f)
                    f.verified = None
                    f.stage = TapeFile.UNVERIFIED
                    f.restore_disk = None
                    f.save()
                    continue

            # check that file is not in another request
            in_other_request = False
            now = datetime.datetime.now(utc)
            for tape_request in TapeRequest.objects.filter(retention__gte=now):
                if tape_request == tr:
                    continue
                if (f.stage == TapeFile.RESTORED or f.stage == TapeFile.RESTORING) and f in tape_request.files.all():
                    logging.info("    Other request has requested this file.", f.logical_path)
                    in_other_request = True
                    break

            if in_other_request:
                continue

            # if we get here then the file exists, has not been modified since checked and is not in another request
            to_remove.append(f)

        logging.info("Removing %s files from restored area:" % len(to_remove))
        # list of files to modify in elastic search
        removed_files = []
        for f in to_remove:
            logging.info("     -  %s" % f)
            logical_dir = os.path.dirname(f.logical_path)
            sign_post = os.path.join(logical_dir, "00FILES_ON_TAPE")
            if not os.path.exists(sign_post):
                if not TEST_VERSION:
                    os.symlink("/badc/ARCHIVE_INFO/FILES_ON_TAPE.txt", sign_post)
            # Commented out deletion of files for testing safety
            if f.stage == TapeFile.RESTORED:
                # remove link and datafile in restore cache
                os.unlink(os.readlink(f.logical_path))
                os.unlink(f.logical_path)
            else:
                # removing for the first time or deleted or unverified
                os.unlink(f.logical_path)
            f.stage = TapeFile.ONTAPE
            # get the restore disk and update
            if f.restore_disk:
                f.restore_disk.update()

            # set no restore disk
            f.restore_disk = None
            f.save()
            # add to list of files to be altered in Elastic Search
            removed_files.append(f.logical_path)

        logging.info("Setting status of files in Elastic Search to not on disk")
        try:
            # Get params and query
            params, query = ElasticsearchQuery.ceda_fbs()
            # Open connection to index and update files
            ElasticsearchUpdater(index="ceda-level-1",
                                 host="jasmin-es1.ceda.ac.uk",
                                 port=9200
                                 ).update_location(file_list=removed_files, params=params, search_query=query, on_disk=False)
            logging.info("Updated Elastic Search Index ", restored_files)
        except Exception as e:
            logging.error("Failed updating Elastic Search Index ", e, restored_files)

        logging.info("Remove request %s" % tr)
        tr.delete()


def run():
    """Entry point for the Django script run via ``./manage.py runscript``"""
    setup_logging(__name__)
    tidy_requests()
