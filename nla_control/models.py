from django.db import models
import fnmatch
import requests
from django.db.models import Sum
from django.db.models import Q

from sizefield.models import FileSizeField
from sizefield.utils import filesizeformat

from nla_site.settings import *

class RestoreDisk(models.Model):
    """Allocated area(s) of disk(s) to hold restored files.  Restore will find a space on one
       of these RestoreDisks to write the files to.

       :var models.CharField mountpoint: the path to the restore area
       :var FileSizeField allocated_bytes: the allocated size of the restore area (in bytes)
       :var FileSizeField used_bytes: the amount of space used of the restore area (in bytes).  Updated by ``update()`` method.
       """
    mountpoint = models.CharField(blank=True, max_length=1024, help_text="E.g. /badc/restore_1", unique=True)
    allocated_bytes = FileSizeField(default=0,
                                    help_text="Maximum size on the disk that can be allocated to the restore area")
    used_bytes = FileSizeField(default=0,
                               help_text="Used value calculated by update method")

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return "%s" % self.mountpoint

    def formatted_used(self):
        return filesizeformat(self.used_bytes)
    formatted_used.short_description = "used"

    def formatted_allocated(self):
        return filesizeformat(self.allocated_bytes)
    formatted_allocated.short_description = "allocated"

    def update(self):
        """Update the number of bytes used on the RestoreDisk by summing the size of each TapeFile that is restored
           to this RestoreDisk"""
        # Get all the tape files that are restored
        restored_files = TapeFile.objects.filter(stage=TapeFile.RESTORED, restore_disk=self)
        # reset the used_bytes
        self.used_bytes = 0
        for f in restored_files:
            self.used_bytes += f.size
        self.save()

class TapeFileException(Exception):
    pass

class TapeFile(models.Model):
    """Files that are archived on tape as the primary media, and have been added to the NLA system via move_files_to_nla.

       :var models.CharField logical_path: The original logical of the file in the archive, before it was moved to tape
       :var FileSizeField size: The size of the file (in bytes)
       :var models.DateTimeField verified: The time and date that the file was verified within the NLA system
       :var models.IntegerField stage: The stage that the file is at, one of **UDTAR**

          - **U**: UNVERIFIED (3)

          - **D**: ONDISK (2)

          - **T**: ONTAPE (0)

          - **A**: RESTORING (1)

          - **R**: RESTORED (5)
      
          - **X**: DELETED (4)

       :var models.ForeignKey restore_disk: A reference to the RestoreDisk where the file has been restored to
    """


    # stages for tape files
    UNVERIFIED = 0
    ONTAPE = 1
    RESTORING = 2
    ONDISK = 3
    DELETED = 4    # NRM - deleted has been restored
    RESTORED = 5
    __CHOICES = ((ONTAPE, 'On tape'), (RESTORING, 'Restoring'), 
                 (ONDISK, 'On Disk'), (UNVERIFIED, 'Unverified'), (RESTORED, 'Restored'),
                 (DELETED, 'Deleted'))

    STAGE_NAMES = ["UNVERIFIED", "ON TAPE", "restoring", "on disk", "DELETED", "RESTORED"]

    logical_path = models.CharField(max_length=2024, help_text='logical path of archived files e.g. /badc/acsoe/file10.dat', db_index=True)
    size = FileSizeField(help_text='size of file in bytes')
    verified = models.DateTimeField(blank=True, null=True, help_text="Checked tape copy is same as disk copy")
    stage = models.IntegerField(choices=__CHOICES, db_index=True)

    # which restore disk is the restored file on?
    restore_disk = models.ForeignKey(RestoreDisk, blank=True, null=True,
                                     on_delete=models.SET_NULL)

    @staticmethod
    def load_storage_paths():
        """Load the fileset logical paths to spotname mappings by retrieving the spotnames from a URL,
           finding the corresponding logical path for the spot and reformatiing them into a dictionary"""

        response = requests.get(CEDA_DOWNLOAD_CONF)
        if response.status_code != 200:
            raise TapeFileException("Cannot find url: {}".format(CEDA_DOWNLOAD_CONF))
        else:
            page = response.text.split("\n")

        TapeFile.fileset_logical_path_map = {}
        TapeFile.fileset_logical_paths = []

        # make a dictotionary that maps logical paths to spot names
        for line in page:
            line = str(line.strip())
            if line == '':
                continue
            spot_name, logical_path = line.split()
            TapeFile.fileset_logical_path_map[logical_path] = spot_name
            TapeFile.fileset_logical_paths.append(logical_path)

        # reverse sort the logical paths so that longer paths match first
        TapeFile.fileset_logical_paths.sort(reverse=True)

        response = requests.get(STORAGE_PATHS_URL)
        if response.status_code != 200:
            raise TapeFileException("Cannot find url: {}".format(STORAGE_PATHS_URL))
        else:
            page = response.text.split("\n")

        TapeFile.fileset_storage_path_map = {}

        # make a dictionary that maps spot names to storage paths
        for line in page:
            line = line.strip()
            if line == '':
                continue
            storage_path, spot_name = line.split()
            TapeFile.fileset_storage_path_map[spot_name] = storage_path

    def spotname(self):
        """Return portion of path that maps to spot name, and the spotname for a file.
            e.g. ``/badc/cira/data/x.dat -> /badc/cira, spot-1234-cira``

            This function is used to give the elements needed to construct a storage path.

            :return: A tuple of (logical_spot_path, spot_name)
            :rtype: (string, string)
        """
        file_path = self._logical_path
        # find the longest logical path that matches the
        for l in TapeFile.fileset_logical_paths:
            # convert to unicode if we have to
            if file_path[:len(l)] == l:
                # start of the filename is the same as a fileset
                return l, TapeFile.fileset_logical_path_map[l]
        else:
            # There should always be a spot for a file
            raise TapeFileException("File %s has no associated fileset" % file_path)

    def storage_path(self):
        """Return the current storage path to file.

           :return: storage path of the TapeFile
           :rtype: string
        """
        logical_spot_path, spot_name = self.spotname()
        return TapeFile.fileset_storage_path_map[spot_name]

    def archive_volume_path(self):
        """Return the current volume path for a file. e.g. /datacentre/archvol/pan52/archive

          :return: volume path of the TapeFile
          :rtype: string
        """
        return os.path.dirname(self.storage_path())

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return "%s (%s)" % (self._logical_path, TapeFile.STAGE_NAMES[self.stage])

    def match(self, pattern):
        """Return whether the logical path of this TapeFile matches the input pattern (a UNIX filesystem pattern).

           :param string pattern: The UNIX filesystem pattern to match against
           :return: ``True | False``
           :rtype: boolean
        """
        return fnmatch.fnmatch(self.logical_path, pattern)

    @staticmethod
    def add(file_path, size):
        """Method to add a logical path as a TapeFile if its not already present on the NLA system.

           :param string file_path: The (original) logical path to the file, before it was archived to tape
           :param integer size: The size of the file, in bytes

        """
        existing_tape_file = TapeFile.objects.filter(logical_path=file_path)
        if len(existing_tape_file) == 0:
            TapeFile(logical_path=file_path, size=size, stage=TapeFile.UNVERIFIED).save()

    @property
    def _logical_path(self):
        slp = str(self.logical_path)
        return slp
        if slp[0] == 'b':
            return slp[2:-1]
        else:
            return slp

    def formatted_size(self):
        return filesizeformat(self.size)
    formatted_size.short_description = "size"

    def formatted_logical_path(self):
        slp = self._logical_path
        return slp
#        if slp[0] == 'b':
#            return slp[2:-1]
#        else:
#            return slp
    formatted_logical_path.short_description = "logical_path"

class Quota(models.Model):
    """Users quota for tape requests

       :var models.CharField user: identified for the user, the same as their JASMIN login
       :var FileSizeField size: The size of the quota in bytes
       :var models.CharField email_address: The email address of the user
       :var models.TextField notes: Notes about the user, affliation, project, etc.

    """
    user = models.CharField(max_length=2024)
    size = FileSizeField(help_text='size of quota in bytes')
    email_address = models.CharField(max_length=2024, blank=True, null=True, help_text='email address of user for notifications')
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return "%s (%s)" % (self.user, filesizeformat(self.size))

    def used(self, retention_date):
        """Get the amount of quota used by this user

           :param DateTime retention: the retention date.  User's requests with retention dates beyond this will be used in the calculation of the used quota.
           :return: The size of the quota in bytes.
           :rtype: integer

        """
        reqs = TapeRequest.objects.filter(quota=self, retention__gte=retention_date)
        size = 0
        for req in reqs:
            size += req.size()
        return size

    def requests(self):
        """Get the requests associated with this quota

           :return: All requests associated with this quota.
           :rtype: QuerySet[TapeRequest]
        """
        return TapeRequest.objects.filter(quota=self)

    def formatted_size(self):
        return filesizeformat(self.size)
    formatted_size.short_description = "size"

class TapeRequest(models.Model):
    """Tape file staging requests.

       :var models.CharField label: A user assigned label for the request
       :var models.ForeignKey quota: A reference to the user id (and their quota) that made the request
       :var models.DateTimeField retention: The date and time when the restored file will be removed from the restore area
       :var models.DateTimeField request_date: The time and date the request was made
       :var models.BooleanField active_request: Whether a request is currently active or not.  Modified by update_requests in process_requests.py
       :var models.DateTimeField storaged_request_start: the date and time the retrieval request started on StorageD
       :var models.DateTimeField storaged_request_end: the date and time the retrieval request concluded on StorageD
       :var models.DateTimeField first_files_on_disk: the date and time the first files arrived on the restore disk
       :var models.DateTimeField last_files_on_disk: the date and time the last files arrived on the restore disk
       :var models.ManyToManyField files: list of files in the request.  Modified by update_requests in process_requests.py
       :var models.TextField request_files: A list of files requested by the user
       :var models.CharField request_patterns: pattern to match against to retrieve files from tape
       :var models.CharField notify_on_first_file: email address to notify when first restored file is available in the restore area
       :var models.CharField notify_on_last_file: email address to notify when last file is available in restore area - i.e. the request is complete
       """
    # Requests for tape file restores
    label = models.CharField(blank=True, null=True, max_length=2024,
                                           help_text="Human readable label for request")
    quota = models.ForeignKey(Quota, help_text="User Quota for request",
                              on_delete=models.PROTECT)
    retention = models.DateTimeField(blank=True, null=True, db_index=True)
    request_date = models.DateTimeField(blank=True, null=True, auto_now_add=True)
    active_request = models.BooleanField(default=False)
    storaged_request_start = models.DateTimeField(blank=True, null=True)
    storaged_request_end = models.DateTimeField(blank=True, null=True)
    first_files_on_disk = models.DateTimeField(blank=True, null=True)
    last_files_on_disk = models.DateTimeField(blank=True, null=True)
    files = models.ManyToManyField(TapeFile, help_text="The subset of files in the request that currently exist in the NLA system")
    request_files = models.TextField(blank=True, help_text="Files selected for this request")
    request_patterns = models.CharField(blank=True, null=True, max_length=2024, default='',
                                        help_text="Original request patterns (first 2k)")
    notify_on_first_file = models.CharField(blank=True, null=True, max_length=2024,
                                            help_text="email to notify on first files")
    notify_on_last_file = models.CharField(blank=True, null=True, max_length=2024,
                                           help_text="email to notify on last files")

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        try:
            files = self.files.filter(Q(stage=TapeFile.ONDISK) | Q(stage=TapeFile.RESTORED))
            nfiles = len(files)
            request_files = self.request_files.split()
            nreqfiles = len(request_files)
            if self.label:
                return "%i : %s [%s / %s files]" % (self.pk, self.label, nfiles, nreqfiles)
            elif self.request_patterns:
                return "%i : Pattern: %s [%s files]" % (self.pk, self.request_patterns[:120], nfiles)
            elif nfiles == 0:
                return "No files requested"
            elif nfiles == 1:
                return "%i : Single File %s" % (self.pk, files[0])
            else:
                return "%i : %s ... [%s / %s files]" % (self.pk, files[0], nfiles, nreqfiles)
        except:
            return "No files present"

    def set_retention(self, retention):
        """Set the retention date for the request.  Files in the request will be maintained on disk until the retention
           date is passed.

           :param DateTime retention: The new retention date for the request
        """
        self.retention = retention
        self.save()

    def set_notify(self, on_first=None, on_last=None):
        """Set the email address for where to send the notifications of the first files arriving on disk and the
           last files arriving on disk.

           :param string on_first: email address for the first files on disk notification to be sent to
           :param string on_last: email address for the last files on disk notification to be sent to
           """
        if on_first:
            self.notify_on_first_file = on_first
        if on_last:
            self.notify_on_last_file = on_last
        self.save()

    # def monitor(self):
    #     """Monitor requested files"""
    #     files_to_monitor = self.files.filter(stage=TapeFile.RESTORING)
    #     for f in files_to_monitor:
    #         if os.path.exists(f.logical_path):
    #             pass

    def size(self):
        """Return the total size of all the files in a request.

           :return: Total size
           :returntype: integer
        """
        s = self.files.all().aggregate(tot_size=Sum('size'))
        if s['tot_size'] is None:
            return 0
        else:
            return s['tot_size']

    def first_1000_files(self):
        """Return a query set of the first 5000 files."""
        # get the tape files:
        tfiles = self.files.all()[0:5000]
        retstr = "\n".join([str(t) for t in tfiles])
        return retstr
    first_1000_files.short_description = "First 5000 files known to NLA"


    def first_1000_request_files(self):
        """Return just the first 5000 request files."""
        req_files = self.request_files.split("\n")[0:5000]
        return "\n".join(req_files)
    first_1000_request_files.short_description = "First 5000 request files"


class StorageDSlot(models.Model):
    """Storage D retrieval queue slots.

       :var models.ForeignKey tape_request: Reference to the TapeRequest in the current slot
       :var models.IntegerField pid: Process id of the instance of sd_get running for this slot
       :var models.CharField host_ip: IP address of host originating the call to sd_get
       :var models.CharField request_dir: temporary directory for files retrieved from sd_get call
       """
    tape_request = models.ForeignKey(
                    TapeRequest, on_delete=models.SET_NULL,
                    blank=True, null=True,
                    help_text="Request being dealt with by storageD",
                )
    pid = models.IntegerField(blank=True, null=True, help_text="Process id for queue request")
    #  ip adress added anticipating using many hosts for retrives
    host_ip = models.CharField(blank=True, null=True, max_length=50, help_text="ip address for the process")
    request_dir = models.CharField(blank=True, null=True, max_length=500, help_text="temporary directory for retrive")

    def __repr__(self):
        return "Slot %s" % self.pk
