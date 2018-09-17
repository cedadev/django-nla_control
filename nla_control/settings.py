# NRM - moved this into an app specific settings file, rather than a site-wide settings file
# -------------------------------------------------
# nla specific settings

import os

STORAGED_SLOTS = 5
MAX_SLOTS_PER_USER = 5

# NRM 06/12/2016 - set this variable to True to use a test version that uses a local disk
# store as an analogue for the NLA tape system
# This will need a Django server with the NLA system and cedaarchive app running on it
TEST_VERSION = False

if not TEST_VERSION:
    # This is the url that contains the mappings between spots and logical paths
    # NRM note - this URL will change when new cedaarchiveapp is deployed
    CEDA_ARCAPP_BASE = 'http://cedaarchiveapp.ceda.ac.uk/cedaarchiveapp/'
    CEDA_DOWNLOAD_CONF = CEDA_ARCAPP_BASE+'fileset/download_conf'

    # This is the url that contains the mapping between the storage path and the spots
    # NRM note - this URL will change when new cedaarchiveapp is deployed
    STORAGE_PATHS_URL = CEDA_ARCAPP_BASE+'storage-d/spotlist?withpath'

    # This is the url that contains the location of the api call to get the files which are marked "primary on tape"
    ON_TAPE_URL = CEDA_ARCAPP_BASE+'fileset/primary_on_tape'

    # host of storage-D retrieval
    SD_HOST = 'ceda_sd-retrieval.fds.rl.ac.uk'
    MIN_FILE_SIZE = 30 * 1024 * 1024 # (30 Mb)

    CHKSUMSDIR = "/datacentre/stats/storaged/chksums"

else:
    # set the url (0.0.0.0:80) of the spot and logical paths
    # this local url should be where the Django site is running with the cedaarchiveapp
    # note that port 80 is used here as this is run on the VM, where port 80 is port 80,
    # rather than it being a forwarded port (e.g. 8031)
    CEDA_DOWNLOAD_CONF = 'http://0.0.0.0:80/cedaarchiveapp/fileset/download_conf'
    STORAGE_PATHS_URL = 'http://0.0.0.0:80/cedaarchiveapp/storage-d/spotlist?withpath'
    ON_TAPE_URL = "http://0.0.0.0:80/cedaarchiveapp/fileset/primary_on_tape"

    # host of storage-D retrieval
    SD_HOST = '?'
    MIN_FILE_SIZE = 1 * 1024 # (1 Kb)

    # directory of checksums
    CHKSUMSDIR = os.path.join(os.path.expanduser("/home/www/datacentre/"), "chksums")

    # directory which emulates tape (in conjunction with sd_get_emulator)
    FAKE_TAPE_DIR = "/home/www/faketape"
