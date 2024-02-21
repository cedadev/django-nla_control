from nla_control.models import *
from django.db.models import Sum

def run(*args):
    # get the files with status matching args
    if args:
        # integer stage
        stage = TapeFile.STAGE_NAMES.index(str(args[0]))
    else:
        # all stages
        stage = 100

    print("STAGE ", stage, ": ", TapeFile.STAGE_NAMES[stage])

    if stage == 100:
        # get all files
        files = TapeFile.objects.all()
    else:
        files = TapeFile.objects.filter(stage=stage)
    print("Number of files in stage : ", str((len(files))))
    size = files.aggregate(Sum('size'))['size__sum']
    size = size / (1024*1024*1024*1024)
    print("Total size (TB)          : ", size)
