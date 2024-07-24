"""
The NLA test system copies a number of files to an area of disk, which it then treats as an emulated version of
the StorageD system.  Files on StorageD have checksums associated with them that are created during the archive to
tape process: files have their checksum calculated, are archived to tape, restored from tape (into a different area)
and the checksum calculated again.  If the checksums match then the file on tape is taken to be a legitimate copy and
the file on disk can be deleted.

The NLA system uses the output from this checksumming process to determine if a file that has been marked for archive
has been successfully stored on tape.  For the test system these checksum logs do not exist.  This script creates
those checksum logs in the test system.  They have the same format as the logs produced by StorageD when archiving to
tape.
"""
__author__ = 'dhk63261' # NRM

from nla_control.models import TapeFile
from nla_site.settings import *
import datetime
import subprocess

def create_checksum_files(calc_checksum_list, CHKSUMSDIR):
    """Create a file containing the checksums.  This is used by the test system as there are no
       checksums from the backup process.  We could copy the checksum files over but the file
       paths in the checksum files would be incorrect - so easier to just recompute.

       :param List[Tuple(string,string)] calc_checksum_list: List of files to calculate checksums for.  Each Tuple
           in the list contains ``(spot_name, spot_path)``

       :param string CHKSUMDIR: Location of the check sum logs - i.e. the output directory
    """
    for checksum_pair in calc_checksum_list:
        # get the spot_name and spot_path
        spot_name, spot_path = checksum_pair

        # create the output file - with the current date / time
        now = datetime.datetime.now()
        fname = "/%s.chksums.%04i%02i%02i%02i%02i" % (spot_name, now.year, now.month, now.day, now.hour, now.minute)
        fh = open(CHKSUMSDIR + fname, 'w')
        # get all the files in the spot directory recursively
        files = [os.path.join(dp, f) for dp, dn, fn in os.walk(spot_path) for f in fn]
        for f in files:
            # calculate the md5 sum - using the system md5sum calculator from the command line
            md5_sum = subprocess.check_output(["/usr/bin/md5sum", f])
            fh.write(md5_sum)
        fh.close()


def run():
    """Function picked up by django-extensions. Calculate the checksums for each file that has been added to the
       NLA test system."""

    # don't do anything if we're not in the TEST_VERSION
    if not TEST_VERSION:
        return

    TapeFile.load_storage_paths()

    # get the unverified files
    files = TapeFile.objects.filter(stage=TapeFile.UNVERIFIED)

    # create CHKSUMDIR if not exist
    if not os.path.exists(CHKSUMSDIR):
        os.makedirs(CHKSUMSDIR)

    calc_checksum_list = []
    for f in files:
        spot_logical_path, spot_name = f.spotname()
        pair = [spot_name, spot_logical_path]
        # add the spots to the list to calculate checksums for
        if not pair in calc_checksum_list:
            calc_checksum_list.append(pair)

    create_checksum_files(calc_checksum_list, CHKSUMSDIR)