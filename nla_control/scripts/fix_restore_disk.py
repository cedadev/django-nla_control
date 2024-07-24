# fix_restore_disk.py
#
"""v0.2 of NLA introduced RestoreDisks - which allow files to be restored to
multiple locations.  This adds a field to the TapeFile model (restore_disk)
for files that have been restored.
Any file that has been restored prior to v0.2 will have an empty entry for
this field.  This script fills in the field to be the first RestoreDisk

This is designed to be used via the django-extensions runscript command
``$ python manage.py runscript fix_restore_disk``
"""

# NRM 2017-02-06

# import nla objects
from nla_control.models import *
from nla_site.settings import *

def run():
    """Entry point for the Django script"""
    # get the first RestoreDisk
    restore_disk = RestoreDisk.objects.all()[0]
    
    # get the restored_files
    restored_files = TapeFile.objects.filter(stage=TapeFile.RESTORED)
    
    # loop over and set the RestoreDisk
    for f in restored_files:
        if f.restore_disk == None:
            f.restore_disk = restore_disk
            f.save()

    # update the restore disk
    for rd in RestoreDisk.objects.all():
       rd.update()
