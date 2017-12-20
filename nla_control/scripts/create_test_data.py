"""
The NLA test system copies a number of files to an area of disk, which it then treats as an emulated version of
the StorageD system.  These files need to be added to the NLA test system, as entries into the underlying database.
This could be done manually via the Django admin interface.  This script adds the ukmo-mslp dataset from the archive
(``/badc/ukmo-mslp/data``) to the NLA test system.
"""

import sys
sys.path.append("/home/www/nla_test/cedaarchiveapp")

from cedaarchiveapp.models import FileSet, Partition
from datetime import datetime
import os

def run():
    """Entry point for the Django script.

    First create a *Partition* for the data to reside in.

    Then create the ukmo-mslp *Fileset*, including creating the logical_path and setting the *Fileset* to
    be ``primary_on_tape = True``."""
    # Create a test partition and test fileset

    # Partition first - check if it exists
    p = Partition()
    p.mountpoint = "/home/www/partition1"
    p.used_bytes = 0
    p.capacity_bytes = 10 * 1000 * 1000 * 1000  # 10 Gb
    p.last_checked = datetime.utcnow()
    p.status = "Allocating"
    results = Partition.objects.filter(mountpoint = p.mountpoint)
    if len(results) == 0:
        p.save()

    # Now create the logical path of the fileset
    logicalpath = "/home/www/badc/ukmo-mslp"

    # create the fileset if it doesn't already exist
    results = FileSet.objects.filter(logical_path = logicalpath)
    if len(results) == 0:
        # unlink if path exists, but logical path not in database
        print(os.path.islink(logicalpath))
        if os.path.islink(logicalpath):
            os.unlink(logicalpath)
        # now create fileset to hold ukmo-mslp data
        f = FileSet()
        f_size = 270 * 1000 * 1000
        f.make_fileset(logicalpath, f_size, on_tape=True)
        f.primary_on_tape = True
        f.sd_backup = True
        f.save()
